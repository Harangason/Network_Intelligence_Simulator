"""Projection over canonical package-owned technology definitions."""
from copy import deepcopy
from typing import Any
from importlib import import_module
DIRECT_IO_TECHNOLOGIES = frozenset({'gpio', 'pwm', 'adc', 'dac'})
PARAMETER_UI_ALIASES = {'bitrate_bps': 'bitrate', 'nominal_bitrate_bps': 'arbitration_bitrate', 'data_bitrate_bps': 'data_bitrate'}
PARAMETER_CORE_ALIASES = {'bitrate': 'bitrate_bps', 'arbitration_bitrate': 'nominal_bitrate_bps', 'data_bitrate': 'data_bitrate_bps'}
RESERVED_PARAMETER_NAMES = frozenset({'arbitration_bitrate',
           'bit_error_rate',
           'bitrate',
           'burst_factor',
           'burst_window_ms',
           'clock_drift_ppm',
           'clock_offset_ms',
           'corruption_probability',
           'critical_threshold',
           'cycle_ms',
           'data_bitrate',
           'deadline_ms',
           'distributed_clock_cycle_ms',
           'dropout_probability',
           'duplex',
           'duplicate_probability',
           'durability',
           'duration_s',
           'frame_loss_probability',
           'freshness_ms',
           'gateway_delay_ms',
           'gateway_input_buffer',
           'gateway_maximum_messages_s',
           'gateway_maximum_routes',
           'gateway_maximum_throughput',
           'gateway_output_buffer',
           'gateway_queue_delay_ms',
           'history_depth',
           'history_kind',
           'jitter_ms',
           'lifespan_ms',
           'liveliness',
           'max_events',
           'maximum_latency_ms',
           'maximum_sync_error_ms',
           'minimum_cycle_time_ms',
           'mtu_bytes',
           'overload_threshold',
           'packet_loss_probability',
           'payload_bytes',
           'peak_factor',
           'propagation_delay_ms',
           'protocol_conversion_delay_ms',
           'qos_priority',
           'queue_policy',
           'queue_size',
           'rate_limit_bit_s',
           'reliability_mode',
           'reordering_probability',
           'required_reliability',
           'reserved_bandwidth_percent',
           'retransmission_delay_ms',
           'retransmission_enabled',
           'retransmission_rate',
           'retry_limit',
           'sample_point_percent',
           'seed',
           'source_processing_delay_ms',
           'sync_interval_ms',
           'sync_method',
           'sync_precision_ms',
           'target_bus_load_percent',
           'target_processing_delay_ms',
           'timeout_ms',
           'traffic_class',
           'vlan_id',
           'warning_threshold'})

TECHNOLOGY_IDS = ('ethernet', 'ip', 'udp', 'tcp', 'can', 'can_fd', 'can_xl', 'lin', 'flexray', 'most', 'canopen', 'j1939', 'isobus', 'uds', 'xcp', 'ccp', 'someip', 'someip_sd', 'doip', 'obd2', 'avb', 'tsn', 'profinet', 'ethercat', 'ethernet_ip', 'modbus_tcp', 'modbus_rtu', 'modbus_ascii', 'profibus_dp', 'profibus_pa', 'devicenet', 'interbus', 'cc_link', 'cc_link_ie', 'sercos_iii', 'powerlink', 'io_link', 'io_link_wireless', 'opc_ua', 'opc_ua_pubsub', 'mqtt', 'sparkplug_b', 'dds', 'ros2', 'arinc429', 'afdx', 'mil_std_1553', 'can_aerospace', 'spacewire', 'tte', 'mvb', 'wtb', 'etb', 'trdp', 'nmea0183', 'nmea2000', 'iec61162', 'bacnet_ip', 'bacnet_mstp', 'bacnet_sc', 'knx_tp', 'knx_ip', 'knx_rf', 'lonworks', 'dali', 'm_bus', 'wireless_m_bus', 'iec61850', 'mms', 'goose', 'sampled_values', 'dnp3', 'iec60870_5_101', 'iec60870_5_104', 'sunspec_modbus', 'ocpp', 'hart', 'wirelesshart', 'foundation_fieldbus_h1', 'i2c', 'i3c', 'spi', 'uart', 'rs232', 'rs422', 'rs485', 'one_wire', 'usb', 'pcie', 'mipi_csi2', 'mipi_dsi', 'lvds', 'gpio', 'pwm', 'adc', 'dac', 'mqtt_sn', 'coap', 'http', 'websocket', 'amqp', 'wifi', 'bluetooth_le', 'zigbee', 'thread', 'matter', 'lorawan', 'lte_m', 'nb_iot', '5g', 'uwb', 'nfc', 'rfid', 'profisafe', 'cip_safety', 'fsoe', 'opensafety', 'generic_serial', 'generic_can', 'generic_ethernet', 'custom_udp', 'custom_tcp', 'custom_binary', 'custom_text', 'custom_protocol')

