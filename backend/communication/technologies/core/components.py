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
        parameters = dict(context.get("parameters") or {})
        for field in ("bitrate_bps", "nominal_bitrate_bps", "data_bitrate_bps"):
            if field in context:
                parameters[field] = context[field]
        rate_model = self.profile.get("rate_model") or {}
        rate_type = rate_model.get("type")
        supplied_rate_fields = {field for field in parameters if field.endswith("bitrate_bps")}
        allowed_fields = set(rate_model.get("fields") or ())
        for field in sorted(supplied_rate_fields - allowed_fields):
            findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_RATE_MODEL_MISMATCH", f"{field} is not valid for {self.technology_id}", "BLOCKER"))
        if supplied_rate_fields:
            for field in sorted(allowed_fields - supplied_rate_fields):
                findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_PARAMETER_INVALID", f"{field} is required by {rate_type}", "BLOCKER"))
        for field in supplied_rate_fields & allowed_fields:
            value = parameters[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_UNIT_MISMATCH", f"{field} must be a positive numeric bit/s value", "BLOCKER"))
                continue
            maximum = rate_model.get("maximum_bps")
            if field == "nominal_bitrate_bps":
                maximum = rate_model.get("nominal_maximum_bps")
            elif field == "data_bitrate_bps":
                maximum = rate_model.get("data_maximum_bps")
            allowed = rate_model.get("allowed_bps")
            fixed = rate_model.get("fixed_bps")
            invalid = (maximum is not None and value > maximum) or (allowed and value not in allowed) or (fixed is not None and value != fixed)
            if invalid:
                findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_PARAMETER_OUT_OF_RANGE", f"{field}={value} bit/s violates the {self.technology_id} profile", "BLOCKER"))
        return findings


class TechnologyTimingModel:
    def __init__(self, technology_id: str, profile: dict[str, Any]) -> None:
        self.technology_id = technology_id
        self.profile = profile

    def transmission_time_us(self, payload_bytes: int, bitrate: int | None = None) -> float:
        selected_bitrate = int(bitrate or self.profile.get("default_bitrate") or 0)
        rate_model = self.profile.get("rate_model") or {}
        rate_field = rate_model.get("fields", ["bitrate_bps"])
        field = rate_field[-1] if rate_field else "bitrate_bps"
        parameters = dict(rate_model.get("defaults_bps") or {})
        parameters[field] = selected_bitrate
        findings = TechnologyValidator(self.technology_id, self.profile).validate({"parameters": parameters})
        if findings:
            raise ValueError(findings[0].message)
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
