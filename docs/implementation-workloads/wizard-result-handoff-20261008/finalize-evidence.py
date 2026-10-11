"""Seal actual final evidence after deployment and UI verification; no product writes."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RECEIPT_PATH = ROOT / 'backend/test-output/release-gates/delivery-488ac00bf2cd/b106f2e968ff/receipt.json'
OUTPUT = RECEIPT_PATH.parent


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


receipt = json.loads(RECEIPT_PATH.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('release_storage_evidence', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
assert storage.complete_pass(receipt), 'Complete release PASS required'
production_path = HERE / 'production-verification.json'
production = json.loads(production_path.read_text(encoding='utf-8'))
assert production['status'] == 'PASSED'
assert production['image_id'] == receipt['image_id']
assert production['source_sha256'] == receipt['release']['source_sha256']
ui_path = HERE / 'production-ui.json'
ui = json.loads(ui_path.read_text(encoding='utf-8'))
assert ui['status'] == 'PASSED'
assert ui['project_id'] == production['project_id']
browser_path = OUTPUT / 'browser.json'
browser = json.loads(browser_path.read_text(encoding='utf-8'))
assert browser['stats']['unexpected'] == 0 and not browser['errors']
target = []


def inspect_suites(suites):
    for suite in suites:
        inspect_suites(suite.get('suites', []))
        for test_spec in suite.get('specs', []):
            if test_spec['title'] == 'new small wizard traverses all nine stages and survives reload/restart @small':
                target.append(test_spec)


inspect_suites(browser['suites'])
assert len(target) == 1 and target[0]['ok'], 'Final real nine-stage restoration case must pass'
attachments = [attachment for test in target[0]['tests'] for result in test['results']
               for attachment in result.get('attachments', [])
               if attachment.get('name') == 'wizard-result-restoration']
assert attachments, 'Final source-bound result screenshot required'
attachment = attachments[-1]
if attachment.get('body'):
    (HERE / 'final-results.png').write_bytes(base64.b64decode(attachment['body']))
else:
    (HERE / 'final-results.png').write_bytes(Path(attachment['path']).read_bytes())
backend_log = OUTPUT / 'backend-tests.log'
backend_summary = re.search(r'(\d+) passed, (\d+) skipped, (\d+) warning, (\d+) subtests passed in ([^\n]+)', backend_log.read_text(encoding='utf-8'))
assert backend_summary, 'Actual backend suite totals required'
frontend_log = OUTPUT / 'frontend-tests.log'
frontend_pass = re.search(r'# pass (\d+)', frontend_log.read_text(encoding='utf-8'))
assert frontend_pass, 'Actual frontend suite totals required'
workload_path = HERE / 'workload.json'
workload = json.loads(workload_path.read_text(encoding='utf-8'))
final_hashes = {}
for file_path, after in zip(workload['files_changed'], workload['after'], strict=True):
    current = hashlib.sha256((ROOT / file_path).read_bytes()).hexdigest()
    assert current == after['sha256'], f'Current source no longer matches frozen after evidence: {file_path}'
    final_hashes[file_path] = current
workload['revision_checks'].append(workload['revision_before'])
workload['revision_before'] = {**workload['revision_before'], **final_hashes}
evidence = [ref(browser_path), ref(frontend_log)]
for outcome in ('finish_result_handoff', 'persisted_run_restoration', 'project_and_history_integrity'):
    workload['outcomes'][outcome] = {'status': 'PASSED', 'evidence': evidence}
workload['outcomes']['production_delivery'] = {'status': 'PASSED', 'evidence': [ref(RECEIPT_PATH), ref(production_path), ref(ui_path)]}
workload['validations']['targeted_regression'] = {'status': 'PASSED', 'evidence': evidence}
workload['validations']['complete_release'] = {'status': 'PASSED', 'evidence': [ref(RECEIPT_PATH), ref(browser_path), ref(backend_log)]}
workload['validations']['production_verification'] = {'status': 'PASSED', 'evidence': [ref(production_path), ref(ui_path)]}
workload['delivery']['tested_version'] = receipt['image_id']
workload['delivery']['running_version'] = production['image_id']
workload['delivery']['checks'] = {
    'release': {'status': 'PASSED', 'evidence': [ref(RECEIPT_PATH)]},
    'deployment': {'status': 'PASSED', 'evidence': [ref(HERE / 'delivery-final.log'), ref(production_path)]},
    'health': {'status': 'PASSED', 'evidence': [ref(production_path)]},
    'functional': {'status': 'PASSED', 'evidence': [ref(production_path), ref(ui_path), ref(browser_path)]},
}
workload['tests']['final_release'] = {
    'source_sha256': receipt['release']['source_sha256'],
    'verification_sha256': receipt['verification_sha256'],
    'backend': {'passed': int(backend_summary[1]), 'skipped': int(backend_summary[2]), 'warnings': int(backend_summary[3]), 'subtests_passed': int(backend_summary[4]), 'duration': backend_summary[5]},
    'frontend_passed': int(frontend_pass[1]),
    'browser': browser['stats'],
    'receipt': ref(RECEIPT_PATH),
    'small_http': ref(OUTPUT / 'small-http.json'),
    'large_http': ref(OUTPUT / 'large-http.json'),
    'result_image': ref(HERE / 'final-results.png'),
}
workload['repair']['status'] = 'VERIFIED'
workload['remaining_findings'] = []
workload['completion_status'] = 'COMPLETED'
workload_path.write_text(json.dumps(workload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'status': 'SEALED', 'tests': workload['tests']['final_release'], 'production_scope': production['scope'], 'production_limit': production['limitation']}, ensure_ascii=False))
