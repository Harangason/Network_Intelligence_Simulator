from __future__ import annotations


def apply_range(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
