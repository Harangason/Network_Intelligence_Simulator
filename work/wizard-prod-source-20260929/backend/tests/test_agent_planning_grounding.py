"""Verify actual canonical evidence reaches planning before a change question."""
import asyncio
import json
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission, ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import create_object
from backend.simulator_engineering_mcp.server import create_server

PROMPT = 'Lege eine Diagnoseabfrage für alle Stellglieder an.'


def fixture():
    authority = ToolAuthority(f'planning-grounding-{uuid4()}')
    seeded = execute(authority, 'test_fixture', Permission.GENERATE_PROPOSAL, {},
        lambda _: [create_object('HardwareNode', {'name': name, 'device_type': 'ActuatorController'})
                   for name in ['Stellglied links', 'Stellglied rechts']])
    assert seeded.success, seeded
    return authority, seeded.data


def test_first_planning_call_has_canonical_nodes_project_facts_and_prior_decisions():
    authority, nodes = fixture()
    captured = []
    class Reasoner:
        async def next(self, messages, context, tools):
            facts = {m['tool_name']: json.loads(m['content']) for m in messages if m['role'] == 'tool'}
            assert facts['inspect_project']['success']
            model = facts['inspect_model_situation']['data']
            assert model['project_ref'] == authority.project_id
            assert {(h['id'], h['name']) for h in model['hardware_nodes']} == {(h['id'], h['name']) for h in nodes}
            assert model['project_revision']
            assert context.answered_questions['diagnostic_trigger']['selected_options'] == ['manual']
            assert context.current_requirement == PROMPT
            assert not any('"steps"' in m['content'] for m in messages if m['role'] == 'system')
            captured.append(facts)
            args = {'question_id': 'diagnostic_service', 'question': 'Welche Diagnoseinformation wird benötigt?',
                    'options': [{'id': 'faults', 'label': 'Fehlerspeicher'}, {'id': 'position', 'label': 'Istposition'}]}
            return {'calls': [{'id': 'q', 'name': 'ask_engineering_question', 'arguments': args}],
                    'assistant_message': {'role': 'assistant', 'content': ''}}
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            before = await client.call('inspect_model_situation')
            context = AgentContext(active_project_id=authority.project_id, current_requirement=PROMPT,
                answered_questions={'diagnostic_trigger': {'selected_options': ['manual']}})
            result = await EngineeringAgent(client, reasoner=Reasoner()).run(PROMPT, context)
            after = await client.call('inspect_model_situation')
            assert before.data == after.data
            return result
    result = asyncio.run(run())
    assert len(captured) == 1
    assert result['status'] == 'BLOCKED'
    assert result['events'][-1]['question']['question'] == 'Welche Diagnoseinformation wird benötigt?'
    assert [t['tool'] for t in result['trace']].index('inspect_model_situation') < [t['tool'] for t in result['trace']].index('ask_engineering_question')


@pytest.mark.parametrize('bad_snapshot', [
    ToolResult(success=False, status='INTERNAL_ERROR', findings=[{'message': 'Snapshot unavailable'}]),
    ToolResult(data={'project_ref': 'foreign-project', 'hardware_nodes': [{'name': 'Foreign motor'}]}),
    ToolResult(data={}),
])
def test_unreadable_or_unbound_snapshot_blocks_before_local_inference(bad_snapshot):
    authority, _ = fixture()
    class Reasoner:
        async def next(self, *args):
            pytest.fail('No planning from missing or foreign canonical evidence')
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as real:
            class Client:
                tools = real.tools
                async def call(self, name, arguments=None):
                    return bad_snapshot if name == 'inspect_model_situation' else await real.call(name, arguments)
            return await EngineeringAgent(Client(), reasoner=Reasoner()).run(PROMPT, AgentContext(active_project_id=authority.project_id))
    result = asyncio.run(run())
    assert result['status'] == 'INCOMPLETE'
    assert not any(e.get('question') for e in result['events'])
    assert any(e.get('metadata', {}).get('code') == 'PLANNING_MODEL_CONTEXT_UNAVAILABLE' for e in result['events'])
