"""HTTP regression: split a multicast command when moving one recipient."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE='http://127.0.0.1:15050/api/engineering'
SOURCE='network-project-20260910042736034-d11591d0'
PROJECT='lasso-assignment-multicast-20260910'
assert PROJECT.startswith('lasso-assignment-')

def call(path, data=None, method=None, project=PROJECT):
    req=Request(BASE+path, data=json.dumps(data).encode() if data is not None else None,
                headers={'Content-Type':'application/json','X-Project-ID':project}, method=method)
    try:
        with urlopen(req,timeout=180) as response:
            return json.load(response) if response.status!=204 else None
    except HTTPError as error:
        raise RuntimeError(error.read().decode()) from error

source=call('/workflow/network-view',project=SOURCE)
if not call('/workflow/network-view')['topology']['nodes']:
    bundle=call('/projects/export',project=SOURCE)
    bundle['project_data']={}
    call('/projects/import',{'bundle':bundle,'target_project_id':PROJECT})
topology=call('/workflow/network-view')['topology']
nodes={n['name']:n for n in topology['nodes']}
producer=nodes['Kraftstoffsystem']['engineeringId']
actuator=nodes['KraftstoffsystemSchaltausgang']
remaining=nodes['KraftstoffsystemStellglied']
target=nodes['Motorsteuerung']
routes=call('/routing?limit=500')['items']
command=next(r for r in routes if r['source']['node_id']==producer and any(d['node_id']==actuator['engineeringId'] for d in r['destinations']))
other=next(r for r in routes if r['id']!=command['id'] and r['source']['node_id']==producer and any(d['node_id']==remaining['engineeringId'] for d in r['destinations']))
assert command['payload']['message_id']==other['payload']['message_id']
if not any(d['node_id']==remaining['engineeringId'] for d in command['destinations']):
    call('/routing/'+command['id'],{'destinations':command['destinations']+other['destinations'],'expected_revision':command['revision']},'PATCH')
call('/routing/'+other['id'],{'source':other['source'],'expected_revision':other['revision']},'PATCH')
call('/routing/'+other['id'],method='DELETE')
state=call('/workflow/network-view')
assignment={'node_ids':[actuator['id']],'target_kind':'frame','target_id':target['id']}
preview=call('/workflow/network-assignment/preview',assignment)
assert preview['new_routes']==1,preview
result=call('/workflow/network-assignment',{**assignment,'plan_token':preview['token'],'expected_token':state['edit_tokens']['topology']},'PUT')
assert all(v['valid'] for v in result['assignment']['validations']),result['assignment']
preserved=call('/routing/'+command['id'])
assert [d['node_id'] for d in preserved['destinations']]==[remaining['engineeringId']]
updated=call('/routing?limit=500')['items']
created=next(r for r in updated if r['source']['node_id']==target['engineeringId'] and any(d['node_id']==actuator['engineeringId'] for d in r['destinations']))
assert created['payload']['message_id']!=preserved['payload']['message_id']
assert all(not str(key).startswith('$assignment-') for edge in result['topology']['edges'] for key in (edge.get('routingMetadata') or {}))
for validation in result['assignment']['validations']:
    call('/routing/'+validation['id']+'/approve',{'actor':'assignment-acceptance'})
assert call('/workflow/network-view',project=SOURCE)==source
report={'multicastSplit':True,'remainingRecipientPreserved':True,'routesReapproved':len(result['assignment']['validations']),'sourceUnchanged':True}
Path('docs/network-assignment-multicast-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
