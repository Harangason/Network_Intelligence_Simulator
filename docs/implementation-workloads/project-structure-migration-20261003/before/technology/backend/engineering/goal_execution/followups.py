"""Persisted simulation/trace follow-ups of an explicitly authorized connection.

External jobs are dispatched after the canonical transaction commits. A snapshot
can be claimed only once by the existing job service; retries inspect that same
snapshot. A simulation start is never evidence that communication occurred.
"""
import re
import json
from hashlib import sha256
from .graph import ModelGraphService
from .store import get_goal, save_goal
from .executor import journal


def requested_followups(text):
    if re.search(r'\b(?:nicht|keine|ohne|no|without)\s+(?:simulat\w*|simulier\w*)', text, re.I):
        return []
    if not re.search(r'\b(?:simuliere\w*|simulate|simulation)\b', text, re.I): return []
    return ['SIMULATE_SCENARIO', 'ANALYZE_TRACE'] if re.search(r'\b(?:analysiere|analyze|traceanalyse)\b', text, re.I) else ['SIMULATE_SCENARIO']


def simulation_configuration(text, state):
    scenario_text = re.sub(r'\b(?:ohne Fehler|ohne Fehleraufschaltung|no faults)\b', '', text, flags=re.I)
    if re.search(r'\b(?:stress\w*|ausfall\w*|fehler\w*|fault\w*|bus.off|dropout|jitter|vergleich\w*|compare)\b', scenario_text, re.I):
        raise ValueError('Der zusätzliche Szenarioauftrag benötigt einen bestätigten Szenario-/Fehlerumfang. Eine Normalprüfung würde diesen Auftrag nicht erfüllen.')
    settings = (state.get('context') or {}).get('engineering_wizard_settings') or {}
    duration = float(settings.get('duration_s') or state.get('parameters', {}).get('duration_s') or 1.0)
    explicit = re.search(r'\b(?:für|for|dauer|duration)\s*([0-9]+(?:[.,][0-9]+)?)\s*(ms|millisekunden|sekunden|seconds|s|minuten|minutes|min)\b', text, re.I)
    if explicit:
        unit = explicit[2].lower()
        duration = float(explicit[1].replace(',', '.')) * (0.001 if unit in {'ms', 'millisekunden'} else 60 if unit in {'min', 'minuten', 'minutes'} else 1)
    if not 0.001 <= duration <= 3600: raise ValueError('Die Simulationsdauer muss zwischen 1 ms und 3600 s liegen.')
    seed = re.search(r'\bseed\s*[:=]?\s*([0-9]+)', text, re.I)
    return {'duration_s': duration, 'seed': int(seed[1]) if seed else 42, 'max_events': 100000,
        'formats': ['universal-jsonl'], 'scenario': {'mode': 'NORMAL', 'faults': []}}


