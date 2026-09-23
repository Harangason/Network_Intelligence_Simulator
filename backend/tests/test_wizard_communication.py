import json
from copy import deepcopy
import pytest
from backend.engineering.wizard_communication import communication_plan, contract_findings


def fixture():
    nodes = {'ecu': {'name': 'Motor', 'device_type': 'ECU'},
             'sensor': {'name': 'Temperatur', 'device_type': 'SensorController'},
             'actuator': {'name': 'Ventil', 'device_type': 'ActuatorController'},
             'diag': {'name': 'Diagnose', 'device_type': 'ECU'},
             'gateway': {'name': 'System', 'device_type': 'Gateway'}}
    graph = {'HardwareNode': nodes, 'Function': {}, 'HardwareNetworkInterface': {}, 'Signal': {},
        'Interface': {key: {'hardware_node_id': key} for key in nodes},
        'Message': {key: {'name': key, 'interface_id': key, 'configuration': {}} for key in nodes}}
    graph['Message']['command'] = {'name': 'Befehl', 'interface_id': 'ecu', 'configuration': {
        'transport_unit': {'consumer_refs': ['actuator']}}}
    prompt = '- Systemcluster-Graph: ' + json.dumps([{'controllers': [
        {'ecu': 'Motor', 'sensors': ['Temperatur'], 'actuators': ['Ventil']},
        {'ecu': 'Diagnose', 'sensors': [], 'actuators': []}]}])
    return prompt, graph


def test_unconfirmed_controller_status_remains_a_review_finding_before_routing():
    prompt, graph = fixture()
    plan = communication_plan(prompt, graph)
    expected = {'sensor': ['ecu'], 'actuator': ['ecu'], 'command': ['actuator'],
                'ecu': [], 'gateway': [], 'diag': []}
    assert {key: config['transport_unit']['consumer_refs'] for key, config in plan.items()} == expected
    for key, config in plan.items():
        graph['Message'][key]['configuration'] = config
    findings = contract_findings(graph)
    assert len(findings) == 3
    assert {finding['code'] for finding in findings} == {'COMMUNICATION_CONTRACT_INVALID'}
    assert communication_plan(prompt, graph) == plan


def display_fixture(enabled):
    prompt, graph = fixture()
    graph['HardwareNode']['hmi'] = {'name': 'Kombiinstrument', 'device_type': 'ECU'}
    graph['Signal']['status'] = {'name': 'MotorStatus', 'message_id': 'ecu'}
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['hmi_routes'] = [{'source': 'Motor', 'target': 'Kombiinstrument',
        'signals': ['MotorStatus'] if enabled else [], 'excluded_signals': [] if enabled else ['MotorStatus']}]
    return '- Systemcluster-Graph: ' + json.dumps(clusters), graph


def test_hmi_switches_change_only_selected_output_consumers_and_preserve_local_io():
    prompt, graph = display_fixture(True)
    plan = communication_plan(prompt, graph)
    assert plan['ecu']['transport_unit']['consumer_refs'] == ['hmi']
    assert plan['command']['transport_unit']['consumer_refs'] == ['actuator']
    assert plan['sensor']['transport_unit']['consumer_refs'] == ['ecu']
    assert plan['actuator']['transport_unit']['consumer_refs'] == ['ecu']
    for key, config in plan.items():
        graph['Message'][key]['configuration'] = config
    off, _ = display_fixture(False)
    off_plan = communication_plan(off, graph)
    assert off_plan['ecu']['transport_unit']['consumer_refs'] == []
    assert graph['Signal']['status']['name'] == 'MotorStatus'
    assert off_plan['ecu']['hmi_routing_selection'] == [{'target_ref': 'hmi', 'enabled': False}]
    for key, config in off_plan.items():
        graph['Message'][key]['configuration'] = config
    assert communication_plan(off, graph) == off_plan


def test_disabled_hmi_is_not_reintroduced_by_the_fallback_monitor():
    prompt, graph = display_fixture(False)
    graph['HardwareNode'] = {key: value for key, value in graph['HardwareNode'].items() if key in {'ecu', 'hmi'}}
    graph['Message'] = {'ecu': graph['Message']['ecu']}
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['controllers'] = [{'ecu': 'Motor'}]
    plan = communication_plan('- Systemcluster-Graph: ' + json.dumps(clusters), graph)
    assert plan['ecu']['transport_unit']['consumer_refs'] == []


def test_partial_frame_and_missing_signal_require_explicit_payload_resolution():
    prompt, graph = display_fixture(True)
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['hmi_routes'][0]['excluded_signals'] = ['PrivateFeedback']
    graph['Signal']['private'] = {'name': 'PrivateFeedback', 'message_id': 'ecu'}
    with pytest.raises(ValueError, match='eigene Nachricht'):
        communication_plan('- Systemcluster-Graph: ' + json.dumps(clusters), graph)
    graph['Signal'] = {}
    with pytest.raises(ValueError, match='Signale fehlen'):
        communication_plan(prompt, graph)


