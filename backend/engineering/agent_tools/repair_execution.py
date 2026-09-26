"""Durable repair handoff: model review, human architecture choice, MCP execution."""
from uuid import uuid4

from ..communication_repair import load_plan, complete_plan, public_plan, apply_repair
from ..goal_execution.store import get_goal, save_goal
from ..project_context import current_project_id
from ..db import ConcurrentUpdateError
from .specialist import review_or_report, candidate_batches


def prepare(arguments):
    planner, _ = load_plan()
    plan = public_plan(complete_plan(planner))
    plan = store_plan(plan)
    return plan if arguments.get('defer_review') else review_saved({'workload_id': plan['workload_id']})


def review_saved(arguments):
    workload_id = arguments['workload_id']
    goal = get_goal(workload_id)
    if not workload_id.startswith('repair-') or goal.get('status') != 'WAITING_FOR_USER':
        raise ConcurrentUpdateError('Der Reparaturauftrag wurde bereits geändert. Den aktuellen Plan prüfen.')
    plan = goal['plan']
    # Inference must not hold the canonical project's write lock. Its snapshot
    # is immutable; the revision is rechecked before publishing the assessment.
    from ..db import _request_unit
    unit = _request_unit.get()
    if unit is not None:
        unit.finish(True)
    candidates = [{'id': option['id'], 'group': group['id'], 'reason': group['reason'], **option}
                  for group in plan['groups'] for option in group['options']]
    # Option IDs are group-local in some historical plans.
    for item in candidates:
        item['id'] = item['group'] + ':' + item['id']
    candidates.extend({'id': group['id'] + ':blocked', 'reason': group['reason'],
                       'routes': group['routes'], 'connections': group['connections'],
                       'restore_unavailable': group.get('restore_unavailable')}
                      for group in plan['groups'] if not group['options'])
    previous = plan.get('agent_review') or {}
    if previous.get('status') in {'REVIEWED', 'NO_CANDIDATES'}:
        return plan
    completed = {item['id']: item for item in previous.get('decisions', [])}
    remaining = [item for item in candidates if item['id'] not in completed]
    batch = next(iter(candidate_batches(remaining)), [])
    review = review_or_report('Kommunikationsreparatur: neue Führung oder historische Führung; Funktionspartner erhalten', batch)
    completed.update({item['id']: item for item in review['decisions']})
    review['decisions'] = list(completed.values())
    review['gaps'] = list(dict.fromkeys([*previous.get('gaps', []), *review['gaps']]))
    review['total'] = len(candidates)
    review['trace_ids'] = [*previous.get('trace_ids', []), review['trace_id']]
    if review['status'] == 'REVIEWED' and len(completed) < len(candidates):
        review['status'] = 'REVIEWING'
    plan['agent_review'] = review
    ranking = {item['id']: item['recommended'] for item in review['decisions']}
    for group in plan['groups']:
        group['options'].sort(key=lambda option: not ranking.get(group['id'] + ':' + option['id'], False))
    goal = get_goal(workload_id)
    planner, _ = load_plan()
    if goal.get('status') != 'WAITING_FOR_USER' or planner.build()['token'] != plan['token']:
        raise ConcurrentUpdateError('Die Architektur wurde während der KI-Prüfung geändert. Erneut prüfen.')
    if len((goal['plan'].get('agent_review') or {}).get('decisions', [])) > len(completed):
        return goal['plan']
    goal['plan'] = plan
    save_goal(goal)
    return plan


def store_plan(plan):
    workload_id = 'repair-' + uuid4().hex
    plan['workload_id'] = workload_id
    plan['agent_response'] = {'type': 'RESULT', 'status': 'READY_FOR_REVIEW' if plan['groups'] else 'ANSWERED',
        'text': f"{len(plan['groups'])} Reparaturgruppen anhand der aktuellen Architektur geprüft. Die gewählte Führung wird auf Anschlüsse, Nachrichten und Routing angewendet und erneut validiert.",
        'actions': [{'type': 'CAPABILITY', 'capability_id': 'repair', 'label': 'Reparaturplan öffnen und instandsetzen',
                     'description': 'Neue oder bisherige Führung auswählen; anschließend atomar ausführen.',
                     'project_id': current_project_id(), 'repair_workload': workload_id}]}
    save_goal({'workload_id': workload_id, 'goal_type': 'FIX_VALIDATION', 'status': 'WAITING_FOR_USER',
               'project_id': current_project_id(), 'plan': plan, 'authorization': None, 'journal': []})
    return plan


