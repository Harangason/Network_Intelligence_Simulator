"""Default binding, transport generation and deterministic validation services."""

from __future__ import annotations

import math
import re
from urllib.parse import urlsplit
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


def required_rate_fields(model: dict[str, Any], parameters: dict[str, Any]) -> set[str]:
    fields = set(model.get('fields') or ())
    for field, conditions in (model.get('optional_fields_when') or {}).items():
        if conditions and all(type(parameters.get(key)) is type(value) and parameters.get(key) == value
                              for key,value in conditions.items()):
            fields.discard(field)
    return fields


def _parameter_expression(expression: Any, parameters: dict[str, Any]) -> float | None:
    """Evaluate profile-declared numeric dependencies; never execute source text."""
    if isinstance(expression,str):
        expression=parameters.get(expression)
    if isinstance(expression,(int,float)) and not isinstance(expression,bool):
        return float(expression) if math.isfinite(expression) else math.nan
    if expression is None:
        return None
    if not isinstance(expression,dict) or len(expression)!=1:
        return math.nan
    operation,terms=next(iter(expression.items()))
    values=[_parameter_expression(term,parameters) for term in terms]
    if any(value is None for value in values):
        return None
    if not all(math.isfinite(value) for value in values):
        return math.nan
    try:
        if operation=='sum': return sum(values)
        if operation=='product': return math.prod(values)
        if operation=='subtract' and len(values)==2: return values[0]-values[1]
        if operation=='power' and len(values)==2: return math.pow(*values)
        if operation=='maximum' and values: return max(values)
        if operation=='ceiling' and len(values)==1: return math.ceil(values[0])
    except (OverflowError,ValueError):
        return math.nan
    return math.nan


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
            for field in sorted(required_rate_fields(rate_model, parameters) - supplied_rate_fields):
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
            minimum = rate_model.get("minimum_bps")
            invalid = (minimum is not None and value < minimum) or (maximum is not None and value > maximum) or (allowed and value not in allowed) or (fixed is not None and value != fixed)
            ranges = rate_model.get('allowed_ranges_bps')
            if ranges and not any(lower <= value <= upper for lower, upper in ranges):
                invalid = True
            if invalid:
                findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_PARAMETER_OUT_OF_RANGE", f"{field}={value} bit/s violates the {self.technology_id} profile", "BLOCKER"))
        for name, spec in (self.profile.get('parameter_schema') or {}).items():
            if name in allowed_fields or name not in parameters:
                continue
            value = parameters[name]
            if value is None or value == '':
                continue  # Completeness is checked separately; blank is not evidence.
            kind = spec.get('type')
            valid_type = (kind not in {'number', 'integer', 'boolean', 'select', 'text'} or
                          kind in {'number', 'integer'} and isinstance(value, (int, float)) and
                          not isinstance(value, bool) and math.isfinite(value) or
                          kind == 'boolean' and type(value) is bool or
                          kind in {'select', 'text'} and isinstance(value, str))
            if not valid_type or (spec.get('integer') or kind == 'integer') and isinstance(value, (int, float)) and value != int(value):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'TECHNOLOGY_PARAMETER_TYPE_MISMATCH',
                    f'{name} has the wrong type for {self.technology_id}', 'BLOCKER'))
                continue
            schema_when = spec.get('schema_when')
            if schema_when and not all(type(parameters.get(key)) is type(expected) and parameters.get(key) == expected
                                       for key, expected in schema_when.items()):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'TECHNOLOGY_PARAMETER_SCOPE_UNVERIFIED',
                    f'{name}: reviewed bounds apply only to {schema_when}; matching device/version schema required', 'REVIEW'))
                continue  # Never validate this variant using another version's limits.
            minimum, maximum = spec.get('min', spec.get('minimum')), spec.get('max', spec.get('maximum'))
            outside = (kind in {'number', 'integer'} and
                       (minimum is not None and value < minimum or maximum is not None and value > maximum))
            if kind == 'text' and spec.get('pattern'):
                matches = re.fullmatch(spec['pattern'], value)
                outside |= matches is None
                if matches and spec.get('integer_text_maximum') is not None:
                    decimal = value.lstrip('0') or '0'
                    outside |= len(decimal) > len(str(spec['integer_text_maximum'])) or int(decimal) > spec['integer_text_maximum']
            outside |= 'allowed_values' in spec and value not in spec['allowed_values']
            if isinstance(value, (int, float)) and not isinstance(value, bool) and spec.get('multiple_of'):
                outside |= not math.isclose(value / spec['multiple_of'], round(value / spec['multiple_of']), rel_tol=0, abs_tol=1e-9)
            outside |= value in spec.get('forbidden_values', ())
            if kind == 'text' and spec.get('format') == 'WSS_URI':
                try:
                    uri = urlsplit(value)
                    outside |= (uri.scheme != 'wss' or not uri.hostname or uri.username is not None
                                or uri.password is not None or bool(uri.fragment) or any(char.isspace() for char in value)
                                or uri.port is not None and not 1 <= uri.port <= 65535)
                except ValueError:
                    outside = True
            if kind == 'text' and spec.get('format') == 'ABSOLUTE_URI':
                try:
                    uri=urlsplit(value)
                    outside |= (uri.scheme not in spec.get('allowed_schemes',[]) or not uri.hostname
                                or uri.username is not None or uri.password is not None or bool(uri.fragment)
                                or any(char.isspace() for char in value) or uri.port is not None and not 1<=uri.port<=65535)
                except ValueError:
                    outside=True
            if kind == 'text' and spec.get('format') == 'IP_ADDRESS':
                from ipaddress import ip_address
                try:
                    ip_address(value)
                except ValueError:
                    outside = True
            if outside or kind == 'select' and value not in spec.get('options', ()):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'TECHNOLOGY_PARAMETER_OUT_OF_RANGE',
                    f'{name} violates the {self.technology_id} parameter schema', 'BLOCKER'))
        local_schema = self.profile.get('local_timing_schema') or []
        if local_schema and any(item.get('source') for item in local_schema) and 'local_timing_evidence' in parameters:
            evidence = parameters['local_timing_evidence']
            if not isinstance(evidence, dict):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_EVIDENCE_INVALID',
                    'local_timing_evidence must be an object', 'BLOCKER'))
            else:
                if evidence.get('confirmed') is not None and type(evidence['confirmed']) is not bool:
                    findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_EVIDENCE_INVALID',
                        'Device confirmation must be an explicit boolean, not a string or numeric flag', 'BLOCKER'))
                if evidence.get('source') is not None and not isinstance(evidence['source'], str):
                    findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_SOURCE_MISSING',
                        'Device timing source must be an actual text reference', 'BLOCKER'))
                if evidence.get('technology') and str(evidence['technology']).lower() != self.technology_id:
                    findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_TECHNOLOGY_MISMATCH',
                        'Device timing belongs to another technology', 'BLOCKER'))
                for spec in local_schema:
                    value = evidence.get(spec['key'])
                    absent = value is None or value == ''
                    invalid = not absent and (not isinstance(value, (int, float)) or isinstance(value, bool)
                        or not math.isfinite(value) or value < spec.get('minimum', 0))
                    if invalid or absent and evidence.get('confirmed') is True and not spec.get('optional'):
                        findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_EVIDENCE_INVALID',
                            f"local_timing_evidence.{spec['key']} requires a finite device bound in {spec.get('unit')}", 'BLOCKER'))
                if evidence.get('confirmed') is True and not str(evidence.get('source') or '').strip():
                    findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_SOURCE_MISSING',
                        'Confirmed device bounds require the actual datasheet or measurement source', 'BLOCKER'))
        for constraint in self.profile.get('parameter_constraints') or ():
            if not all(parameters.get(name) == value for name, value in constraint.get('when', {}).items()):
                continue
            if not all(parameters.get(name) is not None and parameters.get(name) != ''
                       for name in constraint.get('when_present', [])):
                continue
            if not all(isinstance(parameters.get(name), (int, float)) and not isinstance(parameters[name], bool)
                       and parameters[name] > 0 for name in constraint.get('when_positive', [])):
                continue
            if not all(isinstance(parameters.get(name), (int, float)) and not isinstance(parameters[name], bool)
                       and bounds[0] <= parameters[name] <= bounds[1]
                       for name, bounds in constraint.get('when_ranges', {}).items()):
                continue
            if not all(isinstance(parameters.get(name), (int,float)) and not isinstance(parameters[name],bool)
                       and bounds[0] <= parameters[name] and (bounds[1] is None or parameters[name] < bounds[1])
                       for name,bounds in constraint.get('when_half_open_ranges',{}).items()):
                continue
            if not all(isinstance(parameters.get(name),(int,float)) and not isinstance(parameters[name],bool)
                       and parameters[name] > bound for name,bound in constraint.get('when_greater_than',{}).items()):
                continue
            name = constraint['parameter']
            value = parameters.get(name)
            if constraint.get('required') and (value is None or isinstance(value,str) and not value.strip()):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS','TECHNOLOGY_PARAMETER_MISSING',
                    f'{name} is required by the selected {self.technology_id} configuration','REVIEW'))
                continue
            if value is None or value == '' and not constraint.get('text_encoding'):
                continue
            outside = 'allowed' in constraint and value not in constraint['allowed']
            different = parameters.get(constraint.get('not_equal_parameter'))
            if different is not None and different != '':
                outside |= value == different
            reference = parameters.get(constraint.get('equal_parameter'))
            if reference is not None and reference != '':
                offset = constraint.get('equal_parameter_offset', 0)
                if not offset or isinstance(reference, (int, float)) and not isinstance(reference, bool):
                    outside |= value != (reference + offset if offset else reference)
            if isinstance(value, str) and constraint.get('pattern'):
                outside |= re.fullmatch(constraint['pattern'], value) is None
            if isinstance(value, str) and constraint.get('text_encoding'):
                # Only explicitly registered Unicode/ASCII encodings are accepted;
                # encoded application bytes are distinct from scalar/code-unit counts.
                codec = constraint['text_encoding']
                if codec not in {'utf-8', 'ascii', 'utf-16le', 'utf-16be'}:
                    outside = True
                else:
                    try:
                        counts = {'encoded_bytes_parameter': len(value.encode(codec, errors='strict')),
                                  'text_codepoints_parameter': len(value),
                                  'text_utf16_units_parameter': len(value.encode('utf-16le', errors='strict')) // 2}
                        for target, count in counts.items():
                            actual = parameters.get(constraint.get(target))
                            if actual is not None and actual != '':
                                outside |= actual != count
                    except UnicodeError:
                        outside = True
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                for kind in ('equal_expression','minimum_expression','maximum_expression'):
                    if kind not in constraint:
                        continue
                    bound=_parameter_expression(constraint[kind],parameters)
                    if bound is not None:
                        outside |= not math.isfinite(bound) or (not math.isclose(value,bound,rel_tol=1e-9,abs_tol=1e-9)
                            if kind=='equal_expression' else value < bound if kind=='minimum_expression' else value > bound)
                terms = constraint.get('equal_sum')
                if terms and all(isinstance(parameters.get(term['parameter']), (int, float)) and not isinstance(parameters[term['parameter']], bool)
                                 and math.isfinite(parameters[term['parameter']]) for term in terms):
                    expected = sum(parameters[term['parameter']] * term.get('factor', 1) for term in terms) + constraint.get('equal_sum_offset', 0)
                    outside |= not math.isclose(value, expected, rel_tol=0, abs_tol=1e-6)
                for ratio_kind in ('equal_ratio','maximum_ratio'):
                    ratio = constraint.get(ratio_kind)
                    if not ratio:
                        continue
                    keys = [ratio[key] for key in ('numerator_parameter',) if ratio.get(key)]
                    keys += ratio.get('numerator_sum', []) + ratio.get('numerator_product', []) + ratio.get('denominator_sum', []) + ratio.get('denominator_product', [])
                    if all(isinstance(parameters.get(key), (int, float)) and not isinstance(parameters[key], bool)
                           and math.isfinite(parameters[key]) and parameters[key] > 0 for key in keys):
                        numerator = parameters[ratio['numerator_parameter']] if ratio.get('numerator_parameter') else sum(parameters[key] for key in ratio.get('numerator_sum', [])) + ratio.get('numerator_offset', 0)
                        denominator = (sum(parameters[key] for key in ratio.get('denominator_sum', [])) + ratio.get('denominator_offset', 0)) * math.prod(parameters[key] for key in ratio.get('denominator_product', []))
                        bound = numerator * math.prod(parameters[key] for key in ratio.get('numerator_product', [])) * ratio.get('factor', 1) / denominator
                        if ratio_kind=='equal_ratio':
                            outside |= not math.isclose(value, bound, rel_tol=1e-9, abs_tol=1e-6)
                        else:
                            outside |= value >= bound if constraint.get('exclusive_maximum_ratio') else value > bound
                if constraint.get('multiple_of'):
                    outside |= not math.isclose(value / constraint['multiple_of'], round(value / constraint['multiple_of']), rel_tol=0, abs_tol=1e-9)
                outside |= constraint.get('maximum') is not None and value > constraint['maximum']
                outside |= constraint.get('minimum') is not None and value < constraint['minimum']
                outside |= constraint.get('exclusive_minimum') is not None and value <= constraint['exclusive_minimum']
                outside |= constraint.get('exclusive_maximum') is not None and value >= constraint['exclusive_maximum']
                lower = parameters.get(constraint.get('minimum_parameter'))
                if isinstance(lower,(int,float)) and not isinstance(lower,bool):
                    outside |= value < lower
                reference = parameters.get(constraint.get('maximum_parameter'))
                if isinstance(reference, (int, float)) and not isinstance(reference, bool):
                    subtract = [parameters.get(key) for key in constraint.get('maximum_subtract_parameters', [])]
                    if all(isinstance(part, (int, float)) and not isinstance(part, bool) for part in subtract):
                        outside |= value > reference * constraint.get('maximum_factor', 1) + constraint.get('maximum_offset', 0) - sum(subtract)
                difference = constraint.get('difference_parameters')
                if difference:
                    left, right = (parameters.get(key) for key in difference)
                    if all(isinstance(part, (int, float)) and not isinstance(part, bool) for part in (left, right)):
                        outside |= not math.isclose(value, left - right, rel_tol=0, abs_tol=1e-6)
                for group in ('minimum_product_parameters', 'bounded_product_parameters'):
                    terms = constraint.get(group)
                    if not terms:
                        continue
                    actual = [parameters.get(term['parameter']) for term in terms]
                    if all(isinstance(part, (int, float)) and not isinstance(part, bool) and math.isfinite(part) for part in actual):
                        product = math.prod(part + term.get('offset', 0) for part, term in zip(actual, terms))
                        if group == 'minimum_product_parameters':
                            bound = product * constraint.get('minimum_product_factor', 1)
                            outside |= value <= bound if constraint.get('exclusive_minimum_product') else value < bound
                        else:
                            outside |= product > constraint['maximum_product']
            if outside:
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH',
                    f'{name} contradicts {self.technology_id} conditions {constraint.get("when")}', 'BLOCKER'))
        return findings


