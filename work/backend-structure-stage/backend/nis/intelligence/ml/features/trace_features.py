"""Trace feature extraction for controlled fault classification."""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


def trace_features(trace: dict[str, Any]) -> dict[str, Any]:
    values = [_number(item.get("value"), 0.0) for item in trace.get("signals", []) if isinstance(item, dict)]
    bus = [_number(item.get("load_percent"), 0.0) for item in trace.get("bus_load", []) if isinstance(item, dict)]
    faults = trace.get("faults") if isinstance(trace.get("faults"), list) else []
    return {
        "mean": mean(values) if values else 0.0,
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "variance": (pstdev(values) ** 2) if len(values) > 1 else 0.0,
        "dropout_count": sum("drop" in str(item).lower() or "loss" in str(item).lower() for item in faults),
        "timeout_count": sum("timeout" in str(item).lower() for item in faults),
        "jitter_max": max((_number(item.get("jitter_ms"), 0.0) for item in trace.get("events", []) if isinstance(item, dict)), default=0.0),
        "busload_mean": mean(bus) if bus else 0.0,
        "busload_peak": max(bus) if bus else 0.0,
        "state_transition_count": sum(1 for item in trace.get("events", []) if isinstance(item, dict) and item.get("state")),
    }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
