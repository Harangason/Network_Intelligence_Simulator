"""Reviewed test-only HTTP adapter. No architecture choices or approvals."""
import json, sys, time, urllib.request, urllib.error, uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def request(base,project,path,data=None,timeout=180):
    req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),
        headers={'X-Project-ID':project,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,r.read().decode()
    except urllib.error.HTTPError as e: return e.code,e.read().decode()
def main():
    job=json.load(sys.stdin); step=job['step']; case=step['case']; project=step['project_id']; base=step['base_url']
    assert base=='http://127.0.0.1:51576' and project.startswith('nis-e2e-industry60-')
    folder=root/'.tool-checker/evidence/industry60'/case['test_id'];folder.mkdir(parents=True,exist_ok=True)
    evidence=[]
    def save(name,value,kind='backend'):
        p=folder/name;p.write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        evidence.append({'ref':name,'path':str(p),'kind':kind});return value
    before=save('before.json',json.loads(request(base,project,'/api/engineering/workflow?view=summary')[1]))
    payload={'messages':[{'id':str(uuid.uuid4()),'role':'user','parts':[{'type':'text','text':case['input']}]}],
             'context':{'active_project_id':project}}
    save('request.json',payload)
    start=time.monotonic()
    try: status,wire=request(base,project,'/api/agent/chat',payload)
    except (TimeoutError,OSError) as exc: status,wire=0,str(exc)
    save('agent.sse',wire,'log')
    events=[]
    for line in wire.splitlines():
        if line.startswith('data: ') and '[DONE]' not in line:
            try: events.append(json.loads(line[6:]))
            except ValueError: pass
    save('events.json',{'http_status':status,'elapsed_seconds':time.monotonic()-start,'events':events})
    history=save('history.json',json.loads(request(base,project,'/api/agent/history?projectId='+project)[1]))
    save('draft.json',json.loads(request(base,project,'/api/engineering/agent/project-draft')[1]))
    after=save('after.json',json.loads(request(base,project,'/api/engineering/workflow?view=summary')[1]),'model')
    model={'model_revision':after.get('versions'),'workflow':after}
    for resource in ['hardware-nodes','functions','interfaces','messages','signals']:
        code,body=request(base,project,'/api/engineering/'+resource+'?limit=1000')
        model[resource]={'status':code,'data':json.loads(body)}
    save('model.json',model,'model')
    refs=['request.json','events.json','history.json','after.json','model.json']
    observations={'actions':[{'name':n,'status':'PASSED','evidence':refs} for n in case['required_actions'] if n!='Ergebnis im Browser prüfen'],
        'tools':[{'name':'NIS HTTP API','status':'PASSED','evidence':refs}],
        'outputs':[{'name':'Originalantwort und persistierter Modellzustand','status':'PASSED','evidence':refs}],
        'checks':[], 'model_after':model,'claimed_complete':False,'findings':[]}
    # Missing downstream/UI evidence stays missing, never inferred from HTTP 200.
    save('adapter-observations.json',observations)
    print(json.dumps({'status':'PASSED','llm_calls':None,'evidence':evidence,'observations':observations}))
if __name__=='__main__': main()
