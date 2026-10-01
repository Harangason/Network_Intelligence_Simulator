from __future__ import annotations


QUALITY_CODES = {"VALID": 0, "DEGRADED": 1, "STALE": 2, "NOT_AVAILABLE": 3, "SUBSTITUTED": 4, "ESTIMATED": 5, "INVALID": 6}


def quality_at(time_s: float, fault_state: set[str] | None = None) -> str:
    faults = fault_state or set()
    if "SIGNAL_INVALID_VALUE" in faults:
        return "INVALID"
    if "SIGNAL_DROPOUT" in faults:
        return "NOT_AVAILABLE"
    if "SIGNAL_DELAYED" in faults or "SIGNAL_STUCK" in faults or "SIGNAL_FROZEN" in faults:
        return "STALE"
    if time_s > 120.0:
        return "STALE"
    return "VALID"
