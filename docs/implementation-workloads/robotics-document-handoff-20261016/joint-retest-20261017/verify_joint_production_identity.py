"""Independently verify exact image, readiness and owned deployed source files."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import subprocess
import time
from urllib.request import urlopen

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
NATIVE = OUT
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
receipt_path = args.receipt.resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
native = json.loads((NATIVE / 'native-verification.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and native['status'] == 'PASSED'
required_checks = {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'}
assert required_checks <= {item['name'] for item in receipt['checks'] if item['exit_code'] == 0}
assert all(item['exit_code'] == 0 for item in receipt['checks'])
runtime = json.loads((NATIVE / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
assert runtime['image_id'] == receipt['image_id']
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
def inspect():
    return json.loads(subprocess.check_output([docker, 'inspect', 'NetworkIS'], text=True, encoding='utf-8'))[0]
running = inspect()
assert running['Image'] == receipt['image_id'] and running['State']['Status'] == 'running'
for attempt in range(90):
    if running['State'].get('Health', {}).get('Status') == 'healthy':
        break
    time.sleep(1)
    running = inspect()
else:
    raise RuntimeError('Production container health did not become healthy.')
with urlopen('http://127.0.0.1:13500/api/ready', timeout=5) as response:
    ready = json.load(response)
with urlopen('http://127.0.0.1:13500/api/build-info', timeout=5) as response:
    build = json.load(response)
assert ready['status'] == 'ready' and build['source_sha256'] == receipt['initial_source_sha256']
assert build['commit_id'] == receipt['initial_commit_id']
freeze = json.loads((ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/followup-communication-actions/source-freeze.json').read_text(encoding='utf-8'))
assert freeze['source_sha256'] == receipt['initial_source_sha256'] == runtime['source_sha256']
work = {'revision_after': freeze['files']}
program = 'from pathlib import Path\nimport hashlib,json\npaths=' + repr(list(work['revision_after'])) + '\nprint(json.dumps({p:hashlib.sha256((Path("/app")/p).read_bytes()).hexdigest() for p in paths}))\n'
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=program, text=True, encoding='utf-8', capture_output=True, check=True)
hashes = json.loads(result.stdout)
assert hashes == work['revision_after'], 'Deployed owned source files differ from the tested canonical files.'
record = {'status': 'PASSED', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Exact tested image, running container health, ready/build API and all 16 frozen source/test/mapping/fixture files; native document acceptance separately recorded on same immutable image.',
          'receipt': str(receipt_path), 'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
          'image_id': running['Image'], 'source_sha256': build['source_sha256'], 'ready': ready, 'build': build,
          'container_health': running['State']['Health']['Status'], 'container_started_at': running['State']['StartedAt'],
          'module_hashes': hashes, 'canonical_model_writes': False}
(OUT / 'production-identity-verification.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps({key: record[key] for key in ('status', 'image_id', 'source_sha256', 'container_health')}))
