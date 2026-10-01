"""Default binding, transport generation and deterministic validation services."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .models import PayloadElement, TechnologyBinding, TechnologyStack, TransportUnit, TransportUnitType


@dataclass(frozen=True)
class ValidationFinding:
    stage: str
    code: str
    message: str
    severity: str = "ERROR"


class TechnologyBindingAdapter:
    def __init__(self, technology_id: str, stack_validator: Callable | None = None) -> None:
        self.technology_id = technology_id
        self.stack_validator = stack_validator

    def bind(self, functional_interface_ref: str, stack: tuple[str, ...], **context: Any) -> TechnologyBinding:
        model = context.get("stack_model")
        if not isinstance(model, TechnologyStack):
            raise ValueError("TECHNOLOGY_STACK_REQUIRED: an explicit TechnologyStack is required")
        supplied = tuple(stack)
        modeled = tuple(model.technology_ids)
        if self.stack_validator is not None:
            supplied = self.stack_validator(self.technology_id, supplied)
            modeled = self.stack_validator(self.technology_id, modeled)
        if supplied != modeled or not supplied or supplied[-1] != self.technology_id:
            raise ValueError("TECHNOLOGY_STACK_MISMATCH: binding arguments and stack model must identify the same technology layers")
        return TechnologyBinding(
            id=str(context.get("id") or f"{functional_interface_ref}_{self.technology_id}_binding"),
            functional_interface_ref=functional_interface_ref,
            stack=TechnologyStack(supplied),
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
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
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

    def transmission_time_us(
        self, payload_bytes: int, bitrate: int | None = None, *,
        arbitration_bitrate: int | None = None, data_bitrate: int | None = None,
        local_timing_evidence: dict[str, Any] | None = None,
    ) -> float:
        """Use the registered frame branch with explicit rates; never profile defaults as evidence."""
        if self.technology_id in {"i2c", "spi"}:
            from backend.engineering.capacity.calculators import confirmed_serial_evidence
            evidence = confirmed_serial_evidence(self.technology_id, {"local_timing_evidence": local_timing_evidence}, payload_bytes)
            if evidence is None:
                raise ValueError(f"{self.technology_id}: bestätigte Geräte- und Transaktionsgrenzen fehlen.")
            if bitrate is not None and bitrate != evidence["bitrate_bps"]:
                raise ValueError(f"{self.technology_id}: Bitrate widerspricht bestätigtem Geräteprofil.")
            bitrate = evidence["bitrate_bps"]
            rate_parameters = {"bitrate_bps": bitrate}
            frame_parameters = {"local_timing_evidence": evidence}
        elif self.technology_id == "can_fd":
            if not arbitration_bitrate or not data_bitrate:
                raise ValueError("CAN FD benötigt bestätigte Arbitrierungs- und Datenphasenraten.")
            rate_parameters = {"nominal_bitrate_bps": arbitration_bitrate,
                               "data_bitrate_bps": data_bitrate}
            frame_parameters = {"bitrate": arbitration_bitrate,
                                "arbitration_bitrate": arbitration_bitrate,
                                "data_bitrate": data_bitrate}
        else:
            if not bitrate:
                raise ValueError(f"{self.technology_id} benötigt eine bestätigte Bitrate.")
            rate_parameters = {"bitrate_bps": bitrate}
            frame_parameters = {"bitrate": bitrate}
        findings = TechnologyValidator(self.technology_id, self.profile).validate(
            {"parameters": rate_parameters})
        if findings:
            raise ValueError(findings[0].message)
        from backend.engineering.capacity.calculators import estimate_frame
        frame = estimate_frame(self.technology_id, payload_bytes, frame_parameters)
        if frame.is_generic_estimate or not frame.transmission_time_available:
            raise ValueError(f"{self.technology_id}: ausführbares Frame-Modell fehlt.")
        return frame.transmission_time_s * 1_000_000


class TechnologyLoadCalculator:
    def __init__(self, technology_id: str, timing_model: TechnologyTimingModel) -> None:
        self.technology_id = technology_id
        self.timing_model = timing_model

    def calculate(self, *, payload_bytes: int, cycle_ms: float, bitrate: int | None = None,
                  arbitration_bitrate: int | None = None, data_bitrate: int | None = None,
                  local_timing_evidence: dict[str, Any] | None = None) -> dict[str, float]:
        if cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive")
        transmission_us = self.timing_model.transmission_time_us(
            payload_bytes, bitrate, arbitration_bitrate=arbitration_bitrate,
            data_bitrate=data_bitrate, local_timing_evidence=local_timing_evidence)
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