@pytest.mark.parametrize('enabled', [False, True])
def test_routing_generator_obeys_switch_even_with_a_stale_display_consumer(monkeypatch, enabled):
    from backend.engineering.agent_tools import wizard_generation as generation
    prompt, graph = display_fixture(enabled)
    graph['Message'] = {'ecu': {**graph['Message']['ecu'], 'configuration': {
        'transport_unit': {'consumer_refs': ['diag', 'hmi']},
        'communication_contract': {
            'version': 1,
            'role': 'DEVICE_STATUS',
            'basis': 'Statusüberwachung: Diagnose, sonst Gateway, sonst Controller',
            'producer_ref': 'ecu',
            'consumer_refs': ['diag', 'hmi'],
        }}}}
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['controllers'] = [{'ecu': 'Motor'}]
    prompt = '- Systemcluster-Graph: ' + json.dumps(clusters)
    monkeypatch.setattr(generation.model, 'objects', lambda kind: [{**row, 'id': key} for key, row in graph.get(kind, {}).items()])
    monkeypatch.setattr(generation.model, 'routes', lambda: [])
    monkeypatch.setattr(generation.proposal_store, 'list_proposals', lambda **_: [])
    monkeypatch.setattr(generation.proposal_service, 'create', lambda kind, changes, rationale, **_: changes)
    calls = []
    class Routes:
        def _hardware_graph(self):
            return {}, {}
        def generate_route(self, *, source_node_id, destination_node_id, message_id):
            calls.append((source_node_id, destination_node_id, message_id))
            return {'source': {'protocol': 'CAN_FD'}, 'destinations': [{'protocol': 'CAN_FD'}]}
    monkeypatch.setattr(generation, 'RoutingGenerationService', Routes)
    if enabled:
        generation.generate_routing({'prompt': prompt})
    else:
        with pytest.raises(ValueError, match='keine prüfbaren Routen'):
            generation.generate_routing({'prompt': prompt})
    assert ('ecu', 'diag', 'ecu') not in calls
    assert (('ecu', 'hmi', 'ecu') in calls) is enabled


def test_user_consumers_are_preserved_and_missing_receiver_blocks_model_review():
    prompt, graph = fixture()
    graph['Message']['ecu']['configuration'] = {'transport_unit': {'consumer_refs': ['gateway']}}
    plan = communication_plan(prompt, graph)
    assert plan['ecu']['transport_unit']['consumer_refs'] == ['gateway']
    graph['Message']['ecu']['configuration'] = plan['ecu']
    graph['Message']['ecu']['configuration']['transport_unit']['consumer_refs'] = []
    assert contract_findings(graph)[0]['code'] == 'COMMUNICATION_CONTRACT_INVALID'


def test_controller_status_does_not_default_to_diagnosis_and_old_generated_fallback_is_removed():
    prompt, graph = fixture()
    graph['Message']['ecu']['configuration'] = {
        'transport_unit': {'consumer_refs': ['diag']},
        'communication_contract': {
            'version': 1,
            'role': 'DEVICE_STATUS',
            'basis': 'Statusüberwachung: Diagnose, sonst Gateway, sonst Controller',
            'producer_ref': 'ecu',
            'consumer_refs': ['diag'],
        },
    }

    config = communication_plan(prompt, graph)['ecu']

    assert config['transport_unit']['consumer_refs'] == []
    assert config['communication_contract']['role'] == 'UNRESOLVED'
    assert 'muss vor der Modellfreigabe ergänzt werden' in config['communication_contract']['basis']


def test_retiring_generated_diagnostic_default_preserves_other_explicit_consumers():
    prompt, graph = fixture()
    graph['Message']['ecu']['configuration'] = {
        'transport_unit': {'consumer_refs': ['diag', 'gateway']},
        'communication_contract': {
            'version': 1,
            'role': 'DEVICE_STATUS',
            'basis': 'Statusüberwachung: Diagnose, sonst Gateway, sonst Controller',
            'producer_ref': 'ecu',
            'consumer_refs': ['diag', 'gateway'],
        },
    }

    config = communication_plan(prompt, graph)['ecu']

    assert config['transport_unit']['consumer_refs'] == ['gateway']
    assert config['communication_contract']['role'] == 'EXPLICIT'


def test_confirmed_function_route_is_the_only_controller_monitor_source():
    prompt, graph = fixture()
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['functional_routes'] = [{'source': 'Motor', 'target': 'Diagnose'}]

    config = communication_plan('- Systemcluster-Graph: ' + json.dumps(clusters), graph)['ecu']

    assert config['transport_unit']['consumer_refs'] == ['diag']
    assert config['communication_contract']['role'] == 'DEVICE_STATUS'


