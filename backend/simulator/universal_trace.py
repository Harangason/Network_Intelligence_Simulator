"""Technology-neutral event generation and trace writers."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bus_technologies import normalize_technology_id, resolve_technology, technology_registry
from hardware_profile import iter_network_interfaces
from model_based_simulation import ModelBasedSimulationEngine
from backend.engineering.capacity.calculators import estimate_frame
from ethernet_transport import resolve_flow, wire_bytes, packet_bytes


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
    bitrate = max(1, int(template.get("configured_bitrate") or 1_000_000))
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
        "session_id": f"session:{template['route_id']}",
        "signals": [],
        "faults": [],
    }
    for key in ("signal", "signal_id", "signal_value", "value", "unit", "golden_value", "model_label", "behavior_type"):
        event.pop(key, None)
    if tcp_flags is not None:
        event["tcp_flags"] = tcp_flags
    return event


def _add_restbus_sessions(events: list[dict[str, Any]], config: dict[str, Any], max_events: int) -> list[dict[str, Any]]:
    settings = _restbus_settings(config)
    if settings is None:
        return events
    duration_s = max(0.001, float(config.get("duration_s") or config.get("duration") or 1.0))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("ethernet"):
            event["traffic_type"] = "DATA"
            event["protocol_event"] = "DATA"
            event["session_id"] = f"session:{event['route_id']}"
            grouped.setdefault(str(event["route_id"]), []).append(event)
    if not grouped:
        return events

    controls: list[dict[str, Any]] = []
    shifted_data: list[dict[str, Any]] = []
    for route_id, route_events in grouped.items():
        route_events.sort(key=lambda item: (float(item["scheduled_time_s"]), int(item["sequence"])))
        template = route_events[0]
        flow = template["ethernet"]
        protocol = str(flow["transport_protocol"]).lower()
        bitrate = max(1, int(template.get("configured_bitrate") or 1_000_000))
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
                if settings["acknowledge_data"] and shifted.get("status") == "transmitted":
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
        for index, raw in enumerate(explicit):
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
            if sender.get("hardware_type") == "gateway":
                gateway_ids.append(str(sender["hardware_id"]))
            gateway_ids.extend(
                str(item["hardware_id"])
                for item in receivers
                if item.get("hardware_type") == "gateway"
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


def _generate_universal_events(
    config: dict[str, Any],
    profile: dict[str, Any],
    *,
    start_utc: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
    for route in routes:
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
        bitrate = int(network_metadata.get("bitrate") or network_metadata.get("link_speed")
                      or technology.get("default_bitrate") or 1_000_000)
        frame = estimate_frame(technology["id"], payload_size, {**network_metadata, "bitrate": bitrate})
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
            float(config.get("source_processing_delay_ms") or 0.0)
            + float(config.get("target_processing_delay_ms") or 0.0)
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
        jitter_ratio = float(route["metadata"].get("jitter_ratio", 0.01))
        while relative_time <= duration_s and len(events) < max_events:
            jitter = rng.uniform(-cycle_s * jitter_ratio, cycle_s * jitter_ratio) if sequence else 0.0
            reordered = rng.random() < reordering_probability
            event_time = max(0.0, relative_time + jitter + latency_s + (cycle_s * 0.5 if reordered else 0.0))
            status = "transmitted"
            retransmission_count = 0
            if rng.random() < dropout_probability:
                status = "dropped"
                if retransmission_enabled:
                    for _ in range(retry_limit):
                        retransmission_count += 1
                        if rng.random() >= dropout_probability:
                            status = "transmitted"
                            break
            if status != "dropped" and rng.random() < corruption_probability:
                status = "corrupted"
            model_payload = model_engine.encode_event(route, relative_time, payload_size)
            payload_hex = (
                str(model_payload["payload_hex"])
                if model_payload.get("signals")
                else _payload(route["id"], sequence, payload_size)
            )
            if status == "corrupted" and payload_hex:
                payload_hex = ("FF" + payload_hex[2:]) if len(payload_hex) >= 2 else "FF"
            event = {
                "event_id": f"{route['id']}:{sequence}",
                "timestamp_utc": _utc(trace_start + event_time),
                "timestamp_unix": trace_start + event_time,
                "time_s": event_time,
                "scheduled_time_s": relative_time,
                "configured_cycle_ms": cycle_s * 1000.0,
                "deadline_ms": route["metadata"].get("deadline_ms") or (route["metadata"].get("timing") or {}).get("deadline_ms") or config.get("deadline_ms"),
                "configured_latency_ms": latency_s * 1000.0,
                "injected_jitter_ms": jitter * 1000.0,
                "sequence": sequence,
                "transport_sequence_bytes": sequence * payload_size,
                "route_id": route["id"],
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
                "status": status,
                "retransmission_count": retransmission_count,
                "duplicate_injected": rng.random() < duplicate_probability,
                "reordered": reordered,
                "retry_delay_ms": retransmission_count * retry_delay_ms,
                "configured_bitrate": int(
                    network_metadata.get("bitrate")
                    or network_metadata.get("link_speed")
                    or technology.get("default_bitrate")
                    or 1_000_000
                ),
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
                    "event_id": f"{route['id']}:{sequence}:duplicate",
                    "sequence": sequence * 1_000_000 + 1,
                    "time_s": event_time + 0.000001,
                    "duplicate_of": sequence,
                })
            sequence += 1
            relative_time = round(relative_time + max(0.001, float(event['configured_cycle_ms'])) / 1000.0, 12)
        if len(events) >= max_events:
            break

    events = _add_restbus_sessions(events, config, max_events)
    events.sort(key=lambda item: (float(item["time_s"]), str(item["route_id"]), int(item["sequence"])))
    network_available_at: dict[str, float] = {}
    port_available_at: dict[tuple, float] = {}
    for event in events:
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
            continue
        available_at = network_available_at.get(network_id, 0.0)
        transmit_start = max(requested_at, available_at)
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
            network_available_at[network_id] = completion
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
    events.sort(key=lambda item: (float(item["time_s"]), str(item["route_id"]), int(item["sequence"])))
    from transport_dependencies import apply_transport_dependencies
    apply_transport_dependencies(events, model_engine)
    return routes, events


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries, previous, ordered = [], -1.0, True
    with path.open("wb") as handle:
        for index, event in enumerate(events):
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
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "timestamp_utc", "timestamp_unix", "time_s", "scheduled_time_s",
        "configured_cycle_ms", "configured_latency_ms", "injected_jitter_ms",
        "deadline_ms",
        "event_id", "sequence", "transport_sequence_bytes", "route_id", "route_name", "route_ref", "route_refs",
        "technology", "technology_family", "access_model", "timing_model", "error_model",
        "network", "sender_hardware", "source_name", "source_logical_address", "sender_port",
        "sender_interface", "receiver_hardware", "receiver_interfaces", "payload_bytes",
        "receiver_ports", "ip_version", "src_ip", "dst_ips", "transport_protocol", "ethernet", "tx_start_s", "tx_end_s", "rx_ports", "port_model",
        "destination_names", "destination_logical_addresses",
        "payload_hex", "priority", "status", "configured_bitrate", "queue_delay_ms",
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
        "routes": len(routes),
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
