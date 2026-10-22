"""Prepare one normal exact-source candidate after affected reference tests pass.

Preparation is not a complete release gate or production delivery.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
identity = json.loads((OUT / 'candidate-input-identity.json').read_text(encoding='utf-8'))
owned = json.loads((OUT / 'candidate-owned-manifest.json').read_text(encoding='utf-8'))
for name, row in owned.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == row['current'], name
cases = list(ET.parse(OUT / 'affected-reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 190
assert all(case.find('failure') is None and case.find('error') is None
           and case.find('skipped') is None for case in cases)
probes = json.loads((OUT / 'native-io-grammar-probes.json').read_text(encoding='utf-8'))
assert len(probes['results']) == 3 and all(row['http_status'] == 200 for row in probes['results'])
assert shutil.disk_usage(ROOT).free >= 20 * 1024**3
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
production = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
count = len(set(subprocess.check_output(
    [docker, 'image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}'], text=True).split()))
assert count < 100
output = ROOT / ('backend/test-output/release-gates/joint-participant-io-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing candidate preparation; never duplicate it.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity,
    'validation_scope': '190 affected isolated reference cases passed in one run; three one-token native IO compiler probes only. Original workflows and full release gate still pending.',
    'image_count_before': count, 'source_free_bytes': shutil.disk_usage(ROOT).free,
    'production_image_before': production, 'command': command, 'development_base': None,
    'context_timeout_test_override': False, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'candidate-prepare-freeze.json').write_text(json.dumps(freeze, indent=2) + '\n', encoding='utf-8')
print(json.dumps(freeze), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
