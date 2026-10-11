"""Exercise assignment through HTTP on an isolated clone, never on the source."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'http://127.0.0.1:15050/api/engineering'
SOURCE = 'network-project-20260910042736034-d11591d0'
TARGET = 'lasso-assignment-acceptance-20260910'

def call(path, payload=None, method=None, project=TARGET):
    req=Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,
                headers={'Content-Type':'application/json','X-Project-ID':project},method=method)
    try:
        with urlopen(req,timeout=180) as r:return json.load(r)
    except HTTPError as error:
        raise RuntimeError(f'{error.code}: {error.read().decode()}') from error

def rows(resource):
    result=[]
    while True:
        page=call(f'/{resource}?limit=500&offset={len(result)}')['items']
        result+=page
        if len(page)<500:return result

def assign(node_names, kind, target_name):
    state=call('/workflow/network-view')
    topology=state['topology']
    ids=[n['id'] for n in topology['nodes'] if n['name'] in node_names]
    targets=topology['scene']['clusters' if kind=='cluster' else 'frames']
    target=next(t for t in targets if t['label']==target_name)
    request={'node_ids':ids,'target_kind':kind,'target_id':target['id']}
    preview=call('/workflow/network-assignment/preview',request)
    print('preview',json.dumps(preview,ensure_ascii=True),flush=True)
    try:
        call('/workflow/network-assignment',{**request,'plan_token':'stale','expected_token':state['edit_tokens']['topology']},'PUT')
        raise AssertionError('stale preview accepted')
    except RuntimeError as error:assert '409:' in str(error),str(error)
    assert call('/workflow/network-view')==state
    result=call('/workflow/network-assignment',{**request,'plan_token':preview['token'],'expected_token':state['edit_tokens']['topology']},'PUT')
    print('validations',json.dumps(result['assignment']['validations'],ensure_ascii=True),flush=True)
    Path('backend/runtime/assignment-last-result.json').write_text(json.dumps(result),encoding='utf-8')
    assert call('/workflow/network-view')['topology']==result['topology']
    return result

if __name__=='__main__':
    source=call('/workflow/network-view',project=SOURCE)
    if not call('/workflow/network-view')['topology']['nodes']:
        bundle=call('/projects/export',project=SOURCE)
        bundle['project_data']={}
        call('/projects/import',{'bundle':bundle,'target_project_id':TARGET})
        print('isolated clone created',flush=True)
    state=call('/workflow/network-view')
    node=next(n for n in state['topology']['nodes'] if n['name']=='Fahrersitz')
    cluster=next(c for c in state['topology']['scene']['clusters'] if node['id'] in c['memberIds'])
    if cluster['label']!='Karosserie / Komfort':
        first=assign(['Fahrersitz','Fahrertuer'],'cluster','Karosserie / Komfort')
        assert all(v['valid'] for v in first['assignment']['validations'])
    original_commands={m['id']:m for m in rows('messages')}
    second=assign(['FahrersitzSchaltausgang'],'frame','Fahrertuer')
    assert all(v['valid'] for v in second['assignment']['validations'])
    hardware=rows('hardware-nodes')
    actuator=next(n for n in hardware if n['name']=='FahrersitzSchaltausgang')
    owner=next(n for n in hardware if n['name']=='Fahrertuer')
    assert actuator['identity']['system_owner_id']==owner['id']
    report={'sourceUnchanged':call('/workflow/network-view',project=SOURCE)==source,'target':TARGET,
            'stalePreviewRejected':True,'frameMoveValidated':True,'actuatorMoveValidated':True,
            'canonicalOwnerUpdated':True,'createdMessages':len(rows('messages'))-len(original_commands)}
    assert report['sourceUnchanged']
    Path('docs/network-assignment-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
