"""Select existing current simulation evidence by canonical route identity."""
from copy import deepcopy

from ..project_context import current_project_id
from ..workflow.service import WorkflowStatusService

SOURCE_STEPS = ('engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing', 'validation', 'simulation')


def simulation_sequence(route_ids: set[str]) -> dict:
    workflow = WorkflowStatusService(current_project_id())
    state = workflow.get()
    analysis = workflow.latest_analysis('results_analysis')
    result = select_simulation_sequence(analysis, state, route_ids, current_project_id())
    after = workflow.get()['versions']
    if any(after.get(key) != state['versions'].get(key) for key in SOURCE_STEPS):
        return unavailable('MODEL_CHANGED')
    return result


def unavailable(reason: str) -> dict:
    return {'status': 'NOT_OBSERVED', 'reason': reason, 'transactions': [],
            'receiver_action': 'NOT_OBSERVED', 'observed_trace_available': False}


def select_simulation_sequence(analysis: dict | None, state: dict, route_ids: set[str], project_id: str) -> dict:
    """Copy canonical facts; never infer a transaction or receiver acceptance."""
    if not analysis or analysis.get('is_outdated') or analysis.get('project_id') != project_id:
        return unavailable('NO_CURRENT_SIMULATION')
    versions = analysis.get('source_versions') or {}
    current = state.get('versions') or {}
    if any(type(versions.get(key)) is not int or type(current.get(key)) is not int
           or versions[key] != current[key] for key in SOURCE_STEPS):
        return unavailable('STALE_SIMULATION')
    results = analysis.get('results') or {}
    configuration = (analysis.get('input_data') or {}).get('configuration') or {}
    if results.get('status') != 'COMPLETED' or not results.get('simulation_snapshot_id'):
        return unavailable('SIMULATION_NOT_COMPLETED')
    mapping = {}
    for communication in configuration.get('communications') or []:
        if communication.get('canonical_route_id') and communication.get('routing_entry_id') and communication['canonical_route_id'] != communication['routing_entry_id']:
            continue
        canonical = communication.get('canonical_route_id') or communication.get('routing_entry_id')
        if canonical in route_ids and communication.get('id'):
            mapping[str(communication['id'])] = str(canonical)
    metrics = results.get('runtime_metrics') or {}
    model = metrics.get('sequence_model') or {}
    if model.get('source') != 'SIMULATED':
        return unavailable('SIMULATION_SEQUENCE_UNAVAILABLE')
    transactions = [item for item in metrics.get('e2e_transactions') or [] if item.get('route_id') in mapping]
    sequence_transactions = {item['id']: item for item in model.get('transactions') or [] if item.get('id')}
    chosen, events, presentations = [], [], []
    candidate_count = len(transactions)
    seen = set()
    for item in transactions:
        identifier = item.get('transaction_id')
        presentation = sequence_transactions.get(identifier)
        if not identifier or identifier in seen or not presentation:
            continue
        seen.add(identifier)
        evidence_ids = set(item.get('evidence_event_ids') or [])
        visible_ids = set(presentation.get('eventIds') or [])
        selected = [event for event in model.get('events') or []
                    if event.get('transactionId') == identifier and event.get('id') in evidence_ids]
        if not selected or {event['id'] for event in selected} != visible_ids or not visible_ids <= evidence_ids:
            continue
        if presentation.get('receiverStatus') != item.get('receiver_status'):
            continue
        if len(chosen) >= 100 or len(events) + len(selected) > 200:
            continue
        chosen.append({**deepcopy(item), 'canonical_route_id': mapping[item['route_id']]})
        events.extend(deepcopy(selected))
        presentations.append(deepcopy(presentation))
    if not chosen:
        return unavailable('NO_CORRELATED_ROUTE_TRANSACTIONS')
    selected_ids = {event['id'] for event in events}
    events = [deepcopy(event) for event in model.get('events') or [] if event.get('id') in selected_ids]
    participants = sorted({str(event[key]) for event in events for key in ('source', 'destination')})
    return {'status': 'SIMULATED', 'source': 'SIMULATED', 'observed_trace_available': False,
            'analysis_id': str(analysis['id']), 'simulation_snapshot_id': results['simulation_snapshot_id'],
            'job_id': results.get('job_id'), 'source_versions': deepcopy(versions),
            'release': deepcopy(configuration.get('release') or {}),
            'transactions': chosen, 'candidate_transaction_count': candidate_count,
            'truncated_or_uncorrelated_count': candidate_count - len(chosen),
            'receiver_action': 'EVIDENCED_IN_SIMULATION' if any(item.get('receiver_status') in {'ACCEPTED', 'REJECTED'} for item in chosen) else 'NOT_OBSERVED',
            'model': {**deepcopy(model), 'events': events, 'transactions': presentations,
                      'participants': participants, 'correlatedCount': len(events), 'uncorrelatedCount': 0}}
