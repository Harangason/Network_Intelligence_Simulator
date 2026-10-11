from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationContext:
    current_time: float
    dt: float
    seed: int
    scenario: dict[str, Any] = field(default_factory=dict)
    system_state: dict[str, Any] = field(default_factory=dict)
    function_states: dict[str, Any] = field(default_factory=dict)
    signal_values: dict[str, float] = field(default_factory=dict)
    commands: dict[str, Any] = field(default_factory=dict)
    faults: list[dict[str, Any]] = field(default_factory=list)
    environment: dict[str, float] = field(default_factory=dict)
    routing_context: dict[str, Any] = field(default_factory=dict)
    network_context: dict[str, Any] = field(default_factory=dict)

