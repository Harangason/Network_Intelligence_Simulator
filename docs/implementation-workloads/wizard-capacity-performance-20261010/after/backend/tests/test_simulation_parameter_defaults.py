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


@pytest.mark.parametrize('technology', ['lin', 'can_fd', 'ethernet'])
def test_repeated_native_resolution_reuses_validation_without_caching_provenance(monkeypatch, technology):
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    parameters = registry.simulation_defaults_for_project({'technology': technology}, [technology])
    expected = simulation_parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    original = registry._validate_parameters
    calls = []
    def observed(protocol, values):
        calls.append((protocol, deepcopy(values)))
        return original(protocol, values)
    monkeypatch.setattr(registry, '_validate_parameters', observed)
    with registry.parameter_validation_session():
        for _ in range(30):
            assert simulation_parameters_for_protocol(technology, parameters,
                confirmed_parameters=parameters) == expected
        assert len(calls) <= 3
        changed = deepcopy(parameters)
        group = changed['simulation_parameter_assumptions'][technology]
        field = next(iter(group['values']))
        group['provenance'][field]['hardware_evidence'] = True
        rejected = simulation_parameters_for_protocol(technology, changed, confirmed_parameters=changed)
        assert not rejected['_simulation_parameters_usable']
        assert any(row['code'] == 'SIMULATION_PARAMETER_PROVENANCE_MISMATCH'
                   for row in rejected['_simulation_parameter_findings'])
    previous = len(calls)
    assert simulation_parameters_for_protocol(technology, parameters,
        confirmed_parameters=parameters) == expected
    assert len(calls) > previous


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


@pytest.mark.parametrize('technology', ['lin', 'can_fd', 'ethernet'])
def test_saved_scenario_is_a_complete_parameter_artifact_without_qualifying_hardware(technology):
    parameters = registry.simulation_defaults_for_project({
        'industry': 'automotive', 'technology': technology, 'formats': ['universal-jsonl'],
        'cycle_ms': 100, 'payload_bytes': 8, 'queue_size': 256,
        'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90,
    }, [technology])
    before = deepcopy(parameters)
    result = WorkflowStatusService._parameter_artifact_check(parameters)
    assert result['complete'], result
    assert result['configuration_basis'] == 'SAVED_SIMULATION_ASSUMPTIONS'
    assert result['hardware_evidence'] is False
    assert parameters == before
    group = parameters['simulation_parameter_assumptions'][technology]
    key = {'lin': 'lin_bitrate_bps', 'can_fd': 'arbitration_bitrate', 'ethernet': 'bitrate'}[technology]
    group['provenance'][key]['value'] = -1
    rejected = WorkflowStatusService._parameter_artifact_check(parameters)
    assert not rejected['complete']
    assert any(row['code'] == 'SIMULATION_PARAMETER_PROVENANCE_MISMATCH' for row in rejected['profile_findings'])


@pytest.mark.parametrize('technology,rates,retained', [
    ('ethernet', ['bitrate'], ['duplex', 'eth_link_up']),
    ('can_fd', ['arbitration_bitrate', 'data_bitrate'], ['can_clock_hz', 'can_fd_data_prescaler']),
])
def test_confirmed_rate_retains_saved_native_scenario_without_hardware_proof(technology, rates, retained):
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    parameters = registry.simulation_defaults_for_project({'technology': technology}, [technology])
    assumptions = parameters['simulation_parameter_assumptions'][technology]
    values = {key: assumptions['values'][key] for key in rates}
    parameters['technology_parameters'] = {technology: {
        'values': values,
        'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED',
                             'technology': technology, 'value': value} for key, value in values.items()},
    }}
    before = deepcopy(parameters)
    resolved = simulation_parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    assert resolved['_rate_evidenced']
    assert resolved['_simulation_parameters_usable'], resolved['_simulation_parameter_findings']
    for key in retained:
        assert resolved[key] == assumptions['values'][key]
        assert key in resolved['_simulation_assumption_fields']
    assert not resolved['_simulation_hardware_evidence']
    assert parameters == before
    # Even with confirmed rates, a forged assumed configuration must be rejected.
    assumptions['provenance'][retained[0]]['hardware_evidence'] = True
    rejected = simulation_parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    assert not rejected['_simulation_parameters_usable']
    assert any(row['code'] == 'SIMULATION_PARAMETER_PROVENANCE_MISMATCH'
               for row in rejected['_simulation_parameter_findings'])


