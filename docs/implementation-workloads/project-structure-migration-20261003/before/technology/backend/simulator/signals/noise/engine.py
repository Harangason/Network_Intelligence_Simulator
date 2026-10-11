from __future__ import annotations

from typing import Any

from ..core.context import SimulationContext
from ..core.random_service import SimulationRandomService
from ..mathematical import number


class SignalNoiseEngine:
    """Add bounded, semantic-aware and reproducible sensor noise."""

    def __init__(self, random_service: SimulationRandomService) -> None:
        self.random = random_service

    def apply(self, definition: Any, value: float, time_s: float, context: SimulationContext) -> float:
        mode = str(definition.parameters.get("noise") or definition.parameters.get("noise_model") or "NONE").upper()
        if mode in {"", "NONE"}:
            return value
        span = max(1e-9, definition.maximum - definition.minimum)
        sigma = number(definition.parameters.get("noise_sigma"), span * (0.002 if mode == "LOW" else 0.006))
        index = round(time_s / max(definition.cycle_ms / 1000.0, 0.001))
        return value + self.random.gaussian(0.0, sigma, definition.id, "noise", index)
