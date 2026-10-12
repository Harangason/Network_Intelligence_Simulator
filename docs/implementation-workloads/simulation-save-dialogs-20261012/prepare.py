from pathlib import Path
import json,hashlib,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];old=HERE.parent/'simulation-control-folds-20261012'
files=['frontend/src/features/simulation/ui/model-simulation-runner.tsx','frontend/src/features/projects/ui/project-actions.tsx','frontend/src/features/projects/ui/save-dialog.tsx','frontend/src/app/globals.css']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=[];revision={}
for n in files:
 p=ROOT/n;revision[n]=sha(p) if p.exists() else None
 if p.exists():
  b=HERE/'before'/n;b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,b);before.append({'path':str(b),'sha256':sha(b)})
w={'goal_id':HERE.name,'goal_type':'implementation','kind':'implementation','repository':str(ROOT),'requested_change':'Show app save dialogs immediately for scenario Save as and project Save, with cancel and visible save failures','modify_code':True,'allow_repair':True,'revision_before':revision,'before':before,'files_changed':files,'required_outcomes':['scenario_save_dialog','project_save_dialog','production_delivery'],'validation_requirements':['typecheck','focused_browser','production'],'constraints':['Small checks/direct frontend delivery, no image/full gate','Reuse existing scenario and project persistence APIs'],'forbidden_changes':['No backend/model/preflight changes','No product database test writes'],'unresolved_decisions':[],'delivery':{'decision':'YES','authorization':'Standing user instruction: small checks, no image/full test, direct production','target':'Existing NetworkIS frontend'},'completion_status':'IMPLEMENTING'}
(HERE/'workload.json').write_text(json.dumps(w,indent=2))
for f in ['stage_frontend.py','build_frontend.py','deploy_frontend.py','final_proof.py']:shutil.copyfile(old/f,HERE/f)
p=HERE/'stage_frontend.py';s=p.read_text();a=s.index('FILES = ');b=s.index('\n',a);s=s[:a]+'FILES = '+repr([n.removeprefix('frontend/') for n in files])+s[b:];p.write_text(s)