def test_confirmed_ethernet_rate_does_not_override_explicit_link_configuration():
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    parameters = registry.simulation_defaults_for_project({'technology': 'ethernet'}, ['ethernet'])
    parameters['technology_parameters'] = {'ethernet': {
        'values': {'bitrate': 1_000_000_000},
        'provenance': {'bitrate': {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED',
                                   'technology': 'ethernet', 'value': 1_000_000_000}},
    }}
    resolved = simulation_parameters_for_protocol('ethernet', parameters,
        configuration={'technology': 'ethernet', 'eth_link_up': False}, confirmed_parameters=parameters)
    assert resolved['eth_link_up'] is False
    assert 'eth_link_up' not in resolved['_simulation_assumption_fields']
    assert not resolved['_simulation_hardware_evidence']
    from backend.nis.communication.technologies.ethernet.scheduling import parameter_readiness
    assert [row['parameter'] for row in parameter_readiness(resolved)] == ['eth_link_up']


def test_ethernet_starter_has_a_schedulable_active_link_without_hardware_confirmation():
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.communication.technologies.ethernet.scheduling import parameter_readiness
    parameters = registry.simulation_defaults_for_project({'technology': 'ethernet'}, ['ethernet'])
    resolved = simulation_parameters_for_protocol('ethernet', parameters, confirmed_parameters=parameters)
    assert resolved['eth_link_up'] is True
    assert resolved['_simulation_parameters_usable']
    assert not resolved['_simulation_hardware_evidence']
    assert parameter_readiness(resolved) == []
    # A user's persisted inactive scenario must not be silently overwritten by a new preset.
    group = parameters['simulation_parameter_assumptions']['ethernet']
    group['values']['eth_link_up'] = group['provenance']['eth_link_up']['value'] = False
    refreshed = registry.simulation_defaults_for_project(parameters, ['ethernet'])
    assert refreshed['simulation_parameter_assumptions']['ethernet']['values']['eth_link_up'] is False


def test_assumed_ethernet_configuration_follows_confirmed_network_rate_and_payload():
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.communication.technologies.ethernet.timing import planning_frame_parameters
    parameters = registry.simulation_defaults_for_project({'technology': 'ethernet'}, ['ethernet'])
    configuration = {'technology': 'ethernet', 'bitrate': 100_000_000,
                     'eth_payload_layer': 'UPPER_LAYER', 'eth_upper_header_bytes': 28, 'payload_bytes': 8}
    before = deepcopy(parameters)
    resolved = simulation_parameters_for_protocol('ethernet', parameters, configuration, confirmed_parameters=parameters)
    assert resolved['_simulation_parameters_usable'], resolved['_simulation_parameter_findings']
    assert resolved['bitrate'] == 100_000_000 and resolved['eth_peer_rate_bps'] == 100_000_000
    assert resolved['eth_phy'] == '100BASE_TX' and resolved['eth_client_bytes'] == 36
    assert not resolved['_simulation_hardware_evidence']
    message = planning_frame_parameters(100, resolved)
    assert message['eth_client_bytes'] == 128 and message['eth_mac_frame_bytes'] == 146
    assert message['eth_wire_slot_bytes'] == 166
    assert resolved['eth_client_bytes'] == 36 and parameters == before
    rejected = simulation_parameters_for_protocol('ethernet', parameters,
        {**configuration, 'eth_phy': '1000BASE_T'}, confirmed_parameters=parameters)
    assert not rejected['_simulation_parameters_usable']
    assert rejected['eth_phy'] == '1000BASE_T' and rejected['bitrate'] == 100_000_000


