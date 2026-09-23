from __future__ import annotations

import asyncio
from pathlib import Path

from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.context_resolver import ContextResolver
from backend.agent_core.runtime.goal_resolver import GoalResolver, GoalType
from backend.agent_core.runtime.service import EngineeringAssistantService


def test_goal_resolver_identifies_project_inventory_without_guessing_transport():
    goal = GoalResolver().resolve(
        'Erstelle ein einfaches Projekt mit einem Controller, einem Drucksensor und einem Ventilaktor.',
        {'active_project_id': 'project-a'},
    )
    assert goal.goal_type == GoalType.CREATE_PROJECT
    assert {item['type'] for item in goal.requested_objects} >= {
        'CONTROLLER', 'PRESSURE_SENSOR', 'VALVE_ACTUATOR'
    }
    assert goal.technology_constraints == []


def test_goal_resolver_preserves_large_confirmed_wizard_request():
    requirement = (Path(__file__).resolve().parents[2] / 'frontend/e2e/fixtures/wizard-large-50-250-250.txt').read_text(encoding='utf-8')
    prompt = 'Strukturierte Vorgaben fuer den Engineering-Agenten:\nper Wizard-Uebernehmen bestaetigt\n' + requirement
    goal = GoalResolver().resolve(prompt, {'active_project_id': 'project-a'})
    assert goal.original_request == prompt
    assert len(goal.requested_objects) > 100


def test_durable_wizard_target_wins_over_terms_in_full_request_and_followup():
    resolver = GoalResolver()
    wizard_request = {
        'version': 2,
        'target': 'engineering_model',
        'prompt': 'Bestätigter Gesamtauftrag mit Trace analysieren, Simulation und Kapazität prüfen.',
    }
    full_prompt = wizard_request['prompt']
    initial = resolver.resolve(full_prompt, {
        'active_project_id': 'project-a', 'wizard_request': wizard_request,
    })
    continued = resolver.resolve('Nach der Freigabe fortfahren.', {
        'active_project_id': 'project-a', 'wizard_request': wizard_request,
    })

    assert initial.goal_type == GoalType.CREATE_PROJECT
    assert continued.goal_type == GoalType.CREATE_PROJECT


def test_wizard_results_analysis_target_selects_analysis_capability():
    goal = GoalResolver().resolve('Nach der Freigabe fortfahren.', {
        'active_project_id': 'project-a',
        'wizard_request': {'version': 2, 'target': 'results_analysis'},
    })

    assert goal.goal_type == GoalType.ANALYZE_TRACE


def test_context_resolver_carries_durable_wizard_target_to_goal_resolution():
    descriptor = {'version': 2, 'target': 'engineering_model', 'revision': 'saved-revision'}
    resolved = ContextResolver().resolve(AgentContext(
        active_project_id='project-a', wizard_request=descriptor,
    ))

    assert resolved['wizard_request'] == descriptor
    goal = GoalResolver().resolve('Nach der Freigabe fortfahren.', resolved)
    assert goal.goal_type == GoalType.CREATE_PROJECT


def test_goal_resolver_extracts_periodic_acquisition_and_excludes_negated_bus():
    resolver = GoalResolver()
    goal = resolver.resolve(
        'Lege eine ECU an, die Stellgliedpositionen im System alle 30 Sekunden abfragt. Das Projekt nutzt I2C, nicht CAN.',
        {'active_project_id': 'project-a'},
    )
    assert goal.goal_type == GoalType.PERIODIC_ACQUISITION
    assert goal.timing_constraints == [{'kind': 'PERIOD', 'value': 30.0, 'unit': 'Sekunden', 'seconds': 30.0}]
    assert goal.technology_constraints == ['I2C']


def test_goal_resolver_routes_precise_status_queries_and_repair_followups():
    resolver = GoalResolver()
    status = resolver.resolve('Zeige den aktuellen Systemstatus mit Temperatur sowie K- und P-Werten.', {})
    assert status.goal_type == GoalType.STATUS_QUERY
    previous = {'workload_id': 'workload-old', 'goal': {'goal_id': 'goal-old', 'goal_type': 'PERIODIC_ACQUISITION',
                'original_request': 'Erfasse Aktorpositionen.'}}
    followup = resolver.resolve('Mach das auch für die anderen Aktoren.', {}, previous)
    assert followup.goal_type == GoalType.PERIODIC_ACQUISITION
    assert followup.follow_up_of == 'workload-old'


def test_runtime_persists_goal_and_completes_only_with_structured_evidence():
    class Client:
        async def tools(self):
            return [{'name': 'inspect_project'}, {'name': 'inspect_findings'}]

    class Agent:
        def __init__(self, client, *, reasoner=None):
            pass

        async def run(self, prompt, context, *, emit=None, history=None):
            event = {'id': 'result-1', 'type': 'RESULT', 'status': 'ANSWERED', 'text': 'Preflight: PASS',
                     'metadata': {'details': {'preflight_status': 'PASS'}}}
            if emit:
                emit(event)
            return {'run_id': 'run-1', 'status': 'ANSWERED', 'events': [event], 'context': context.model_dump(),
                    'trace': [{'tool': 'validate_simulation_preflight', 'trace_id': 'trace-1', 'status': 'SUCCESS'}],
                    'proposals': []}

    saved = []
    context = AgentContext(active_project_id='project-a')
    result = asyncio.run(EngineeringAssistantService(Client(), agent_factory=Agent,
        persist=lambda workload: saved.append(workload.copy())).execute(
            'Zeige den aktuellen Systemstatus.', context, saved_state={}))

    assert result['runtime']['goal']['goal_type'] == 'STATUS_QUERY'
    assert result['runtime']['status'] == 'COMPLETED'
    assert len(saved) == 3
    assert saved[-1]['status'] == 'COMPLETED'
    assert result['events'][0]['metadata']['engineering_goal_type'] == 'STATUS_QUERY'


def test_completion_evaluator_rejects_success_without_model_evidence():
    from backend.agent_core.runtime.completion import CompletionEvaluator

    goal = GoalResolver().resolve('Erstelle ein Signal.', {'active_project_id': 'project-a'}).model_dump(mode='json')
    completion = CompletionEvaluator().evaluate(goal, [
        {'type': 'RESULT', 'status': 'COMPLETED', 'text': 'Erfolgreich.'},
    ])

    assert completion['status'] == 'INCOMPLETE'
    assert completion['missing_outcomes']
