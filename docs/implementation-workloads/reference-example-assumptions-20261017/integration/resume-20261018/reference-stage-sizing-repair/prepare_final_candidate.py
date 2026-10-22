"""Build one normal isolated production candidate; never a release PASS."""
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
identity = json.loads((OUT / 'final-input-identity.json').read_text(encoding='utf-8'))
owned = json.loads((OUT / 'final-joint-owned-manifest.json').read_text(encoding='utf-8'))
for name, row in owned.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == row['current'], ('Source drift', name)
combined = {}
for file in ('affected-reference-regressions.xml', 'stage-expectation-regressions.xml'):
    for case in ET.parse(OUT / file).getroot().iter('testcase'):
        combined[case.get('classname', '') + '::' + case.get('name', '')] = (
            case.find('failure') is None and case.find('error') is None and case.find('skipped') is None)
assert len(combined) == 375 and all(combined.values())
assert shutil.disk_usage(ROOT).free >= 20 * 1024**3
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
production = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
count = len(set(subprocess.check_output([docker, 'image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}'], text=True).split()))
assert count < 100
output = ROOT / ('backend/test-output/release-gates/joint-reference-staged-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing preparation instead of creating a duplicate.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity,
    'validation_scope': '375 unique passing affected cases across preserved full first run and targeted expectation/protocol retest; not a single complete gate PASS.',
    'image_count_before': count, 'source_free_bytes': shutil.disk_usage(ROOT).free,
    'command': command, 'development_base': None, 'context_timeout_test_override': False,
    'production_image_before': production, 'full_pass': False, 'productive_delivery': False}
(OUT / 'new-candidate-freeze.json').write_text(json.dumps(freeze, indent=2) + '\n', encoding='utf-8')
print(json.dumps(freeze), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
