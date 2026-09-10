"""Run inside NetworkIS: inject a failure after writes on the test clone only."""
from flask import Flask
from unittest.mock import patch
import json
from backend.engineering import api

PROJECT = 'lasso-assignment-acceptance-20260910'
assert PROJECT.startswith('lasso-assignment-acceptance-')
app = Flask(__name__)
app.register_blueprint(api.engineering_api, url_prefix='/api/engineering')
client = app.test_client()
headers = {'X-Project-ID': PROJECT}
def get(path):
    response=client.get('/api/engineering'+path,headers=headers)
    assert response.status_code==200,response.get_json()
    return response.get_json()
def snapshot():
    state=get('/workflow/network-view')
    workflow=get('/workflow')
    data={'view':state,'workflow':{key:workflow[key] for key in ('context','parameters','versions','statuses','stale_reasons')}}
    for resource in ['hardware-nodes','hardware-interfaces','interfaces','messages','signals','routing','relations']:
        data[resource]=[]
        while True:
            page=get(f'/{resource}?limit=500&offset={len(data[resource])}')['items']
            data[resource]+=page
            if len(page)<500:break
    return data
before=snapshot()
t=before['view']['topology']
node=next(n for n in t['nodes'] if n['name']=='FahrersitzStellglied')
target=next(n for n in t['nodes'] if n['name']=='Fahrertuer')
assignment={'node_ids':[node['id']],'target_kind':'frame','target_id':target['id']}
preview=client.post('/api/engineering/workflow/network-assignment/preview',json=assignment,headers=headers)
assert preview.status_code==200,preview.get_json()
original=api.update_route
calls=[]
def fail_after_write(*args,**kwargs):
    result=original(*args,**kwargs)
    calls.append(result['id'])
    raise RuntimeError('Injected assignment rollback test after first route update')
with patch.object(api,'update_route',side_effect=fail_after_write):
    response=client.put('/api/engineering/workflow/network-assignment',headers=headers,
        json={**assignment,'plan_token':preview.get_json()['token'],'expected_token':before['view']['edit_tokens']['topology']})
assert response.status_code>=400
assert len(calls)==1,'failure must occur after a route was actually written'
after=snapshot()
assert before==after,'a partially applied reassignment escaped the transaction'
with patch.object(api.RoutingValidator,'validate',return_value={'valid':False,'errors':[{'code':'TEST_CONFLICT','message':'Injected invalid communication path'}]}):
    invalid=client.put('/api/engineering/workflow/network-assignment',headers=headers,
        json={**assignment,'plan_token':preview.get_json()['token'],'expected_token':before['view']['edit_tokens']['topology']})
assert invalid.status_code==400,invalid.get_json()
assert snapshot()==before,'validation conflict did not roll back all changes'
print(json.dumps({'project':PROJECT,'failureAfterRouteWrite':True,'completeRollback':True,'invalidRouteRollback':True}))
from backend.engineering.db import get_pool
get_pool().close()