def authorize(workload_id, token, choices):
    """Only the human REST boundary calls this; it is deliberately not an MCP tool."""
    goal = get_goal(workload_id)
    if goal.get('status') == 'COMPLETE' and goal.get('authorization') == {'token': token, 'choices': choices}:
        return
    if goal.get('status') != 'WAITING_FOR_USER' or goal['plan']['token'] != token:
        raise ConcurrentUpdateError('Der Reparaturplan ist nicht mehr aktuell. Erneut prüfen.')
    if not isinstance(choices, dict) or len(choices) != 1:
        raise ValueError('Eine konkrete Reparaturstrategie auswählen.')
    valid = {g['id']: {o['id'] for o in g['options']} for g in goal['plan']['groups']}
    if any(group not in valid or option not in valid[group] for group, option in choices.items()):
        raise ValueError('Die Strategie gehört nicht zu diesem Reparaturplan.')
    goal['authorization'] = {'token': token, 'choices': choices}
    goal['status'] = 'AUTHORIZED'
    save_goal(goal)


def resume(arguments):
    goal = get_goal(arguments['workload_id'])
    if goal.get('goal_type') != 'FIX_VALIDATION' or not goal.get('authorization'):
        raise PermissionError('Für diesen Reparaturauftrag fehlt die gespeicherte Strategieentscheidung.')
    if goal['status'] == 'COMPLETE':
        return goal['result']
    result = apply_repair(goal['authorization'])
    # Include the newly repaired, not yet released routes in the engineering
    # estimate. Do not publish this draft as the released capacity baseline.
    from ..capacity.service import CapacityTimingService
    assessment = CapacityTimingService(current_project_id()).calculate(persist=False, include_drafts=True)
    result['followup'] = {'status': assessment['status'], 'scope': 'INCLUDING_DRAFT_ROUTES',
        'source_versions': assessment['source_versions'], 'findings': assessment['findings'],
        'provenance': assessment['provenance'], 'results': assessment['results']}
    result['plan'] = store_plan(result['plan'])
    goal['status'] = 'COMPLETE'
    goal['result'] = result
    goal['journal'].append({'event': 'REPAIRED_AND_VALIDATED', 'applied': result['applied']})
    save_goal(goal)
    return result


def inspect(workload_id):
    goal = get_goal(workload_id)
    if not workload_id.startswith('repair-') or goal.get('goal_type') != 'FIX_VALIDATION':
        raise ValueError('Kein Kommunikations-Reparaturauftrag.')
    return goal['result']['plan'] if goal.get('status') == 'COMPLETE' else goal['plan']


def _recipient_workload(workload_id):
    from backend.agent_core.runtime.goal_resolver import recipient_repair_intent, RECIPIENT_REPAIR_OUTCOMES
    from . import conversation
    from ..models import EngineeringValidationError
    state = conversation.read()
    workload = (state.get('engineering_workloads') or {}).get(workload_id)
    goal = (workload or {}).get('goal') or {}
    if (not state.get('run_id') or not workload or workload.get('project_id') != current_project_id()
            or state.get('active_engineering_workload_id') != workload_id
            or workload.get('owner_run_id') != state.get('run_id')
            or goal.get('goal_type') != 'REPAIR' or not recipient_repair_intent(goal.get('original_request', ''))
            or goal.get('required_outcomes') != RECIPIENT_REPAIR_OUTCOMES):
        raise EngineeringValidationError('Ein ausdrücklicher Empfängerprüfauftrag im aktuellen Projekt und Gespräch fehlt.')
    return state, workload


def _recipient_scan():
    from ..communication_contract_repair import scan_signal_recipients
    from ..routing.validation import RoutingValidator
    from .model import model_revision, json_safe
    planner, _ = load_plan()
    validator = RoutingValidator(current_project_id(), physical_planner=planner)
    result = scan_signal_recipients(planner, lambda route:
        validator.validate(route, exclude_route_id=route.get('id')))
    return json_safe({**result, 'project_id': current_project_id(), 'model_revision': model_revision()})


def inspect_recipients(arguments):
    _recipient_workload(arguments['workload_id'])
    scan = _recipient_scan()
    return {key: value for key, value in scan.items() if key != 'changes'}


def prepare_recipients(arguments):
    from . import conversation, proposal_service
    state, workload = _recipient_workload(arguments['workload_id'])
    scan = _recipient_scan()
    if scan['model_revision'] != arguments['expected_model_revision']:
        raise ConcurrentUpdateError('Der Signal- oder Empfängerbestand hat sich seit der Prüfung geändert.')
    changes = scan.pop('changes')
    old = workload.get('recipient_repair') or {}
    proposal = None
    if changes:
        if old.get('proposal_id') and old.get('model_revision') == scan['model_revision']:
            proposal = proposal_service.get(old['proposal_id'])
        else:
            proposal = proposal_service.create('SIGNAL_RECIPIENT_REPAIR', changes,
                workload['goal']['original_request'], evidence=[{'source': 'explicit_signal_recipient_repair',
                    'engineering_goal_id': arguments['workload_id'], 'model_revision': scan['model_revision'],
                    'repairable_signal_ids': scan['repairable_signal_ids'],
                    'review_required_signal_ids': scan['review_required_signal_ids']}], workload_id=arguments['workload_id'])
    workload['recipient_repair'] = {**scan, 'proposal_id': proposal['proposal_id'] if proposal else None}
    conversation.write(state)
    return {**scan, 'proposal': proposal}


