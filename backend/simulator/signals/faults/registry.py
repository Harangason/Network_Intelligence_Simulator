from __future__ import annotations

import random
from typing import Any

from ..core.registry_utils import stable_seed
from .delayed import delayed
from .drift import drift
from .dropout import dropout
from .invalid_state import invalid_state
from .offset import offset
from .stuck import stuck


class SignalFaultOverlayRegistry:
    def apply(self, fault_type: str, *, value: float | None, baseline: float, signal: Any, fault: dict[str, Any], time_s: float, behavior: Any, seed: int, cache: dict[str, float]) -> float | None:
        current = baseline if value is None else value
        magnitude = float(fault.get("magnitude") or (signal.maximum - signal.minimum) * 0.1)
        if fault_type in {"SIGNAL_STUCK", "SIGNAL_FROZEN", "STUCK_STATE", "STUCK_TRUE", "STUCK_FALSE"}:
            if fault_type == "STUCK_TRUE":
                return 1.0
            if fault_type == "STUCK_FALSE":
                return 0.0
            return stuck(cache, signal.id, baseline)
        if fault_type == "SIGNAL_OFFSET":
            return offset(current, magnitude)
        if fault_type == "SIGNAL_DRIFT":
            return drift(current, magnitude, time_s - float(fault.get("start_s") or 0.0))
        if fault_type == "SIGNAL_SPIKE":
            return offset(current, magnitude)
        if fault_type == "SIGNAL_DROPOUT":
            return dropout()
        if fault_type == "SIGNAL_NOISE":
            rng = random.Random(stable_seed(seed, signal.id, fault_type, time_s))
            return current + rng.gauss(0.0, abs(magnitude))
        if fault_type == "SIGNAL_OUT_OF_RANGE":
            return signal.maximum + abs(magnitude)
        if fault_type == "SIGNAL_DELAYED":
            return delayed(behavior, signal.id, time_s, float(fault.get("delay_s") or 0.1), baseline)
        if fault_type == "SIGNAL_WRONG_SCALE":
            return current * float(fault.get("scale") or 2.0)
        if fault_type in {"SIGNAL_INVALID_VALUE", "INVALID_STATE", "WRONG_TRANSITION"}:
            return invalid_state()
        if fault_type == "TOGGLE":
            return 0.0 if current else 1.0
        return value
