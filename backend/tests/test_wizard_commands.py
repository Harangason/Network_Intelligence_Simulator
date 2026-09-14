"""Wizard operation identity and ownership, on the disposable SQL test database."""
import asyncio
import json
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.agent_response import AgentResponse, InteractiveQuestion
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.run_status import WizardExecutionTracker, recover_interrupted_wizard_runs
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.wizard_commands import WizardCommand, resolve_request
from backend.engineering.workflow.models import WORKFLOW_STEPS
from backend.engineering.workflow.service import WorkflowStatusService


def invoke(authority, fn):
    return execute(authority, 'wizard_command_test', Permission.READ_MODEL, {}, lambda _: fn())


@pytest.fixture
def request_case():
    authority = ToolAuthority('pytest-wizard-command-' + uuid4().hex)
    run_id = str(uuid4())
    prompt = ('Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
              'per Wizard-Uebernehmen bestaetigt\n- Hardware-Sollwerte: {"ecus":1}\n'
              f'- Lauf-ID: {run_id}\n- Aufgabe: Steuergerät mit Status modellieren.')
    context = AgentContext(active_project_id=authority.project_id, active_view='engineering')
    command = {'action': 'START', 'run_id': run_id, 'operation_id': str(uuid4()),
               'target': WORKFLOW_STEPS[-1], 'wizard_context': {'project_id': authority.project_id,
               'run_id': run_id, 'scope_ids': list(WORKFLOW_STEPS), 'agent_prompt': prompt}}
    return authority, context, command, prompt


def start(case):
    authority, context, command, prompt = case
    result = invoke(authority, lambda: conversation.begin(prompt, context, wizard_command=command))
    assert result.success, result.findings
    return result.data


def continuation(case, started, **extra):
    return {'action': 'CONTINUE', 'run_id': case[2]['run_id'], 'operation_id': str(uuid4()),
            'request_revision': started['wizard_receipt']['request_revision'], **extra}


def release(case, started):
    return invoke(case[0], lambda: conversation.finish(started['run_id']))


def test_start_stores_request_conversation_and_execution_atomically(request_case, monkeypatch):
    authority, context, command, prompt = request_case
    def fail_started(_):
        raise RuntimeError('injected status write failure')
    original = WizardExecutionTracker.started
    monkeypatch.setattr(WizardExecutionTracker, 'started', fail_started)
    failed = invoke(authority, lambda: conversation.begin(prompt, context, wizard_command=command))
    assert not failed.success
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert not state['context'].get('wizard_request')
    monkeypatch.setattr(WizardExecutionTracker, 'started', original)
    accepted = start(request_case)
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert state['context']['wizard_request']['prompt'] == prompt
    assert state['context']['wizard_request']['target'] == WORKFLOW_STEPS[-1]
    assert state['context']['agent_execution']['owner_turn_id'] == accepted['run_id']
    assert state['context']['agent_execution']['state'] == 'RUNNING'


def test_repeated_start_has_one_receipt_and_owner(request_case):
    first = start(request_case)
    second = start(request_case)
    assert second['duplicate'] is True
    assert first['run_id'] == second['run_id']
    assert first['wizard_receipt']['request_revision'] == second['wizard_receipt']['request_revision']
    authority, context, command, prompt = request_case
    changed = invoke(authority, lambda: conversation.begin(prompt + '\nOther input', context, wizard_command=command))
    assert not changed.success and changed.status.value == 'CONFLICT'
    new_operation = {**command, 'operation_id': str(uuid4())}
    duplicate_start = invoke(authority, lambda: conversation.begin(prompt, context, wizard_command=new_operation))
    assert duplicate_start.success and duplicate_start.data['duplicate'] is True
    stored = invoke(authority, conversation.read).data
    assert stored['wizard_operations'][new_operation['operation_id']]['accepted'] is True
    assert stored['run_id'] == first['run_id']


