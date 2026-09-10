"""Check the persisted result of the browser lasso acceptance test."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

BASE='http://127.0.0.1:15050/api/engineering'
HEADERS={'X-Project-ID':'lasso-assignment-acceptance-20260910','Content-Type':'application/json'}
def call(path, data=None):
    with urlopen(Request(BASE+path,headers=HEADERS,data=json.dumps(data).encode() if data is not None else None),timeout=180) as response:
        return json.load(response)

topology=call('/workflow/network-view')['topology']
node=next(n for n in topology['nodes'] if n['name']=='Drehmomentkoordination')
frame=next(f for f in topology['scene']['frames'] if f['id']==node['id'])
cluster=next(c for c in topology['scene']['clusters'] if c['id']==frame['clusterId'])
assert cluster['label']=='Karosserie / Komfort'
identifiers={n['engineeringId'] for n in topology['nodes'] if n['id'] in frame['memberIds']}
routes=[r for r in call('/routing?limit=500')['items'] if r['source']['node_id'] in identifiers or any(d['node_id'] in identifiers for d in r['destinations'])]
assert all(route['validation']['valid'] for route in routes)
for route in routes:
    call('/routing/'+route['id']+'/approve',{'actor':'assignment-ui-acceptance'})
report={'uiFrameSave':True,'cluster':cluster['label'],'members':len(frame['memberIds']),'routesReapproved':len(routes),'sceneStored':True}
Path('docs/network-assignment-ui-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
