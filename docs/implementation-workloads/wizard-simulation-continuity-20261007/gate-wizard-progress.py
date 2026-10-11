import json
from urllib.request import Request,urlopen

# Observed publication of nis-e2e-app-860f9d4a7375, never the product port.
base='http://127.0.0.1:62540'
with urlopen(base+'/api/engineering/projects',timeout=10) as response:
    projects=json.load(response)['items']
large=[item for item in projects if 'nis-e2e-large-' in item['project_id']]
if large:
    current=large[0]
    progress={key:current[key] for key in ('project_id','active_step','statuses','updated_at')}
    request=Request(base+'/api/engineering/workflow?view=summary',headers={'X-Project-ID':current['project_id']})
    with urlopen(request,timeout=10) as response:
        workflow=json.load(response)
    execution=workflow.get('context',{}).get('agent_execution') or {}
    progress['execution']={key:execution.get(key) for key in ('run_id','step','state')}
    progress['blocking_codes']=sorted({item.get('code','') for item in execution.get('blocking_findings',[])})
    print(json.dumps(progress,ensure_ascii=False))
else:
    print(json.dumps({'large_project_present':False}))
