import asyncio
import os
from uuid import uuid4

import httpx
import pytest

from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.orchestration.capability_intent import capability_question
from backend.agent_core.orchestration.tool_selection import select_tools
from backend.engineering.agent_tools import capabilities
from backend.engineering.agent_tools.services import TOOLS
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.simulator_engineering_mcp.server import create_server


@pytest.fixture
def directory(monkeypatch):
    monkeypatch.setattr(capabilities, 'current_project_id', lambda: 'project-a')
    monkeypatch.setattr(capabilities.WorkflowStatusService, 'get', lambda *a, **k: {
        'context': {'engineering_wizard_settings': {'project_name': 'NIS Projekt A'}}})
    return capabilities.catalog({})


def test_directory_has_unique_executable_workflows_and_real_tools(directory):
    entries = directory['capabilities']
    assert len(entries) == len({item['id'] for item in entries})
    assert {'signal', 'repair', 'project', 'dependencies', 'structure', 'duplicates', 'faults', 'analysis'} <= {item['id'] for item in entries}
    for item in entries:
        assert item['available'], item
        assert all(tool in TOOLS for tool in item['tools'])
        assert item['action']['project_id'] == 'project-a'
        assert len(item['steps']) >= 3
    assert directory['project_name'] == 'NIS Projekt A'


def test_capability_contract_does_not_equate_navigation_or_analysis_with_apply(directory):
    entries = {item['id']: item for item in directory['capabilities']}
    for item in entries.values():
        assert item['execution']['navigation_executes'] is False
        assert item['execution']['completion_condition']
    assert entries['duplicates']['execution']['mode'] == 'ANALYSIS_ONLY'
    assert entries['duplicates']['execution']['agent_can_apply'] is False
    assert entries['structure']['execution']['ui_only_completion'] is False
    assert entries['faults']['execution']['ui_only_completion'] is False
    assert entries['faults']['execution']['mode'] == 'REVIEWABLE_PROPOSAL'
    assert entries['hardware']['execution']['requires_human_model_approval'] is True
    contracts = {item['skill_id']: item for item in directory['skill_contracts']}
    assert 'PROPOSAL' not in contracts['spatial']['outputs']
    assert contracts['structure']['execution'] == entries['structure']['execution']


@pytest.mark.parametrize('prompt,expected', [
    ('kennst du den reparatur agenten', 'repair'),
    ('zeige mir deine fähigkeiten', ''),
    ('Welche Wizard-Abläufe kennst du?', ''),
    ('Welche anderen Agenten gibt es?', ''),
    ('Was macht der Signal-Wizard?', 'signal'),
    ('In welchem Projekt arbeitest du?', '@project'),
    ('Repariere die Kommunikation.', None),
    ('Kannst du mit dem Reparatur-Agenten die Kommunikation reparieren?', None),
])
def test_product_questions_do_not_steal_work_requests(prompt, expected):
    assert capability_question(prompt) == expected


@pytest.mark.parametrize('prompt', ['kennst du den reparatur agenten', 'zeige mir deine fähigkeiten', 'In welchem Projekt arbeitest du?'])
def test_help_works_without_inference_and_does_not_resume_pending_work(directory, prompt):
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'inspect_assistant_capabilities'
            return ToolResult(data=capabilities.catalog(arguments or {}))
    class OfflineReasoner:
        async def next(self, *args):
            raise AssertionError('Product help must not require inference')
    result = asyncio.run(EngineeringAgent(Client(), reasoner=OfflineReasoner()).run(prompt,
        AgentContext(active_project_id='project-a', active_proposal='pending-proposal')))
    assert result['status'] == 'ANSWERED'
    assert all(trace['tool'] == 'inspect_assistant_capabilities' for trace in result['trace'])
    assert not result['proposals']
    cards = [a for event in result['events'] for a in event.get('actions', [])]
    assert all(a['project_id'] == 'project-a' for a in cards)
    assert not any(e.get('metadata', {}).get('contract_error') for e in result['events'])


def test_action_lookup_rejects_invented_capability(directory):
    with pytest.raises(ValueError): capabilities.prepare_action({'capability_id': 'delete-everything'})
    action = capabilities.prepare_action({'capability_id': 'repair'})['agent_response']
    assert action['status'] == 'ANSWERED'
    assert action['actions'][0]['capability_id'] == 'repair'


