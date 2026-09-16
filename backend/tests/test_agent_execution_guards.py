import asyncio

from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent


class Client:
    def __init__(self):
        self.calls = []

    async def tools(self):
        return [
            {'name': 'ask_engineering_question', 'description': '', 'input_schema': {
                'type': 'object', 'properties': {'question_id': {'type': 'string'}}}},
            {'name': 'inspect_project', 'description': '', 'input_schema': {'type': 'object'}},
        ]

    async def call(self, name, arguments=None):
        self.calls.append((name, arguments))
        return ToolResult(data={})


def test_answered_architecture_decision_is_reused_without_a_new_question():
    client = Client()

    class Reasoner:
        step = 0
        async def next(self, messages, context, tools):
            self.step += 1
            if self.step == 1:
                return {'calls': [{'id': 'q', 'name': 'ask_engineering_question', 'arguments': {
                    'question_id': 'robot_bus_strategy'}}], 'assistant_message': {'role': 'assistant', 'content': ''}}
            assert 'decision_already_answered' in messages[-2]['content'] or any(
                'decision_already_answered' in m.get('content', '') for m in messages)
            return {'calls': [], 'text': 'Die bestätigte Busstrategie wird verwendet.'}

    context = AgentContext(active_project_id='guard-test', answered_questions={
        'robot_bus_strategy': {'selected_options': ['canfd_ethernet'], 'status': 'ANSWERED'}})
    result = asyncio.run(EngineeringAgent(client, reasoner=Reasoner()).run('Welche Busstrategie?', context))
    assert not any(name == 'ask_engineering_question' for name, _ in client.calls)
    assert not any(event.get('question') for event in result['events'])
    assert result['context']['answered_questions'] == context.answered_questions


def test_unbacked_busload_is_not_returned_as_an_answer():
    class Reasoner:
        async def next(self, *args):
            return {'calls': [], 'text': 'Die berechnete Modbus-Buslast beträgt 5,12 %.'}
    result = asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run(
        'Wie hoch ist die Buslast?', AgentContext(active_project_id='guard-test')))
    assert result['status'] == 'INCOMPLETE'
    assert '5,12' not in result['text']
    assert 'Ergebnisartefakt' in result['text']


def test_repeated_failed_calls_do_not_repeat_side_effects_beyond_repair_budget():
    class FailingClient(Client):
        async def call(self, name, arguments=None):
            self.calls.append((name, arguments))
            return ToolResult(success=False, status='NOT_FOUND', data={}, findings=[{'message': 'Not found'}])
    class Reasoner:
        async def next(self, *args):
            return {'calls': [{'id': 'bad', 'name': 'inspect_project', 'arguments': {}}],
                    'assistant_message': {'role': 'assistant', 'content': ''}}
    client = FailingClient()
    asyncio.run(EngineeringAgent(client, reasoner=Reasoner(), max_steps=6, max_repairs=2).run(
        'Prüfe das Projekt', AgentContext(active_project_id='guard-test')))
    assert sum(name == 'inspect_project' for name, _ in client.calls) <= 2


def test_preflight_argument_rejection_cannot_be_reported_as_successful_answer():
    class Reasoner:
        step = 0
        async def next(self, *args):
            self.step += 1
            if self.step == 1:
                return {'calls': [{'id': 'bad', 'name': 'inspect_project', 'arguments': {'request': 'not an object'}}],
                        'assistant_message': {'role': 'assistant', 'content': ''}}
            return {'calls': [], 'text': 'Die Prüfung ist beendet.'}
    client = Client()
    result = asyncio.run(EngineeringAgent(client, reasoner=Reasoner()).run(
        'Prüfe das Projekt', AgentContext(active_project_id='guard-test')))
    assert result['status'] == 'INCOMPLETE'
    assert not any(name == 'inspect_project' for name, _ in client.calls)
