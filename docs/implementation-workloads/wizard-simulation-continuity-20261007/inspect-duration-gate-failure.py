import json,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlparse
out=Path(__file__).parent.resolve();root=out.parents[2]
trace=root/'backend/test-output/release-gates/duration-intent-d7d049e2b8d6/860f9d4a7375/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
before={};after={};network=[]
with zipfile.ZipFile(trace) as archive:
    for name in archive.namelist():
        if not name.endswith(('.trace','.network')):continue
        with archive.open(name) as stream:
            for raw in stream:
                item=json.loads(raw)
                if item.get('type')=='before':before[item['callId']]=item
                elif item.get('type')=='after':after[item['callId']]=item
                elif item.get('type')=='resource-snapshot':
                    snapshot=item['snapshot'];request=snapshot.get('request',{})
                    network.append({'method':request.get('method'),'path':urlparse(request.get('url','')).path,
                        'duration_ms':snapshot.get('time'),'status':snapshot.get('response',{}).get('status')})
calls=[]
for key,item in before.items():
    result=after.get(key,{})
    if item.get('class')=='APIRequestContext' or item.get('apiName','').startswith('apiRequestContext.'):
        calls.append({'method':item.get('apiName') or item.get('method'),'path':urlparse(item.get('params',{}).get('url','')).path,
            'start_ms':item.get('startTime'),'end_ms':result.get('endTime'),'error':result.get('error'),
            'stack':item.get('stack')})
proof={'last_api_calls':calls[-15:],'slow_network':sorted(network,key=lambda item:item['duration_ms'] or 0,reverse=True)[:25],
 'trace_structure':[{key:item.get(key) for key in ('type','class','method','apiName','startTime')} for item in list(before.values())[:6]]}
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe';db='nis-e2e-db-860f9d4a7375'
assert subprocess.check_output([docker,'inspect',db,'--format','{{index .Config.Labels "networkis.test"}}'],text=True).strip()=='disposable'
query="""SELECT json_build_object('workflow', (SELECT json_build_object('statuses',statuses,'execution',context->'agent_execution')
 FROM engineering_workflow_projects WHERE project_id='nis-e2e-large-efbde825-d726-46c0-af82-d85123f578e8'),
 'snapshot', (SELECT json_build_object('id',id,'assessment',(result->'assessment')-'scope_coverage',
 'duration',configuration->'duration_s','origin',configuration->'parameters'->'parameter_provenance'->'duration_s',
 'observation',(configuration->'observation_window')-'routes') FROM engineering_simulation_snapshots
 WHERE project_id='nis-e2e-large-efbde825-d726-46c0-af82-d85123f578e8' ORDER BY created_at DESC LIMIT 1))"""
proof['frozen_result']=json.loads(subprocess.check_output([docker,'exec',db,'psql','-U','nis_test','-d','nis_test_e2e','-At','-c',query],text=True))
(out/'duration-full-failure-inspection.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
execution=(proof['frozen_result'].get('workflow') or {}).get('execution') or {}
print(json.dumps({'last_calls':calls[-5:],'snapshot':proof['frozen_result']['snapshot'],
 'execution':{key:execution.get(key) for key in ('step','state','run_id')},'slow_network':proof['slow_network'][:5]},ensure_ascii=False))