def test_agent_keeps_navigation_action_success_instead_of_blocked(directory):
    class Client:
        async def call(self, name, arguments=None):
            if name == 'inspect_project': return ToolResult(data={})
            if name == 'inspect_assistant_capabilities': return ToolResult(data=directory)
            assert name == 'prepare_assistant_action'
            return ToolResult(data=capabilities.prepare_action(arguments))
        async def tools(self):
            return [{'name': 'prepare_assistant_action'}]
    class Reasoner:
        async def next(self, messages, context, tools):
            assert any('Verifizierter Fähigkeitenkatalog' in message['content'] for message in messages)
            return {'assistant_message': {'role': 'assistant', 'content': ''}, 'calls': [{
                'id': 'one', 'name': 'prepare_assistant_action', 'arguments': {'capability_id': 'signal'}}]}
    result = asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run('Ich möchte ein Signal anlegen.', AgentContext(active_project_id='project-a')))
    assert result['status'] == 'ANSWERED'
    assert result['events'][-1]['actions'][0]['capability_id'] == 'signal'


def test_named_single_signal_request_returns_specific_missing_facts_not_workload_error():
    class Client:
        async def call(self, name, arguments=None):
            if name == 'inspect_project':
                return ToolResult(data={'context': {}, 'active_step': None})
            raise AssertionError(f'unexpected tool call: {name}')
        async def tools(self):
            return []

    prompt = 'Lege mir ein Signal an vom PLC1 ventilator_notaus, 1Bit, Init, aus, ein'
    result = asyncio.run(EngineeringAgent(Client()).run(
        prompt, AgentContext(active_project_id='project-a')))

    assert result['status'] == 'INCOMPLETE'
    assert 'zugehörige Nachricht' in result['text']
    assert 'Rohwert' in result['text']
    assert 'Gesamtzielmenge' not in result['text']
    finding = next(event for event in result['events'] if event['type'] == 'FINDING')
    assert finding['metadata']['missing_fields'] == [
        'message_id', 'raw_values', 'start_bit', 'byte_order']


def test_repair_and_navigation_tools_survive_large_tool_selection():
    tools = [{'name': name} for name in TOOLS]
    names = {t['name'] for t in select_tools('Reparatur neue Hardwarearchitektur Signal Nachricht CAN Bus Routing Simulation Trace Fehler', tools)}
    assert {'inspect_communication_repair', 'inspect_assistant_capabilities', 'prepare_assistant_action'} <= names


@pytest.mark.parametrize('prompt, required', [
    ('Erstelle einen Sensor', {'describe_model_object_fields', 'create_objects_via_proposal'}),
    ('Den gespeicherten Projektentwurf planen', {'inspect_project_draft', 'plan_project_model', 'update_project_draft'}),
    ('Funktion einem anderen Controller zuordnen', {'plan_structure_assignments', 'map_function_to_hardware'}),
    ('Das gewählte Gerät entfernen', {'delete_object_via_impact_analysis'}),
])
def test_new_execution_tools_are_available_to_the_reasoner(prompt, required):
    selected = select_tools(prompt, [{'name': name} for name in TOOLS])
    assert required <= {tool['name'] for tool in selected}
    assert len(selected) <= 24


def test_general_terms_do_not_invite_invented_object_ids():
    tools = [{'name': name} for name in TOOLS]
    names = {t['name'] for t in select_tools('Erkläre wozu Hardware, Funktionen und Signale dienen.', tools)}
    assert 'describe_engineering_concepts' in names
    assert 'inspect_object' not in names
    concrete = {t['name'] for t in select_tools('Erkläre das Signal im aktuellen Projekt.', tools)}
    assert 'inspect_signal' in concrete


def test_service_failure_is_specific_even_inside_mcp_exception_group():
    from backend.engineering.agent_tools.api import agent_failure_message
    error = ExceptionGroup('MCP', [ExceptionGroup('task', [httpx.ConnectError('secret endpoint')])])
    text = agent_failure_message(error)
    assert 'Ollama' in text and 'secret endpoint' not in text


@pytest.mark.skipif(not os.environ.get('DATABASE_URL'), reason='Isolated SQL required')
def test_real_mcp_catalog_scope_and_action_negotiation():
    async def run():
        authority = ToolAuthority('assistant-catalog-test-' + str(uuid4()))
        async with EngineeringMCPClient(create_server(authority)) as client:
            directory = await client.call('inspect_assistant_capabilities')
            assert directory.success, directory
            assert directory.data['project_id'] == authority.project_id
            assert all(item['available'] for item in directory.data['capabilities'])
            action = await client.call('prepare_assistant_action', {'capability_id': 'repair'})
            assert action.success
            assert action.data['agent_response']['actions'][0]['project_id'] == authority.project_id
            denied = await client.call('inspect_assistant_capabilities', {'project_id': 'another-project'})
            assert not denied.success
    asyncio.run(run())
