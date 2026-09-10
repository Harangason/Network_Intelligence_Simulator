"""Full-project SQL/API regression in an isolated database; never edits source DB.

Run inside NetworkIS: python script.py /tmp/zoning-before-bundle.json
"""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import psycopg

sys.path[:0] = ['/app', '/app/backend', '/app/backend/simulator']
url = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg', 'postgresql'))
database = 'nis_spatial_zoning_tests'
assert url.path != '/' + database
with psycopg.connect(urlunsplit(url._replace(path='/postgres')), autocommit=True) as connection:
    if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
        connection.execute('CREATE DATABASE nis_spatial_zoning_tests')
os.environ['DATABASE_URL'] = urlunsplit(url._replace(path='/' + database))
from backend.app import create_app
from backend.engineering.project_bundle import ProjectBundleService
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.routing.validation import RoutingValidator
from backend.engineering.spatial_zoning import zone_findings
from backend.engineering.repository import list_objects
from backend.engineering.pagination import all_pages

project = 'pytest-zoning-' + str(uuid4())
bundle = json.loads(Path(sys.argv[1]).read_text())
token = activate_project(project)
try:
    ProjectBundleService().import_bundle(bundle, target_project_id=project)
    client = create_app(testing=True).test_client()
    client.environ_base['HTTP_X_PROJECT_ID'] = project
    workflow = WorkflowStatusService(project)
    before = workflow.get()
    preview = client.post('/api/engineering/workflow/spatial-zoning/preview', json={'driving_side': 'LHD'})
    assert preview.status_code == 200, preview.get_json()
    payload = {'driving_side': 'LHD', 'plan_token': preview.get_json()['token'], 'approve_valid': True}
    stale = client.put('/api/engineering/workflow/spatial-zoning', json={**payload, 'plan_token': 'stale'})
    assert stale.status_code == 409, stale.get_json()
    print('stale-token: passed', flush=True)
    with patch.object(RoutingValidator, 'validate', return_value={'valid': False, 'errors': [{'message': 'forced rollback test'}]}):
        failure = client.put('/api/engineering/workflow/spatial-zoning', json=payload)
    assert failure.status_code == 400, failure.get_json()
    assert 'forced rollback test' in json.dumps(failure.get_json()), failure.get_json()
    after_failure = workflow.get()
    assert after_failure['versions'] == before['versions']
    assert after_failure['topology'] == before['topology']
    print('rollback after canonical writes: passed', flush=True)
    applied = client.put('/api/engineering/workflow/spatial-zoning', json=payload)
    assert applied.status_code == 200, applied.get_json()
    state = workflow.get()
    hw = all_pages(list_objects, 'HardwareNode')
    assert not zone_findings(state['topology'], hw, driving_side='LHD')
    repeat = client.post('/api/engineering/workflow/spatial-zoning/preview', json={'driving_side': 'LHD'})
    assert repeat.status_code == 200, repeat.get_json()
    next_plan = repeat.get_json()
    assert not next_plan['divisions'] and not next_plan['new_channels'] and not next_plan['changed_objects'], next_plan
    assert state['parameters']['communication_schedule']['networks']
    assert client.get('/api/engineering/workflow/network-view').get_json()['topology'] == state['topology']
    assert client.put('/api/engineering/workflow/spatial-zoning', json=payload).status_code == 409
    print(json.dumps({'passed': True, 'project': project, 'zoning': applied.get_json()['zoning'],
                      'statuses': state['statuses']}), flush=True)
finally:
    reset_project(token)
    from backend.engineering.db import close_pool
    close_pool()
