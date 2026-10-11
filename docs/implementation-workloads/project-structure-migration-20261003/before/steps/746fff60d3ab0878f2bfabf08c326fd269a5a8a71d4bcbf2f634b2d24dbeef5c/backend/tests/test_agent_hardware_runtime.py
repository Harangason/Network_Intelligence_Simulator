"""Free text -> real MCP -> proposal -> reviewed SQL mutation; no LLM needed."""
import asyncio
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.agent_core.runtime.hardware_intent import simple_hardware_intent
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools import proposal_service, model
from backend.simulator_engineering_mcp.server import create_server


class UnavailableReasoner:
    async def next(self, *args):
        raise AssertionError('Simple hardware must not depend on model inference')


def scoped(authority, operation):
    result = execute(authority, 'runtime_acceptance', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings
    return result.data


@pytest.mark.parametrize('device,context,kind', [
    ('ECU', 'Fahrzeugs', 'ECU'), ('Controller', 'Roboters', 'EmbeddedController'),
    ('PLC', 'Anlage', 'PLC'),
])
def test_free_chat_hardware_reaches_review_and_real_canonical_apply(device, context, kind):
    prompt = f'Erstelle eine {device} für die Datenerfassung ' + ('der ' if context == 'Anlage' else 'des ') + context
    authority = ToolAuthority('hardware-chat-' + uuid4().hex)
    saved = []

    async def invoke(request=prompt, state=None):
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=UnavailableReasoner(),
                persist=lambda value: saved.append(value)).execute(request, AgentContext(active_project_id=authority.project_id), saved_state=state)

    result = asyncio.run(invoke())
    assert result['runtime']['status'] == 'WAITING_FOR_ENGINEERING_DECISION'
    assert not result['proposals']
    workload = saved[-1]
    state = {'active_engineering_workload_id': workload['workload_id'], 'engineering_workloads': {workload['workload_id']: workload}}
    reply = 'Statusanschluss I2C, Statuszyklus 100 ms'
    result = asyncio.run(invoke(reply, state))
    assert saved[-1]['workload_id'] == workload['workload_id']
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', [(e.get('text'), e.get('metadata')) for e in result['events']]
    assert not result['runtime']['completed']
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal
    data = proposal['changes'][0]['data']
    assert data['device_type'] == kind
    assert not data.get('domain')
    assert scoped(authority, lambda: {'items': model.objects('HardwareNode')})['items'] == []
    full_prompt = prompt + '. ' + reply
    retry = asyncio.run(invoke(full_prompt))
    assert retry['proposals'][0]['proposal_id'] == proposal['proposal_id']

    def approve_apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve',
                                actor='human-test', trace_id=str(uuid4()))
        return proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4()))
    applied = scoped(authority, approve_apply)
    assert applied['status'] == 'APPLIED'
    hardware = scoped(authority, lambda: {'items': model.objects('HardwareNode')})['items']
    assert len(hardware) == 1
    assert hardware[0]['device_type'] == kind
    assert hardware[0]['description'] == full_prompt
    ports = scoped(authority, lambda: {'items': model.objects('HardwareNetworkInterface')})['items']
    assert len(ports) == 1 and ports[0]['technology'] == 'I2C'
    resumed = asyncio.run(invoke(full_prompt))
    assert resumed['proposals'] == []
    assert not resumed['runtime']['completed']  # Data acquisition still needs actual bindings.
    assert len(scoped(authority, lambda: {'items': model.objects('HardwareNode')})['items']) == 1
    other = ToolAuthority('other-' + uuid4().hex)
    assert scoped(other, lambda: {'items': model.objects('HardwareNode')})['items'] == []


@pytest.mark.parametrize('prompt', [
    'Erstelle zwei ECUs.', 'Erstelle eine ECU mit CAN-FD.',
    'Erstelle eine ECU und lösche alle Sensoren.',
    'Lege eine ECU an, die alle 30 Sekunden die Stellgliedpositionen abfragt.',
    'Erstelle keine ECU.', 'Wie erstelle ich eine ECU?',
])
def test_richer_or_negated_requests_are_not_partially_executed(prompt):
    assert simple_hardware_intent(prompt) is None


