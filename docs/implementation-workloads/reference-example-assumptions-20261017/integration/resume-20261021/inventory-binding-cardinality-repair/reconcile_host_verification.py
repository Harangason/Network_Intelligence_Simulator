"""Refreeze only tested host verification inputs; retain prior app evidence."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
HOST = ROOT / 'docs/implementation-workloads/test-stack-retention-20261021'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


assert read(HOST / 'workload.json')['status'] == 'COMPLETED'
host = read(HOST / 'workload.json')
assert host['tests'] == {'count': 38, 'failures': 0, 'scope': 'Host release tooling; no SQL or application E2E claims'}
assert read(HOST / 'removal-result.json')['status'] == 'COMPLETED'
assert read(HOST / 'live-tooling-verification.json')['status'] == 'PASSED'
for row in host['after']:
    path = Path(row['path'])
    assert ref(path)['sha256'] == row['sha256']
    assert ref(ROOT / path.relative_to(HOST / 'after'))['sha256'] == row['sha256']
retirement = OUT / 'retire-6d6-stack/retirement.json'
assert read(retirement)['status'] == 'EXACT_OBSOLETE_STACK_RETIRED'
work = read(OUT / 'workload.json')
for row in work['after']:
    path = Path(row['path'])
    assert ref(path)['sha256'] == row['sha256']
    assert ref(ROOT / path.relative_to(OUT / 'after'))['sha256'] == row['sha256']
path = OUT / 'current-input-identity.json'
previous_bytes = path.read_bytes()
previous = read(path)
historical = OUT / 'current-input-identity-before-host-retention.json'
assert not historical.exists()
historical.write_bytes(previous_bytes)
spec = importlib.util.spec_from_file_location('nis_refreeze_delivery', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
actual = owner.current_identity()
assert actual[:2] == (previous['source_sha256'], previous['commit_id'])
assert actual[2] != previous['verification_sha256']
now = datetime.now(timezone.utc).isoformat()
identity = {**previous, 'at_utc': now, 'verification_sha256': actual[2],
            'previous_identity_preserved': ref(historical),
            'host_tooling_reconciliation': str(OUT / 'host-verification-reconciliation.json')}
write(path, identity)
record = {'at_utc': now, 'status': 'TESTED_HOST_VERIFICATION_REFROZEN',
          'previous_identity': ref(historical), 'current_identity': ref(path),
          'application_and_git_unchanged': True, 'host_tests': 38,
          'host_test_scope': 'Host release tooling only',
          'targeted_app_tests': '258 distinct cases in two runs; no native/model/simulation/full-gate claim',
          'host_workload': ref(HOST / 'workload.json'),
          'host_after': host['after'], 'host_live_verification': ref(HOST / 'live-tooling-verification.json'),
          'obsolete_stack_retirement': ref(retirement), 'no_gate_or_budget_bypass': True}
write(OUT / 'host-verification-reconciliation.json', record)
work.update(status='TARGETED_PASS_HOST_VERIFIED_READY_FOR_NORMAL_PREPARATION', current_input_identity=identity,
            host_verification_reconciliation=ref(OUT / 'host-verification-reconciliation.json'))
write(OUT / 'workload.json', work)
print(json.dumps({'status': record['status'], 'identity': actual}))
