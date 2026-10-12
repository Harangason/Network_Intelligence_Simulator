import json,subprocess
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[3]
docker=json.loads((ROOT/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
port=subprocess.check_output([docker,'port','nis-e2e-app-44fdae5dc2e1','13500/tcp'],text=True).strip()
assert port.startswith('127.0.0.1:') and port!='127.0.0.1:13500'
base='http://'+port
def read(path,project=None):
    request=Request(base+path,headers={'X-Project-ID':project} if project else {})
    with urlopen(request,timeout=10) as response:return json.load(response)
try:
    items=read('/api/engineering/projects')['items']
    projects=[p for p in items if 'nis-e2e-large-' in p['project_id'] or 'nis-e2e-large-return-' in p['project_id'] or 'astra-e2e-' in p['project_id']]
    result=[]
    for project in projects[:1]:
        workflow=read('/api/engineering/workflow?view=summary',project['project_id'])
        execution=workflow.get('context',{}).get('agent_execution',{})
        result.append({'project':project['project_id'],'active_step':workflow.get('active_step'),'statuses':workflow.get('statuses'),'execution_state':execution.get('state'),'execution_step':execution.get('step')})
    print(json.dumps({'scope':'Read-only current disposable gate instance only','progress':result}))
except Exception as error:print(json.dumps({'scope':'Read-only disposable gate instance','transient_read_error':type(error).__name__}))

