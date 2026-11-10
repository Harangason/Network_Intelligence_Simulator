"""Freeze the checked accumulation repair, retaining failed native prompt evidence."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path.cwd(); OUT=Path(__file__).resolve().parent; GOAL=OUT.parent
def read(p): return json.loads(p.read_text(encoding='utf8'))
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ref(p): return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
assert not (OUT/'source-scope-proof.json').exists()
work=read(OUT/'workload.json')
runs=[]
for name,session in [('green.xml',48766),('regression.xml',32957),('native-runtime.xml',62523)]:
    suites=list(ET.parse(OUT/name).getroot().iter('testsuite'))
    totals={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    assert totals['tests'] and totals['failures']==totals['errors']==totals['skipped']==0
    runs.append({'session':session,**totals,'evidence':ref(OUT/name)})
raw=read(OUT/'native-v3/response.json')
findings=json.loads(raw['message']['content'])['unresolved']
test_tree=ast.parse((ROOT/'backend/tests/test_reference_finding_accumulation.py').read_text(encoding='utf8'))
native_branch=next(n for n in ast.walk(test_tree) if isinstance(n,ast.If) and ast.unparse(n.test)=="different_field == 'native'")
test_first=ast.literal_eval(native_branch.body[0].value)
test_second=eval(compile(ast.Expression(native_branch.body[1].value),'<native-test-record>','eval'),{'__builtins__':{}},{'first':test_first})
assert findings==[test_first,test_second]
save(OUT/'native-runtime-replay.json',{'status':'PASS_NATIVE_FINDINGS_PRODUCT_RUNTIME_REPLAY',
    'scope':'Exact native finding records through actual planner under isolated pytest; surrounding source and model responses mocked. Not a full-native workflow.',
    'source_native_response':ref(OUT/'native-v3/response.json'),'replay_test':ref(OUT/'native-runtime.xml'),
    'findings_preserved':findings,'native_prompt_only_deduplication':'FAILED_PRESERVED',
    'aborted_standalone_helper':{'session':83795,'exit':1,'reason':'Moved replay into canonical isolated test harness; no new inference.'},
    'new_generation_requests':0,'original_acceptance':False,'production_delivered':False})
assert read(OUT/'retire-790bd-stack/retirement.json')['no_image_removed'] is True
before=ast.parse((OUT/'before/local_reasoner.py').read_text(encoding='utf8'))
after=ast.parse((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf8'))
def without_method(tree):
    for node in tree.body:
        if isinstance(node,ast.ClassDef) and node.name=='LocalEngineeringReasoner':
            node.body=[m for m in node.body if getattr(m,'name',None)!='plan_reference_design']
    return ast.dump(tree)
assert without_method(before)==without_method(after)
save(OUT/'regression-aggregate.json',{'runs':runs,'native_sessions':[{'session':1888,'exit':1,'scope':'Native prompt counter; selected one device and expected a finding for an unselected device'},
    {'session':83282,'exit':1,'scope':'Both selected; prompt-only dedup failed, new distinct finding present'},
    {'session':62523,'exit':0,'scope':'Exact native findings replayed through actual planner in isolated pytest, surrounding workflow mocked'}],
    'native_raw':ref(OUT/'native-v3/response.json'),'runtime_replay':ref(OUT/'native-runtime-replay.json'),
    'original_acceptance':False,'full_native_workflow':False,'production_delivered':False})
after_refs=[]; changes=[]
for name in work['repair']['affected_files']:
    p=ROOT/name; old=OUT/'before'/p.name
    dest=OUT/'after'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    after_refs.append(ref(dest))
    changes.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(OUT/'final-change.diff').write_text(''.join(changes),encoding='utf8')
evidence=[ref(OUT/p) for p in ('finding.json','red.xml','green.xml','regression.xml','regression-aggregate.json','native-v3/response.json','native-v3/result.json','native-runtime-replay.json')]
work.update(status='LOCALLY_VERIFIED_FULL_ORIGINAL_PENDING',files_changed=work['repair']['affected_files'],after=after_refs,diff=[ref(OUT/'final-change.diff')],
    outcomes={k:{'status':'PASSED','evidence':evidence} for k in work['required_outcomes']},
    validations={k:{'status':'PASSED','evidence':evidence} for k in work['validation_requirements']})
work['remaining_findings']=['Native model still repeats existing findings despite instruction; deterministic product accumulation protects state. Original/simulation/full release and exact delivery remain pending.']
save(OUT/'workload.json',work)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
manifest=module('finding_build',ROOT/'scripts/write-build-info.py').build_manifest()
verification=module('finding_release',ROOT/'scripts/run-release-gate.py').verification_manifest()
files={name:ref(ROOT/name)['sha256'] for name in work['repair']['affected_files']}
proof={'at':datetime.now(timezone.utc).isoformat(),'source':manifest,'verification':verification,'files':files,
       'only_plan_reference_design_changed':True,'raw_native_failures_preserved':True,'evidence':evidence,
       'production_delivered':False,'original_acceptance':False}
save(OUT/'source-scope-proof.json',proof)
root=read(GOAL/'workload.json')
for name,value in root['frozen_files'].items():
    if name not in files: assert ref(ROOT/name)['sha256']==value,name
assert len(root['required_outcomes'])==len(root['validation_requirements'])==7
assert ref(Path(root['source']['path']))['sha256']==root['source']['sha256']
root['frozen_files'].update(files);root['frozen_source']=manifest;root['frozen_verification_sha256']=verification
root['current_repair']=ref(OUT/'workload.json');root['status']='PREPARING_FRESH_ORIGINAL';root['final_local_repair_evidence']=ref(OUT/'source-scope-proof.json')
for name in files:
    if name not in root['files_changed']:root['files_changed'].append(name)
save(GOAL/'workload.json',root)
print(json.dumps({'source':manifest,'verification':verification,'runs':runs}))
