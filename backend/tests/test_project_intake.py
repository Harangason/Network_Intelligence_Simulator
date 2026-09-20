import asyncio

import pytest
from uuid import uuid4

from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.orchestration.project_intake import is_project_request, project_intake_text
from backend.engineering.agent_tools import capabilities
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.agent_core.api.tool_contract import Permission


REQUEST = ('ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen '
           'und ein respary pi und aktoren die ventile steuern')


@pytest.mark.parametrize('text', [REQUEST, 'Bitte plane ein System mit Sensoren und Ventilen.',
                                'Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.',
                                'New project with two temperature sensors.',
                                'I want a small project with temperature sensors and a Raspberry Pi.'])
def test_natural_project_requests(text):
    assert is_project_request(text)


@pytest.mark.parametrize('text', ['Suche ein Projekt mit Sensoren.', 'Wie erstelle ich ein Projekt mit Sensoren?',
                                'Ich möchte ein Signal anlegen.', 'Zeige die Ventile im Projekt.'])
def test_read_queries_and_object_commands_keep_their_own_workflow(text):
    assert not is_project_request(text)


def test_project_request_prepares_real_capability_instead_of_search_apology(monkeypatch):
    authority = ToolAuthority('intake-' + uuid4().hex)
    monkeypatch.setattr(capabilities, 'catalog', lambda _: {'capabilities': [{
        'available': True, 'action': {'type': 'CAPABILITY', 'capability_id': 'project', 'project_id': 'test-intake'},
    }]})
    class Client:
        async def tools(self):
            return [{'name': 'prepare_project_request'}]
        async def call(self, name, arguments=None):
            assert name == 'prepare_project_request'
            return execute(authority, name, Permission.GENERATE_PROPOSAL, arguments, capabilities.prepare_project_request)
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


def test_explicit_quantity_is_not_asked_again_in_generic_intake_prose():
    text = project_intake_text('Ich möchte ein Projekt mit Raspberry-Pi, drei Temperatursensoren und zwei Ventilen.')
    assert 'Wie viele Ventile' not in text
    assert 'Temperatursensor1' in text
    assert 'Ventilaktor2' in text
    assert 'RaspberryPi' in text
    assert '→' not in text
    assert 'Projektentwurf ausarbeiten' not in text


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
    assert len(calls) == 1
    assert calls[0][0] == 'prepare_project_request'
    assert calls[0][1]['requirement'] == REQUEST
    assert calls[0][1]['planning_notes'] == 'Drei Messstellen, Zuordnung zu den Ventilen noch offen.'
    assert calls[0][1]['operation_id']
    assert calls[0][1]['revision'] is None


def test_project_intake_reads_generator_policy_and_reviewed_experience_first():
    calls = []

    class Client:
        async def tools(self):
            return [
                {'name': 'prepare_project_request'},
                {'name': 'resolve_generation_rules'},
                {'name': 'inspect_generation_experience'},
            ]

        async def call(self, name, arguments=None):
            calls.append((name, arguments))
            if name == 'prepare_project_request':
                return ToolResult(data={'agent_response': {
                    'type': 'RESULT', 'status': 'INCOMPLETE', 'text': 'Entwurf',
                    'metadata': {},
                }})
            return ToolResult(data={
                'status': 'READY',
                'authority': 'advisory_only' if name == 'inspect_generation_experience' else 'registry',
            })

    class Reasoner:
        async def next(self, messages, context, tools):
            assert [tool['name'] for tool in tools] == ['prepare_project_request']
            assert any(message.get('tool_name') == 'resolve_generation_rules' for message in messages)
            assert any(message.get('tool_name') == 'inspect_generation_experience' for message in messages)
            return {'calls': [{'name': 'prepare_project_request', 'arguments': {
                'planning_notes': 'Registry und geprüfte Erfahrungen wurden getrennt berücksichtigt.',
            }}]}

    result = asyncio.run(EngineeringAgent(Client(), reasoner=Reasoner()).run(
        REQUEST,
        AgentContext(active_project_id='test-generation-experience-intake'),
    ))

    assert result['status'] == 'INCOMPLETE'
    assert [name for name, _ in calls] == [
        'resolve_generation_rules',
        'inspect_generation_experience',
        'prepare_project_request',
    ]
    assert calls[-1][1]['requirement'] == REQUEST
    assert 'Registry und geprüfte Erfahrungen' in calls[-1][1]['planning_notes']


@pytest.mark.parametrize('text', ['Ich möchte kein Projekt mit Sensoren.',
    'Strukturierte Vorgaben fuer den Engineering-Agenten: Erstelle Projekt mit Sensoren.'])
def test_negation_and_confirmed_wizard_are_not_redirected(text):
    assert not is_project_request(text)
