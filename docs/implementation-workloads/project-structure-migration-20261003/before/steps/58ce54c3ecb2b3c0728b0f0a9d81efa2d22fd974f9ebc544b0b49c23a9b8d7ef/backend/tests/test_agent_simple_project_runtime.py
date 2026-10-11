"""Free chat project intent must reach a reviewed canonical model change."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from uuid import uuid4

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools import conversation, model, proposal_service
from backend.engineering.agent_tools.project_draft import parse_requirement
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.simulator_engineering_mcp.server import create_server


PROMPT = 'Erstelle ein einfaches Projekt mit einem Controller, einem Druck Sensor und einem Ventil Aktor.'


def scoped(authority, operation):
    result = execute(authority, 'simple_project_acceptance', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings
    return result.data


def test_spaced_device_names_preserve_explicit_inventory():
    parsed = parse_requirement(PROMPT)
    assert [(item['name'], item['role']) for item in parsed['devices']] == [
        ('Drucksensor1', 'SENSOR'), ('Ventilaktor1', 'ACTUATOR'), ('Controller1', 'CONTROLLER')]


def test_free_chat_project_proposal_and_reviewed_apply_are_real():
    authority = ToolAuthority('simple-project-' + uuid4().hex)
    saved = []

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client,
                persist=lambda value: saved.append(deepcopy(value))).execute(
                    PROMPT, AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['runtime']['goal']['goal_type'] == 'CREATE_PROJECT'
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    assert not result['runtime']['completed']
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal
    assert any(finding['code'] == 'DEVICE_STATUS_MISSING' and finding['severity'] == 'OPEN'
               for finding in proposal['validation_result']['findings'])
    assert len(proposal['changes']) == 7
    assert {change['object_type'] for change in proposal['changes']} == {
        'HardwareNode', 'Function', 'DataObject'}
    assert not any(change['object_type'] in {'Interface', 'HardwareNetworkInterface', 'Network'}
                   for change in proposal['changes'])
    assert scoped(authority, lambda: model.objects('HardwareNode')) == []

    def review_and_apply():
        state = conversation.read()
        workload = deepcopy(saved[-1])
        state.setdefault('engineering_workloads', {})[workload['workload_id']] = workload
        conversation.write(state)
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'],
                                decision='approve', actor='human-test', trace_id=str(uuid4()))
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4()))
        assert conversation.reconcile_runtime_model_apply(applied)
        return applied

    applied = scoped(authority, review_and_apply)
    assert applied['status'] == 'APPLIED'
    hardware = scoped(authority, lambda: model.objects('HardwareNode'))
    assert len(hardware) == 3
    assert {item['name'] for item in hardware} == {'Controller1', 'Drucksensor1', 'Ventilaktor1'}
    functions = scoped(authority, lambda: model.objects('Function'))
    assert {item['name'] for item in functions} == {'PressureAcquire', 'ValveControl'}
    state = scoped(authority, conversation.read)
    goal = state['engineering_workloads'][saved[-1]['workload_id']]
    assert goal['status'] == 'COMPLETED'
    assert goal['result']['model_revision_after']
    assert len(goal['result']['canonical_ids']) == 7


def test_chat_http_review_and_apply_complete_the_persisted_goal(monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api as api_module

    class OfflineReasoner:
        async def next(self, *args):
            raise AssertionError('The explicit simple project must not require an LLM')

        async def close(self):
            pass

    monkeypatch.setattr(api_module, 'LocalEngineeringReasoner', OfflineReasoner)
    authority = ToolAuthority('http-simple-project-' + uuid4().hex)
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': authority.project_id}
    response = client.post('/api/engineering/agent/chat', headers=headers,
                           json={'prompt': PROMPT, 'context': {}}, buffered=True)
    assert response.status_code == 200, response.data
    events = [json.loads(line) for line in response.data.decode().splitlines() if line.strip()]
    proposal = next(event['proposal'] for event in events if event.get('type') == 'APPROVAL')
    assert proposal['status'] == 'VALIDATED'
    assert scoped(authority, lambda: model.objects('HardwareNode')) == []
    csrf = client.get('/api/engineering/agent/review-session').json['csrf_token']
    headers.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed'})
    path = '/api/engineering/agent/proposals/' + proposal['proposal_id']
    reviewed = client.post(path + '/review', headers=headers,
                           json={'revision': proposal['revision'], 'decision': 'approve'})
    assert reviewed.status_code == 200, reviewed.json
    applied = client.post(path + '/apply', headers=headers, json={})
    assert applied.status_code == 200, applied.json
    assert len(scoped(authority, lambda: model.objects('HardwareNode'))) == 3
    state = scoped(authority, conversation.read)
    workload = state['engineering_workloads'][state['active_engineering_workload_id']]
    assert workload['status'] == 'COMPLETED'
    assert len(workload['result']['canonical_ids']) == 7
