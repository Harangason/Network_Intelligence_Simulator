import asyncio
import threading
from uuid import uuid4

from backend.app import create_app
from backend.engineering.agent_tools import api
from backend.engineering.agent_tools.run_status import WizardExecutionTracker
from backend.engineering.workflow.service import WorkflowStatusService


def test_cancellation_requires_confirmation_and_is_durable():
    project, run_id = f'cancel-test-{uuid4()}', str(uuid4())
    tracker = WizardExecutionTracker(project, run_id)
    tracker.started()
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': project}
    url = f'/api/engineering/agent/runs/{run_id}/cancel'
    assert client.post(url, headers=headers, json={}).status_code == 400
    assert client.post(url, headers={'X-Project-ID': 'different-project'}, json={'confirmed': True}).status_code == 409
    for _ in range(2):
        response = client.post(url, headers=headers, json={'confirmed': True})
        assert response.status_code == 200, response.json
        assert response.json['data']['context']['agent_execution']['state'] == 'CANCELED'
    tracker.heartbeat()
    tracker.finished({'status': 'COMPLETED'})
    tracker.failed('late error')
    assert WorkflowStatusService(project).get(summary=True)['context']['agent_execution']['state'] == 'CANCELED'


def test_cancellation_interrupts_hanging_server_worker(monkeypatch):
    started, canceled = threading.Event(), threading.Event()
    class HangingAgent:
        def __init__(self, *args, **kwargs):
            pass
        async def run(self, *args, **kwargs):
            started.set()
            kwargs['emit']({'type': 'PROGRESS', 'text': 'Testlauf wartet.'})
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                canceled.set()
                raise
    monkeypatch.setattr(api, 'EngineeringAgent', HangingAgent)
    project, run_id = f'cancel-worker-{uuid4()}', str(uuid4())
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': project}
    response = client.post('/api/engineering/agent/chat', headers=headers,
        json={'prompt': f'- Lauf-ID: {run_id}\nAuftrag'}, buffered=False)
    assert response.status_code == 200
    assert started.wait(3)
    response.close()
    result = client.post(f'/api/engineering/agent/runs/{run_id}/cancel', headers=headers, json={'confirmed': True})
    assert result.status_code == 200, result.json
    assert canceled.wait(3), 'Backend task must not keep running after stream cancellation'
