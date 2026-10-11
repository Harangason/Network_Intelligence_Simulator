"""The finish HTTP command must not trust complete cards over pending work."""
from copy import deepcopy

import pytest

from backend.app import create_app
from backend.engineering.agent_tools import conversation
from backend.engineering.workflow.service import WorkflowStatusService


@pytest.mark.parametrize('case', ['question', 'approval', 'new_revision', 'blocked', 'ready'])
def test_finish_checks_current_request_and_pending_decisions(monkeypatch, case):
    workflow = {'statuses': {'engineering_model': 'COMPLETE', 'routing': 'COMPLETE'}, 'context': {
        'wizard_request': {'version': 2, 'revision': 'current-revision'},
        'agent_wizard_status': {'run_id': 'current-run', 'model_request_revision': 'current-revision',
                                'scope_ids': ['engineering_model', 'routing']},
        'agent_execution': {'state': 'COMPLETED'},
    }}
    state = {'current_question': None, 'questions': {}, 'pending_approvals': []}
    if case == 'question':
        state.update(current_question='confirmation', questions={'confirmation': {'status': 'OPEN'}})
    elif case == 'approval':
        state['pending_approvals'] = ['current-model-proposal']
    elif case == 'new_revision':
        workflow['context']['agent_wizard_status']['model_request_revision'] = 'previous-revision'
    elif case == 'blocked':
        workflow['context']['agent_execution']['state'] = 'BLOCKED'
    writes = []
    monkeypatch.setattr(WorkflowStatusService, 'get', lambda *_args, **_kwargs: deepcopy(workflow))
    monkeypatch.setattr(conversation, 'inspect', lambda: deepcopy(state))
    def save(_self, context, **_kwargs):
        writes.append(context)
        return {**workflow, 'context': {**workflow['context'], **context}}
    monkeypatch.setattr(WorkflowStatusService, 'set_context', save)
    response = create_app(testing=True).test_client().post(
        '/api/engineering/agent/runs/current-run/finish', headers={'X-Project-ID': 'finish-contract-test'},
        json={'request_revision': 'current-revision'})
    assert response.status_code == (200 if case == 'ready' else 409), response.json
    assert writes == ([{'agent_wizard_status': None}] if case == 'ready' else [])
