from __future__ import annotations


def event_impulse(time_s: float, *, at_s: float, width_s: float = 0.001) -> float:
    return 1.0 if at_s <= time_s < at_s + max(0.000001, width_s) else 0.0