class TechnologyTimingModel:
    def __init__(self, technology_id: str, profile: dict[str, Any]) -> None:
        self.technology_id = technology_id
        self.profile = profile

    def transmission_time_us(
        self, payload_bytes: int, bitrate: int | None = None, *,
        arbitration_bitrate: int | None = None, data_bitrate: int | None = None,
        local_timing_evidence: dict[str, Any] | None = None,
        can_fd_brs: bool | None = None, can_frame_format: str | None = None,
        can_fd_dlc: int | None = None, can_fd_wire_data_bytes: int | None = None,
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
            nominal = arbitration_bitrate if arbitration_bitrate is not None else bitrate
            if can_fd_brs is not None and type(can_fd_brs) is not bool:
                raise ValueError('CAN FD BRS must be an actual boolean.')
            if not nominal or can_fd_brs is not False and not data_bitrate:
                raise ValueError("CAN FD benötigt bestätigte Arbitrierungs- und Datenphasenraten.")
            rate_parameters = {"nominal_bitrate_bps": nominal}
            if data_bitrate is not None:
                rate_parameters['data_bitrate_bps']=data_bitrate
            frame_parameters = {"bitrate": nominal,
                                "arbitration_bitrate": nominal,
                                "data_bitrate": data_bitrate}
        else:
            if not bitrate:
                raise ValueError(f"{self.technology_id} benötigt eine bestätigte Bitrate.")
            rate_parameters = {"bitrate_bps": bitrate}
            frame_parameters = {"bitrate": bitrate}
        native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
            'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
        if native and self.technology_id not in {'can','can_fd'} or self.technology_id=='can' and set(native)-{'can_frame_format'}:
            raise ValueError('CAN timing options are not applicable to this technology.')
        rate_parameters.update(native)
        frame_parameters.update(native)
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
                  local_timing_evidence: dict[str, Any] | None = None,
                  can_fd_brs: bool | None = None, can_frame_format: str | None = None,
                  can_fd_dlc: int | None = None, can_fd_wire_data_bytes: int | None = None) -> dict[str, float]:
        if cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive")
        transmission_us = self.timing_model.transmission_time_us(
            payload_bytes, bitrate, arbitration_bitrate=arbitration_bitrate,
            data_bitrate=data_bitrate, local_timing_evidence=local_timing_evidence,
            can_fd_brs=can_fd_brs,can_frame_format=can_frame_format,
            can_fd_dlc=can_fd_dlc,can_fd_wire_data_bytes=can_fd_wire_data_bytes)
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