def test_continuation_uses_immutable_request_and_rejects_stale_revision(request_case):
    accepted = start(request_case)
    release(request_case, accepted)
    authority, context, _, prompt = request_case
    command = continuation(request_case, accepted)
    bad = invoke(authority, lambda: conversation.begin('', context, wizard_command={**command, 'request_revision': 'outdated'}))
    assert bad.status.value == 'CONFLICT'
    result = invoke(authority, lambda: conversation.begin('beliebige Formulierung ohne Ziel', context, wizard_command=command))
    assert result.success, result.findings
    assert result.data['prompt'] == prompt
    assert result.data['context']['wizard_request']['target'] == WORKFLOW_STEPS[-1]
    assert result.data['wizard_receipt']['request_revision'] == accepted['wizard_receipt']['request_revision']


def test_structured_question_answer_survives_wizard_navigation(request_case):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    question = InteractiveQuestion(question='Welcher Ausgang?', options=[{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}])
    event = AgentResponse(type='SINGLE_SELECT', question=question).model_dump(mode='json', exclude_none=True)
    recorded = invoke(authority, lambda: conversation.record_event(accepted['run_id'], event))
    assert recorded.success
    release(request_case, accepted)
    answer = {'type': 'QUESTION_ANSWER', 'question_id': question.id, 'selected_options': ['b']}
    command = continuation(request_case, accepted)
    result = invoke(authority, lambda: conversation.begin('', context.model_copy(update={'active_view': 'routing'}),
        raw_input=answer, wizard_command=command))
    assert result.success, result.findings
    assert result.data['context']['answered_questions'][question.id]['selected_options'] == ['b']
    state = invoke(authority, conversation.read).data
    assert state['questions'][question.id]['status'] == 'ANSWERED'
    assert state['current_question'] is None
    repeated = invoke(authority, lambda: conversation.begin('', context, raw_input=answer, wizard_command=command))
    assert repeated.success and repeated.data['duplicate'] is True
    changed = invoke(authority, lambda: conversation.begin('', context,
        raw_input={**answer, 'selected_options': ['a']}, wizard_command=command))
    assert changed.status.value == 'CONFLICT'


def test_restart_recovers_execution_and_unexpired_conversation_lease(request_case, monkeypatch):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    monkeypatch.setattr('backend.engineering.agent_tools.run_status.SERVER_INSTANCE_ID', 'new-test-worker')
    assert recover_interrupted_wizard_runs(authority.project_id) == 1
    state = invoke(authority, conversation.read).data
    assert state['run_id'] is None
    result = invoke(authority, lambda: conversation.begin('', context,
        wizard_command=continuation(request_case, accepted, automatic=True)))
    assert result.success, result.findings
    workflow = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert workflow['context']['agent_wizard_status']['automatic_resume_count'] == 1
    assert workflow['context']['agent_execution']['owner_turn_id'] == result.data['run_id']


def test_expired_question_rejects_stale_answer_without_blocking_resume(request_case):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    question = InteractiveQuestion(question='Welcher Ausgang?', options=[{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}])
    event = AgentResponse(type='SINGLE_SELECT', question=question).model_dump(mode='json', exclude_none=True)
    invoke(authority, lambda: conversation.record_event(accepted['run_id'], event))
    release(request_case, accepted)
    def expire():
        state = conversation.read()
        state['questions'][question.id]['expires_at'] = '2000-01-01T00:00:00+00:00'
        conversation.write(state)
    invoke(authority, expire)
    answer = {'type': 'QUESTION_ANSWER', 'question_id': question.id, 'selected_options': ['a']}
    stale = invoke(authority, lambda: conversation.begin('', context, raw_input=answer,
        wizard_command=continuation(request_case, accepted)))
    assert stale.status.value == 'CONFLICT'
    resumed = invoke(authority, lambda: conversation.begin('', context,
        wizard_command=continuation(request_case, accepted)))
    assert resumed.success, resumed.findings
    state = invoke(authority, conversation.read).data
    assert state['current_question'] is None
    assert state['questions'][question.id]['status'] == 'EXPIRED'


