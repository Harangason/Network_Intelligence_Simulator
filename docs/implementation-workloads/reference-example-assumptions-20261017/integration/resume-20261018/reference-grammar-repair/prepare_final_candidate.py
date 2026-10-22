"""Prepare the frozen grammar repair using the normal production Dockerfile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
identity = json.loads((OUT / 'final-input-identity.json').read_text())
owned = json.loads((OUT / 'final-joint-owned-manifest.json').read_text())
for relative, row in owned.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('Source drift', relative)
test_file = OUT / 'final-reference-document-regressions.xml'
suites = ET.parse(test_file).getroot().iter('testsuite')
totals = {key: 0 for key in ('tests', 'errors', 'failures', 'skipped')}
for suite in suites:
    for key in totals:
        totals[key] += int(suite.get(key, 0))
assert totals == {'tests': 329, 'errors': 0, 'failures': 0, 'skipped': 0}, totals
assert shutil.disk_usage(ROOT).free >= 20 * 1024**3
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
prod = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert prod == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
count = len(set(subprocess.check_output([docker, 'image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}'], text=True).split()))
assert count < 100
output = ROOT / ('backend/test-output/release-gates/joint-reference-grammar-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing preparation instead of creating a duplicate.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
# Exercise the regular code defaults, not a test-only context/timeout override.
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity, 'regressions': totals,
          'image_count_before': count, 'source_free_bytes': shutil.disk_usage(ROOT).free,
          'command': command, 'development_base': None, 'context_timeout_test_override': False,
          'production_image_before': prod, 'full_pass': False, 'productive_delivery': False}
(OUT / 'new-candidate-freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
workload = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
workload.update(status='LOCAL_VALIDATED_DELIVERY_PENDING',
                completion_status='All329 affected reference/document regressions passed. Preparing normal image36f; both original native simulations and full exact-image delivery remain pending.')
workload['tests'] = {'status': 'PASSED', 'passed': 329, 'errors': 0, 'failures': 0, 'skipped': 0,
                     'report': {'path': str(test_file), 'sha256': hashlib.sha256(test_file.read_bytes()).hexdigest()}}
(OUT / 'workload.json').write_text(json.dumps(workload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(freeze), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
