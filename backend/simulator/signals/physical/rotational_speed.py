from __future__ import annotations

import math
from typing import Any

from .common import clamp, number, previous_value, time_delta


def rotational_speed(signal: Any, time_s: float, context: Any, state: Any) -> float:
    operating = str(getattr(context, "system_state", {}).get("operating_state") or "")
    if not operating:
        if time_s < 3.0:
            operating = "READY"
        elif time_s < 5.0:
            operating = "STARTING"
        elif time_s < 55.0:
            operating = "RUNNING"
        else:
            operating = "STOPPING"
    if operating in {"OFF", "INIT", "READY", "STANDBY"}:
        target = 0.0
    elif operating == "STARTING":
        target = min(signal.maximum, number(signal.parameters.get("start_target"), 900.0))
    elif operating == "LIMITED":
        target = min(signal.maximum, number(signal.parameters.get("limited_target"), 1200.0))
    elif operating == "STOPPING":
        target = 0.0
    else:
        command = max((float(value) for key, value in getattr(context, "signal_values", {}).items() if "throttle" in str(key).lower()), default=0.5)
        target = clamp(number(signal.parameters.get("idle_rpm"), 850.0) + command * number(signal.parameters.get("rpm_span"), 2200.0) + 120.0 * math.sin(time_s / 7.0), signal.minimum, signal.maximum)
    previous = previous_value(signal, state, 0.0)
    dt = time_delta(signal, time_s, state)
    up = number(signal.parameters.get("max_rise_rate"), 1000.0) * dt
    down = number(signal.parameters.get("max_fall_rate"), 1500.0) * dt
    return clamp(previous + clamp(target - previous, -down, up), signal.minimum, signal.maximum)
