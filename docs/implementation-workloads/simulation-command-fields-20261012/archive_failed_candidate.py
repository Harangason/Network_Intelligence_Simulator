"""Prepare one recoverable failed-candidate retention review. Deletes nothing."""
import hashlib
import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
TAG = 'networkis:candidate-999af6c2d1bb'
IMAGE = 'sha256:3047b7a5753d356ddfeebd617b430cf5a6f70215a0cf8c4e3787922d42531992'
PROTECTED = 'sha256:89885e8cbdb16eb96e09e00dfea97936d604f3f31abe83a3ce65ce464720a382'
RECEIPT = Path('I:\\PycharmProjects\\My_first_Network_Simulator\\backend\\test-output\\release-gates\\delivery-d236d438cfff\\999af6c2d1bb\\receipt.json')
TARGET = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/failed-candidate-999af6c2d1bb.tar')

def command(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()

receipt = json.loads(RECEIPT.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'FAIL' and receipt['image_id'] == IMAGE
assert command('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
assert not any(json.loads(p.read_text()).get('status') == 'PASS' and json.loads(p.read_text()).get('image_id') == IMAGE for p in (ROOT / 'backend/test-output/release-gates').rglob('receipt.json'))
assert command('inspect', 'NetworkIS', '--format', '{{.Image}}') == PROTECTED
container_ids = command('ps', '-aq', '--no-trunc').split()
containers = json.loads(command('inspect', *container_ids)) if container_ids else []
assert not any(row['Image'] == IMAGE for row in containers), 'Candidate still referenced by a container.'
assert shutil.disk_usage(TARGET.parent).free > 5 * 1024**3
if not TARGET.exists():
    subprocess.run([DOCKER, 'image', 'save', '--output', str(TARGET), TAG], check=True)
verified = set()
with tarfile.open(TARGET) as archive:
    def verify_descriptor(descriptor):
        digest = descriptor['digest']
        assert digest.startswith('sha256:')
        if digest in verified:
            return
        name = 'blobs/sha256/' + digest.split(':', 1)[1]
        member = archive.getmember(name)
        assert member.isfile() and member.size == descriptor['size']
        with archive.extractfile(member) as blob:
            assert 'sha256:' + hashlib.file_digest(blob, 'sha256').hexdigest() == digest
        verified.add(digest)
        media = descriptor.get('mediaType', '')
        if media.endswith('index.v1+json') or media.endswith('manifest.v1+json'):
            data = json.load(archive.extractfile(member))
            for child in data.get('manifests', []):
                verify_descriptor(child)
            if 'config' in data:
                verify_descriptor(data['config'])
            for child in data.get('layers', []):
                verify_descriptor(child)
    index = json.load(archive.extractfile('index.json'))
    verify_descriptor(next(item for item in index['manifests'] if item['digest'] == IMAGE))
    manifest = json.load(archive.extractfile('manifest.json'))
    entry = next(item for item in manifest if TAG in item['RepoTags'])
    config = archive.extractfile(entry['Config']).read()
    assert entry['Config'] == 'blobs/sha256/' + hashlib.sha256(config).hexdigest()
    assert 'sha256:' + hashlib.sha256(config).hexdigest() in verified
    for layer in entry['Layers']:
        assert archive.getmember(layer).isfile()
with TARGET.open('rb') as stream:
    archive_sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
assert command('inspect', 'NetworkIS', '--format', '{{.Image}}') == PROTECTED
shutil.copyfile(RECEIPT, HERE / 'failed-candidate-999af6c2d1bb-receipt.json')
review = {
    'status': 'ARCHIVE_VERIFIED_STANDING_AUTHORIZATION',
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'image_id': IMAGE, 'tag': TAG,
    'source_sha256': receipt['initial_source_sha256'],
    'archive': str(TARGET), 'archive_sha256': archive_sha256,
    'archive_bytes': TARGET.stat().st_size,
    'immutable_index_verified': True, 'immutable_config_verified': True,
    'all_layers_present': True, 'verified_blob_count': len(verified),
    'all_containers_checked': [{'id': row['Id'], 'name': row['Name'], 'image': row['Image']} for row in containers],
    'protected_running_image': PROTECTED,
    'failed_receipt': str(HERE / 'failed-candidate-999af6c2d1bb-receipt.json'),
    'failed_receipt_sha256': hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
    'requested_delete_count': 1, 'deleted': False,
    'restore_command': [DOCKER, 'image', 'load', '--input', str(TARGET)],
    'requested_action': [DOCKER, 'image', 'rm', '--no-prune', TAG],
    'scope': 'Only this unused failed candidate; complete source, immutable image, layers and FAIL receipt retained. Production and rollback images remain protected. No force, pruning, retention-window changes or feature-delivery equivalence claims.',
    'reason': 'This older unused candidate has only FAIL receipts and cannot be delivered with them. Its complete recoverable archive is verified under standing user authorization because the release gate blocks new candidates at 100 immutable images; no feature-delivery equivalence is claimed.'
}
(HERE / 'failed-candidate-999af6c2d1bb-storage-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
print(json.dumps({key: review[key] for key in ['status', 'image_id', 'tag', 'archive', 'archive_sha256', 'archive_bytes', 'verified_blob_count', 'deleted']}), flush=True)



