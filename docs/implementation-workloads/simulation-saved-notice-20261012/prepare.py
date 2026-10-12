from pathlib import Path
import json,hashlib,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];old=HERE.parent/'simulation-window-separation-20261012'
n='frontend/src/features/simulation/ui/model-simulation-runner.tsx';p=ROOT/n;b=HERE/'before'/n;b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,b)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
w={'goal_id':HERE.name,'goal_type':'implementation','kind':'implementation','repository':str(ROOT),'requested_change':'Remove the marked saved simulation run notice from primary simulation controls','modify_code':True,'allow_repair':True,'revision_before':{n:sha(p)},'before':[{'path':str(b),'sha256':sha(b)}],'files_changed':[n],'required_outcomes':['notice_removed','production_delivery'],'validation_requirements':['typecheck','focused_browser','production'],'constraints':['Small checks and direct frontend delivery, no image/full gate'],'forbidden_changes':['No backend/model/staleness changes'],'unresolved_decisions':[],'delivery':{'decision':'YES','authorization':'Standing user instruction: small checks, no image/full test, direct production','target':'Existing NetworkIS frontend'},'completion_status':'IMPLEMENTING'}
(HERE/'workload.json').write_text(json.dumps(w,indent=2))
for f in ['stage_frontend.py','build_frontend.py','deploy_frontend.py','final_proof.py']:shutil.copyfile(old/f,HERE/f)
s=HERE/'stage_frontend.py';text=s.read_text();text=text.replace("FILES = ['src/features/traces/ui/analysis-workspace-tools.tsx', 'src/features/traces/lib/analysis-workspace.ts', 'src/features/traces/lib/analysis-workspace-browser.ts', 'src/app/globals.css']","FILES = ['src/features/simulation/ui/model-simulation-runner.tsx']");s.write_text(text)
