from __future__ import annotations


def counter_value(time_s: float, cycle_ms: float, *, modulus: int, increment: int = 1) -> float:
    index = int(time_s * 1000.0 / max(cycle_ms, 0.001))
    return float((index * increment) % max(1, modulus))
