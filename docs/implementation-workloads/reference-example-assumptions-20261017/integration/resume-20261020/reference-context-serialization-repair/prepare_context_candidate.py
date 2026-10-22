"""Prepare one normal exact-source image after isolated checks; no full PASS."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--attempt', default='')
args = parser.parse_args()
assert not args.attempt or re.fullmatch('[a-z0-9-]+', args.attempt)
suffix = '-' + args.attempt if args.attempt else ''
expected = json.loads((OUT / 'current-input-identity.json').read_text())
result = json.loads((OUT / 'reference-regressions-result.json').read_text())
assert result['cases'] == 253 and result['exit_code'] == 0
assert not any(result[k] for k in ('failures', 'errors', 'skipped'))
cases = list(ET.parse(OUT / 'reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 253 and all(not any(c.find(t) is not None for t in ('failure', 'error', 'skipped')) for c in cases)
frozen = {}
for name in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'):
    raw = (ROOT / name).read_bytes()
    assert raw == (OUT / 'after' / name).read_bytes()
    frozen[name] = hashlib.sha256(raw).hexdigest()
removal = json.loads((OUT / 'archive-review-55794a287afa/authorized-removal.json').read_text())
assert removal['status'] == 'EXACT_AUTHORIZED_IMAGE_REMOVED'
assert removal['tag'] == 'networkis:candidate-55794a287afa'
spec = importlib.util.spec_from_file_location('nis_context_delivery_identity', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
actual = owner.current_identity()
assert actual == (expected['source_sha256'], expected['commit_id'], expected['verification_sha256']), actual
output = ROOT / ('backend/test-output/release-gates/joint-context-text-originals-' + actual[0][:12] + suffix)
assert not output.exists(), 'Inspect existing preparation instead of starting twice.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
for key in ('LOCAL_AI_CONTEXT_TOKENS', 'LOCAL_AI_TIMEOUT_SECONDS'):
    env.pop(key, None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': expected,
    'frozen_affected_files': frozen, 'targeted_current_cases': 253,
    'historical_native_grammar_is_not_current_full_original_evidence': True,
    'command': command, 'output': str(output), 'full_release_pass': False, 'productive_delivery': False}
(OUT / ('candidate-prepare' + suffix + '-freeze.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record), flush=True)
with (OUT / ('candidate-prepare' + suffix + '.log')).open('w', encoding='utf-8') as log:
    completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=completed.returncode)
(OUT / ('candidate-prepare' + suffix + '-result.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
assert completed.returncode == 0, 'Inspect candidate-prepare.log; no full PASS claimed.'
print(json.dumps({'prepared_output': str(output), 'exit_code': 0, 'full_release_pass': False}), flush=True)
