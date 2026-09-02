from __future__ import annotations

from typing import Any


class SignalQualityEngine:
    """Classify actual signal samples for downstream trace consumers."""

    def evaluate(self, definition: Any, value: float | None, fault_state: list[str] | None = None) -> str:
        faults = set(fault_state or [])
        if value is None:
            return "NOT_AVAILABLE"
        if "SIGNAL_DELAYED" in faults or "SIGNAL_FROZEN" in faults or "SIGNAL_STUCK" in faults:
            return "STALE"
        if value < definition.minimum or value > definition.maximum or "SIGNAL_INVALID_VALUE" in faults:
            return "INVALID"
        if definition.model_label == "GENERIC_ESTIMATE":
            return "ESTIMATED"
        return "VALID"
