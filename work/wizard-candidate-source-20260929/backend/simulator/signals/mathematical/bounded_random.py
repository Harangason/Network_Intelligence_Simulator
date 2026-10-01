from __future__ import annotations

from typing import Any

from .random_walk import random_walk


def bounded_random(signal: Any, time_s: float, context: Any, state: Any) -> float:
    return random_walk(signal, time_s, context, state)
