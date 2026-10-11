"""Gateway intent and SQL ownership/atomicity controls, separate from browser E2E."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.executor import EngineeringExecutor
from backend.agent_core.runtime.gateway_intent import gateway_outage_intent, OUTCOMES
from backend.agent_core.runtime.goal_resolver import GoalResolver
from backend.engineering.agent_tools import conversation, gateway_outage, model
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import create_object, update_object
from backend.engineering.routing.repository import create_route
from backend.engineering.simulation import list_scenarios
from backend.engineering.workflow.service import WorkflowStatusService

PROMPT = 'Simuliere den Ausfall dieses Gateways und zeige mir, welche Kommunikation betroffen ist.'


def scoped(authority, operation, *, success=True):
    def invoke(_):
        try:
            return operation()
        except Exception:
            if success:
                import traceback
                traceback.print_exc()
            raise
    result = execute(authority, 'gateway_acceptance', Permission.RUN_SIMULATION, {}, invoke)
    assert result.success is success, result.findings
    return result.data if success else result


def seed():
    authority = ToolAuthority('gateway-' + uuid4().hex)

    def create():
        gateway = create_object('HardwareNode', {'name': 'Gateway', 'device_type': 'Gateway'})
        endpoint = create_object('HardwareNode', {'name': 'Receiver', 'device_type': 'ECU'})
        route = create_route({'name': 'Through gateway', 'source': {'node_id': str(endpoint['id'])},
            'destinations': [{'node_id': str(gateway['id'])}],
            'route': {'gateways': [{'node_id': str(gateway['id'])}]}})
        goal = GoalResolver().resolve(PROMPT, {'active_project_id': authority.project_id,
            'selected_object_refs': [{'id': str(gateway['id']), 'object_type': 'HardwareNode'}]})
        state = conversation.read()
        state['run_id'] = 'gateway-test-run'
        conversation.write(state)
        conversation.save_runtime_workload(state['run_id'], {'workload_id': goal.goal_id,
            'project_id': authority.project_id, 'goal': goal.model_dump(mode='json')})
        return {'gateway': gateway, 'endpoint': endpoint, 'route': route, 'workload_id': goal.goal_id}

    return authority, scoped(authority, create)


@pytest.mark.parametrize('prompt', [PROMPT, PROMPT.lower(), PROMPT.replace('dieses', 'des ausgewählten')])
def test_explicit_gateway_request_has_trace_bound_required_outcomes(prompt):
    assert gateway_outage_intent(prompt)
    assert GoalResolver().resolve(prompt).required_outcomes == OUTCOMES


@pytest.mark.parametrize('prompt', [PROMPT + ' Lösche danach das Gateway.',
    PROMPT.replace('Simuliere', 'Simuliere nicht'), PROMPT.replace('den Ausfall', 'keinen Ausfall'),
    'Wie simuliere ich den Ausfall dieses Gateways?', 'Simuliere das Netzwerk.',
    PROMPT.replace('dieses Gateways', 'aller Gateways')])
def test_gateway_authority_is_not_inferred_from_negated_or_mixed_text(prompt):
    assert not gateway_outage_intent(prompt)


@pytest.mark.parametrize('change', ['missing', 'multiple', 'foreign-id', 'wrong-type', 'non-gateway',
    'foreign-project', 'old-owner', 'inactive', 'different-intent'])
def test_saved_request_and_target_must_belong_to_current_project_and_turn(change):
    authority, data = seed()

    def mutate():
        state = conversation.read(); workload = state['engineering_workloads'][data['workload_id']]
        targets = workload['goal']['target_objects']
        if change == 'missing': targets.clear()
        elif change == 'multiple': targets.append(deepcopy(targets[0]))
        elif change == 'foreign-id': targets[0]['id'] = str(uuid4())
        elif change == 'wrong-type': targets[0]['object_type'] = 'Message'
        elif change == 'non-gateway': targets[0]['id'] = str(data['endpoint']['id'])
        elif change == 'foreign-project': workload['project_id'] = 'other-project'
        elif change == 'old-owner': workload['owner_run_id'] = 'old-run'
        elif change == 'inactive': state['active_engineering_workload_id'] = 'other-workload'
        elif change == 'different-intent': workload['goal']['original_request'] = 'Liste Gateways auf.'
        conversation.write(state)

    scoped(authority, mutate)
    assert scoped(authority, lambda: gateway_outage.inspect_request(data), success=False).status == 'INVALID_INPUT'
    assert scoped(authority, list_scenarios) == []


def install_configuration_boundary(monkeypatch, authority, data):
    """Stub only transport assembly: test actual SQL transaction/snapshot guards."""
    import backend.engineering.simulation as simulation
    def assemble(config, project_id):
        assert project_id == authority.project_id
        assert config['duration_mode'] == 'AUTO_OBSERVATION'
        return {**deepcopy(config), 'duration_s': 1,
                'communications': [{'id': 'runtime-route', 'canonical_route_id': str(data['route']['id']),
                                     'gateways': [str(data['gateway']['id'])]}]}
    monkeypatch.setattr(simulation, 'prepare_workflow_simulation_config', assemble)
    scoped(authority, lambda: WorkflowStatusService(authority.project_id).create_analysis_snapshot(
        'preflight', input_data={}, results={'preflight_status': 'READY', 'ready_for_simulation': True},
        findings=[], provenance={'test': 'SQL boundary only'}, status='APPROVED'))


def test_preparation_persists_once_and_refuses_stale_model(monkeypatch):
    authority, data = seed(); install_configuration_boundary(monkeypatch, authority, data)
    before = scoped(authority, model.model)
    inspected = scoped(authority, lambda: gateway_outage.inspect_request(data))
    args = {**data, 'expected_model_revision': inspected['model_revision']}
    first = scoped(authority, lambda: gateway_outage.prepare(args))
    second = scoped(authority, lambda: gateway_outage.prepare(args))
    assert not first['reused'] and second['reused']
    assert first['snapshot_id'] == second['snapshot_id'] and first['scenario_id'] == second['scenario_id']
    scenarios = scoped(authority, list_scenarios)
    assert len(scenarios) == 1 and scenarios[0]['source'] == 'explicit_user_request'
    assert scenarios[0]['faults'][0]['target']['id'] == data['gateway']['id']
    snapshot = scoped(authority, lambda: WorkflowStatusService(authority.project_id).get_simulation_snapshot(first['snapshot_id']))
    assert snapshot['configuration']['scenario']['faults'] == scenarios[0]['faults']
    assert snapshot['configuration']['scenario']['faults'][0]['model_fidelity'] == 'SIMPLIFIED_FAULT_MODEL'
    assert scoped(authority, model.model) == before
    scoped(authority, lambda: update_object('HardwareNode', data['gateway']['id'], {'description': 'new revision'}))
    assert scoped(authority, lambda: gateway_outage.prepare(args), success=False).status == 'CONFLICT'
    assert len(scoped(authority, list_scenarios)) == 1


def test_snapshot_failure_rolls_back_scenario_and_workload_identity(monkeypatch):
    authority, data = seed(); install_configuration_boundary(monkeypatch, authority, data)
    revision = scoped(authority, model.model_revision)
    def fail(*args, **kwargs):
        raise ValueError('injected snapshot persistence failure')
    monkeypatch.setattr(WorkflowStatusService, 'create_simulation_snapshot', fail)
    result = scoped(authority, lambda: gateway_outage.prepare({**data, 'expected_model_revision': revision}), success=False)
    assert result.status == 'INVALID_INPUT'
    assert scoped(authority, list_scenarios) == []
    state = scoped(authority, conversation.read)
    assert 'simulation_execution' not in state['engineering_workloads'][data['workload_id']]


@pytest.mark.parametrize('case', ['preflight-blocked', 'failed-job', 'missing-job-id', 'partial-analysis', 'missing-tool', 'reused-job'])
def test_executor_preserves_failures_and_reuses_existing_job(case):
    calls = []
    tools = {'inspect_gateway_outage_request', 'calculate_capacity', 'validate_simulation_preflight',
             'prepare_gateway_outage', 'start_simulation', 'get_simulation_status',
             'analyze_fault_effects', 'assess_gateway_outage'}
    class Client:
        async def call(self, name, arguments):
            calls.append(name)
            data = {
                'inspect_gateway_outage_request': {'model_revision': 'revision', 'gateway_id': 'gateway'},
                'calculate_capacity': {},
                'validate_simulation_preflight': {'ready_for_simulation': case != 'preflight-blocked'},
                'prepare_gateway_outage': {'snapshot_id': 'snapshot', 'snapshot_status': 'READY',
                                           'job_id': 'existing' if case == 'reused-job' else None},
                'start_simulation': {} if case == 'missing-job-id' else {'id': 'job'},
                'get_simulation_status': {'status': 'failed' if case == 'failed-job' else 'completed'},
                'analyze_fault_effects': {'reasoning_id': 'reasoning'},
                'assess_gateway_outage': {'completion': {'complete': False}},
            }[name]
            return ToolResult(data=data)
    if case == 'missing-tool': tools.remove('assess_gateway_outage')
    result = asyncio.run(EngineeringExecutor(Client()).execute(GoalResolver().resolve(PROMPT),
        AgentContext(active_project_id='component-control'), {}, emit=lambda event: None, available_tools=tools))
    assert result['status'] != 'COMPLETED'
    if case == 'preflight-blocked': assert 'prepare_gateway_outage' not in calls
    if case in {'failed-job', 'missing-job-id'}: assert 'analyze_fault_effects' not in calls
    if case == 'missing-tool': assert not calls
    if case == 'reused-job': assert 'start_simulation' not in calls


def test_unrelated_simulation_request_keeps_general_executor():
    result = asyncio.run(EngineeringExecutor(None).execute(GoalResolver().resolve('Starte die Simulation.'),
        AgentContext(active_project_id='component-control'), {}, emit=lambda event: None, available_tools=set()))
    assert result is None


@pytest.mark.parametrize('change', ['none', 'foreign-job-project', 'wrong-job-snapshot', 'wrong-job-id',
    'no-drops', 'wrong-frame-gateway', 'wrong-frame-route', 'missing-event-id', 'missing-affected-route',
    'altered-scenario', 'stale-snapshot', 'stale-reasoning', 'unlinked-findings'])
def test_completion_requires_actual_persisted_correlated_results(monkeypatch, change):
    """Real SQL scenario/snapshot/reasoning, with controlled job transport only."""
    from psycopg.types.json import Jsonb
    from backend.engineering.db import get_connection
    from backend.engineering.reasoning.service import ReasoningService
    from backend.engineering.agent_tools import simulation_gateway
    from backend.tests.test_engineering_reasoning import frame
    authority, data = seed(); install_configuration_boundary(monkeypatch, authority, data)
    revision = scoped(authority, model.model_revision)
    prepared = scoped(authority, lambda: gateway_outage.prepare({**data, 'expected_model_revision': revision}))
    job_id = uuid4().hex
    event = frame(event_id='gateway-drop-event', route_id='runtime-route', gateway_ids=[data['gateway']['id']],
        status='dropped', faults=['GATEWAY_DROP'], queue_delay_ms=0, queue_depth_estimate=0,
        end_to_end_latency_ms=None, time_s=.02, scheduled_time_s=.01, origin_release_time_s=.01)
    job = {'id': job_id, 'project_id': authority.project_id, 'status': 'completed',
           'workflow_snapshot_id': prepared['snapshot_id'], 'updated_at': 'trace-r1',
           'result': {'model_simulation': {'frames': [event], 'affected_routes': ['runtime-route']}}}

    def request(path, **kwargs):
        if 'trace-window' in path:
            return {'events': deepcopy(job['result']['model_simulation']['frames']), 'next_cursor': None}
        return deepcopy(job)
    monkeypatch.setattr(simulation_gateway, 'request_json', request)

    def finish_snapshot():
        with get_connection() as conn:
            conn.execute("UPDATE engineering_simulation_snapshots SET status='COMPLETED',job_id=%s WHERE id=%s AND project_id=%s",
                         (job_id, prepared['snapshot_id'], authority.project_id))
    scoped(authority, finish_snapshot)
    reason = scoped(authority, lambda: ReasoningService().analyze({'job_id': job_id, 'goal': PROMPT}).model_dump(mode='json'))
    assert reason['completion_status'] == 'COMPLETE', reason
    assert any(c.endswith(':GATEWAY_DROP') for c in reason['confirmed_causes']), reason

    if change == 'foreign-job-project': job['project_id'] = 'other'
    elif change == 'wrong-job-snapshot': job['workflow_snapshot_id'] = str(uuid4())
    elif change == 'wrong-job-id': job['id'] = 'wrong'
    elif change == 'no-drops': event['faults'] = []
    elif change == 'wrong-frame-gateway': event['gateway_ids'] = ['different']
    elif change == 'wrong-frame-route': event['route_id'] = 'different'
    elif change == 'missing-event-id': event.pop('event_id')
    elif change == 'missing-affected-route': job['result']['model_simulation']['affected_routes'] = []
    elif change == 'stale-reasoning': job['updated_at'] = 'trace-r2'
    elif change in {'altered-scenario', 'stale-snapshot', 'unlinked-findings'}:
        def tamper():
            with get_connection() as conn:
                if change == 'altered-scenario':
                    conn.execute("UPDATE engineering_simulation_scenarios SET faults='[]'::jsonb WHERE scenario_id=%s AND project_id=%s",
                                 (prepared['scenario_id'], authority.project_id))
                elif change == 'stale-snapshot':
                    conn.execute('UPDATE engineering_simulation_snapshots SET is_outdated=TRUE WHERE id=%s AND project_id=%s',
                                 (prepared['snapshot_id'], authority.project_id))
                else:
                    modified = deepcopy(reason)
                    for finding in modified['findings']: finding['evidence_refs'] = []
                    conn.execute('UPDATE engineering_analysis_snapshots SET results=%s WHERE id=%s AND project_id=%s',
                                 (Jsonb(modified), reason['reasoning_id'], authority.project_id))
        scoped(authority, tamper)
    if change == 'stale-snapshot':
        result = scoped(authority, lambda: gateway_outage.assess({**data, 'reasoning_id': reason['reasoning_id']}), success=False)
        assert result.status == 'CONFLICT'
    else:
        result = scoped(authority, lambda: gateway_outage.assess({**data, 'reasoning_id': reason['reasoning_id']}))
        assert result['completion']['complete'] is (change == 'none'), result
        if change == 'none':
            assert result['affected_route_ids'] == [data['route']['id']]
            assert result['scope'] == 'SIMULATED_GATEWAY_OUTAGE_NOT_FUNCTIONAL_TIMING_RELEASE'
