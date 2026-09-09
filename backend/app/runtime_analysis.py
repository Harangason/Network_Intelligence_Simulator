"""Deterministic runtime metrics derived from universal simulation traces."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _load_in_window(events: list[dict[str, Any]], window_s: float) -> float:
    if not events:
        return 0.0
    buckets: dict[int, float] = defaultdict(float)
    for event in events:
        if event.get("status") == "dropped":
            continue
        bucket = int(_number(event.get("time_s")) / window_s)
        buckets[bucket] += _number(event.get("transmission_latency_ms")) / 1000.0
    return max((busy / window_s * 100.0 for busy in buckets.values()), default=0.0)


def _route_requirements(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    communications = config.get("communications") or config.get("routes") or []
    return {
        str(item.get("id") or item.get("route_id")): item
        for item in communications
        if isinstance(item, dict)
    }


def _network_definitions(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or item.get("network_id")): item
        for item in config.get("networks") or []
        if isinstance(item, dict) and (item.get("id") or item.get("network_id"))
    }


def _hardware_names(config: dict[str, Any]) -> dict[str, str]:
    hardware = config.get("hardware") if isinstance(config.get("hardware"), dict) else {}
    devices = hardware.get("devices") or hardware.get("nodes") or []
    return {
        str(item.get("id")): str(item.get("name") or item.get("id"))
        for item in devices
        if isinstance(item, dict) and item.get("id")
    }


def _participant_names(values: Any, names: dict[str, str]) -> list[str]:
    items = values if isinstance(values, list) else [values]
    return sorted({names.get(str(item), str(item)) for item in items if item})


def analyze_runtime_trace(
    result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    config = {**(config.get("parameters") or {}), **config}
    trace_path = next(
        (Path(path) for path in result.get("artifacts") or [] if str(path).endswith("universal_trace.jsonl")),
        None,
    )
    events: list[dict[str, Any]] = []
    trace_source = "model_simulation.frames"
    if trace_path is not None and trace_path.is_file():
        trace_source = "universal_trace.jsonl"
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(json.loads(line))
    else:
        model_simulation = result.get("model_simulation") if isinstance(result.get("model_simulation"), dict) else {}
        events = [item for item in model_simulation.get("frames") or [] if isinstance(item, dict)]
    if not events and not _route_requirements(config):
        return {
            "available": False,
            "reason": "Simulation trace contains no frame events.",
            "calculation_model": "RUNTIME_TRACE_ANALYSIS_V1",
        }

    configured_duration = max(0.001, _number(config.get("duration_s") or config.get("duration"), 1.0))
    observed_duration = max(configured_duration, max((_number(item.get("time_s")) for item in events), default=0.0))
    route_requirements = _route_requirements(config)
    network_definitions = _network_definitions(config)
    hardware_names = _hardware_names(config)
    by_network: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_network[str(event.get("network") or "unknown")].append(event)
        if str(event.get("traffic_type") or "DATA").upper() == "DATA" and event.get("final_segment", True):
            by_route[str(event.get("end_to_end_route_id") or event.get("route_id") or "unknown")].append(event)
    for route_id in route_requirements:
        by_route.setdefault(route_id, [])

    network_metrics: list[dict[str, Any]] = []
    for network_id, items in by_network.items():
        network_definition = network_definitions.get(network_id, {})
        senders = _participant_names([item.get("sender_hardware") or item.get("sender") for item in items], hardware_names)
        receivers = _participant_names(
            [receiver for item in items for receiver in (item.get("receiver_hardware") or item.get("receivers") or [])],
            hardware_names,
        )
        transmitted = [item for item in items if item.get("status") != "dropped"]
        busy_s = sum(_number(item.get("transmission_latency_ms")) / 1000.0 for item in transmitted)
        average = busy_s / observed_duration * 100.0
        peak = max(average, _load_in_window(items, 0.01))
        burst = max(average, _load_in_window(items, 0.1))
        ports = []
        if all(item.get('port_model') == 'SWITCHED_FULL_DUPLEX_STORE_FORWARD_V1' for item in items):
            from .port_load import ethernet_port_load
            ports = ethernet_port_load(items, observed_duration)
            average = max((p['average_load_percent'] for p in ports), default=0)
            peak = max((p['peak_load_percent'] for p in ports), default=0)
            burst = max((p['peak_load_percent'] for p in ethernet_port_load(items, observed_duration, .1)), default=0)
        network_metrics.append(
            {
                "network_id": network_id,
                "network_name": str(network_definition.get("name") or network_id),
                "technology": str(items[0].get("technology") or "unknown"),
                "senders": senders,
                "receivers": receivers,
                "event_count": len(items),
                "transmitted_count": sum(item.get("status") == "transmitted" for item in items),
                "dropped_count": sum(item.get("status") == "dropped" for item in items),
                "corrupted_count": sum(item.get("status") == "corrupted" for item in items),
                "average_load_percent": round(average, 6),
                "peak_load_percent": round(peak, 6),
                "burst_load_percent": round(burst, 6),
                "load_basis": "BUSIEST_FULL_DUPLEX_PORT" if ports else "SHARED_BUS",
                "port_metrics": ports,
                "average_queue_depth": round(
                    sum(_number(item.get("queue_depth_estimate")) for item in items) / len(items), 6
                ),
                "maximum_queue_depth": max(int(item.get("queue_depth_estimate") or 0) for item in items),
                "average_queue_delay_ms": round(
                    sum(_number(item.get("queue_delay_ms")) for item in items) / len(items), 6
                ),
                "maximum_queue_delay_ms": round(
                    max(_number(item.get("queue_delay_ms")) for item in items), 6
                ),
            }
        )
    network_metrics.sort(key=lambda item: item["burst_load_percent"], reverse=True)

    route_metrics: list[dict[str, Any]] = []
    timeout_total = 0
    jitter_violation_total = 0
    latency_violation_total = 0
    freshness_violation_total = 0
    for route_id, items in by_route.items():
        items.sort(key=lambda item: _number(item.get("time_s")))
        valid = [item for item in items if item.get("status") == "transmitted"]
        times = [_number(item.get("time_s")) for item in valid]
        intervals_ms = [(right - left) * 1000.0 for left, right in zip(times, times[1:])]
        requirement = route_requirements.get(route_id, {})
        metadata = requirement.get("metadata") if isinstance(requirement.get("metadata"), dict) else {}
        first = items[0] if items else {}
        expected_cycle_ms = _number(first.get("configured_cycle_ms") or requirement.get("cycle_ms"), 0.0)
        jitters = [abs(interval - expected_cycle_ms) for interval in intervals_ms]

        def limit(*names):
            for source in (requirement, requirement.get("timing") or {}, metadata, config):
                value = next((source[name] for name in names if source.get(name) is not None), None)
                if value is not None:
                    number = _number(value, -1)
                    return number if number >= 0 else None
            return None

        jitter_limit = limit("jitter_limit_ms", "maximum_jitter_ms", "jitter_ms")
        timeout_ms = limit("timeout_ms")
        maximum_latency_ms = limit("maximum_latency_ms", "max_latency_ms", "deadline_ms")
        freshness_ms = limit("freshness_ms", "data_freshness_limit")
        release_start = max(0.0, _number(requirement.get("phase_ms"), 0.0) / 1000)
        # Observe silence before the first reception and after the last one as
        # well as gaps between receptions. A totally dead route is not healthy.
        monitored_times = [time for time in times if release_start <= time <= observed_duration]
        gaps_ms = [(right - left) * 1000 for left, right in zip(
            [release_start, *monitored_times], [*monitored_times, observed_duration])]
        timeout_events = sum(gap > timeout_ms + 1e-7 for gap in gaps_ms) if timeout_ms is not None and timeout_ms > 0 else 0
        jitter_violations = sum(value > jitter_limit + 1e-7 for value in jitters) if jitter_limit is not None else 0
        latencies = [_number(item.get("end_to_end_latency_ms")) for item in valid]
        queue_delays = [_number(item.get("queue_delay_ms")) for item in items]
        latency_violations = sum(value > maximum_latency_ms + 1e-7 for value in latencies) if maximum_latency_ms is not None else 0
        freshness_violations = (sum(value > freshness_ms + 1e-7 for value in latencies)
            + sum(gap > freshness_ms + 1e-7 for gap in gaps_ms)) if freshness_ms is not None else 0
        jitter_violation_total += jitter_violations
        timeout_total += timeout_events
        latency_violation_total += latency_violations
        freshness_violation_total += freshness_violations
        requirement_statuses = {
            "jitter": "FAIL" if jitter_violations else "PASS" if jitter_limit is not None and jitters else "NOT_EVALUATED",
            "latency": "FAIL" if latency_violations else "PASS" if maximum_latency_ms is not None and latencies else "NOT_EVALUATED",
            "timeout": "FAIL" if timeout_events else "PASS" if timeout_ms is not None and timeout_ms > 0 and (times or observed_duration-release_start >= timeout_ms/1000) else "NOT_EVALUATED",
            "freshness": "FAIL" if freshness_violations else "PASS" if freshness_ms is not None and latencies else "NOT_EVALUATED",
        }
        dropped_count = sum(item.get("status") == "dropped" for item in items)
        corrupted_count = sum(item.get("status") == "corrupted" for item in items)
        configured_checks = [name for name, value in (("jitter", jitter_limit), ("latency", maximum_latency_ms),
            ("timeout", timeout_ms), ("freshness", freshness_ms)) if value is not None]
        route_status = ("FAIL" if dropped_count or corrupted_count or "FAIL" in requirement_statuses.values()
            else "PASS" if configured_checks and all(requirement_statuses[name] == "PASS" for name in configured_checks)
            else "NOT_EVALUATED")
        sender_id = str(first.get("origin_sender_hardware") or requirement.get("source") or first.get("sender_hardware") or first.get("sender") or "")
        receiver_ids = [str(item) for item in (first.get("receiver_hardware") or first.get("receivers") or [requirement.get("target")]) if item]
        route_metrics.append(
            {
                "route_id": route_id,
                "route_name": str(requirement.get("name") or first.get("route_name") or route_id),
                "canonical_route_id": requirement.get("canonical_route_id") or requirement.get("routing_entry_id") or first.get("route_ref"),
                "route_segment_count": len(requirement.get("segments") or []) or 1,
                "network_id": str(first.get("network") or requirement.get("network_id") or "unknown"),
                "sender_id": sender_id,
                "sender": hardware_names.get(sender_id, sender_id),
                "receiver_ids": receiver_ids,
                "receivers": [hardware_names.get(item, item) for item in receiver_ids],
                "event_count": len(items),
                "drop_rate": round(dropped_count / len(items), 6) if items else None,
                "corruption_rate": round(corrupted_count / len(items), 6) if items else None,
                "configured_cycle_ms": expected_cycle_ms,
                "actual_average_cycle_ms": round(sum(intervals_ms) / len(intervals_ms), 6) if intervals_ms else 0.0,
                "actual_min_cycle_ms": round(min(intervals_ms), 6) if intervals_ms else 0.0,
                "actual_max_cycle_ms": round(max(intervals_ms), 6) if intervals_ms else 0.0,
                "average_jitter_ms": round(sum(jitters) / len(jitters), 6) if jitters else 0.0,
                "p95_jitter_ms": round(_percentile(jitters, 0.95), 6),
                "p99_jitter_ms": round(_percentile(jitters, 0.99), 6),
                "maximum_jitter_ms": round(max(jitters), 6) if jitters else 0.0,
                "jitter_limit_ms": jitter_limit,
                "jitter_violations": jitter_violations,
                "maximum_latency_limit_ms": maximum_latency_ms,
                "latency_violations": latency_violations,
                "freshness_limit_ms": freshness_ms,
                "freshness_violations": freshness_violations,
                "average_end_to_end_latency_ms": round(sum(latencies) / len(latencies), 6) if latencies else 0.0,
                "maximum_end_to_end_latency_ms": round(max(latencies, default=0.0), 6),
                "average_queue_delay_ms": round(sum(queue_delays) / len(queue_delays), 6) if queue_delays else 0.0,
                "maximum_queue_delay_ms": round(max(queue_delays, default=0.0), 6),
                "timeouts": timeout_events,
                "status": route_status,
                "requirement_statuses": requirement_statuses,
                "timeout_limit_ms": timeout_ms,
                "received_event_count": len(valid),
                "observed_silence_max_ms": round(max(gaps_ms, default=0.0), 6),
            }
        )
    route_metrics.sort(
        key=lambda item: (item["status"] == "FAIL", item["maximum_end_to_end_latency_ms"]),
        reverse=True,
    )

    total = len(events)
    dropped = sum(item.get("status") == "dropped" for item in events)
    corrupted = sum(item.get("status") == "corrupted" for item in events)
    clock_drift_ppm = max(0.0, _number(config.get("clock_drift_ppm"), 0.0))
    sync_precision_ms = max(0.0, _number(config.get("sync_precision_ms"), 0.0))
    configured_clock_offset = abs(_number(config.get("clock_offset_ms"), 0.0))
    maximum_clock_offset = configured_clock_offset + clock_drift_ppm * observed_duration / 1000.0 + sync_precision_ms
    gateway_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        for gateway_id in event.get("gateway_ids") or []:
            gateway_events[str(gateway_id)].append(event)
    maximum_gateway_throughput = max(1.0, _number(config.get("gateway_maximum_throughput"), 100_000_000.0))
    gateway_metrics = []
    for gateway_id, items in gateway_events.items():
        transmitted = [item for item in items if item.get("status") != "dropped"]
        throughput = sum(_number(item.get("payload_bytes")) * 8 for item in transmitted) / observed_duration
        gateway_metrics.append(
            {
                "gateway_id": gateway_id,
                "event_count": len(items),
                "current_throughput_bps": round(throughput, 6),
                "maximum_throughput_bps": maximum_gateway_throughput,
                "processing_load_percent": round(throughput / maximum_gateway_throughput * 100.0, 6),
                "average_queue_delay_ms": round(
                    sum(_number(item.get("queue_delay_ms")) for item in items) / len(items), 6
                ),
                "processing_delay_ms": _number(config.get("gateway_delay_ms"), 0.0),
                "protocol_conversion_delay_ms": _number(config.get("protocol_conversion_delay_ms"), 0.0),
            }
        )
    gateway_metrics.sort(key=lambda item: item["processing_load_percent"], reverse=True)
    bottlenecks: list[dict[str, Any]] = []
    if network_metrics:
        busiest = network_metrics[0]
        bottlenecks.append(
            {
                "type": "NETWORK_CAPACITY",
                "object_id": busiest["network_id"],
                "value": busiest["burst_load_percent"],
                "unit": "%",
            }
        )
    if route_metrics:
        slowest = max(route_metrics, key=lambda item: item["maximum_end_to_end_latency_ms"])
        bottlenecks.append(
            {
                "type": "ROUTE_LATENCY",
                "object_id": slowest["route_id"],
                "value": slowest["maximum_end_to_end_latency_ms"],
                "unit": "ms",
            }
        )
    if gateway_metrics:
        busiest_gateway = gateway_metrics[0]
        bottlenecks.append(
            {
                "type": "GATEWAY_LOAD",
                "object_id": busiest_gateway["gateway_id"],
                "value": busiest_gateway["processing_load_percent"],
                "unit": "%",
            }
        )

    return {
        "available": True,
        "calculation_model": "RUNTIME_TRACE_ANALYSIS_V1",
        "calculation_version": "1.0",
        "trace_source": trace_source,
        "jitter_definition": "abs(actual_interval - expected_interval)",
        "peak_window_ms": 10,
        "burst_window_ms": 100,
        "summary": {
            "event_count": total,
            "expected_route_count": len(route_requirements),
            "evaluated_route_count": sum(item["status"] != "NOT_EVALUATED" for item in route_metrics),
            "route_status_counts": {status: sum(item["status"] == status for item in route_metrics) for status in ("PASS", "FAIL", "NOT_EVALUATED")},
            "transmitted_events": total - dropped - corrupted,
            "dropped_frames": dropped,
            "corrupted_frames": corrupted,
            "timeouts": timeout_total,
            "jitter_violations": jitter_violation_total,
            "latency_violations": latency_violation_total,
            "freshness_violations": freshness_violation_total,
            "observed_duration_s": round(observed_duration, 6),
        },
        "networks": network_metrics,
        "routes": route_metrics,
        "queues": {
            "average_depth": round(
                sum(item["average_queue_depth"] for item in network_metrics) / len(network_metrics), 6
            ) if network_metrics else 0.0,
            "maximum_depth": max((item["maximum_queue_depth"] for item in network_metrics), default=0),
            "queue_drops": sum(item.get("drop_reason") == "queue_overflow" for item in events),
        },
        "reliability": {
            "delivery_probability": round((total - dropped - corrupted) / total, 8) if total else None,
            "packet_loss_rate": round(dropped / total, 8) if total else None,
            "corruption_rate": round(corrupted / total, 8) if total else None,
            "retransmissions": sum(int(item.get("retransmission_count") or 0) for item in events),
            "duplicates": sum(bool(item.get("duplicate_injected")) for item in events),
            "reordered_events": sum(bool(item.get("reordered")) for item in events),
        },
        "synchronization": {
            "configured_clock_offset_ms": configured_clock_offset,
            "clock_drift_ppm": clock_drift_ppm,
            "sync_precision_ms": sync_precision_ms,
            "maximum_clock_offset_ms": round(maximum_clock_offset, 6),
        },
        "gateways": gateway_metrics,
        "bottlenecks": bottlenecks,
    }


class RuntimeBusLoadMonitor:
    """Calculate simulated load exclusively from emitted frame timing and wire size."""

    def analyze(self, result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return analyze_runtime_trace(result, config)
