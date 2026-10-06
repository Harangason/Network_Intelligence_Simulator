from __future__ import annotations

from typing import Any

from backend.nis.simulation.signals.mathematical.common import bounds
from backend.nis.simulation.signals.mathematical.common import clamp
from backend.nis.simulation.signals.mathematical.common import number


def constant(signal: Any, _time_s: float, _context: Any, _state: Any) -> float:
    minimum, maximum, _span, midpoint = bounds(signal)
    return clamp(number(signal.parameters.get("value"), midpoint), minimum, maximum)
