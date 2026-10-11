from __future__ import annotations

from typing import Any

from ..states import COMMUNICATION_CODES, StateMachineEngine, communication_at, gateway_profile
from .generic import health, operating, quality, safety, status_dimension


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
