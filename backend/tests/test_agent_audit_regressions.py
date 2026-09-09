"""Complete contracts for the agent defects found in the September audit."""
import asyncio
from datetime import datetime, timezone, timedelta
import threading
from uuid import uuid4

import pytest

from backend.agent_core.api.agent_response import validate_response
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.runtime import ToolAuthority, execute


def scoped(authority, operation):
    result = execute(authority, 'audit_regression', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result
    return result.data


@pytest.mark.parametrize('prompt', ['Lege ein Gateway an.', 'Ändere den Namen des Gateways.', 'Lösche das Gateway.', 'Please create a gateway.', 'Ich brauche ein Gateway.'])
def test_free_form_mutations_cannot_claim_success_without_a_proposal(prompt):
    class Client:
        async def call(self, name, arguments=None):
            return ToolResult(data={'active_step': 'engineering_model'})

        async def tools(self):
            return []

    class Reasoner:
        async def next(self, messages, context, tools):
            return {'text': 'Das Gateway wurde erfolgreich angelegt.', 'calls': [], 'assistant_message': {}}

    result = asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run(prompt, AgentContext(active_project_id='isolated')))
    assert result['status'] == 'INCOMPLETE'
    assert 'erfolgreich angelegt' not in result['text']
    assert not result['proposals']


def test_read_question_still_returns_answer_and_change_proposal_gets_evidence_text():
    class Client:
        async def call(self, name, arguments=None):
            if name in {'generate_data_objects', 'validate_proposal'}:
                return ToolResult(data={'proposal_id': 'p1', 'revision': 'r1', 'status': 'VALIDATED', 'rationale': 'Gateway ergänzen',
                    'assumptions': [], 'changes': [{'action': 'CREATE', 'object_type': 'HardwareNode', 'data': {'name': 'Gateway'}}],
                    'validation_result': {'valid': True}, 'canonical_ids': []})
            return ToolResult(data={'active_step': 'engineering_model'})

        async def tools(self):
            return [{'name': 'generate_data_objects'}]

    class ReadReasoner:
        async def next(self, messages, context, tools):
            return {'text': 'Das Projekt enthält ein Gateway.', 'calls': [], 'assistant_message': {}}

    read = asyncio.run(EngineeringAgent(Client(), reasoner=ReadReasoner()).run('Zeige die vorhandenen Gateways.', AgentContext(active_project_id='isolated')))
    assert read['status'] == 'ANSWERED'
    assert read['text'] == 'Das Projekt enthält ein Gateway.'

    class ChangeReasoner:
        step = 0

        async def next(self, messages, context, tools):
            self.step += 1
            if self.step == 1:
                return {'calls': [{'id': 'call1', 'name': 'generate_data_objects', 'arguments': {}}],
                    'assistant_message': {'role': 'assistant', 'content': ''}}
            return {'text': 'Das Gateway wurde angelegt und übernommen.', 'calls': [], 'assistant_message': {}}

    changed = asyncio.run(EngineeringAgent(Client(), reasoner=ChangeReasoner()).run('Erzeuge neue Hardware.', AgentContext(active_project_id='isolated')))
    assert changed['status'] == 'READY_FOR_REVIEW'
    assert len(changed['proposals']) == 1
    assert 'warten auf deine Freigabe' in changed['text']
    assert 'wurde angelegt' not in changed['text']


