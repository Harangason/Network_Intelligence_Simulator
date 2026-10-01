from __future__ import annotations

from ..states import OPERATING_CODES, StateMachineEngine, motor_profile, operating_state


class SignalStateMachineEngine(StateMachineEngine):
    """Backward-compatible motor operating-state timeline."""

    def __init__(self) -> None:
        super().__init__(motor_profile())
