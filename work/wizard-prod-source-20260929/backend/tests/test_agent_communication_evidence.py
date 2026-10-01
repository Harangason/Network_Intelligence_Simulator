"""Current simulation facts must retain their exact route and evidence scope."""
import asyncio
from copy import deepcopy

import pytest
from psycopg.types.json import Jsonb

from backend.app.e2e_assurance import build_e2e_transactions, build_sequence_model
from backend.engineering.agent_tools.communication_evidence import SOURCE_STEPS, select_simulation_sequence
from backend.tests.test_e2e_assurance import frame
from backend.tests.test_agent_communication_path import connected_model, PROMPT
from backend.tests.test_goal_execution_sql import project


def evidence(project_id='fixture-project', canonical='canonical-route', events=None):
    events = events or [frame(source_name='Controller A', destination_names=['Controller B'])]
    versions = {key: 1 for key in SOURCE_STEPS}
    analysis = {'id': 'analysis-id', 'project_id': project_id, 'is_outdated': False,
        'source_versions': versions, 'input_data': {'configuration': {'communications': [
            {'id': 'route', 'canonical_route_id': canonical, 'routing_entry_id': canonical}]}},
        'results': {'status': 'COMPLETED', 'simulation_snapshot_id': 'snapshot-id', 'job_id': 'job-id',
            'runtime_metrics': {'e2e_transactions': build_e2e_transactions(events),
                                'sequence_model': build_sequence_model(events, source='SIMULATED')}}}
    return analysis, {'versions': deepcopy(versions)}


def select(analysis, state):
    return select_simulation_sequence(analysis, state, {'canonical-route'}, 'fixture-project')


def test_delivery_stays_simulated_and_preserves_shared_sequence_without_acceptance():
    analysis, state = evidence(); before = deepcopy(analysis)
    result = select(analysis, state)
    assert result['status'] == 'SIMULATED' and result['observed_trace_available'] is False
    assert result['model'] == analysis['results']['runtime_metrics']['sequence_model']
    assert result['transactions'][0]['canonical_route_id'] == 'canonical-route'
    assert result['transactions'][0]['transport_latency_ms'] == 8
    assert result['transactions'][0]['e2e_latency_ms'] is None
    assert result['receiver_action'] == 'NOT_OBSERVED'
    assert analysis == before


@pytest.mark.parametrize('step', SOURCE_STEPS)
def test_every_changed_source_or_preflight_version_excludes_simulation(step):
    analysis, state = evidence(); state['versions'][step] += 1
    assert select(analysis, state)['reason'] == 'STALE_SIMULATION'


@pytest.mark.parametrize('change', ['foreign-project', 'outdated', 'missing-version', 'boolean-version',
    'not-completed', 'observed-source', 'wrong-route', 'contradictory-route', 'missing-event-id',
    'wrong-transaction-id', 'receiver-contradiction'])
def test_untrusted_or_uncorrelated_evidence_is_not_substituted(change):
    analysis, state = evidence(); metrics = analysis['results']['runtime_metrics']
    if change == 'foreign-project': analysis['project_id'] = 'other-project'
    elif change == 'outdated': analysis['is_outdated'] = True
    elif change == 'missing-version': del analysis['source_versions']['parameters']
    elif change == 'boolean-version': analysis['source_versions']['parameters'] = True
    elif change == 'not-completed': analysis['results']['status'] = 'RUNNING'
    elif change == 'observed-source': metrics['sequence_model']['source'] = 'OBSERVED'
    elif change == 'wrong-route': metrics['e2e_transactions'][0]['route_id'] = 'other-route'
    elif change == 'contradictory-route': analysis['input_data']['configuration']['communications'][0]['routing_entry_id'] = 'other-route'
    elif change == 'missing-event-id': metrics['e2e_transactions'][0]['evidence_event_ids'] = []
    elif change == 'wrong-transaction-id': metrics['sequence_model']['events'][0]['transactionId'] = 'other-transaction'
    elif change == 'receiver-contradiction': metrics['sequence_model']['transactions'][0]['receiverStatus'] = 'ACCEPTED'
    result = select(analysis, state)
    assert result['status'] == 'NOT_OBSERVED' and result['transactions'] == []


def test_explicit_receiver_acceptance_is_preserved_with_simulation_provenance():
    analysis, state = evidence(events=[frame(source_name='Controller A', destination_names=['Controller B']),
        {'transaction_id': 'route:1', 'event_id': 'receiver:1', 'event_type': 'RECEIVER_ACCEPTANCE', 'time_s': 1.014}])
    result = select(analysis, state)
    assert result['receiver_action'] == 'EVIDENCED_IN_SIMULATION'
    assert result['transactions'][0]['receiver_status'] == 'ACCEPTED'
    assert result['transactions'][0]['e2e_latency_ms'] == 14
    assert result['observed_trace_available'] is False


def test_actual_project_analysis_is_read_only_and_excludes_other_routes(project):
    from backend.engineering.agent_tools.communication_path import inspect_communication_path
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.db import get_connection
    connected_model()
    arguments = {'source_ref': 'ParkAssist', 'target_ref': 'DriverAssistance'}
    path = inspect_communication_path(arguments)
    analysis, _ = evidence(project, path['routes'][0]['id'])
    state = WorkflowStatusService(project).get(); analysis['source_versions'] = state['versions']
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_analysis_snapshots (project_id,analysis_type,source_versions,input_data,results,findings,provenance,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
            (project, 'results_analysis', Jsonb(analysis['source_versions']), Jsonb(analysis['input_data']),
             Jsonb(analysis['results']), Jsonb([]), Jsonb({'source': 'TEST_FIXTURE'}), 'WARNING'))
    revision = ModelGraphService.load().revision
    result = inspect_communication_path(arguments)
    assert result['sequence']['status'] == 'SIMULATED'
    assert result['sequence']['transactions'][0]['canonical_route_id'] == path['routes'][0]['id']
    assert result['observed_trace_available'] is False
    assert result['evidence_kind'] == 'CALCULATED_MODEL_AND_SIMULATION'
    assert ModelGraphService.load().revision == revision


def test_assistant_explains_simulated_transport_without_claiming_receiver_acceptance():
    from backend.agent_core.api.tool_contract import ToolResult
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.runtime.service import EngineeringAssistantService
    class Client:
        async def tools(self): return [{'name': 'inspect_communication_path'}]
        async def call(self, name, arguments):
            assert name == 'inspect_communication_path'
            analysis, state = evidence()
            return ToolResult(data={'status': 'MODEL_PATH_RESOLVED', 'routes': [], 'sequence': select(analysis, state)})
    result = asyncio.run(EngineeringAssistantService(Client()).execute(PROMPT, AgentContext(active_project_id='fixture-project')))
    answer = next(event for event in result['events'] if event['type'] == 'RESULT')['text']
    assert 'Simulierte Transportlaufzeit: 8 ms' in answer
    assert 'Empfängerakzeptanz ist nicht nachgewiesen' in answer
    assert '1 korrelierte Transaktionen' in answer
