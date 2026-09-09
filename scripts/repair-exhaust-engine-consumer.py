"""Apply the user's confirmed exhaust-status consumer through canonical review APIs."""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.db import RequestUnit, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.agent_tools import model, proposal_service
from backend.engineering.repository import update_object
from backend.engineering.routing.generation import RoutingGenerationService
from backend.engineering.routing.validation import RoutingValidator
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.confirmed_routes import route_keys

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--requirement-only', action='store_true')
args = parser.parse_args()
project = 'network-project-20260909082213746-780a13ef'
token = activate_project(project)
unit = RequestUnit(project)
try:
    nodes = model.objects('HardwareNode')
    source = next(n for n in nodes if n['name'] == 'Abgasnachbehandlung')
    target = next(n for n in nodes if n['name'] == 'Motorsteuerung')
    message = next(m for m in model.objects('Message') if str(m['id']) == '5d0429b9-6aed-4540-ab29-02aac3230d94')
    routes = model.routes()
    config = deepcopy(message['configuration'])
    consumers = set(config['transport_unit'].get('consumer_refs') or [])
    # Preserve every existing approved receiver when making the previously empty list explicit.
    for route in routes:
        payload = route.get('payload') or {}
        if route.get('approval_state') == 'APPROVED' and str(message['id']) in [str(payload.get('message_id') or ''), *map(str, payload.get('message_ids') or [])]:
            consumers.update(str(d['node_id']) for d in route['destinations'])
    consumers.add(str(target['id']))
    config['transport_unit']['consumer_refs'] = sorted(consumers)
    config['transport_unit']['consumer_provenance'] = {
        'source': 'user-confirmed-requirement',
        'requirement': 'Motorsteuerung empfängt den Status der Abgasnachbehandlung; bestehende Anzeigeempfänger bleiben erhalten.',
    }
    key = (str(source['id']), str(target['id']), str(message['id']))
    exists = key in route_keys(routes, model.objects('Signal'))
    route = RoutingGenerationService().generate_route(source_node_id=key[0], destination_node_id=key[1], message_id=key[2])
    validation = RoutingValidator().validate(route)
    if not validation['valid']:
        raise ValueError(json.dumps(validation))
    report = {'applied': False, 'already_exists': exists, 'source': source['name'], 'target': target['name'], 'route': route, 'validation': validation, 'consumer_refs': sorted(consumers)}
    if args.apply and not args.requirement_only and validation.get('metrics', {}).get('physical_path_mapped') is not True:
        raise ValueError('Kein nachgewiesener physischer Pfad; Route wird nicht freigegeben.')
    if args.apply:
        if config != message['configuration']:
            update_object('Message', key[2], {'configuration': config, 'expected_version': message['version']})
        if not exists and not args.requirement_only:
            route['description'] = config['transport_unit']['consumer_provenance']['requirement']
            proposal = proposal_service.create('WIZARD_ROUTING', [{'object_type': 'RoutingEntry', 'data': route}], route['description'], evidence=[config['transport_unit']['consumer_provenance']])
            proposal = proposal_service.validate(proposal['proposal_id'])
            if proposal['status'] != 'VALIDATED':
                raise ValueError(str(proposal.get('validation_result')))
            proposal = proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='user-confirmed-consumer-repair', trace_id=str(uuid4()))
            applied = proposal_service.apply(proposal['proposal_id'], actor='user-confirmed-consumer-repair', trace_id=str(uuid4()))
            report['canonical_ids'] = applied['canonical_ids']
            WorkflowStatusService(project).mark_changed('routing', reason=route['description'], actor='user-confirmed-consumer-repair')
        if config != message['configuration']:
            WorkflowStatusService(project).mark_changed('engineering_model', reason='Motorsteuerung als bestätigten Status-Empfänger hinterlegt; physischer Buspfad offen.', actor='user-confirmed-consumer-repair')
        report['requirement_only'] = args.requirement_only
        unit.finish(True)
        report['applied'] = True
    print(json.dumps(report, ensure_ascii=False, default=str))
finally:
    unit.close()
    reset_project(token)
    close_pool()


