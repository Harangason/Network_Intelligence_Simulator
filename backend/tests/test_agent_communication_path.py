"""A path/timing question must not ask permission to create new functions."""
import asyncio
from copy import deepcopy

import pytest

from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.orchestration.capability_intent import communication_path_question
from backend.agent_core.runtime.goal_resolver import GoalResolver, GoalType
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools import communication_path
from backend.tests.test_goal_execution_sql import project, fixture, prepare, confirm

PROMPT = 'Zeige mir den Weg von Function A zu Function B und wie lange die Botschaft benötigt.'


@pytest.mark.parametrize('prompt', [PROMPT, 'Zeige den Pfad von Function A zu Function B.',
    'Show me the path from Function A to Function B and its latency.'])
def test_read_query_resolves_both_endpoints_without_timing_clause(prompt):
    assert communication_path_question(prompt) == ('Function A', 'Function B')
    assert GoalResolver().resolve(prompt).goal_type == GoalType.EXPLAIN


def test_creation_and_confirmed_wizard_are_not_redirected_to_read_only_query():
    assert communication_path_question('Erstelle eine Funktion Function A.') is None
    assert GoalResolver().resolve('Erstelle eine Funktion Function A.').goal_type == GoalType.CREATE_FUNCTION
    goal = GoalResolver().resolve(PROMPT, {'wizard_request': {'version': 2, 'target': 'engineering_model'}})
    assert goal.goal_type == GoalType.CREATE_PROJECT


@pytest.mark.parametrize('selected', [[], [{'id': 'existing-controller', 'object_type': 'HardwareNode'}]])
def test_read_query_never_calls_generation_even_with_selected_hardware(selected):
    class Client:
        calls = []
        async def tools(self): return [{'name': 'inspect_communication_path'}]
        async def call(self, name, arguments):
            self.calls.append((name, arguments))
            assert name == 'inspect_communication_path', 'Read-only request must not call generation or proposal tools'
            return ToolResult(data={'status': 'MODEL_PATH_RESOLVED', 'routes': [
                {'name': 'Function A -> Function B', 'hops': [{'name': 'Controller A'}, {'name': 'Controller B'}],
                 'timing': [{'end_to_end_latency_ms': 1.25}]}]})
    client = Client(); client.calls = []
    result = asyncio.run(EngineeringAssistantService(client).execute(PROMPT,
        AgentContext(active_project_id='path-test', selected_object_refs=selected)))
    assert client.calls == [('inspect_communication_path', {'source_ref': 'Function A', 'target_ref': 'Function B'})]
    assert result['runtime']['goal']['goal_type'] == 'EXPLAIN'
    assert result['runtime']['status'] == 'COMPLETED'
    answer = next(e for e in result['events'] if e['type'] == 'RESULT')
    assert '1.25 ms' in answer['text'] and 'nicht nachgewiesen' in answer['text']
    assert result.get('proposals') == []


def connected_model():
    from backend.engineering.goal_execution import service
    data = fixture(); goal = prepare(data); confirm(goal)
    assert service.resume(goal['workload_id'])['status'] == 'COMPLETE'
    return data


def test_real_canonical_path_and_calculation_remain_read_only(project):
    from backend.engineering.goal_execution.graph import ModelGraphService
    connected_model(); before = ModelGraphService.load().revision
    result = communication_path.inspect_communication_path({'source_ref': 'ParkAssist', 'target_ref': 'DriverAssistance'})
    assert result['status'] == 'MODEL_PATH_RESOLVED', result
    assert len(result['routes']) == 1
    assert result['routes'][0]['timing'][0]['end_to_end_latency_ms'] > 0
    assert result['routes'][0]['physical_paths'][0]['resolved'] is True
    assert result['sequence']['status'] == 'NOT_OBSERVED' and result['sequence']['transactions'] == []
    assert result['evidence_kind'] == 'CALCULATED_MODEL'
    assert ModelGraphService.load().revision == before


def test_sharing_hardware_does_not_assign_another_functions_route(project):
    from backend.engineering.repository import create_object
    data = connected_model()
    create_object('Function', {'name': 'UnrelatedFunction', 'hardware_node_id': data['sf']['hardware_node_id']})
    result = communication_path.inspect_communication_path({'source_ref': 'UnrelatedFunction', 'target_ref': 'DriverAssistance'})
    assert result['status'] == 'NO_FUNCTIONAL_ROUTE' and result['routes'] == []


def test_unknown_endpoint_does_not_use_the_only_available_route(project):
    connected_model()
    result = communication_path.inspect_communication_path({'source_ref': 'Missing', 'target_ref': 'DriverAssistance'})
    assert result['status'] == 'ENDPOINT_NOT_RESOLVED' and result['routes'] == []


def test_missing_timing_does_not_report_completed_model_analysis(project, monkeypatch):
    connected_model()
    monkeypatch.setattr(communication_path.CapacityTimingService, 'calculate', lambda self, **kwargs: {'results': {'routes': []}})
    result = communication_path.inspect_communication_path({'source_ref': 'ParkAssist', 'target_ref': 'DriverAssistance'})
    assert result['status'] == 'TIMING_UNVERIFIED'
    assert result['routes'][0]['timing'] == []
