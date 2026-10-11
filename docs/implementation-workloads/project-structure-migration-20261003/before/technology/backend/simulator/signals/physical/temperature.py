from __future__ import annotations

from typing import Any

import math

from .common import clamp, number, previous_value, time_delta


def temperature(signal: Any, time_s: float, context: Any, state: Any) -> float:
    ambient = number(getattr(context, "environment", {}).get("ambient_temperature"), 22.0)
    previous = previous_value(signal, state, ambient)
    if time_s <= 0:
        return clamp(previous, signal.minimum, signal.maximum)
    signal_values = getattr(context, "signal_values", {})
    vehicle = getattr(context, "system_state", {})
    name = str(signal.name).lower()
    current = max((abs(float(value)) for key, value in signal_values.items() if "current" in str(key).lower()), default=0.0)
    rpm = max((abs(float(value)) for key, value in signal_values.items() if "rpm" in str(key).lower() or "speed" in str(key).lower()), default=0.0)
    rpm = max(rpm, number(vehicle.get("engine_rpm"), 0.0))
    load = number(vehicle.get("load_factor"), 0.0)
    speed = number(vehicle.get("vehicle_speed_kph"), 0.0)
    if any(token in name for token in ("ambient", "outside", "aussen")):
        target = ambient + 0.35 * math.sin(time_s / 11.0)
        time_constant, default_rise, default_fall, ripple = 18.0, 0.25, 0.25, 0.08
    elif any(token in name for token in ("exhaust", "abgas", "catalyst", "katalys")):
        target = ambient + 95.0 + load * 430.0 + rpm * 0.025
        time_constant, default_rise, default_fall, ripple = 1.8, 180.0, 55.0, 4.0 + 5.0 * load
    elif "battery" in name or "batterie" in name:
        target = ambient + 4.0 + current * 0.09 + load * 7.0
        time_constant, default_rise, default_fall, ripple = 22.0, 1.2, 0.45, 0.12
    elif any(token in name for token in ("motor", "engine", "oil", "oel", "transmission", "getriebe")):
        target = ambient + 38.0 + load * 62.0 + speed * 0.12
        time_constant, default_rise, default_fall, ripple = 7.0, 12.0, 3.0, 0.45
    else:
        target = ambient + 8.0 + load * 24.0 + current * 0.025
        time_constant, default_rise, default_fall, ripple = 10.0, 5.0, 1.4, 0.25
    target = number(signal.parameters.get("target_temperature"), target)
    thermal_mass = max(0.05, number(signal.parameters.get("thermal_mass"), time_constant))
    target_delta = (target - previous) / thermal_mass
    dt = time_delta(signal, time_s, state)
    rise = number(signal.parameters.get("max_rise_rate"), default_rise)
    fall = number(signal.parameters.get("max_fall_rate"), default_fall)
    delta = clamp(target_delta * dt, -fall * dt, rise * dt)
    fluctuation = ripple * math.sin(time_s * (2.4 + min(5.0, rpm / 900.0)))
    return clamp(previous + delta + fluctuation * min(dt, 0.1), signal.minimum, signal.maximum)