def validate_recipient_changes(changes):
    from ..models import EngineeringValidationError
    if changes != _recipient_scan()['changes']:
        raise EngineeringValidationError('Der Vorschlag entspricht nicht den aktuell eindeutig belegten fehlenden Empfängerrouten.')


def reconcile_recipient_apply(proposal, evidence):
    from datetime import datetime, timezone
    from . import conversation
    from ..db import flush_model_changes
    from ..capacity.service import CapacityTimingService, PreflightService
    from ..routing.repository import get_route
    from ..routing.validation import RoutingValidator
    from backend.agent_core.runtime.goal_resolver import recipient_repair_intent, RECIPIENT_REPAIR_OUTCOMES
    state = conversation.read()
    goal_id = str(evidence['engineering_goal_id'])
    workload = (state.get('engineering_workloads') or {}).get(goal_id)
    saved = (workload or {}).get('recipient_repair') or {}
    goal = (workload or {}).get('goal') or {}
    if (not workload or workload.get('project_id') != current_project_id()
            or goal.get('goal_type') != 'REPAIR' or not recipient_repair_intent(goal.get('original_request', ''))
            or goal.get('required_outcomes') != RECIPIENT_REPAIR_OUTCOMES
            or proposal.get('proposal_type') != 'SIGNAL_RECIPIENT_REPAIR'
            or proposal.get('status') != 'APPLIED' or not proposal.get('validation_result', {}).get('valid')
            or saved.get('proposal_id') != proposal.get('proposal_id')
            or evidence.get('model_revision') != saved.get('model_revision')):
        raise ConcurrentUpdateError('Der geprüfte Empfängervorschlag gehört nicht zum gespeicherten Auftrag.')
    canonical = proposal.get('canonical_ids') or []
    if not canonical or len(canonical) != len(proposal.get('changes') or []):
        raise ValueError('Der kanonische Routennachweis ist unvollständig.')
    for item in canonical:
        if item.get('object_type') != 'RoutingEntry':
            raise ValueError('Die Empfängerreparatur darf ausschließlich fehlende Routen ergänzen.')
        route = get_route(item['id'])
        if not RoutingValidator().validate(route, exclude_route_id=item['id'])['valid']:
            raise ValueError('Die übernommene Empfängerroute ist nicht gültig.')
    flush_model_changes(actor='local-human', reason='Eindeutig belegte Empfängerrouten nach Prüfung übernommen.')
    scan = _recipient_scan()
    covered = {item['signal_id'] for item in scan['signals'] if item['status'] == 'COVERED'}
    if (set(scan['scanned_signal_ids']) != set(saved.get('scanned_signal_ids') or [])
            or not set(saved.get('repairable_signal_ids') or []) <= covered
            or set(scan['review_required_signal_ids']) != set(saved.get('review_required_signal_ids') or [])
            or scan['repairable_signal_ids']):
        raise ValueError('Die erneut geprüften Empfänger stimmen nicht mit dem freigegebenen Reparaturumfang überein.')
    capacity = CapacityTimingService(current_project_id()).calculate(persist=True)
    preflight = PreflightService(current_project_id()).run()
    capacity_id = str(capacity.get('id') or capacity.get('snapshot_id') or '')
    preflight_id = str(preflight.get('snapshot_id') or '')
    checked = bool(capacity_id and preflight_id and preflight.get('capacity_snapshot_id') == capacity_id)
    required = goal['required_outcomes']
    missing = [] if checked else ['revalidation_complete']
    refs = [proposal['proposal_id'], *[item['id'] for item in canonical], *[s for s in (capacity_id, preflight_id) if s]]
    completion = {'status': 'COMPLETED' if checked else 'BLOCKED_WITH_EXPLICIT_CAUSE', 'completed': checked,
                  'achieved_outcomes': [key for key in required if key not in missing],
                  'missing_outcomes': missing, 'evidence_refs': refs}
    workload['status'] = completion['status']
    workload['evidence'] = refs
    workload['result'] = {**(workload.get('result') or {}), 'status': 'APPLIED', 'completion': completion,
        'proposal_id': proposal['proposal_id'], 'canonical_ids': canonical,
        'model_diff': proposal['changes'], 'model_revision_after': scan['model_revision'],
        'recipient_revalidation': {key: value for key, value in scan.items() if key != 'changes'},
        'dependent_results': {'capacity_snapshot_id': capacity_id, 'preflight_snapshot_id': preflight_id,
            'capacity_status': capacity.get('status'), 'preflight_status': preflight.get('preflight_status'),
            'ready_for_simulation': preflight.get('ready_for_simulation'),
            'scope': 'Empfängerreparatur geprüft; offene Empfänger bleiben Review-Befunde. Keine funktionale Timing-Freigabe.'}}
    workload['updated_at'] = datetime.now(timezone.utc).isoformat()
    conversation.write(state)
    return True
