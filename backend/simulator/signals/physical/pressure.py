from __future__ import annotations

import math
from typing import Any

from .common import clamp, number, previous_value, time_delta


def pressure(signal: Any, time_s: float, _context: Any, state: Any) -> float:
    midpoint = (signal.minimum + signal.maximum) / 2.0
    target = midpoint + (signal.maximum - signal.minimum) * 0.25 * math.sin(time_s / 4.0)
    previous = previous_value(signal, state, midpoint)
    dt = time_delta(signal, time_s, state)
    rate = number(signal.parameters.get("max_rise_rate"), (signal.maximum - signal.minimum) * 0.5)
    return clamp(previous + clamp(target - previous, -rate * dt, rate * dt), signal.minimum, signal.maximum)
