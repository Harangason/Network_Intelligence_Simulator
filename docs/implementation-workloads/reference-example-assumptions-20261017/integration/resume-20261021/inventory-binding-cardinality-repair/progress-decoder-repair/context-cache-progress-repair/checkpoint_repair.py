"""Record current evidence without claiming original/release acceptance."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
P = Path(__file__).resolve().parent
C = P.parent
W = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017'

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

work = json.loads((P / 'workload.json').read_text(encoding='utf-8'))
changed = ['backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py',
           'frontend/src/features/agent/lib/engineering-specification.ts', 'frontend/src/features/agent/lib/engineering-specification.test.mjs']
after = P / 'after'
after.mkdir(exist_ok=True)
diff = []
for file in changed:
    current = ROOT / file
    snapshot = after / file
    snapshot.parent.mkdir(exist_ok=True, parents=True)
    snapshot.write_bytes(current.read_bytes())
    before = P / ('before-' + current.name if file.startswith('backend') else 'before-preview-' + current.name)
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),
        current.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + file, tofile=file))
diff_path = P / 'applied-repair.diff'
diff_path.write_text(''.join(diff), encoding='utf-8')
work.update(files_changed=changed, after=[ref(after / file) for file in changed], diff=[ref(diff_path)],
    status='VALIDATING', automation_status='DELETED_AT_DIRECT_HUMAN_REQUEST', cancellation_authorized=True,
    native_cache_probe_status='NOT_STARTED', original_acceptance=False, full_release_pass=False, productive_delivery=False)
work['validations'].update(red_green={'status': 'PASSED', 'evidence': [ref(P / 'red.xml'), ref(P / 'green.xml'), ref(P / 'preview-red.txt'), ref(P / 'preview-green.txt')]})
write(P / 'workload.json', work)
checkpoint = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'CONTEXT_AND_PREVIEW_REPAIR_VALIDATING',
    'cancellation': ref(P / 'cancellation-74486.json'), 'workload': ref(P / 'workload.json'),
    'backend_full_regression_session': 23914, 'exact_wire_regression_session': 32345,
    'green_cases': 12, 'frontend_parser_cases': 132, 'frontend_adjacent_cases': 40,
    'typecheck_exit': 0, 'automation_status': 'DELETED_AT_DIRECT_HUMAN_REQUEST',
    'application_changed': True, 'candidate99b_source_is_now_obsolete': True,
    'next': 'Complete backend/native cache verification; archive exact99b stack with image preserved; one final normal candidate; both original full workflows/ALL simulations/full release/deploy.',
    'original_model_acceptance': False, 'full_release_pass': False, 'productive_delivery': False}
write(P / 'checkpoint.json', checkpoint)
root_path = W / 'integration/workload.json'
root = json.loads(root_path.read_text(encoding='utf-8'))
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 15
root.update(status='REPAIRING', automation_status='DELETED_AT_DIRECT_HUMAN_REQUEST',
    latest_context_cache_progress_repair=ref(P / 'checkpoint.json'),
    native74486_actual_terminal=ref(P / 'cancellation-74486.json'))
write(root_path, root)
state_path = W / 'integration/native-progress-vehicle/state.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
if state['status'] == 'NATIVE_PLAN_REFERENCE_RUNNING':
    backup = P / 'client-state-before-cancel-reconciliation.json'
    assert not backup.exists()
    write(backup, state)
    state.update(status='NATIVE_PLAN_REFERENCE_CANCELED_BY_EXPLICIT_USER',
        at_utc=datetime.now(timezone.utc).isoformat(), terminal_evidence=ref(P / 'cancellation-74486.json'),
        error='Client interrupted at explicit human request; server REFERENCE_CANCELED; driver and main worker ended. Exit code unavailable.')
    write(state_path, state)
heading = ('# Current:74486 canceled by explicit human approval; repairs applied and validating\n\n'
    'Automation is DELETED; continue directly here, never recreate. Cancellation is verified by\n'
    'server REFERENCE_CANCELED, absent driver/main worker and empty main /api/ps. Client exitcode\n'
    'is unavailable; do not invent it. Last saved32calls were unaccepted inventory, no model.\n\n'
    'context-cache-progress-repair/workload.json and checkpoint.json are current. Native prompt\n'
    'history now uses lossless append-only state deltas, stable configured131072 capacity and\n'
    'complete-snapshot rebasing; output8192/timeout1200/strict gates unchanged. Three RED then\n'
    '12 GREEN cases;132 frontend parser and40 adjacent cases PASS, typecheck exit0. Full backend\n'
    'session23914 and exact-wire32345 still require terminal results. Actual native cache probe\n'
    'NOT STARTED; no native performance improvement or original acceptance claimed yet.\n\n'
    'Raw preview defect independently reproduced on literal423922-byte35-profile source.\n'
    'Profile identity now retained; Medizingeräte gateway is021Ambulance, missing transport\n'
    'stays unknown rather than borrowed LIN; TC assertions do not declare physical devices.\n'
    'Browser exactfilehash remains unverified. Production3792/fd2d remains unchanged.\n\n'
    'After relevant verification, archive/retire exact99b retained stack, preserve image/receipt,\n'
    'freeze new bundled source, prepare one normal candidate. Both originals/full canonical\n'
    'models/ALL simulations/all15/15/full exact-image releasegate/productive takeover remain\n'
    'required and OPEN. No internal-inventory resume or manual model changes.\n\n')
for path in (C / 'NEXT.md', W / 'TODO.md'):
    old = path.read_text(encoding='utf-8')
    if not old.startswith('# Current:74486 canceled'):
        path.write_text(heading + old, encoding='utf-8')
print(json.dumps(checkpoint, ensure_ascii=False))
