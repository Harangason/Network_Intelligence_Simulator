"""Execute the user's exact recoverable retention exception; no force or prune."""
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
image = 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da'
tag = 'networkis:candidate-42a674cad1bc'
protected = 'sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1'
review = json.loads((HERE / 'storage-review.json').read_text())
assert review['image_id'] == image and review['tag'] == tag and review['delete_count'] == 1
archive = review['archive']
path = Path(archive['archive'])
assert path.resolve().parent == HERE.resolve() and path.stat().st_size == archive['bytes']
with path.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == archive['sha256']
assert archive['immutable_index_verified'] and archive['immutable_config_verified'] and archive['all_layers_present']
ids = subprocess.check_output([docker, 'ps', '-aq', '--no-trunc'], text=True).split()
inventory = json.loads(subprocess.check_output([docker, 'inspect', *ids], text=True)) if ids else []
assert not any(row['Image'] == image for row in inventory), 'Target is used by a container.'
assert next(row['Image'] for row in inventory if row['Name'] == '/NetworkIS') == protected
target = json.loads(subprocess.check_output([docker, 'image', 'inspect', tag], text=True))[0]
assert target['Id'] == image and target['RepoTags'] == [tag], 'Image identity or tags changed.'
assert subprocess.check_output([docker, 'image', 'inspect', protected, '--format', '{{.Id}}'], text=True).strip() == protected
record = {'status': 'AUTHORIZED_EXACT_RETENTION_EXCEPTION', 'approved_at': datetime.now(timezone.utc).isoformat(),
    'authorization': 'User answered Freigabe to the pending explicit request to remove only candidate-42a674cad1bc after preserving and verifying its full archive and PASS receipt.',
    'image_id': image, 'tag': tag, 'archive': archive, 'protected_running_image': protected,
    'all_containers_checked': [{'id': row['Id'], 'name': row['Name'], 'image': row['Image']} for row in inventory],
    'retention_disposition': 'ARCHIVED_RECOVERABLE_USER_EXCEPTION',
    'feature_disposition': 'Archive retains the complete prior candidate, every layer and the historical complete PASS receipt. No claim of delivered feature equivalence is used to authorize general pruning.',
    'scope': 'One explicitly authorized archived image only; no seven-day policy changes, no general cleanup, no force, no parent pruning.',
    'deleted': False}
output = HERE / 'authorized-image-removal.json'
output.write_text(json.dumps(record, indent=2), encoding='utf-8')
removed = subprocess.check_output([docker, 'image', 'rm', '--no-prune', tag], text=True)
assert subprocess.run([docker, 'image', 'inspect', image], capture_output=True).returncode != 0
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == protected
assert path.exists() and path.stat().st_size == archive['bytes']
remaining = set(subprocess.check_output([docker, 'image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}'], text=True).split())
record.update(deleted=True, removal_output=removed, remaining_networkis_image_count=len(remaining), status='EXACT_ARCHIVED_IMAGE_REMOVED')
output.write_text(json.dumps(record, indent=2), encoding='utf-8')
for folder in [HERE, HERE.parent / 'simulation-visibility-20261010']:
    workload_path = folder / 'workload.json'
    work = json.loads(workload_path.read_text(encoding='utf-8'))
    work['unresolved_decisions'] = []
    work['completion_status'] = 'IN_PROGRESS'
    work['delivery']['status'] = 'RELEASE_REQUIRED_AFTER_AUTHORIZED_RETENTION_EXCEPTION'
    work['delivery']['retention_exception'] = {'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    workload_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'status': record['status'], 'removed_image': image, 'retained_archive': str(path),
    'protected_running_image': protected, 'remaining_image_count': len(remaining)}))