def test_native_can_fd_conservative_bound_retains_only_explicit_padding():
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.communication.technologies.can_fd.timing import planning_frame_parameters
    from backend.nis.engineering.capacity.calculators import can_frame_time_bound_ms
    parameters = registry.simulation_defaults_for_project({'technology': 'can_fd'}, ['can_fd'])
    resolved = simulation_parameters_for_protocol('can_fd', parameters, confirmed_parameters=parameters)
    actual = planning_frame_parameters(2, resolved)
    assert actual['can_fd_dlc'] == 2 and actual['can_fd_wire_data_bytes'] == 2
    bound = can_frame_time_bound_ms('CAN_FD', 2, {**actual, '_rate_evidenced': actual['_simulation_parameters_usable']})
    assert bound == pytest.approx(.528)
    fixed = simulation_parameters_for_protocol('can_fd', parameters,
        {'technology': 'can_fd', 'can_fd_dlc': 15, 'can_fd_wire_data_bytes': 64,
         'can_fd_crc_bits': 21}, confirmed_parameters=parameters)
    padded = planning_frame_parameters(2, fixed)
    assert padded['can_fd_dlc'] == 15 and padded['can_fd_wire_data_bytes'] == 64
    assert padded['_simulation_parameters_usable'], padded['_simulation_parameter_findings']
    assert can_frame_time_bound_ms('CAN_FD', 2, {**padded, '_rate_evidenced': padded['_simulation_parameters_usable']}) > bound
    assert not actual['_simulation_hardware_evidence'] and not padded['_simulation_hardware_evidence']


@pytest.mark.parametrize('technology', ['lin', 'can_fd'])
def test_saved_assumptions_execute_native_trace_without_device_sources(tmp_path, technology):
    import csv
    import json
    from backend.tests.test_acceptance_scenarios import case_config
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.simulation.hardware_profile import normalize_hardware_config
    from backend.nis.traces.universal_trace import generate_universal_events, write_csv, write_jsonl
    parameters = registry.simulation_defaults_for_project({'technology': technology}, [technology])
    resolved = simulation_parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    config = case_config(tmp_path, [technology])
    config['parameters'] = parameters
    config['networks'] = [{**{key: value for key, value in resolved.items() if key in registry.parameter_keys(technology)},
        'id': 'network-0', 'technology': technology, 'bitrate': resolved['bitrate'],
        '_rate_evidenced': False, '_simulation_assumption_fields': resolved['_simulation_assumption_fields'],
        'simulation_parameter_assumptions': resolved['_simulation_parameter_assumptions']}]
    before = deepcopy(config)
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    assert events and all(row['tx_end_s'] > row['tx_start_s'] for row in events)
    assert all(row['timing_basis'] == 'SAVED_SIMULATION_ASSUMPTIONS' and row['hardware_evidence'] is False
               and row['functional_timing_accepted'] is False for row in events)
    csv_path = write_csv(tmp_path/'scenario.csv', events)
    jsonl_path = write_jsonl(tmp_path/'scenario.jsonl', events)
    with csv_path.open(encoding='utf-8', newline='') as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == len(events)
    assert all(row['timing_basis'] == 'SAVED_SIMULATION_ASSUMPTIONS'
               and row['hardware_evidence'] == 'False'
               and row['functional_timing_accepted'] == 'False' for row in exported)
    assert [json.loads(line) for line in jsonl_path.read_text(encoding='utf-8').splitlines()] == events
    assert config == before
    assert not resolved['_rate_evidenced']
    group = parameters['simulation_parameter_assumptions'][technology]
    key = 'lin_bitrate_bps' if technology == 'lin' else 'arbitration_bitrate'
    group['provenance'][key]['technology'] = 'spi'
    with pytest.raises(ValueError, match='TIMING_UNVERIFIED'):
        generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)


