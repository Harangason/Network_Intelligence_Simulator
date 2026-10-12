import difflib
import hashlib
import json
from pathlib import Path
import shutil

here = Path(__file__).resolve().parent
root = here.parents[2]
work = here / 'transport-read-repair'
path = work / 'workload.json'
data = json.loads(path.read_text(encoding='utf-8'))
before = work / 'wizard.spec.before.ts'
after = work / 'wizard.spec.after.ts'
shutil.copyfile(root / 'frontend/e2e/wizard.spec.ts', after)
old = before.read_text(encoding='utf-8')
new = after.read_text(encoding='utf-8')
line = "  const result = await page.request.get(path, { headers: { 'X-Project-ID': project }, timeout: 60_000 });"
replacement = "  // Recover only a peer connection reset on this idempotent read. HTTP errors,\n  // malformed data and all continuity assertions remain failures within 60s.\n  const result = await page.request.get(path, { headers: { 'X-Project-ID': project }, timeout: 60_000, maxRetries: 2 });"
assert old.count(line) == 1 and new == old.replace(line, replacement), 'Unrelated test or assertion drift'
diff = work / 'owned-changes.diff'
diff.write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='before/frontend/e2e/wizard.spec.ts', tofile='after/frontend/e2e/wizard.spec.ts')), encoding='utf-8')

def ref(file):
    return {'path': str(file.resolve()), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}

proof = {'status': 'PASSED', 'only_get_transport_options_and_two_comments_changed': True,
    'assertions_preserved': True, 'write_requests_unchanged': True, 'timeout_unchanged_ms': 60000}
proof_path = work / 'assertion-preservation.json'
proof_path.write_text(json.dumps(proof, indent=2), encoding='utf-8')
data.update(files_changed=['frontend/e2e/wizard.spec.ts'], after=[ref(after)], diff=[ref(diff)], completion_status='VALIDATING')
data['repair']['evidence'] = [ref(here / 'transport-diagnosis.json'), ref(here / 'transport-counterprobe.json'), ref(root / 'frontend/node_modules/playwright-core/lib/coreBundle.js')]
data['outcomes']['bounded_read_transport_recovery'] = {'status': 'PASSED', 'evidence': [ref(here / 'transport-counterprobe.json')]}
data['outcomes']['original_assertions_preserved'] = {'status': 'PASSED', 'evidence': [ref(proof_path), ref(diff)]}
data['validations']['transport_counterprobe'] = data['outcomes']['bounded_read_transport_recovery']
path.write_text(json.dumps(data, indent=2), encoding='utf-8')
print(json.dumps(proof))
