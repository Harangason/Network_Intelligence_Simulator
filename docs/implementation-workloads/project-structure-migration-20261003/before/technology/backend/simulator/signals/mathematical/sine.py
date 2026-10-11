from __future__ import annotations

import math
from typing import Any

from .common import bounds, number


def sine(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    _minimum, _maximum, span, midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    phase = number(signal.parameters.get("phase"), 0.0)
    amplitude = number(signal.parameters.get("amplitude"), span * 0.4)
    return midpoint + amplitude * math.sin(2 * math.pi * time_s / period + phase)
