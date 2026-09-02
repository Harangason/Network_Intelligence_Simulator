from __future__ import annotations

from typing import Any

from .common import bounds, number


def triangle(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    minimum, _maximum, span, _midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    fraction = ((time_s / period) + number(signal.parameters.get("phase"), 0.0)) % 1.0
    return minimum + span * (1.0 - abs(2.0 * fraction - 1.0))
