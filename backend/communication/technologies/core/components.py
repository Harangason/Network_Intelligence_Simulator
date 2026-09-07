"""Default binding, transport generation and deterministic validation services."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from .models import PayloadElement, TechnologyBinding, TransportUnit, TransportUnitType


@dataclass(frozen=True)
class ValidationFinding:
    stage: str
    code: str
    message: str
    severity: str = "ERROR"


class TechnologyBindingAdapter:
    def __init__(self, technology_id: str) -> None:
        self.technology_id = technology_id

    def bind(self, functional_interface_ref: str, stack: tuple[str, ...], **context: Any) -> TechnologyBinding:
        return TechnologyBinding(
            id=str(context.get("id") or f"{functional_interface_ref}_{self.technology_id}_binding"),
            functional_interface_ref=functional_interface_ref,
            stack=context["stack_model"],
            hardware_interface_ref=context.get("hardware_interface_ref"),
            network_ref=context.get("network_ref"),
            parameters=dict(context.get("parameters") or {}),
        )


class TechnologyTransportGenerator:
    """Deterministic generator selected through the registry, never a wizard switch."""

    def __init__(self, technology_id: str, transport_unit_type: str, max_payload_bytes: int | None) -> None:
        self.technology_id = technology_id
        self.transport_unit_type = TransportUnitType(transport_unit_type)
        self.max_payload_bytes = max_payload_bytes

    def generate(
        self,
        binding: TechnologyBinding,
        payload_elements: Iterable[PayloadElement],
        *,
        producer_ref: str,
        consumer_refs: Iterable[str],
        timing: dict[str, Any] | None = None,
        identifier: dict[str, Any] | None = None,
        qos: dict[str, Any] | None = None,
    ) -> TransportUnit:
        elements = tuple(payload_elements)
        payload_size = sum(math.ceil(element.size / 8) for element in elements)
        if self.max_payload_bytes is not None and payload_size > self.max_payload_bytes:
            raise ValueError(f"payload {payload_size} B exceeds {self.technology_id} limit {self.max_payload_bytes} B")
        return TransportUnit(
            id=f"{binding.id}_transport",
            technology_binding_ref=binding.id,
            transport_unit_type=self.transport_unit_type,
            producer_ref=producer_ref,
            consumer_refs=tuple(consumer_refs),
            payload_elements=elements,
            payload_size=payload_size,
            timing=dict(timing or {}),
            identifier=dict(identifier or {}),
            qos=dict(qos or {}),
            provenance={"generator": type(self).__name__, "technology": self.technology_id},
        )


class TechnologyValidator:
    def __init__(self, technology_id: str, profile: dict[str, Any]) -> None:
        self.technology_id = technology_id
        self.profile = profile

    def validate(self, context: dict[str, Any]) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        payload_size = int(context.get("payload_size") or 0)
        maximum = self.profile.get("max_payload_bytes")
        if maximum is not None and payload_size > int(maximum):
            findings.append(ValidationFinding("PAYLOAD", "payload_too_large", f"{payload_size} B exceeds {maximum} B"))
        interface_capabilities = {str(item).lower() for item in context.get("hardware_capabilities") or ()}
        required = str(self.profile.get("hardware_interface") or "").lower()
        if interface_capabilities and required and required not in interface_capabilities:
            findings.append(ValidationFinding("HARDWARE_INTERFACE", "incompatible_interface", f"{required} is not provided by the selected hardware interface"))
        return findings


class TechnologyTimingModel:
    def __init__(self, technology_id: str, profile: dict[str, Any]) -> None:
        self.technology_id = technology_id
        self.profile = profile

    def transmission_time_us(self, payload_bytes: int, bitrate: int | None = None) -> float:
        selected_bitrate = int(bitrate or self.profile.get("default_bitrate") or 1)
        overhead = int(self.profile.get("overhead_bytes") or 0)
        return ((max(0, payload_bytes) + overhead) * 8 / selected_bitrate) * 1_000_000


class TechnologyLoadCalculator:
    def __init__(self, technology_id: str, timing_model: TechnologyTimingModel) -> None:
        self.technology_id = technology_id
        self.timing_model = timing_model

    def calculate(self, *, payload_bytes: int, cycle_ms: float, bitrate: int | None = None) -> dict[str, float]:
        if cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive")
        transmission_us = self.timing_model.transmission_time_us(payload_bytes, bitrate)
        return {
            "transmission_time_us": transmission_us,
            "load_percent": transmission_us / (cycle_ms * 1_000) * 100,
        }


class IdentityEncoder:
    def encode(self, payload: bytes) -> bytes:
        return bytes(payload)


class IdentityDecoder:
    def decode(self, payload: bytes) -> bytes:
        return bytes(payload)
