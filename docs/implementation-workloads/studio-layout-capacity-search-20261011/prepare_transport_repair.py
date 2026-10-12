"""Record the verification-helper repair plan and genuine before/evidence hashes."""
import hashlib
import json
from pathlib import Path
import shutil

here = Path(__file__).resolve().parent
root = here.parents[2]
work = here / 'transport-read-repair'
work.mkdir(exist_ok=True)
relative = 'frontend/e2e/wizard.spec.ts'
before = work / 'wizard.spec.before.ts'
assert not before.exists(), 'Preserve the existing before evidence'
shutil.copyfile(root / relative, before)

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

workload = {'goal_id': 'studio-release-get-transport-repair', 'goal_type': 'implementation', 'kind': 'repair',
    'repository': str(root), 'modify_code': True, 'allow_repair': True,
    'revision_before': {relative: ref(before)['sha256']},
    'before': [ref(before)], 'files_changed': [], 'unresolved_decisions': [],
    'required_outcomes': ['bounded_read_transport_recovery', 'original_assertions_preserved', 'complete_release_pass'],
    'validation_requirements': ['transport_counterprobe', 'full_release_gate'],
    'outcomes': {}, 'validations': {}, 'completion_status': 'REPAIRING',
    'repair': {'owner': 'TOOL_CHECKER', 'finding_ids': ['ROUTING_REVIEW_GET_SOCKET_RESET'],
      'root_cause': 'The verification readProject helper uses a single HTTP GET with zero transport retries. The genuine Node trace shows Socket.socketOnEnd socket hang up in 4.791 ms, before any HTTP response; the same isolated persisted endpoint then returns correct project data on three consecutive reads. A transient connection reset prematurely terminates the persisted-state assertions. The underlying reason for peer socket closure is not claimed.',
      'first_failing_layer': 'Playwright APIRequestContext HTTP read transport, before HTTP status/body and continuity assertions',
      'reproduction': 'Full immutable-image gate: routing parameter return review fails at wizard.spec.ts:276 -> readProject:62. Real loopback counterprobe reproduces the same socket hang up and proves recovery is limited to ECONNRESET.',
      'evidence': [ref(here / 'transport-diagnosis.json'), ref(here / 'transport-counterprobe.json'),
        ref(root / 'frontend/node_modules/playwright-core/lib/coreBundle.js')],
      'affected_files': [relative], 'affected_services': ['release verification read helper'],
      'required_fix': 'Use the pinned Playwright maxRetries=2 only on readProject GET. Keep timeout 60s, HTTP failures, JSON validation, project/provenance/continuity assertions and writes unchanged.',
      'acceptance_criteria': ['one reset recovers with actual response', 'persistent resets still fail',
        'HTTP 500 not retried', 'malformed JSON still fails', 'writes never retried', 'original assertions byte-preserved outside GET options', 'fresh complete gate on exact same source image'],
      'targeted_tests': ['transport_counterprobe.mjs', 'actual routing-review case in fresh full gate'],
      'weaken_assertions_to_pass': False}}
(work / 'workload.json').write_text(json.dumps(workload, indent=2), encoding='utf-8')
print(json.dumps({'workload': str(work / 'workload.json'), 'before_sha256': ref(before)['sha256']}))
