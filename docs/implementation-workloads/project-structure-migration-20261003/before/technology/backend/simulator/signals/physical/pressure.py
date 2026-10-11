from __future__ import annotations

import math
from typing import Any

from .common import clamp, number, previous_value, time_delta


def pressure(signal: Any, time_s: float, _context: Any, state: Any) -> float:
    midpoint = (signal.minimum + signal.maximum) / 2.0
    vehicle = getattr(_context, "system_state", {})
    name = str(signal.name).lower()
    span = signal.maximum - signal.minimum
    if "brake" in name or "brems" in name:
        target = signal.minimum + span * number(vehicle.get("brake_factor"), 0.0) * 0.85
    elif "boost" in name or "lade" in name:
        target = signal.minimum + span * (0.18 + number(vehicle.get("load_factor"), 0.0) * 0.55)
    else:
        target = midpoint + span * 0.16 * math.sin(time_s * 1.7)
    previous = previous_value(signal, state, midpoint)
    dt = time_delta(signal, time_s, state)
    rate = number(signal.parameters.get("max_rise_rate"), (signal.maximum - signal.minimum) * 0.5)
    return clamp(previous + clamp(target - previous, -rate * dt, rate * dt), signal.minimum, signal.maximum)
