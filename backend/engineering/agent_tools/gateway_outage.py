"""Execute an explicit outage through existing scenario, snapshot and trace services."""
from backend.agent_core.runtime.gateway_intent import gateway_outage_intent, OUTCOMES
from ..models import EngineeringValidationError
from ..project_context import current_project_id
from ..workflow.service import WorkflowStatusService, WorkflowConflictError
from . import conversation, model, simulation_gateway

SOURCE_STEPS = ('engineering_model', 'network_editor', 'routing', 'parameters')


def _load(arguments):
    state = conversation.read()
    workload = (state.get('engineering_workloads') or {}).get(arguments['workload_id'])
    if (not state.get('run_id') or not workload or workload.get('project_id') != current_project_id()
            or state.get('active_engineering_workload_id') != arguments['workload_id']
            or workload.get('owner_run_id') != state.get('run_id')):
        raise EngineeringValidationError('Der Gateway-Auftrag gehört nicht zum aktuellen Projekt und Gesprächslauf.')
    goal = workload.get('goal') or {}
    if goal.get('goal_type') != 'RUN_SIMULATION' or not gateway_outage_intent(goal.get('original_request', '')):
        raise EngineeringValidationError('Ein ausdrücklicher Auftrag zur Simulation des ausgewählten Gateway-Ausfalls fehlt.')
    selected = goal.get('target_objects') or []
    if len(selected) != 1 or selected[0].get('object_type') != 'HardwareNode':
        raise EngineeringValidationError('Genau ein kanonisches Gateway auswählen; mehrere oder fehlende Ziele sind nicht eindeutig.')
    gateway = next((n for n in model.objects('HardwareNode') if str(n['id']) == selected[0].get('id')), None)
    if not gateway or str(gateway.get('device_type')).casefold() != 'gateway':
        raise EngineeringValidationError('Die Auswahl ist kein vorhandenes Gateway im aktiven Projekt.')
    return state, workload, gateway


def inspect_request(arguments):
    _, workload, gateway = _load(arguments)
    routes = [r for r in model.routes() if any(str(g.get('node_id')) == str(gateway['id'])
              for g in (r.get('route') or {}).get('gateways') or [])]
    if not routes:
        raise EngineeringValidationError('Für das ausgewählte Gateway ist keine kanonische Kommunikationsroute belegt.')
    return {'status': 'READY', 'project_id': current_project_id(), 'gateway_id': str(gateway['id']),
            'gateway_name': gateway['name'], 'model_revision': model.model_revision(),
            'route_ids': [str(r['id']) for r in routes], 'execution': workload.get('simulation_execution')}


def _current_snapshot(workflow, execution):
    snapshot = workflow.get_simulation_snapshot(execution['snapshot_id'], require_current=True)
    versions = workflow.get(summary=True)['versions']
    if (not snapshot or snapshot.get('is_outdated') is not False
            or any(type(snapshot['source_versions'].get(k)) is not int
                   or snapshot['source_versions'].get(k) != versions.get(k) for k in SOURCE_STEPS)):
        raise WorkflowConflictError('Der gespeicherte Gateway-Lauf passt nicht mehr zum aktuellen Modell.')
    return snapshot


def prepare(arguments):
    from ..simulation import prepare_workflow_simulation_config, save_scenario
    state, workload, gateway = _load(arguments)
    if model.model_revision() != arguments['expected_model_revision']:
        raise WorkflowConflictError('Das Modell hat sich seit der Gateway-Prüfung geändert.')
    workflow = WorkflowStatusService(current_project_id())
    existing = workload.get('simulation_execution')
    if existing:
        if existing['gateway_id'] != str(gateway['id']):
            raise WorkflowConflictError('Der gespeicherte Simulationsauftrag gehört zu einer anderen Gateway-Auswahl.')
        snapshot = _current_snapshot(workflow, existing)
        return {**existing, 'job_id': snapshot.get('job_id'), 'snapshot_status': snapshot['status'], 'reused': True}
    inspected = inspect_request(arguments)
    # The fault is the user's literal request, not an AI-generated suggestion.
    scenario = {'name': 'Ausfall ' + gateway['name'], 'mode': 'USER_DEFINED_FAULT',
                'source': 'explicit_user_request', 'description': workload['goal']['original_request'],
                'created_by': arguments.get('_actor', 'engineering-agent'),
                'faults': [{'type': 'GATEWAY_DROP', 'scope': 'NETWORK', 'target': {'id': str(gateway['id'])},
                            'start_s': 0, 'source': 'explicit_user_request'}]}
    config = prepare_workflow_simulation_config({'duration_mode': 'AUTO_OBSERVATION',
        'observation_window': {'mode': 'AUTO_REQUIREMENTS'}, 'formats': ['universal-jsonl'],
        'scenario': scenario}, current_project_id())
    # Both artifacts and their goal identity share the MCP project transaction.
    saved = save_scenario({**config['scenario'], 'duration_s': config['duration_s']})
    config['scenario'] = {**config['scenario'], 'faults': saved['faults'],
                          'scenario_id': str(saved['scenario_id'])}
    snapshot = workflow.create_simulation_snapshot(config, metadata_only=True)
    execution = {'scenario_id': str(saved['scenario_id']), 'snapshot_id': snapshot['id'],
                 'gateway_id': str(gateway['id']), 'gateway_name': gateway['name'],
                 'route_ids': inspected['route_ids'], 'model_revision': arguments['expected_model_revision']}
    workload['simulation_execution'] = execution
    conversation.write(state)
    return {**execution, 'job_id': snapshot.get('job_id'), 'snapshot_status': snapshot['status'], 'reused': False}


