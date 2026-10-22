"""Prepare one ordinary production candidate after exact isolated regressions.

PREPARED is not original-model acceptance, full release PASS or deployment.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
expected = json.loads((OUT / 'current-input-identity.json').read_text())
work = json.loads((OUT / 'workload.json').read_text())
for row in work['after']:
    saved = Path(row['path'])
    live = ROOT / saved.relative_to(OUT / 'after')
    assert hashlib.sha256(live.read_bytes()).hexdigest() == row['sha256']
    assert saved.read_bytes() == live.read_bytes()
for name, count in [('reasoner-regressions', 103), ('remaining-reference-regressions', 155)]:
    result = json.loads((OUT / (name + '-result.json')).read_text())
    cases = list(ET.parse(OUT / (name + '.xml')).getroot().iter('testcase'))
    assert result['exit_code'] == 0 and len(cases) == result['cases'] == count
    assert not any(result[key] for key in ('failures', 'errors', 'skipped'))
    assert all(not any(c.find(tag) is not None for tag in ('failure', 'error', 'skipped')) for c in cases)
removal = json.loads((OUT / 'archive-review-75ccb83f4e33/authorized-removal.json').read_text())
assert removal['status'] == 'EXACT_AUTHORIZED_IMAGE_REMOVED'
spec = importlib.util.spec_from_file_location('nis_current_delivery_identity', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
actual = owner.current_identity()
assert actual == (expected['source_sha256'], expected['commit_id'], expected['verification_sha256']), actual
output = ROOT / ('backend/test-output/release-gates/joint-single-inventory-originals-' + actual[0][:12])
assert not output.exists(), 'Inspect an existing preparation; never duplicate it.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
for key in ('LOCAL_AI_CONTEXT_TOKENS', 'LOCAL_AI_TIMEOUT_SECONDS'):
    env.pop(key, None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': expected,
          'targeted_cases_in_two_disjoint_runs': 258, 'command': command,
          'frozen_affected_files': {str(Path(row['path']).relative_to(OUT / 'after')).replace('\\', '/'): row['sha256']
                                    for row in work['after']},
          'output': str(output), 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'candidate-prepare-freeze.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
with (OUT / 'candidate-prepare.log').open('w', encoding='utf-8') as log:
    completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=completed.returncode)
(OUT / 'candidate-prepare-result.json').write_text(json.dumps(record, indent=2) + '\n')
assert completed.returncode == 0, 'Inspect preparation evidence; no full PASS claimed.'
print(json.dumps({'prepared_output': str(output), 'full_release_pass': False}), flush=True)
