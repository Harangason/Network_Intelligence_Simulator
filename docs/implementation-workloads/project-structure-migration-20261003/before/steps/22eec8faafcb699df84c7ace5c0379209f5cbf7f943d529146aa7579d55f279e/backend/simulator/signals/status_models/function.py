from __future__ import annotations

from typing import Any

from backend.simulator.signals.states import StateMachineEngine, function_profile
from backend.simulator.signals.status_models.generic import operating


def function_status(signal: Any, time_s: float, context: Any, state: Any) -> float:
    return operating(signal, time_s, context, state, StateMachineEngine(function_profile()))