def test_planner_timeout_is_classified_and_persisted_without_success():
    class TimeoutReasoner:
        async def next(self, *args):
            raise TimeoutError()
    authority = ToolAuthority('timeout-chat-' + uuid4().hex)
    saved = []
    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=TimeoutReasoner(),
                persist=lambda value: saved.append(value)).execute(
                    'Vergleiche die möglichen Controllerarchitekturen.', AgentContext(active_project_id=authority.project_id))
    result = asyncio.run(invoke())
    assert result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    assert not result['runtime']['completed']
    assert saved[-1]['failure']['code'] == 'ENGINEERING_EXECUTION_TIMEOUT'
    assert saved[-1]['failure']['retryable'] is True
    assert saved[0]['workload_id'] == saved[-1]['workload_id']
    assert sum(e.get('metadata', {}).get('recovery_code') == 'PLANNING_RETRY' for e in result['events']) == 1


def test_read_only_classification_is_not_a_hardware_creation_capability():
    from backend.agent_core.runtime.capability_registry import CapabilityRegistry
    from backend.agent_core.runtime.goal_resolver import GoalType
    result = CapabilityRegistry().resolve(GoalType.CREATE_HARDWARE, {'classify_device', 'get_device_capabilities'})
    assert not result['available']


def test_followup_cannot_reuse_another_projects_request():
    from backend.agent_core.runtime.hardware_intent import resume_hardware_request
    reply = 'Statusanschluss I2C, Statuszyklus 100 ms'
    assert resume_hardware_request(reply, {'active_project_id': 'other', 'active_workload': {
        'project_id': 'original', 'status': 'WAITING_FOR_ENGINEERING_DECISION', 'workload_id': 'old',
        'goal': {'goal_type': 'CREATE_HARDWARE', 'original_request': 'Erstelle eine ECU'},
    }}) == (reply, None)


def test_real_chat_endpoint_preserves_hardware_followup_and_review(monkeypatch):
    import json
    from backend.app import create_app
    from backend.engineering.agent_tools import api as api_module, conversation

    class OfflineReasoner(UnavailableReasoner):
        async def close(self):
            pass
    monkeypatch.setattr(api_module, 'LocalEngineeringReasoner', OfflineReasoner)
    authority = ToolAuthority('http-hardware-' + uuid4().hex)
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': authority.project_id}
    def chat(prompt):
        response = client.post('/api/engineering/agent/chat', headers=headers,
                               json={'prompt': prompt, 'context': {}}, buffered=True)
        assert response.status_code == 200, response.data
        return [json.loads(line) for line in response.data.decode().splitlines() if line.strip()]
    events = chat('Erstelle eine ECU für die Datenerfassung des Fahrzeugs')
    assert any(e.get('status') == 'WAITING_FOR_ENGINEERING_DECISION' for e in events), events
    stored = scoped(authority, conversation.read)
    workload_id = stored['active_engineering_workload_id']
    # A new HTTP client represents a reload; follow-up context comes from SQL.
    client = create_app(testing=True).test_client()
    events = chat('Statusanschluss I2C, Statuszyklus 100 ms')
    proposals = [e['proposal'] for e in events if e.get('proposal')]
    assert proposals, events
    proposal = proposals[0]
    assert proposal['status'] == 'VALIDATED'
    assert scoped(authority, conversation.read)['active_engineering_workload_id'] == workload_id
    csrf = client.get('/api/engineering/agent/review-session').json['csrf_token']
    headers.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed'})
    path = '/api/engineering/agent/proposals/' + proposal['proposal_id']
    reviewed = client.post(path + '/review', headers=headers, json={'revision': proposal['revision'], 'decision': 'approve'})
    assert reviewed.status_code == 200, reviewed.json
    applied = client.post(path + '/apply', headers=headers, json={})
    assert applied.status_code == 200, applied.json
    assert len(scoped(authority, lambda: {'items': model.objects('HardwareNode')})['items']) == 1
