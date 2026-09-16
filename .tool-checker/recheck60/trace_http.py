import json, time, urllib.request, urllib.error
from pathlib import Path
from industry60_adapter import request
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.tool-checker/evidence/industry60-recheck/trace'
BASE='http://127.0.0.1:49546'; PROJECT='nis-e2e-industry60-trace'
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
jobs=json.loads((OUT/'canonical-jobs.json').read_text())['jobs']
for label in ['golden-canonical','fault-canonical']:
    payload={'job_id':jobs[label],'start_s':11,'end_s':16}
    if label=='fault-canonical':payload['golden_job_id']=jobs['golden-canonical']
    code,body=request(BASE,PROJECT,'/api/engineering/reasoning',payload,timeout=120)
    save(label+'-reasoning.json',{'request':payload,'http_status':code,'response':json.loads(body)})
events=[{'time_s':i/1000,'sequence':i,'source':'src','destination':'dst','network':'test-net','technology':'CAN_FD','message_id':'MotorStatus','route_id':'route-test'} for i in range(100501)]
source=OUT/'large-import.jsonl';source.write_text('\n'.join(json.dumps(x) for x in events),encoding='utf8')
start=time.monotonic()
req=urllib.request.Request(BASE+'/api/trace-import?filename=large.jsonl',data=source.read_bytes(),headers={'X-Project-ID':PROJECT,'Content-Type':'application/octet-stream'})
with urllib.request.urlopen(req,timeout=120) as r:first=json.load(r)
save('large-import-http.json',{'elapsed_s':time.monotonic()-start,'response':first})
for label,path,project in [
 ('large-next','/api/trace-import/'+first['session_id']+'?cursor='+str(first['next_cursor']),PROJECT),
 ('large-reload','/api/trace-import/'+first['session_id'],PROJECT),
 ('large-other-project','/api/trace-import/'+first['session_id'],'nis-e2e-industry60-other')]:
 code,body=request(BASE,project,path);save(label+'.json',{'http_status':code,'response':json.loads(body)})
print(json.dumps({'count':first['total_events'],'window':len(first['events']),'session':first['session_id']}),flush=True)
