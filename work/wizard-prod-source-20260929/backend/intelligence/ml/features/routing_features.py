"""Feature extraction for ranking already validated routes."""

from __future__ import annotations

from typing import Any


def routing_features(route: dict[str, Any]) -> dict[str, Any]:
    destinations = route.get("destinations") if isinstance(route.get("destinations"), list) else []
    path = route.get("path") if isinstance(route.get("path"), list) else []
    timing = route.get("timing") if isinstance(route.get("timing"), dict) else {}
    return {
        "hop_count": len(path) or _number(route.get("hop_count"), 1),
        "gateway_count": sum("gateway" in str(item).lower() for item in path),
        "network_load": _number(route.get("network_load") or timing.get("network_load"), 0),
        "latency": _number(timing.get("latency_ms") or route.get("latency_ms"), 0),
        "jitter": _number(timing.get("jitter_ms") or route.get("jitter_ms"), 0),
        "redundancy": _number(route.get("redundancy"), 0),
        "priority": str(route.get("priority") or timing.get("priority") or "NORMAL").upper(),
        "receiver_count": len(destinations) or _number(route.get("receiver_count"), 1),
    }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
