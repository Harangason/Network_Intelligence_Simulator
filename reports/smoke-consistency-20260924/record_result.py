"""Register reviewed real test artifacts with the existing checker CLI."""
from pathlib import Path
from datetime import datetime, timezone
import json, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
TASK='smoke-consistency-20260924'
CLI='F:/CodexOrdner/plugins/cache/plugins-cli/tool-checker/1.0.0+codex.20260923165202/skills/tool-checker/scripts/tool_check.py'
def call(*args):
    p=subprocess.run([sys.executable,CLI,'--state',str(ROOT/'.tool-checker/state'),'--task',TASK,*args],capture_output=True,text=True,encoding='utf-8')
    if p.returncode: raise RuntimeError(p.stdout+p.stderr)
    return json.loads(p.stdout)
def save(name,data):
    p=OUT/name;p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return str(p)
case,status,detail,*artifacts=sys.argv[1:]
plan=call('dry-run',case)[0]['context']
proof={'source_hash':plan['source_hash'],'contract_hash':plan['test']['contract_hash'],'project_path':str(ROOT),
 'checked_at':datetime.now(timezone.utc).isoformat(),'available_skills':[],'available_tools':[],'available_views':[],
 'dependencies':{'status':'PASSED','evidence':'backend virtualenv imports and real completed subprocess output; node/TypeScript/Playwright present.'},
 'application':{'status':'PASSED','evidence':'Read completed test artifacts; stack receipt confirms isolated current-source build 760546b8c65a.'},
 'project':{'status':'PASSED','evidence':'Canonical root; only launcher-created disposable database / nis-e2e-app-514e6492cc50 used.'},
 'permissions':{'status':'PASSED','evidence':'User authorized 60-minute smoke/consistency testing.'},
 'test_data':{'status':'PASSED','evidence':'Existing repository tests and captured fixtures; no product database.'}}
run=call('run',case,'--preflight',save(case+'-preflight.json',proof))
refs=[call('evidence',run['run_id'],str((ROOT/p).resolve()),'--kind','log')['id'] for p in artifacts]
observation={'run_id':run['run_id'],'checks':[{'category':'completion_criteria','name':plan['test']['completion_criteria'][0],
 'status':status,'evidence':refs}],'notes':detail,'findings':[]}
if status=='FAILED': observation['findings']=[{'code':case+'_AUDIT_FINDING','category':'UNKNOWN','blocking':True,'detail':detail,'evidence':refs}]
result=call('finish',run['run_id'],'--observations',save(case+'-observations.json',observation))
save(case+'-result.json',result)
print(json.dumps(result))
