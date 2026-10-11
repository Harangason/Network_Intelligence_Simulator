"""Complete scenario defaults never become actual hardware evidence."""
from copy import deepcopy
import re

import pytest

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.simulation.service import SimulationService
from backend.nis.workflow.services.service import WorkflowStatusService


def test_every_operational_parameter_has_a_typed_start_value_and_references_are_not_invented():
    profiles = registry.profiles()
    assert len(profiles) == 125
    for profile in profiles:
        for field in registry.parameter_fields(profile['id']):
            value = field['simulation_default']
            proof = field['simulation_default_provenance']
            if field['value_role'] != 'CONFIGURATION' and value is None:
                assert proof['status'] == 'UNKNOWN'
                assert proof['basis'] == 'EXPLICIT_REFERENCE_REQUIRED'
                assert proof['hardware_evidence'] is False
                continue
            assert value is not None and value != '', (profile['id'], field['key'])
            assert proof['technology'] == profile['id']
            assert proof['source'] == 'NIS_SIMULATION_ASSUMPTION'
            assert proof['hardware_evidence'] is False
            if field.get('numeric_encoding') == 'DECIMAL_STRING':
                integer = int(value)
                assert int(field['decimal_min']) <= integer <= int(field['decimal_max'])
            elif field['type'] == 'number':
                assert isinstance(value, (int, float)) and not isinstance(value, bool)
                assert field.get('min') is None or value >= field['min']
                assert field.get('max') is None or value <= field['max']
            elif field['type'] == 'boolean':
                assert type(value) is bool
            elif field['type'] == 'select':
                assert value in field['options']
            else:
                assert isinstance(value, str)
                if field.get('pattern'):
                    assert re.fullmatch(field['pattern'], value), (profile['id'], field['key'], value)


@pytest.mark.parametrize('technology', ['can', 'can_fd'])
def test_can_starter_is_coherent_without_changing_unknown_device_defaults(technology):
    profile = registry.profile(technology)
    values = profile['simulation_defaults']['values']
    result = registry.validate_parameters(technology, values)
    assert result['status'] == 'VALID', result
    assert values['can_clock_hz'] / (values['can_prescaler'] * (1 + values['can_tseg1_tq'] + values['can_tseg2_tq'])) == 500000
    assert registry.validate_parameters(technology, {})['status'] == 'UNVERIFIED'
    assert 'default' not in profile['parameter_schema']['can_clock_hz']


def test_catalog_device_fields_also_load_proposals_without_confirming_evidence():
    catalog = SimulationService().catalog()
    for domain in catalog['domains']:
        for profile in domain['technologies']:
            for field in profile.get('local_timing_schema') or []:
                if field['key'] in {'master_node_id', 'hs_clock_timing_source'}:
                    assert field['simulation_default'] is None
                    assert field['simulation_default_provenance']['basis'] == 'EXPLICIT_REFERENCE_REQUIRED'
                else:
                    assert field['simulation_default'] is not None and field['simulation_default'] != ''
                assert field['simulation_default_provenance']['hardware_evidence'] is False


def assumption_group():
    return {'values': {'arbitration_bitrate': 500000, 'can_clock_hz': 40000000},
            'provenance': {key: {'source': 'NIS_SIMULATION_ASSUMPTION', 'status': 'ASSUMED',
                                'technology': 'can_fd', 'hardware_evidence': False, 'value': value}
                           for key, value in {'arbitration_bitrate': 500000, 'can_clock_hz': 40000000}.items()}}


def test_simulation_assumptions_roundtrip_without_actual_confirmation_or_graph_changes():
    service = WorkflowStatusService()
    values = {'technology': 'can_fd', 'simulation_parameter_assumptions': {'can_fd': assumption_group()},
              'networks': [], 'spatial_architecture': {'retain': 'original'}}
    saved = service.save_parameters(values)['parameters']
    assert saved['simulation_parameter_assumptions'] == values['simulation_parameter_assumptions']
    assert saved['networks'] == values['networks']
    assert saved['spatial_architecture']['retain'] == 'original'
    assert service.get()['parameters'] == saved
    assert 'arbitration_bitrate' not in saved
    from backend.nis.engineering.capacity.service import parameters_for_protocol
    assert not parameters_for_protocol('CAN_FD', saved, confirmed_parameters=saved)['_rate_evidenced']


def test_forged_assumption_proof_rejects_without_mutating_saved_project():
    service = WorkflowStatusService()
    values = {'simulation_parameter_assumptions': {'can_fd': assumption_group()}}
    saved = service.save_parameters(values)['parameters']
    malicious = deepcopy(values)
    malicious['simulation_parameter_assumptions']['can_fd']['provenance']['can_clock_hz']['hardware_evidence'] = True
    with pytest.raises(ValueError, match='Gerätebestätigung'):
        service.save_parameters(malicious)
    assert service.get()['parameters'] == saved


def test_lin_simulation_defaults_never_fabricate_device_ids_or_evidence_sources():
    fields = {field['key']: field for field in registry.parameter_fields('lin')}
    for key in ['lin_registered_source', 'lin_device_source', 'lin_revision', 'lin_commander_node_id']:
        assert fields[key]['simulation_default'] is None
        assert fields[key]['simulation_default_provenance']['status'] == 'UNKNOWN'
    parameters = registry.simulation_defaults_for_project({'technology': 'lin'}, ['lin'])
    values = parameters['simulation_parameter_assumptions']['lin']['values']
    assert values['lin_bitrate_bps'] == 19200
    assert 'lin_registered_source' not in values
    assert 'lin_commander_node_id' not in values
    assert registry.validate_parameters('lin', values)['status'] != 'VALID'
    old = deepcopy(parameters)
    old['simulation_parameter_assumptions']['lin']['values'].update(lin_registered_source='simulation:lin:lin_registered_source', lin_bitrate_bps=9600)
    old['technology_parameters'] = {'lin': {'values': {'lin_device_source': 'reviewed-device-file'}, 'provenance': {}}}
    repaired = registry.simulation_defaults_for_project(old, ['lin'])
    assert 'lin_registered_source' not in repaired['simulation_parameter_assumptions']['lin']['values']
    assert repaired['simulation_parameter_assumptions']['lin']['values']['lin_bitrate_bps'] == 9600
    assert repaired['technology_parameters'] == old['technology_parameters']
