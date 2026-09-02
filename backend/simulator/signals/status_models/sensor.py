from __future__ import annotations

from typing import Any

from ..states.state_machine import StateMachineEngine, profile_from_states
from .generic import health, operating, quality, safety, status_dimension


def sensor_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    dimension = status_dimension(signal)
    if dimension == "HEALTH":
        return health(signal, time_s, context, state)
    if dimension in {"QUALITY", "COMMUNICATION"}:
        return quality(signal, time_s, context, state)
    if dimension == "SAFETY":
        return safety(signal, time_s, context, state)
    profile = profile_from_states("sensor_operating", ("OFF", "INIT", "CALIBRATING", "READY", "MEASURING", "STANDBY"), (0.2, 0.8, 1.5, 2.0, 60.0))
    return operating(signal, time_s, context, state, StateMachineEngine(profile))
