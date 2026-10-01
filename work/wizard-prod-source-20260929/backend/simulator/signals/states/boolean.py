from __future__ import annotations


def boolean_value(time_s: float, *, active_after_s: float = 1.5, active_until_s: float | None = None) -> float:
    if time_s < active_after_s:
        return 0.0
    if active_until_s is not None and time_s > active_until_s:
        return 0.0
    return 1.0
