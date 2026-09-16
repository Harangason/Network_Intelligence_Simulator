"""Fresh public-API probes. Pending architecture choices remain unanswered."""
import json, subprocess, sys, time, uuid
from pathlib import Path
from industry60_adapter import request
from industry60_fixtures import seed, ROOT
from industry60_manual import snapshot

BASE='http://127.0.0.1:49546'
OUT=ROOT/'.tool-checker/evidence/industry60-recheck'
CASES=json.loads((ROOT/'.tool-checker/industry60-recheck.normalized.json').read_text(encoding='utf8'))['test_cases']
def runfile(name):
    subprocess.run([sys.executable,str(Path(__file__).parent/name)],cwd=ROOT,check=True)
def chat(cid,context=None):
    case=next(c for c in CASES if c['test_id']==cid)
    project='nis-e2e-industry60-trace' if cid=='S28' else 'nis-e2e-industry60-'+cid.lower()
    directory=OUT/cid;directory.mkdir(parents=True,exist_ok=True)
    snapshot(cid,'before')
    payload={'messages':[{'id':str(uuid.uuid4()),'role':'user','parts':[{'type':'text','text':case['input']}]}],
             'context':{'active_project_id':project,**(context or {})}}
    (directory/'request.json').write_text(json.dumps(payload),encoding='utf8')
    start=time.monotonic()
    try: code,body=request(BASE,project,'/api/agent/chat',payload,timeout=240)
    except (TimeoutError,OSError) as exc:code,body=0,str(exc)
    (directory/'agent.sse').write_text(body,encoding='utf8')
    (directory/'transport.json').write_text(json.dumps({'status':code,'elapsed_s':time.monotonic()-start}),encoding='utf8')
    snapshot(cid,'after')
    print(cid,code,flush=True)

if __name__=='__main__':
    # Await only this batch; never replay an already recorded mutation.
    last=OUT/'S20-B/job.json'
    while True:
        if last.exists():
            job=json.loads(last.read_text())
            state=json.loads((ROOT/'.tool-checker/state/jobs'/job['job_id']/'job.json').read_text())
            if state['status'] in ['COMPLETE','FAILED','BLOCKED','CANCELLED']:break
        time.sleep(2)
    for cid in ['S21','S22','S23','S24','S26','S27','S29','S30']:
        directory=OUT/cid;directory.mkdir(parents=True,exist_ok=True)
        if (directory/'after.json').exists():continue
        if cid in ['S22','S23','S24','S30']:seed('nis-e2e-industry60-'+cid.lower())
        if cid in ['S26','S27','S29']:runfile('seed60_'+cid.lower()+'.py')
        context={'requested_mode':'CREATE_ARCHITECTURE'} if cid in ['S21','S30'] else {}
        if cid=='S27':
            fixture=json.loads((directory/'fixture.json').read_text())
            context={'requested_mode':'VALIDATE_SIGNAL','selected_object_refs':[{'object_type':'Signal','id':fixture['signal']['id']}]}
        if cid=='S29':context={'requested_mode':'ASSESS_FINDING'}
        chat(cid,context)
    runfile('seed60_trace.py')
    runfile('run_industry60_canonical_jobs.py')
    jobs=json.loads((OUT/'trace/canonical-jobs.json').read_text())
    chat('S28',{'requested_mode':'ANALYZE_TRACE','selected_object_refs':[{'object_type':'SimulationRun','id':jobs['jobs']['fault-canonical']}]})
