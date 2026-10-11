from __future__ import annotations

import random
from typing import Any

from .registry import stable_seed


class SimulationRandomService:
    """Central deterministic random streams for signal emulation."""

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)

    def stream(self, *parts: Any) -> random.Random:
        return random.Random(stable_seed(self.seed, *parts))

    def uniform(self, minimum: float, maximum: float, *parts: Any) -> float:
        return self.stream(*parts).uniform(minimum, maximum)

    def gaussian(self, mean: float, sigma: float, *parts: Any) -> float:
        return self.stream(*parts).gauss(mean, sigma)