def test_heartbeat_actual_thread_keeps_project_lease_beyond_six_minutes(monkeypatch):
    from backend.engineering.agent_tools.api import renew_conversation_lease
    from backend.engineering.project_context import current_project_id

    offset = [0]
    real_now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_now + timedelta(seconds=offset[0])

    monkeypatch.setattr(conversation, 'datetime', Clock)
    authority = ToolAuthority(f'audit-heartbeat-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    started = scoped(authority, lambda: conversation.begin('Analysiere das Projekt.', context))
    errors = []

    def heartbeat():
        try:
            assert current_project_id() == 'default'
            renew_conversation_lease(authority, started['run_id'])
            assert current_project_id() == 'default'
        except Exception as error:
            errors.append(error)

    for seconds in [290, 580]:
        offset[0] = seconds
        thread = threading.Thread(target=heartbeat)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert not errors
    offset[0] = 700
    result = execute(authority, 'competing_turn', Permission.READ_MODEL, {}, lambda _: conversation.begin('Zweiter Auftrag', context))
    assert result.status == 'CONFLICT'
    state = scoped(authority, conversation.read)
    assert state['run_id'] == started['run_id']
    assert datetime.fromisoformat(state['lease_until']) > real_now + timedelta(seconds=700)
    scoped(authority, lambda: conversation.finish(started['run_id']))


def test_missing_heartbeat_ownership_is_checked():
    from backend.engineering.agent_tools.api import renew_conversation_lease
    from backend.engineering.db import ConcurrentUpdateError
    with pytest.raises(ConcurrentUpdateError):
        renew_conversation_lease(ToolAuthority(f'audit-missing-run-{uuid4()}'), str(uuid4()))


def test_heartbeat_renews_while_model_transaction_holds_project_lock():
    from backend.engineering.agent_tools.api import renew_conversation_lease
    from backend.engineering.db import RequestUnit
    authority = ToolAuthority(f'audit-busy-heartbeat-{uuid4()}')
    started = scoped(authority, lambda: conversation.begin('Prüfen', AgentContext(active_project_id=authority.project_id)))
    unit = RequestUnit(authority.project_id)
    errors = []
    def renew():
        try:
            renew_conversation_lease(authority, started['run_id'])
        except Exception as error:
            errors.append(error)
    try:
        unit.acquire()
        thread = threading.Thread(target=renew)
        thread.start()
        thread.join(timeout=3)
        assert not thread.is_alive(), 'Heartbeat is blocked by a long model calculation'
        assert not errors
    finally:
        unit.close()
        thread.join(timeout=5)
    scoped(authority, lambda: conversation.finish(started['run_id']))


def test_real_chat_worker_stops_if_lease_renewal_fails(monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api as module

    class WaitingAgent:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, prompt, context, *, emit, history):
            await asyncio.sleep(2)
            pytest.fail('The agent must be canceled after losing its lease')

    def lost(*args):
        raise RuntimeError('Lease unavailable')

    monkeypatch.setattr(module, 'EngineeringAgent', WaitingAgent)
    monkeypatch.setattr(module, 'renew_conversation_lease', lost)
    monkeypatch.setattr(module, '_HEARTBEAT_SECONDS', 0.02)
    project = f'audit-lost-lease-{uuid4()}'
    response = create_app(testing=True).test_client().post('/api/engineering/agent/chat',
        headers={'X-Project-ID': project}, json={'prompt': 'Analysiere das Projekt.', 'context': {}})
    assert response.status_code == 200
    assert 'BLOCKED' in response.text
    assert 'Gesprächssperre' in response.text
    assert scoped(ToolAuthority(project), conversation.read)['run_id'] is None


def test_generic_progress_preserves_workload_through_resume():
    authority = ToolAuthority(f'audit-progress-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    started = scoped(authority, lambda: conversation.begin('Prüfe diesen Auftrag.', context))
    workload = str(uuid4())
    for payload in [{'workload_id': workload, 'valid': 1, 'requested': 2}, {'completed': 1, 'total': 12}, {'completed': 2, 'total': 12}]:
        event = validate_response({'type': 'PROGRESS', 'workload': payload})
        scoped(authority, lambda: conversation.record_event(started['run_id'], event))
    scoped(authority, lambda: conversation.finish(started['run_id']))
    resumed = scoped(authority, lambda: conversation.begin('', context, {'type': 'RESUME'}))
    assert resumed['context']['current_workload'] == workload
    scoped(authority, lambda: conversation.finish(resumed['run_id']))


def test_server_history_restores_only_proposal_references_for_large_and_legacy_content():
    authority = ToolAuthority(f'audit-history-{uuid4()}')
    proposal = {'proposal_id': str(uuid4()), 'proposal_type': 'WIZARD_ENGINEERING_MODEL', 'revision': 'r1', 'status': 'VALIDATED',
        'rationale': 'Alle Änderungen prüfen', 'assumptions': [], 'validation_result': {}, 'canonical_ids': [],
        'changes': [{'action': 'CREATE', 'object_type': 'Signal', 'data': {'name': f'Signal{index}'}} for index in range(3000)]}
    event = validate_response({'type': 'APPROVAL', 'proposal': proposal})
    messages = [{'id': 'reply', 'role': 'assistant', 'parts': [{'type': 'data-engineering', 'data': event}]}]
    scoped(authority, lambda: conversation.history(messages))
    restored = scoped(authority, conversation.history)['messages'][0]['parts'][0]['data']['proposal']
    assert restored['content_state'] == 'REFERENCE'
    assert restored['change_count'] == 3000
    assert restored['changes'] == []
    assert len(proposal['changes']) == 3000
