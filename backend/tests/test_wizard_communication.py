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
    graph = {'HardwareNode': nodes, 'Function': {}, 'HardwareNetworkInterface': {},
        'Interface': {key: {'hardware_node_id': key} for key in nodes},
        'Message': {key: {'name': key, 'interface_id': key, 'configuration': {}} for key in nodes}}
    graph['Message']['command'] = {'name': 'Befehl', 'interface_id': 'ecu', 'configuration': {
        'transport_unit': {'consumer_refs': ['actuator']}}}
    prompt = '- Systemcluster-Graph: ' + json.dumps([{'controllers': [
        {'ecu': 'Motor', 'sensors': ['Temperatur'], 'actuators': ['Ventil']},
        {'ecu': 'Diagnose', 'sensors': [], 'actuators': []}]}])
    return prompt, graph


def test_every_message_has_a_purpose_and_consumer_before_routing():
    prompt, graph = fixture()
    plan = communication_plan(prompt, graph)
    expected = {'sensor': ['ecu'], 'actuator': ['ecu'], 'command': ['actuator'],
                'ecu': ['diag'], 'gateway': ['diag'], 'diag': ['gateway']}
    assert {key: config['transport_unit']['consumer_refs'] for key, config in plan.items()} == expected
    for key, config in plan.items():
        graph['Message'][key]['configuration'] = config
    assert contract_findings(graph) == []
    assert communication_plan(prompt, graph) == plan


def test_user_consumers_are_preserved_and_missing_receiver_blocks_model_review():
    prompt, graph = fixture()
    graph['Message']['ecu']['configuration'] = {'transport_unit': {'consumer_refs': ['gateway']}}
    plan = communication_plan(prompt, graph)
    assert plan['ecu']['transport_unit']['consumer_refs'] == ['gateway']
    graph['Message']['ecu']['configuration'] = plan['ecu']
    graph['Message']['ecu']['configuration']['transport_unit']['consumer_refs'] = []
    assert contract_findings(graph)[0]['code'] == 'COMMUNICATION_CONTRACT_INVALID'


def test_single_controller_keeps_an_explicit_unresolved_review_finding():
    prompt, graph = fixture()
    graph['HardwareNode'] = {'ecu': graph['HardwareNode']['ecu']}
    graph['Message'] = {'ecu': graph['Message']['ecu']}
    prompt = '- Systemcluster-Graph: [{"controllers":[{"ecu":"Motor"}]}]'
    plan = communication_plan(prompt, graph)
    graph['Message']['ecu']['configuration'] = plan['ecu']
    assert plan['ecu']['communication_contract']['role'] == 'UNRESOLVED'
    assert contract_findings(graph)


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
