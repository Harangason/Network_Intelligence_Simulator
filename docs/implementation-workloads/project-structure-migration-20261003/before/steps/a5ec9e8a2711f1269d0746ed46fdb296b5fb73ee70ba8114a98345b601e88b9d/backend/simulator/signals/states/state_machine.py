from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


Guard = Callable[[dict[str, object]], bool]


@dataclass(frozen=True)
class StateTransition:
    source: str
    target: str
    at_s: float
    delay_s: float = 0.0
    guard: str | None = None


@dataclass
class StateMachineProfile:
    name: str
    initial_state: str
    allowed_states: tuple[str, ...]
    allowed_transitions: dict[str, tuple[str, ...]]
    timeline: tuple[StateTransition, ...]
    transition_delays: dict[tuple[str, str], float] = field(default_factory=dict)
    fault_transitions: dict[str, str] = field(default_factory=dict)
    reset_behavior: str = "initial"


class StateMachineEngine:
    def __init__(self, profile: StateMachineProfile, guards: dict[str, Guard] | None = None) -> None:
        self.profile = profile
        self.guards = guards or {}
        self.current_state = profile.initial_state

    @property
    def allowed_states(self) -> tuple[str, ...]:
        return self.profile.allowed_states

    @property
    def allowed_transitions(self) -> dict[str, tuple[str, ...]]:
        return self.profile.allowed_transitions

    def can_transition(self, source: str, target: str, context: dict[str, object] | None = None) -> bool:
        if target not in self.profile.allowed_states:
            return False
        if target not in self.profile.allowed_transitions.get(source, ()):
            return False
        guard_name = next(
            (item.guard for item in self.profile.timeline if item.source == source and item.target == target),
            None,
        )
        if guard_name and guard_name in self.guards:
            return bool(self.guards[guard_name](context or {}))
        return True

    def transition(self, target: str, context: dict[str, object] | None = None) -> str:
        if not self.can_transition(self.current_state, target, context):
            raise ValueError(f"Invalid transition {self.current_state} -> {target}")
        self.current_state = target
        return self.current_state

    def state_at(self, time_s: float, context: dict[str, object] | None = None, faults: set[str] | None = None) -> str:
        state = self.profile.initial_state
        active_faults = faults or set()
        for fault, target in self.profile.fault_transitions.items():
            if fault in active_faults:
                return target
        for item in sorted(self.profile.timeline, key=lambda transition: transition.at_s + transition.delay_s):
            effective_time = item.at_s + self.profile.transition_delays.get((item.source, item.target), item.delay_s)
            if time_s < effective_time:
                continue
            if state == item.source and self.can_transition(item.source, item.target, context):
                state = item.target
        return state

    def code_at(self, time_s: float, context: dict[str, object] | None = None, faults: set[str] | None = None) -> int:
        state = self.state_at(time_s, context, faults)
        return self.profile.allowed_states.index(state)

    def reset(self) -> None:
        self.current_state = self.profile.initial_state


def profile_from_states(name: str, states: tuple[str, ...], switch_times: tuple[float, ...]) -> StateMachineProfile:
    transitions = tuple(
        StateTransition(source=states[index], target=states[index + 1], at_s=switch_times[index])
        for index in range(min(len(states) - 1, len(switch_times)))
    )
    allowed = {state: ((states[index + 1],) if index + 1 < len(states) else tuple()) for index, state in enumerate(states)}
    return StateMachineProfile(name=name, initial_state=states[0], allowed_states=states, allowed_transitions=allowed, timeline=transitions)