from json import loads
from pathlib import Path
from backend.nis.communication.technologies.can_fd.constants import CAN_FD_DATA_LENGTHS
from backend.nis.communication.technologies.dds.policies import DDS_POLICY_ENTITIES

def technology_identity(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'identity.json'
    return loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def technology_review(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'review.json'
    review = loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    profile_path = path.with_name('profile.json')
    profile = loads(profile_path.read_text(encoding='utf-8')) if profile_path.is_file() else {}
    if profile.get('parameter_proposals'):
        review['rate_proposal'] = profile['parameter_proposals']
    return review

REVIEW_RATE_PROPOSALS = {key: review['rate_proposal'] for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('legacy_rate_projection')}
LOCAL_EVIDENCE_FIELDS = {key.upper(): tuple(map(tuple, review['local_evidence_fields']))
                         for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('local_evidence_fields')}

def technology_definitions():
    return [deepcopy(import_module(f"backend.nis.communication.technologies.{key}.definition").PROFILE)
            for key in TECHNOLOGY_IDS]

def parameter_value_role(name: str, spec: dict[str, Any]) -> str:
    """Identity and evidence references cannot be invented as scenario values."""
    if spec.get('value_role'):
        return spec['value_role']
    if (spec.get('type') == 'boolean' or spec.get('boolean')) and name.endswith(
            ('_confirmed', '_verified', '_proven', '_validated')):
        return 'EVIDENCE'
    if spec.get('type') in {'text', 'string'} or not spec.get('type') and not spec.get('numeric') and not spec.get('boolean') and not spec.get('options'):
        if name.endswith('_source') or name.endswith('_revision') or name == 'revision':
            return 'EVIDENCE'
        if name.endswith(('_node_id', '_ref')):
            return 'REFERENCE'
    return 'CONFIGURATION'


def simulation_parameter_proposal(technology_id: str, profile: dict[str, Any], name: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Complete editable scenario examples; never actual device evidence.

    Use only this registered field's choices/bounds and its owner's preset.
    Keep original default/UNKNOWN declarations and physical gates intact.
    """
    preset = (profile.get('simulation_defaults') or {}).get('values', {})
    value = preset.get(name, spec.get('default'))
    basis = ('PROFILE_SIMULATION_PRESET' if name in preset else
             'REGISTERED_PARAMETER_DEFAULT' if value is not None else 'SCHEMA_SIMULATION_EXAMPLE')
    comparison = ((profile.get('simulation_defaults') or {}).get('comparison_values') or {}).get(name) or spec.get('simulation_comparison') or {}
    if name in preset and comparison.get('technology') == technology_id and comparison.get('value') == value:
        basis = 'COMPARABLE_PROTOCOL_SCENARIO'
    if value is None and comparison.get('technology') == technology_id and comparison.get('value') is not None:
        value, basis = comparison['value'], 'COMPARABLE_PROTOCOL_SCENARIO'
    model = profile.get('rate_model') or {}
    rate_fields = model.get('fields') or (profile.get('simulation_defaults') or {}).get('rate_fields') or []
    registered_rate = profile.get('default_bitrate')
    if name not in preset and name in rate_fields and len(rate_fields) == 1 and isinstance(registered_rate, (int, float)) and registered_rate > 0:
        allowed = model.get('allowed_bps') or []
        if (not allowed or registered_rate in allowed) and registered_rate >= model.get('minimum_bps', 0) and registered_rate <= model.get('maximum_bps', float('inf')):
            value, basis = registered_rate, 'REGISTERED_PROFILE_RATE'
    role = parameter_value_role(name, spec)
    if value is None and role != 'CONFIGURATION':
        return {'value': None, 'basis': 'EXPLICIT_REFERENCE_REQUIRED', 'source': 'NIS_SIMULATION_ASSUMPTION',
                'status': 'UNKNOWN', 'technology': technology_id, 'hardware_evidence': False}
    if value is None:
        kind = spec.get('type') or ('number' if spec.get('numeric') else 'boolean' if spec.get('boolean') else 'select' if spec.get('options') else 'text')
        if kind in {'number', 'integer'}:
            minimum = spec.get('min', spec.get('minimum', 0))
            maximum = spec.get('max', spec.get('maximum'))
            value = max(0, minimum if minimum is not None else 0)
            if maximum is not None:
                value = min(value, maximum)
            if spec.get('allowed_values'):
                value = spec['allowed_values'][0]
            if spec.get('multiple_of'):
                from math import ceil
                value = ceil(value / spec['multiple_of']) * spec['multiple_of']
            if spec.get('integer') or kind == 'integer':
                value = int(value)
        elif kind == 'boolean':
            value = spec['allowed_values'][0] if spec.get('allowed_values') else False
        elif kind == 'select':
            choices = spec.get('options') or []
            value = choices[0] if choices else 'SIMULATION_UNSPECIFIED'
        else:
            formats = {'IP_ADDRESS': '192.0.2.1', 'IP_NETWORK': '192.0.2.0/24',
                       'WSS_URI': 'wss://simulation.invalid', 'ABSOLUTE_URI': 'https://simulation.invalid'}
            value = formats.get(spec.get('format'), f'simulation:{technology_id}:{name}')
            if spec.get('pattern'):
                import re
                # Schema-constrained examples, including unicast/multicast
                # addresses, UUIDs, object identifiers and encoded bytes.
                examples = ['0', 'GET', 'simulation_context', '1.3.6.1',
                            '02:00:00:00:00:01', '01:00:00:00:00:01',
                            '00000000-0000-4000-8000-000000000001']
                examples.extend('0' * length for length in range(2, 81))
                value = next((item for item in examples if re.fullmatch(spec['pattern'], item)), value)
    return {'value': value, 'basis': basis, 'source': 'NIS_SIMULATION_ASSUMPTION',
            'status': 'ASSUMED', 'technology': technology_id, 'hardware_evidence': False,
            'reference_source': comparison.get('source') if basis == 'COMPARABLE_PROTOCOL_SCENARIO' else spec.get('source') or (profile.get('simulation_defaults') or {}).get('source'),
            'reference_revision': comparison.get('source_revision') if basis == 'COMPARABLE_PROTOCOL_SCENARIO' else spec.get('source_revision')}


def simulation_parameter_values(technology_id: str, profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve the owner's complete scenario, including dependent native modes.

    Presets are explicit scenario choices, not physical lower bounds. Conditional
    proposals apply only to fields without such a choice. Device facts stay ASSUMED.
    """
    schema = profile.get('parameter_schema') or {}
    proposals = {name: simulation_parameter_proposal(technology_id, profile, name, spec)
                 for name, spec in schema.items()}
    preset = (profile.get('simulation_defaults') or {}).get('values') or {}
    for _ in range(len(schema)):
        changed = False
        for name, spec in schema.items():
            if name in preset:
                continue
            matches = [item for item in spec.get('conditional_defaults') or []
                       if all(proposals.get(key, {}).get('value') == value for key, value in item['when'].items())]
            if matches and all(item['value'] == matches[0]['value'] for item in matches):
                item = matches[0]
                if proposals[name]['value'] != item['value']:
                    proposals[name] = {**proposals[name], 'value': item['value'],
                        'basis': 'CONDITIONAL_PROFILE_PROPOSAL', 'reference_source': item.get('source'),
                        'reference_revision': item.get('source_revision')}
                    changed = True
        if not changed:
            break
    return _constrained_simulation_proposals(technology_id, profile, proposals, set(preset))


def _constrained_simulation_proposals(technology_id, profile, proposals, fixed):
    """Derive editable examples from the same rules used by native validation.

    This is scenario construction only. Never alter explicit preset choices or
    promote confirmation flags. Unresolved codecs and physical proof remain
    subject to the unchanged strict validator.
    """
    import math
    from backend.nis.communication.core.components import _condition_equal, _parameter_expression
    schema = profile.get('parameter_schema') or {}
    values = {key: proposal['value'] for key, proposal in proposals.items()}

    def numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    for _ in range(12):
        changed = False
        for rule in profile.get('parameter_constraints') or []:
            key = rule['parameter']
            if key not in values or key in fixed or 'confirmed' in key.lower():
                continue
            if not all(_condition_equal(values.get(k), v) for k, v in rule.get('when', {}).items()):
                continue
            if any(_condition_equal(values.get(k), v) for k, v in rule.get('when_not', {}).items()):
                continue
            if not all(values.get(k) not in (None, '') for k in rule.get('when_present', [])):
                continue
            if not all(numeric(values.get(k)) and values[k] > 0 for k in rule.get('when_positive', [])):
                continue
            if not all(numeric(values.get(k)) and low <= values[k] <= high for k, (low, high) in rule.get('when_ranges', {}).items()):
                continue
            if not all(numeric(values.get(k)) and low <= values[k] and (high is None or values[k] < high) for k, (low, high) in rule.get('when_half_open_ranges', {}).items()):
                continue
            if not all(numeric(values.get(k)) and values[k] > bound for k, bound in rule.get('when_greater_than', {}).items()):
                continue
            value = values[key]
            allowed = rule.get('allowed')
            if allowed and value not in allowed and allowed[0] != '':
                value = allowed[0]
            reference = values.get(rule.get('equal_parameter'))
            if reference is not None:
                offset = rule.get('equal_parameter_offset', 0)
                if not offset or numeric(reference):
                    value = reference + offset if offset else reference
            if rule.get('equals_parameters_boolean'):
                left, right = (values.get(k) for k in rule['equals_parameters_boolean'])
                if left is not None and right is not None:
                    value = _condition_equal(left, right)
            if numeric(value):
                spec = schema[key]
                integer = spec.get('integer') or spec.get('type') == 'integer'
                step = 1 if integer else 1e-6
                for kind in ('equal_expression', 'minimum_expression', 'maximum_expression', 'exclusive_minimum_expression', 'exclusive_maximum_expression'):
                    if kind in rule:
                        bound = _parameter_expression(rule[kind], values, exact=bool(integer))
                        if bound is not None and math.isfinite(bound):
                            value = bound if kind == 'equal_expression' else max(value, bound + (step if kind.startswith('exclusive_minimum') else 0)) if 'minimum' in kind else min(value, bound - (step if kind.startswith('exclusive_maximum') else 0))
                terms = rule.get('equal_sum')
                if terms and all(numeric(values.get(term['parameter'])) for term in terms):
                    value = sum(values[term['parameter']] * term.get('factor', 1) for term in terms) + rule.get('equal_sum_offset', 0)
                ratio = rule.get('equal_ratio')
                if ratio:
                    numerator = values.get(ratio['numerator_parameter']) if ratio.get('numerator_parameter') else sum(values.get(k, 0) for k in ratio.get('numerator_sum', [])) + ratio.get('numerator_offset', 0)
                    denominator = values.get(ratio['denominator_parameter']) if ratio.get('denominator_parameter') else sum(values.get(k, 0) for k in ratio.get('denominator_sum', [])) + ratio.get('denominator_offset', 0)
                    parts = [values.get(k) for k in ratio.get('numerator_product', []) + ratio.get('denominator_product', [])]
                    if numeric(numerator) and numeric(denominator) and all(numeric(part) for part in parts):
                        denominator *= math.prod(values[k] for k in ratio.get('denominator_product', []))
                        if denominator > 0:
                            value = numerator * math.prod(values[k] for k in ratio.get('numerator_product', [])) * ratio.get('factor', 1) / denominator
                difference = rule.get('difference_parameters')
                if difference and all(numeric(values.get(k)) for k in difference):
                    value = values[difference[0]] - values[difference[1]]
                minimum = rule.get('minimum')
                maximum = rule.get('maximum')
                lower = values.get(rule.get('minimum_parameter'))
                upper = values.get(rule.get('maximum_parameter'))
                if numeric(lower):
                    minimum = max(minimum, lower) if minimum is not None else lower
                if numeric(upper) and all(numeric(values.get(k)) for k in rule.get('maximum_subtract_parameters', [])):
                    upper = upper * rule.get('maximum_factor', 1) + rule.get('maximum_offset', 0) - sum(values[k] for k in rule.get('maximum_subtract_parameters', []))
                    maximum = min(maximum, upper) if maximum is not None else upper
                if rule.get('exclusive_minimum') is not None:
                    bound = rule['exclusive_minimum'] + step
                    minimum = max(minimum, bound) if minimum is not None else bound
                if rule.get('exclusive_maximum') is not None:
                    bound = rule['exclusive_maximum'] - step
                    maximum = min(maximum, bound) if maximum is not None else bound
                if minimum is not None:
                    value = max(value, math.ceil(minimum) if integer else minimum)
                if maximum is not None:
                    value = min(value, math.floor(maximum) if integer else maximum)
                if rule.get('multiple_of'):
                    value = math.ceil(value / rule['multiple_of']) * rule['multiple_of']
                if not math.isfinite(value) or integer and value != int(value):
                    continue
                value = int(value) if integer else float(value)
                if spec.get('min') is not None and value < spec['min'] or spec.get('max') is not None and value > spec['max']:
                    continue
            if not _condition_equal(value, values[key]):
                values[key] = value
                proposals[key] = {**proposals[key], 'value': value,
                    'basis': 'PROFILE_RULE_SIMULATION_PROPOSAL', 'reference_source': rule.get('source'),
                    'reference_revision': rule.get('source_revision')}
                changed = True
        if not changed:
            break
    for rule in profile.get('parameter_constraints') or []:
        if rule.get('allowed') in ([], ['']) and all(_condition_equal(values.get(k), v) for k, v in rule.get('when', {}).items()) and not any(k.startswith('when_') for k in rule):
            key = rule['parameter']
            if key in proposals:
                proposals[key]['applicable'] = False
    return proposals


def _parameter_defaults_review(technology_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """One review policy for every consumer; suggestions are never evidence."""
    model = profile.get("rate_model") or {}
    proposal = profile.get("parameter_proposals") or {}
    values, basis = {}, "NOT_APPLICABLE"
    if model.get("type") == "MULTI_PHASE_BITRATE":
        values = dict(model.get("defaults_bps") or {})
        basis = "PROFILE_PHASE_DEFAULTS" if values else "DEVICE_DEPENDENT"
    elif model.get("fields"):
        basis = "DEVICE_DEPENDENT"
        if model.get("type") != "DEVICE_DEPENDENT_CLOCK" and proposal.get('kind') != 'VARIANT_DEPENDENT':
            options = proposal.get("options") or []
            modes = [option["maximum"] for option in options if option.get("maximum", 0) > 0]
            allowed = model.get("allowed_bps") or model.get("typical_bps") or []
            if model.get("fixed_bps"):
                value, basis = model["fixed_bps"], "FIXED_PROFILE_RATE"
            elif proposal.get('default_bps'):
                value, basis = proposal['default_bps'], proposal.get('default_basis', 'LITERATURE_DEFAULT')
            elif modes:
                value, basis = min(modes), "STANDARD_MODE"
            elif allowed:
                value, basis = min(allowed), "LOWEST_PROFILE_MODE"
            elif model.get("minimum_bps", 0) > 1:
                value, basis = model["minimum_bps"], "PROFILE_MINIMUM"
            else:
                value, basis = proposal.get("candidate"), "CATALOG_REVIEW_CANDIDATE"
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                values = {field: value for field in model["fields"]}
            else:
                basis = "DEVICE_DEPENDENT"
    return {"technology": technology_id, "rate_profile": profile["id"],
            "values": values, "basis": basis, "status": "REVIEW_REQUIRED",
            "source": proposal.get("source") or f"TechnologyProfile:{profile['id']}",
            "source_revision": proposal.get("source_revision")}

from backend.nis.industries.models import MODEL_TYPES
