from __future__ import annotations

from typing import Any

from .common import clamp, number, previous_value, time_delta


def position(signal: Any, _time_s: float, context: Any, state: Any) -> float:
    target = number(getattr(context, "commands", {}).get(signal.id), number(signal.parameters.get("target_position"), (signal.minimum + signal.maximum) / 2.0))
    previous = previous_value(signal, state, signal.minimum)
    dt = time_delta(signal, getattr(context, "current_time", 0.0), state)
    velocity = number(signal.parameters.get("max_velocity"), (signal.maximum - signal.minimum) * 0.2)
    return clamp(previous + clamp(target - previous, -velocity * dt, velocity * dt), signal.minimum, signal.maximum)
