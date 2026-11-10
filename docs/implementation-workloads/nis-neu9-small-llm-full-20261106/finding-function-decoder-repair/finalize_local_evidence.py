"""Record completed local checks and freeze canonical candidate inputs; no model/API writes."""
from pathlib import Path
import hashlib, json, difflib, importlib.util, sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

child = Path(__file__).resolve().parent
goal = child.parent
root = goal.parents[2]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p, value): p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def ref(p): return {'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
work = read(child/'workload.json')
reports = []
for name, session, phase in [
    ('red.xml',49625,'initial RED including rejected target bound experiment'),
    ('red-early-cycle.xml',44305,'cycle rejection RED'),
    ('green-final-focused.xml',47616,'final focused'),
    ('regression.xml',68719,'pre-final broad; old schema expectation FAIL retained'),
    ('green-schema-expectation.xml',74671,'corrected expectation only; negative rejection preserved'),
    ('regression-final-runtime.xml',68816,'final runtime regression')]:
    p=child/name
    suites=list(ET.parse(p).getroot().iter('testsuite'))
    totals={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
    totals['passed']=totals['tests']-totals['failures']-totals['errors']-totals['skipped']
    if phase in {'final focused','final runtime regression'} or session==74671:
        assert totals['failures']==totals['errors']==0
    reports.append({'session':session,'phase':phase,**totals,'evidence':ref(p)})
aggregate={'at':datetime.now(timezone.utc).isoformat(),'runs':reports,
    'single_fully_green_broad_run_claimed':False,'original_or_simulation_acceptance':False,
    'native_final':ref(child/'native-final/result.json'),
    'note':'Initial RED has 8 relevant negatives plus 1 rejected target-bound experiment. Public target bound remains; native baseline target projection preserved. Final focused 33, final runtime 182, corrected schema expectation 1 PASS, in separate runs.'}
save(child/'regression-aggregate.json',aggregate)
before=[]; after=[]; diffs=[]; absent=[]
for rel in work['repair']['affected_files']:
    current=root/rel
    old=child/'before'/rel
    new=child/'after'/rel
    new.parent.mkdir(parents=True,exist_ok=True)
    new.write_bytes(current.read_bytes())
    after.append(ref(new))
    if old.exists(): before.append(ref(old))
    else: absent.append({'path':rel,'existed_before':False})
    diffs.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
save(child/'before/absent-files.json',absent)
before.append(ref(child/'before/absent-files.json'))
(child/'final-change.diff').write_text(''.join(diffs),encoding='utf-8')
work.update(status='LOCALLY_VERIFIED_PENDING_FULL_ORIGINAL_AND_DELIVERY',files_changed=work['repair']['affected_files'],before=before,after=after,diff=[ref(child/'final-change.diff')])
for name in work['required_outcomes']:
    work['outcomes'][name]={'status':'PASSED','evidence':[ref(child/'native-final/result.json'),ref(child/'final-scope-review.json'),ref(child/'green-final-focused.xml')]}
for name in work['validation_requirements']:
    work['validations'][name]={'status':'PASSED','evidence':[ref(child/'regression-aggregate.json'),ref(child/'native-final/result.json')]}
work['delivery']={'decision':'YES','authorization':'Standing AGENTS rule and latest direct human request; 75% limit lifted for this task','target':'Canonical production NIS port 13500','status':'PENDING_FULL_ORIGINAL_AND_RELEASE','checks':{}}
save(child/'workload.json',work)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
build=module('nis_evidence_build',root/'scripts/write-build-info.py')
release=module('nis_evidence_release',root/'scripts/run-release-gate.py')
source=build.build_manifest()
verification=release.verification_manifest()
freeze={'at':datetime.now(timezone.utc).isoformat(),'source':source,'verification':verification,'files':{rel:ref(root/rel)['sha256'] for rel in work['repair']['affected_files']},'local_checks':ref(child/'regression-aggregate.json'),'application_scope':ref(child/'final-scope-review.json'),'production_delivered':False}
save(child/'source-scope-proof.json',freeze)
rootwork=read(goal/'workload.json')
save(child/'previous-freeze.json',{k:rootwork.get(k) for k in ['frozen_source','frozen_verification_sha256','frozen_files']})
rootwork['frozen_source']=source
rootwork['frozen_verification_sha256']=verification
rootwork['frozen_files'].update(freeze['files'])
for rel,digest in rootwork['frozen_files'].items():
    assert ref(root/rel)['sha256']==digest, 'Unexpected changed frozen input: '+rel
rootwork['current_status']='LOCAL_AND_NATIVE_COUNTERS_PASS_PREPARING_FRESH_ORIGINAL_CANDIDATE'
rootwork['active_native_counter']['status']='PASS_TERMINAL'
rootwork['final_local_repair_evidence']=ref(child/'source-scope-proof.json')
save(goal/'workload.json',rootwork)
save(child/'checkpoint.json',{'at':freeze['at'],'status':rootwork['current_status'],'regression_final':{'session':68816,'exit_code':0,'passed':182},'original_complete':False,'release_pass':False,'production_delivered':False})
print(json.dumps({'source':source,'verification':rootwork['frozen_verification_sha256'],'runs':[{k:v for k,v in r.items() if k!='evidence'} for r in reports]}))
