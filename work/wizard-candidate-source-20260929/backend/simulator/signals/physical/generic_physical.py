from __future__ import annotations

import math
from typing import Any

from .common import clamp


def generic_physical(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    midpoint = (signal.minimum + signal.maximum) / 2.0
    span = signal.maximum - signal.minimum
    return clamp(midpoint + span * 0.08 * math.sin(time_s / 3.0), signal.minimum, signal.maximum)
