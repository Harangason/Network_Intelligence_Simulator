"""Cross-consumer regressions: exact protocol values and transport isolation."""
from copy import deepcopy

import pytest

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.core.components import TechnologyValidator
from backend.nis.agent.tools.project_draft import parse_requirement


@pytest.mark.parametrize('profile', registry.profiles(), ids=lambda p: p['id'])
def test_exported_schema_preserves_actual_wide_integer_bounds(profile):
    fields = {f['key']: f for f in registry.parameter_fields(profile['id'])}
    for name, spec in profile.get('parameter_schema', {}).items():
        if not spec.get('label') or not spec.get('integer'):
            continue
        maximum = spec.get('max', spec.get('maximum'))
        if not isinstance(maximum, int) or maximum <= 2**53 - 1:
            continue
        assert fields[name]['numeric_encoding'] == 'DECIMAL_STRING'
        assert fields[name]['decimal_max'] == str(maximum)
        assert 'max' not in fields[name]
        normalized = registry.normalize_parameters(profile['id'], {name: str(maximum)})
        assert normalized[name] == maximum
        assert isinstance(normalized[name], int)


def test_wide_integer_relationship_rejects_one_bit_difference_without_float_tolerance():
    spec = {'type': 'number', 'integer': True, 'min': 0, 'max': 2**64 - 1}
    profile = {'parameter_schema': {'total': spec, 'part': spec},
               'parameter_constraints': [{'parameter': 'total', 'equal_expression': {'sum': ['part', 1]}}]}
    validator = TechnologyValidator('actual_counter', profile)
    exact = 2**63 + 37
    assert not validator.validate({'parameters': {'total': str(exact + 1), 'part': str(exact)}})
    assert any(f.code == 'TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH' for f in
               validator.validate({'parameters': {'total': str(exact), 'part': str(exact)}}))
    assert any(f.code == 'TECHNOLOGY_PARAMETER_TYPE_MISMATCH' for f in
               validator.validate({'parameters': {'total': float(exact)}}))
    assert any(f.code == 'TECHNOLOGY_PARAMETER_OUT_OF_RANGE' for f in
               validator.validate({'parameters': {'total': str(2**64)}}))


def test_decimal_wire_support_does_not_coerce_other_numeric_or_boolean_fields():
    validator = TechnologyValidator('strict', {'parameter_schema': {
        'channel': {'type': 'number', 'integer': True, 'max': 255}, 'enabled': {'type': 'boolean'}}})
    issues = validator.validate({'parameters': {'channel': '12', 'enabled': 'false'}})
    assert len([f for f in issues if f.code == 'TECHNOLOGY_PARAMETER_TYPE_MISMATCH']) == 2


def test_application_without_explicit_ip_parameters_does_not_require_an_ethernet_rate():
    for technology in ('coap', 'mqtt', 'http', 'opc_ua'):
        if 'ip' not in registry.profile(technology).get('default_stack', []):
            continue
        result = registry.validate_parameters(technology, {})
        assert 'ip' in result['unverified_stack_layers']
        assert result['stack_parameter_completeness'] == 'UNVERIFIED'
        assert not any(f.get('parameter') == 'bitrate_bps' for f in result['findings'])


def test_exact_proportional_closing_requirement_is_concrete_but_not_commissioned():
    requirement = 'ein Aktor zum proportional schließen eines Ventil'
    draft = parse_requirement(requirement, 'custom')
    actuators = [d for d in draft['devices'] if d['role'] == 'ACTUATOR']
    assert len(actuators) == 1
    assert actuators[0]['name'] == 'Ventilaktor1'
    assert actuators[0]['known_kind'] is True
    assert actuators[0]['source'] == requirement
    assert actuators[0]['technology'] is None
    assert not any(i['code'] == 'DEVICE_KIND_REQUIRED' for i in draft['issues'])
    assert any(i['code'] == 'CONNECTION_REQUIRED' for i in draft['issues'])


@pytest.mark.parametrize('technology', ['m_bus', 'matter', 'mil_std_1553', 'zigbee', 'wirelesshart'])
def test_reviewed_semantics_do_not_install_a_fake_physical_capacity_executor(technology):
    profile = registry.profile(technology)
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    try:
        assert registry.resolve_stack(profile['default_stack'])['timing_model'] is None
    except LookupError:
        assert profile['implementation_status'] in ('PLANNED', 'NOT_SUPPORTED')
    result = registry.validate_physical_realization({'technology_id': technology})
    assert result['status'] != 'VALID'


def test_nmea2000_rejects_ethernet_clock_even_when_ethernet_parameters_exist_elsewhere():
    result = registry.validate_parameters('nmea2000', {'bitrate': 100_000_000})
    assert result['findings']
    assert result['status'] != 'VALID'
    assert registry.parameter_defaults_review('nmea2000')['values']['bitrate_bps'] == 250_000


@pytest.mark.parametrize('rule', [
    {'parameter':'payload_bytes','minimum_ratio':1},
    {'parameter':'payload_bytes','when':{'mode':['STANDARD']},'allowed':[1]},
    {'parameter':'payload_bytes','equal_expression':{'divide':[1,2]}},
    {'parameter':'payload_bytes','equal_expression':{'subtract':[1]}},
])
def test_unimplemented_rule_cannot_be_registered_and_silently_ignored(rule):
    from backend.nis.communication.registry import TechnologyRegistry
    isolated = TechnologyRegistry()
    profile = deepcopy(registry.profile('can'))
    profile['parameter_constraints'] = [rule]
    with pytest.raises(ValueError):
        isolated.register_profile('can',profile)
    assert not isolated.profiles()
