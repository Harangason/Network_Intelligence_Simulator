from __future__ import annotations


COMMUNICATION_CODES = {"OFFLINE": 0, "INITIALIZING": 1, "CONNECTED": 2, "PARTIAL": 3, "BUS_OFF": 4, "LINK_LOSS": 5, "ERROR": 6}


def communication_at(time_s: float, fault_state: set[str] | None = None) -> str:
    faults = fault_state or set()
    if "BUS_OFF" in faults:
        return "BUS_OFF"
    if "LINK_LOSS" in faults:
        return "LINK_LOSS"
    if time_s < 0.2:
        return "OFFLINE"
    if time_s < 1.0:
        return "INITIALIZING"
    return "CONNECTED"