def test_single_controller_keeps_an_explicit_unresolved_review_finding():
    prompt, graph = fixture()
    graph['HardwareNode'] = {'ecu': graph['HardwareNode']['ecu']}
    graph['Message'] = {'ecu': graph['Message']['ecu']}
    prompt = '- Systemcluster-Graph: [{"controllers":[{"ecu":"Motor"}]}]'
    plan = communication_plan(prompt, graph)
    graph['Message']['ecu']['configuration'] = plan['ecu']
    assert plan['ecu']['communication_contract']['role'] == 'UNRESOLVED'
    assert contract_findings(graph)


def test_single_local_regulation_keeps_unrequested_controller_status_internal():
    prompt, graph = fixture()
    for kind in ('HardwareNode', 'Interface', 'Message'):
        graph[kind] = {key: row for key, row in graph[kind].items() if key not in {'diag', 'gateway'}}
    prompt = '- Systemcluster-Graph: ' + json.dumps([{
        'network_id': 'i2c',
        'controllers': [{
            'ecu': 'Motor',
            'sensors': ['Temperatur'],
            'actuators': ['Ventil'],
        }],
        'hmi_routes': [],
    }])

    plan = communication_plan(prompt, graph)

    assert plan['ecu']['communication_contract']['role'] == 'INTERNAL_STATE'
    assert plan['ecu']['communication_contract']['scope'] == 'FUNCTION_OUTPUT'
    assert plan['ecu']['routing']['enabled'] is False
    assert plan['sensor']['transport_unit']['consumer_refs'] == ['ecu']
    assert plan['actuator']['transport_unit']['consumer_refs'] == ['ecu']
    assert plan['command']['transport_unit']['consumer_refs'] == ['actuator']
    for key, config in plan.items():
        graph['Message'][key]['configuration'] = config
    assert contract_findings(graph) == []


def test_confirmed_local_status_excludes_only_controller_output_from_transport():
    prompt, graph = fixture()
    for kind in ('HardwareNode', 'Interface', 'Message'):
        graph[kind] = {key: row for key, row in graph[kind].items() if key not in {'diag', 'gateway'}}
    prompt = '- Systemcluster-Graph: ' + json.dumps([{'controller_status_scope': 'INTERNAL',
        'controllers': [{'ecu': 'Motor', 'sensors': ['Temperatur'], 'actuators': ['Ventil']}]}])
    plan = communication_plan(prompt, graph)
    assert plan['ecu']['communication_contract']['scope'] == 'FUNCTION_OUTPUT'
    assert plan['ecu']['routing']['enabled'] is False
    assert plan['sensor']['transport_unit']['consumer_refs'] == ['ecu']
    assert plan['actuator']['transport_unit']['consumer_refs'] == ['ecu']
    assert plan['command']['transport_unit']['consumer_refs'] == ['actuator']
    for key, config in plan.items():
        graph['Message'][key]['configuration'] = config
    assert contract_findings(graph) == []
    assert communication_plan(prompt, graph) == plan


def test_conflicting_ownership_is_not_silently_resolved():
    prompt, graph = fixture()
    clusters = json.loads(prompt.split(': ', 1)[1])
    clusters[0]['controllers'][1]['sensors'] = ['Temperatur']
    with pytest.raises(ValueError, match='mehrere Controller'):
        communication_plan('- Systemcluster-Graph: ' + json.dumps(clusters), graph)


def test_resource_inventory_uses_the_server_request_in_generation_and_review():
    from backend.engineering.intelligence.resource_policy import planning_inventory
    prompt = '- Kommunikationssystem-Sollwerte: [{"id":"can_fd","count":10}]'
    state = {'context': {'wizard_request': {'version': 1, 'prompt': prompt},
                         'agent_wizard_status': {'agent_prompt': '- Kommunikationssystem-Sollwerte: [{"id":"can_fd","count":2}]'}}}
    assert planning_inventory(state) == planning_inventory(state, 'unrelated')
    assert planning_inventory(state).get('CAN_FD') == 10


def test_legacy_upgrade_reuses_pending_review_and_becomes_unchanged_after_apply(monkeypatch):
    from backend.engineering.agent_tools import wizard_generation as generation
    prompt, graph = fixture()
    stored = []
    monkeypatch.setattr(generation.model, 'objects', lambda kind: [
        {**row, 'id': key, 'version': 1} for key, row in graph[kind].items()])
    monkeypatch.setattr(generation.proposal_store, 'list_proposals', lambda **_: stored)
    monkeypatch.setattr(generation.proposal_service, 'envelope', lambda row: row)
    def create(kind, changes, rationale, **metadata):
        row = {'proposal_id': 'same-review', 'proposal_type': kind, 'changes': changes,
               'engineering_contract': {'status': 'VALIDATED'}, **metadata}
        stored.append(row)
        return row
    monkeypatch.setattr(generation.proposal_service, 'create', create)
    first = generation.generate_communication_contract({'prompt': prompt})
    assert generation.generate_communication_contract({'prompt': prompt}) is first
    assert len(stored) == 1
    for change in first['changes']:
        graph['Message'][change['object_id']]['configuration'] = change['data']['configuration']
    assert generation.generate_communication_contract({'prompt': prompt}) == {'status': 'UNCHANGED'}
