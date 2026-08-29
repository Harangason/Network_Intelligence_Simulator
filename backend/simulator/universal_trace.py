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


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _payload(route_id: str, sequence: int, size: int) -> str:
    seed = hashlib.sha256(f"{route_id}:{sequence}".encode("utf-8")).digest()
    data = (seed * ((size // len(seed)) + 1))[:size]
    return data.hex(" ").upper()


def _interface_index(profile: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_network: dict[str, list[dict[str, Any]]] = {}
    for node, port, interface in iter_network_interfaces(profile):
        record = {
            "hardware_id": node["id"],
            "hardware_name": node.get("name") or node["id"],
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
    seed = int(config.get("seed") or 42)
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
        relative_time = 0.0
        jitter_ratio = float(route["metadata"].get("jitter_ratio") or 0.01)
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
                "timestamp_utc": _utc(trace_start + event_time),
                "timestamp_unix": trace_start + event_time,
                "time_s": event_time,
                "scheduled_time_s": relative_time,
                "configured_cycle_ms": cycle_s * 1000.0,
                "configured_latency_ms": latency_s * 1000.0,
                "injected_jitter_ms": jitter * 1000.0,
                "sequence": sequence,
                "route_id": route["id"],
                "route_name": route["name"],
                "technology": technology["id"],
                "technology_family": technology.get("family"),
                "access_model": technology.get("access"),
                "timing_model": technology.get("timing_model"),
                "error_model": technology.get("error_model"),
                "network": route["network"],
                "sender_hardware": sender["hardware_id"],
                "sender_port": sender["port_id"],
                "sender_interface": sender["interface_id"],
                "receiver_hardware": [item["hardware_id"] for item in receivers],
                "receiver_interfaces": [item["interface_id"] for item in receivers],
                "gateway_ids": gateways,
                "message_ids": route.get("metadata", {}).get("message_ids") or [],
                "payload_bytes": payload_size,
                "payload_hex": payload_hex,
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
            event["faults"] = model_engine.faults.event_faults(event)
            if scenario_mode == "STRESS":
                event["fault_load_multiplier"] = max(1.0, float(scenario.get("load_factor") or 2.0))
            events.append(event)
            if event.get("duplicate_injected") and len(events) < max_events:
                events.append({
                    **event,
                    "sequence": sequence * 1_000_000 + 1,
                    "time_s": event_time + 0.000001,
                    "duplicate_of": sequence,
                })
            sequence += 1
            relative_time = sequence * cycle_s
        if len(events) >= max_events:
            break

    events.sort(key=lambda item: (float(item["time_s"]), str(item["route_id"]), int(item["sequence"])))
    network_available_at: dict[str, float] = {}
    for event in events:
        requested_at = float(event["time_s"])
        network_id = str(event["network"])
        bitrate = max(1, int(event["configured_bitrate"]))
        payload_bytes = int(event["payload_bytes"])
        technology_id = str(event["technology"]).lower()
        if "ethernet" in technology_id or technology_id in {"some_ip", "someip", "dds", "ros_2", "udp", "tcp"}:
            wire_bits = max(84, payload_bytes + 74) * 8
        elif technology_id in {"can_fd", "canfd", "can_xl"}:
            wire_bits = int((payload_bytes * 8 + 83) * 1.15)
        elif technology_id in {"can", "can_classic"}:
            wire_bits = int((payload_bytes * 8 + 47) * 1.2)
        else:
            wire_bits = (payload_bytes + 24) * 8
        wire_bits = int(wire_bits * max(1.0, float(event.get("fault_load_multiplier") or 1.0)))
        transmission_s = wire_bits / bitrate * (1 + int(event.get("retransmission_count") or 0))
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
    return routes, events


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return path


def _write_csv(path: Path, events: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "timestamp_utc", "timestamp_unix", "time_s", "scheduled_time_s",
        "configured_cycle_ms", "configured_latency_ms", "injected_jitter_ms",
        "sequence", "route_id", "route_name",
        "technology", "technology_family", "access_model", "timing_model", "error_model",
        "network", "sender_hardware", "sender_port",
        "sender_interface", "receiver_hardware", "receiver_interfaces", "payload_bytes",
        "payload_hex", "priority", "status", "configured_bitrate", "queue_delay_ms",
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
                    "gateway_ids": ",".join(event.get("gateway_ids") or []),
                    "message_ids": ",".join(str(item) for item in event.get("message_ids") or []),
                    "signals": json.dumps(event.get("signals") or [], ensure_ascii=False),
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
