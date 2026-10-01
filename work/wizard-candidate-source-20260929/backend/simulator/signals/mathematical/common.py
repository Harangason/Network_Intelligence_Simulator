from __future__ import annotations

import math
from typing import Any


def number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def bounds(signal: Any) -> tuple[float, float, float, float]:
    minimum = float(signal.minimum)
    maximum = float(signal.maximum)
    span = max(1e-9, maximum - minimum)
    return minimum, maximum, span, (minimum + maximum) / 2.0
