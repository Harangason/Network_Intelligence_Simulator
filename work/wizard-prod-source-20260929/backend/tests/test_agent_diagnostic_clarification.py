"""A genuinely missing trigger is asked from canonical facts, without guessing."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.orchestration.capability_intent import sparse_diagnostic_trigger_question
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import create_object
from backend.simulator_engineering_mcp.server import create_server


PROMPT = 'Lege eine Diagnoseabfrage für alle Stellglieder an.'


class NoPlanning:
    async def next(self, *args):
        pytest.fail('An unambiguous missing trigger needs no speculative local planning')


def fixture():
    authority = ToolAuthority(f'diagnostic-clarification-{uuid4()}')
    seeded = execute(authority, 'test_fixture', Permission.GENERATE_PROPOSAL, {},
        lambda _: [create_object('HardwareNode', {'name': name, 'device_type': 'ActuatorController'})
                   for name in ['Stellglied links', 'Stellglied rechts']])
    assert seeded.success
    return authority


@pytest.mark.parametrize('prompt', [PROMPT,
    'Bitte erstelle eine Diagnoseabfrage für alle Aktoren.',
    'Create a diagnostic request for every actuator.'])
def test_sparse_model_asks_trigger_through_actual_mcp_without_mutation(prompt):
    async def run():
        authority = fixture()
        async with EngineeringMCPClient(create_server(authority)) as client:
            before = await client.call('inspect_model_situation')
            result = await EngineeringAssistantService(client, reasoner=NoPlanning()).execute(
                prompt, AgentContext(active_project_id=authority.project_id))
            after = await client.call('inspect_model_situation')
            assert before.data == after.data
            questions = [e['question'] for e in result['events'] if e.get('question')]
            assert len(questions) == 1
            question = questions[0]
            assert question['required'] and question['engineering_impact'] == 'REQUIRED'
            assert [o['id'] for o in question['options']] == ['manual', 'cyclic', 'event']
            assert not any(h['name'] == o['label'] for h in before.data['hardware_nodes'] for o in question['options'])
            trace = [t['tool'] for t in result['trace']]
            assert trace.index('inspect_model_situation') < trace.index('ask_engineering_question')
            assert not result.get('proposals')
            assert result['runtime']['status'] == 'WAITING_FOR_ENGINEERING_DECISION'
            assert result['runtime']['completed'] is False
    asyncio.run(run())


def test_known_model_facts_decisions_and_qualified_intents_are_not_reasked():
    async def run():
        authority = fixture()
        async with EngineeringMCPClient(create_server(authority)) as client:
            model = (await client.call('inspect_model_situation')).data
        assert sparse_diagnostic_trigger_question(PROMPT, model, {})
        for prompt in [
            'Lege keine Diagnoseabfrage für alle Stellglieder an.',
            'Lege eine Diagnoseabfrage für alle Stellglieder alle 30 Sekunden an.',
            'Lege eine Diagnoseabfrage für alle Stellglieder an und lösche den Controller.',
            'Lege eine Diagnoseabfrage für Stellglied links an.',
            'Explain a diagnostic request for every actuator.',
        ]:
            assert sparse_diagnostic_trigger_question(prompt, model, {}) is None
        assert sparse_diagnostic_trigger_question(PROMPT, model,
            {'diagnostic_trigger': {'selected_options': ['manual']}}) is None
        for section in ['functions', 'functional_interfaces', 'hardware_interfaces',
                        'transport_units', 'payload_elements', 'routes', 'networks',
                        'communication_capabilities', 'communication_controllers',
                        'physical_ports', 'network_connections']:
            changed = deepcopy(model); changed[section] = [{'id': 'modeled-fact'}]
            assert sparse_diagnostic_trigger_question(PROMPT, changed, {}) is None
            del changed[section]
            assert sparse_diagnostic_trigger_question(PROMPT, changed, {}) is None
        changed = deepcopy(model)
        changed['hardware_nodes'][0]['identity'] = {'diagnostic_trigger': 'manual'}
        assert sparse_diagnostic_trigger_question(PROMPT, changed, {}) is None
        changed['hardware_nodes'] = []
        assert sparse_diagnostic_trigger_question(PROMPT, changed, {}) is None
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['foreign', 'read', 'question'])
def test_failed_or_foreign_canonical_read_and_question_failure_cannot_succeed(failure):
    async def run():
        authority = fixture()
        async with EngineeringMCPClient(create_server(authority)) as real:
            class Client:
                tools = real.tools

                async def call(self, name, arguments=None):
                    if name == 'inspect_model_situation' and failure in {'read', 'foreign'}:
                        return (ToolResult(success=False, status='INTERNAL_ERROR') if failure == 'read'
                                else ToolResult(data={'project_ref': 'foreign', 'project_revision': 'r'}))
                    if name == 'ask_engineering_question' and failure == 'question':
                        return ToolResult(success=False, status='INVALID_INPUT', findings=[{'message': 'Question rejected'}])
                    return await real.call(name, arguments)
            result = await EngineeringAgent(Client(), reasoner=NoPlanning()).run(
                PROMPT, AgentContext(active_project_id=authority.project_id))
            assert result['status'] == 'INCOMPLETE'
            assert not any(e.get('question') for e in result['events'])
            assert not result.get('proposals')
    asyncio.run(run())
