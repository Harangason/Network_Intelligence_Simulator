"""Read-only, message-scoped timing evidence from the canonical model."""
from __future__ import annotations

import re

from ..capacity.service import CapacityTimingService
from ..project_context import current_project_id
from . import model
from .communication_evidence import simulation_sequence


def inspect_message_timing(arguments: dict) -> dict:
    revision = model.model_revision()
    request = str(arguments['request']).strip()
    messages = model.objects('Message')
    mentioned = [item for item in messages if re.search(
        rf'(?<!\w){re.escape(str(item.get("name") or item["id"]))}(?!\w)', request, re.I)]
    if len(mentioned) != 1:
        return {
            'status': 'MESSAGE_NOT_RESOLVED' if not mentioned else 'AMBIGUOUS_MESSAGE',
            'reason': ('Keine eindeutige kanonische Nachricht im Auftrag gefunden.' if not mentioned
                       else 'Mehrere kanonische Nachrichten sind im Auftrag genannt.'),
            'candidates': [{'id': str(item['id']), 'name': item.get('name')} for item in mentioned],
            'model_revision': model.model_revision(),
        }
    message = mentioned[0]
    calculation = CapacityTimingService(current_project_id()).calculate(persist=False)
    route_rows = [row for row in calculation.get('results', {}).get('routes', [])
                  if str(row.get('message_id')) == str(message['id'])]
    routes = {}
    for row in route_rows:
        route_id = str(row['route_id'])
        route = routes.setdefault(route_id, {
            'route_id': route_id,
            'end_to_end_latency_ms': row.get('end_to_end_latency_ms'),
            'max_latency_ms': row.get('max_latency_ms'),
            'latency_status': row.get('latency_status'),
            'estimated_jitter_ms': row.get('estimated_jitter_ms'),
            'jitter_budget_ms': row.get('jitter_budget_ms'),
            'breakdown_ms': row.get('breakdown') or {},
            'bottleneck': row.get('bottleneck') or {},
            'network_ids': [],
            'protocols': [],
        })
        network_id = str(row.get('network_id') or '')
        protocol = str(row.get('protocol') or '')
        if network_id and network_id not in route['network_ids']:
            route['network_ids'].append(network_id)
        if protocol and protocol not in route['protocols']:
            route['protocols'].append(protocol)
    ordered = list(routes.values())
    sequence = simulation_sequence(set(routes)) if routes else {'status': 'NOT_OBSERVED', 'reason': 'NO_ROUTE', 'transactions': []}
    if model.model_revision() != revision or sequence.get('reason') == 'MODEL_CHANGED':
        return {'status': 'MODEL_CHANGED', 'reason': 'Der Modellstand änderte sich während der Diagnose. Erneut lesen.',
                'routes': [], 'model_revision': revision}
    status = ('NO_ROUTE' if not ordered else
              'NO_DEADLINE' if all(row['max_latency_ms'] is None for row in ordered) else
              'MODEL_DEADLINE_FAIL' if any(row['latency_status'] == 'FAIL' for row in ordered) else
              'MODEL_DEADLINE_PASS' if all(row['latency_status'] == 'PASS' for row in ordered) else
              'TIMING_UNVERIFIED')
    return {
        'status': status, 'message': {'id': str(message['id']), 'name': message.get('name')},
        'routes': ordered, 'model_revision': revision, 'sequence': sequence,
        'calculation_version': calculation.get('provenance', {}).get('calculation_version'),
        'capacity_status': calculation.get('status'), 'evidence_kind': 'CALCULATED_MODEL',
        'observed_trace_available': False,
        'simulation_trace_available': sequence.get('status') == 'SIMULATED',
        'reason': ('Für diese Nachricht ist keine berechenbare Route vorhanden.' if status == 'NO_ROUTE' else
                   'Für diese Nachricht ist keine maximale E2E-Latenz bestätigt.' if status == 'NO_DEADLINE' else ''),
    }
