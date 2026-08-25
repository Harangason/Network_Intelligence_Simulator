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


def analyze_runtime_trace(
    result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    trace_path = next(
        (Path(path) for path in result.get("artifacts") or [] if str(path).endswith("universal_trace.jsonl")),
        None,
    )
    if trace_path is None or not trace_path.is_file():
        return {
            "available": False,
            "reason": "Universal trace is not available.",
            "calculation_model": "RUNTIME_TRACE_ANALYSIS_V1",
        }

    events: list[dict[str, Any]] = []
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    if not events:
        return {
            "available": False,
            "reason": "Universal trace contains no events.",
            "calculation_model": "RUNTIME_TRACE_ANALYSIS_V1",
        }

    configured_duration = max(0.001, _number(config.get("duration_s") or config.get("duration"), 1.0))
    observed_duration = max(configured_duration, max(_number(item.get("time_s")) for item in events))
    route_requirements = _route_requirements(config)
    by_network: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_network[str(event.get("network") or "unknown")].append(event)
        by_route[str(event.get("route_id") or "unknown")].append(event)

    network_metrics: list[dict[str, Any]] = []
    for network_id, items in by_network.items():
        transmitted = [item for item in items if item.get("status") != "dropped"]
        busy_s = sum(_number(item.get("transmission_latency_ms")) / 1000.0 for item in transmitted)
        average = busy_s / observed_duration * 100.0
        network_metrics.append(
            {
                "network_id": network_id,
                "technology": str(items[0].get("technology") or "unknown"),
                "event_count": len(items),
                "transmitted_count": sum(item.get("status") == "transmitted" for item in items),
                "dropped_count": sum(item.get("status") == "dropped" for item in items),
                "corrupted_count": sum(item.get("status") == "corrupted" for item in items),
                "average_load_percent": round(average, 6),
                "peak_load_percent": round(_load_in_window(items, 0.01), 6),
                "burst_load_percent": round(_load_in_window(items, 0.1), 6),
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
        expected_cycle_ms = _number(items[0].get("configured_cycle_ms"), 0.0)
        jitters = [abs(interval - expected_cycle_ms) for interval in intervals_ms]
        requirement = route_requirements.get(route_id, {})
        metadata = requirement.get("metadata") if isinstance(requirement.get("metadata"), dict) else {}
        jitter_limit = _number(
            requirement.get("maximum_jitter_ms")
            or requirement.get("jitter_limit_ms")
            or metadata.get("maximum_jitter_ms")
            or config.get("jitter_ms"),
            0.0,
        )
        timeout_ms = _number(requirement.get("timeout_ms") or metadata.get("timeout_ms") or config.get("timeout_ms"), 0.0)
        maximum_latency_ms = _number(
            requirement.get("maximum_latency_ms")
            or requirement.get("deadline_ms")
            or metadata.get("maximum_latency_ms")
            or config.get("maximum_latency_ms")
            or config.get("deadline_ms"),
            0.0,
        )
        freshness_ms = _number(
            requirement.get("freshness_ms")
            or requirement.get("data_freshness_limit")
            or metadata.get("freshness_ms"),
            0.0,
        )
        jitter_violations = sum(jitter_limit > 0 and value > jitter_limit for value in jitters)
        timeout_events = sum(timeout_ms > 0 and interval > timeout_ms for interval in intervals_ms)
        jitter_violation_total += jitter_violations
        timeout_total += timeout_events
        latencies = [_number(item.get("end_to_end_latency_ms")) for item in items]
        queue_delays = [_number(item.get("queue_delay_ms")) for item in items]
        latency_violations = sum(maximum_latency_ms > 0 and value > maximum_latency_ms for value in latencies)
        freshness_violations = sum(
            freshness_ms > 0 and interval + latency > freshness_ms
            for interval, latency in zip(intervals_ms, latencies[1:])
        )
        latency_violation_total += latency_violations
        freshness_violation_total += freshness_violations
        route_metrics.append(
            {
                "route_id": route_id,
                "route_name": str(items[0].get("route_name") or route_id),
                "network_id": str(items[0].get("network") or "unknown"),
                "event_count": len(items),
                "drop_rate": round(sum(item.get("status") == "dropped" for item in items) / len(items), 6),
                "corruption_rate": round(sum(item.get("status") == "corrupted" for item in items) / len(items), 6),
                "configured_cycle_ms": expected_cycle_ms,
                "actual_average_cycle_ms": round(sum(intervals_ms) / len(intervals_ms), 6) if intervals_ms else 0.0,
                "actual_min_cycle_ms": round(min(intervals_ms), 6) if intervals_ms else 0.0,
                "actual_max_cycle_ms": round(max(intervals_ms), 6) if intervals_ms else 0.0,
                "average_jitter_ms": round(sum(jitters) / len(jitters), 6) if jitters else 0.0,
                "p95_jitter_ms": round(_percentile(jitters, 0.95), 6),
                "p99_jitter_ms": round(_percentile(jitters, 0.99), 6),
                "maximum_jitter_ms": round(max(jitters), 6) if jitters else 0.0,
                "jitter_limit_ms": jitter_limit or None,
                "jitter_violations": jitter_violations,
                "maximum_latency_limit_ms": maximum_latency_ms or None,
                "latency_violations": latency_violations,
                "freshness_limit_ms": freshness_ms or None,
                "freshness_violations": freshness_violations,
                "average_end_to_end_latency_ms": round(sum(latencies) / len(latencies), 6),
                "maximum_end_to_end_latency_ms": round(max(latencies), 6),
                "average_queue_delay_ms": round(sum(queue_delays) / len(queue_delays), 6),
                "maximum_queue_delay_ms": round(max(queue_delays), 6),
                "timeouts": timeout_events,
                "status": "FAIL" if jitter_violations or timeout_events or latency_violations or freshness_violations else "PASS",
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
        "jitter_definition": "abs(actual_interval - expected_interval)",
        "peak_window_ms": 10,
        "burst_window_ms": 100,
        "summary": {
            "event_count": total,
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
            "delivery_probability": round((total - dropped - corrupted) / total, 8),
            "packet_loss_rate": round(dropped / total, 8),
            "corruption_rate": round(corrupted / total, 8),
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
