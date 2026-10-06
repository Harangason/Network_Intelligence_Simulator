from __future__ import annotations

from typing import Any

from backend.nis.simulation.signals.states import COMMUNICATION_CODES
from backend.nis.simulation.signals.states import StateMachineEngine
from backend.nis.simulation.signals.states import communication_at
from backend.nis.simulation.signals.states import gateway_profile
from backend.nis.simulation.signals.status_models.generic import health
from backend.nis.simulation.signals.status_models.generic import operating
from backend.nis.simulation.signals.status_models.generic import quality
from backend.nis.simulation.signals.status_models.generic import safety
from backend.nis.simulation.signals.status_models.generic import status_dimension


def gateway_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    dimension = status_dimension(signal)
    if dimension == "COMMUNICATION":
        return float(COMMUNICATION_CODES[communication_at(time_s)])
    if dimension == "HEALTH":
        return health(signal, time_s, context, state)
    if dimension == "SAFETY":
        return safety(signal, time_s, context, state)
    if dimension == "QUALITY":
        return quality(signal, time_s, context, state)
    return operating(signal, time_s, context, state, StateMachineEngine(gateway_profile()))
