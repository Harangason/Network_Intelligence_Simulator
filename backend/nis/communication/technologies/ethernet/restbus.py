"""Existing Ethernet restbus session and acknowledgement behavior."""
from __future__ import annotations
from typing import Any
import hashlib
from backend.nis.communication.technologies.ethernet.transport import wire_bytes

def _restbus_settings(config: dict[str, Any]) -> dict[str, Any] | None:
    raw = config.get("restbus_session")
    if raw is True:
        raw = {}
    if not isinstance(raw, dict) or raw.get("enabled", True) is False:
        return None
    return {
        "acknowledge_data": bool(raw.get("acknowledge_data", True)),
        "handshake": bool(raw.get("handshake", True)),
        "heartbeat_interval_s": max(0.05, float(raw.get("heartbeat_interval_s") or 0.5)),
        "response_delay_s": max(0.0001, float(raw.get("response_delay_ms") or 1.0) / 1000.0),
    }


def _reverse_flow(flow: dict[str, Any], receiver_index: int) -> dict[str, Any]:
    return {
        **flow,
        "source": flow["destinations"][receiver_index],
        "destinations": [flow["source"]],
        "source_port": flow["destination_ports"][receiver_index],
        "destination_ports": [flow["source_port"]],
    }


def _restbus_control_event(
    template: dict[str, Any],
    *,
    event_id: str,
    protocol_event: str,
    requested_at: float,
    payload: bytes = b"",
    receiver_index: int = 0,
    reverse: bool = False,
    tcp_flags: int | None = None,
    transport_sequence: int = 0,
    transport_acknowledgement: int = 0,
) -> dict[str, Any]:
    original_flow = template["ethernet"]
    flow = _reverse_flow(original_flow, receiver_index) if reverse else {
        **original_flow,
        "destinations": [original_flow["destinations"][receiver_index]],
        "destination_ports": [original_flow["destination_ports"][receiver_index]],
    }
    source = flow["source"]
    target = flow["destinations"][0]
    source_name = (
        (template.get("destination_names") or [target["hardware_id"]])[receiver_index]
        if reverse
        else template.get("source_name") or source["hardware_id"]
    )
    target_name = (
        template.get("source_name") or target["hardware_id"]
        if reverse
        else (template.get("destination_names") or [target["hardware_id"]])[receiver_index]
    )
    bitrate = int(template.get("configured_bitrate") or 0)
    if bitrate <= 0:
        raise ValueError("Ethernet-Trace benötigt eine positive konfigurierte Linkrate.")
    payload_hex = payload.hex(" ").upper()
    frame_bits = wire_bytes(flow, len(payload)) * 8
    event = {
        **template,
        "event_id": event_id,
        "time_s": requested_at,
        "scheduled_time_s": requested_at,
        "timestamp_unix": float(template["timestamp_unix"]) - float(template["time_s"]) + requested_at,
        "timestamp_utc": template["timestamp_utc"],
        "configured_cycle_ms": 0.0,
        "configured_latency_ms": 0.0,
        "injected_jitter_ms": 0.0,
        "sequence": -1,
        "transport_sequence_bytes": transport_sequence,
        "transport_ack_number": transport_acknowledgement,
        "sender_hardware": source["hardware_id"],
        "source_name": source_name,
        "source_logical_address": (
            (template.get("destination_logical_addresses") or [None])[receiver_index]
            if reverse else template.get("source_logical_address")
        ),
        "sender_port": source["port_id"],
        "sender_interface": source["interface_id"],
        "receiver_hardware": [target["hardware_id"]],
        "destination_names": [target_name],
        "destination_logical_addresses": [
            template.get("source_logical_address")
            if reverse else (template.get("destination_logical_addresses") or [None])[receiver_index]
        ],
        "receiver_interfaces": [target["interface_id"]],
        "receiver_ports": [target["port_id"]],
        "payload_bytes": len(payload),
        "payload_hex": payload_hex,
        "frame_bits": frame_bits,
        "base_transmission_time_s": frame_bits / bitrate,
        "frame_calculation_model": "PROJECT_IP_RESTBUS_CONTROL_V1",
        "status": "transmitted",
        "retransmission_count": 0,
        "duplicate_injected": False,
        "reordered": False,
        "retry_delay_ms": 0.0,
        "ethernet": flow,
        "src_ip": source["ip"],
        "dst_ips": [target["ip"]],
        "traffic_type": "CONTROL",
        "protocol_event": protocol_event,
        "session_id": template.get("session_id") or f"session:{template['route_id']}",
        "signals": [],
        "faults": [],
    }
    for key in ("signal", "signal_id", "signal_value", "value", "unit", "golden_value", "model_label", "behavior_type", "caused_by_event_id"):
        event.pop(key, None)
    for key in list(event):
        if key.startswith("_"):
            event.pop(key)
    if tcp_flags is not None:
        event["tcp_flags"] = tcp_flags
    return event


