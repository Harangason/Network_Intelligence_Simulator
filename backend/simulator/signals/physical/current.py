from __future__ import annotations

from typing import Any

from .common import clamp, number


def current(signal: Any, _time_s: float, context: Any, _state: Any) -> float:
    rpm = max((float(value) for key, value in getattr(context, "signal_values", {}).items() if "rpm" in str(key).lower()), default=0.0)
    torque = max((float(value) for key, value in getattr(context, "signal_values", {}).items() if "torque" in str(key).lower()), default=0.0)
    value = number(signal.parameters.get("idle_current"), 2.0 if rpm > 1.0 else 0.0) + rpm * 0.004 + torque * 0.12
    return clamp(value, signal.minimum, signal.maximum)
