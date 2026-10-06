"""Primary standalone entry point for the technology-neutral simulator."""

from __future__ import annotations

# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.nis.simulation.bus_technologies import catalog_summary
from backend.nis.simulation.bus_technologies import normalize_technology_id
from backend.nis.simulation.bus_technologies import technology_registry
from backend.nis.simulation.hardware_profile import hardware_profile_summary
from backend.nis.simulation.hardware_profile import normalize_hardware_config
from backend.nis.simulation.hardware_profile import validate_hardware_profile
from backend.nis.simulation.model_based_simulation import build_model_trace
from backend.nis.traces.universal_trace import generate_universal_events
from backend.nis.traces.universal_trace import trace_summary
from backend.nis.traces.universal_trace import write_csv
from backend.nis.traces.universal_trace import write_jsonl
from backend.nis.simulation.simulation_cancellation import check_cancellation
from backend.nis.communication.technologies.ethernet.transport import write_project_captures


CONFIG_SCHEMA = "communication-simulator.simulation-config.v1"
RESULT_SCHEMA = "communication-simulator.simulation-result.v1"
from backend.nis.communication.technologies.can.formats.native_configuration import (
    NATIVE_CAN_FORMATS, NATIVE_ETHERNET_FORMATS, CAN_TECHNOLOGIES, ETHERNET_TECHNOLOGIES,
    _native_participants, _native_configuration,
)
DEFAULT_GOLDEN_TRACE_EVENT_LIMIT = 0


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
    from backend.nis.infrastructure.paths import TRACE_ROOT
    value = config.get("output_dir")
    if not value:
        return (TRACE_ROOT / f"run_{_timestamp_slug()}").resolve()
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.parts and candidate.parts[0].lower() == "traces":
        return (TRACE_ROOT / Path(*candidate.parts[1:])).resolve()
    return (TRACE_ROOT / candidate).resolve()






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
    check_cancellation(force=True)
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
    native_ethernet: dict[str, Any] = {}

    if not validate_only and validation["valid"]:
        trace_start = datetime.now(timezone.utc).timestamp()
        routes, events = generate_universal_events(config, profile, start_utc=trace_start)
        check_cancellation(force=True)
        # A baseline is an independently scheduled normal run. Copying a faulty
        # event cannot undo its payload, delivery history, queueing or timing.
        golden_config = deepcopy(config)
        golden_config["scenario"] = {**(golden_config.get("scenario") or {}), "mode": "NORMAL", "faults": []}
        golden_config["faults"] = []
        for source in [golden_config, golden_config.get("parameters") or {},
                       *(golden_config.get("networks") or []), *(golden_config.get("communications") or [])]:
            source["fault_model"] = {}
            for key in ("dropout_probability", "corruption_probability", "duplicate_probability", "reordering_probability"):
                source[key] = 0
        _, golden_events = generate_universal_events(golden_config, normalize_hardware_config(golden_config), start_utc=trace_start)
        golden_by_id = {event["event_id"]: event for event in golden_events}
        for event in events:
            check_cancellation()
            baseline = golden_by_id.get(event["event_id"])
            if baseline is None:
                continue
            baseline_signals = {sample["signal_id"]: sample for sample in baseline.get("signals") or []}
            for sample in event.get("signals") or []:
                if sample.get("signal_id") in baseline_signals:
                    sample["golden_value"] = baseline_signals[sample["signal_id"]].get("value")
            event["golden_time_s"] = baseline["time_s"]
            if event.get("signals"):
                event["golden_value"] = event["signals"][0].get("golden_value")
        if "universal-jsonl" in formats or "jsonl" in formats:
            written.append(write_jsonl(out_dir / "traces" / "universal_trace.jsonl", events))
        if "universal-csv" in formats:
            written.append(write_csv(out_dir / "traces" / "universal_trace.csv", events))
        check_cancellation(force=True)
        model_trace = build_model_trace(events, config)
        check_cancellation(force=True)
        model_trace_path = out_dir / "traces" / "model_trace.json"
        model_trace_path.parent.mkdir(parents=True, exist_ok=True)
        model_trace_path.write_text(
            json.dumps(model_trace, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        written.append(model_trace_path)
        if events or golden_events:
            golden_limit = _int_option(config, "golden_trace_event_limit", DEFAULT_GOLDEN_TRACE_EVENT_LIMIT)
            golden_source = golden_events if golden_limit == 0 else golden_events[:golden_limit]
            if golden_limit and len(golden_events) > golden_limit:
                warnings.append(f"Golden Trace wurde durch die konfigurierte Exportgrenze auf {golden_limit} von {len(golden_events)} Events begrenzt.")
            written.append(write_jsonl(out_dir / "traces" / "golden_trace.jsonl", golden_source))
            if model_trace.get("scenario", {}).get("mode") != "NORMAL":
                written.append(write_jsonl(out_dir / "traces" / "fault_trace.jsonl", events))
        model_trace_reference = _model_trace_manifest_reference(model_trace, model_trace_path)

        check_cancellation(force=True)
        packet_paths, native_ethernet = write_project_captures(out_dir / "native", events, formats)
        written.extend(packet_paths)
        if native_ethernet.get("unsupported_events"):
            warnings.append("PCAP enthält ausschließlich unterstützte IP-Ereignisse; andere Technologien bleiben im Universal Trace. Keine Ersatz-/Demo-Pakete.")
        native_config = _native_configuration(config, profile, out_dir, formats)
        if native_config is not None:
            try:
                from backend.nis.simulation.communication_generator import run_simulation as run_native_simulation

                run_native_simulation(native_config)
                native_root = Path(native_config["output_dir"])
                for artifact_path in sorted(path for path in native_root.rglob("*") if path.is_file()):
                    if artifact_path not in written:
                        written.append(artifact_path)
            except Exception as exc:  # Native writers must not suppress the universal result.
                warnings.append(f"Native writer adapter failed: {exc}")

    check_cancellation(force=True)
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
        "native_ethernet": native_ethernet,
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
        "native_ethernet": native_ethernet,
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
