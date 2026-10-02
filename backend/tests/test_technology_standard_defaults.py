"""Catalog-wide operating proposals and adversarial transport isolation."""
from copy import deepcopy

import pytest

from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.engineering.agent_tools.wizard_generation import _parameter_defaults, _rate_review_candidate
from backend.engineering.capacity.calculators import confirmed_serial_evidence, serial_evidence_missing_fields
from backend.engineering.capacity.dimensioning import local_evidence_proposal
from backend.engineering.capacity.service import parameters_for_protocol


ALIASES = {'bitrate': 'bitrate_bps', 'arbitration_bitrate': 'nominal_bitrate_bps', 'data_bitrate': 'data_bitrate_bps'}


def test_every_registered_profile_proposal_is_valid_consistent_and_unconfirmed():
    profiles = registry.profiles()
    catalog = {p['id']: p for d in SimulationService().catalog()['domains'] for p in d['technologies']}
    assert set(catalog) == {p['id'] for p in profiles}
    for profile in profiles:
        key = profile['id']
        review = registry.parameter_defaults_review(key)
        schema = catalog[key]['parameter_schema']
        assert review['status'] == 'REVIEW_REQUIRED'
        rates = {ALIASES[f['key']]: f['default'] for f in schema if f['key'] in ALIASES and 'default' in f}
        assert rates == review['values'], key
        if rates:
            result = registry.validate_parameters(key, rates)
            assert result['status'] in {'VALID', 'UNVERIFIED'}, key
            if result['status'] == 'UNVERIFIED':
                # A sound link-rate proposal does not fill mandatory evidence
                # for an application profile in the explicitly declared stack.
                assert result['findings'] and all(f['code'] == 'TECHNOLOGY_PARAMETER_MISSING' for f in result['findings']), key
        generated = _parameter_defaults(key)
        for field in schema:
            if 'default' not in field:
                continue
            value = field['default']
            assert generated[field['key']] == value, (key, field['key'])
            if field['type'] == 'number':
                assert not isinstance(value, bool)
                assert field.get('min') is None or value >= field['min'], (key, field['key'])
                assert field.get('max') is None or value <= field['max'], (key, field['key'])
            elif field['type'] == 'select':
                assert value in field['options'], (key, field['key'])
            elif field['type'] == 'boolean':
                assert type(value) is bool
        # This is a proposal audit, not complete device/electrical verification.
        assert registry.validate_parameters(key, {})['required_parameter_completeness'] == 'UNVERIFIED'


def test_every_distinct_bus_pair_rejects_foreign_confirmed_rate():
    profiles = registry.profiles()
    for source in profiles:
        review = registry.parameter_defaults_review(source['id'])
        if not review['values']:
            continue
        aliases = {value: key for key, value in ALIASES.items()}
        values = {aliases[k]: v for k, v in review['values'].items()}
        for target in profiles:
            if target['id'] == source['id']:
                continue
            parameters = {'technology': source['id'], **values, 'networks': [
                {'id': 'same-id', 'technology': source['id'], **values}]}
            original = deepcopy(parameters)
            resolved = parameters_for_protocol(target['id'], parameters, network_id='same-id', confirmed_parameters=parameters)
            assert not resolved['_rate_evidenced'], (source['id'], target['id'])
            assert not set(ALIASES).intersection(resolved), (source['id'], target['id'])
            assert parameters == original


def device_evidence():
    return {'technology': 'I2C', 'confirmed': True, 'source': 'Reviewed device datasheet',
            'master_node_id': 'controller', 'slave_address': '0x20', 'address_bits': 7,
            'i2c_mode': 'STANDARD', 'transfer_direction': 'READ', 'start_stop_bound_us': 8,
            'clock_stretch_limit_us': 5, 'multi_master': False,
            'transfer_bits_bound': 100, 'bitrate_bps': 100_000}


def test_i2c_standard_is_shared_but_does_not_invent_device_evidence():
    assert _rate_review_candidate('i2c')[0] == 100_000
    assert _parameter_defaults('i2c')['bitrate'] == 100_000
    proposal = local_evidence_proposal('I2C', [{'stream_id': 'one'}])
    assert next(f for f in proposal['fields'] if f['key'].endswith(':bitrate_bps'))['candidate'] == 100_000
    assert proposal['hardware_profile_status'] == 'UNCONFIRMED'
    missing = serial_evidence_missing_fields('I2C', {'bitrate': 100_000})
    assert 'local_timing_evidence.slave_address' in missing
    assert 'local_timing_evidence.master_node_id' in missing
    assert 'local_timing_evidence.clock_stretch_limit_us' in missing
    assert confirmed_serial_evidence('I2C', {'bitrate': 100_000}) is None
    assert _rate_review_candidate('spi')[0] is None
    assert 'bitrate' not in _parameter_defaults('spi')


