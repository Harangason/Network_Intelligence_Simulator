from __future__ import annotations

from typing import Any

from .common import bounds, number


def step(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    minimum, maximum, _span, _midpoint = bounds(signal)
    at_s = number(signal.parameters.get("at_s"), max(signal.cycle_ms / 1000.0, 0.1))
    return number(signal.parameters.get("before"), minimum) if time_s < at_s else number(signal.parameters.get("after"), maximum)
