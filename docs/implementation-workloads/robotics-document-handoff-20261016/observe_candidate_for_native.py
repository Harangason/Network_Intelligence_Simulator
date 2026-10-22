"""Observe the gate's running immutable image without changing its receipt.

The gate persists its image fields only after the browser subprocess finishes.
This independent observation is preparation evidence, never a release PASS.
"""
from pathlib import Path
import json
import subprocess

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
path = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016/911347665bea/receipt.json'
receipt = json.loads(path.read_text(encoding='utf-8'))
assert receipt['status'] == 'RUNNING'
assert any(c['name'] == 'production-build' and c['exit_code'] == 0 for c in receipt['checks'])
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()
app = json.loads(call('inspect', receipt['containers']['app']))[0]
assert app['State']['Running'] and app['Config']['Labels']['networkis.test'] == 'disposable'
image = json.loads(call('image', 'inspect', receipt['image_tag']))[0]
assert image['Id'] == app['Image']
assert image['Config']['Labels']['networkis.release.gate'] == '911347665bea'
assert image['Config']['Labels']['networkis.release.source'] == receipt['initial_source_sha256']
manifest = json.loads(call('exec', receipt['containers']['app'], 'cat', '/app/backend/nis/app/build-info.json'))
assert manifest['source_sha256'] == receipt['initial_source_sha256'] and manifest['commit_id'] == receipt['initial_commit_id']
observation = {**receipt, 'image_id': app['Image'], 'release': manifest,
               'observation_only': True, 'release_pass': False, 'original_gate_receipt': str(path),
               'observation_provenance': 'Read-only running gate-container/image/tag/label/build-manifest verification while the official browser subprocess is active. Original gate receipt unchanged.'}
target = OUT / 'native-candidate-observed.json'
target.write_text(json.dumps(observation, indent=2), encoding='utf-8')
print(json.dumps({'status': 'OBSERVED_FOR_NATIVE_PREPARATION_ONLY', 'image_id': app['Image'], 'source_sha256': manifest['source_sha256']}))
