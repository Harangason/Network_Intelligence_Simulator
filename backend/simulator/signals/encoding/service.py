from __future__ import annotations

from typing import Any


class SignalEncodingService:
    """Quantize and expose raw values before message packing."""

    @staticmethod
    def quantize(definition: Any, value: float) -> float:
        resolution = max(1e-12, abs(float(definition.resolution)))
        return round(value / resolution) * resolution

    @staticmethod
    def raw_value(definition: Any, value: float | None) -> int | None:
        if value is None:
            return None
        raw = int(round((value - definition.offset) / definition.factor))
        signed = "int" in definition.data_type.lower() and "uint" not in definition.data_type.lower() or "signed" in definition.data_type.lower()
        if signed:
            return max(-(1 << (definition.length_bits - 1)), min((1 << (definition.length_bits - 1)) - 1, raw))
        return max(0, min((1 << definition.length_bits) - 1, raw))
