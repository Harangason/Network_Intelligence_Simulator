from __future__ import annotations


SAFETY_CODES = {"NORMAL": 0, "SAFE_STATE": 1, "EMERGENCY_STOP": 2}


def safety_from_health(health: str) -> str:
    if health == "CRITICAL":
        return "SAFE_STATE"
    if health == "ERROR":
        return "EMERGENCY_STOP"
    return "NORMAL"
