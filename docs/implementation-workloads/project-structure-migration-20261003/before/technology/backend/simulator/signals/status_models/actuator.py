from __future__ import annotations

from typing import Any

from ..states.state_machine import StateMachineEngine, profile_from_states
from .generic import health, operating, quality, safety, status_dimension


def actuator_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    dimension = status_dimension(signal)
    if dimension == "HEALTH":
        return health(signal, time_s, context, state)
    if dimension == "SAFETY":
        return safety(signal, time_s, context, state)
    if dimension == "QUALITY":
        return quality(signal, time_s, context, state)
    profile = profile_from_states("actuator_operating", ("OFF", "INIT", "READY", "ENABLED", "ACTIVE", "HOLDING", "STOPPING", "LIMITED", "ERROR"), (0.2, 0.8, 1.3, 1.8, 10.0, 55.0, 58.0, 120.0))
    return operating(signal, time_s, context, state, StateMachineEngine(profile))