def advance(goal, present):
    from ..agent_tools.runtime import PostCommitAction
    from ..workflow.service import WorkflowStatusService
    from ..project_context import current_project_id
    from ..simulation import prepare_workflow_simulation_config
    auth = goal.get('followup_authorization') or {}
    if auth.get('goal') != goal['goal'] or auth.get('goal_types') != goal.get('followup_goals'):
        raise PermissionError('Für die Simulation fehlt die gespeicherte Freigabe des Gesamtauftrags.')
    graph = ModelGraphService.load()
    if auth.get('model_revision') != graph.revision:
        goal.update(status='PLAN_STALE', followup_authorization=None)
        journal(goal, 'FOLLOWUP_MODEL_CHANGED', expected=auth.get('model_revision'), actual=graph.revision)
        return present(save_goal(goal))
    workflow = WorkflowStatusService(current_project_id())
    followup = goal.setdefault('followup', {})
    snapshot = workflow.get_simulation_snapshot(followup['snapshot_id']) if followup.get('snapshot_id') else None
    if snapshot is None:
        # Reproducible NORMAL verification uses persisted scenario settings when
        # present. This test scenario does not supply missing functional demands.
        config = goal['plan']['followup_configuration']
        frozen = prepare_workflow_simulation_config(config, current_project_id())
        frozen['engineering_model']['hardware_interfaces'] = list(graph.hni.values())
        frozen['engineering_model']['communication_resources'] = graph.resources
        snapshot = workflow.create_simulation_snapshot(frozen)
        followup.update(snapshot_id=str(snapshot['id']), configuration=config)
        journal(goal, 'SIMULATION_SNAPSHOT_PREPARED', snapshot_id=snapshot['id'], configuration=config)
    if snapshot.get('is_outdated'):
        goal.update(status='PLAN_STALE', followup_authorization=None)
        return present(save_goal(goal))
    job_id = snapshot.get('job_id') or followup.get('job_id')
    if not job_id and snapshot['status'] != 'READY':
        goal['status'] = 'SIMULATION_RUNNING'
        goal['findings'] = [{'code': 'SIMULATION_DISPATCH_PENDING', 'severity': 'OPEN',
            'message': 'Der vorhandene Snapshot wurde bereits reserviert. Sein Job wird erneut geprüft; kein zweiter Lauf wird angelegt.'}]
        return present(save_goal(goal))
    goal['status'] = 'SIMULATION_RUNNING'
    save_goal(goal)
    workload_id, snapshot_id = goal['workload_id'], str(snapshot['id'])
    def dispatched():
        from ..agent_tools import simulation_gateway
        item = simulation_gateway.job(job_id) if job_id else simulation_gateway.start(snapshot_id)
        # Network reads must precede acquiring the project lock for the journal.
        trace, observed, trace_count, trace_hash = [], set(), 0, sha256()
        if str(item.get('status')).lower() == 'completed':
            for event in simulation_gateway.iter_trace(str(item['id'])):
                trace_count += 1
                trace_hash.update(json.dumps(event, sort_keys=True, default=str).encode())
                trace_hash.update(b'\n')
                if len(trace) < 100000: trace.append(event)
                if event.get('status') == 'transmitted' and event.get('final_segment', True) and str(event.get('traffic_type', 'DATA')).upper() == 'DATA':
                    observed.update(str(ref) for ref in [event.get('route_ref'), event.get('canonical_route_id'), *(event.get('route_refs') or [])] if ref)
        current = get_goal(workload_id)
        saved_snapshot = workflow.get_simulation_snapshot(snapshot_id)
        if (current['status'] in {'COMPLETE', 'INCOMPLETE'} and current.get('followup', {}).get('job_id') == str(item['id'])
                and current.get('completion', {}).get('model_revision') == auth['model_revision']):
            return present(current)
        if (current.get('followup_authorization') != auth or ModelGraphService.load().revision != auth['model_revision']
                or not saved_snapshot or saved_snapshot.get('is_outdated')):
            current.update(status='PLAN_STALE', followup_authorization=None)
            return present(save_goal(current))
        current['followup']['job_id'] = str(item['id'])
        state = str(item.get('status')).lower()
        if state in {'failed', 'canceled'}:
            current.update(status='FAILED', findings=[{'severity': 'ERROR', 'code': 'SIMULATION_FAILED',
                'message': str(item.get('error') or 'Simulationslauf abgebrochen.')}])
            current['completion']['status'] = 'FAILED'
        elif state == 'completed':
            if saved_snapshot.get('status') != 'COMPLETED' or str(saved_snapshot.get('job_id')) != str(item['id']):
                current['status'] = 'SIMULATION_RUNNING'
                return present(save_goal(current))
            current['followup'].update(event_count=trace_count, observed_routes=sorted(observed), trace_sha256=trace_hash.hexdigest())
            evidence = {**current['connection_completion']['evidence'], 'simulation_complete': True,
                'communication_observed': set(current['route_ids']) <= observed}
            if 'ANALYZE_TRACE' in current['followup_goals']:
                from ..agent_tools.analysis import analyze
                analysis = analyze({'events': trace or [], 'configuration': snapshot['configuration']})
                current['followup']['analysis'] = analysis
                evidence['analysis_complete'] = analysis.get('available') is not False and analysis.get('event_count', 0) > 0 and trace_count == len(trace)
            missing = [key for key, valid in evidence.items() if valid is not True]
            current['completion'] = {'status': 'INCOMPLETE' if missing else 'COMPLETE', 'evidence': evidence,
                'missing_conditions': missing, 'model_revision': auth['model_revision']}
            current['status'] = current['completion']['status']
            current['followup_authorization'] = None
            journal(current, 'SIMULATION_EVALUATED', job_id=item['id'], completion=current['completion'])
        return present(save_goal(current))
    def failed():
        current = get_goal(workload_id)
        journal(current, 'SIMULATION_DISPATCH_RETRYABLE', snapshot_id=snapshot_id)
        save_goal(current)
    return PostCommitAction(dispatched, failed)
