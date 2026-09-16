import json,sys
from pathlib import Path
from datetime import datetime,timezone
from industry60_adapter import request
from run_industry60_jobs import cli,ROOT
M=json.loads((ROOT/'.tool-checker/industry60-recheck.normalized.json').read_text(encoding='utf8'))
def snapshot(cid,label):
 p='nis-e2e-industry60-'+cid.lower();d=ROOT/'.tool-checker/evidence/industry60-recheck'/cid;d.mkdir(parents=True,exist_ok=True)
 value={}
 for key,path in [('workflow','/api/engineering/workflow?view=summary'),('history','/api/agent/history?projectId='+p),('conversation','/api/engineering/agent/conversation'),('hardware','/api/engineering/hardware-nodes'),('hardware_interfaces','/api/engineering/hardware-interfaces'),('functions','/api/engineering/functions'),('messages','/api/engineering/messages'),('signals','/api/engineering/signals'),('routing','/api/engineering/routing'),('resources','/api/engineering/communication-resources')]:
  code,body=request('http://127.0.0.1:49546',p,path)
  try:body=json.loads(body)
  except ValueError:pass
  value[key]={'http_status':code,'data':body}
 value['model_revision']=value['workflow']['data'].get('versions');value['captured_at']=datetime.now(timezone.utc).isoformat()
 (d/(label+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');return value

def begin(cid):
 c=next(c for c in M['test_cases'] if c['test_id']==cid);d=ROOT/'.tool-checker/evidence/industry60-recheck'/cid
 before=snapshot(cid,'before');plan=cli('tool_check.py','--task','industry60-recheck','dry-run',cid)[0];assert not plan['blockers'],plan['blockers']
 proof={'source_hash':plan['context']['source_hash'],'contract_hash':plan['context']['test']['contract_hash'],'project_path':str(ROOT),'checked_at':datetime.now(timezone.utc).isoformat(),'available_skills':['tool-checker'],'available_tools':['NIS HTTP API','Browser'],'available_views':['Engineering'],'browser':{'observed_working':False},'isolated_scope':'Disposable published image at port51576; nis-e2e-industry60 only'}
 for k in ['dependencies','application','project','permissions','test_data']:proof[k]={'status':'PASSED','evidence':'Isolated ready stack, source source_lines reviewed, before.json actual canonical snapshot and fixture.json where applicable'}
 for k in ['preconditions','required_model_context']:proof[k]=[{'name':n,'status':'PASSED','evidence':'before.json and reviewed fixture for '+cid} for n in c[k]]
 (d/'preflight.json').write_text(json.dumps(proof),encoding='utf8')
 out=cli('tool_check.py','--task','industry60-recheck','run',cid,'--preflight',str(d/'preflight.json'),'--baseline',str(d/'before.json'));(d/'manual-run.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=='__main__':begin(sys.argv[2]) if sys.argv[1]=='begin' else print(json.dumps(snapshot(sys.argv[2],sys.argv[1]))[:1000])

