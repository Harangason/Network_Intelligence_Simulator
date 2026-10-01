"""Browser polling reads committed state; command validation remains authoritative."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import threading
from uuid import uuid4

from psycopg.types.json import Jsonb
import pytest

from backend.app import create_app
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.db import RequestUnit, get_connection
from backend.engineering.project_context import current_project_id
from backend.engineering.workflow.service import WorkflowStatusService


pytestmark = pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'),
    reason='isolated verification database required')


@pytest.fixture
def stored_conversation():
    project = 'conversation-read-' + uuid4().hex
    workflow = WorkflowStatusService(project).get(summary=True)
    question_id = str(uuid4())
    run_id = str(uuid4())
    state = {
        'current_requirement': 'Weiter mit dem bestehenden Modell.',
        'current_question': question_id,
        'questions': {question_id: {
            'id': question_id, 'status': 'OPEN', 'model_revision': 'older-model',
            'expires_at': '2000-01-01T00:00:00+00:00', 'question': 'Anschluss wählen?',
            'options': [{'id': 'can', 'label': 'CAN'}],
        }},
        'decisions': {'finding': {'status': 'ACCEPTED_RISK', 'review_on_change': True,
            'model_revision': 'older-model', 'rationale': 'Entwurf'}},
        'pending_approvals': [str(uuid4())], 'active_proposal': str(uuid4()),
        'run_id': run_id, 'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        'wizard_request': {'run_id': run_id, 'revision': 'accepted-request'},
        'wizard_operations': {'continue-1': {'run_id': run_id, 'status': 'RUNNING'}},
        'selected_context': {'active_view': 'engineering', 'selected_object_refs': []},
        'ui_history': [{'role': 'user', 'parts': [{'type': 'text', 'text': 'history-only'}]}],
    }
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_agent_conversations(project_id, state) VALUES (%s,%s)',
            (project, Jsonb(state)))
        connection.execute(
            'INSERT INTO engineering_simulation_snapshots(project_id, source_versions, configuration, status, job_id) '
            "VALUES (%s,%s,%s,'RUNNING',%s)",
            (project, Jsonb(workflow['versions']), Jsonb({'scope': 'ALL'}), run_id))
    return project, state


def persisted(project):
    tables = ('engineering_agent_conversations', 'engineering_workflow_projects',
        'engineering_simulation_snapshots', 'engineering_workflow_events', 'engineering_agent_audit')
    with get_connection() as connection:
        return {table: connection.execute(f'SELECT * FROM {table} WHERE project_id=%s', (project,)).fetchall()
            for table in tables}


def test_get_returns_pending_and_running_committed_state_without_reconcile_or_model_hash(stored_conversation, monkeypatch):
    project, state = stored_conversation
    before = persisted(project)
    caller_scope = current_project_id()
    def forbidden():
        raise AssertionError('A conversation GET must not hash or load the complete model.')
    monkeypatch.setattr(conversation, 'model_revision', forbidden)
    client = create_app(testing=True).test_client()
    for _ in range(3):
        response = client.get('/api/engineering/agent/conversation', headers={'X-Project-ID': project})
        assert response.status_code == 200, response.get_json()
        assert response.headers['Cache-Control'] == 'no-store'
        result = response.get_json()
        assert result['success'] and result['validation_status'] == 'NOT_EVALUATED'
        assert result['data']['conversation_id'] == project
        assert 'ui_history' not in result['data']
        for key, expected in state.items():
            if key != 'ui_history':
                assert result['data'][key] == expected
    assert current_project_id() == caller_scope
    # Includes modified_at, versions, snapshot status and all audit/event rows.
    assert persisted(project) == before


def test_unknown_project_get_creates_no_conversation_workflow_or_audit():
    project = 'conversation-unknown-' + uuid4().hex
    before = persisted(project)
    assert not any(before.values())
    response = create_app(testing=True).test_client().get('/api/engineering/agent/conversation',
        headers={'X-Project-ID': project})
    assert response.status_code == 200
    assert response.get_json()['data'] == {
        'conversation_id': project, 'current_question': None, 'answered_questions': {}, 'questions': {},
        'active_proposal': None, 'active_workload': None, 'pending_approvals': [], 'selected_context': {}, 'decisions': {},
    }
    assert persisted(project) == before


def test_get_finishes_while_same_project_writer_holds_advisory_and_conversation_locks(stored_conversation):
    project, state = stored_conversation
    app = create_app(testing=True)
    finished = threading.Event()
    result = {}
    def read():
        try:
            response = app.test_client().get('/api/engineering/agent/conversation', headers={'X-Project-ID': project})
            result.update(status=response.status_code, body=response.get_json())
        except Exception as error:
            result['error'] = error
        finally:
            finished.set()
    unit = RequestUnit(project)
    worker = threading.Thread(target=read, daemon=True)
    try:
        # This is the same lock path used by an active agent command.
        with get_connection() as writer:
            changed = {**state, 'current_requirement': 'uncommitted worker result'}
            writer.execute('UPDATE engineering_agent_conversations SET state=%s, modified_at=now() WHERE project_id=%s',
                (Jsonb(changed), project))
        worker.start()
        assert finished.wait(3), 'Conversation GET waited for the active project writer.'
        assert result.get('status') == 200, result
        assert result['body']['data']['current_requirement'] == state['current_requirement']
        unit.finish(True)
    finally:
        unit.close()
        worker.join(5)
    assert not worker.is_alive()
    assert conversation.snapshot(project)['current_requirement'] == changed['current_requirement']


def test_snapshot_is_project_scoped_and_caller_edits_do_not_alias_persisted_state(stored_conversation):
    project, state = stored_conversation
    before = persisted(project)
    foreign = 'conversation-foreign-' + uuid4().hex
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_agent_conversations(project_id,state) VALUES (%s,%s)',
            (foreign, Jsonb({'current_requirement': 'foreign requirement'})))
    client = create_app(testing=True).test_client()
    snapshot = client.get('/api/engineering/agent/conversation', headers={'X-Project-ID': project}).get_json()['data']
    snapshot['questions'].clear()
    other = client.get('/api/engineering/agent/conversation', headers={'X-Project-ID': foreign}).get_json()['data']
    assert other['current_requirement'] == 'foreign requirement'
    assert other['questions'] == {}
    assert conversation.snapshot(project)['questions'] == state['questions']
    assert persisted(project) == before


def test_command_still_rejects_a_stale_question_after_read_only_polling(stored_conversation):
    project, state = stored_conversation
    state = deepcopy(state)
    state.update(run_id=None, lease_until=None, pending_approvals=[])
    with get_connection() as connection:
        connection.execute('UPDATE engineering_agent_conversations SET state=%s WHERE project_id=%s',
            (Jsonb(state), project))
    client = create_app(testing=True).test_client()
    polled = client.get('/api/engineering/agent/conversation', headers={'X-Project-ID': project}).get_json()['data']
    assert polled['questions'][state['current_question']]['status'] == 'OPEN'
    authority = ToolAuthority(project)
    context = AgentContext(active_project_id=project, active_view='engineering')
    answer = {'type': 'QUESTION_ANSWER', 'question_id': state['current_question'], 'selected_options': ['can']}
    result = execute(authority, 'answer_after_poll', Permission.READ_MODEL, {},
        lambda _: conversation.begin('', context, answer))
    assert not result.success and result.status == 'CONFLICT'
    assert 'nicht mehr offen' in result.findings[0]['message']
    assert conversation.snapshot(project)['answered_questions'] == {}
