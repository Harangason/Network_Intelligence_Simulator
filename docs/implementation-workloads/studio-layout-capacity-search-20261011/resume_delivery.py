"""Repeat the complete gate on the interrupted immutable candidate, then deliver its PASS."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

here = Path(__file__).resolve().parent
root = here.parents[2]
old_path = root / 'backend/test-output/release-gates/delivery-6ca4ab5fb4eb/bb493012fb1c/receipt.json'
old = json.loads(old_path.read_text(encoding='utf-8'))
image = 'sha256:04d9a791b807799cbec822820db86f00ccd1554910f44cc1b01f3de5e59749c5'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']

def control(*args):
    return subprocess.check_output([docker, *args], text=True).strip()

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

# No previous result is converted into a PASS or reused as completed browser coverage.
assert old['status'] == 'RUNNING'
spec = subprocess.run(['powershell', '-NoProfile', '-Command',
    f'if (Get-Process -Id {int(old["gate_pid"])} -ErrorAction SilentlyContinue) {{ exit 1 }} else {{ exit 0 }}'])
assert spec.returncode == 0, 'Previous gate is still active'
info = module('recovery_build_info', root / 'scripts/write-build-info.py').build_manifest()
assert info['source_sha256'] == old['initial_source_sha256']
assert info['commit_id'] == old['initial_commit_id']
assert control('image', 'inspect', old['image_tag'], '--format', '{{.Id}}') == image
manifest = json.loads(control('run', '--rm', '--entrypoint', 'cat', image, '/app/backend/nis/app/build-info.json'))
assert manifest['source_sha256'] == info['source_sha256']
assert manifest['commit_id'] == info['commit_id']
review = {'status': 'INTERRUPTED', 'captured_at': datetime.now(timezone.utc).isoformat(),
    'previous_receipt': str(old_path), 'previous_receipt_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
    'previous_gate_pid_absent': True, 'previous_checks': old['checks'],
    'candidate_image': image, 'source_sha256': info['source_sha256'], 'commit_id': info['commit_id'],
    'reason': 'Gate process no longer exists; browser log ends after case 106. No complete PASS exists.',
    'next_action': 'Repeat the complete mandatory gate on the same immutable image, then use canonical release-and-deploy with its PASS receipt.'}
(here / 'interrupted-release-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
for kind, key in [('container', 'app'), ('container', 'db'), ('network', 'network'), ('volume', 'runtime')]:
    name = old['containers'][key]
    assert name == f'nis-e2e-{key}-bb493012fb1c'
    existing = subprocess.run([docker, kind, 'inspect', name], capture_output=True, text=True)
    if existing.returncode:
        continue
    record = json.loads(existing.stdout)[0]
    labels = record['Config'].get('Labels', {}) if kind == 'container' else record.get('Labels', {})
    assert labels.get('networkis.test') == 'disposable'
    command = [docker, 'rm', '-f', name] if kind == 'container' else [docker, kind, 'rm', name]
    subprocess.run(command, check=True)

output = root / 'backend/test-output/release-gates/delivery-resumed-studio-20261011'
assert not output.exists(), 'Recovery output already exists; inspect rather than restart'
subprocess.run([sys.executable, str(root / 'scripts/run-release-gate.py'), '--image', image,
    '--output', str(output)], cwd=root, check=True)
receipts = list(output.rglob('receipt.json'))
assert len(receipts) == 1
subprocess.run([sys.executable, str(root / 'scripts/release-and-deploy.py'), '--receipt', str(receipts[0])],
    cwd=root, check=True)
