"""Record actual integrated evidence without claiming native or release success."""
from datetime import datetime, timezone
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = OUT.parent
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def ref(path):
    return {'path': str(path.resolve()), 'sha256': digest(path)}
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

workload = json.loads((OUT/'workload.json').read_text(encoding='utf-8'))
manifest = json.loads((OUT/'combined-manifest.json').read_text(encoding='utf-8'))
peer = BASE/'root/qualification-stage'
for relative, item in json.loads((peer/'manifest.json').read_text(encoding='utf-8')).items():
    if relative not in manifest:
        manifest[relative] = item
        if item['before'] is not None:
            target = OUT/'combined-before'/relative
            original = peer/'before'/relative
            assert digest(original) == item['before'], relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
relative = 'backend/nis/agent/tools/proposal_service.py'
if relative not in manifest:
    original = OUT/'reference-replay-guard/before'/relative
    manifest[relative] = {'before': digest(original)}
    target = OUT/'combined-before'/relative
    target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(original.read_bytes())
manifest.setdefault('backend/tests/test_reference_model_persistence.py', {'before': None})
diff, after = [], []
for relative, item in manifest.items():
    current = ROOT/relative
    before = OUT/'combined-before'/relative
    assert item['before'] == digest(before), ('BASELINE_CHANGED', relative)
    item['current'] = digest(current)
    target = OUT/'current-after'/relative
    target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(current.read_bytes())
    after.append(ref(target))
    diff += difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True) if before.exists() else [],
        current.read_text(encoding='utf-8').splitlines(True), fromfile='before/'+relative, tofile='after/'+relative)
(OUT/'current-owned.diff').write_text(''.join(diff),encoding='utf-8')
save(OUT/'current-owned-manifest.json',manifest)

sources = []
for path, role in [
 ('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt','PRIMARY_VEHICLE'),
 ('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md','PRIMARY_ROBOTICS'),
 ('I:/PycharmProjects/neu 9.txt','REFERENCE_SUPPLEMENT_NO_QUANTITY_OVERRIDE')]:
    source = Path(path)
    sources.append({**ref(source),'role':role,'bytes':source.stat().st_size,'chars':len(source.read_bytes().decode('utf-8-sig'))})
save(OUT/'unchanged-original-sources.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'sources':sources,'source_edits':0})

checks = {}
for name, path in [('canonical_persistence',OUT/'reference-replay-guard/persistence5.xml'),
                   ('canonical_backend',OUT/'final-reference-backend.xml')]:
    if not path.exists():
        checks[name]={'status':'RUNNING_OR_PENDING'};continue
    suites=ET.parse(path).getroot().findall('testsuite')
    count={key:sum(int(s.get(key,'0')) for s in suites) for key in ('tests','failures','errors','skipped')}
    checks[name]={'status':'PASSED' if count['failures']==count['errors']==0 else 'FAILED',**count,'evidence':[ref(path)]}
front = OUT/'qualification-followup/final-frontend.log'
if front.exists():
    text=front.read_text(encoding='utf-8-sig')
    checks['canonical_frontend']={'status':'PASSED' if '# pass 143' in text and '# fail 0' in text else 'FAILED','tests':143,'evidence':[ref(front)]}
checks['canonical_typecheck']={'status':'PASSED','command':'node node_modules/typescript/bin/tsc --noEmit --incremental false','exit_code':0,'evidence':[ref(OUT/'qualification-followup/typecheck.log')]}
save(OUT/'current-validation.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
    'scope':'Unit/component and real isolated SQL persistence with a mocked reference plan. No native original-file Qwen/model/simulation or full release proof.',
    'original_native_runs':'NOT_STARTED_FOR_NEW_FEATURE','new_feature_deployment':'PENDING',
    'current_productive_image':'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'})
workload.update(status='VALIDATING' if checks['canonical_backend']['status']=='RUNNING_OR_PENDING' else 'WAITING_FOR_DECISION',
    files_changed=list(manifest),after=after,before=[ref(OUT/'combined-before'/path) for path,item in manifest.items() if item['before']],
    diff=[ref(OUT/'current-owned.diff')],current_owned_manifest=ref(OUT/'current-owned-manifest.json'),
    current_validation=ref(OUT/'current-validation.json'),updated_at_utc=datetime.now(timezone.utc).isoformat(),
    remaining_findings=[
      {'code':'EXACT_CANDIDATE_CLEANUP_APPROVAL_PENDING','image':'networkis:candidate-66a892b0b219','evidence':ref(BASE/'archive-review-66a892b0b219/archive-audit.json'),
       'reason':'100-image budget; preserved PREPARED receipt newer than FAIL is protected under AGENTS and release_storage; exact human question remains pending.'},
      {'code':'TWO_ORIGINAL_NATIVE_WORKFLOWS_PENDING','reason':'Actual local Qwen proposals, canonical full models, routing/physics/parameters/capacity/preflight and saved successful simulations remain required.'},
      {'code':'NEW_FEATURE_RELEASE_AND_DELIVERY_PENDING','reason':'Prepare exact candidate after authorized cleanup, native original-file verification, full release gate then exact-image productive adoption.'}])
save(OUT/'workload.json',workload)
print(json.dumps({'files':len(manifest),'checks':{key:value['status'] for key,value in checks.items()},'complete':False}))
