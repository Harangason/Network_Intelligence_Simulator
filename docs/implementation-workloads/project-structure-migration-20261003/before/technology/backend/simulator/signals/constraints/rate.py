from __future__ import annotations

from .range import apply_range


def apply_rate_limit(previous: float, target: float, dt: float, rise_rate: float, fall_rate: float) -> float:
    return previous + apply_range(target - previous, -fall_rate * dt, rise_rate * dt)
