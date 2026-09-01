"""Primary standalone entry point for the technology-neutral simulator."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bus_technologies import catalog_summary, normalize_technology_id, technology_registry
from hardware_profile import hardware_profile_summary, normalize_hardware_config, validate_hardware_profile
from model_based_simulation import build_model_trace
from universal_trace import generate_universal_events, trace_summary, write_csv, write_jsonl


CONFIG_SCHEMA = "communication-simulator.simulation-config.v1"
RESULT_SCHEMA = "communication-simulator.simulation-result.v1"
NATIVE_CAN_FORMATS = {"blf", "dbc", "asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex", "mdf", "mf4"}
NATIVE_ETHERNET_FORMATS = {"pcap", "pcapng"}
CAN_TECHNOLOGIES = {"can", "can_fd", "can_xl", "canopen", "j1939", "arinc825", "devicenet", "nmea2000"}
ETHERNET_TECHNOLOGIES = {
    "ethernet", "automotive_ethernet", "profinet", "ethercat", "ethernet_ip",
    "modbus_tcp", "arinc664_afdx", "etb", "bacnet_ip", "iec61850",
    "someip", "doip", "dds_rtps", "ipv4", "ipv6", "udp", "tcp",
}
DEFAULT_GOLDEN_TRACE_EVENT_LIMIT = 10_000


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _format_tokens(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "universal-jsonl,universal-csv").split(",")
    result: list[str] = []
    for item in raw:
        token = str(item).strip().lower()
        if token and token not in result:
            result.append(token)
    return result


def _output_directory(config: dict[str, Any]) -> Path:
    value = config.get("output_dir")
    if not value:
        return (Path("traces") / f"run_{_timestamp_slug()}").resolve()
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.parts and candidate.parts[0].lower() == "traces":
        return candidate.resolve()
    return (Path("traces") / candidate).resolve()


def _native_participants(profile: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = profile.get("hardware") or []
    if len(nodes) < 2:
        return []
    participants: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        next_node = nodes[(index + 1) % len(nodes)]
        service = f"DATA_{node['id'].upper()}"
        consumed = f"DATA_{nodes[index - 1]['id'].upper()}"
        channel = 0
        for port in node.get("ports") or []:
            for interface in port.get("network_interfaces") or []:
                if normalize_technology_id(interface.get("technology")) in CAN_TECHNOLOGIES:
                    channel = int(interface.get("channel") or 0)
                    break
        participants.append(
            {
                "name": node["id"],
                "role": node.get("type") or "device",
                "channel": channel,
                "cycle_ms": int(node.get("cycle_ms") or 100),
                "provided_services": [service],
                "consumed_services": [consumed],
                "health": node.get("health") or "nominal",
                "_next": next_node["id"],
            }
        )
    for participant in participants:
        participant.pop("_next", None)
    return participants


def _native_configuration(
    config: dict[str, Any],
    profile: dict[str, Any],
    out_dir: Path,
    formats: list[str],
) -> dict[str, Any] | None:
    technologies = {
        normalize_technology_id(network.get("technology"))
        for network in profile.get("networks") or []
    }
    can_enabled = bool(technologies & CAN_TECHNOLOGIES)
    ethernet_enabled = bool(technologies & ETHERNET_TECHNOLOGIES)
    native_formats = [
        item for item in formats
        if (can_enabled and item in NATIVE_CAN_FORMATS)
        or (ethernet_enabled and item in NATIVE_ETHERNET_FORMATS)
    ]
    if not native_formats:
        return None
    bus = "fd"
    if "can_xl" in technologies:
        bus = "xl"
    elif can_enabled and "can_fd" not in technologies:
        bus = "classic"
    channels = 1
    for _, _, interface in _all_interfaces(profile):
        if normalize_technology_id(interface.get("technology")) in CAN_TECHNOLOGIES:
            channels = max(channels, int(interface.get("channel") or 0) + 1)
    participants = _native_participants(profile)
    return {
        "schema": CONFIG_SCHEMA,
        "simulation_mode": "restbus" if participants else "existing",
        "output_dir": str((out_dir / "native").resolve()),
        "formats": ",".join(native_formats),
        "duration_s": float(config.get("duration_s") or config.get("duration") or 1.0),
        "bus_type": bus,
        "channels": min(16, channels),
        "messages": config.get("native_messages") or config.get("messages"),
        "nominal_bitrate": int(config.get("nominal_bitrate") or 500_000),
        "data_bitrate": int(config.get("data_bitrate") or 2_000_000),
        "eth_bitrate": int(config.get("eth_bitrate") or 1_000_000_000),
        "eth_messages": config.get("eth_messages"),
        "seed": int(config.get("seed") or 42),
        "participants": participants,
        "scenario": {"domain": str(config.get("domain") or "generic")},
    }


def _all_interfaces(profile: dict[str, Any]):
    for node in profile.get("hardware") or []:
        for port in node.get("ports") or []:
            for interface in port.get("network_interfaces") or []:
                yield node, port, interface


def _write_config_template(path: Path) -> Path:
    template = {
        "schema": CONFIG_SCHEMA,
        "name": "standalone_multi_bus_demo",
        "output_dir": "standalone_multi_bus_demo",
        "duration_s": 1.0,
        "seed": 42,
        "formats": ["universal-jsonl", "universal-csv", "blf", "dbc", "pcapng"],
        "networks": [
            {"id": "control_can", "technology": "can_fd", "nominal_bitrate": 500000, "data_bitrate": 2000000},
            {"id": "backbone_eth", "technology": "automotive_ethernet", "bitrate": 1000000000},
            {"id": "sensor_i2c", "technology": "i2c", "bitrate": 400000},
        ],
        "hardware": [
            {
                "id": "controller",
                "type": "ecu",
                "ports": [
                    {
                        "id": "controller_can1",
                        "physical_type": "can",
                        "network_interfaces": [{"id": "controller_can_if", "technology": "can_fd", "network": "control_can", "channel": 0}],
                    },
                    {
                        "id": "controller_eth0",
                        "physical_type": "ethernet",
                        "network_interfaces": [{"id": "controller_eth_if", "technology": "automotive_ethernet", "network": "backbone_eth", "ipv4": "192.168.10.10/24"}],
                    },
                    {
                        "id": "controller_i2c0",
                        "physical_type": "i2c",
                        "network_interfaces": [{"id": "controller_i2c_if", "technology": "i2c", "network": "sensor_i2c", "address": "controller"}],
                    },
                ],
            },
            {
                "id": "sensor",
                "type": "sensor",
                "ports": [
                    {
                        "id": "sensor_can1",
                        "physical_type": "can",
                        "network_interfaces": [{"id": "sensor_can_if", "technology": "can_fd", "network": "control_can", "channel": 0}],
                    },
                    {
                        "id": "sensor_eth0",
                        "physical_type": "ethernet",
                        "network_interfaces": [{"id": "sensor_eth_if", "technology": "automotive_ethernet", "network": "backbone_eth", "ipv4": "192.168.10.20/24"}],
                    },
                    {
                        "id": "sensor_i2c0",
                        "physical_type": "i2c",
                        "network_interfaces": [{"id": "sensor_i2c_if", "technology": "i2c", "network": "sensor_i2c", "address": "0x48"}],
                    },
                ],
            },
        ],
        "communications": [
            {"id": "can_status", "sender_interface": "sensor_can_if", "receivers": ["controller_can_if"], "cycle_ms": 20, "payload_bytes": 16},
            {"id": "ethernet_objects", "sender_interface": "sensor_eth_if", "receivers": ["controller_eth_if"], "cycle_ms": 50, "payload_bytes": 256},
            {"id": "i2c_temperature", "sender_interface": "sensor_i2c_if", "receivers": ["controller_i2c_if"], "cycle_ms": 100, "payload_bytes": 4},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _int_option(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return max(0, int(config.get(key) if config.get(key) is not None else default))
    except (TypeError, ValueError):
        return default


def _model_trace_manifest_reference(model_trace: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "schema": model_trace.get("schema"),
        "scenario": model_trace.get("scenario"),
        "trace_file": str(path),
        "comparison": model_trace.get("comparison"),
        "signal_summary": model_trace.get("signal_summary"),
        "fault_summary": model_trace.get("fault_summary"),
        "timing_summary": model_trace.get("timing_summary"),
        "network_load_summary": model_trace.get("network_load_summary"),
        "first_anomaly": model_trace.get("first_anomaly"),
        "affected_routes": model_trace.get("affected_routes"),
        "affected_signals": model_trace.get("affected_signals"),
        "warnings": model_trace.get("warnings"),
        "errors": model_trace.get("errors"),
        "storage": model_trace.get("storage"),
        "model_labels": model_trace.get("model_labels"),
        "clock": model_trace.get("clock"),
    }


def _run_simulation(config: dict[str, Any], *, validate_only: bool = False) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise TypeError("Simulation configuration must be a JSON object.")
    profile = normalize_hardware_config(config)
    validation = validate_hardware_profile(profile)
    summary = hardware_profile_summary(profile)
    registry = technology_registry(profile.get("technology_profiles"))
    out_dir = _output_directory(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = _format_tokens(config.get("formats"))
    written: list[Path] = []
    warnings: list[str] = []
    routes: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    model_trace: dict[str, Any] = {}
    model_trace_reference: dict[str, Any] = {}

    if not validate_only and validation["valid"]:
        routes, events = generate_universal_events(config, profile)
        if "universal-jsonl" in formats or "jsonl" in formats:
            written.append(write_jsonl(out_dir / "traces" / "universal_trace.jsonl", events))
        if "universal-csv" in formats:
            written.append(write_csv(out_dir / "traces" / "universal_trace.csv", events))
        model_trace = build_model_trace(events, config)
        model_trace_path = out_dir / "traces" / "model_trace.json"
        model_trace_path.parent.mkdir(parents=True, exist_ok=True)
        model_trace_path.write_text(
            json.dumps(model_trace, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        written.append(model_trace_path)
        if any(event.get("signals") for event in events):
            golden_events = []
            golden_limit = _int_option(config, "golden_trace_event_limit", DEFAULT_GOLDEN_TRACE_EVENT_LIMIT)
            golden_source = events if golden_limit == 0 else events[:golden_limit]
            for event in golden_source:
                golden_signals = [
                    {**signal, "value": signal.get("golden_value"), "faults": []}
                    for signal in event.get("signals") or []
                ]
                golden_events.append({
                    **event,
                    "status": "transmitted",
                    "faults": [],
                    "signals": golden_signals,
                    "signal_value": golden_signals[0].get("value") if golden_signals else None,
                    "value": golden_signals[0].get("value") if golden_signals else None,
                })
            if golden_limit and len(events) > golden_limit:
                warnings.append(f"Golden Trace wurde fuer interaktive Laufzeit auf {golden_limit} von {len(events)} Events begrenzt.")
            written.append(write_jsonl(out_dir / "traces" / "golden_trace.jsonl", golden_events))
            if model_trace.get("scenario", {}).get("mode") != "NORMAL":
                written.append(write_jsonl(out_dir / "traces" / "fault_trace.jsonl", events))
        model_trace_reference = _model_trace_manifest_reference(model_trace, model_trace_path)

        native_config = _native_configuration(config, profile, out_dir, formats)
        if native_config is not None:
            try:
                from generate_realistic_communication_tool import run_simulation as run_native_simulation

                run_native_simulation(native_config)
                native_root = Path(native_config["output_dir"])
                for artifact_path in sorted(path for path in native_root.rglob("*") if path.is_file()):
                    if artifact_path not in written:
                        written.append(artifact_path)
            except Exception as exc:  # Native writers must not suppress the universal result.
                warnings.append(f"Native writer adapter failed: {exc}")

    manifest = {
        "schema": "communication-simulator.generation-manifest.v1",
        "name": str(config.get("name") or out_dir.name),
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "standalone": True,
        "configuration_schema": str(config.get("schema") or CONFIG_SCHEMA),
        "output_dir": str(out_dir),
        "formats": formats,
        "artifacts": [str(path) for path in written],
        "warnings": warnings,
        "hardware_profile": summary,
        "hardware_validation": validation,
        "technology_catalog": catalog_summary(registry),
        "trace": trace_summary(routes, events),
        "model_simulation": model_trace_reference,
    }
    manifest_path = out_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    written.append(manifest_path)
    result = {
        "schema": RESULT_SCHEMA,
        "status": "validation_failed" if not validation["valid"] else "validated" if validate_only else "completed",
        "standalone": True,
        "output_dir": str(out_dir),
        "artifacts": [str(path) for path in written],
        "warnings": warnings,
        "hardware_profile": summary,
        "hardware_validation": validation,
        "trace": trace_summary(routes, events),
        "model_simulation": model_trace,
    }
    result_path = out_dir / "simulation_result.json"
    result["artifacts"].append(str(result_path))
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return result


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration must contain a JSON object: {path}")
    return payload


class CommunicationSimulator:
    """Standalone orchestration API for validation and trace generation."""

    def run(self, config: dict[str, Any], *, validate_only: bool = False) -> dict[str, Any]:
        return _run_simulation(config, validate_only=validate_only)

    def load_config(self, path: Path) -> dict[str, Any]:
        return _load_config(path)

    def write_config_template(self, path: Path) -> Path:
        return _write_config_template(path)

    def technology_catalog(self) -> dict[str, Any]:
        return catalog_summary()


DEFAULT_SIMULATOR = CommunicationSimulator()


def write_config_template(path: Path) -> Path:
    return DEFAULT_SIMULATOR.write_config_template(path)


def run_simulation(config: dict[str, Any], *, validate_only: bool = False) -> dict[str, Any]:
    return DEFAULT_SIMULATOR.run(config, validate_only=validate_only)


def load_config(path: Path) -> dict[str, Any]:
    return DEFAULT_SIMULATOR.load_config(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone multi-bus and network communication simulator")
    parser.add_argument("--config", type=Path, help="Standalone JSON simulation configuration")
    parser.add_argument("--write-config-template", type=Path, help="Write a standalone configuration template and exit")
    parser.add_argument("--list-technologies", action="store_true", help="List built-in bus and protocol technology profiles")
    parser.add_argument("--validate-only", action="store_true", help="Validate topology without generating trace events")
    args = parser.parse_args()

    if args.write_config_template:
        path = write_config_template(args.write_config_template)
        print(f"Configuration template written: {path.resolve()}")
        return
    if args.list_technologies:
        summary = catalog_summary()
        print(f"Built-in technologies: {summary['technology_count']}")
        for technology in summary["technologies"]:
            print(f"- {technology}")
        return
    if not args.config:
        parser.error("--config is required unless --write-config-template or --list-technologies is used")
    try:
        result = run_simulation(load_config(args.config), validate_only=args.validate_only)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Status: {result['status']}")
    print(f"Output: {result['output_dir']}")
    print(f"Artifacts: {len(result['artifacts'])}")
    if result["warnings"]:
        for warning in result["warnings"]:
            print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
