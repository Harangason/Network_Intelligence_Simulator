import hashlib, json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
files=['frontend/src/features/traces/ui/analysis-workspace-tools.tsx','frontend/src/app/globals.css']
before=[]
revision={}
for name in files:
    data=(root/name).read_bytes()
    target=here/'before'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists(), 'Do not replace original evidence'
    target.write_bytes(data)
    digest=hashlib.sha256(data).hexdigest()
    revision[name]=digest
    before.append({'path':str(target),'sha256':digest})
work={'goal_id':'analysis-toolbar-compact-20261012','goal_type':'implementation','kind':'implementation',
 'repository':str(root),'project_scope':'NIS analysis toolbar presentation',
 'requested_change':'Reduce the analysis workspace toolbar height while preserving directly accessible window actions and cursor/status; collapse explanatory information and profiles by default.',
 'modify_code':True,'allow_repair':True,'revision_before':revision,'before':before,
 'required_outcomes':['compact_default_toolbar','existing_actions_and_context_preserved','verified_production_delivery'],
 'validation_requirements':['typecheck','release','production'],
 'outcomes':{},'validations':{},'files_changed':files,
 'forbidden_changes':['No workspace protocol or calculation changes','No EIP deployment','No unaudited image deletion'],
 'constraints':['Native collapsed details, existing labels/actions and context','No extra design test suite; required full release gate remains mandatory'],
 'unresolved_decisions':[],
 'implementation_plan':['Move cursor to compact header, remove duplicate heading and visible label rows','Move explanation into existing collapsed details','Scope compact spacing to toolbar CSS and preserve responsive wrapping','Typecheck, canonical release-and-deploy, actual production size/actions verification'],
 'delivery':{'decision':'YES','authorization':'Standing user AGENTS.md verified production delivery authorization','target':'Canonical NIS stack'},
 'completion_status':'IMPLEMENTING'}
(here/'workload.json').write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
print('BEFORE_EVIDENCE_RECORDED')
