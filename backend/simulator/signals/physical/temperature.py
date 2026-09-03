from __future__ import annotations

from typing import Any

from .common import clamp, number, previous_value, time_delta


def temperature(signal: Any, time_s: float, context: Any, state: Any) -> float:
    ambient = number(getattr(context, "environment", {}).get("ambient_temperature"), 22.0)
    previous = previous_value(signal, state, ambient)
    signal_values = getattr(context, "signal_values", {})
    current = max((abs(float(value)) for key, value in signal_values.items() if "current" in str(key).lower()), default=0.0)
    rpm = max((abs(float(value)) for key, value in signal_values.items() if "rpm" in str(key).lower() or "speed" in str(key).lower()), default=0.0)
    heat_input = number(signal.parameters.get("heat_input"), 0.02 * current + 0.0006 * rpm)
    thermal_mass = max(0.001, number(signal.parameters.get("thermal_mass"), 8.0))
    cooling = number(signal.parameters.get("cooling"), 0.06) * max(0.0, previous - ambient)
    target_delta = (heat_input - cooling) / thermal_mass
    if not signal_values or (current <= 0.0 and rpm <= 0.0):
        target_delta = max(target_delta, number(signal.parameters.get("warmup_rate"), 1.4))
    dt = time_delta(signal, time_s, state)
    rise = number(signal.parameters.get("max_rise_rate"), 2.0)
    fall = number(signal.parameters.get("max_fall_rate"), 1.0)
    delta = clamp(target_delta * dt, -fall * dt, rise * dt)
    return clamp(previous + delta, signal.minimum, signal.maximum)
