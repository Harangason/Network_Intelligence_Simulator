import hashlib, json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
files=['frontend/src/app/globals.css']
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
work={'goal_id':'simulation-command-fields-20261012','goal_type':'implementation','kind':'implementation',
 'repository':str(root),'project_scope':'NIS simulation command bar presentation',
 'requested_change':'Give duration, speed and seed equally sized readable fields, aligned captions and consistent spacing; wrap run actions into their own row rather than squeezing numeric fields.',
 'modify_code':True,'allow_repair':True,'revision_before':revision,'before':before,
 'required_outcomes':['consistent_readable_numeric_fields','responsive_layout_and_existing_controls_preserved','verified_production_delivery'],
 'validation_requirements':['typecheck','release','production'],
 'outcomes':{},'validations':{},'files_changed':files,
 'forbidden_changes':['No workspace protocol or calculation changes','No EIP deployment','No unaudited image deletion'],
 'constraints':['Preserve labels, values, limits, steps, simulation actions and previous presentation changes','No extra design test suite; required full release gate remains mandatory'],
 'unresolved_decisions':[],
 'implementation_plan':['Use five readable field columns and a separate run-action row','Preserve existing responsive three-column and mobile single-column layouts','Typecheck, canonical release-and-deploy, actual production field alignment and mobile verification'],
 'delivery':{'decision':'YES','authorization':'Standing user AGENTS.md verified production delivery authorization','target':'Canonical NIS stack'},
 'completion_status':'IMPLEMENTING'}
(here/'workload.json').write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
print('BEFORE_EVIDENCE_RECORDED')
