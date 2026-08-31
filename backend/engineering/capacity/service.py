"""Capacity, timing and full-workflow preflight analysis."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from ..repository import list_objects
from ..routing.repository import list_routes
from ..routing.validation import PROTOCOL_CAPACITY, RoutingValidator
from ..signal_audit import build_generation_signal_audit
from ..workflow.models import WORKFLOW_LABELS, WORKFLOW_STEPS
from ..workflow.service import WorkflowStatusService
from .calculators import (
    classify_load,
    clock_drift_ms,
    estimate_frame,
    scheduled_queueing_delay_ms,
    utilization_percent,
)


DEFAULT_PARAMETER_VALUES: dict[str, Any] = {
    "industry": "automotive",
    "technology": "can_fd",
    "formats": ["universal-jsonl", "universal-csv"],
    "bitrate": 2_000_000,
    "cycle_ms": 100.0,
    "payload_bytes": 8,
    "queue_size": 256,
    "warning_threshold": 60.0,
    "critical_threshold": 75.0,
    "overload_threshold": 90.0,
    "target_bus_load_percent": 60.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parameters_for_protocol(
    protocol: str, parameters: dict[str, Any], configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aliases = {"AUTOMOTIVE_ETHERNET": "ETHERNET", "CANFD": "CAN_FD", "CAN_CLASSIC": "CAN", "SOMEIP": "SOME_IP"}

    def canonical(value: Any) -> str:
        name = str(value or "").upper().replace("-", "_").replace(" ", "_")
        return aliases.get(name, name)

    resolved = dict(parameters)
    configured = canonical(parameters.get("technology") or parameters.get("protocol"))
    target = canonical(protocol)
    # A global speed applies to the selected technology, not every bus in a mixed network.
    if configured and configured != target:
        for key in ("bitrate", "arbitration_bitrate", "data_bitrate"):
            resolved.pop(key, None)
        resolved["bitrate"] = PROTOCOL_CAPACITY.get(target, PROTOCOL_CAPACITY["CUSTOM"])[0]
    resolved.setdefault("bitrate", PROTOCOL_CAPACITY.get(target, PROTOCOL_CAPACITY["CUSTOM"])[0])
    for key in ("bitrate", "arbitration_bitrate", "data_bitrate"):
        value = (configuration or {}).get(key)
        if _number(value, 0) > 0:
            resolved[key] = value
    return resolved


def _payload_bytes(route: dict[str, Any], messages: dict[str, dict[str, Any]], default: int) -> int:
    payload = route.get("payload") or {}
    direct = payload.get("payload_bytes") or payload.get("length_bytes") or payload.get("dlc")
    if direct is not None:
        return max(0, int(_number(direct, default)))
    message_ids = list(dict.fromkeys([
        *[str(item) for item in payload.get("message_ids", []) if item],
        *([str(payload.get("message_id"))] if payload.get("message_id") else []),
    ]))
    selected = [messages[item] for item in message_ids if item in messages]
    if selected:
        return sum(max(0, int(_number(message.get("dlc"), default))) for message in selected)
    return default


def _route_segment_network_ids(
    source: dict[str, Any],
    route_path: dict[str, Any],
    destinations: list[dict[str, Any]],
    fallback_network_id: str,
) -> list[str]:
    values: list[Any] = [
        source.get("network_id"),
        route_path.get("network_id"),
    ]
    for hop in route_path.get("hops") or []:
        if isinstance(hop, dict):
            values.append(hop.get("network_id"))
    for destination in destinations:
        values.append(destination.get("network_id"))

    segment_ids: list[str] = []
    seen: set[str] = set()
    for value in values:
        network_id = str(value or "").strip()
        if not network_id or network_id in seen:
            continue
        seen.add(network_id)
        segment_ids.append(network_id)
    return segment_ids or [fallback_network_id]


def _requirement_value(
    route_timing: dict[str, Any],
    message: dict[str, Any],
    signals: list[dict[str, Any]],
    *keys: str,
) -> float | None:
    """Resolve the strictest positive requirement from route, message and signals."""
    values: list[float] = []
    message_requirements = message.get("configuration") or {}
    for source in (route_timing, message_requirements):
        for key in keys:
            value = _number(source.get(key), 0.0)
            if value > 0:
                values.append(value)
    for signal in signals:
        communication = signal.get("communication") or {}
        for key in keys:
            value = _number(communication.get(key), 0.0)
            if value > 0:
                values.append(value)
    return min(values) if values else None


def _priority_value(route: dict[str, Any], message: dict[str, Any], signals: list[dict[str, Any]]) -> int:
    semantic = {
        "LOW": 20,
        "NORMAL": 50,
        "HIGH": 70,
        "CRITICAL": 90,
        "SAFETY_CRITICAL": 100,
    }
    policy = route.get("routing_policy") or {}
    candidates: list[Any] = [
        (route.get("route") or {}).get("priority"),
        policy.get("priority"),
        (message.get("configuration") or {}).get("priority"),
    ]
    candidates.extend((signal.get("communication") or {}).get("priority") for signal in signals)
    for value in candidates:
        if isinstance(value, (int, float)):
            numeric = float(value)
            if 0 <= numeric <= 7:
                numeric = numeric / 7.0 * 100.0
            return max(0, min(100, int(numeric)))
        normalized = str(value or "").upper()
        if normalized in semantic:
            return semantic[normalized]
    return 50


class CapacityTimingService:
    CALCULATION_VERSION = "2.1"

    def __init__(self, project_id: str = "default") -> None:
        self.workflow = WorkflowStatusService(project_id)

    def calculate(self, overrides: dict[str, Any] | None = None, *, persist: bool = True) -> dict[str, Any]:
        state = self.workflow.get()
        parameters = {
            **DEFAULT_PARAMETER_VALUES,
            **(state.get("parameters") or {}),
            **(overrides or {}),
        }
        thresholds = {
            "warning": _number(parameters.get("warning_threshold"), 60.0),
            "critical": _number(parameters.get("critical_threshold"), 75.0),
            "overload": _number(parameters.get("overload_threshold"), 90.0),
        }
        target_bus_load = min(max(_number(parameters.get("target_bus_load_percent"), 60.0), 0.0), 100.0)
        routes = [
            route
            for route in list_routes(limit=500)
            if route.get("approval_state") == "APPROVED"
            and route.get("status") not in {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}
        ]
        messages = {str(item["id"]): item for item in list_objects("Message", limit=500)}
        signals = {str(item["id"]): item for item in list_objects("Signal", limit=2000)}
        interfaces = {str(item["id"]): item for item in list_objects("Interface", limit=500)}
        hardware = {str(item["id"]): item for item in list_objects("HardwareNode", limit=500)}
        route_metrics: list[dict[str, Any]] = []
        logical_route_metrics: list[dict[str, Any]] = []
        network_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        generic_models: set[str] = set()

        default_protocol = str(parameters.get("technology") or parameters.get("protocol") or "CAN_FD")
        default_payload = int(_number(parameters.get("payload_bytes"), 8))
        default_cycle = _number(parameters.get("cycle_ms"), 100.0)
        peak_factor = max(1.0, _number(parameters.get("peak_factor"), 1.15))
        burst_factor = max(peak_factor, _number(parameters.get("burst_factor"), 1.5))
        burst_window_ms = max(0.1, _number(parameters.get("burst_window_ms"), 100.0))
        retry_rate = min(max(_number(parameters.get("retransmission_rate"), 0.0), 0.0), 1.0)
        gateway_delay = max(0.0, _number(parameters.get("gateway_delay_ms"), 0.2))
        gateway_queue_delay = max(0.0, _number(parameters.get("gateway_queue_delay_ms"), 0.0))
        protocol_conversion_delay = max(0.0, _number(parameters.get("protocol_conversion_delay_ms"), 0.0))
        source_processing_delay = max(0.0, _number(parameters.get("source_processing_delay_ms"), 0.1))
        target_processing_delay = max(0.0, _number(parameters.get("target_processing_delay_ms"), 0.1))
        propagation_delay = max(0.0, _number(parameters.get("propagation_delay_ms"), 0.0))
        sync_precision_ms = max(0.0, _number(parameters.get("sync_precision_ms"), 0.1))
        clock_drift_ppm = max(0.0, _number(parameters.get("clock_drift_ppm"), 20.0))
        observation_s = max(0.001, _number(parameters.get("duration_s"), 1.0))
        queue_policy = str(parameters.get("queue_policy") or "FIFO")
        configured_packet_loss = min(
            max(_number(parameters.get("packet_loss_probability"), _number(parameters.get("dropout_probability"), 0.0)), 0.0),
            1.0,
        )

        for route in routes:
            source = route.get("source") or {}
            route_path = route.get("route") or {}
            timing = route.get("timing") or {}
            destinations = [item for item in route.get("destinations") or [] if isinstance(item, dict)]
            protocol = str(source.get("protocol") or route_path.get("protocol") or default_protocol)
            network_id = str(
                source.get("network_id")
                or source.get("interface_id")
                or route_path.get("network_id")
                or protocol.upper()
            )
            segment_network_ids = _route_segment_network_ids(source, route_path, destinations, network_id)
            segment_count = max(1, len(segment_network_ids))
            payload_bytes = _payload_bytes(route, messages, default_payload)
            payload = route.get("payload") or {}
            message_id = str(payload.get("message_id") or "")
            message = messages.get(message_id, {})
            selected_signals = [signals[str(item)] for item in payload.get("signal_ids") or [] if str(item) in signals]
            cycle_requirement = _requirement_value(
                timing,
                message,
                selected_signals,
                "cycle_time_ms",
                "cycle_time",
            )
            cycle_ms = cycle_requirement or _number(message.get("cycle_ms"), default_cycle)
            interface = interfaces.get(str(source.get("interface_id") or ""), {})
            route_parameters = parameters_for_protocol(protocol, parameters, interface.get("configuration"))
            estimate = estimate_frame(protocol, payload_bytes, route_parameters)
            average = utilization_percent(estimate.transmission_time_s, cycle_ms) * (1.0 + retry_rate)
            peak = average * peak_factor
            burst = average * burst_factor
            gateways = route_path.get("gateways") or []
            priority = _priority_value(route, message, selected_signals)
            queue_ms = scheduled_queueing_delay_ms(
                estimate.transmission_time_s,
                average,
                queue_policy,
                priority,
            )
            transmission_ms = estimate.transmission_time_s * 1000.0
            gateway_processing_ms = len(gateways) * gateway_delay
            gateway_queue_ms = len(gateways) * gateway_queue_delay
            conversion_ms = len(gateways) * protocol_conversion_delay
            route_queue_ms = queue_ms * segment_count
            route_transmission_ms = transmission_ms * segment_count
            route_propagation_ms = propagation_delay * segment_count
            end_to_end = (
                source_processing_delay
                + route_queue_ms
                + route_transmission_ms
                + route_propagation_ms
                + gateway_processing_ms
                + gateway_queue_ms
                + conversion_ms
                + target_processing_delay
            )
            jitter_limit = _requirement_value(
                timing,
                message,
                selected_signals,
                "jitter_limit_ms",
                "maximum_jitter_ms",
                "maximum_jitter",
            ) or _number(parameters.get("jitter_ms"), 0.0)
            max_latency = _requirement_value(
                timing,
                message,
                selected_signals,
                "max_latency_ms",
                "maximum_latency_ms",
                "maximum_latency",
                "deadline_ms",
                "deadline",
            )
            timeout_ms = _requirement_value(timing, message, selected_signals, "timeout_ms", "timeout")
            freshness_ms = _requirement_value(
                timing,
                message,
                selected_signals,
                "freshness_ms",
                "data_freshness_limit",
            )
            estimated_jitter = route_queue_ms * 0.25 + gateway_queue_ms * 0.25 + sync_precision_ms
            load_status = classify_load(max(average, peak, burst), thresholds)
            latency_status = "FAIL" if max_latency and end_to_end > max_latency else "PASS"
            jitter_status = "FAIL" if jitter_limit and estimated_jitter > jitter_limit else "PASS"
            breakdown = {
                "source_processing_ms": round(source_processing_delay, 6),
                "source_queue_ms": round(route_queue_ms, 6),
                "network_transmission_ms": round(route_transmission_ms, 6),
                "propagation_ms": round(route_propagation_ms, 6),
                "gateway_processing_ms": round(gateway_processing_ms, 6),
                "gateway_queue_ms": round(gateway_queue_ms, 6),
                "protocol_conversion_ms": round(conversion_ms, 6),
                "target_processing_ms": round(target_processing_delay, 6),
            }
            bottleneck_key = max(breakdown, key=breakdown.get)
            metric = {
                "route_id": str(route["id"]),
                "route_code": route.get("route_code"),
                "name": route.get("name"),
                "network_id": network_id,
                "physical_network_ids": segment_network_ids,
                "route_segment_count": segment_count,
                "protocol": estimate.protocol,
                "bitrate": _number(route_parameters.get("bitrate"), 1_000_000.0),
                "payload_bytes": payload_bytes,
                "cycle_ms": cycle_ms,
                "frame_bits": estimate.frame_bits,
                "average_load_percent": round(average, 4),
                "peak_load_percent": round(peak, 4),
                "burst_load_percent": round(burst, 4),
                "burst_window_ms": burst_window_ms,
                "transmission_latency_ms": round(route_transmission_ms, 6),
                "queueing_latency_ms": round(route_queue_ms, 6),
                "gateway_latency_ms": round(gateway_processing_ms + gateway_queue_ms + conversion_ms, 6),
                "end_to_end_latency_ms": round(end_to_end, 6),
                "estimated_jitter_ms": round(estimated_jitter, 6),
                "jitter_budget_ms": jitter_limit,
                "max_latency_ms": max_latency,
                "timeout_ms": timeout_ms,
                "freshness_ms": freshness_ms,
                "latency_status": latency_status,
                "jitter_status": jitter_status,
                "status": load_status,
                "calculation_model": estimate.calculation_model,
                "calculation_version": estimate.calculation_version,
                "producer": source.get("node_id"),
                "consumers": [item.get("node_id") for item in destinations],
                "gateways": gateways,
                "priority": priority,
                "queue_policy": queue_policy,
                "breakdown": breakdown,
                "bottleneck": {"component": bottleneck_key, "delay_ms": breakdown[bottleneck_key]},
                "requirement_status": "FAIL" if "FAIL" in {latency_status, jitter_status} else "PASS",
            }
            if estimate.is_generic_estimate:
                generic_models.add(protocol.upper())
            logical_route_metrics.append(metric)
            for index, segment_network_id in enumerate(segment_network_ids):
                segment_metric = {
                    **metric,
                    "network_id": segment_network_id,
                    "route_segment_index": index + 1,
                    "route_segment_count": segment_count,
                }
                route_metrics.append(segment_metric)
                network_groups[segment_network_id].append(segment_metric)

        network_metrics: list[dict[str, Any]] = []
        for network_id, items in network_groups.items():
            average = sum(item["average_load_percent"] for item in items)
            peak = sum(item["peak_load_percent"] for item in items)
            burst = sum(item["burst_load_percent"] for item in items)
            governing_load = max(average, peak, burst)
            network_metrics.append(
                {
                    "network_id": network_id,
                    "protocol": items[0]["protocol"],
                    "route_count": len(items),
                    "bitrate": items[0]["bitrate"],
                    "average_load_percent": round(average, 4),
                    "peak_load_percent": round(peak, 4),
                    "burst_load_percent": round(burst, 4),
                    "available_capacity_percent": round(100.0 - average, 4),
                    "capacity_reserve_percent": round(100.0 - average, 4),
                    "capacity_margin_percent": round(100.0 - governing_load, 4),
                    "target_bus_load_percent": target_bus_load,
                    "target_margin_percent": round(target_bus_load - governing_load, 4),
                    "target_status": "PASS" if governing_load <= target_bus_load else "EXCEEDED",
                    "status": classify_load(governing_load, thresholds),
                    "worst_end_to_end_latency_ms": round(
                        max((item["end_to_end_latency_ms"] for item in items), default=0.0), 6
                    ),
                    "top_contributors": [
                        {"route_id": item["route_id"], "name": item["name"], "load_percent": item["average_load_percent"]}
                        for item in sorted(items, key=lambda entry: entry["average_load_percent"], reverse=True)[:5]
                    ],
                }
            )
        network_metrics.sort(key=lambda item: item["burst_load_percent"], reverse=True)
        route_metrics.sort(key=lambda item: item["burst_load_percent"], reverse=True)

        gateway_metrics = []
        by_gateway: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for metric in logical_route_metrics:
            for gateway in metric["gateways"]:
                gateway_id = str(gateway.get("node_id") if isinstance(gateway, dict) else gateway)
                by_gateway[gateway_id].append(metric)
        for gateway_id, items in by_gateway.items():
            gateway = hardware.get(gateway_id, {})
            hardware_information = gateway.get("hardware_information") or {}
            peak_throughput = sum(
                item["frame_bits"] / max(item["cycle_ms"] / 1000.0, 0.000001)
                for item in items
            )
            maximum_throughput = _number(
                hardware_information.get("maximum_throughput"),
                _number(parameters.get("gateway_maximum_throughput"), 100_000_000.0),
            )
            processing_load = peak_throughput / max(maximum_throughput, 1.0) * 100.0
            gateway_metrics.append(
                {
                    "gateway_id": gateway_id,
                    "name": gateway.get("name") or gateway_id,
                    "route_count": len(items),
                    "current_throughput_bps": round(sum(item["frame_bits"] / max(item["cycle_ms"] / 1000.0, 0.000001) for item in items), 3),
                    "peak_throughput_bps": round(peak_throughput * burst_factor, 3),
                    "maximum_throughput_bps": maximum_throughput,
                    "processing_load_percent": round(processing_load, 4),
                    "queue_load_percent": round(min(100.0, processing_load * burst_factor), 4),
                    "peak_load_percent": round(sum(item["peak_load_percent"] for item in items), 4),
                    "processing_delay_ms": gateway_delay,
                    "queue_delay_ms": gateway_queue_delay,
                    "protocol_conversion_delay_ms": protocol_conversion_delay,
                    "status": classify_load(processing_load * burst_factor, thresholds),
                }
            )

        findings: list[dict[str, Any]] = []
        for step, accepted in (
            ("engineering_model", {"COMPLETE"}),
            ("routing", {"APPROVED"}),
            ("network_editor", {"COMPLETE"}),
            ("parameters", {"APPROVED", "COMPLETE"}),
        ):
            current_status = state["statuses"].get(step)
            if current_status not in accepted:
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "CAPACITY_SOURCE_NOT_READY",
                        "message": f"{WORKFLOW_LABELS[step]} ist nicht vollstaendig ({current_status}).",
                        "step": step,
                        "recommendation": f"Workflow-Schritt {WORKFLOW_LABELS[step]} vervollstaendigen.",
                    }
                )
        if not routes:
            findings.append(
                {
                    "severity": "ERROR",
                    "code": "CAPACITY_NO_ROUTES",
                    "message": "Ohne Routing-Eintraege kann keine belastbare Capacity-Analyse erstellt werden.",
                    "recommendation": "Routing-Tabelle vervollstaendigen und erneut berechnen.",
                }
            )
        for network in network_metrics:
            if network["target_status"] == "EXCEEDED":
                governing_load = max(
                    network["average_load_percent"],
                    network["peak_load_percent"],
                    network["burst_load_percent"],
                )
                findings.append(
                    {
                        "severity": "ERROR" if governing_load >= thresholds["overload"] else "WARNING",
                        "code": "CAPACITY_TARGET_LOAD_EXCEEDED",
                        "object_type": "Network",
                        "object_id": network["network_id"],
                        "message": (
                            f"{network['network_id']} erreicht {governing_load:.2f}% und ueberschreitet "
                            f"die Ziel-Buslast von {target_bus_load:.2f}%."
                        ),
                        "recommendation": "Zyklus, Payload, Bitrate oder Ziel-Buslast pruefen.",
                    }
                )
            if network["status"] in {"WARNING", "CRITICAL", "OVERLOAD"}:
                severity = "ERROR" if network["status"] == "OVERLOAD" else "WARNING"
                findings.append(
                    {
                        "severity": severity,
                        "code": f"CAPACITY_{network['status']}",
                        "object_type": "Network",
                        "object_id": network["network_id"],
                        "message": (
                            f"{network['network_id']} erreicht {network['peak_load_percent']:.2f}% Peak "
                            f"und {network['burst_load_percent']:.2f}% Burst Load."
                        ),
                        "recommendation": "Zyklen, Payload, Bitrate, Segmentierung oder Routingpfad pruefen.",
                    }
                )
        for route in logical_route_metrics:
            max_latency = _number(route.get("max_latency_ms"), 0.0)
            if max_latency > 0 and route["end_to_end_latency_ms"] > max_latency:
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "TIMING_DEADLINE_MISS",
                        "object_type": "RoutingEntry",
                        "object_id": route["route_id"],
                        "message": f"{route['name']} ueberschreitet die maximale Latenz von {max_latency:g} ms.",
                        "recommendation": "Pfad, Queue-Prioritaet, Gateway Delay oder Zykluszeit optimieren.",
                    }
                )
            jitter_limit = _number(route.get("jitter_budget_ms"), 0.0)
            if jitter_limit > 0 and route["estimated_jitter_ms"] > jitter_limit:
                findings.append(
                    {
                        "severity": "WARNING",
                        "code": "TIMING_JITTER_EXCEEDED",
                        "object_type": "RoutingEntry",
                        "object_id": route["route_id"],
                        "message": f"Geschaetzter Jitter fuer {route['name']} liegt ueber dem Budget.",
                        "recommendation": "Scheduling, Synchronisation und Burst-Verhalten pruefen.",
                    }
                )
            timeout = _number(route.get("timeout_ms"), 0.0)
            if timeout > 0 and route["end_to_end_latency_ms"] > timeout:
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "TIMING_TIMEOUT_RISK",
                        "object_type": "RoutingEntry",
                        "object_id": route["route_id"],
                        "message": f"{route['name']} kann das Timeout von {timeout:g} ms verletzen.",
                        "recommendation": "Timeout, Route, Queueing oder Gateway-Verarbeitung pruefen.",
                    }
                )
            freshness = _number(route.get("freshness_ms"), 0.0)
            if freshness > 0 and route["cycle_ms"] + route["end_to_end_latency_ms"] > freshness:
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "TIMING_FRESHNESS_RISK",
                        "object_type": "RoutingEntry",
                        "object_id": route["route_id"],
                        "message": f"{route['name']} kann die Freshness-Anforderung von {freshness:g} ms nicht einhalten.",
                        "recommendation": "Zykluszeit oder Transportpfad reduzieren.",
                    }
                )
        for gateway in gateway_metrics:
            if gateway["status"] in {"CRITICAL", "OVERLOAD"}:
                findings.append(
                    {
                        "severity": "ERROR" if gateway["status"] == "OVERLOAD" else "WARNING",
                        "code": f"GATEWAY_{gateway['status']}",
                        "object_type": "HardwareNode",
                        "object_id": gateway["gateway_id"],
                        "message": f"Gateway {gateway['name']} erreicht {gateway['processing_load_percent']:.2f}% Verarbeitungslast.",
                        "recommendation": "Gateway-Kapazitaet, Queueing und Routenzuordnung pruefen.",
                    }
                )
        required_reliability = min(max(_number(parameters.get("required_reliability"), 0.0), 0.0), 1.0)
        expected_reliability = max(0.0, 1.0 - configured_packet_loss)
        if required_reliability and expected_reliability < required_reliability:
            findings.append(
                {
                    "severity": "ERROR",
                    "code": "RELIABILITY_REQUIREMENT_MISS",
                    "message": "Die konfigurierte Verlustwahrscheinlichkeit verletzt die Reliability-Anforderung.",
                    "recommendation": "Retransmission, Redundanz oder physische Fehlerparameter anpassen.",
                }
            )
        maximum_sync_error = _number(parameters.get("maximum_sync_error_ms"), 0.0)
        total_sync_error = sync_precision_ms + clock_drift_ms(clock_drift_ppm, observation_s)
        if maximum_sync_error and total_sync_error > maximum_sync_error:
            findings.append(
                {
                    "severity": "ERROR",
                    "code": "SYNCHRONIZATION_REQUIREMENT_MISS",
                    "message": f"Erwarteter Synchronisationsfehler {total_sync_error:.3f} ms ueberschreitet {maximum_sync_error:g} ms.",
                    "recommendation": "Sync-Intervall, Clock-Quelle oder Synchronisationsmethode verbessern.",
                }
            )
        if generic_models:
            findings.append(
                {
                    "severity": "INFO",
                    "code": "GENERIC_ESTIMATE",
                    "message": "Fuer " + ", ".join(sorted(generic_models)) + " wurde ein generisches Modell verwendet.",
                    "recommendation": "Technologiespezifische Overhead- und Scheduling-Parameter hinterlegen.",
                }
            )

        message_metrics: list[dict[str, Any]] = []
        for message_id, message in messages.items():
            interface = interfaces.get(str(message.get("interface_id") or ""), {})
            configuration = interface.get("configuration") or {}
            protocol = str(interface.get("interface_type") or default_protocol)
            payload_bytes = max(0, int(_number(message.get("dlc"), default_payload)))
            cycle_ms = _number(message.get("cycle_ms"), default_cycle)
            estimate = estimate_frame(protocol, payload_bytes, parameters_for_protocol(protocol, parameters, configuration))
            load = utilization_percent(estimate.transmission_time_s, cycle_ms) * (1.0 + retry_rate)
            requirements = message.get("configuration") or {}
            message_metrics.append(
                {
                    "message_id": message_id,
                    "name": message.get("name"),
                    "network_id": configuration.get("network_id") or configuration.get("network") or protocol,
                    "protocol": estimate.protocol,
                    "payload_bytes": payload_bytes,
                    "cycle_ms": cycle_ms,
                    "average_load_percent": round(load, 4),
                    "peak_load_percent": round(load * peak_factor, 4),
                    "burst_load_percent": round(load * burst_factor, 4),
                    "maximum_latency_ms": requirements.get("maximum_latency_ms") or requirements.get("deadline_ms"),
                    "maximum_jitter_ms": requirements.get("maximum_jitter_ms"),
                    "timeout_ms": requirements.get("timeout_ms"),
                    "freshness_ms": requirements.get("data_freshness_limit"),
                    "priority": requirements.get("priority") or "NORMAL",
                    "calculation_model": estimate.calculation_model,
                }
            )
        message_metrics.sort(key=lambda item: item["burst_load_percent"], reverse=True)

        signal_metrics: list[dict[str, Any]] = []
        for signal_id, signal in signals.items():
            communication = signal.get("communication") or {}
            message = messages.get(str(signal.get("message_id") or ""), {})
            message_metric = next(
                (item for item in message_metrics if item["message_id"] == str(message.get("id") or "")),
                None,
            )
            signal_metrics.append(
                {
                    "signal_id": signal_id,
                    "name": signal.get("display_name") or signal.get("name"),
                    "message_id": str(signal.get("message_id") or ""),
                    "message_name": message.get("name"),
                    "load_contribution_percent": message_metric.get("average_load_percent", 0.0) if message_metric else 0.0,
                    "cycle_ms": communication.get("cycle_time_ms") or message.get("cycle_ms"),
                    "maximum_latency_ms": communication.get("maximum_latency_ms"),
                    "maximum_jitter_ms": communication.get("maximum_jitter_ms"),
                    "timeout_ms": communication.get("timeout_ms"),
                    "freshness_ms": communication.get("data_freshness_limit"),
                    "priority": communication.get("priority") or "NORMAL",
                    "critical": str(communication.get("priority") or "").upper() in {"CRITICAL", "SAFETY_CRITICAL"},
                }
            )
        signal_metrics.sort(key=lambda item: (not item["critical"], -item["load_contribution_percent"]))

        signal_quality = build_generation_signal_audit(
            hardware=list(hardware.values()),
            interfaces=list(interfaces.values()),
            messages=list(messages.values()),
            signals=list(signals.values()),
            routes=routes,
            topology=state.get("topology") or {},
        )
        for issue in signal_quality["issues"][:50]:
            findings.append(
                {
                    "severity": "ERROR" if issue["status"] == "ERROR" else "WARNING",
                    "code": next((check["code"] for check in issue.get("checks") or [] if check.get("severity") in {"ERROR", "WARNING"}), "SIGNAL_CONFIGURATION_OPEN"),
                    "object_type": "Signal",
                    "object_id": issue["signal_id"],
                    "message": f"{issue['name']}: " + "; ".join(check["text"] for check in issue.get("checks") or []),
                    "recommendation": (
                        "Signalbreite, Wertebereich, Skalierung und Nachrichtenbelegung pruefen. "
                        "KI-Vorschlaege duerfen daraus Optimierungen ableiten, aber nicht automatisch freigeben."
                    ),
                    "evidence": [{
                        "message_id": issue.get("message_id"),
                        "message_name": issue.get("message_name"),
                        "length_bits": issue.get("length_bits"),
                        "required_bits": issue.get("required_bits"),
                    }],
                }
            )
        remaining_signal_issues = len(signal_quality["issues"]) - 50
        if remaining_signal_issues > 0:
            findings.append(
                {
                    "severity": "WARNING",
                    "code": "SIGNAL_CONFIGURATION_ISSUES_TRUNCATED",
                    "message": f"{remaining_signal_issues} weitere Signal-Konfigurationsbefunde sind im Signal-Audit enthalten.",
                    "recommendation": "Signal-Audit im Capacity-Snapshot oeffnen und nach Fehlerstatus sortieren.",
                }
            )

        worst_status = "ERROR" if any(item["severity"] == "ERROR" for item in findings) else (
            "WARNING" if any(item["severity"] == "WARNING" for item in findings) else "COMPLETE"
        )
        load_counts = {
            status: sum(item["status"] == status for item in network_metrics)
            for status in ("NORMAL", "WARNING", "CRITICAL", "OVERLOAD")
        }
        critical_paths = sorted(
            logical_route_metrics,
            key=lambda item: (item["requirement_status"] == "FAIL", item["end_to_end_latency_ms"]),
            reverse=True,
        )[:10]
        bottlenecks: list[dict[str, Any]] = []
        bottlenecks.extend(
            {
                "type": "network_capacity",
                "object_id": item["network_id"],
                "severity": item["status"],
                "value": item["burst_load_percent"],
                "unit": "%",
            }
            for item in network_metrics
            if item["status"] != "NORMAL"
        )
        bottlenecks.extend(
            {
                "type": "route_timing" if item["requirement_status"] == "FAIL" else "route_delay",
                "object_id": item["route_id"],
                "severity": "ERROR" if item["requirement_status"] == "FAIL" else "INFO",
                "value": item["bottleneck"]["delay_ms"],
                "unit": "ms",
                "component": item["bottleneck"]["component"],
            }
            for item in critical_paths
        )
        results = {
            "overview": {
                "network_count": len(network_metrics),
                "route_count": len(logical_route_metrics),
                "route_segment_count": len(route_metrics),
                "gateway_count": len(gateway_metrics),
                "signal_count": len(signal_metrics),
                "load_status_counts": load_counts,
                "max_peak_load_percent": max(
                    (item["peak_load_percent"] for item in network_metrics), default=0.0
                ),
                "max_burst_load_percent": max(
                    (item["burst_load_percent"] for item in network_metrics), default=0.0
                ),
                "target_bus_load_percent": target_bus_load,
                "minimum_capacity_reserve_percent": min(
                    (item["capacity_reserve_percent"] for item in network_metrics), default=100.0
                ),
                "minimum_capacity_margin_percent": min(
                    (item["capacity_margin_percent"] for item in network_metrics), default=100.0
                ),
                "worst_end_to_end_latency_ms": max(
                    (item["end_to_end_latency_ms"] for item in logical_route_metrics), default=0.0
                ),
                "highest_load_network": network_metrics[0]["network_id"] if network_metrics else None,
                "status": worst_status,
            },
            "networks": network_metrics,
            "messages": message_metrics,
            "signals": signal_metrics,
            "signal_quality": signal_quality,
            "routes": route_metrics,
            "gateways": gateway_metrics,
            "critical_paths": critical_paths,
            "bottlenecks": bottlenecks,
            "thresholds": thresholds,
            "timing": {
                "worst_end_to_end_latency_ms": max((item["end_to_end_latency_ms"] for item in logical_route_metrics), default=0.0),
                "worst_queueing_latency_ms": max((item["queueing_latency_ms"] for item in logical_route_metrics), default=0.0),
                "worst_estimated_jitter_ms": max((item["estimated_jitter_ms"] for item in logical_route_metrics), default=0.0),
                "queue_policy": queue_policy,
                "deadline_violations": sum(item["latency_status"] == "FAIL" for item in logical_route_metrics),
                "jitter_violations": sum(item["jitter_status"] == "FAIL" for item in logical_route_metrics),
            },
            "reliability": {
                "configured_retransmission_rate": retry_rate,
                "traffic_multiplier": 1.0 + retry_rate,
                "packet_loss_probability": configured_packet_loss,
                "expected_delivery_probability": expected_reliability,
                "required_reliability": required_reliability or None,
                "status": "FAIL" if required_reliability and expected_reliability < required_reliability else "PASS",
            },
            "synchronization": {
                "clock_drift_ppm": clock_drift_ppm,
                "sync_precision_ms": sync_precision_ms,
                "max_drift_over_observation_ms": round(clock_drift_ms(clock_drift_ppm, observation_s), 6),
                "expected_maximum_error_ms": round(total_sync_error, 6),
                "maximum_allowed_error_ms": maximum_sync_error or None,
                "status": "FAIL" if maximum_sync_error and total_sync_error > maximum_sync_error else "PASS",
                "observation_s": observation_s,
            },
        }
        provenance = {
            "calculation_model": "TECHNOLOGY_AWARE_CAPACITY_TIMING",
            "calculation_version": self.CALCULATION_VERSION,
            "inputs": {
                "routing_entries": len(routes),
                "messages": len(messages),
                "signals": len(signals),
                "parameters_version": state["versions"]["parameters"],
                "network_version": state["versions"]["network_editor"],
            },
            "assumptions": {
                "peak_factor": peak_factor,
                "burst_factor": burst_factor,
                "burst_window_ms": burst_window_ms,
                "retransmission_rate": retry_rate,
                "gateway_delay_ms": gateway_delay,
                "gateway_queue_delay_ms": gateway_queue_delay,
                "protocol_conversion_delay_ms": protocol_conversion_delay,
                "queue_policy": queue_policy,
                "clock_drift_ppm": clock_drift_ppm,
                "sync_precision_ms": sync_precision_ms,
                "thresholds": thresholds,
                "target_bus_load_percent": target_bus_load,
                "generic_models": sorted(generic_models),
            },
            "timestamp": _now(),
        }
        response = {
            "project_id": state["project_id"],
            "source_versions": state["versions"],
            "status": worst_status,
            "results": results,
            "findings": findings,
            "provenance": provenance,
            "scenario": not persist,
        }
        if persist:
            snapshot = self.workflow.create_analysis_snapshot(
                "capacity_timing",
                input_data={"parameters": parameters, "topology": state.get("topology") or {}},
                results=results,
                findings=findings,
                provenance=provenance,
                status=worst_status,
            )
            response["snapshot_id"] = snapshot["id"]
            response["source_versions"] = snapshot["source_versions"]
        else:
            current = self.latest()
            current_results = current.get("results") if current else None
            current_overview = current_results.get("overview") if isinstance(current_results, dict) else None
            if isinstance(current_overview, dict):
                response["impact"] = {
                    "current": current_overview,
                    "scenario": results["overview"],
                    "delta": {
                        "peak_load_percent": round(
                            results["overview"]["max_peak_load_percent"]
                            - _number(current_overview.get("max_peak_load_percent"), 0.0),
                            4,
                        ),
                        "burst_load_percent": round(
                            results["overview"]["max_burst_load_percent"]
                            - _number(current_overview.get("max_burst_load_percent"), 0.0),
                            4,
                        ),
                        "capacity_reserve_percent": round(
                            results["overview"]["minimum_capacity_reserve_percent"]
                            - _number(current_overview.get("minimum_capacity_reserve_percent"), 100.0),
                            4,
                        ),
                        "end_to_end_latency_ms": round(
                            results["overview"]["worst_end_to_end_latency_ms"]
                            - _number(current_overview.get("worst_end_to_end_latency_ms"), 0.0),
                            6,
                        ),
                    },
                    "affected": {
                        "networks": len(network_metrics),
                        "messages": len(message_metrics),
                        "signals": len(signal_metrics),
                        "routes": len(logical_route_metrics),
                        "route_segments": len(route_metrics),
                        "gateways": len(gateway_metrics),
                    },
                }
        return response

    def latest(self) -> dict[str, Any] | None:
        return self.workflow.latest_analysis("capacity_timing", include_outdated=True)


class PreflightService:
    def __init__(self, project_id: str = "default") -> None:
        self.workflow = WorkflowStatusService(project_id)

    def run(self) -> dict[str, Any]:
        state = self.workflow.get()
        capacity = self.workflow.latest_analysis("capacity_timing")
        findings: list[dict[str, Any]] = []
        category_checks: dict[str, list[dict[str, Any]]] = {
            category: []
            for category in (
                "engineering_model",
                "routing",
                "network",
                "parameters",
                "capacity",
                "timing",
                "reliability",
                "synchronization",
            )
        }

        def add(
            category: str,
            severity: str,
            code: str,
            message: str,
            recommendation: str | None = None,
            **extra: Any,
        ) -> None:
            item = {
                "category": category,
                "severity": severity,
                "code": code,
                "message": message,
                **extra,
            }
            if recommendation:
                item["recommendation"] = recommendation
            findings.append(item)
            category_checks[category].append(item)

        required = WORKFLOW_STEPS[:5]
        for step in required:
            status = state["statuses"][step]
            if status in {"EMPTY", "IN_PROGRESS", "ERROR", "OUTDATED"}:
                category = {
                    "network_editor": "network",
                    "capacity_timing": "capacity",
                }.get(step, step)
                add(
                    category,
                    "ERROR",
                    "WORKFLOW_STEP_NOT_READY",
                    f"{WORKFLOW_LABELS[step]} ist nicht simulationsbereit ({status}).",
                    step=step,
                )
            elif status == "WARNING":
                category = {
                    "network_editor": "network",
                    "capacity_timing": "capacity",
                }.get(step, step)
                add(
                    category,
                    "WARNING",
                    "WORKFLOW_STEP_WARNING",
                    f"{WORKFLOW_LABELS[step]} enthaelt Warnungen.",
                    step=step,
                )

        hardware = list_objects("HardwareNode", limit=1000)
        functions = list_objects("Function", limit=1000)
        interfaces = list_objects("Interface", limit=2000)
        messages = list_objects("Message", limit=5000)
        signals = list_objects("Signal", limit=10000)
        if not hardware:
            add("engineering_model", "ERROR", "MODEL_NODES_MISSING", "Das Engineering-Modell enthaelt keine Hardware Nodes.")
        if not interfaces:
            add("engineering_model", "ERROR", "MODEL_INTERFACES_MISSING", "Das Engineering-Modell enthaelt keine Interfaces.")
        if not functions:
            add("engineering_model", "WARNING", "MODEL_FUNCTIONS_MISSING", "Es sind keine Funktionen definiert.")
        if not messages:
            add("engineering_model", "WARNING", "MODEL_MESSAGES_MISSING", "Es sind keine Messages definiert.")
        if not signals:
            add("engineering_model", "WARNING", "MODEL_SIGNALS_MISSING", "Es sind keine Signale definiert.")
        for item in functions:
            if not item.get("hardware_node_id"):
                add("engineering_model", "ERROR", "FUNCTION_PARENT_MISSING", f"Funktion {item.get('name')} besitzt keinen Hardware Node.")
        for item in interfaces:
            if not item.get("function_id"):
                add("engineering_model", "ERROR", "INTERFACE_PARENT_MISSING", f"Interface {item.get('name')} besitzt keine Funktion.")
        for item in messages:
            if not item.get("interface_id"):
                add("engineering_model", "ERROR", "MESSAGE_PARENT_MISSING", f"Message {item.get('name')} besitzt kein Interface.")
        for item in signals:
            if not item.get("message_id"):
                add("engineering_model", "ERROR", "SIGNAL_PARENT_MISSING", f"Signal {item.get('name')} besitzt keine Message.")

        routes = [route for route in list_routes(limit=1000) if route.get("status") not in {"REJECTED", "SUPERSEDED"}]
        if not routes:
            add("routing", "ERROR", "ROUTING_MISSING", "Es existieren keine aktiven Routing-Eintraege.")
        else:
            validation = RoutingValidator().validate_table(routes)
            for route, route_result in zip(routes, validation["results"]):
                for error in route_result["errors"]:
                    add(
                        "routing",
                        "ERROR",
                        error["code"],
                        f"{route.get('route_code')}: {error['message']}",
                        object_type="RoutingEntry",
                        object_id=str(route.get("id")),
                    )
                for warning in route_result["warnings"]:
                    add(
                        "routing",
                        "WARNING",
                        warning["code"],
                        f"{route.get('route_code')}: {warning['message']}",
                        object_type="RoutingEntry",
                        object_id=str(route.get("id")),
                    )

        topology = state.get("topology") or {}
        nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
        edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
        if len(nodes) < 2:
            add("network", "ERROR", "NETWORK_NODES_MISSING", "Die Topologie benoetigt mindestens zwei Nodes.")
        if not edges:
            add("network", "ERROR", "NETWORK_CONNECTIONS_MISSING", "Die Topologie enthaelt keine Verbindung.")
        node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
        connected_ids: set[str] = set()
        for edge in edges:
            if not isinstance(edge, dict):
                add("network", "ERROR", "NETWORK_EDGE_INVALID", "Eine Netzwerkverbindung ist ungueltig.")
                continue
            source_id = str(edge.get("source") or "")
            target_id = str(edge.get("target") or "")
            if source_id not in node_by_id or target_id not in node_by_id:
                add("network", "ERROR", "NETWORK_ENDPOINT_MISSING", "Eine Verbindung referenziert einen unbekannten Node.")
                continue
            connected_ids.update((source_id, target_id))
            for node_id, port_key in ((source_id, "sourcePort"), (target_id, "targetPort")):
                ports = node_by_id[node_id].get("ports") or []
                port_id = str(edge.get(port_key) or "")
                if not any(str(port.get("id")) == port_id for port in ports if isinstance(port, dict)):
                    add("network", "ERROR", "NETWORK_PORT_MISSING", f"Verbindung referenziert den fehlenden Port {port_id}.")
        for node_id, node in node_by_id.items():
            if node_id not in connected_ids:
                add("network", "ERROR", "NETWORK_NODE_DISCONNECTED", f"Node {node.get('name') or node_id} ist nicht verbunden.")

        parameters = {**DEFAULT_PARAMETER_VALUES, **(state.get("parameters") or {})}
        if _number(parameters.get("bitrate"), 0.0) <= 0:
            add("parameters", "ERROR", "PARAMETER_BITRATE_MISSING", "Eine positive Bitrate ist erforderlich.")
        if _number(parameters.get("cycle_ms"), 0.0) <= 0:
            add("parameters", "ERROR", "PARAMETER_CYCLE_INVALID", "Cycle Time muss groesser als null sein.")
        if _number(parameters.get("payload_bytes"), -1.0) < 0:
            add("parameters", "ERROR", "PARAMETER_PAYLOAD_INVALID", "Payload muss groesser oder gleich null sein.")
        warning = _number(parameters.get("warning_threshold"), 60.0)
        critical = _number(parameters.get("critical_threshold"), 75.0)
        overload = _number(parameters.get("overload_threshold"), 90.0)
        if not (0 <= warning < critical < overload):
            add("parameters", "ERROR", "PARAMETER_THRESHOLDS_INVALID", "Load-Grenzwerte muessen aufsteigend sein.")
        target_bus_load = _number(parameters.get("target_bus_load_percent"), 60.0)
        if not 0 <= target_bus_load <= 100:
            add("parameters", "ERROR", "PARAMETER_TARGET_BUS_LOAD_INVALID", "Ziel-Buslast muss zwischen 0 und 100 Prozent liegen.")
        queue_size = _number(parameters.get("queue_size"), 1.0)
        if queue_size <= 0:
            add("parameters", "ERROR", "PARAMETER_QUEUE_INVALID", "Queue Size muss groesser als null sein.")

        if not capacity:
            add(
                "capacity",
                "ERROR",
                "CAPACITY_MISSING_OR_OUTDATED",
                "Capacity & Timing muss mit aktuellen Quelldaten berechnet werden.",
                step="capacity_timing",
            )
        else:
            for item in capacity.get("findings") or []:
                code = str(item.get("code") or "CAPACITY_FINDING")
                category = (
                    "timing" if code.startswith("TIMING_")
                    else "reliability" if code.startswith("RELIABILITY_")
                    else "synchronization" if code.startswith("SYNCHRONIZATION_")
                    else "capacity"
                )
                add(
                    category,
                    str(item.get("severity") or "INFO"),
                    code,
                    str(item.get("message") or code),
                    item.get("recommendation"),
                    object_type=item.get("object_type"),
                    object_id=item.get("object_id"),
                )

        category_statuses: dict[str, str] = {}
        for category, checks in category_checks.items():
            category_statuses[category] = (
                "ERROR" if any(item["severity"] == "ERROR" for item in checks)
                else "WARNING" if any(item["severity"] == "WARNING" for item in checks)
                else "PASS"
            )

        error_count = sum(item["severity"] == "ERROR" for item in findings)
        warning_count = sum(item["severity"] == "WARNING" for item in findings)
        status = "ERROR" if error_count else ("WARNING" if warning_count else "APPROVED")
        results = {
            "ready_for_simulation": error_count == 0,
            "error_count": error_count,
            "warning_count": warning_count,
            "checked_steps": list(required),
            "capacity_snapshot_id": capacity.get("id") if capacity else None,
            "category_statuses": category_statuses,
            "category_checks": category_checks,
        }
        snapshot = self.workflow.create_analysis_snapshot(
            "preflight",
            input_data={"workflow_statuses": state["statuses"]},
            results=results,
            findings=findings,
            provenance={
                "calculation_model": "WORKFLOW_PREFLIGHT",
                "calculation_version": "1.0",
                "inputs": {"source_versions": state["versions"]},
                "assumptions": {"warnings_are_non_blocking": True},
                "timestamp": _now(),
            },
            status=status,
        )
        return {**results, "status": status, "findings": findings, "snapshot_id": snapshot["id"]}
