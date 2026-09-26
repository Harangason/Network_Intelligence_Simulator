"""A free chat rate change must persist and recalculate the same project."""
from __future__ import annotations

import asyncio
import json
import pytest
from copy import deepcopy
from uuid import uuid4

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools import conversation, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.workflow.service import WorkflowStatusService
from backend.simulator_engineering_mcp.server import create_server


PROMPT = 'Ändere das LIN-Netz auf 19,2 kbit/s und berechne alles neu.'


def scoped(authority, operation):
    result = execute(authority, 'lin_rate_acceptance', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings
    return result.data


@pytest.mark.parametrize('prompt', [
    PROMPT,
    'Ändere das LIN-Netz auf 19,2 kbit/s und prüfe alle abhängigen Berechnungen.',
])
def test_reviewed_lin_rate_change_recalculates_capacity_timing_and_preflight(prompt):
    authority = ToolAuthority('lin-rate-' + uuid4().hex)
    parameters = {'industry': 'custom', 'technology': 'LIN', 'bitrate': 9600,
                  'cycle_ms': 100, 'payload_bytes': 1, 'queue_size': 10,
                  'formats': ['LIN'], 'warning_threshold': 60,
                  'critical_threshold': 75, 'overload_threshold': 90,
                  'networks': [{'id': 'lin-main', 'name': 'LIN_Main',
                                'technology': 'LIN', 'bitrate': 9600}]}
    scoped(authority, lambda: WorkflowStatusService(authority.project_id).save_parameters(parameters))
    saved = []

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client,
                persist=lambda value: saved.append(deepcopy(value))).execute(
                    prompt, AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['runtime']['goal']['goal_type'] == 'CHANGE_CONFIGURATION'
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal
    assert proposal['changes'][0]['data']['bitrate'] == 19200
    assert scoped(authority, lambda: WorkflowStatusService(authority.project_id).get()['parameters']['networks'][0]['bitrate']) == 9600

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
    assert scoped(authority, lambda: WorkflowStatusService(authority.project_id).get()['parameters']['networks'][0]['bitrate']) == 19200
    dependent = applied['dependent_results']
    assert dependent['capacity_snapshot_id']
    assert dependent['preflight_snapshot_id']
    assert dependent['bitrate_bps'] == 19200
    state = scoped(authority, conversation.read)
    workload = state['engineering_workloads'][saved[-1]['workload_id']]
    assert_incomplete_calculations(workload)
    assert workload['result']['model_revision_after']


def test_http_chat_review_and_apply_expose_recalculation_to_frontend(monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api as api_module

    class OfflineReasoner:
        async def next(self, *args):
            raise AssertionError('The explicit LIN command must not require an LLM')

        async def close(self):
            pass

    monkeypatch.setattr(api_module, 'LocalEngineeringReasoner', OfflineReasoner)
    authority = ToolAuthority('http-lin-rate-' + uuid4().hex)
    scoped(authority, lambda: WorkflowStatusService(authority.project_id).save_parameters({
        'industry': 'custom', 'technology': 'LIN', 'bitrate': 9600,
        'cycle_ms': 100, 'payload_bytes': 1, 'queue_size': 10,
        'formats': ['LIN'], 'warning_threshold': 60,
        'critical_threshold': 75, 'overload_threshold': 90,
        'networks': [{'id': 'lin-main', 'name': 'LIN_Main', 'technology': 'LIN', 'bitrate': 9600}]}))
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': authority.project_id}
    response = client.post('/api/engineering/agent/chat', headers=headers,
                           json={'prompt': PROMPT, 'context': {}}, buffered=True)
    assert response.status_code == 200, response.data
    events = [json.loads(line) for line in response.data.decode().splitlines() if line.strip()]
    proposal = next(item['proposal'] for item in events if item.get('type') == 'APPROVAL')
    assert proposal['changes'][0]['data']['bitrate'] == 19200
    csrf = client.get('/api/engineering/agent/review-session').json['csrf_token']
    headers.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed'})
    path = '/api/engineering/agent/proposals/' + proposal['proposal_id']
    reviewed = client.post(path + '/review', headers=headers,
                           json={'revision': proposal['revision'], 'decision': 'approve'})
    assert reviewed.status_code == 200, reviewed.json
    applied = client.post(path + '/apply', headers=headers, json={})
    assert applied.status_code == 200, applied.json
    assert applied.json['data']['dependent_results']['bitrate_bps'] == 19200
    assert applied.json['data']['dependent_results']['capacity_snapshot_id']
    refreshed = client.get(path + '?view=status', headers={'X-Project-ID': authority.project_id})
    assert refreshed.status_code == 200, refreshed.json
    assert refreshed.json['data']['dependent_results']['preflight_snapshot_id']
    state = scoped(authority, conversation.read)
    workload = state['engineering_workloads'][state['active_engineering_workload_id']]
    assert_incomplete_calculations(workload)
    assert refreshed.json['data']['dependent_results']['completion'] == workload['result']['completion']


def assert_incomplete_calculations(workload):
    # This fixture has only a network parameter, no routed communication.
    # EA-04 requires actual recalculation evidence, not just snapshot existence.
    assert workload['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    assert workload['result']['status'] == 'APPLIED'
    completion = workload['result']['completion']
    assert completion['completed'] is False
    assert completion['achieved_outcomes'] == ['configuration_persisted', 'preflight_rerun']
    assert completion['missing_outcomes'] == ['capacity_recalculated', 'timing_recalculated']
    assert completion['failure']['code'] == 'DEPENDENT_CALCULATION_INCOMPLETE'
    assert any(item['code'] == 'CAPACITY_NO_ROUTES' for item in completion['failure']['capacity_findings'])


@pytest.mark.parametrize('case,missing', [
    ('verified', []),
    ('deadline_violation', []),
    ('empty', ['capacity_recalculated', 'timing_recalculated']),
    ('source_incomplete', ['capacity_recalculated', 'timing_recalculated']),
    ('capacity_unverified', ['capacity_recalculated']),
    ('route_timing_unverified', ['timing_recalculated']),
    ('network_timing_unverified', ['timing_recalculated']),
    ('stale', ['capacity_recalculated', 'timing_recalculated']),
    ('unrelated_preflight', ['preflight_rerun']),
    ('unknown_outcome', ['simulation_passed']),
])
def test_configuration_completion_requires_calculation_evidence(case, missing):
    """Component decision matrix; these snapshots are not E2E evidence."""
    from backend.agent_core.runtime.completion import CompletionEvaluator
    from backend.agent_core.runtime.goal_resolver import GoalResolver

    goal = GoalResolver().resolve(PROMPT).model_dump(mode='json')
    capacity = {'snapshot_id': 'capacity-new', 'status': 'APPROVED', 'findings': [],
                'results': {'networks': [{'capacity_verified': True, 'timing_verified': True}],
                            'routes': [{'timing_verified': True}]}}
    preflight = {'snapshot_id': 'preflight-new', 'capacity_snapshot_id': 'capacity-new',
                 'preflight_status': 'READY', 'ready_for_simulation': True}
    if case == 'deadline_violation':
        capacity.update(status='ERROR', findings=[{'code': 'TIMING_LATENCY_EXCEEDED', 'severity': 'ERROR'}])
        capacity['results']['routes'][0]['requirement_status'] = 'FAIL'
        preflight.update(preflight_status='BLOCKED', ready_for_simulation=False)
    elif case == 'empty':
        capacity['results'].update(networks=[], routes=[])
    elif case == 'source_incomplete':
        capacity['findings'] = [{'code': 'CAPACITY_SOURCE_NOT_READY', 'severity': 'ERROR'}]
    elif case == 'capacity_unverified':
        capacity['results']['networks'][0]['capacity_verified'] = False
    elif case == 'route_timing_unverified':
        capacity['results']['routes'][0]['timing_verified'] = False
    elif case == 'network_timing_unverified':
        capacity['results']['networks'][0]['timing_verified'] = False
    elif case == 'stale':
        capacity['is_outdated'] = True
    elif case == 'unrelated_preflight':
        preflight['capacity_snapshot_id'] = 'capacity-old'
    elif case == 'unknown_outcome':
        goal['required_outcomes'].append('simulation_passed')
    completion = CompletionEvaluator().evaluate_configuration_apply(
        goal, capacity, preflight, evidence_refs=['proposal', 'capacity-new', 'preflight-new'])
    assert completion['missing_outcomes'] == missing
    assert completion['completed'] is (not missing)
    assert completion['status'] == ('BLOCKED_WITH_EXPLICIT_CAUSE' if missing else 'COMPLETED')
    assert completion['achieved_outcomes'] == [name for name in goal['required_outcomes'] if name not in missing]
