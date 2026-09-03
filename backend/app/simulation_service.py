"""Adapter between HTTP payloads and the existing simulator API."""

from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path
from typing import Any

from .config import SIMULATOR_ROOT


if str(SIMULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATOR_ROOT))

from bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY  # noqa: E402
from communication_simulator import CommunicationSimulator  # noqa: E402
from standalone_cli import (  # noqa: E402
    DOMAIN_LABELS,
    SUPPORTED_STANDALONE_FORMATS,
    StandaloneSimulationOptions,
    domain_for_technology,
)

from .runtime_analysis import RuntimeBusLoadMonitor


DEFAULT_WORKFLOW_EVENT_LIMIT = 100_000


def _workflow_event_limit() -> int:
    raw = os.environ.get("WORKFLOW_EVENT_LIMIT", str(DEFAULT_WORKFLOW_EVENT_LIMIT)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_WORKFLOW_EVENT_LIMIT
    return min(10_000_000, max(1, value))


class SimulationService:
    def __init__(self) -> None:
        self.simulator = CommunicationSimulator()
        self.runtime_load_monitor = RuntimeBusLoadMonitor()

    def catalog(self) -> dict[str, Any]:
        domains: list[dict[str, Any]] = []
        for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
            technologies = []
            for technology_id, profile in generator.generate().items():
                technology = {"id": technology_id, **profile.to_dict()}
                technology["parameter_schema"] = self._parameter_schema(technology_id, technology)
                technologies.append(technology)
            domains.append(
                {
                    "id": generator.domain,
                    "label": DOMAIN_LABELS.get(generator.domain, generator.domain),
                    "technologies": technologies,
                }
            )
        return {
            "technology_count": sum(len(item["technologies"]) for item in domains),
            "domains": domains,
            "formats": sorted(SUPPORTED_STANDALONE_FORMATS),
        }

    @staticmethod
    def _parameter_schema(technology_id: str, technology: dict[str, Any]) -> list[dict[str, Any]]:
        """Describe editable parameters so the UI does not hard-code technology forms."""
        maximum_payload = int(technology.get("max_payload_bytes") or 65_535)

        def field(
            key: str,
            label: str,
            category: str,
            scope: str,
            *,
            field_type: str = "number",
            unit: str | None = None,
            default: Any = 0,
            minimum: float | None = None,
            maximum: float | None = None,
            options: list[str] | None = None,
            description: str = "",
            simulation_relevant: bool = True,
            validation_relevant: bool = True,
        ) -> dict[str, Any]:
            item: dict[str, Any] = {
                "key": key,
                "label": label,
                "category": category,
                "scope": scope,
                "type": field_type,
                "default": default,
                "description": description,
                "required": True,
                "editable": True,
                "simulation_relevant": simulation_relevant,
                "validation_relevant": validation_relevant,
            }
            if unit:
                item["unit"] = unit
            if minimum is not None:
                item["min"] = minimum
            if maximum is not None:
                item["max"] = maximum
            if options:
                item["options"] = options
            return item

        fields: list[dict[str, Any]] = [
            field("bitrate", "Bitrate", "physical", "network", unit="bit/s", minimum=1, default=technology.get("default_bitrate") or 1_000_000, description="Nominale Leitungskapazitaet des Netzes."),
            field("payload_bytes", "Payload", "physical", "message", unit="Byte", minimum=0, maximum=maximum_payload, default=min(8, maximum_payload), description="Nutzdaten pro Nachricht."),
            field("cycle_ms", "Cycle Time", "timing", "message", unit="ms", minimum=0.001, default=100, description="Standardperiode fuer zyklische Nachrichten."),
            field("minimum_cycle_time_ms", "Minimum Cycle Time", "timing", "message", unit="ms", minimum=0.001, default=1),
            field("deadline_ms", "Deadline", "timing", "message", unit="ms", minimum=0.001, default=100),
            field("timeout_ms", "Timeout", "timing", "route", unit="ms", minimum=0.001, default=500),
            field("maximum_latency_ms", "Maximum Latency", "timing", "route", unit="ms", minimum=0, default=100),
            field("jitter_ms", "Jitter Budget", "timing", "route", unit="ms", minimum=0, default=1),
            field("freshness_ms", "Data Freshness", "timing", "signal", unit="ms", minimum=0, default=500),
            field("source_processing_delay_ms", "Source Processing", "timing", "route", unit="ms", minimum=0, default=0.1),
            field("target_processing_delay_ms", "Target Processing", "timing", "route", unit="ms", minimum=0, default=0.1),
            field("propagation_delay_ms", "Propagation", "timing", "network", unit="ms", minimum=0, default=0.01),
            field("target_bus_load_percent", "Ziel-Buslast", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=60, description="Zielwert fuer die aus Routing, Payload, Zyklus und Bitrate berechnete Buslast.", simulation_relevant=False),
            field("peak_factor", "Peak Factor", "capacity", "analysis", minimum=1, default=1.15, simulation_relevant=False),
            field("burst_factor", "Burst Factor", "capacity", "analysis", minimum=1, default=1.5, simulation_relevant=False),
            field("burst_window_ms", "Burst Window", "capacity", "analysis", unit="ms", minimum=0.1, default=100, simulation_relevant=False),
            field("warning_threshold", "Load Warning", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=60, simulation_relevant=False),
            field("critical_threshold", "Load Critical", "capacity", "analysis", unit="%", minimum=0, maximum=100, default=75, simulation_relevant=False),
            field("overload_threshold", "Load Overload", "capacity", "analysis", unit="%", minimum=1, maximum=100, default=90, simulation_relevant=False),
            field("queue_size", "Queue Size", "qos", "network", unit="Frames", minimum=1, default=256),
            field("queue_policy", "Queue Policy", "qos", "network", field_type="select", default="FIFO", options=["FIFO", "PRIORITY", "STRICT_PRIORITY", "WEIGHTED_PRIORITY", "WRR", "ROUND_ROBIN", "TIME_TRIGGERED", "TAS", "CBS", "CUSTOM"]),
            field("qos_priority", "Default Priority", "qos", "route", minimum=0, maximum=7, default=3),
            field("traffic_class", "Traffic Class", "qos", "route", field_type="select", default="BEST_EFFORT", options=["BEST_EFFORT", "CONTROL", "REALTIME", "SAFETY_CRITICAL"]),
            field("reserved_bandwidth_percent", "Reserved Bandwidth", "qos", "network", unit="%", minimum=0, maximum=100, default=0),
            field("packet_loss_probability", "Packet Loss", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("frame_loss_probability", "Frame Loss", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("bit_error_rate", "Bit Error Rate", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("corruption_probability", "Corruption", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("duplicate_probability", "Duplication", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("reordering_probability", "Reordering", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("retransmission_enabled", "Retransmission", "reliability", "reliability", field_type="boolean", default=False),
            field("retransmission_rate", "Retransmission Rate", "reliability", "reliability", minimum=0, maximum=1, default=0),
            field("retry_limit", "Retry Limit", "reliability", "reliability", minimum=0, default=0),
            field("retransmission_delay_ms", "Retry Delay", "reliability", "reliability", unit="ms", minimum=0, default=0),
            field("required_reliability", "Required Reliability", "reliability", "reliability", minimum=0, maximum=1, default=0.999),
            field("clock_offset_ms", "Clock Offset", "synchronization", "network", unit="ms", default=0),
            field("clock_drift_ppm", "Clock Drift", "synchronization", "network", unit="ppm", minimum=0, default=20),
            field("sync_precision_ms", "Sync Precision", "synchronization", "network", unit="ms", minimum=0, default=0.1),
            field("sync_interval_ms", "Sync Interval", "synchronization", "network", unit="ms", minimum=0.001, default=1000),
            field("sync_method", "Sync Method", "synchronization", "network", field_type="select", default="NONE", options=["NONE", "NTP", "PTP", "GPTP", "BUS_NATIVE"]),
            field("maximum_sync_error_ms", "Maximum Sync Error", "synchronization", "network", unit="ms", minimum=0, default=1),
            field("gateway_delay_ms", "Gateway Processing", "gateway", "gateway", unit="ms", minimum=0, default=0.2),
            field("gateway_queue_delay_ms", "Gateway Queueing", "gateway", "gateway", unit="ms", minimum=0, default=0),
            field("protocol_conversion_delay_ms", "Protocol Conversion", "gateway", "gateway", unit="ms", minimum=0, default=0),
            field("gateway_maximum_throughput", "Gateway Throughput", "gateway", "gateway", unit="bit/s", minimum=1, default=100_000_000),
            field("gateway_input_buffer", "Gateway Input Buffer", "gateway", "gateway", unit="Frames", minimum=1, default=256),
            field("gateway_output_buffer", "Gateway Output Buffer", "gateway", "gateway", unit="Frames", minimum=1, default=256),
            field("gateway_maximum_routes", "Gateway Maximum Routes", "gateway", "gateway", minimum=1, default=10_000),
            field("gateway_maximum_messages_s", "Gateway Messages per Second", "gateway", "gateway", unit="msg/s", minimum=1, default=100_000),
            field("duration_s", "Simulation Duration", "simulation", "simulation", unit="s", minimum=0.001, default=1, validation_relevant=False),
            field("seed", "Random Seed", "simulation", "simulation", minimum=0, default=42, validation_relevant=False),
            field("max_events", "Maximum Events", "simulation", "simulation", minimum=1, default=100_000, validation_relevant=False),
            field("dropout_probability", "Failure Injection Dropout", "simulation", "simulation", minimum=0, maximum=1, default=0, validation_relevant=False),
        ]
        normalized = technology_id.lower()
        if normalized in {"can_fd", "can_xl"}:
            fields.extend(
                [
                    field("arbitration_bitrate", "Arbitration Bitrate", "physical", "network", unit="bit/s", minimum=1, default=500_000),
                    field("data_bitrate", "Data Bitrate", "physical", "network", unit="bit/s", minimum=1, default=technology.get("default_bitrate") or 2_000_000),
                    field("sample_point_percent", "Sample Point", "physical", "network", unit="%", minimum=50, maximum=99.9, default=80),
                ]
            )
        if "ethernet" in normalized or normalized in {"someip", "udp", "tcp", "dds_rtps"}:
            fields.extend(
                [
                    field("mtu_bytes", "MTU", "physical", "network", unit="Byte", minimum=64, maximum=65_535, default=1500),
                    field("duplex", "Duplex", "physical", "network", field_type="select", default="FULL", options=["FULL", "HALF"]),
                    field("vlan_id", "VLAN ID", "qos", "network", minimum=0, maximum=4094, default=0),
                    field("rate_limit_bit_s", "Rate Limit", "qos", "route", unit="bit/s", minimum=0, default=0),
                ]
            )
        if normalized in {"dds", "dds_rtps", "ros2"}:
            fields.extend(
                [
                    field("history_depth", "History Depth", "qos", "route", minimum=1, default=10),
                    field("history_kind", "History", "qos", "route", field_type="select", default="KEEP_LAST", options=["KEEP_LAST", "KEEP_ALL"]),
                    field("durability", "Durability", "qos", "route", field_type="select", default="VOLATILE", options=["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"]),
                    field("lifespan_ms", "Lifespan", "timing", "message", unit="ms", minimum=0, default=0),
                    field("liveliness", "Liveliness", "qos", "route", field_type="select", default="AUTOMATIC", options=["AUTOMATIC", "MANUAL_BY_PARTICIPANT", "MANUAL_BY_TOPIC"]),
                    field("reliability_mode", "Reliability Mode", "reliability", "route", field_type="select", default="RELIABLE", options=["BEST_EFFORT", "RELIABLE"]),
                ]
            )
        if "ethercat" in normalized:
            fields.append(field("distributed_clock_cycle_ms", "Distributed Clock Cycle", "synchronization", "network", unit="ms", minimum=0.001, default=1))
        return fields

    def prepare_config(self, payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Die Simulationsanfrage muss ein JSON-Objekt sein.")
        if isinstance(payload.get("config"), dict):
            config = copy.deepcopy(payload["config"])
            for key in (
                "project_id", "scenario", "duration_s", "seed", "formats", "max_events",
                "model_trace_frame_limit", "model_trace_signal_point_limit", "model_trace_points_per_signal",
                "model_trace_event_limit", "golden_trace_event_limit",
                "dropout_probability", "corruption_probability", "duplicate_probability",
                "reordering_probability",
            ):
                if key in payload:
                    config[key] = copy.deepcopy(payload[key])
            if payload.get("workflow_managed"):
                try:
                    requested_events = int(config.get("max_events") or DEFAULT_WORKFLOW_EVENT_LIMIT)
                except (TypeError, ValueError):
                    requested_events = DEFAULT_WORKFLOW_EVENT_LIMIT
                config["max_events"] = min(max(1, requested_events), _workflow_event_limit())
            config["output_dir"] = str(output_dir)
            return config

        technology_id = str(payload.get("technology") or "can_fd")
        technology = DEFAULT_TECHNOLOGY_REGISTRY.resolve(technology_id)
        if technology.get("requires_profile"):
            raise ValueError(f"Unbekannte Technologie: {technology_id}")

        formats_value = payload.get("formats") or ["universal-jsonl", "universal-csv"]
        if isinstance(formats_value, str):
            formats = tuple(
                token for token in re.split(r"[\s,;]+", formats_value.lower()) if token
            )
        else:
            formats = tuple(str(item).strip().lower() for item in formats_value if str(item).strip())
        unknown_formats = sorted(set(formats) - SUPPORTED_STANDALONE_FORMATS)
        if unknown_formats:
            raise ValueError(f"Unbekannte Ausgabeformate: {', '.join(unknown_formats)}")

        options = StandaloneSimulationOptions(
            technology=technology["id"],
            industry=str(payload.get("industry") or domain_for_technology(technology["id"])),
            output_dir=output_dir,
            formats=formats,
            duration_s=float(payload.get("duration_s", 1.0)),
            seed=int(payload.get("seed", 42)),
            node_count=int(payload.get("node_count", 2)),
            bitrate=int(payload["bitrate"]) if payload.get("bitrate") not in {None, ""} else None,
            cycle_ms=float(payload.get("cycle_ms", 100.0)),
            payload_bytes=int(payload.get("payload_bytes", min(8, int(technology.get("max_payload_bytes") or 8)))),
            max_events=int(payload.get("max_events", 100_000)),
            dropout_probability=float(payload.get("dropout_probability", 0.0)),
            corruption_probability=float(payload.get("corruption_probability", 0.0)),
            network_id=str(payload["network_id"]) if payload.get("network_id") else None,
        )
        self._validate_options(options, technology)
        return options.to_config()

    @staticmethod
    def _validate_options(
        options: StandaloneSimulationOptions,
        technology: dict[str, Any],
    ) -> None:
        if not 2 <= options.node_count <= 100:
            raise ValueError("node_count muss zwischen 2 und 100 liegen.")
        if options.duration_s <= 0 or options.cycle_ms <= 0:
            raise ValueError("Dauer und Zyklus müssen größer als 0 sein.")
        if not 1 <= options.max_events <= 10_000_000:
            raise ValueError("max_events muss zwischen 1 und 10.000.000 liegen.")
        if options.bitrate is not None and options.bitrate < 1:
            raise ValueError("Die Bitrate muss mindestens 1 bit/s betragen.")
        payload_limit = int(technology.get("max_payload_bytes") or 65_535)
        if not 0 <= options.payload_bytes <= payload_limit:
            raise ValueError(f"payload_bytes muss zwischen 0 und {payload_limit} liegen.")
        for label, value in (
            ("dropout_probability", options.dropout_probability),
            ("corruption_probability", options.corruption_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{label} muss zwischen 0 und 1 liegen.")

    def run(
        self,
        payload: dict[str, Any],
        output_dir: Path,
        *,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        config = self.prepare_config(payload, output_dir)
        project_id = str(payload.get("project_id") or config.get("project_id") or "default")
        if payload.get("workflow_managed") or project_id != "default":
            from ..engineering.simulation import enrich_simulation_config, validate_scenario

            config = enrich_simulation_config(config, project_id)
            config["scenario"] = validate_scenario(
                config.get("scenario") if isinstance(config.get("scenario"), dict) else {},
                config.get("engineering_model") if isinstance(config.get("engineering_model"), dict) else {},
            )
        result = self.simulator.run(config, validate_only=validate_only)
        if not validate_only:
            result["runtime_metrics"] = self.runtime_load_monitor.analyze(result, config)
            if payload.get("workflow_managed") or project_id != "default":
                from ..engineering.simulation import artifact_job_id, persist_trace_metadata

                persist_trace_metadata(project_id, artifact_job_id(output_dir), result, config)
        return result