def test_resumed_parameter_generation_retains_later_saved_values_over_original_prompt(monkeypatch):
    from backend.nis.agent.tools import wizard_generation
    from backend.nis.engineering.projects.project_context import current_project_id
    workflow = WorkflowStatusService(current_project_id())
    parameters = registry.simulation_defaults_for_project({
        'technology': 'can_fd', 'industry': 'automotive', 'formats': ['universal-jsonl'],
        'bitrate': 4_000_000, 'arbitration_bitrate': 500_000, 'data_bitrate': 4_000_000,
        'cycle_ms': 100, 'payload_bytes': 8, 'queue_size': 256,
        'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90,
        'spatial_zoning': {'retained': True}, 'communication_sizing': {'enabled': False},
    }, ['can_fd'])
    workflow.save_parameters(parameters)
    before = workflow.get()['parameters']
    monkeypatch.setattr(wizard_generation.model, 'routes', lambda: [])
    result = wizard_generation.generate_parameters({'prompt': '- Projekt-Modelltyp: automotive\n- Netzwerktechnologien: CAN-FD (can_fd)\nCAN-FD: 500 kbit/s arbitration, 2 Mbit/s data'})
    assert result['parameters']['bitrate'] == 4_000_000
    assert result['parameters']['data_bitrate'] == 4_000_000
    assert result['parameters']['simulation_parameter_assumptions'] == before['simulation_parameter_assumptions']


def test_sizing_only_continuation_never_regenerates_saved_defaults_or_spatial_plan(monkeypatch):
    from types import SimpleNamespace
    from backend.nis.agent.tools import wizard_generation
    from backend.nis.engineering.capacity.sizing_service import CommunicationSizingService
    from backend.nis.engineering.structure.zoning_service import SpatialZoningService
    parameters = registry.simulation_defaults_for_project({'technology': 'lin', 'seed': 73,
        'communication_sizing': {'enabled': True}}, ['lin'])
    state = {'parameters': parameters, 'statuses': {'parameters': 'APPROVED'},
             'artifact_checks': {'parameters': {'complete': True}, 'network_editor': {'complete': True}}}
    before = deepcopy(state)
    monkeypatch.setattr(wizard_generation, 'WorkflowStatusService', lambda _: SimpleNamespace(get=lambda: deepcopy(state)))
    calls = []
    monkeypatch.setattr(CommunicationSizingService, 'preview', lambda self: calls.append('native-sizing') or {'changes': []})
    def forbidden(*args, **kwargs):
        pytest.fail('Complete saved configuration must not be regenerated or rezoned.')
    monkeypatch.setattr(registry, 'simulation_defaults_for_project', forbidden)
    monkeypatch.setattr(SpatialZoningService, 'plan', forbidden)
    monkeypatch.setattr(wizard_generation.model, 'routes', forbidden)
    result = wizard_generation.generate_parameters({'prompt': 'LIN: 9,6 kbit/s', 'sizing_only': True})
    assert calls == ['native-sizing']
    assert result['parameters'] == before['parameters'] and state == before
    assert result['source'] == 'saved-project-configuration'


@pytest.mark.parametrize('parameter_complete,topology_complete', [(False, True), (True, False), (False, False)])
def test_sizing_only_rejects_incomplete_input_without_generation_or_writes(monkeypatch, parameter_complete, topology_complete):
    from types import SimpleNamespace
    from backend.nis.agent.tools import wizard_generation
    state = {'artifact_checks': {'parameters': {'complete': parameter_complete},
                                'network_editor': {'complete': topology_complete}}}
    monkeypatch.setattr(wizard_generation, 'WorkflowStatusService', lambda _: SimpleNamespace(get=lambda: deepcopy(state)))
    def forbidden(*args, **kwargs):
        pytest.fail('Sizing-only must fail before any missing defaults are generated.')
    monkeypatch.setattr(registry, 'simulation_defaults_for_project', forbidden)
    with pytest.raises(ValueError, match='vollständige gespeicherte Parameter und Netzwerktopologie'):
        wizard_generation.generate_parameters({'prompt': 'LIN', 'sizing_only': True})


