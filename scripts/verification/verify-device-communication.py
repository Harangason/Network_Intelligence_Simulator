"""Revalidate current routes after the minimum-communication migration."""

import sys as _entry_sys
from pathlib import Path as _EntryPath
_entry_sys.path.insert(0, str(_EntryPath(__file__).resolve().parents[1]))
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.nis.agent.tools import model as model
from backend.nis.infrastructure.persistence.db import RequestUnit
from backend.nis.infrastructure.persistence.db import close_pool
from backend.nis.engineering.projects.project_context import activate_project
from backend.nis.engineering.projects.project_context import reset_project
from backend.nis.engineering.routing.validation import RoutingValidator
from backend.nis.engineering.routing.repository import save_validation
from backend.nis.engineering.signals.signal_audit import inspect_message_signals
project = 'network-project-20260909082213746-780a13ef'
token = activate_project(project)
unit = RequestUnit(project)
try:
    validator = RoutingValidator(project_id=project)
    invalid, ready = [], []
    for route in model.routes():
        if route['status'] in ('OUTDATED', 'REJECTED', 'SUPERSEDED'):
            continue
        result = validator.validate(route, exclude_route_id=route['id'])
        if not result['valid']:
            invalid.append({'route': route['route_code'], 'errors': result['errors']})
        if route['status'] == 'CONFLICT' or not result['valid']:
            saved = save_validation(route['id'], result, actor='device-communication-validation')
            if saved['status'] == 'READY_FOR_REVIEW':
                ready.append(route['route_code'])
    signals = model.objects('Signal')
    packing = []
    for message in model.objects('Message'):
        items = [s for s in signals if str(s.get('message_id')) == str(message['id'])]
        if not any((s.get('configuration') or {}).get('template') == 'generic-simulation-actuator-v1' for s in items):
            continue
        for report in inspect_message_signals(items, message):
            errors = [c for c in report['checks'] if c['severity'] == 'ERROR']
            if errors:
                packing.append({'message': message['name'], 'errors': errors})
    assert not packing, packing
    unit.finish(True)
    print(json.dumps({'ready_for_review': len(ready), 'invalid_routes': invalid, 'packing_errors': packing,
        'statuses': dict(Counter(r['status'] for r in model.routes()))}, default=str))
finally:
    unit.close()
    reset_project(token)
    close_pool()
