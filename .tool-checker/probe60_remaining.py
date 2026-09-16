import json,uuid
from pathlib import Path
from industry60_adapter import request
from industry60_fixtures import seed
from industry60_manual import snapshot
m=json.loads(Path('.tool-checker/industry60.normalized.json').read_text())
seed('nis-e2e-industry60-s22')
for cid in ['S22','S29']:
 p='nis-e2e-industry60-'+cid.lower();d=Path('.tool-checker/evidence/industry60')/cid;d.mkdir(exist_ok=True)
 snapshot(cid,'before')
 c=next(x for x in m['test_cases'] if x['test_id']==cid)
 payload={'messages':[{'id':str(uuid.uuid4()),'role':'user','parts':[{'type':'text','text':c['input']}]}],'context':{'active_project_id':p}}
 (d/'request.json').write_text(json.dumps(payload))
 try:code,body=request('http://127.0.0.1:51576',p,'/api/agent/chat',payload)
 except (TimeoutError,OSError) as e:code,body=0,str(e)
 (d/'agent.sse').write_text(body,encoding='utf8');snapshot(cid,'after');print(cid,code,flush=True)
for cid in ['S21','S26','S27','S30']:snapshot(cid,'after')
