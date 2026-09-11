"""Run repair integration checks exclusively in the existing isolated test database."""
import os, sys, json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
from backend.engineering.project_bundle import SOURCE_TABLES, BUNDLE_VERSION, _json_safe, ProjectBundleService
from backend.engineering.db import close_pool
from backend.app import create_app

source_project = 'network-project-20260910042736034-d11591d0'
source_url = os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://')
with psycopg.connect(source_url, row_factory=dict_row, options='-c default_transaction_read_only=on') as connection:
    state = connection.execute('SELECT * FROM engineering_workflow_projects WHERE project_id=%s', (source_project,)).fetchone()
    tables = [t for t in SOURCE_TABLES if t not in {'engineering_ai_proposals','engineering_routing_proposals','engineering_routing_audit','engineering_address_audit'}]
    source_data = {t: [_json_safe(r) for r in connection.execute(sql.SQL('SELECT * FROM {} WHERE project_id=%s').format(sql.Identifier(t)),(source_project,)).fetchall()] for t in tables}
bundle = {'format':'network-intelligence-project', 'bundle_version':BUNDLE_VERSION,'project_id':source_project,'source_project_id':source_project,'workflow':_json_safe(state),'source_data':source_data,'project_data':{}}
url = urlsplit(source_url); test_url = urlunsplit(url._replace(path='/nis_bus_naming_tests'))
assert urlsplit(test_url).path == '/nis_bus_naming_tests' and test_url != source_url
os.environ['ENGINEERING_TEST_DATABASE_URL'] = os.environ['DATABASE_URL'] = test_url
close_pool()
import pytest
result = pytest.main(['backend/tests/test_communication_repair.py','-q','-p','no:cacheprovider'])
if result: raise SystemExit(result)

from backend.engineering.project_context import activate_project
from backend.engineering.repository import list_objects
from backend.engineering.pagination import all_pages
from backend.engineering.routing.repository import list_routes
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.communication_repair import load_plan, complete_plan
from backend.engineering.routing.validation import RoutingValidator
from backend.engineering.repository import update_object
from unittest.mock import patch
import uuid
reports=[]
for action in ('adopt','restore'):
    project='pytest-repair-routing-'+action+'-'+uuid.uuid4().hex[:12]
    activate_project(project)
    ProjectBundleService().import_bundle(bundle,target_project_id=project)
    client=create_app(testing=True).test_client();client.environ_base['HTTP_X_PROJECT_ID']=project
    base='/api/engineering/workflow/communication-repair/'
    response=client.post(base+'preview',json={}); assert response.status_code==200,response.get_json()
    plan=response.get_json()
    option_group=next(((g,o) for g in plan['groups'] for o in g['options'] if o['action']==action),None)
    assert option_group, (action,plan)
    group,option=option_group
    print('Checking',action,'routes',len(option['comparison']), flush=True)
    before_objects={k:all_pages(list_objects,k) for k in ('Function','Interface','Message','Signal','HardwareNode','HardwareNetworkInterface')}
    before_routes={str(r['id']):r for r in all_pages(list_routes)}
    before_workflow=WorkflowStatusService(project).network_view()
    # Fail after all staged changes, including created channels and forwarding rules.
    with patch.object(RoutingValidator, 'validate', return_value={'valid':False,'errors':[{'message':'Injected rollback check'}]}):
        rejected=client.post(base+'apply',json={'token':plan['token'],'choices':{group['id']:option['id']}})
        assert rejected.status_code==400,rejected.get_json()
    for kind, rows in before_objects.items(): assert all_pages(list_objects,kind)==rows,(action,'rollback',kind)
    assert {str(r['id']):r for r in all_pages(list_routes)}==before_routes,(action,'rollback routes')
    assert WorkflowStatusService(project).network_view()==before_workflow,(action,'rollback topology')
    response=client.post(base+'apply',json={'token':plan['token'],'choices':{group['id']:option['id']}})
    assert response.status_code==200,(action,response.get_json())
    applied=response.get_json();print('Applied',action,applied['applied'], flush=True)
    for k in ('Function','Interface','Signal'):
        assert all_pages(list_objects,k)==before_objects[k],(action,k)
    changed_routes=[]
    for route in all_pages(list_routes):
        old=before_routes[str(route['id'])]
        for field in ('payload','timing','routing_policy'):assert route[field]==old[field],(action,route['route_code'],field)
        if route['revision']!=old['revision']:
            assert route['validation']['valid'] and route['approval_state']=='PENDING',route
            changed_routes.append(route['route_code'])
    after_messages={str(m['id']):m for m in all_pages(list_objects,'Message')}
    for old in before_objects['Message']:
        new=after_messages[str(old['id'])]
        for field in ('interface_id','message_id_hex','dlc','cycle_ms'):assert old[field]==new[field]
    after_hardware={str(n['id']):n for n in all_pages(list_objects,'HardwareNode')}
    assert all(after_hardware[str(old['id'])]['device_type']==old['device_type'] for old in before_objects['HardwareNode'])
    assert changed_routes
    assert client.post(base+'apply',json={'token':plan['token'],'choices':{group['id']:option['id']}}).status_code==409
    again=client.post(base+'preview',json={}).get_json()
    # Previously repaired route identities must not be resurrected from history.
    still={r['code'] for g in again['groups'] for r in g['routes']}
    assert not set(changed_routes)&still,(action,still)
    if action=='adopt':
        # Exact direction/port-pair confirmation is required again after revocation.
        forwarding=next(n for n in after_hardware.values() if (n.get('identity') or {}).get('communication_forwarding'))
        identity={**forwarding['identity'],'communication_forwarding':[]}
        update_object('HardwareNode',str(forwarding['id']),{'identity':identity,'expected_version':forwarding['version']})
        validator=RoutingValidator(project)
        forwarded=next(r for r in all_pages(list_routes) if r['route_code'] in changed_routes and any(str(g.get('node_id'))==str(forwarding['id']) for g in r['route'].get('gateways',[])))
        invalid=validator.validate(forwarded,exclude_route_id=str(forwarded['id']))
        assert not invalid['valid'] and any(e['code']=='PHYSICAL_PATH_REMOVED' for e in invalid['errors']), invalid
        revoked=client.post(base+'preview',json={}).get_json()
        assert revoked['groups'],revoked
    reports.append({'action':action,'project':project,'routeCount':len(changed_routes),'remainingGroups':len(again['groups']),'preservedCommunication':True,'pendingApproval':True,'atomicRollback':True})
print(json.dumps(reports,indent=2));close_pool()
