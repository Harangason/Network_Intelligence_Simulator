"""Ethernet full-duplex port queues and runtime load measurement."""
from backend.nis.traces.trace_support import iso_utc as _utc

def serialize_event(event, config, trace_start, port_available_at, requested_at, network_id, transmission_s):
    flow = event["ethernet"]
    tx_key = (network_id, event["sender_hardware"], event["sender_port"], "TX")
    tx_start = max(requested_at, port_available_at.get(tx_key, 0.0))
    tx_wait = tx_start - requested_at
    queue_size = max(1, int(config.get("queue_size") or 256))
    if tx_wait / max(transmission_s, 1e-9) > queue_size and event["status"] != "dropped":
        event.update(status="dropped", drop_reason="tx_queue_overflow")
    rx_ports = []
    dropped = event["status"] == "dropped"
    tx_end = tx_start + transmission_s if not dropped else requested_at
    if not dropped:
        port_available_at[tx_key] = tx_end
    for receiver in flow["destinations"]:
        key = (network_id, receiver["hardware_id"], receiver["port_id"], "RX")
        start = max(tx_end, port_available_at.get(key, 0.0)) if not dropped else requested_at
        wait = max(0.0, start - tx_end)
        overflow = wait / max(transmission_s, 1e-9) > queue_size
        status = "dropped" if dropped or overflow else event["status"]
        end = start + transmission_s if status != "dropped" else requested_at
        if status != "dropped":
            port_available_at[key] = end
        rx_ports.append({**receiver, "start_s": start, "end_s": end, "queue_delay_ms": wait * 1000, "status": status})
    delivered = [rx for rx in rx_ports if rx["status"] != "dropped"]
    if not dropped and not delivered:
        event.update(status="dropped", drop_reason="rx_queue_overflow")
    completion = max((rx["end_s"] for rx in delivered), default=requested_at)
    queue_delay = tx_wait + max((rx["queue_delay_ms"] / 1000 for rx in delivered), default=0)
    event.update(tx_start_s=tx_start if not dropped else None, tx_end_s=tx_end if not dropped else None,
        rx_ports=rx_ports, queue_delay_ms=queue_delay * 1000,
        queue_depth_estimate=int(queue_delay / max(transmission_s, 1e-9)),
        transmission_latency_ms=transmission_s * 2000,
        end_to_end_latency_ms=(completion-requested_at)*1000 + float(event["configured_latency_ms"]) + float(event.get("retry_delay_ms") or 0),
        port_model="SWITCHED_FULL_DUPLEX_STORE_FORWARD_V1", time_s=completion,
        timestamp_unix=trace_start+completion, timestamp_utc=_utc(trace_start+completion))
    return



from collections import defaultdict


def ethernet_port_load(events, duration, window_s=.01):
    totals, buckets = defaultdict(float), defaultdict(lambda: defaultdict(float))
    def add(key, start, end):
        if start is None or end is None or end <= start:
            return
        totals[key] += end-start
        first, last = int(start / window_s), int(end / window_s)
        for bucket in range(first, last+1):
            busy = max(0, min(end, (bucket+1)*window_s) - max(start, bucket*window_s))
            buckets[key][bucket] += busy
    for event in events:
        add((event['sender_hardware'], event['sender_port'], 'TX'), event.get('tx_start_s'), event.get('tx_end_s'))
        for receiver in event.get('rx_ports', []):
            if receiver['status'] != 'dropped':
                add((receiver['hardware_id'], receiver['port_id'], 'RX'), receiver['start_s'], receiver['end_s'])
    return [{'hardware_id': key[0], 'port_id': key[1], 'direction': key[2], 'busy_s': busy,
        'average_load_percent': busy / max(.001, duration) * 100,
        'peak_load_percent': max(buckets[key].values(), default=0) / window_s * 100} for key, busy in totals.items()]
