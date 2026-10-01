"""Ethernet occupancy is measured per full-duplex port, not across a fake bus."""
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
