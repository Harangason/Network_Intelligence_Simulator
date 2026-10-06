"""Shared frame result and numeric contract; no technology formulas."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

@dataclass(frozen=True)
class FrameEstimate:
    protocol: str
    payload_bytes: int
    frame_bits: float
    transmission_time_s: float
    calculation_model: str
    calculation_version: str = "1.0"
    is_generic_estimate: bool = False
    transmission_time_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if not self.transmission_time_available:
            result["transmission_time_s"] = None
        return result

def _positive(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) and parsed > 0 else default
