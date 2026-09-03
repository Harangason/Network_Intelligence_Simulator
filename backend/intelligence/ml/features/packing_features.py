"""Feature extraction for message packing quality proposals."""

from __future__ import annotations

from typing import Any


def packing_features(message: dict[str, Any]) -> dict[str, Any]:
    used = _number(message.get("payload_used_bits"), _number(message.get("used_bits"), 0))
    capacity = max(1.0, _number(message.get("payload_capacity_bits"), _number(message.get("dlc"), 8) * 8))
    return {
        "payload_utilization": used / capacity,
        "payload_free_bits": max(0.0, capacity - used),
        "cycle_time": _number(message.get("cycle_ms") or message.get("cycle_time_ms"), 0),
        "receiver_count": len(message.get("receiver_set") or message.get("receivers") or []),
        "busload": _number(message.get("busload") or message.get("load_contribution_percent"), 0),
    }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
