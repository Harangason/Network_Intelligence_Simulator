"""Reviewed model amendments must neither duplicate networks nor disappear."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import model, proposal_service, wizard_generation
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.workflow.service import WorkflowStatusService


GRAPH = [
    {'network_id': 'can_fd', 'bus_name': 'Drive', 'controllers': [
        {'ecu': 'Motorsteuerung', 'sensors': [], 'actuators': []}],
     'hmi_routes': [{'source': 'Motorsteuerung', 'target': 'Anzeige'}]},
    {'network_id': 'ethernet', 'bus_name': 'Display', 'controllers': [
        {'ecu': 'Anzeige', 'sensors': [], 'actuators': []}]},
]
PROMPT = '\n'.join([
    '- Industrie: Automotive',
    '- Netzwerktechnologien: CAN-FD (can_fd); Ethernet (ethernet)',
    '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}',
    '- Systemcluster-Graph: ' + json.dumps(GRAPH),
    'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:',
    'Motorsteuerung und Anzeige mit einem zentralen Gateway verbinden.',
])


@pytest.fixture
def applied_model():
    authority = ToolAuthority('pytest-amend-model-' + uuid4().hex)

    def call(fn):
        result = execute(authority, 'amend_model', Permission.GENERATE_PROPOSAL, {}, lambda _: fn())
        assert result.success, json.dumps(result.model_dump(), ensure_ascii=False, default=str)
        return result.data

    def apply(proposal):
        checked = proposal_service.validate(proposal['proposal_id'])
        assert checked['validation_result']['valid'], checked['validation_result']
        approved = proposal_service.review(proposal['proposal_id'], revision=checked['revision'],
            decision='approve', actor='test-human', trace_id=uuid4().hex)
        return proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=uuid4().hex)

    call(lambda: apply(wizard_generation.generate({'prompt': PROMPT})))

    def amend(addition):
        prompt = PROMPT + '\n\nBestaetigte Ergaenzung des Nutzers:\n' + addition
        request = {'version': 2, 'run_id': 'amend-model-test-run', 'revision': 'amend-revision-2',
            'prompt': prompt, 'base_prompt': PROMPT, 'amendments': [addition], 'target': 'data_science_intelligence'}
        def generate():
            WorkflowStatusService(authority.project_id).set_context({'wizard_request': request})
            return wizard_generation.generate({'prompt': prompt})
        return call(generate)

    return call, amend, apply


def test_descriptive_amend_requires_current_revision_confirmation_without_model_mutation(applied_model):
    call, amend, _ = applied_model
    before = call(model.model_revision)
    networks = call(model.networks)
    result = amend('Darstellung bitte übersichtlich halten.')
    assert result['status'] == 'MODEL_CONFIRMATION_REQUIRED', result
    assert result['model_revision'] == before
    assert result['request_revision'] == 'amend-revision-2'
    assert result['run_id'] == 'amend-model-test-run'
    assert result['findings'][0]['code'] == 'AMENDMENT_WITHOUT_MODEL_DELTA'
    assert call(model.model_revision) == before
    assert call(model.networks) == networks


def test_explicit_amend_adds_owned_sensor_as_reviewable_delta(applied_model):
    call, amend, apply = applied_model
    before = call(model.model_revision)
    previous_ids = {row['id'] for row in call(lambda: model.objects('HardwareNode'))}
    graph = deepcopy(GRAPH)
    graph[0]['controllers'][0]['sensors'] = ['MotorTemperature']
    result = amend('\n'.join([
        '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":1,"actuators":0}',
        '- Systemcluster-Graph: ' + json.dumps(graph),
        'MotorTemperature zusätzlich als Sensor der Motorsteuerung aufnehmen.',
    ]))
    hardware = [change for change in result['changes'] if change['object_type'] == 'HardwareNode']
    assert [change['data']['name'] for change in hardware] == ['MotorTemperature'], result['changes']
    assert not any(change['object_type'] == 'Network' and change['data']['id'] in {'Drive', 'Display'}
                   for change in result['changes'])
    assert call(model.model_revision) == before
    call(lambda: apply(result))
    rows = call(lambda: model.objects('HardwareNode'))
    owner = next(row for row in rows if row['name'] == 'Motorsteuerung')
    sensor = next(row for row in rows if row['name'] == 'MotorTemperature')
    assert sensor['identity']['system_owner_id'] == owner['id']
    assert previous_ids < {row['id'] for row in rows}
    assert call(model.model_revision) != before
    routing = call(lambda: wizard_generation.generate_routing({'prompt': PROMPT +
        '\n\nBestaetigte Ergaenzung des Nutzers:\n' + '\n'.join([
            '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":1,"actuators":0}',
            '- Systemcluster-Graph: ' + json.dumps(graph),
            'MotorTemperature zusätzlich als Sensor der Motorsteuerung aufnehmen.',
        ])}))
    checked = call(lambda: proposal_service.validate(routing['proposal_id']))
    assert checked['validation_result']['valid'], checked['validation_result']
    assert any(change['data']['source']['node_id'] == sensor['id'] and
               any(target['node_id'] == owner['id'] for target in change['data']['destinations'])
               for change in routing['changes'])


def test_same_network_id_with_changed_technology_is_reported_before_proposal(applied_model):
    call, amend, _ = applied_model
    before = call(model.model_revision)
    graph = deepcopy(GRAPH)
    graph[0]['network_id'] = 'ethernet'
    with pytest.raises(AssertionError, match='Drive.*CAN_FD.*ETHERNET'):
        amend('- Systemcluster-Graph: ' + json.dumps(graph))
    assert call(model.model_revision) == before


def test_explicit_network_parameter_amendment_is_not_silently_ignored(applied_model):
    call, amend, _ = applied_model
    before = call(model.model_revision)
    graph = deepcopy(GRAPH)
    graph[0]['bitrate_bps'] = 1000000
    with pytest.raises(AssertionError, match='Drive.*bitrate_bps.*1000000'):
        amend('- Systemcluster-Graph: ' + json.dumps(graph))
    assert call(model.model_revision) == before


@pytest.mark.parametrize('field,value', [
    ('controller_status_scope', 'INTERNAL'),
    ('functional_routes', [{'source': 'Motorsteuerung', 'target': 'Anzeige'}]),
])
def test_unapplied_model_can_amend_communication_decisions_but_applied_model_requires_review(
        monkeypatch, field, value):
    graph = deepcopy(GRAPH)
    graph[0][field] = value
    prompt = PROMPT + '\n\nBestaetigte Ergaenzung des Nutzers:\n- Systemcluster-Graph: ' + json.dumps(graph)
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _: {'chains': []})
    wizard_generation._check_existing_amendment_semantics(
        prompt, {'chains': []}, {'HardwareNode': []}, {})
    with pytest.raises(ValueError, match='Kommunikations- und Routingvorschlag'):
        wizard_generation._check_existing_amendment_semantics(
            prompt, {'chains': []}, {'HardwareNode': [{'name': 'Motorsteuerung'}]}, {})


@pytest.mark.parametrize('field,new_value', [('cycle_ms', 5), ('length_bits', 12), ('factor', 0.5),
                                          ('transport_network_ref', 'AnotherNetwork')])
def test_existing_signal_technical_amendment_is_a_concrete_conflict(monkeypatch, field, new_value):
    old = {'hardware_name': 'Motor', 'signal_name': 'Temperature', 'cycle_ms': 20,
           'length_bits': 8, 'factor': 1}
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _: {'chains': [old]})
    with pytest.raises(ValueError, match=f'Motor / Temperature: {field}'):
        wizard_generation._check_existing_amendment_semantics(
            PROMPT + '\n\nBestaetigte Ergaenzung des Nutzers:\nKodierung ändern.',
            {'chains': [{**old, field: new_value}]}, {'HardwareNode': [{'name': 'Motor'}]}, {})


def test_unchanged_canonical_encoding_is_not_compared_with_fresh_defaults(monkeypatch):
    chain = {'hardware_name': 'Motor', 'signal_name': 'Temperature', 'length_bits': 8}
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _: {'chains': [chain]})
    wizard_generation._check_existing_amendment_semantics(
        PROMPT + '\n\nBestaetigte Ergaenzung des Nutzers:\nBeschreibung übersichtlicher.',
        {'chains': [chain]}, {'HardwareNode': [{'name': 'Motor'}],
                              'Signal': [{'name': 'Temperature', 'length_bits': 16}]}, {})