def test_amend_preserves_confirmed_answers_and_rejects_mixed_command_input(request_case):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    release(request_case, accepted)
    def save_answer():
        state = conversation.read()
        state['answered_questions']['ownership'] = {'selected_options': ['controller'], 'status': 'ANSWERED'}
        conversation.write(state)
    invoke(authority, save_answer)
    command = {**continuation(request_case, accepted), 'action': 'AMEND'}
    mixed = invoke(authority, lambda: conversation.begin('Add display', context, raw_input={'type': 'RESUME'}, wizard_command=command))
    assert not mixed.success
    amended = invoke(authority, lambda: conversation.begin('Add display', context, wizard_command=command))
    assert amended.success, amended.findings
    assert amended.data['context']['answered_questions']['ownership']['selected_options'] == ['controller']


@pytest.mark.parametrize('status,expected', [('COMPLETED', 'COMPLETED'), ('INCOMPLETE', 'BLOCKED'), ('READY_FOR_REVIEW', 'REVIEW_REQUIRED')])
def test_late_heartbeat_cannot_undo_terminal_outcome(request_case, status, expected):
    accepted = start(request_case)
    authority = request_case[0]
    tracker = WizardExecutionTracker(authority.project_id, request_case[2]['run_id'], owner_turn_id=accepted['run_id'])
    tracker.finished({'status': status, 'text': 'saved outcome'})
    tracker.heartbeat()
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert state['context']['agent_execution']['state'] == expected
    assert state['context']['agent_execution']['message'] == 'saved outcome'


def test_old_worker_cannot_overwrite_resumed_owner(request_case):
    first = start(request_case)
    release(request_case, first)
    authority, context, command, _ = request_case
    newer = invoke(authority, lambda: conversation.begin('', context, wizard_command=continuation(request_case, first))).data
    old = WizardExecutionTracker(authority.project_id, command['run_id'], owner_turn_id=first['run_id'])
    old.heartbeat()
    old.finished({'status': 'INCOMPLETE', 'text': 'old error'})
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert state['context']['agent_execution']['owner_turn_id'] == newer['run_id']
    assert state['context']['agent_execution']['state'] == 'RUNNING'


def test_modern_control_state_is_not_browser_context(request_case):
    start(request_case)
    authority = request_case[0]
    changed = invoke(authority, lambda: WorkflowStatusService(authority.project_id).set_context(
        {'agent_execution': {'state': 'COMPLETED'}}, client_write=True))
    assert changed.status.value == 'CONFLICT'
    preference = invoke(authority, lambda: WorkflowStatusService(authority.project_id).set_context(
        {'engineering_wizard_settings': {'project_name': 'Renamed'}}, client_write=True))
    assert preference.success


def test_amendment_creates_revision_and_preserves_base_request(request_case):
    first = start(request_case)
    release(request_case, first)
    authority, context, command, prompt = request_case
    amend = {**continuation(request_case, first), 'action': 'AMEND'}
    result = invoke(authority, lambda: conversation.begin('Ein weiteres Temperatursignal ergänzen.', context, wizard_command=amend))
    assert result.success, result.findings
    request = result.data['context']['wizard_request']
    assert request['base_prompt'] == prompt
    assert request['parent_revision'] == first['wizard_receipt']['request_revision']
    assert request['revision'] != request['parent_revision']
    assert request['model_review_required'] is True
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data
    assert state['context']['agent_execution']['step'] == 'engineering_model'
    assert state['context']['agent_execution']['model_review_required'] is True


