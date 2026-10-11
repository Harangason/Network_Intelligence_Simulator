from __future__ import annotations

from typing import Any

from backend.nis.simulation.signals.mathematical.common import bounds
from backend.nis.simulation.signals.mathematical.common import number


def ramp(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    minimum, _maximum, span, _midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    slope = number(signal.parameters.get("slope"), span / period)
    return number(signal.parameters.get("start"), minimum) + slope * time_s