def test_saved_primary_configuration_cannot_skip_missing_secondary_bus_defaults():
    parameters = registry.simulation_defaults_for_project({
        'industry': 'automotive', 'technology': 'can_fd', 'formats': ['universal-jsonl'],
        'cycle_ms': 100, 'payload_bytes': 8, 'queue_size': 256,
        'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90,
        'networks': [{'id':'lin-local','technology':'lin'}, {'id':'eth-backbone','technology':'ethernet'}],
    }, ['can_fd'])
    # The registry fills declared networks too; reproduce a previously saved
    # partial parameter form by retaining only its selected bus group.
    parameters['simulation_parameter_assumptions'] = {'can_fd':parameters['simulation_parameter_assumptions']['can_fd']}
    before = deepcopy(parameters)
    partial = WorkflowStatusService._parameter_artifact_check(parameters)
    assert not partial['complete']
    assert not partial['required']['technology:lin'] and not partial['required']['technology:ethernet']
    assert parameters == before, 'Read-only validation must not silently write defaults.'
    filled = registry.simulation_defaults_for_project(parameters, ['can_fd','lin','ethernet'])
    complete = WorkflowStatusService._parameter_artifact_check(filled)
    assert complete['complete'], complete
    assert filled['simulation_parameter_assumptions']['can_fd'] == before['simulation_parameter_assumptions']['can_fd']
    assert complete['hardware_evidence'] is False


@pytest.mark.parametrize('technology', ['lin', 'can_fd', 'ethernet'])
def test_saved_native_review_executes_without_regenerating_default_proposals(monkeypatch, technology):
    from backend.nis.agent.tools import validation
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
    parameters = registry.simulation_defaults_for_project({'technology':technology, 'industry':'automotive'}, [technology])
    before = deepcopy(parameters)
    changes = [
        {'action':'CREATE', 'object_type':'Network', 'local_ref':'network',
         'data':{'id':'review-network', 'technology':technology}},
        {'action':'CREATE', 'object_type':'HardwareNode', 'local_ref':'node', 'data':{'name':'Controller'}},
        {'action':'CREATE', 'object_type':'HardwareNetworkInterface', 'local_ref':'port',
         'data':{'name':'Port', 'technology':technology, 'network_ref':'review-network', 'hardware_node_id':'$node'}},
        {'action':'CREATE', 'object_type':'Message', 'local_ref':'message',
         'data':{'hardware_interface_id':'$port', 'dlc':8, 'cycle_ms':100}},
    ]
    monkeypatch.setattr(validation, 'objects', lambda kind: [])
    def forbidden_defaults(*args, **kwargs):
        pytest.fail('Saved review must not regenerate default proposals')
    monkeypatch.setattr(registry, 'parameter_fields', forbidden_defaults)
    resolved = simulation_parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    assert resolved['_simulation_parameters_usable'] and not resolved['_rate_evidenced']
    assert estimate_simulation_frame(technology, 8, resolved).transmission_time_available
    checks = validation.review_simulation_capacity({'parameters':parameters}, changes)
    assert len(checks) == 1 and checks[0]['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS'
    findings = validation.review_parameter_findings({'parameters':parameters}, changes, simulation_checks=checks)
    assert len(findings) == 1 and findings[0]['code'] == 'CAPACITY_DEVICE_EVIDENCE_MISSING'
    assert findings[0]['severity'] == 'INFO' and findings[0]['simulation_parameters_usable']
    assert parameters == before
