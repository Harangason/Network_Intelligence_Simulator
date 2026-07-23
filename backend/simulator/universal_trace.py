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
            sender_id = str(raw.get("sender_interface") or raw.get("sender") or "")
            sender = by_id.get(sender_id)
            receiver_values = raw.get("receiver_interfaces") or raw.get("receivers") or raw.get("receiver") or []
            if isinstance(receiver_values, str):
                receiver_values = [receiver_values]
            receivers = [by_id[item] for item in receiver_values if item in by_id]
            if sender is None:
                continue
            network_id = str(raw.get("network") or sender.get("network") or "")
            if not receivers:
                receivers = [item for item in by_network.get(network_id, []) if item["interface_id"] != sender_id]
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
                    "network_metadata": network_by_id.get(network_id, {}),
                    "metadata": {key: value for key, value in raw.items() if key not in {"sender_interface", "sender", "receiver_interfaces", "receivers", "receiver"}},
                }
            )
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
        if str(sender.get("health")).lower() in {"degraded", "faulty"}:
            cycle_s *= 2
        network_metadata = route.get("network_metadata") if isinstance(route.get("network_metadata"), dict) else {}
        network_faults = network_metadata.get("fault_model") if isinstance(network_metadata.get("fault_model"), dict) else {}
        route_faults = route["metadata"].get("fault_model") if isinstance(route["metadata"].get("fault_model"), dict) else {}
        fault_model = {**network_faults, **route_faults}
        dropout_probability = max(0.0, min(1.0, float(fault_model.get("dropout_probability") or 0.0)))
        corruption_probability = max(0.0, min(1.0, float(fault_model.get("corruption_probability") or fault_model.get("crc_error_probability") or 0.0)))
        latency_s = float(route["metadata"].get("latency_us") or network_metadata.get("latency_us") or 0.0) / 1_000_000.0
        sequence = 0
        relative_time = 0.0
        jitter_ratio = float(route["metadata"].get("jitter_ratio") or 0.01)
        while relative_time <= duration_s and len(events) < max_events:
            jitter = rng.uniform(-cycle_s * jitter_ratio, cycle_s * jitter_ratio) if sequence else 0.0
            event_time = max(0.0, relative_time + jitter + latency_s)
            status = "transmitted"
            if rng.random() < dropout_probability:
                status = "dropped"
            elif rng.random() < corruption_probability:
                status = "corrupted"
            payload_hex = _payload(route["id"], sequence, payload_size)
            if status == "corrupted" and payload_hex:
                payload_hex = ("FF" + payload_hex[2:]) if len(payload_hex) >= 2 else "FF"
            event = {
                "timestamp_utc": _utc(trace_start + event_time),
                "timestamp_unix": trace_start + event_time,
                "time_s": event_time,
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
                "payload_bytes": payload_size,
                "payload_hex": payload_hex,
                "priority": route.get("priority"),
                "status": status,
            }
            events.append(event)
            sequence += 1
            relative_time = sequence * cycle_s
        if len(events) >= max_events:
            break

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
        "timestamp_utc", "timestamp_unix", "time_s", "sequence", "route_id", "route_name",
        "technology", "technology_family", "access_model", "timing_model", "error_model",
        "network", "sender_hardware", "sender_port",
        "sender_interface", "receiver_hardware", "receiver_interfaces", "payload_bytes",
        "payload_hex", "priority", "status",
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
