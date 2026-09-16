import json, urllib.request
from pathlib import Path
base=Path(__file__).resolve().parent/'evidence/industry40-live-ai'
def read_api(info,route):
    if info['base']!='http://127.0.0.1:57797': raise ValueError('Wrong isolated target')
    with urllib.request.urlopen(urllib.request.Request(info['base']+route,headers={'X-Project-ID':info['project']}),timeout=30) as response:return json.load(response)
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
for directory in sorted(base.iterdir()):
    if not (directory/'finished.json').exists():continue
    info=json.loads((directory/'run-id.json').read_text(encoding='utf-8'))
    data=read_api(info,'/api/engineering/agent/conversation');save(directory/'conversation.json',data)
    state=data.get('data',{});workload=state.get('active_workload')
    if workload:
        route='/api/engineering/agent/execution-goals/'+workload+'/response' if workload.startswith('goal-') else '/api/engineering/workloads/'+workload+'/progress'
        save(directory/'workload.json',read_api(info,route))
    print(directory.name, 'workload='+str(workload), 'question='+str(state.get('current_question')))