def test_amendment_updates_confirmed_count_and_graph_status_without_rewriting_base(request_case):
    first = start(request_case)
    release(request_case, first)
    authority, context, _, prompt = request_case
    graph = [{'cluster_id': 'drive', 'label': 'Antrieb', 'network_id': 'can_fd',
              'controllers': [{'ecu': 'Motor', 'sensors': ['Temperature', 'Pressure'], 'actuators': []}],
              'unassigned': [], 'hmi_routes': []}]
    addition = '- Hardware-Sollwerte: {"ecus":1,"sensors":2,"actuators":0,"gateways":0}\n- Systemcluster-Graph: ' + json.dumps(graph)
    amended = invoke(authority, lambda: conversation.begin(addition, context,
        wizard_command={**continuation(request_case, first), 'action': 'AMEND'}))
    assert amended.success, amended.findings
    state = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data['context']
    assert state['wizard_request']['base_prompt'] == prompt
    assert state['agent_wizard_status']['hardware_counts']['sensors'] == 2
    assert state['agent_wizard_status']['system_cluster_graph'] == graph
    branches = state['agent_wizard_status']['system_cluster_assignments'][0]['tree']
    assert branches[0]['name'] == 'Motor'
    assert [leaf['name'] for leaf in branches[0]['sensors']] == ['Temperature', 'Pressure']
    # New members have no fabricated interface or confidence in a status projection.
    assert branches[0]['sensors'][0]['interfaceType'] == ''
    assert branches[0]['sensors'][0]['confidence'] == 0


@pytest.mark.parametrize('prompt', ['Keine Steuerwörter erforderlich.', 'Zeige mir deine Fähigkeiten.', 'Verbinde Motorsteuerung mit HMI.'])
def test_typed_target_has_no_dependency_on_continuation_sentence(prompt):
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'inspect_project'
            return ToolResult(data={'artifact_checks': {'engineering_model': {'complete': True}},
                                    'statuses': {'engineering_model': 'COMPLETE'}})
    context = AgentContext(active_project_id='pytest-typed-target', wizard_request={'target': 'engineering_model'})
    result = asyncio.run(EngineeringAgent(Client()).run(prompt, context))
    assert result['status'] == 'COMPLETED'


def test_zero_delta_amendment_asks_for_model_confirmation_without_a_phantom_proposal():
    calls = []
    class Client:
        async def call(self, name, arguments=None):
            calls.append(name)
            if name == 'inspect_project':
                return ToolResult(data={'artifact_checks': {'engineering_model': {'complete': True}}})
            assert name == 'generate_wizard_model'
            return ToolResult(data={'status': 'MODEL_CONFIRMATION_REQUIRED', 'model_revision': 'model-r1',
                                    'request_revision': 'request-r2', 'run_id': 'wizard-run'})
    context = AgentContext(active_project_id='pytest-typed-target', wizard_request={
        'run_id': 'wizard-run', 'revision': 'request-r2', 'target': 'routing', 'model_review_required': True})
    result = asyncio.run(EngineeringAgent(Client()).run('Bestaetigte Ergaenzung', context))
    assert result['status'] == 'BLOCKED'
    assert not result['proposals']
    question = next(event for event in result['events'] if event['type'] == 'SINGLE_SELECT')
    assert question['metadata']['decision_key'] == 'wizard-model-confirm:request-r2:model-r1'
    assert question['metadata']['wizard_model_confirmation']['model_revision'] == 'model-r1'
    assert [option['id'] for option in question['question']['options']] == ['confirm_current_model', 'refine_requirement']
    assert calls == ['inspect_project', 'generate_wizard_model']


