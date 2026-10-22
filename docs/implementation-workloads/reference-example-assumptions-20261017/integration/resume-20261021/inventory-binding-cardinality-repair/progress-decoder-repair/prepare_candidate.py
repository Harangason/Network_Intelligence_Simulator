"""One canonical preparation for changed app source; never a full PASS."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf8')


assert read(OUT / 'regression-aggregate.json')['distinct_latest_pass'] == 262
assert read(OUT / 'native-grammar/result.json')['status'] == 'PASSED'
assert read(OUT / 'retire-6d4-stack/retirement.json')['status'] == 'EXACT_OBSOLETE_STACK_RETIRED'
work = read(OUT / 'workload.json')
for ref in work['after']:
    snapshot = Path(ref['path'])
    live = ROOT / snapshot.relative_to(OUT / 'after')
    assert snapshot.read_bytes() == live.read_bytes()
    assert hashlib.sha256(live.read_bytes()).hexdigest() == ref['sha256']
spec = importlib.util.spec_from_file_location('nis_delivery_identity', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
output = ROOT / ('backend/test-output/release-gates/joint-progress-inventory-originals-' + source[:12])
assert not output.exists(), 'Inspect/reuse existing canonical output; never duplicate preparation.'
assert not (OUT / 'candidate-prepare-freeze.json').exists(), 'Existing preparation must be reconciled.'
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source,
          'commit_id': commit, 'verification_sha256': verification, 'command': command, 'output': str(output),
          'targeted_distinct_cases': 262, 'initial_failures_and_targeted_retests_preserved': True,
          'native_grammar_cases': 2, 'full_release_pass': False, 'productive_delivery': False}
write('candidate-prepare-freeze.json', record)
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
for name in ('LOCAL_AI_CONTEXT_TOKENS', 'LOCAL_AI_TIMEOUT_SECONDS'):
    env.pop(name, None)
print(json.dumps(record), flush=True)
with (OUT / 'candidate-prepare.log').open('w', encoding='utf8') as log:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode)
write('candidate-prepare-result.json', record)
assert result.returncode == 0, 'Inspect exact canonical preparation failure; no gate workaround.'
print(json.dumps({'status': 'PREPARED_ONLY', 'output': str(output)}), flush=True)
