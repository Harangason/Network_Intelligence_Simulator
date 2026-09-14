import asyncio

import pytest

from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.orchestration.project_intake import is_project_request, project_intake_text
from backend.engineering.agent_tools import capabilities


REQUEST = ('ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen '
           'und ein respary pi und aktoren die ventile steuern')


@pytest.mark.parametrize('text', [REQUEST, 'Bitte plane ein System mit Sensoren und Ventilen.',
                                'I want a small project with temperature sensors and a Raspberry Pi.'])
def test_natural_project_requests(text):
    assert is_project_request(text)


@pytest.mark.parametrize('text', ['Suche ein Projekt mit Sensoren.', 'Wie erstelle ich ein Projekt mit Sensoren?',
                                'Ich möchte ein Signal anlegen.', 'Zeige die Ventile im Projekt.'])
def test_read_queries_and_object_commands_keep_their_own_workflow(text):
    assert not is_project_request(text)


def test_project_request_prepares_real_capability_instead_of_search_apology(monkeypatch):
    monkeypatch.setattr(capabilities, 'catalog', lambda _: {'capabilities': [{
        'available': True, 'action': {'type': 'CAPABILITY', 'capability_id': 'project', 'project_id': 'test-intake'},
    }]})
    class Client:
        async def tools(self):
            return [{'name': 'prepare_project_request'}]
        async def call(self, name, arguments=None):
            assert name == 'prepare_project_request'
            return ToolResult(data=capabilities.prepare_project_request(arguments))
    class Reasoner:
        async def next(self, *args):
            return {'calls': [], 'text': 'Ich konnte keine passenden Ergebnisse finden.'}
    result = asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run(
        REQUEST, AgentContext(active_project_id='test-intake', active_proposal='unrelated')))
    assert result['status'] == 'INCOMPLETE'
    assert not result['proposals']
    event = result['events'][-1]
    assert not event.get('metadata', {}).get('contract_error')
    assert REQUEST in event['text']
    assert 'Wie viele Ventile' in event['text']
    assert event['actions'][0]['requirement'] == REQUEST
    assert event['actions'][0]['project_id'] == 'test-intake'
    assert 'kein Modell' in event['text']


def test_intake_does_not_invent_protocol_counts_or_electrical_compatibility():
    text = project_intake_text(REQUEST)
    assert 'bleiben bis zur Klärung offen' in text
    assert 'drei Ventile' not in text
    assert 'I2C' not in text
    assert 'nicht bestätigt' in text


def test_model_can_reason_about_the_draft_but_cannot_replace_the_user_requirement():
    calls = []
    class Client:
        async def tools(self):
            return [{'name': 'prepare_project_request'}, {'name': 'delete_object'}]
        async def call(self, name, arguments=None):
            calls.append((name, arguments))
            return ToolResult(data={'agent_response': {'type': 'RESULT', 'status': 'INCOMPLETE', 'text': 'Entwurf'}})
    class Reasoner:
        async def next(self, messages, context, tools):
            assert [tool['name'] for tool in tools] == ['prepare_project_request']
            return {'calls': [{'name': 'prepare_project_request', 'arguments': {
                'requirement': 'erfunden', 'planning_notes': 'Drei Messstellen, Zuordnung zu den Ventilen noch offen.'}}]}
    asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run(REQUEST, AgentContext(active_project_id='test-intake')))
    assert calls == [('prepare_project_request', {'requirement': REQUEST,
                     'planning_notes': 'Drei Messstellen, Zuordnung zu den Ventilen noch offen.'})]


@pytest.mark.parametrize('text', ['Ich möchte kein Projekt mit Sensoren.',
    'Strukturierte Vorgaben fuer den Engineering-Agenten: Erstelle Projekt mit Sensoren.'])
def test_negation_and_confirmed_wizard_are_not_redirected(text):
    assert not is_project_request(text)
