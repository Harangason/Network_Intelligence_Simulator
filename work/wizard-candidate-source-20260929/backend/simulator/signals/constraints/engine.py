from __future__ import annotations

from typing import Any

from ..core.runtime_state import SignalRuntimeState
from ..mathematical import clamp, number


class SignalConstraintEngine:
    """Apply physical bounds and optional rate limits after golden behavior."""

    def apply(self, definition: Any, value: float, time_s: float, state: SignalRuntimeState) -> float:
        limited = clamp(value, definition.minimum, definition.maximum)
        previous = state.previous(definition.id, limited)
        dt = state.dt(definition.id, time_s, definition.cycle_ms / 1000.0)
        rise = definition.parameters.get("max_rise_rate")
        fall = definition.parameters.get("max_fall_rate")
        if rise is None and fall is None:
            return limited
        rise_rate = number(rise, float("inf"))
        fall_rate = number(fall, float("inf"))
        max_up = float("inf") if rise_rate == float("inf") else rise_rate * dt
        max_down = float("inf") if fall_rate == float("inf") else fall_rate * dt
        return previous + clamp(limited - previous, -max_down, max_up)