def test_port_capability_evidence_is_used_and_rejects_wrong_bus_and_clock():
    p = {'technology': 'i2c', 'bitrate': 100_000,'i2c_mode':'STANDARD',
         'i2c_profile':'UM10204_STANDARD_LIMITS','i2c_endpoint_role':'CONTROLLER',
         'i2c_controller_id':'controller','i2c_device_source':'actual device datasheet',
         'i2c_binding_source':'actual controller target port binding',
         'i2c_physical_source':'actual voltage and capacitance evidence',
         'i2c_schedule_source':'actual bounded transactions'}
    port = {'technology': 'I2C', 'capabilities': {'local_timing_evidence': device_evidence()}}
    resolved = parameters_for_protocol('I2C', p, port, confirmed_parameters=p)
    assert resolved['_rate_evidenced'] and resolved['bitrate'] == 100_000
    assert serial_evidence_missing_fields('I2C', resolved, 8) == []
    wrong = deepcopy(port); wrong['capabilities']['local_timing_evidence']['technology'] = 'SPI'
    assert not parameters_for_protocol('I2C', p, wrong, confirmed_parameters=p)['_rate_evidenced']
    wrong = deepcopy(port); wrong['capabilities']['local_timing_evidence'].update(bitrate_bps=400_000, i2c_mode='FAST')
    assert not parameters_for_protocol('I2C', p, wrong, confirmed_parameters=p)['_rate_evidenced']


def test_single_master_editor_null_arbitration_is_optional_but_multi_master_requires_it():
    evidence = {**device_evidence(), 'arbitration_bound_us': None}
    assert confirmed_serial_evidence('I2C', {'local_timing_evidence': evidence}, 8) == evidence
    evidence['multi_master'] = True
    assert confirmed_serial_evidence('I2C', {'local_timing_evidence': evidence}, 8) is None
    assert 'local_timing_evidence.arbitration_bound_us' in serial_evidence_missing_fields('I2C', {'local_timing_evidence': evidence}, 8)
    evidence['arbitration_bound_us'] = 0
    assert confirmed_serial_evidence('I2C', {'local_timing_evidence': evidence}, 8) == evidence


@pytest.mark.parametrize('technology,value', [('can', 1_000_001), ('modbus_rtu', 0), ('nmea2000', 100_000_000), ('ethernet', 250_000)])
def test_matching_identity_cannot_authorize_out_of_profile_rate(technology, value):
    p = {'technology': technology, 'bitrate': value}
    assert registry.validate_parameters(technology, {'bitrate_bps': value})['status'] == 'INVALID'
    resolved = parameters_for_protocol(technology, p, confirmed_parameters=p)
    assert not resolved['_rate_evidenced'] and 'bitrate' not in resolved


def test_layered_can_form_has_no_ethernet_label_or_phy_parameters():
    for technology in ['uds', 'xcp', 'obd2', 'nmea2000']:
        fields = SimulationService._parameter_schema(technology, registry.profile(technology))
        assert 'Ethernet' not in next(f for f in fields if f['key'] == 'bitrate')['label']
        assert not {'duplex', 'mtu_bytes', 'vlan_id'}.intersection(f['key'] for f in fields)
    for technology in ['ros2']:
        fields = SimulationService._parameter_schema(technology, registry.profile(technology))
        assert {'ros_middleware', 'ros_rmw', 'ros_transport'} <= {f['key'] for f in fields}
        assert not {'duplex', 'mtu_bytes', 'vlan_id', 'bitrate'}.intersection(f['key'] for f in fields)
    pn_fields = SimulationService._parameter_schema('profinet', registry.profile('profinet'))
    pn_keys = {f['key'] for f in pn_fields}
    assert {'pn_duplex', 'pn_vlan_id', 'pn_csdu_bytes'} <= pn_keys
    assert not {'duplex', 'mtu_bytes', 'vlan_id'}.intersection(pn_keys)
    for technology in ['dds','modbus_tcp']:
        fields = SimulationService._parameter_schema(technology, registry.profile(technology))
        assert not {'bitrate', 'duplex', 'mtu_bytes', 'vlan_id'}.intersection(f['key'] for f in fields)


def test_changed_global_rate_does_not_reuse_old_confirmation():
    p = {'technology': 'lin', 'bitrate': 9600, 'defaults_source': 'technology-registry',
         'parameter_provenance': {'bitrate': {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': 19200}}}
    assert not parameters_for_protocol('LIN', p, confirmed_parameters=p)['_rate_evidenced']


def test_saved_can_fd_nominal_alias_survives_strict_phase_validation():
    p = {'technology': 'can_fd', 'bitrate': 500_000, 'data_bitrate': 2_000_000}
    resolved = parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)
    assert resolved['_rate_evidenced'] and resolved['bitrate'] == 500_000
    assert resolved['data_bitrate'] == 2_000_000
    p['arbitration_bitrate'] = 250_000
    assert parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)['_rate_evidenced']
    p.pop('data_bitrate')
    assert not parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)['_rate_evidenced']