@pytest.mark.parametrize('choice', ['confirm_current_model', 'refine_requirement'])
def test_model_confirmation_is_durable_and_bound_to_both_revisions(request_case, monkeypatch, choice):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    original_get = WorkflowStatusService.get
    def model_complete(service, **kwargs):
        state = original_get(service, **kwargs)
        state['artifact_checks']['engineering_model']['complete'] = True
        return state
    monkeypatch.setattr(WorkflowStatusService, 'get', model_complete)
    monkeypatch.setattr(conversation, 'model_revision', lambda: 'model-r1')
    binding = {'run_id': request_case[2]['run_id'], 'request_revision': accepted['wizard_receipt']['request_revision'],
               'model_revision': 'model-r1'}
    question = InteractiveQuestion(question='Aktuellen Modellstand verwenden?', options=[
        {'id': 'confirm_current_model', 'label': 'Stand bestätigen'}, {'id': 'refine_requirement', 'label': 'Präzisieren'}])
    event = AgentResponse(type='SINGLE_SELECT', question=question, metadata={
        'decision_key': f"wizard-model-confirm:{binding['request_revision']}:model-r1", 'wizard_model_confirmation': binding
    }).model_dump(mode='json', exclude_none=True)
    assert invoke(authority, lambda: conversation.record_event(accepted['run_id'], event)).success
    release(request_case, accepted)
    answer = {'type': 'QUESTION_ANSWER', 'question_id': question.id, 'selected_options': [choice]}
    command = continuation(request_case, accepted)
    automatic = invoke(authority, lambda: conversation.begin('', context, raw_input=answer,
        wizard_command={**command, 'automatic': True}))
    assert automatic.status.value == 'CONFLICT'
    result = invoke(authority, lambda: conversation.begin('', context, raw_input=answer, wizard_command=command))
    assert result.success, result.findings
    request = result.data['context']['wizard_request']
    assert request['model_review_required'] is (choice != 'confirm_current_model')
    assert request['model_refinement_required'] is (choice == 'refine_requirement')
    stored = invoke(authority, conversation.read).data
    key = event['metadata']['decision_key']
    assert stored['answered_questions'][key]['wizard_model_confirmation'] == binding
    release(request_case, result.data)
    # A reload/ordinary resume retains the human decision.
    resumed = invoke(authority, lambda: conversation.begin('', context, wizard_command=continuation(request_case, accepted)))
    assert resumed.success
    assert resumed.data['context']['wizard_request']['model_review_required'] is (choice != 'confirm_current_model')


def test_changed_model_cannot_consume_confirmation_of_older_model(request_case, monkeypatch):
    accepted = start(request_case)
    authority, context, _, _ = request_case
    monkeypatch.setattr(conversation, 'model_revision', lambda: 'model-r1')
    binding = {'run_id': request_case[2]['run_id'], 'request_revision': accepted['wizard_receipt']['request_revision'],
               'model_revision': 'model-r1'}
    question = InteractiveQuestion(question='Stand bestätigen?', options=[
        {'id': 'confirm_current_model', 'label': 'Bestätigen'}, {'id': 'refine_requirement', 'label': 'Präzisieren'}])
    event = AgentResponse(type='SINGLE_SELECT', question=question, metadata={
        'decision_key': f"wizard-model-confirm:{binding['request_revision']}:model-r1", 'wizard_model_confirmation': binding
    }).model_dump(mode='json', exclude_none=True)
    assert invoke(authority, lambda: conversation.record_event(accepted['run_id'], event)).success
    release(request_case, accepted)
    monkeypatch.setattr(conversation, 'model_revision', lambda: 'model-r2')
    result = invoke(authority, lambda: conversation.begin('', context,
        raw_input={'type': 'QUESTION_ANSWER', 'question_id': question.id, 'selected_options': ['confirm_current_model']},
        wizard_command=continuation(request_case, accepted)))
    assert result.status.value == 'CONFLICT'
    wizard = invoke(authority, lambda: WorkflowStatusService(authority.project_id).get(summary=True)).data['context']['agent_wizard_status']
    assert not wizard.get('model_request_revision')


def test_refinement_decision_does_not_regenerate_or_implicitly_confirm_on_resume():
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'inspect_project'
            return ToolResult(data={'artifact_checks': {'engineering_model': {'complete': True}}})
    context = AgentContext(active_project_id='pytest-refinement', wizard_request={
        'target': 'routing', 'model_review_required': True, 'model_refinement_required': True})
    result = asyncio.run(EngineeringAgent(Client()).run('immutable prompt', context))
    assert result['status'] == 'INCOMPLETE'
    assert not result['proposals']
    assert 'Ergänzen' in result['text']


