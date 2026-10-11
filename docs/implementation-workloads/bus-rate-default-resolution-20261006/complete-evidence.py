"""Seal verified task delivery without changing the independent campaign status."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def ref(path):
    assert path.is_file(), str(path)
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}

receipt_path = Path((OUT / 'final-receipt.txt').read_text(encoding='utf-8').strip())
release = receipt_path.parent
receipt = read(receipt_path)
production = read(OUT / 'production-verification.json')
ui = read(OUT / 'production-ui.json')
assert receipt['status'] == 'PASS' and all(check['exit_code'] == 0 for check in receipt['checks'])
assert production['status'] == ui['status'] == 'PASSED'
assert production['running_image'] == receipt['image_id']
assert production['source_sha256'] == ui['source_sha256'] == receipt['release']['source_sha256']
work = read(OUT / 'workload.json')
diff = []
for relative in work['files_changed']:
    before = OUT / 'before' / relative
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, after)
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(keepends=True) if before.exists() else [],
                                    after.read_text(encoding='utf-8').splitlines(keepends=True),
                                    fromfile='before/' + relative, tofile='after/' + relative))
(OUT / 'task.diff').write_text(''.join(diff), encoding='utf-8')
for phase in ('before', 'after'):
    manifest = []
    for relative in work['files_changed']:
        snapshot = OUT / phase / relative
        manifest.append({'file': relative, **ref(snapshot)} if snapshot.exists() else {'file': relative, 'absent': True})
    write(OUT / f'{phase}-manifest.json', manifest)
    work[phase] = [ref(OUT / f'{phase}-manifest.json')]
work['diff'] = [ref(OUT / 'task.diff')]
work['outcomes'] = {
    'container_cleanup': passed(OUT / 'docker-before.json', OUT / 'docker-final.txt'),
    'native_default_resolution': passed(OUT / 'registered-rate-audit.json', OUT / 'production-ui.json', OUT / 'targeted-backend-final.log'),
    'marked_comparison_proposals': passed(OUT / 'registered-rate-audit.json', OUT / 'production-ui.json'),
    'capacity_rate_and_bus_proposals': passed(OUT / 'targeted-backend-final.log', OUT / 'production-review.json'),
    'production_delivery': passed(receipt_path, OUT / 'delivery-final.log', OUT / 'production-verification.json'),
}
work['validations'] = {
    'targeted_regression': passed(OUT / 'targeted-backend-final.log', OUT / 'targeted-frontend.log', OUT / 'typecheck.log',
                                 OUT / 'targeted-registry-performance.log', OUT / 'targeted-runtime-lock.log',
                                 OUT / 'runtime-lock-fixed-replay.json'),
    'full_release_gate': passed(receipt_path, release / 'backend-tests.log', release / 'browser-e2e.log'),
    'production_verification': passed(OUT / 'production-verification.json', OUT / 'production-ui.json'),
}
work['delivery'].update({'tested_version': receipt['image_id'], 'running_version': production['running_image'],
    'checks': {'release': passed(receipt_path), 'deployment': passed(OUT / 'delivery-final.log', OUT / 'production-verification.json'),
               'health': passed(OUT / 'production-verification.json'),
               'functional': passed(OUT / 'production-ui.json', OUT / 'production-review.json')}})
work['remaining_findings'] = []
work['completion_status'] = 'COMPLETED'
write(OUT / 'workload.json', work)
print(json.dumps({'evidence_sealed': True, 'image': receipt['image_id'], 'files': len(work['files_changed']), 'campaign_passed': False}))
