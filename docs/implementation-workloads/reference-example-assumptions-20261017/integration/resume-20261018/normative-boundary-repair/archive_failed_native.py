"""Secure the superseded native test runtime. Never removes an image."""
import hashlib
import importlib.util
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent / 'archive-review-d520e6b852e5'
OUT.mkdir(exist_ok=True)
TAG = 'networkis:candidate-d520e6b852e5'
IMAGE = 'sha256:2c2840df896a406910ef4c1c68f3c43afcb48f819dae1f493805d0aeb4d0d896'
BASE = 'http://127.0.0.1:61987'
APP, DB = 'nis-e2e-app-d520e6b852e5', 'nis-e2e-db-d520e6b852e5'
ARCHIVE_ROOT = Path('C:/Users/marti/AppData/Local/NetworkIS/archived-candidates/normative-boundary-20261018')
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
ARCHIVE = ARCHIVE_ROOT / 'candidate-d520e6b852e5.tar'
DUMP = ARCHIVE_ROOT / 'native-test-projects-d520e6b852e5.dump'
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']

def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()

def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.resolve()), 'sha256': digest, 'bytes': path.stat().st_size}

assert call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert production != IMAGE
projects = ['20261018110232672-964994ce', '20261018113821095-5bb997f2']
exports = []
for project in projects:
    for name, endpoint in [('bundle', '/api/engineering/projects/export'), ('jobs', '/api/simulations')]:
        request = Request(BASE + endpoint, headers={'X-Project-ID': project})
        with urlopen(request, timeout=45) as response:
            raw = response.read()
        data = json.loads(raw)
        assert data.get('project_id', project).removeprefix('network-project-') == project
        if name == 'jobs':
            assert data['jobs'] == [], 'An unexpected simulation protects this runtime.'
        path = OUT / (project + '-' + name + '.json')
        path.write_bytes(raw)
        exports.append(ref(path))
assert not ARCHIVE.exists() and not DUMP.exists(), 'Do not overwrite a secured recovery artifact.'
with DUMP.open('wb') as output:
    subprocess.run([DOCKER, 'exec', DB, 'sh', '-c', 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=output, check=True)
with DUMP.open('rb') as source:
    result = subprocess.run([DOCKER, 'exec', '-i', DB, 'pg_restore', '--list'], stdin=source, capture_output=True, check=True)
(OUT / 'database-restore-list.txt').write_bytes(result.stdout)
subprocess.run([DOCKER, 'image', 'save', '--output', str(ARCHIVE), TAG], check=True)
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'IMAGE_AND_NATIVE_RUNTIME_SECURED_NO_IMAGE_REMOVAL',
          'tag': TAG, 'image_id': IMAGE, 'production_image': production, 'test_projects': projects,
          'exports': exports, 'database_dump': ref(DUMP), 'dump_contents_readable': True,
          'archive': ref(ARCHIVE), 'image_removal': False,
          'reason': 'Actual completed local Qwen intake failed the aggregate normative-context guard. General source fix requires a new candidate; no model was manually corrected.'}
(OUT / 'secured-runtime.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert call('inspect', APP, '--format', '{{.Image}}') == IMAGE
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == production
verified = set()
with tarfile.open(ARCHIVE) as tar:
    def verify(desc):
        digest = desc['digest']
        assert digest.startswith('sha256:')
        if digest in verified:
            return
        member = tar.getmember('blobs/sha256/' + digest.split(':')[1])
        assert member.isfile() and member.size == desc['size']
        with tar.extractfile(member) as stream:
            assert 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() == digest
        verified.add(digest)
        if desc.get('mediaType', '').endswith(('index.v1+json', 'manifest.v1+json', 'manifest.v2+json', 'manifest.list.v2+json')):
            data = json.load(tar.extractfile(member))
            for child in data.get('manifests', []):
                verify(child)
            if 'config' in data:
                verify(data['config'])
            for child in data.get('layers', []):
                verify(child)
    index = json.load(tar.extractfile('index.json'))
    verify(next(desc for desc in index['manifests'] if desc['digest'] == IMAGE))
    manifest = json.load(tar.extractfile('manifest.json'))
    entry = next(item for item in manifest if TAG in item['RepoTags'])
    config = tar.extractfile(entry['Config']).read()
    config_hash = hashlib.sha256(config).hexdigest()
    assert entry['Config'] == 'blobs/sha256/' + config_hash and 'sha256:' + config_hash in verified
    assert all(tar.getmember(layer).isfile() and 'sha256:' + layer.split('/')[-1] in verified for layer in entry['Layers'])
container_ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *container_ids)) if container_ids else []
receipt_path = ROOT / 'backend/test-output/release-gates/joint-reference-portfolio-native-cf37e30cc3a5/d520e6b852e5/receipt.json'
assert json.loads(receipt_path.read_text())['status'] == 'PREPARED'
audit = {'status': 'ARCHIVED_VERIFIED_STILL_CONTAINER_REFERENCED', 'tag': TAG, 'image': IMAGE,
         'archive': record['archive'], 'database_dump': record['database_dump'], 'exports': exports,
         'verified_blobs': sorted(verified), 'immutable_index_verified': True, 'immutable_config_verified': True,
         'all_layers_verified': True, 'receipt': ref(receipt_path), 'receipt_status': 'PREPARED',
         'container_references': [{'id': row['Id'], 'name': row['Name'], 'image': row['Image']} for row in containers if row['Image'] == IMAGE],
         'production': production, 'container_removal': False, 'image_removal': False,
         'restore_command': [DOCKER, 'image', 'load', '--input', str(ARCHIVE)]}
(OUT / 'archive-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': audit['status'], 'tag': TAG, 'verified_blobs': len(verified), 'production_unchanged': True}), flush=True)