def test_superseded_approved_proposal_cannot_be_applied_or_reviewed(monkeypatch):
    from backend.engineering.agent_tools import proposal_service
    from backend.engineering.db import ConcurrentUpdateError
    contract = {'status': 'APPROVED', 'replacement_proposal_id': 'new-proposal', 'revision': 'approved-revision'}
    monkeypatch.setattr(proposal_service.legacy, 'get_proposal', lambda _: {'engineering_contract': deepcopy(contract)})
    monkeypatch.setattr(proposal_service, 'envelope', lambda row: row['engineering_contract'])
    with pytest.raises(ConcurrentUpdateError, match='ersetzt'):
        proposal_service.apply('old-proposal', actor='human', trace_id='test')
    with pytest.raises(ConcurrentUpdateError, match='ersetzt'):
        proposal_service.review('old-proposal', revision='approved-revision', decision='approve', actor='human', trace_id='test')


def test_chat_command_receipt_is_persisted_and_duplicate_does_not_start_worker(request_case, monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api
    calls = []
    class Agent:
        def __init__(self, *args, **kwargs):
            pass
        async def run(self, prompt, context, **kwargs):
            calls.append((prompt, context.wizard_request['target']))
            return {'context': context.model_dump(), 'status': 'INCOMPLETE', 'text': 'controlled backend result'}
    monkeypatch.setattr(api, 'EngineeringAgent', Agent)
    authority, _, command, prompt = request_case
    client = create_app(testing=True).test_client()
    data = {'prompt': prompt, 'wizard_command': command}
    for duplicate in (False, True):
        response = client.post('/api/engineering/agent/chat', json=data, headers={'X-Project-ID': authority.project_id})
        assert response.status_code == 200, response.json
        events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
        accepted = next(event['wizard_receipt'] for event in events if 'wizard_receipt' in event)
        assert accepted['accepted'] is True and accepted['duplicate'] is duplicate
        assert accepted['operation_id'] == command['operation_id']
    assert calls == [(prompt, WORKFLOW_STEPS[-1])]


def test_migrated_legacy_request_preserves_applied_model(request_case, monkeypatch):
    authority, context, command, prompt = request_case
    original_get = WorkflowStatusService.get
    def model_complete(service, **kwargs):
        state = original_get(service, **kwargs)
        state['artifact_checks']['engineering_model']['complete'] = True
        return state
    def setup():
        WorkflowStatusService(authority.project_id).set_context({'agent_wizard_status': command['wizard_context']})
        state = conversation.read()
        state['current_requirement'] = prompt
        conversation.write(state)
    assert invoke(authority, setup).success
    monkeypatch.setattr(WorkflowStatusService, 'get', model_complete)
    continued = invoke(authority, lambda: conversation.begin('', context, wizard_command={
        'action': 'CONTINUE', 'run_id': command['run_id'], 'operation_id': str(uuid4())}))
    assert continued.success, continued.findings
    assert continued.data['context']['wizard_request']['model_review_required'] is False


def test_cancel_requires_current_typed_request_revision(request_case):
    from backend.app import create_app
    accepted = start(request_case)
    authority, _, command, _ = request_case
    client = create_app(testing=True).test_client()
    url = f'/api/engineering/agent/runs/{command["run_id"]}/cancel'
    response = client.post(url, headers={'X-Project-ID': authority.project_id}, json={'confirmed': True, 'request_revision': 'stale'})
    assert response.status_code == 409
    response = client.post(url, headers={'X-Project-ID': authority.project_id}, json={'confirmed': True,
        'request_revision': accepted['wizard_receipt']['request_revision']})
    assert response.status_code == 200, response.json
    assert response.json['data']['context']['agent_execution']['state'] == 'CANCELED'
