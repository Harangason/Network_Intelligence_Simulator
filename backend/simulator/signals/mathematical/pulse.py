from __future__ import annotations

from typing import Any

from .common import bounds, clamp, number


def pulse(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    minimum, maximum, _span, _midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    duty = clamp(number(signal.parameters.get("duty_cycle"), 0.5), 0.0, 1.0)
    return maximum if ((time_s / period) + number(signal.parameters.get("phase"), 0.0)) % 1.0 < duty else minimum
