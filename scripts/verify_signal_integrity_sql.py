"""Verify on a separate SQL database; --apply-live adopts the approved repair."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import psycopg

sys.path[:0] = ['/app', '/app/backend', '/app/backend/simulator']
parser = argparse.ArgumentParser()
parser.add_argument('bundle')
parser.add_argument('--apply-live', action='store_true')
args = parser.parse_args()
bundle = json.loads(Path(args.bundle).read_text())
source = 'network-project-20260910042736034-d11591d0'
assert bundle['source_project_id'] == source
if not args.apply_live:
    url = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg', 'postgresql'))
    database = 'nis_signal_integrity_tests'
    assert url.path != '/' + database
    with psycopg.connect(urlunsplit(url._replace(path='/postgres')), autocommit=True) as connection:
        if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
            connection.execute('CREATE DATABASE nis_signal_integrity_tests')
    os.environ['DATABASE_URL'] = urlunsplit(url._replace(path='/' + database))

from backend.app import create_app
from backend.engineering import db
from backend.engineering.project_bundle import ProjectBundleService
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.signal_integrity_service import SignalIntegrityService
from backend.engineering.repository import list_objects
from backend.engineering.pagination import all_pages
from backend.engineering.routing.repository import list_routes
from backend.engineering.capacity.service import CapacityTimingService

create_app(testing=not args.apply_live)
project = source if args.apply_live else 'pytest-integrity-' + str(uuid4())
token = activate_project(project)
try:
    if not args.apply_live:
        ProjectBundleService().import_bundle(bundle, target_project_id=project)
    service = SignalIntegrityService(project)
    before = all_pages(list_objects, 'Signal')
    physical = service.workflow.get()['topology']
    plan = service.preview()
    print(json.dumps({'stage': 'preview', 'changes': len(plan['changes']), 'remaining': len(plan['remaining'])}), flush=True)
    if not args.apply_live:
        try:
            service.apply('stale-token')
            raise AssertionError('Stale plan accepted')
        except db.ConcurrentUpdateError:
            pass
        from backend.engineering import signal_integrity_service as implementation
        original = implementation.update_object
        count = 0
        def failing(*a, **kw):
            global count
            result = original(*a, **kw)
            count += 1
            if count == 2:
                raise ValueError('injected write failure')
            return result
        try:
            with patch.object(implementation, 'update_object', side_effect=failing):
                service.apply(plan['token'], approve_valid=True)
            raise AssertionError('Injected failure not raised')
        except ValueError as error:
            assert str(error) == 'injected write failure', error
        assert all_pages(list_objects, 'Signal') == before, 'Transaction did not roll back'
        print(json.dumps({'stage': 'rollback', 'passed': True}), flush=True)
    receipt = service.apply(service.preview()['token'], approve_valid=True)
    after = all_pages(list_objects, 'Signal')
    before_by_id = {str(s['id']): s for s in before}
    for signal in after:
        original = before_by_id[str(signal['id'])]
        for field in ('start_bit', 'length_bits', 'factor', 'offset_value', 'min_value', 'max_value', 'data_type', 'byte_order', 'message_id'):
            assert signal[field] == original[field], (signal['name'], field)
    current_topology = service.workflow.get()['topology']
    for field in ('nodes', 'edges', 'networks'):
        assert current_topology.get(field) == physical.get(field), field
    repeat = service.apply(service.preview()['token'], approve_valid=True)
    assert repeat['changed_signals'] == 0
    routes = all_pages(list_routes)
    capacity = CapacityTimingService(project).calculate(persist=True)
    brake = [{key: n.get(key) for key in ('network_name', 'protocol', 'average_load_percent', 'evaluation')}
             for n in capacity['results']['networks'] if str(n.get('network_name', '')).startswith('Bremsregelung LIN')]
    result = {'project': project, 'receipt': receipt, 'idempotent': True, 'physical_encoding_unchanged': True,
        'topology_unchanged': True, 'route_count': len(routes), 'approved_routes': sum(r['status'] == 'APPROVED' for r in routes),
        'capacity_status': capacity['status'], 'signal_quality': capacity['results']['signal_quality']['summary'], 'brake_networks': brake}
    assert not any(f['severity'] == 'ERROR' for f in capacity['findings']), capacity['findings']
    output = Path('/verification-output') if Path('/verification-output').exists() else Path('/tmp')
    (output / ('signal-integrity-' + ('live' if args.apply_live else 'sql') + '.json')).write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in {'receipt', 'brake_networks'}}, default=str), flush=True)
finally:
    reset_project(token)
    db.close_pool()