def assess(arguments):
    from ..simulation import list_scenarios
    from ..reasoning.service import ReasoningService
    state, workload, gateway = _load(arguments)
    execution = workload.get('simulation_execution') or {}
    if not execution or execution.get('gateway_id') != str(gateway['id']):
        raise EngineeringValidationError('Für diesen Gateway-Auftrag fehlt ein gespeicherter Simulationsstand.')
    workflow = WorkflowStatusService(current_project_id())
    snapshot = _current_snapshot(workflow, execution)
    job_id = snapshot.get('job_id')
    if not job_id:
        raise EngineeringValidationError('Der gespeicherte Gateway-Simulationsstand wurde noch nicht ausgeführt.')
    job = simulation_gateway.job(job_id)
    reasoning = ReasoningService().get(arguments['reasoning_id']).model_dump(mode='json')
    scenario = next((s for s in list_scenarios() if str(s['scenario_id']) == execution['scenario_id']), {})
    faults = (snapshot.get('configuration') or {}).get('scenario', {}).get('faults') or []
    exact_fault = (len(faults) == 1 and faults[0].get('type') == 'GATEWAY_DROP'
                   and faults[0].get('scope') == 'NETWORK' and faults[0].get('target', {}).get('id') == str(gateway['id'])
                   and faults[0].get('start_s') == 0 and faults[0].get('end_s') is None)
    scenario_valid = (exact_fault and scenario.get('mode') == 'USER_DEFINED_FAULT'
                      and scenario.get('faults') == faults
                      and str(snapshot['configuration']['scenario'].get('scenario_id')) == execution['scenario_id'])
    complete_job = (job.get('id') == job_id and job.get('status') == 'completed' and job.get('project_id') == current_project_id()
                    and job.get('workflow_snapshot_id') == snapshot['id'] and snapshot.get('status') == 'COMPLETED')
    communications = snapshot['configuration'].get('communications') or []
    route_map = {c['id']: c.get('routing_entry_id') or c.get('canonical_route_id') for c in communications
                 if str(gateway['id']) in (c.get('gateways') or [])}
    result = (job.get('result') or {}).get('model_simulation') or {}
    dropped = [f for f in result.get('frames') or [] if 'GATEWAY_DROP' in (f.get('faults') or [])]
    traced = bool(complete_job and dropped and all(f.get('status') == 'dropped'
                  and str(gateway['id']) in (f.get('gateway_ids') or []) and f.get('route_id') in route_map
                  and f.get('event_id') for f in dropped))
    affected = sorted({route_map[f['route_id']] for f in dropped if route_map.get(f.get('route_id'))})
    routes_valid = bool(traced and affected and set(affected) <= set(execution['route_ids'])
                        and all(f['route_id'] in (result.get('affected_routes') or []) for f in dropped))
    event_ids = {f.get('event_id') for f in dropped}
    trace_refs = {e['id'] for e in reasoning.get('evidence_refs') or [] if e.get('source_type') == 'TraceEvent'
                  and e.get('simulation_run_id') == job_id and e.get('source_id') in event_ids}
    lineage = reasoning.get('lineage') or {}
    versions = workflow.get(summary=True)['versions']
    findings_valid = bool(routes_valid and reasoning.get('project_id') == current_project_id()
        and reasoning.get('simulation_run_id') == job_id and lineage.get('simulation_snapshot') == snapshot['id']
        and lineage.get('snapshot_outdated') is False and reasoning.get('validation_status') == 'CURRENT'
        and reasoning.get('completion_status') == 'COMPLETE'
        and all(lineage.get('source_versions', {}).get(k) == versions.get(k) for k in SOURCE_STEPS)
        and any(c.endswith(':GATEWAY_DROP') for c in reasoning.get('confirmed_causes') or [])
        and any(f.get('code') == 'ROOT_CAUSE_IDENTIFIED' and trace_refs.intersection(f.get('evidence_refs') or [])
                for f in reasoning.get('findings') or []))
    outcomes = dict(zip(OUTCOMES, [True, bool(scenario_valid), bool(complete_job), traced, routes_valid, findings_valid]))
    complete = all(outcomes.values())
    canonical_routes = {str(r['id']): r for r in model.routes()}
    affected_communications = [{'route_id': identifier,
        'name': canonical_routes[identifier]['name'],
        'message_ids': (canonical_routes[identifier].get('payload') or {}).get('message_ids') or []}
        for identifier in affected if identifier in canonical_routes]
    details = {**execution, 'job_id': job_id, 'reasoning_id': reasoning['reasoning_id'],
               'outcomes': outcomes, 'completion': {'complete': complete}, 'affected_route_ids': affected,
               'affected_communications': affected_communications,
               'dropped_frame_count': len(dropped), 'findings': reasoning.get('findings') or [],
               'evidence_refs': reasoning.get('evidence_refs') or [],
               'scope': 'SIMULATED_GATEWAY_OUTAGE_NOT_FUNCTIONAL_TIMING_RELEASE'}
    workload['simulation_execution'] = {**execution, 'job_id': job_id, 'reasoning_id': reasoning['reasoning_id']}
    conversation.write(state)
    return details
