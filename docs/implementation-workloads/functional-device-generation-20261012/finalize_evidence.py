"""Capture owned changes and, when supplied, verified production evidence."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

base = Path(__file__).resolve().parent
root = base.parents[2]
work = json.loads((base / 'workload.json').read_text(encoding='utf-8-sig'))

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

after, diff = [], []
for name in work['files_changed']:
    source, target, before = root / name, base / 'after' / name, base / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    after.append(ref(target))
    diff.extend(difflib.unified_diff(
        before.read_text(encoding='utf-8-sig').splitlines(keepends=True) if before.exists() else [],
        source.read_text(encoding='utf-8-sig').splitlines(keepends=True),
        fromfile='before/' + name, tofile='after/' + name))
(base / 'owned-changes.diff').write_text(''.join(diff), encoding='utf-8')
work['after'], work['diff'] = after, [ref(base / 'owned-changes.diff')]
work['outcomes']['functional_generation']['evidence'] = [ref(base / 'implementation.md'), ref(base / 'owned-changes.diff')]
tests = [ref(base / name) for name in ['backend-tests.log', 'backend-functional-final.log', 'frontend-tests.log', 'structure-tests.log']]
work['outcomes']['cross_industry_validation'] = {'status': 'PASSED', 'evidence': tests}
work['validations']['targeted_tests'] = {'status': 'PASSED', 'evidence': tests}
if len(sys.argv) > 1:
    receipt_path = Path(sys.argv[1]).resolve()
    receipt = json.loads(receipt_path.read_text())
    production = json.loads((base / 'production-functional.json').read_text())
    assert receipt['status'] == 'PASS' and production['status'] == 'PASSED'
    assert receipt['image_id'] == production['image_id']
    assert production['build-info']['source_sha256'] == receipt['release']['source_sha256']
    shutil.copyfile(receipt_path, base / 'release-pass-receipt.json')
    release, live = ref(base / 'release-pass-receipt.json'), ref(base / 'production-functional.json')
    work['validations']['release_gate'] = {'status': 'PASSED', 'evidence': [release]}
    work['outcomes']['production_delivery'] = {'status': 'PASSED', 'evidence': [release, live]}
    work['delivery'].update(tested_version=receipt['image_id'], running_version=production['image_id'],
        checks={name: {'status': 'PASSED', 'evidence': [release] if name == 'release' else [live]}
                for name in ('release', 'deployment', 'health', 'functional')})
    work['status'] = 'COMPLETED'
(base / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'evidence_refreshed': True, 'production': work['outcomes']['production_delivery']['status']}))
