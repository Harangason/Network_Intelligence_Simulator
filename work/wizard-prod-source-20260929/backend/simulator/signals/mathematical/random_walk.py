from __future__ import annotations

import random
from typing import Any

from ..core.registry_utils import stable_seed
from .common import bounds, number


def random_walk(signal: Any, time_s: float, context: Any, state: Any) -> float:
    minimum, _maximum, span, midpoint = bounds(signal)
    dt = state.dt(signal.id, time_s, signal.cycle_ms / 1000.0)
    index = int(time_s * 1000.0 / max(signal.cycle_ms, 0.001))
    rng = random.Random(stable_seed(context.seed, signal.id, index))
    previous = state.previous(signal.id, number(signal.parameters.get("initial_value"), midpoint))
    step_size = number(signal.parameters.get("step"), span * 0.01)
    return previous + rng.uniform(-step_size, step_size) * max(1.0, dt / max(signal.cycle_ms / 1000.0, 0.001))
