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
TAG = 'networkis:candidate-ba52fd62fb41'
IMAGE = 'sha256:5191ed7ffff4ff97e550487b6ab74d366f56cdc1961eb5bb757ea6a7483b99a0'
PROTECTED = 'sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1'
RECEIPT = ROOT / 'backend/test-output/release-gates/delivery-f87cc6f48f53/ba52fd62fb41/receipt.json'
TARGET = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/failed-release-ba52fd62fb41.tar')

def command(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()

receipt = json.loads(RECEIPT.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'FAIL' and receipt['image_id'] == IMAGE
assert command('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
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
shutil.copyfile(RECEIPT, HERE / 'failed-candidate-receipt.json')
review = {
    'status': 'ARCHIVE_VERIFIED_REQUIRES_SCOPED_RETENTION_EXCEPTION',
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'image_id': IMAGE, 'tag': TAG,
    'source_sha256': receipt['release']['source_sha256'],
    'archive': str(TARGET), 'archive_sha256': archive_sha256,
    'archive_bytes': TARGET.stat().st_size,
    'immutable_index_verified': True, 'immutable_config_verified': True,
    'all_layers_present': True, 'verified_blob_count': len(verified),
    'all_containers_checked': [{'id': row['Id'], 'name': row['Name'], 'image': row['Image']} for row in containers],
    'protected_running_image': PROTECTED,
    'failed_receipt': str(HERE / 'failed-candidate-receipt.json'),
    'failed_receipt_sha256': hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
    'requested_delete_count': 1, 'deleted': False,
    'restore_command': [DOCKER, 'image', 'load', '--input', str(TARGET)],
    'requested_action': [DOCKER, 'image', 'rm', '--no-prune', TAG],
    'scope': 'Only this unused failed release candidate; complete source, immutable image, layers and failed receipt retained. Production and rollback images remain protected. No force, pruning, retention-window changes or feature-delivery equivalence claims.',
    'reason': 'New source needs a new complete release gate. The existing candidate failed the required large wizard timeout before the performance repair. Automatic retention rules protect undelivered and fresh candidate images.'
}
(HERE / 'failed-candidate-storage-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
print(json.dumps({key: review[key] for key in ['status', 'image_id', 'tag', 'archive', 'archive_sha256', 'archive_bytes', 'verified_blob_count', 'deleted']}), flush=True)
