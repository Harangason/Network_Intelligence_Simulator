from __future__ import annotations

from typing import Any

from backend.nis.simulation.signals.states.state_machine import StateMachineEngine
from backend.nis.simulation.signals.states.state_machine import profile_from_states
from backend.nis.simulation.signals.status_models.generic import health
from backend.nis.simulation.signals.status_models.generic import operating
from backend.nis.simulation.signals.status_models.generic import quality
from backend.nis.simulation.signals.status_models.generic import safety
from backend.nis.simulation.signals.status_models.generic import status_dimension


def camera_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    dimension = status_dimension(signal)
    if dimension == "HEALTH":
        return health(signal, time_s, context, state)
    if dimension == "QUALITY":
        return quality(signal, time_s, context, state)
    if dimension == "SAFETY":
        return safety(signal, time_s, context, state)
    profile = profile_from_states("camera_operating", ("OFF", "INIT", "CALIBRATING", "READY", "ACTIVE", "STANDBY"), (0.2, 0.8, 1.5, 2.0, 60.0))
    return operating(signal, time_s, context, state, StateMachineEngine(profile))
