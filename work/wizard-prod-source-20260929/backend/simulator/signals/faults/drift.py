from __future__ import annotations


def drift(value: float, magnitude: float, elapsed_s: float) -> float:
    return value + magnitude * max(0.0, elapsed_s)
