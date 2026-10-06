from __future__ import annotations

from backend.nis.simulation.signals.states import OPERATING_CODES
from backend.nis.simulation.signals.states import StateMachineEngine
from backend.nis.simulation.signals.states import motor_profile
from backend.nis.simulation.signals.states import operating_state as operating_state


class SignalStateMachineEngine(StateMachineEngine):
    """Backward-compatible motor operating-state timeline."""

    def __init__(self) -> None:
        super().__init__(motor_profile())
