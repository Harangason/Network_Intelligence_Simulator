from __future__ import annotations


def bounded_value(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