def _add_restbus_sessions(events: list[dict[str, Any]], config: dict[str, Any], max_events: int) -> list[dict[str, Any]]:
    settings = _restbus_settings(config)
    if settings is None:
        return events
    config = {**(config.get("parameters") or {}), **config}
    duration_s = max(0.001, float(config.get("duration_s") or config.get("duration") or 1.0))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("ethernet"):
            event["traffic_type"] = "DATA"
            event["protocol_event"] = "DATA"
            session_key = event.get("segment_id") if int(event.get("segment_count") or 1) > 1 else event["route_id"]
            event["session_id"] = f"session:{session_key}"
            grouped.setdefault(str(session_key), []).append(event)
    if not grouped:
        return events

    controls: list[dict[str, Any]] = []
    shifted_data: list[dict[str, Any]] = []
    for route_id, route_events in grouped.items():
        route_events.sort(key=lambda item: (float(item["scheduled_time_s"]), int(item["sequence"])))
        template = route_events[0]
        flow = template["ethernet"]
        protocol = str(flow["transport_protocol"]).lower()
        bitrate = int(template.get("configured_bitrate") or 0)
        if bitrate <= 0:
            raise ValueError("Ethernet-Restbus benötigt eine positive konfigurierte Linkrate.")
        control_delivery_s = wire_bytes(flow, 0) * 8 / bitrate * 2
        response_delay_s = float(settings["response_delay_s"])
        handshake_step_s = control_delivery_s + response_delay_s
        establishment_s = handshake_step_s * (3 if protocol == "tcp" else 2) if settings["handshake"] else 0.0
        client_isn = int.from_bytes(hashlib.sha256(f"{route_id}:client".encode()).digest()[:4], "big")
        server_isn = int.from_bytes(hashlib.sha256(f"{route_id}:server".encode()).digest()[:4], "big")

        if settings["handshake"]:
            for receiver_index, _receiver in enumerate(flow["destinations"]):
                if protocol == "tcp":
                    controls.extend([
                        _restbus_control_event(template, event_id=f"{route_id}:tcp-syn:{receiver_index}", protocol_event="TCP_SYN", requested_at=0.0, receiver_index=receiver_index, tcp_flags=0x02, transport_sequence=client_isn),
                        _restbus_control_event(template, event_id=f"{route_id}:tcp-syn-ack:{receiver_index}", protocol_event="TCP_SYN_ACK", requested_at=handshake_step_s, receiver_index=receiver_index, reverse=True, tcp_flags=0x12, transport_sequence=server_isn, transport_acknowledgement=client_isn + 1),
                        _restbus_control_event(template, event_id=f"{route_id}:tcp-ack:{receiver_index}", protocol_event="TCP_ACK", requested_at=handshake_step_s * 2, receiver_index=receiver_index, tcp_flags=0x10, transport_sequence=client_isn + 1, transport_acknowledgement=server_isn + 1),
                    ])
                else:
                    controls.extend([
                        _restbus_control_event(template, event_id=f"{route_id}:hello:{receiver_index}", protocol_event="SESSION_HELLO", requested_at=0.0, payload=b"HELLO", receiver_index=receiver_index),
                        _restbus_control_event(template, event_id=f"{route_id}:hello-ack:{receiver_index}", protocol_event="SESSION_HELLO_ACK", requested_at=handshake_step_s, payload=b"HELLO_ACK", receiver_index=receiver_index, reverse=True),
                    ])

        for data_event in route_events:
            shifted = {**data_event}
            shifted["scheduled_time_s"] = float(data_event["scheduled_time_s"]) + establishment_s
            shifted["time_s"] = float(data_event["time_s"]) + establishment_s
            shifted["timestamp_unix"] = float(data_event["timestamp_unix"]) + establishment_s
            if protocol == "tcp":
                shifted["tcp_flags"] = 0x18
                shifted["transport_sequence_bytes"] = client_isn + 1 + int(data_event.get("transport_sequence_bytes") or 0)
                shifted["transport_ack_number"] = server_isn + 1
            if shifted["scheduled_time_s"] <= duration_s + 1e-12:
                shifted_data.append(shifted)
                if settings["acknowledge_data"] and shifted.get("status") == "transmitted" and not config.get("_defer_restbus_acks"):
                    for receiver_index, _receiver in enumerate(flow["destinations"]):
                        data_delivery_s = float(shifted.get("base_transmission_time_s") or 0.0) * 2
                        ack_time = float(shifted["time_s"]) + data_delivery_s + response_delay_s
                        if ack_time > duration_s + 1e-12:
                            continue
                        if protocol == "tcp":
                            controls.append(_restbus_control_event(
                                template,
                                event_id=f"{shifted['event_id']}:ack:{receiver_index}",
                                protocol_event="DATA_ACK",
                                requested_at=ack_time,
                                receiver_index=receiver_index,
                                reverse=True,
                                tcp_flags=0x10,
                                transport_sequence=server_isn + 1,
                                transport_acknowledgement=int(shifted["transport_sequence_bytes"]) + int(shifted["payload_bytes"]),
                            ))
                        else:
                            controls.append(_restbus_control_event(template, event_id=f"{shifted['event_id']}:ack:{receiver_index}", protocol_event="DATA_ACK", requested_at=ack_time, payload=f"ACK:{shifted['sequence']}".encode(), receiver_index=receiver_index, reverse=True))

        heartbeat_time = establishment_s + float(settings["heartbeat_interval_s"])
        heartbeat_index = 0
        heartbeat_delivery_s = wire_bytes(flow, len(b"ALIVE? 0")) * 8 / bitrate * 2
        while heartbeat_time + heartbeat_delivery_s + response_delay_s <= duration_s + 1e-12:
            for receiver_index, _receiver in enumerate(flow["destinations"]):
                ping_payload = f"ALIVE? {heartbeat_index}".encode()
                pong_payload = f"ALIVE {heartbeat_index}".encode()
                controls.extend([
                    _restbus_control_event(template, event_id=f"{route_id}:heartbeat:{heartbeat_index}:{receiver_index}", protocol_event="HEARTBEAT", requested_at=heartbeat_time, payload=ping_payload, receiver_index=receiver_index, tcp_flags=0x18 if protocol == "tcp" else None, transport_sequence=client_isn + 1),
                    _restbus_control_event(template, event_id=f"{route_id}:heartbeat-ack:{heartbeat_index}:{receiver_index}", protocol_event="HEARTBEAT_ACK", requested_at=heartbeat_time + heartbeat_delivery_s + response_delay_s, payload=pong_payload, receiver_index=receiver_index, reverse=True, tcp_flags=0x18 if protocol == "tcp" else None, transport_sequence=server_isn + 1, transport_acknowledgement=client_isn + 1),
                ])
            heartbeat_index += 1
            heartbeat_time += float(settings["heartbeat_interval_s"])

    untouched = [event for event in events if not event.get("ethernet")]
    available_controls = max(0, max_events - len(untouched) - len(shifted_data))
    controls.sort(key=lambda item: (float(item["time_s"]), str(item["route_id"]), str(item["event_id"])))
    return untouched + shifted_data + controls[:available_controls]


def _restbus_ack_events(event, settings):
    """Acknowledge delivered data after its actual queued arrival."""
    if not settings or not settings["acknowledge_data"] or not event.get("ethernet") or event.get("traffic_type") != "DATA" or event["status"] != "transmitted":
        return []
    result = []
    for receiver_index, _ in enumerate(event["ethernet"]["destinations"]):
        kwargs = {}
        if event["ethernet"]["transport_protocol"].lower() == "tcp":
            kwargs = {"tcp_flags": 0x10, "transport_sequence": int(event.get("transport_ack_number") or 0),
                "transport_acknowledgement": int(event.get("transport_sequence_bytes") or 0) + int(event["payload_bytes"])}
        else:
            kwargs = {"payload": f"ACK:{event['sequence']}".encode()}
        result.append(_restbus_control_event(event, event_id=f"{event['event_id']}:ack:{receiver_index}",
            protocol_event="DATA_ACK", requested_at=float(event["time_s"]) + settings["response_delay_s"],
            receiver_index=receiver_index, reverse=True, **kwargs))
    return result

