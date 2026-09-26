"""Technology-neutral event generation and trace writers."""

from __future__ import annotations

import csv
import hashlib
from copy import deepcopy
import json
import random
from math import ceil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bus_technologies import normalize_technology_id, resolve_technology, technology_registry
from hardware_profile import iter_network_interfaces
from model_based_simulation import ModelBasedSimulationEngine
from backend.engineering.capacity.calculators import estimate_frame
from backend.engineering.capacity.transmission import release_grid
from ethernet_transport import resolve_flow, wire_bytes, packet_bytes
from event_scheduler import EventScheduler
from simulation_cancellation import check_cancellation


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _payload(route_id: str, sequence: int, size: int) -> str:
    seed = hashlib.sha256(f"{route_id}:{sequence}".encode("utf-8")).digest()
    data = (seed * ((size // len(seed)) + 1))[:size]
    return data.hex(" ").upper()


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


def _interface_index(profile: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_network: dict[str, list[dict[str, Any]]] = {}
    for node, port, interface in iter_network_interfaces(profile):
        record = {
            "hardware_id": node["id"],
            "hardware_name": node.get("name") or node["id"],
            "logical_node_address": node.get("logical_node_address"),
            "formatted_logical_node_address": node.get("formatted_logical_node_address"),
            "address_namespace": node.get("address_namespace") or "PROJECT",
            "hardware_type": str(node.get("type") or node.get("device_type") or "").lower(),
            "health": node.get("health") or "nominal",
            "port_id": port["id"],
            "interface_id": interface["id"],
            "technology": normalize_technology_id(interface.get("technology")),
            "network": interface.get("network"),
            "interface": interface,
        }
        by_id[interface["id"]] = record
        if interface.get("network"):
            by_network.setdefault(str(interface["network"]), []).append(record)
    return by_id, by_network


def _build_routes(config: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    by_id, by_network = _interface_index(profile)
    network_by_id = {
        str(network.get("id")): network
        for network in profile.get("networks") or []
        if isinstance(network, dict)
    }
    explicit = config.get("communications")
    routes: list[dict[str, Any]] = []
    if isinstance(explicit, list):
        expanded = []
        for raw in explicit:
            if not isinstance(raw, dict):
                continue
            segments = raw.get("segments") or []
            if len(segments) > 1:
                for segment in segments:
                    # A schedule belongs to one physical bus, not to the whole
                    # end-to-end route. Do not poll a CAN hop in the LIN slot.
                    local = raw if segment.get("network_id") == raw.get("network_id") else {}
                    expanded.append({**raw, **segment, "segments": [],
                        "lin_slot": segment.get("lin_slot", local.get("lin_slot")),
                        "phase_ms": segment.get("phase_ms", local.get("phase_ms", 0)),
                        "end_to_end_route_id": raw["id"], "origin_sender_hardware": raw.get("source"),
                        "origin_target_hardware": raw.get("target"), "name": raw.get("name") or raw["id"],
                        "gateways": segment.get("gateway_ids") or []})
            else:
                expanded.append(raw)
        for index, raw in enumerate(expanded):
            if not isinstance(raw, dict):
                continue
            sender_id = str(raw.get("sender_interface") or raw.get("source_interface") or raw.get("sender") or "")
            sender = by_id.get(sender_id)
            receiver_values = (
                raw.get("receiver_interfaces")
                or raw.get("target_interfaces")
                or raw.get("target_interface")
                or raw.get("receivers")
                or raw.get("receiver")
                or []
            )
            if isinstance(receiver_values, str):
                receiver_values = [receiver_values]
            receivers = [by_id[item] for item in receiver_values if item in by_id]
            if sender is None:
                continue
            network_id = str(raw.get("network") or raw.get("network_id") or sender.get("network") or "")
            if not receivers:
                receivers = [item for item in by_network.get(network_id, []) if item["interface_id"] != sender_id]
            gateway_ids = [str(item) for item in raw.get("gateways") or []]
            if int(raw.get("segment_count") or 1) == 1 and sender.get("hardware_type") == "gateway":
                gateway_ids.append(str(sender["hardware_id"]))
            gateway_ids.extend(
                str(item["hardware_id"])
                for item in receivers
                if int(raw.get("segment_count") or 1) == 1 and item.get("hardware_type") == "gateway"
            )
            routes.append(
                {
                    "id": str(raw.get("id") or raw.get("name") or f"communication_{index + 1}"),
                    "name": str(raw.get("name") or raw.get("id") or f"Communication {index + 1}"),
                    "sender": sender,
                    "receivers": receivers,
                    "network": network_id,
                    "technology": normalize_technology_id(raw.get("technology") or sender.get("technology")),
                    "cycle_ms": max(0.001, float(raw.get("cycle_ms") or raw.get("period_ms") or 100.0)),
                    "payload_bytes": max(0, int(raw.get("payload_bytes") or raw.get("length") or 8)),
                    "priority": raw.get("priority"),
                    "gateways": sorted(set(gateway_ids)),
                    "network_metadata": network_by_id.get(network_id, {}),
                    "metadata": {key: value for key, value in raw.items() if key not in {"sender_interface", "source_interface", "sender", "receiver_interfaces", "target_interfaces", "target_interface", "receivers", "receiver"}},
                }
            )
        if routes:
            return routes

    for network_id, interfaces in sorted(by_network.items()):
        if len(interfaces) < 2:
            continue
        for index, sender in enumerate(interfaces):
            receiver = interfaces[(index + 1) % len(interfaces)]
            routes.append(
                {
                    "id": f"{network_id}_{sender['interface_id']}_to_{receiver['interface_id']}",
                    "name": f"{sender['hardware_name']} to {receiver['hardware_name']}",
                    "sender": sender,
                    "receivers": [receiver],
                    "network": network_id,
                    "technology": sender["technology"],
                    "cycle_ms": 100.0,
                    "payload_bytes": 8,
                    "priority": None,
                    "gateways": sorted({
                        str(item["hardware_id"])
                        for item in (sender, receiver)
                        if item.get("hardware_type") == "gateway"
                    }),
                    "network_metadata": network_by_id.get(network_id, {}),
                    "metadata": {"inferred": True},
                }
            )
    return routes


def _serialize_event(event, config, trace_start, network_available_at, port_available_at):
    requested_at = float(event["time_s"])
    network_id = str(event["network"])
    # Capacity and runtime must serialize the same frame with the same
    # technology model (including the separate CAN-FD bit-rate phases).
    transmission_s = (float(event["base_transmission_time_s"])
                      * max(1.0, float(event.get("fault_load_multiplier") or 1.0))
                      * (1 + int(event.get("retransmission_count") or 0)))
    if event.get("ethernet"):
        # Switched, store-and-forward, full-duplex data plane. TX and RX
        # queues are separate per physical port; no fictitious shared bus.
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
    available_at = network_available_at.get(network_id, 0.0)
    transmit_start = max(requested_at, available_at)
    slot = event.get("lin_slot")
    if slot:
        period_s, offset_s = float(slot["period_ms"]) / 1000, float(slot["offset_ms"]) / 1000
        transmit_start = offset_s + max(0, ceil((transmit_start - offset_s) / period_s - 1e-9)) * period_s
    queue_delay_s = max(0.0, transmit_start - requested_at)
    queue_depth = int(queue_delay_s / max(transmission_s, 0.000000001))
    queue_size = max(1, int(config.get("queue_size") or 256))
    queue_overflow = queue_depth > queue_size and event.get("status") != "dropped"
    if queue_overflow:
        event["status"] = "dropped"
        event["drop_reason"] = "queue_overflow"
        completion = requested_at
    elif event.get("status") == "dropped":
        completion = requested_at
    else:
        completion = transmit_start + transmission_s
        network_available_at[network_id] = max(completion, transmit_start + float(slot["duration_ms"]) / 1000) if slot else completion
    event["tx_start_s"] = transmit_start
    event["tx_end_s"] = completion
    event["queue_delay_ms"] = queue_delay_s * 1000.0
    event["queue_depth_estimate"] = queue_depth
    event["transmission_latency_ms"] = transmission_s * 1000.0
    event["end_to_end_latency_ms"] = (
        queue_delay_s * 1000.0
        + transmission_s * 1000.0
        + float(event["configured_latency_ms"])
        + float(event.get("retry_delay_ms") or 0.0)
    )
    event["time_s"] = completion
    event["timestamp_unix"] = trace_start + completion
    event["timestamp_utc"] = _utc(trace_start + completion)


def _generate_universal_events(
    config: dict[str, Any],
    profile: dict[str, Any],
    *,
    start_utc: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    check_cancellation()
    config = {**(config.get("parameters") or {}), **config}
    duration_s = max(0.001, float(config.get("duration_s") or config.get("duration") or 1.0))
    seed = int(config.get("seed", 42))
    max_events = max(1, int(config.get("max_events") or 100_000))
    trace_start = float(start_utc if start_utc is not None else datetime.now(timezone.utc).timestamp())
    registry = technology_registry(profile.get("technology_profiles"))
    routes = _build_routes(config, profile)
    events: list[dict[str, Any]] = []
    rng = random.Random(seed)
    model_engine = ModelBasedSimulationEngine(config)
    scenario_is_explicit = isinstance(config.get("scenario"), dict)
    scenario = config.get("scenario") if scenario_is_explicit else {}
    scenario_mode = str(scenario.get("mode") or "NORMAL").upper()
    suppress_root_faults = scenario_is_explicit and scenario_mode == "NORMAL"
    root_faults = {
        "dropout_probability": 0 if suppress_root_faults else config.get("dropout_probability"),
        "corruption_probability": 0 if suppress_root_faults else config.get("corruption_probability"),
        "duplicate_probability": 0 if suppress_root_faults else config.get("duplicate_probability"),
        "reordering_probability": 0 if suppress_root_faults else config.get("reordering_probability"),
    }

    address_owners = {}
    forwarding_templates = {}
    for route in routes:
        check_cancellation()
        segment_index = int(route["metadata"].get("segment_index") or 0)
        segment_count = int(route["metadata"].get("segment_count") or 1)
        end_to_end_id = str(route["metadata"].get("end_to_end_route_id") or route["id"])
        is_forwarding = segment_index > 0
        sender = route["sender"]
        receivers = route["receivers"]
        if str(sender.get("health")).lower() in {"offline", "disabled", "not_available"}:
            continue
        technology = resolve_technology(route["technology"], registry)
        max_payload = technology.get("max_payload_bytes")
        payload_size = int(route["payload_bytes"])
        if isinstance(max_payload, int) and max_payload > 0:
            payload_size = min(payload_size, max_payload)
        cycle_s = float(route["cycle_ms"]) / 1000.0
        if scenario_mode == "STRESS":
            cycle_s *= max(0.05, float(scenario.get("cycle_factor") or 0.5))
        if str(sender.get("health")).lower() in {"degraded", "faulty"}:
            cycle_s *= 2
        network_metadata = route.get("network_metadata") if isinstance(route.get("network_metadata"), dict) else {}
        frame_parameters = dict(network_metadata)
        if "bitrate" not in frame_parameters and "link_speed" in frame_parameters:
            frame_parameters["bitrate"] = frame_parameters["link_speed"]
        frame = estimate_frame(technology["id"], payload_size, frame_parameters)
        if frame.is_generic_estimate or not frame.transmission_time_available:
            raise ValueError(
                f"TIMING_UNVERIFIED: {technology['id']} auf Netz {route['network']}: "
                "Explizite gültige Raten und ein technologiespezifisches Übertragungsmodell sind erforderlich."
            )
        bitrate = frame_parameters.get("bitrate") or frame_parameters.get("arbitration_bitrate") or 0
        ethernet = resolve_flow({**route, 'network_metadata': {
            **{key: config[key] for key in ('ip_version', 'transport_protocol', 'source_port', 'destination_port', 'mtu', 'vlan_id') if key in config},
            **network_metadata}})
        if ethernet:
            for endpoint in [ethernet["source"], *ethernet["destinations"]]:
                for key in ("ip", "mac"):
                    address_key = (route["network"], ethernet["vlan_id"], key, endpoint[key])
                    owner = address_owners.setdefault(address_key, endpoint["interface_id"])
                    if owner != endpoint["interface_id"]:
                        raise ValueError(f"Duplicate {key} on network {route['network']}: {endpoint[key]}")
            # Validate MTU before generating any events; never truncate an IP packet.
            packet_bytes({"ethernet": ethernet, "payload_hex": bytes(payload_size).hex(), "sequence": 0, "route_id": route["id"]})
        network_faults = network_metadata.get("fault_model") if isinstance(network_metadata.get("fault_model"), dict) else {}
        route_faults = route["metadata"].get("fault_model") if isinstance(route["metadata"].get("fault_model"), dict) else {}
        fault_model = {**root_faults, **network_faults, **route_faults}
        dropout_probability = max(0.0, min(1.0, float(fault_model.get("dropout_probability") or 0.0)))
        corruption_probability = max(0.0, min(1.0, float(fault_model.get("corruption_probability") or fault_model.get("crc_error_probability") or 0.0)))
        duplicate_probability = max(0.0, min(1.0, float(fault_model.get("duplicate_probability") or 0.0)))
        reordering_probability = max(0.0, min(1.0, float(fault_model.get("reordering_probability") or 0.0)))
        retry_limit = max(0, int(config.get("retry_limit") or route["metadata"].get("retry_limit") or 0))
        retransmission_enabled = bool(config.get("retransmission_enabled") or retry_limit > 0)
        retry_delay_ms = max(0.0, float(config.get("retransmission_delay_ms") or 0.0))
        gateways = route.get("gateways") or []
        engineering_latency_ms = (
            (float(config.get("source_processing_delay_ms") or 0.0) if segment_index == 0 else 0.0)
            + (float(config.get("target_processing_delay_ms") or 0.0) if segment_index == segment_count - 1 else 0.0)
            + float(config.get("propagation_delay_ms") or 0.0)
            + len(gateways) * float(config.get("gateway_delay_ms") or 0.0)
            + len(gateways) * float(config.get("gateway_queue_delay_ms") or 0.0)
            + len(gateways) * float(config.get("protocol_conversion_delay_ms") or 0.0)
        )
        latency_s = (
            float(route["metadata"].get("latency_us") or network_metadata.get("latency_us") or 0.0)
            / 1_000_000.0
            + engineering_latency_ms / 1000.0
        )
        sequence = 0
        relative_time = max(0.0, float(route["metadata"].get("phase_ms") or 0)) / 1000.0
        if "jitter_ratio" in route["metadata"]:
            jitter_amplitude_s = cycle_s * max(0.0, float(route["metadata"]["jitter_ratio"]))
        else:
            # jitter_ms is an acceptance budget, not a random disturbance.
            # Inject source timing variation only when explicitly configured;
            # network arbitration/serialization still contributes real jitter.
            configured_jitter = route["metadata"].get("source_jitter_ms", network_metadata.get("source_jitter_ms", config.get("source_jitter_ms")))
            jitter_amplitude_s = max(0.0, float(configured_jitter)) / 1000 if configured_jitter is not None else 0.0
        contract = deepcopy(route["metadata"].get("transmission_contract") or {})
        mode = str(contract.get("mode") or "CYCLIC").upper()
        if mode == "CYCLIC":
            contract["period_ms"] = cycle_s * 1000
        candidates = [0.0] if is_forwarding else release_grid(contract, cycle_s * 1000, duration_s * 1000,
            relative_time * 1000, max_events)
        last_payload, last_sent = None, None
        for release_ms in candidates:
            check_cancellation()
            if len(events) >= max_events:
                break
            relative_time = release_ms / 1000
            jitter = rng.uniform(-jitter_amplitude_s, jitter_amplitude_s) if sequence and not is_forwarding else 0.0
            reordered = not is_forwarding and rng.random() < reordering_probability
            event_time = max(0.0, relative_time + jitter + latency_s + (cycle_s * 0.5 if reordered else 0.0))
            if route["metadata"].get("lin_slot"):
                event_time = max(0.0, relative_time + jitter)
            status = "transmitted"
            retransmission_count = 0
            if not is_forwarding and rng.random() < dropout_probability:
                status = "dropped"
                if retransmission_enabled:
                    for _ in range(retry_limit):
                        retransmission_count += 1
                        if rng.random() >= dropout_probability:
                            status = "transmitted"
                            break
            if not is_forwarding and status != "dropped" and rng.random() < corruption_probability:
                status = "corrupted"
            model_payload = {} if is_forwarding else model_engine.encode_event(route, relative_time, payload_size)
            payload_hex = (
                str(model_payload["payload_hex"])
                if model_payload.get("signals")
                else _payload(route["id"], sequence, payload_size)
            )
            if not is_forwarding and mode in {"EVENT", "MIXED"} and contract.get("trigger") == "on_change":
                if not model_payload.get("signals"):
                    raise ValueError("on_change benötigt modellierte Signale; Zufallspayload ist kein Zustandsereignis.")
                heartbeat = mode == "MIXED" and last_sent is not None and release_ms - last_sent >= float(contract["period_ms"]) - 1e-8
                first_sample = last_payload is None
                changed = payload_hex != last_payload
                last_payload = payload_hex
                if not heartbeat and (not changed or (first_sample and contract.get("send_initial") is False)):
                    continue
            last_sent = release_ms
            if status == "corrupted" and payload_hex:
                payload_hex = ("FF" + payload_hex[2:]) if len(payload_hex) >= 2 else "FF"
            event = {
                "event_id": f"{end_to_end_id}:{sequence}" + (f":segment:{segment_index}" if segment_count > 1 else ""),
                "end_to_end_event_id": f"{end_to_end_id}:{sequence}",
                "transaction_id": f"{end_to_end_id}:{sequence}",
                "end_to_end_route_id": end_to_end_id,
                "canonical_route_id": route["metadata"].get("canonical_route_id") or route["metadata"].get("routing_entry_id"),
                "segment_index": segment_index, "segment_count": segment_count, "final_segment": segment_index == segment_count - 1,
                "segment_id": route["id"],
                "origin_sender_hardware": route["metadata"].get("origin_sender_hardware") or sender["hardware_id"],
                "origin_scheduled_time_s": relative_time,
                "origin_release_time_s": max(0.0, relative_time + jitter),
                "timestamp_utc": _utc(trace_start + event_time),
                "timestamp_unix": trace_start + event_time,
                "time_s": event_time,
                "scheduled_time_s": relative_time,
                "configured_cycle_ms": cycle_s * 1000.0,
                "release_mode": mode,
                "release_basis": "scenario_application_request" if mode == "ON_REQUEST" else "model_change" if mode == "EVENT" else "periodic_or_mixed",
                "deadline_ms": route["metadata"].get("deadline_ms") or (route["metadata"].get("timing") or {}).get("deadline_ms") or config.get("deadline_ms"),
                "configured_latency_ms": latency_s * 1000.0,
                "injected_jitter_ms": jitter * 1000.0,
                "sequence": sequence,
                "transport_sequence_bytes": sequence * payload_size,
                "route_id": end_to_end_id,
                "route_name": route["name"],
                "route_ref": route.get('metadata', {}).get('routing_entry_id'),
                "route_refs": route.get('metadata', {}).get('routing_entry_ids') or [],
                "technology": technology["id"],
                "technology_family": technology.get("family"),
                "access_model": technology.get("access"),
                "timing_model": technology.get("timing_model"),
                "error_model": technology.get("error_model"),
                "network": route["network"],
                "sender_hardware": sender["hardware_id"],
                "source_name": sender["hardware_name"],
                "source_logical_address": sender.get("formatted_logical_node_address"),
                "sender_port": sender["port_id"],
                "sender_interface": sender["interface_id"],
                "receiver_hardware": [item["hardware_id"] for item in receivers],
                "destination_names": [item["hardware_name"] for item in receivers],
                "destination_logical_addresses": [item.get("formatted_logical_node_address") for item in receivers],
                "receiver_interfaces": [item["interface_id"] for item in receivers],
                "receiver_ports": [item["port_id"] for item in receivers],
                "gateway_ids": gateways,
                "message_ids": route.get("metadata", {}).get("message_ids") or [],
                "payload_bytes": payload_size,
                "payload_hex": payload_hex,
                "frame_bits": frame.frame_bits,
                "frame_calculation_model": frame.calculation_model,
                "base_transmission_time_s": frame.transmission_time_s,
                "priority": route.get("priority"),
                "arbitration_id": route.get("metadata", {}).get("arbitration_id"),
                "lin_slot": route.get("metadata", {}).get("lin_slot"),
                "status": status,
                "retransmission_count": retransmission_count,
                "duplicate_injected": not is_forwarding and rng.random() < duplicate_probability,
                "reordered": reordered,
                "retry_delay_ms": retransmission_count * retry_delay_ms,
                "configured_bitrate": bitrate,
            }
            if ethernet:
                event["ethernet"] = ethernet
                event["frame_bits"] = wire_bytes(ethernet, payload_size) * 8
                event["base_transmission_time_s"] = event["frame_bits"] / bitrate
                event["frame_calculation_model"] = "PROJECT_IP_ETHERNET_WIRE_V1"
                event["src_ip"] = ethernet["source"]["ip"]
                event["dst_ips"] = [d["ip"] for d in ethernet["destinations"]]
                event["ip_version"] = ethernet["ip_version"]
                event["transport_protocol"] = ethernet["transport_protocol"]
            event["signals"] = model_payload.get("signals") or []
            if event["signals"]:
                first_signal = event["signals"][0]
                event["signal"] = first_signal.get("signal")
                event["signal_id"] = first_signal.get("signal_id")
                event["signal_value"] = first_signal.get("value")
                event["value"] = first_signal.get("value")
                event["unit"] = first_signal.get("unit")
                event["golden_value"] = first_signal.get("golden_value")
                event["model_label"] = first_signal.get("model_label")
                event["behavior_type"] = first_signal.get("behavior_type")
            if is_forwarding:
                event["faults"] = []
                event["_probabilities"] = (dropout_probability, corruption_probability)
                forwarding_templates[(end_to_end_id, segment_index)] = event
                break
            event["faults"] = list(dict.fromkeys([
                *model_engine.faults.event_faults(event),
                *(fault for signal in event['signals'] for fault in signal.get('faults') or []),
            ]))
            if scenario_mode == "STRESS":
                event["fault_load_multiplier"] = max(1.0, float(scenario.get("load_factor") or 2.0))
            events.append(event)
            if event.get("duplicate_injected") and len(events) < max_events:
                events.append({
                    **event,
                    "event_id": event["event_id"] + ":duplicate",
                    "end_to_end_event_id": event["end_to_end_event_id"] + ":duplicate",
                    "transaction_id": event["end_to_end_event_id"] + ":duplicate",
                    "sequence": sequence * 1_000_000 + 1,
                    "time_s": event_time + 0.000001,
                    "duplicate_of": sequence,
                })
            sequence += 1

        if len(events) >= max_events:
            break

    session_config = {**config, "_defer_restbus_acks": True}
    events = _add_restbus_sessions(events, session_config, max_events)
    session_settings = _restbus_settings(config)
    # Gateways originate a separate IP session on their outgoing physical
    # segment. Set it up independently, then release data only after both
    # upstream delivery and local session establishment.
    for key, template in list(forwarding_templates.items()):
        if not template.get("ethernet") or not session_settings:
            continue
        prepared = _add_restbus_sessions([deepcopy(template)], session_config, max_events)
        shifted = next((item for item in prepared if item.get("traffic_type") == "DATA"), template)
        shifted["_session_ready_at"] = float(shifted["scheduled_time_s"])
        shifted["_session_sequence_base"] = int(shifted.get("transport_sequence_bytes") or 0)
        forwarding_templates[key] = shifted
        events.extend(item for item in prepared if item.get("traffic_type") == "CONTROL")
    for event in events:
        if event.get("traffic_type") == "CONTROL":
            event["faults"] = model_engine.faults.event_faults(event)
    # Simultaneously due LIN polls use shortest period first. UUID ordering
    # is not a bus schedule: it could put a slow frame before a 10 ms poll,
    # making the same regenerated project randomly pass or fail its jitter.
    events.sort(key=lambda item: (float(item["time_s"]),
        float(item.get('configured_cycle_ms') or 0) if item.get('technology') == 'lin' else 0,
        str(item["route_id"]), int(item["sequence"])))
    network_available_at: dict[str, float] = {}
    port_available_at: dict[tuple, float] = {}
    pending = EventScheduler(events, network_available_at)
    events = []
    physical_frames = {}
    while len(events) < max_events:
        check_cancellation()
        event = pending.pop()
        if event is None:
            break
        physical_key = None
        if not event.get("ethernet") and event.get("message_ids") and not event.get("duplicate_injected"):
            physical_key = (event["network"], event["sender_hardware"], event["sender_port"],
                            tuple(event["message_ids"]), round(float(event.get("origin_scheduled_time_s", 0)), 9), event["sequence"])
        previous = physical_frames.get(physical_key) if physical_key else None
        if previous:
            for field in ("time_s", "timestamp_unix", "timestamp_utc", "tx_start_s", "tx_end_s", "queue_delay_ms", "queue_depth_estimate",
                          "end_to_end_latency_ms", "transmission_latency_ms", "status", "payload_hex", "physical_transmission_id"):
                if field in previous:
                    event[field] = previous[field]
            event["shared_transmission_observation"] = True
        else:
            _serialize_event(event, config, trace_start, network_available_at, port_available_at)
            if physical_key:
                event["physical_transmission_id"] = hashlib.sha256(repr(physical_key).encode()).hexdigest()[:24]
                physical_frames[physical_key] = dict(event)
        if int(event.get("segment_count") or 1) > 1:
            event["end_to_end_latency_ms"] = max(0.0, (float(event["time_s"]) - float(event["origin_release_time_s"])) * 1000)
        if event.get("transmission_attempted") is False:
            event["transmission_latency_ms"] = 0.0
        events.append(event)
        for acknowledgement in _restbus_ack_events(event, session_settings):
            acknowledgement["faults"] = model_engine.faults.event_faults(acknowledgement)
            if float(acknowledgement["time_s"]) <= duration_s:
                pending.enqueue(acknowledgement)
        next_index = int(event.get("segment_index") or 0) + 1
        template = forwarding_templates.get((event.get("end_to_end_route_id"), next_index))
        if template is None or event.get("traffic_type") == "CONTROL":
            continue
        forwarded = deepcopy(template)
        drop_probability, corrupt_probability = forwarded.pop("_probabilities", (0, 0))
        session_ready_at = forwarded.pop("_session_ready_at", 0.0)
        session_sequence_base = forwarded.pop("_session_sequence_base", 0)
        for key in ("sequence", "transport_sequence_bytes", "origin_release_time_s", "origin_scheduled_time_s",
                    "origin_sender_hardware", "end_to_end_event_id", "payload_hex", "signals", "signal", "signal_id",
                    "signal_value", "value", "unit", "golden_value", "model_label", "behavior_type"):
            if key in event:
                forwarded[key] = deepcopy(event[key])
        forwarded["event_id"] = str(event["end_to_end_event_id"]) + f":segment:{next_index}"
        forwarded["transaction_id"] = event.get("transaction_id") or event["end_to_end_event_id"]
        forwarded["caused_by_event_id"] = event["event_id"]
        forwarded["scheduled_time_s"] = float(event["time_s"])
        forwarded["time_s"] = max(float(event["time_s"]), session_ready_at) + float(forwarded["configured_latency_ms"]) / 1000
        if session_sequence_base:
            forwarded["transport_sequence_bytes"] = session_sequence_base + int(event["sequence"]) * int(event["payload_bytes"])
        if event["status"] != "transmitted":
            forwarded.update(status="dropped", drop_reason="upstream_" + event["status"], transmission_attempted=False)
            forwarded["faults"] = list(event.get("faults") or [])
        else:
            if rng.random() < drop_probability:
                forwarded.update(status="dropped", drop_reason="configured_packet_loss")
            elif rng.random() < corrupt_probability:
                forwarded["status"] = "corrupted"
                payload_hex = str(forwarded.get("payload_hex") or "")
                forwarded["payload_hex"] = "FF" + payload_hex[2:] if payload_hex else "FF"
            forwarded["faults"] = list(dict.fromkeys([*event.get("faults", []), *model_engine.faults.event_faults(forwarded)]))
        pending.enqueue(forwarded)
    events.sort(key=lambda item: (float(item["time_s"]), str(item["route_id"]), int(item["sequence"])))
    from transport_dependencies import apply_transport_dependencies
    check_cancellation()
    apply_transport_dependencies(events, model_engine)
    check_cancellation()
    return routes, events


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> Path:
    check_cancellation()
    path.parent.mkdir(parents=True, exist_ok=True)
    entries, previous, ordered = [], -1.0, True
    with path.open("wb") as handle:
        for index, event in enumerate(events):
            check_cancellation()
            timestamp = float(event.get("time_s", 0))
            ordered &= timestamp >= previous
            previous = timestamp
            if index % 512 == 0:
                entries.append([timestamp, handle.tell()])
            handle.write((json.dumps(event, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
    metadata = path.stat()
    path.with_suffix(".index.json").write_text(json.dumps({"schema": "trace-time-index-v1", "size_bytes": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns, "ordered": ordered, "entries": entries}), encoding="utf-8")
    return path


def _write_csv(path: Path, events: list[dict[str, Any]]) -> Path:
    check_cancellation()
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "timestamp_utc", "timestamp_unix", "time_s", "scheduled_time_s",
        "configured_cycle_ms", "configured_latency_ms", "injected_jitter_ms", "release_mode", "release_basis",
        "deadline_ms",
        "event_id", "sequence", "transport_sequence_bytes", "route_id", "route_name", "route_ref", "route_refs",
        "end_to_end_event_id", "transaction_id", "end_to_end_route_id", "canonical_route_id", "segment_index", "segment_count",
        "segment_id", "final_segment", "origin_sender_hardware", "origin_scheduled_time_s", "origin_release_time_s",
        "caused_by_event_id", "transmission_attempted", "golden_time_s",
        "traffic_type", "protocol_event", "session_id", "tcp_flags", "transport_ack_number",
        "technology", "technology_family", "access_model", "timing_model", "error_model",
        "network", "sender_hardware", "source_name", "source_logical_address", "sender_port",
        "sender_interface", "receiver_hardware", "receiver_interfaces", "payload_bytes",
        "receiver_ports", "ip_version", "src_ip", "dst_ips", "transport_protocol", "ethernet", "tx_start_s", "tx_end_s", "rx_ports", "port_model",
        "destination_names", "destination_logical_addresses",
        "payload_hex", "priority", "status", "configured_bitrate", "queue_delay_ms",
        "arbitration_id", "lin_slot", "physical_transmission_id", "shared_transmission_observation",
        "frame_bits", "frame_calculation_model", "base_transmission_time_s",
        "queue_depth_estimate", "transmission_latency_ms", "end_to_end_latency_ms",
        "gateway_ids", "retransmission_count", "duplicate_injected", "reordered",
        "retry_delay_ms", "drop_reason", "signal", "signal_id", "signal_value",
        "value", "golden_value", "unit", "behavior_type", "model_label", "message_ids", "signals", "faults",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for event in events:
            check_cancellation()
            writer.writerow(
                {
                    **event,
                    "receiver_hardware": ",".join(event["receiver_hardware"]),
                    "receiver_interfaces": ",".join(event["receiver_interfaces"]),
                    "destination_names": ",".join(event.get("destination_names") or []),
                    "destination_logical_addresses": ",".join(str(item or "") for item in event.get("destination_logical_addresses") or []),
                    "gateway_ids": ",".join(event.get("gateway_ids") or []),
                    "message_ids": ",".join(str(item) for item in event.get("message_ids") or []),
                    "signals": json.dumps(event.get("signals") or [], ensure_ascii=False),
                    "lin_slot": json.dumps(event.get("lin_slot")),
                    "ethernet": json.dumps(event.get("ethernet"), ensure_ascii=False),
                    "rx_ports": json.dumps(event.get("rx_ports") or [], ensure_ascii=False),
                    "dst_ips": json.dumps(event.get("dst_ips") or []),
                    "receiver_ports": json.dumps(event.get("receiver_ports") or []),
                    "faults": ",".join(str(item) for item in event.get("faults") or []),
                }
            )
    return path


def _trace_summary(routes: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    technologies = sorted({str(event["technology"]) for event in events})
    networks = sorted({str(event["network"]) for event in events})
    return {
        "routes": len({str(route.get("metadata", {}).get("end_to_end_route_id") or route["id"]) for route in routes}),
        "route_segments": len(routes),
        "events": len(events),
        "technologies": technologies,
        "networks": networks,
        "universal_trace": True,
    }


class UniversalTraceGenerator:
    """Generate technology-neutral routes and communication events."""

    def build_routes(self, config: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
        return _build_routes(config, profile)

    def generate(
        self,
        config: dict[str, Any],
        profile: dict[str, Any],
        *,
        start_utc: float | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return _generate_universal_events(config, profile, start_utc=start_utc)


class JsonLinesTraceWriter:
    """Write neutral events as JSON Lines."""

    def write(self, path: Path, events: list[dict[str, Any]]) -> Path:
        return _write_jsonl(path, events)


class CsvTraceWriter:
    """Write neutral events as CSV."""

    def write(self, path: Path, events: list[dict[str, Any]]) -> Path:
        return _write_csv(path, events)


class TraceSummaryBuilder:
    """Create compact metadata for a generated trace."""

    def build(self, routes: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
        return _trace_summary(routes, events)


DEFAULT_TRACE_GENERATOR = UniversalTraceGenerator()
DEFAULT_JSONL_WRITER = JsonLinesTraceWriter()
DEFAULT_CSV_WRITER = CsvTraceWriter()
DEFAULT_TRACE_SUMMARY_BUILDER = TraceSummaryBuilder()


def build_routes(config: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    return DEFAULT_TRACE_GENERATOR.build_routes(config, profile)


def generate_universal_events(
    config: dict[str, Any],
    profile: dict[str, Any],
    *,
    start_utc: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return DEFAULT_TRACE_GENERATOR.generate(config, profile, start_utc=start_utc)


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> Path:
    return DEFAULT_JSONL_WRITER.write(path, events)


def write_csv(path: Path, events: list[dict[str, Any]]) -> Path:
    return DEFAULT_CSV_WRITER.write(path, events)


def trace_summary(routes: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    return DEFAULT_TRACE_SUMMARY_BUILDER.build(routes, events)
