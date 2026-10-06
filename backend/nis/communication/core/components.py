"""Default binding, transport generation and deterministic validation services."""

from __future__ import annotations

import math
import json
import re
from fractions import Fraction
from decimal import Decimal
from urllib.parse import urlsplit
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from backend.nis.communication.core.models import PayloadElement, TechnologyBinding, TechnologyStack, TransportUnit, TransportUnitType


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
        if conditions and all(any(type(parameters.get(key)) is type(candidate) and parameters.get(key) == candidate
                                  for candidate in (value if isinstance(value, list) else [value]))
                              for key,value in conditions.items()):
            fields.discard(field)
    return fields


# Supported rule vocabulary is explicit; unknown rules must never silently pass.
_PARAMETER_RULE_KEYS = frozenset(['allow_empty_text', 'allowed', 'bounded_product_parameters', 'delimited_ascii_sentence_fields', 'difference_parameters', 'encoded_bytes_parameter', 'equal_decimal_parameter', 'equal_expression', 'equal_parameter', 'equal_parameter_offset', 'equal_ratio', 'equal_sum', 'equal_sum_offset', 'equals_parameters_boolean', 'exact_decimal_bounds', 'exact_decimal_equality', 'exclusive_maximum', 'exclusive_maximum_expression', 'exclusive_maximum_ratio', 'exclusive_minimum', 'exclusive_minimum_expression', 'exclusive_minimum_product', 'forbidden', 'forbidden_bit_mask', 'hex_bytes_parameter', 'hex_crc16_modbus_parameter', 'hex_crc32_ieee_parameter', 'hex_crc32_prefix_bytes', 'hex_crc8_maxim_parameter', 'hex_crc8_prefix_bytes', 'hex_octets', 'integer', 'integer_bitfields', 'integer_text_base', 'integer_text_maximum', 'ip_address_max', 'ip_address_maximum', 'ip_address_min', 'ip_address_minimum', 'ip_address_version', 'json_array_envelope', 'json_gate_schedule', 'json_number_array', 'maximum', 'maximum_expression', 'maximum_factor', 'maximum_offset', 'maximum_parameter', 'maximum_product', 'maximum_ratio', 'maximum_subtract_parameters', 'minimum', 'minimum_expression', 'minimum_parameter', 'minimum_product', 'minimum_product_factor', 'minimum_product_parameters', 'multiple_of', 'not_equal_parameter', 'parameter', 'pattern', 'required', 'source', 'source_revision', 'text_codepoints_parameter', 'text_encoding', 'text_join', 'text_utf16_units_parameter', 'when', 'when_greater_than', 'when_half_open_ranges', 'when_not', 'when_positive', 'when_present', 'when_ranges'])

def validate_parameter_rule_syntax(profile: dict[str, Any]) -> None:
    """Reject unsupported rule DSL before a profile can be registered."""
    arities = {'sum': None, 'product': None, 'subtract': 2, 'integer_remainder': 2,
               'power': 2, 'maximum': None, 'minimum': None, 'ceiling': 1, 'floor': 1}
    def expression(value, depth=0):
        if depth > 64:
            raise ValueError('Technology parameter expression is too deep')
        if isinstance(value, str) or isinstance(value, (int, float)) and not isinstance(value, bool) and _safe_finite(value):
            return
        if not isinstance(value, dict) or len(value) != 1:
            raise ValueError('Invalid technology parameter expression')
        operation, terms = next(iter(value.items()))
        if operation not in arities or not isinstance(terms, list) or not terms or arities[operation] is not None and len(terms) != arities[operation]:
            raise ValueError(f'Unsupported technology parameter expression: {operation}')
        for term in terms:
            expression(term, depth + 1)
    for rule in profile.get('parameter_constraints') or ():
        if not isinstance(rule, dict) or not isinstance(rule.get('parameter'), str):
            raise ValueError('Technology parameter rule requires a parameter')
        unknown = set(rule) - _PARAMETER_RULE_KEYS
        if unknown:
            raise ValueError(f'Unsupported technology parameter rule keys: {sorted(unknown)}')
        for condition in ('when', 'when_not'):
            if not isinstance(rule.get(condition, {}), dict) or any(not isinstance(value, (str, int, float, bool)) for value in rule.get(condition, {}).values()):
                raise ValueError(f'Technology parameter {condition} requires explicit scalar conditions')
        for key in ('equal_expression', 'minimum_expression', 'maximum_expression', 'exclusive_minimum_expression', 'exclusive_maximum_expression'):
            if key in rule:
                expression(rule[key])


