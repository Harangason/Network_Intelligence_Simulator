from __future__ import annotations

from typing import Any

from .common import clamp


def velocity(signal: Any, _time_s: float, context: Any, _state: Any) -> float:
    speed = max((float(value) for key, value in getattr(context, "signal_values", {}).items() if "speed" in str(key).lower() or "rpm" in str(key).lower()), default=0.0)
    return clamp(speed, signal.minimum, signal.maximum)
