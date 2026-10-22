"""Independently inspect the peer-owned native candidate without changing it."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from urllib.parse import urlsplit
from urllib.request import urlopen

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
peer_path = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/native-be82385-20261017/native-runtime-preparation.json'
runtime = json.loads(peer_path.read_text(encoding='utf-8'))
assert runtime['release_pass'] is False and runtime['uses_product_database'] is False
freeze = json.loads((ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/followup-communication-actions/source-freeze.json').read_text(encoding='utf-8'))
receipt = json.loads(Path(runtime['candidate_receipt']).read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
assert receipt['image_id'] == runtime['image_id']
assert receipt['initial_source_sha256'] == runtime['source_sha256'] == freeze['source_sha256']
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
app = json.loads(subprocess.check_output([docker, 'inspect', runtime['containers']['app']], text=True, encoding='utf-8'))[0]
assert app['Image'] == runtime['image_id'] and app['Id'] == runtime['app_container_id']
assert app['Config']['Labels']['networkis.test'] == 'disposable'
environment = dict(row.split('=', 1) for row in app['Config']['Env'] if '=' in row)
database = urlsplit(environment['DATABASE_URL'])
assert database.hostname == 'test-db' and database.path == '/nis_test_e2e'
binding = app['HostConfig']['PortBindings']['13500/tcp'][0]
assert binding['HostIp'] == '127.0.0.1' and binding['HostPort'] == '62641'
with urlopen(runtime['base_url'] + '/api/ready', timeout=10) as response:
    ready = json.load(response)
with urlopen(runtime['base_url'] + '/api/build-info', timeout=10) as response:
    build = json.load(response)
assert ready['status'] == 'ready' and build['source_sha256'] == freeze['source_sha256']
assert build['commit_id'] == freeze['commit_id']
program = 'from pathlib import Path\nimport hashlib,json\npaths=' + repr(list(freeze['files'])) + '\nprint(json.dumps({p:hashlib.sha256((Path("/app")/p).read_bytes()).hexdigest() for p in paths}))\n'
result = subprocess.run([docker, 'exec', '-i', runtime['containers']['app'], 'python', '-'], input=program, text=True, encoding='utf-8', capture_output=True, check=True)
hashes = json.loads(result.stdout)
assert hashes == freeze['files']
record = {'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Independent read-only image/container/test-isolation/ready/source/16-file verification; no stack mutation, Qwen call, SQL test or model generation.', 'image_id': app['Image'], 'source_sha256': build['source_sha256'], 'build': build, 'ready': ready, 'module_hashes': hashes, 'peer_runtime_sha256': hashlib.sha256(peer_path.read_bytes()).hexdigest()}
(OUT / 'shared-runtime-identity-verification.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
runtime.update(stack_owner='NIS starten', own_project='20261016084924562-131ed051', shared_stack=True, cleanup_owner='NIS starten', peer_runtime=str(peer_path), native_qwen_slot='NOT_YET_TRANSFERRED')
assert not (OUT / 'native-runtime-preparation.json').exists()
(OUT / 'native-runtime-preparation.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'image_id': app['Image'], 'source_sha256': build['source_sha256'], 'files_checked': len(hashes)}))