def _normalize_wide_integers(parameters: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Decimal wire text is allowed only for declared wide integer fields.

    Python calculations retain exact integers; canonical JSON/UI can keep the
    decimal text and its identical provenance without an IEEE754 round trip.
    """
    result = dict(parameters)
    for name, spec in schema.items():
        wide = (spec.get('integer') or spec.get('type') == 'integer') and any(
            isinstance(spec.get(key), int) and abs(spec[key]) > 2**53 - 1
            for key in ('min', 'max', 'minimum', 'maximum'))
        value = result.get(name)
        if wide and isinstance(value, str) and len(value) <= 40 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)', value):
            result[name] = int(value)
    return result


def _safe_finite(value: Any) -> bool:
    """Untrusted integers and exact intermediate fractions may exceed float range."""
    try:
        return math.isfinite(value)
    except (OverflowError,TypeError,ValueError):
        return False


def _condition_equal(actual: Any, expected: Any) -> bool:
    """Numeric JSON int/float values match; boolean1 and numeric1 do not."""
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        return isinstance(actual,(int,float)) and not isinstance(actual,bool) and _safe_finite(actual) and actual==expected
    return type(actual)is type(expected) and actual==expected


def _parameter_expression(expression: Any, parameters: dict[str, Any], *, exact: bool = False, _depth: int = 0) -> Fraction | float | None:
    """Evaluate registered dependencies; exact decimal inputs protect strict bounds."""
    if _depth > 64:
        return math.nan
    if isinstance(expression,str):
        expression=parameters.get(expression)
        # Parameter values are scalar operands, never registered expression trees.
        if expression is not None and (not isinstance(expression,(int,float)) or isinstance(expression,bool)):
            return math.nan
    if isinstance(expression,(int,float)) and not isinstance(expression,bool):
        try:
            if not _safe_finite(expression): return math.nan
            return Fraction(str(expression)) if exact else float(expression)
        except (OverflowError,ValueError):
            return math.nan
    if expression is None:
        return None
    if not isinstance(expression,dict) or len(expression)!=1:
        return math.nan
    operation,terms=next(iter(expression.items()))
    arities={'sum':None,'product':None,'subtract':2,'integer_remainder':2,'power':2,
             'maximum':None,'minimum':None,'ceiling':1,'floor':1}
    if operation not in arities or not isinstance(terms,list) or not terms or (arities[operation] is not None and len(terms)!=arities[operation]):
        return math.nan
    values=[_parameter_expression(term,parameters,exact=exact,_depth=_depth+1) for term in terms]
    if any(value is None for value in values):
        return None
    if not all(_safe_finite(value) for value in values):
        return math.nan
    try:
        if operation in ('sum','product','subtract'):
            result=sum(values) if operation=='sum' else math.prod(values) if operation=='product' else values[0]-values[1]
            return result if _safe_finite(result) else math.nan
        if operation=='integer_remainder' and len(values)==2:
            # Registered integer-width/channel rules only; never truncate a
            # fractional value or reuse floating remainder for addresses.
            if any(value != int(value) for value in values) or values[1] <= 0:
                return math.nan
            return int(values[0]) % int(values[1])
        if operation=='power' and len(values)==2:
            exponent=values[1]
            if isinstance(exponent,Fraction) and exponent.denominator==1:
                # Reject nonrepresentable powers before exact big-integer allocation.
                # All registered widths are small; invalid user exponents must not
                # allocate billions of bits merely to report a schema error.
                math.pow(float(values[0]),float(exponent))
                if abs(exponent)>4096 or abs(exponent)*(values[0].numerator.bit_length()+values[0].denominator.bit_length())>32768:
                    return math.nan
                return values[0] ** int(exponent)
            return math.pow(*values)
        if operation=='maximum' and values: return max(values)
        if operation=='minimum' and values: return min(values)
        if operation=='ceiling' and len(values)==1: return math.ceil(values[0])
        if operation=='floor' and len(values)==1: return math.floor(values[0])
    except (OverflowError,ValueError,ZeroDivisionError):
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
        if interface_capabilities and required and not interface_capabilities.intersection({required, self.technology_id, *self.profile.get('hardware_capability_aliases', [])}):
            findings.append(ValidationFinding("HARDWARE_INTERFACE", "incompatible_interface", f"{required} is not provided by the selected hardware interface"))
        parameters = _normalize_wide_integers(dict(context.get("parameters") or {}), self.profile.get("parameter_schema", {}))
        for field in ("bitrate_bps", "nominal_bitrate_bps", "data_bitrate_bps"):
            if field in context:
                parameters[field] = context[field]
        rate_model = self.profile.get("rate_model") or {}
        rate_type = rate_model.get("type")
        allowed_fields = set(rate_model.get("fields") or ())
        # Native phase/part clocks are validated by their declared schema and
        # applicability constraints. Their suffix does not turn them into the
        # universal transport rate (e.g. IEC61162 serial/CAN/IP parts).
        native_prefixes = self.profile.get('native_parameter_prefixes') or ()
        native_clocks = {field for field in self.profile.get('parameter_schema', {})
                         if any(field.startswith(prefix) for prefix in native_prefixes)}
        supplied_rate_fields = {field for field in parameters if field.endswith("bitrate_bps")
                                and (field in allowed_fields or field not in native_clocks)}
        for field in sorted(supplied_rate_fields - allowed_fields):
            findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_RATE_MODEL_MISMATCH", f"{field} is not valid for {self.technology_id}", "BLOCKER"))
        if supplied_rate_fields:
            for field in sorted(required_rate_fields(rate_model, parameters) - supplied_rate_fields):
                findings.append(ValidationFinding("TECHNOLOGY_PARAMETERS", "TECHNOLOGY_PARAMETER_INVALID", f"{field} is required by {rate_type}", "BLOCKER"))
        for field in supplied_rate_fields & allowed_fields:
            value = parameters[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not _safe_finite(value) or value <= 0:
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
                          not isinstance(value, bool) and _safe_finite(value) or
                          kind == 'boolean' and type(value) is bool or
                          kind in {'select', 'text'} and isinstance(value, str))
            if not valid_type or (spec.get('integer') or kind == 'integer') and isinstance(value, (int, float)) and (value != int(value) or isinstance(value, float) and abs(value) > 2**53 - 1):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'TECHNOLOGY_PARAMETER_TYPE_MISMATCH',
                    f'{name} has the wrong type for {self.technology_id}', 'BLOCKER'))
                continue
            schema_when = spec.get('schema_when')
            if schema_when and not all(
                any(type(parameters.get(key)) is type(candidate) and parameters.get(key) == candidate
                    for candidate in (expected if isinstance(expected, list) else [expected]))
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
            if kind == 'text' and spec.get('format') == 'IP_NETWORK':
                from ipaddress import ip_network
                try:
                    network = ip_network(value, strict=True)
                    outside |= ('/' not in value or '%' in value
                                or spec.get('ip_version') is not None and network.version != spec['ip_version']
                                or spec.get('prefix_length') is not None and network.prefixlen != spec['prefix_length'])
                    if spec.get('within_network'):
                        parent = ip_network(spec['within_network'], strict=True)
                        outside |= network.version != parent.version or not network.subnet_of(parent)
                except (ValueError, TypeError):
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
                    kind=spec.get('type','number' if spec.get('numeric') else 'boolean' if spec.get('boolean') else 'text')
                    invalid=False
                    if not absent:
                        if kind=='number':
                            invalid=(not isinstance(value,(int,float)) or isinstance(value,bool) or not _safe_finite(value))
                            if not invalid:
                                invalid=(value<spec.get('minimum',0) or spec.get('maximum') is not None and value>spec['maximum']
                                    or spec.get('integer') and value!=int(value))
                        elif kind=='boolean': invalid=type(value)is not bool
                        elif kind=='address':
                            invalid=not (isinstance(value,str) and re.fullmatch(r'(?:[0-9]+|0[xX][0-9a-fA-F]+)',value)
                                or isinstance(value,(int,float)) and not isinstance(value,bool)
                                and _safe_finite(value) and value==int(value))
                        elif kind in ('text','select'): invalid=not isinstance(value,str) or not value.strip()
                        if spec.get('options'): invalid |= value not in spec['options']
                        if spec.get('allowed_values'): invalid |= value not in spec['allowed_values']
                    required_local=not spec.get('optional')
                    if spec.get('required_scopes'):
                        required_local=(evidence.get('evidence_scope') or 'TRANSACTION') in spec['required_scopes']
                    if 'required_when' in spec:
                        required_local=all(type(parameters.get(key)) is type(expected) and parameters.get(key)==expected
                            for key,expected in spec['required_when'].items())
                    if invalid or absent and evidence.get('confirmed') is True and required_local:
                        findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_EVIDENCE_INVALID',
                            f"local_timing_evidence.{spec['key']} requires a matching {kind} value in its declared device scope", 'BLOCKER'))
                if self.technology_id=='i2c' and evidence.get('confirmed') is True:
                    from backend.nis.communication.technologies.i2c.rules import evidence_issues
                    for key in evidence_issues(evidence):
                        findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS','LOCAL_TIMING_EVIDENCE_INVALID',
                            f'local_timing_evidence.{key} violates the I2C role/mode/transaction rules','BLOCKER'))
                if evidence.get('confirmed') is True and not str(evidence.get('source') or '').strip():
                    findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS', 'LOCAL_TIMING_SOURCE_MISSING',
                        'Confirmed device bounds require the actual datasheet or measurement source', 'BLOCKER'))
        for constraint in self.profile.get('parameter_constraints') or ():
            if not all(_condition_equal(parameters.get(name),value) for name,value in constraint.get('when',{}).items()):
                continue
            if any(type(parameters.get(name)) is type(value) and parameters.get(name)==value
                   for name,value in constraint.get('when_not',{}).items()):
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
            if constraint.get('required') and (value is None or isinstance(value,str) and not value.strip()
                    and not constraint.get('allow_empty_text')):
                findings.append(ValidationFinding('TECHNOLOGY_PARAMETERS','TECHNOLOGY_PARAMETER_MISSING',
                    f'{name} is required by the selected {self.technology_id} configuration','REVIEW'))
                continue
            if value is None or value == '' and not constraint.get('text_encoding'):
                continue
            outside = 'allowed' in constraint and value not in constraint['allowed']
            if constraint.get('integer'):
                outside |= (not isinstance(value, (int, float)) or isinstance(value, bool)
                            or not _safe_finite(value) or value != int(value))
            outside |= value in constraint.get('forbidden', [])
            different = parameters.get(constraint.get('not_equal_parameter'))
            if different is not None and different != '':
                outside |= value == different
            reference = parameters.get(constraint.get('equal_parameter'))
            if reference is not None and reference != '':
                offset = constraint.get('equal_parameter_offset', 0)
                if not offset or isinstance(reference, (int, float)) and not isinstance(reference, bool):
                    outside |= value != (reference + offset if offset else reference)
            if constraint.get('equals_parameters_boolean'):
                left,right=(parameters.get(key)for key in constraint['equals_parameters_boolean'])
                if left is not None and right is not None:
                    outside |= type(value)is not bool or value != _condition_equal(left,right)
            if isinstance(value,str) and constraint.get('text_join'):
                parts=constraint['text_join']
                resolved=[part.get('literal')if 'literal'in part else parameters.get(part.get('parameter'))for part in parts]
                if all(isinstance(part,str)for part in resolved):
                    outside |= value != ''.join(resolved)
            decimal_reference=parameters.get(constraint.get('equal_decimal_parameter'))
            if decimal_reference is not None and isinstance(value,str) and isinstance(decimal_reference,str):
                if re.fullmatch(r'[0-9]+',value) and re.fullmatch(r'[0-9]+',decimal_reference):
                    # Exact decimal comparison without int/float conversion, including huge HTTP lengths.
                    outside |= (value.lstrip('0') or '0') != (decimal_reference.lstrip('0') or '0')
            if isinstance(value, str) and constraint.get('pattern'):
                outside |= re.fullmatch(constraint['pattern'], value) is None
            if isinstance(value,str) and 'integer_text_maximum' in constraint:
                maximum=str(constraint['integer_text_maximum'])
                decimal=value.lstrip('0') or '0'
                outside |= (re.fullmatch(r'[0-9]+',value)is None or
                            len(decimal)>len(maximum) or len(decimal)==len(maximum) and decimal>maximum)
            if isinstance(value,str) and constraint.get('json_number_array'):
                try:
                    def reject_number_constant(token):raise ValueError('non-finite JSON number')
                    numbers=json.loads(value,parse_float=Decimal,parse_int=Decimal,parse_constant=reject_number_constant)
                    if not isinstance(numbers,list):raise ValueError('numeric array required')
                    for number in numbers:
                        if not isinstance(number,Decimal) or not number.is_finite():raise ValueError('finite numeric element required')
                        actual=float(number)
                        if not _safe_finite(actual) or number!=0 and actual==0:raise ValueError('finite representable Double required')
                    count=parameters.get(constraint['json_number_array'].get('count_parameter'))
                    if count is not None:outside |= count != len(numbers)
                except (ValueError,TypeError,OverflowError):
                    outside=True
            if isinstance(value,str) and constraint.get('ip_address_version'):
                from ipaddress import ip_address
                try:
                    address=ip_address(value)
                    outside |= address.version != constraint['ip_address_version']
                    for key,minimum in [('ip_address_min',True),('ip_address_max',False)]:
                        if key in constraint:
                            bound=ip_address(constraint[key])
                            outside |= address.version != bound.version or (int(address) < int(bound)if minimum else int(address) > int(bound))
                except ValueError:
                    outside=True
            if isinstance(value,str) and constraint.get('integer_bitfields'):
                # Exact uint64 identity decoding; never round a NAME through
                # float/JavaScript Number or execute expressions from sources.
                base=constraint.get('integer_text_base',16)
                try:
                    raw=int(value,base)if base in (10,16)else None
                    outside |= raw is None or raw < 0
                    if raw is not None and raw >= 0:
                        for bitfield in constraint['integer_bitfields']:
                            actual=parameters.get(bitfield['parameter'])
                            if actual is None or actual=='':continue
                            expected=(raw >> bitfield['offset']) & ((1 << bitfield['width'])-1)
                            if bitfield.get('boolean'):expected=bool(expected)
                            outside |= actual != expected
                except ValueError:
                    outside=True
            if isinstance(value,str) and any(key in constraint for key in ('hex_bytes_parameter','hex_crc16_modbus_parameter','hex_crc8_maxim_parameter','hex_crc32_ieee_parameter','hex_octets')):
                try:
                    if re.fullmatch(r'(?:[0-9A-Fa-f]{2})*',value) is None:raise ValueError('hex octets required')
                    octets=bytes.fromhex(value)
                    length=parameters.get(constraint.get('hex_bytes_parameter'))
                    if length is not None:outside |= length != len(octets)
                    for part in constraint.get('hex_octets',[]):
                        actual=parameters.get(part['parameter']); offset,width=part['offset'],part['width']
                        if actual is not None:
                            byte_order=part.get('byte_order','big')
                            outside |= byte_order not in ('big','little') or len(octets)<offset+width
                            if byte_order in ('big','little'):
                                signed=part.get('signed',False)
                                if type(signed)is not bool:
                                    outside=True
                                else:
                                    outside |= type(actual)is not int or actual!=int.from_bytes(octets[offset:offset+width],byte_order,signed=signed)
                    actual_crc32=parameters.get(constraint.get('hex_crc32_ieee_parameter'))
                    if actual_crc32 is not None:
                        count=constraint.get('hex_crc32_prefix_bytes',len(octets))
                        if type(count)is not int or count<0 or count>len(octets):
                            outside=True
                        else:
                            # Reflected IEEE CRC32, initial FFFFFFFF, final XOR.
                            # TRDP's header FCS is this value in little endian;
                            # a header CRC does not cover the application data.
                            crc32=0xffffffff
                            for octet in octets[:count]:
                                crc32 ^= octet
                                for _ in range(8):crc32=(crc32>>1)^0xedb88320 if crc32&1 else crc32>>1
                            outside |= type(actual_crc32)is not int or actual_crc32!=(crc32^0xffffffff)
                    actual_crc=parameters.get(constraint.get('hex_crc16_modbus_parameter'))
                    if actual_crc is not None:
                        crc=0xFFFF
                        for octet in octets:
                            crc ^= octet
                            for _ in range(8):crc=(crc>>1)^0xA001 if crc&1 else crc>>1
                        outside |= actual_crc!=crc
                    actual_crc8=parameters.get(constraint.get('hex_crc8_maxim_parameter'))
                    if actual_crc8 is not None:
                        count=constraint.get('hex_crc8_prefix_bytes',len(octets))
                        if not isinstance(count,int) or isinstance(count,bool) or count<0 or count>len(octets):
                            outside=True
                        else:
                            # Dallas/Maxim reflected CRC8, initial zero, no XOR.
                            # Explicit prefix avoids accidentally including the
                            # transmitted CRC or using Modbus's CRC16 polynomial.
                            crc8=0
                            for octet in octets[:count]:
                                crc8 ^= octet
                                for _ in range(8):crc8=(crc8>>1)^0x8C if crc8&1 else crc8>>1
                            outside |= type(actual_crc8)is not int or actual_crc8!=crc8
                except ValueError:
                    outside=True
            if isinstance(value,str) and constraint.get('json_gate_schedule'):
                # Normalized scheduling evidence, not a wire/YANG executor.
                schedule_spec=constraint['json_gate_schedule']
                try:
                    def schedule_members(pairs):
                        result={}
                        for key,member in pairs:
                            if key in result:raise ValueError('duplicate schedule member')
                            result[key]=member
                        return result
                    entries=json.loads(value,object_pairs_hook=schedule_members)
                    if not isinstance(entries,list) or not entries:raise ValueError('nonempty gate list required')
                    indexes=set();total=0
                    limit=parameters.get(schedule_spec.get('max_entries_parameter'))
                    if limit is not None:outside |= type(limit)is not int or len(entries)>limit
                    interval_limit=parameters.get(schedule_spec.get('max_interval_parameter'))
                    for entry in entries:
                        if not isinstance(entry,dict) or set(entry)!={'index','operation','mask','interval_ns'}:raise ValueError('gate entry members')
                        index,mask,interval=entry['index'],entry['mask'],entry['interval_ns']
                        if any(type(v)is not int for v in (index,mask,interval)):raise ValueError('integer gate values required')
                        outside |= index<0 or index>0xffffffff or index in indexes
                        outside |= mask<0 or mask>schedule_spec['mask_max']
                        outside |= interval<0 or interval>0xffffffff or entry['operation']not in schedule_spec['commands']
                        if interval_limit is not None:outside |= type(interval_limit)is not int or interval>interval_limit
                        indexes.add(index);total+=interval
                    declared_total=parameters.get(schedule_spec.get('sum_parameter'))
                    if declared_total is not None:outside |= type(declared_total)is not int or declared_total!=total
                except (ValueError,TypeError,KeyError,OverflowError):outside=True
            if isinstance(value,str) and constraint.get('json_array_envelope'):
                # Explicit envelope declarations only; this does not substitute
                # for an action schema or execute a protocol state machine.
                envelope=constraint['json_array_envelope']
                try:
                    def unique_object(pairs):
                        result={}
                        for key,part in pairs:
                            if key in result:raise ValueError('duplicate JSON member')
                            result[key]=part
                        return result
                    def finite_constant(part):raise ValueError('non-finite JSON constant')
                    decoded=json.loads(value,object_pairs_hook=unique_object,parse_constant=finite_constant,parse_float=Decimal)
                    def unicode_strings(part):
                        if isinstance(part,str):part.encode('utf-8',errors='strict')
                        elif isinstance(part,list):
                            for child in part:unicode_strings(child)
                        elif isinstance(part,dict):
                            for key,child in part.items():unicode_strings(key);unicode_strings(child)
                    unicode_strings(decoded)
                    if not isinstance(decoded,list) or len(decoded)!=envelope['length']:
                        outside=True
                    else:
                        types={'integer':int,'text':str,'object':dict,'array':list,'boolean':bool}
                        for part in envelope['fields']:
                            actual=decoded[part['index']]
                            outside |= type(actual)is not types.get(part['type'])
                            if part.get('parameter'):
                                expected=parameters.get(part['parameter'])
                                if expected is not None:outside |= type(actual)is not type(expected) or actual!=expected
                except (ValueError,UnicodeError,RecursionError,IndexError):
                    outside=True
            if isinstance(value,str) and constraint.get('delimited_ascii_sentence_fields'):
                # Declared untagged ASCII sentence integrity only. The profile
                # owns all field references and applicability; a valid XOR does
                # not prove field semantics, source identity or data freshness.
                targets=constraint['delimited_ascii_sentence_fields']
                match=re.fullmatch(r'([$!])([\x20-\x7e]+)\*([0-9A-Fa-f]{2})\r\n',value)
                if match is None:
                    outside=True
                else:
                    start,body,encoded_checksum=match.groups()
                    outside |= any(delimiter in body for delimiter in('$','!','*'))
                    address=body.split(',',1)[0]
                    outside |= re.fullmatch(r'[A-Z0-9]+',address)is None
                    checksum=0
                    for octet in body.encode('ascii'):checksum^=octet
                    outside |= int(encoded_checksum,16)!=checksum
                    for field,decoded in [('start',start),('body',body),('checksum',checksum),('address',address)]:
                        supplied=parameters.get(targets.get(field))
                        if supplied is not None:outside |= supplied!=decoded
                    for field,decoded in [('talker',address[:2]),('formatter',address[2:]),('manufacturer',address[1:])]:
                        supplied=parameters.get(targets.get(field))
                        if supplied is not None:outside |= supplied!=decoded
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
                if constraint.get('forbidden_bit_mask') is not None:
                    outside |= not _safe_finite(value) or value != int(value) or bool(int(value) & constraint['forbidden_bit_mask'])
                for kind in ('equal_expression','minimum_expression','maximum_expression','exclusive_minimum_expression','exclusive_maximum_expression'):
                    if kind not in constraint:
                        continue
                    integer_output = bool(self.profile.get('parameter_schema', {}).get(name, {}).get('integer') or self.profile.get('parameter_schema', {}).get(name, {}).get('type') == 'integer')
                    exact_equality=kind=='equal_expression' and (integer_output or constraint.get('exact_decimal_equality',False))
                    exact_decimal=integer_output or exact_equality or kind in ('exclusive_minimum_expression','exclusive_maximum_expression') or constraint.get('exact_decimal_bounds',False)
                    bound=_parameter_expression(constraint[kind],parameters,exact=exact_decimal)
                    if bound is not None:
                        decimal_value=Fraction(str(value)) if exact_decimal and _safe_finite(value) else value
                        outside |= not _safe_finite(bound) or (decimal_value != bound if exact_equality else not math.isclose(value,bound,rel_tol=1e-9,abs_tol=1e-9)
                            if kind=='equal_expression' else decimal_value < bound if kind=='minimum_expression'
                            else decimal_value <= bound if kind=='exclusive_minimum_expression'
                            else decimal_value >= bound if kind=='exclusive_maximum_expression' else decimal_value > bound)
                terms = constraint.get('equal_sum')
                if terms and all(isinstance(parameters.get(term['parameter']), (int, float)) and not isinstance(parameters[term['parameter']], bool)
                                 and _safe_finite(parameters[term['parameter']]) for term in terms):
                    expected = sum(parameters[term['parameter']] * term.get('factor', 1) for term in terms) + constraint.get('equal_sum_offset', 0)
                    outside |= (value != expected if self.profile.get('parameter_schema', {}).get(name, {}).get('integer') else not math.isclose(value, expected, rel_tol=0, abs_tol=1e-6))
                for ratio_kind in ('equal_ratio','maximum_ratio'):
                    ratio = constraint.get(ratio_kind)
                    if not ratio:
                        continue
                    keys = [ratio[key] for key in ('numerator_parameter','denominator_parameter') if ratio.get(key)]
                    keys += ratio.get('numerator_sum', []) + ratio.get('numerator_product', []) + ratio.get('denominator_sum', []) + ratio.get('denominator_product', [])
                    if all(isinstance(parameters.get(key), (int, float)) and not isinstance(parameters[key], bool)
                           and _safe_finite(parameters[key]) for key in keys):
                        numerator = parameters[ratio['numerator_parameter']] if ratio.get('numerator_parameter') else sum(parameters[key] for key in ratio.get('numerator_sum', [])) + ratio.get('numerator_offset', 0)
                        denominator_base = (parameters[ratio['denominator_parameter']] if ratio.get('denominator_parameter')
                            else sum(parameters[key] for key in ratio.get('denominator_sum', [])) + ratio.get('denominator_offset', 0))
                        try:
                            denominator = denominator_base * math.prod(parameters[key] for key in ratio.get('denominator_product', []))
                            total = numerator * math.prod(parameters[key] for key in ratio.get('numerator_product', [])) * ratio.get('factor', 1)
                            if not _safe_finite(denominator) or denominator <= 0 or not _safe_finite(total):
                                outside = True
                            else:
                                integer_output = bool(self.profile.get('parameter_schema', {}).get(name, {}).get('integer'))
                                bound = Fraction(str(total)) / Fraction(str(denominator)) if integer_output else total / denominator
                                if ratio_kind=='equal_ratio':
                                    outside |= not _safe_finite(bound) or (value != bound if integer_output else not math.isclose(value, bound, rel_tol=1e-9, abs_tol=1e-6))
                                else:
                                    outside |= not _safe_finite(bound) or (value >= bound if constraint.get('exclusive_maximum_ratio') else value > bound)
                        except (OverflowError, ZeroDivisionError):
                            outside = True
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
                    if all(isinstance(part, (int, float)) and not isinstance(part, bool) and _safe_finite(part) for part in actual):
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
    """Registry adapter; concrete framing and scope rules belong to technology owners."""
    def __init__(self, technology_id, profile):
        from importlib import import_module
        self.technology_id = technology_id
        self.profile = profile
        self.implementation = import_module(f'backend.nis.communication.technologies.{technology_id}.timing')

    def transmission_time_us(self, payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None, technology_parameters=None):
        rate_parameters, frame_parameters = self.implementation.prepare_timing_parameters(
            payload_bytes, bitrate, arbitration_bitrate=arbitration_bitrate, data_bitrate=data_bitrate,
            local_timing_evidence=local_timing_evidence, can_fd_brs=can_fd_brs, can_frame_format=can_frame_format,
            can_fd_dlc=can_fd_dlc, can_fd_wire_data_bytes=can_fd_wire_data_bytes)
        if technology_parameters is not None:
            if not isinstance(technology_parameters, dict):
                raise ValueError('Technology parameters must be an object.')
            from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
            normalize = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id
            if any(normalize(technology_parameters[key]) != self.technology_id
                   for key in ('technology','protocol') if technology_parameters.get(key)):
                raise ValueError('Timing parameters belong to another technology.')
            for key,value in technology_parameters.items():
                if key in rate_parameters and rate_parameters[key] != value or key in frame_parameters and frame_parameters[key] != value:
                    raise ValueError(f'{key} conflicts with the explicit timing input.')
            rate_parameters = {**technology_parameters,**rate_parameters}
            frame_parameters = {**technology_parameters,**frame_parameters}
        self.implementation.validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters)
        findings = TechnologyValidator(self.technology_id, self.profile).validate({'parameters': rate_parameters})
        if findings:
            raise ValueError(findings[0].message)
        frame = self.implementation.estimate_frame(self.technology_id, payload_bytes, frame_parameters)
        if frame.is_generic_estimate or not frame.transmission_time_available:
            raise ValueError(f'{self.technology_id}: ausführbares Frame-Modell fehlt.')
        return frame.transmission_time_s * 1_000_000



class TechnologyLoadCalculator:
    def __init__(self, technology_id: str, timing_model: TechnologyTimingModel) -> None:
        self.technology_id = technology_id
        self.timing_model = timing_model

    def calculate(self, *, payload_bytes: int, cycle_ms: float, bitrate: int | None = None,
                  arbitration_bitrate: int | None = None, data_bitrate: int | None = None,
                  local_timing_evidence: dict[str, Any] | None = None,
                  can_fd_brs: bool | None = None, can_frame_format: str | None = None,
                  can_fd_dlc: int | None = None, can_fd_wire_data_bytes: int | None = None,
                  technology_parameters: dict[str, Any] | None = None) -> dict[str, float]:
        if cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive")
        transmission_us = self.timing_model.transmission_time_us(
            payload_bytes, bitrate, arbitration_bitrate=arbitration_bitrate,
            data_bitrate=data_bitrate, local_timing_evidence=local_timing_evidence,
            can_fd_brs=can_fd_brs,can_frame_format=can_frame_format,
            can_fd_dlc=can_fd_dlc,can_fd_wire_data_bytes=can_fd_wire_data_bytes,
            technology_parameters=technology_parameters)
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
