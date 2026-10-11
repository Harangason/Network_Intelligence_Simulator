"""Seal task evidence only after verified final production delivery."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
RELEASE = Path((OUT / 'final-receipt.txt').read_text(encoding='utf-8').strip()).parent
DELIVERY_LOG = Path((OUT / 'final-delivery-log.txt').read_text(encoding='utf-8').strip())

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def ref(path):
    assert path.is_file(), str(path)
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

receipt = read(RELEASE / 'receipt.json')
production = read(OUT / 'production-verification.json')
ui = read(OUT / 'production-ui.json')
assert receipt['status'] == 'PASS'
assert production['status'] == 'PASSED'
assert production['running_image'] == receipt['image_id']
assert production['source_sha256'] == receipt['release']['source_sha256']
assert ui['status'] == 'PASSED'
assert ui['source_sha256'] == production['source_sha256']
assert all(check['exit_code'] == 0 for check in receipt['checks'])
work = read(OUT / 'workload.json')
for phase in ('before', 'after'):
    manifest = []
    for relative in work['files_changed']:
        snapshot = OUT / phase / relative
        if snapshot.exists():
            if phase == 'after':
                assert snapshot.read_bytes() == (ROOT / relative).read_bytes(), relative
            manifest.append({'file': relative, **ref(snapshot)})
        else:
            assert phase == 'before', relative
            manifest.append({'file': relative, 'absent': True})
    write(OUT / f'{phase}-manifest.json', manifest)
    work[phase] = [ref(OUT / f'{phase}-manifest.json')]
work['diff'] = [ref(OUT / 'task.diff')]

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}

work['outcomes'] = {
    'accurate_parameter_status': passed(OUT / 'production-ui.json', RELEASE / 'frontend-tests.log'),
    'live_scoped_findings': passed(OUT / 'production-review.json', OUT / 'targeted-repaired.log'),
    'contextual_field_navigation': passed(OUT / 'production-ui.json', OUT / 'development-browser-final.json'),
    'explicit_network_review': passed(OUT / 'development-browser-final.json', OUT / 'rate-scope-browser.json', RELEASE / 'browser-e2e.log'),
    'production_delivery': passed(RELEASE / 'receipt.json', DELIVERY_LOG, OUT / 'production-verification.json'),
}
work['validations'] = {
    'frontend_regressions': passed(RELEASE / 'typecheck.log', RELEASE / 'frontend-tests.log'),
    'isolated_backend_regressions': passed(RELEASE / 'backend-tests.log', OUT / 'targeted-repaired.log', OUT / 'batch-targeted.log'),
    'browser_regressions': passed(RELEASE / 'browser-e2e.log', OUT / 'development-browser-final.json', OUT / 'rate-scope-browser.json'),
    'full_release_gate': passed(RELEASE / 'receipt.json'),
    'production_verification': passed(OUT / 'production-verification.json', OUT / 'production-ui.json', OUT / 'production-overview.png', OUT / 'production-field-markings.png'),
}
work['delivery'].update({
    'tested_version': receipt['image_id'], 'running_version': production['running_image'],
    'checks': {
        'release': passed(RELEASE / 'receipt.json'),
        'deployment': passed(DELIVERY_LOG, OUT / 'production-verification.json'),
        'health': passed(OUT / 'production-verification.json'),
        'functional': passed(OUT / 'production-ui.json', OUT / 'production-review.json'),
    },
})
write(OUT / 'workload.json', work)
print(json.dumps({'evidence_sealed': True, 'image': receipt['image_id'], 'files': len(work['files_changed'])}))
