"""Function-led repair checks: read live, mutate only a copy in the test database."""
import os,sys,json,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
from backend.engineering.project_bundle import SOURCE_TABLES,BUNDLE_VERSION,_json_safe,ProjectBundleService
from backend.engineering.db import close_pool

source_project='network-project-20260910042736034-d11591d0'
source_url=os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')
with psycopg.connect(source_url,row_factory=dict_row,options='-c default_transaction_read_only=on') as connection:
    state=connection.execute('SELECT * FROM engineering_workflow_projects WHERE project_id=%s',(source_project,)).fetchone()
    tables=[t for t in SOURCE_TABLES if t not in {'engineering_ai_proposals','engineering_routing_proposals','engineering_routing_audit','engineering_address_audit'}]
    data={t:[_json_safe(r) for r in connection.execute(sql.SQL('SELECT * FROM {} WHERE project_id=%s').format(sql.Identifier(t)),(source_project,)).fetchall()] for t in tables}
bundle={'format':'network-intelligence-project','bundle_version':BUNDLE_VERSION,'project_id':source_project,'source_project_id':source_project,'workflow':_json_safe(state),'source_data':data,'project_data':{}}
url=urlsplit(source_url);test_url=urlunsplit(url._replace(path='/nis_bus_naming_tests'))
assert test_url!=source_url and urlsplit(test_url).path=='/nis_bus_naming_tests'
os.environ['ENGINEERING_TEST_DATABASE_URL']=os.environ['DATABASE_URL']=test_url
close_pool()
import pytest
result=pytest.main(['backend/tests/test_communication_repair.py','backend/tests/test_communication_intent.py','backend/tests/test_routing.py','backend/tests/test_routing_context_consistency.py','-q','-p','no:cacheprovider'])
if result:raise SystemExit(result)

from backend.app import create_app
from backend.engineering.project_context import activate_project
from backend.engineering.repository import list_objects
from backend.engineering.pagination import all_pages
from backend.engineering.routing.repository import list_routes
from backend.engineering.communication_intent import FunctionalArchitecture
project='pytest-function-architecture-'+uuid.uuid4().hex[:12]
activate_project(project)
ProjectBundleService().import_bundle(bundle,target_project_id=project)
client=create_app(testing=True).test_client();client.environ_base['HTTP_X_PROJECT_ID']=project
base='/api/engineering/workflow/communication-repair/'
before={k:all_pages(list_objects,k) for k in ('Function','Signal','Message','Interface','HardwareNode')}
routes={str(r['id']):r for r in all_pages(list_routes)}
fixed=[]
for step in range(100):
    result=client.post(base+'preview',json={});assert result.status_code==200,result.get_json()
    plan=result.get_json()
    if step==0:print('ARCHITECTURE',json.dumps({k:v for k,v in plan['architecture'].items() if k not in {'flows','unresolved'}}),'groups',len(plan['groups']),flush=True)
    choice=next(((g,o) for g in plan['groups'] for o in g['options'] if o['action']=='adopt'),None)
    if not choice:break
    g,o=choice
    print('APPLY',step,'routes',len(o['comparison']),flush=True)
    applied=client.post(base+'apply',json={'token':plan['token'],'choices':{g['id']:o['id']}})
    assert applied.status_code==200,applied.get_json()
    fixed+=o['comparison']
else:raise AssertionError('Repair did not converge')
for k in ('Function','Signal'):assert all_pages(list_objects,k)==before[k],k
after={str(r['id']):r for r in all_pages(list_routes)}
for rid,r in after.items():
    for field in ('payload','timing','routing_policy'):assert r[field]==routes[rid][field],(r['route_code'],field)
    if r['revision']!=routes[rid]['revision']:
        assert r['validation']['valid'] and r['approval_state']=='PENDING'
        assert r['route']['functional_intent']['source']['function_id'] or r['route']['functional_intent']['source'].get('partner_type')=='hardware_io'
        assert all(e['function_id'] or e.get('partner_type')=='hardware_io' for e in r['route']['functional_intent']['destinations'])
print('RESULT',json.dumps({'project':project,'updatedRoutes':len({r['id'] for r in fixed}),'remainingGroups':len(plan['groups']),
    'unresolvedFunctions':len(plan['architecture']['unresolved']),'functionPartnersPreserved':True,'signalsAndTimingPreserved':True,
    'remainingReasons':[g['reason'] for g in plan['groups']][:8]}),flush=True)
close_pool()
