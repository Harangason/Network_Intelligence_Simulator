import json,zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse,parse_qs
out=Path(__file__).parent.resolve();root=out.parents[2]
path=root/'backend/test-output/release-gates/duration-intent-d7d049e2b8d6/860f9d4a7375/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
before={};after={};stacks={};network=[]
def safe_path(url):
    parsed=urlparse(url);view=parse_qs(parsed.query).get('view',[])
    return parsed.path+('?view='+view[0] if view and view[0] in ('summary','status') else '')
with zipfile.ZipFile(path) as archive:
    for name in archive.namelist():
        if name.endswith('.stacks'):
            item=json.loads(archive.read(name))
            files=item.get('files',[])
            for key,frames in item.get('stacks',[]):
                stacks[key]=[{'file':files[f[0]],'line':f[1],'column':f[2]} for f in frames]
        if not name.endswith(('.trace','.network')):continue
        with archive.open(name) as stream:
            for raw in stream:
                item=json.loads(raw)
                if item.get('type')=='before':before[item['callId']]=item
                elif item.get('type')=='after':after[item['callId']]=item
                elif item.get('type')=='resource-snapshot':
                    record=item['snapshot'];request=record.get('request',{})
                    network.append({'method':request.get('method'),'path':safe_path(request.get('url','')),
                        'start_ms':record.get('_monotonicTime'),'duration_ms':record.get('time'),
                        'status':record.get('response',{}).get('status')})
calls=[]
for key,item in before.items():
    result=after.get(key,{})
    if item.get('class')=='APIRequestContext':
        start=item.get('startTime');end=result.get('endTime')
        calls.append({'id':key,'method':item.get('params',{}).get('method'),'path':safe_path(item.get('params',{}).get('url','')),
            'start_ms':start,'end_ms':end,'duration_ms':end-start if end is not None else None,
            'error':result.get('error'),'stack':stacks.get(key)})
calls.sort(key=lambda row:row['start_ms'] or 0)
groups=defaultdict(list)
for record in network:groups[(record['method'],record['path'])].append(record)
grouped=[{'method':method,'path':endpoint,'count':len(items),
 'total_ms':round(sum(item['duration_ms'] or 0 for item in items)),
 'max_ms':max(item['duration_ms'] or 0 for item in items)} for (method,endpoint),items in groups.items()]
proof={'last_api_calls':calls[-15:],
 'slow_api_calls':sorted(calls,key=lambda row:row['duration_ms'] or 0,reverse=True)[:25],
 'network_groups':sorted(grouped,key=lambda row:row['total_ms'],reverse=True),
 'slow_network':sorted(network,key=lambda row:row['duration_ms'] or 0,reverse=True)[:25]}
(out/'duration-full-trace-analysis.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps({'last_api_calls':calls[-8:],'slow_api_calls':proof['slow_api_calls'][:5],
 'network_groups':proof['network_groups'][:8]},ensure_ascii=False))
