from pathlib import Path
import json,hashlib,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];old=HERE.parent/'simulation-window-separation-20261012'
files=['frontend/src/features/simulation/ui/model-simulation-runner.tsx','frontend/src/features/traces/ui/analysis-workspace-tools.tsx','frontend/src/features/traces/lib/analysis-workspace-browser.ts','frontend/src/features/traces/lib/analysis-workspace.test.mjs','frontend/src/app/globals.css']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=[];revision={}
for n in files:
 p=ROOT/n;b=HERE/'before'/n;b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,b);before.append({'path':str(b),'sha256':sha(b)});revision[n]=sha(p)
w={'goal_id':HERE.name,'goal_type':'implementation','kind':'implementation','repository':str(ROOT),'requested_change':'Open coupled simulation views in normal browser tabs; all four simulation control panels collapsed by default with equal closed dimensions','modify_code':True,'allow_repair':True,'revision_before':revision,'before':before,'files_changed':files,'required_outcomes':['browser_tabs','four_equal_closed_panels','production_delivery'],'validation_requirements':['typecheck','workspace_tests','focused_browser','production'],'constraints':['Small checks/direct frontend delivery, no image/full gate','Preserve source identity and primary context'],'forbidden_changes':['No backend/model/staleness changes'],'unresolved_decisions':[],'delivery':{'decision':'YES','authorization':'Standing user instruction: small checks, no image/full test, direct production','target':'Existing NetworkIS frontend'},'completion_status':'IMPLEMENTING'}
(HERE/'workload.json').write_text(json.dumps(w,indent=2))
for f in ['stage_frontend.py','build_frontend.py','deploy_frontend.py','final_proof.py','checks.py']:shutil.copyfile(old/f,HERE/f)
p=HERE/'stage_frontend.py';s=p.read_text();a=s.index('FILES = ');b=s.index('\n',a);s=s[:a]+'FILES = '+repr([n.removeprefix('frontend/') for n in files if not n.endswith('.test.mjs')])+s[b:];p.write_text(s)
