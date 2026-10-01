"""Structured concurrency must not erase an actionable dependency failure."""
import json
from uuid import uuid4

import httpx
import pytest

from backend.agent_core.runtime.recovery import RecoveryManager


@pytest.mark.parametrize('error,code', [
    (httpx.ConnectError('unavailable'), 'ENGINEERING_REASONER_UNAVAILABLE'),
    (httpx.ReadTimeout('late'), 'ENGINEERING_EXECUTION_TIMEOUT'),
    (TimeoutError('late'), 'ENGINEERING_EXECUTION_TIMEOUT'),
    (PermissionError('approval required'), 'ENGINEERING_AUTHORIZATION_REQUIRED'),
])
def test_nested_homogeneous_groups_preserve_failure(error, code):
    group = ExceptionGroup('outer', [ExceptionGroup('inner', [error]), error])
    result = RecoveryManager().classify(group)
    assert result['code'] == code
    assert result == RecoveryManager().classify(error)


@pytest.mark.parametrize('errors', [
    [httpx.ConnectError('unavailable'), ValueError('invalid input')],
    [httpx.ConnectError('unavailable'), PermissionError('approval required')],
    [ValueError('unknown'), RuntimeError('unknown')],
])
def test_mixed_or_unknown_groups_remain_unclassified(errors):
    assert RecoveryManager().classify(ExceptionGroup('mixed', errors))['code'] == 'ENGINEERING_ASSISTANT_EXECUTION_DEFECT'


def test_actual_mcp_group_keeps_persisted_failure_in_stream(monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api as agent_api

    class UnavailableAgent:
        def __init__(self, client, reasoner=None):
            pass

        async def run(self, prompt, context, *, emit, history):
            raise httpx.ConnectError('controlled isolated test dependency failure')

    monkeypatch.setattr(agent_api, 'EngineeringAgent', UnavailableAgent)
    project = 'recovery-group-' + uuid4().hex
    client = create_app(testing=True).test_client()
    response = client.post('/api/engineering/agent/chat', headers={'X-Project-ID': project},
                           json={'prompt': 'Lege eine Diagnoseabfrage an.', 'context': {}}, buffered=True)
    assert response.status_code == 200
    assert response.mimetype == 'application/x-ndjson'
    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines() if line.strip()]
    error = next(event for event in events if event.get('type') == 'ERROR')
    assert error['metadata']['failure_code'] == 'ENGINEERING_REASONER_UNAVAILABLE'
    assert error['metadata']['failure_category'] == 'DEPENDENCY_UNAVAILABLE'
    assert 'nicht erreichbar' in error['text']
    snapshot = client.get('/api/engineering/agent/conversation', headers={'X-Project-ID': project}).get_json()['data']
    workload = snapshot['engineering_workloads'][snapshot['active_engineering_workload_id']]
    assert workload['failure']['code'] == error['metadata']['failure_code']
    assert workload['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
