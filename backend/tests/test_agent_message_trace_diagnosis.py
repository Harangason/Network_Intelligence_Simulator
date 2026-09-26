"""Message-scoped diagnosis uses the real reasoning service without new persistence."""
import asyncio
from copy import deepcopy

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.executor import EngineeringExecutor
from backend.agent_core.runtime.goal_resolver import GoalResolver
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.db import get_connection
from backend.engineering.reasoning.service import ReasoningService
from backend.engineering.repository import NotFoundError
from backend.simulator_engineering_mcp.server import create_server
from backend.tests.test_reasoning_integration import setup
from backend.tests.test_engineering_reasoning import frame


def scenario():
    return {'seed': 42, 'duration_s': 2, 'scenario': {'mode': 'NORMAL', 'faults': []},
            'engineering_model': {'messages': [{'id': 'selected', 'name': 'PressureCommand'},
                                               {'id': 'other', 'name': 'Unrelated'}]}}


def test_message_scope_rejects_other_events_and_does_not_persist(setup):
    project, jobs, add, client, workflow = setup
    job = add([frame(event_id='selected-event', message_ids=['selected']),
               frame(event_id='other-event', message_ids=['other'], queue_delay_ms=1000)], config=scenario())
    with get_connection() as db:
        before = db.execute('SELECT count(*) AS n FROM engineering_analysis_snapshots WHERE project_id=%s', (project,)).fetchone()['n']
    result = ReasoningService().analyze({'job_id': job}, persist=False, message_id='selected')
    assert result.completion_status == 'COMPLETE'
    assert result.lineage['message_id'] == 'selected'
    assert result.time_range['scanned_event_count'] == 2
    assert result.time_range['event_count'] == 1
    assert result.time_range['capacity_scope'] == 'SELECTED_MESSAGE_CONTRIBUTION_ONLY'
    events = [e for e in result.evidence_refs if e.source_type == 'TraceEvent']
    assert len(events) == 1 and events[0].source_id == 'selected-event'
    with get_connection() as db:
        assert db.execute('SELECT count(*) AS n FROM engineering_analysis_snapshots WHERE project_id=%s', (project,)).fetchone()['n'] == before


def test_absent_or_foreign_message_cannot_confirm_a_cause(setup):
    project, jobs, add, client, workflow = setup
    job = add([frame(message_ids=['other'])], config=scenario())
    result = ReasoningService().analyze({'job_id': job}, persist=False, message_id='selected')
    assert result.completion_status == 'INCOMPLETE' and not result.confirmed_causes
    assert 'MESSAGE_TRACE_MISSING' in {g['code'] for g in result.data_gaps}
    with pytest.raises(NotFoundError):
        ReasoningService().analyze({'job_id': job}, persist=False, message_id='foreign')
    with pytest.raises(ValueError):
        ReasoningService().analyze({'job_id': job}, message_id='selected')


def test_trace_inspection_requires_trace_authority(setup):
    project, jobs, add, client, workflow = setup
    job = add([frame(message_ids=['selected'])], config=scenario())

    async def invoke(permission):
        async with EngineeringMCPClient(create_server(ToolAuthority(project, permissions=frozenset({permission})))) as mcp:
            return await mcp.call('inspect_message_trace_timing', {'job_id': job, 'message_id': 'selected', 'request': 'Warum verspätet?'})

    denied = asyncio.run(invoke(Permission.READ_MODEL))
    assert not denied.success and denied.status.value == 'PERMISSION_DENIED'
    allowed = asyncio.run(invoke(Permission.ANALYZE_TRACE))
    assert allowed.success and allowed.data['lineage']['message_id'] == 'selected'


@pytest.mark.parametrize('invalid', [None, 'foreign_project', 'foreign_job', 'foreign_message', 'stale', 'changed_versions', 'unconfirmed', 'non_timing_cause', 'no_deadline_miss'])
def test_executor_completes_only_current_message_bound_cause(setup, invalid):
    project, jobs, add, client, workflow = setup
    job = add([frame(message_ids=['selected'])], config=scenario())
    analysis = ReasoningService().analyze({'job_id': job}, persist=False, message_id='selected').model_dump(mode='json')
    sequence = {'status': 'SIMULATED', 'job_id': job, 'source_versions': deepcopy(analysis['lineage']['source_versions']),
                'transactions': [{'transport_latency_ms': 20, 'deadline_status': 'FAIL', 'receiver_status': 'NOT_OBSERVED', 'e2e_latency_ms': None}]}
    if invalid == 'foreign_project': analysis['project_id'] = 'foreign'
    if invalid == 'foreign_job': analysis['simulation_run_id'] = 'foreign'
    if invalid == 'foreign_message': analysis['lineage']['message_id'] = 'other'
    if invalid == 'stale': analysis['validation_status'] = 'STALE'
    if invalid == 'changed_versions': analysis['lineage']['source_versions']['parameters'] += 1
    if invalid == 'unconfirmed': analysis['confirmed_causes'] = []
    if invalid == 'non_timing_cause':
        analysis['confirmed_causes'] = ['fault:0:SIGNAL_NOISE']
        analysis['hypotheses'] = [{'id': 'fault:0:SIGNAL_NOISE', 'status': 'SUPPORTED', 'description': 'Unrelated signal cause'}]
    if invalid == 'no_deadline_miss': sequence['transactions'][0]['deadline_status'] = 'PASS'

    class Client:
        def __init__(self): self.calls = []
        async def call(self, name, arguments):
            self.calls.append((name, arguments))
            if name == 'inspect_message_timing':
                return ToolResult(data={'status': 'MODEL_DEADLINE_PASS', 'message': {'id': 'selected', 'name': 'PressureCommand'},
                    'sequence': sequence, 'routes': [{'route_id': 'route', 'end_to_end_latency_ms': .704,
                                                     'max_latency_ms': 10, 'latency_status': 'PASS'}]})
            assert arguments['job_id'] == job and arguments['message_id'] == 'selected'
            return ToolResult(data=analysis)

    mcp = Client()
    context = AgentContext(active_project_id=project)
    goal = GoalResolver().resolve('Warum kommt PressureCommand zu spät an?', {'active_project_id': project})
    result = asyncio.run(EngineeringExecutor(mcp).execute(goal, context, {}, emit=lambda _: None,
        available_tools={'inspect_message_timing', 'inspect_message_trace_timing'}))
    assert [name for name, _ in mcp.calls] == ['inspect_message_timing', 'inspect_message_trace_timing']
    assert result['status'] == ('ANSWERED' if invalid is None else 'INCOMPLETE')
    if invalid is None:
        text = result['events'][0]['text']
        assert 'Simulations-Trace' in text and '0.704 ms' in text
        assert 'Empfängerannahme ist damit nicht bestätigt' in text
    else:
        assert 'nicht vollständig bestätigt' in result['events'][0]['text']
