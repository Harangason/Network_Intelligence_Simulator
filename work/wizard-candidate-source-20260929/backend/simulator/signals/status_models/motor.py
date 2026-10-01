from __future__ import annotations

from typing import Any

from ..states import StateMachineEngine, motor_profile
from .generic import health, operating, quality, safety, status_dimension


def motor_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    dimension = status_dimension(signal)
    if dimension == "HEALTH":
        return health(signal, time_s, context, state)
    if dimension == "SAFETY":
        return safety(signal, time_s, context, state)
    if dimension == "QUALITY":
        return quality(signal, time_s, context, state)
    return operating(signal, time_s, context, state, StateMachineEngine(motor_profile()))
