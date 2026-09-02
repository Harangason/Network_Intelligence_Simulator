from __future__ import annotations

import math
from typing import Any


def number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def previous_value(signal: Any, state: Any, default: float) -> float:
    return float(state.previous(signal.id, number(signal.parameters.get("initial_value"), default)))


def time_delta(signal: Any, time_s: float, state: Any) -> float:
    return float(state.dt(signal.id, time_s, max(signal.cycle_ms / 1000.0, 0.001)))


def operating_state(context: Any) -> str:
    for key, value in getattr(context, "signal_values", {}).items():
        if "operating" in str(key).lower() or "state" in str(key).lower():
            if isinstance(value, str):
                return value
    return str(getattr(context, "system_state", {}).get("operating_state") or "")
