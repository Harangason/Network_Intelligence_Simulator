"""Remove only the verified, unreferenced FAIL candidate under standing authorization."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
HERE = BASE / 'editor-image-cleanup'
review = json.loads((HERE / 'failed-candidate-storage-review.json').read_text(encoding='utf-8'))
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
tag, image = review['tag'], review['image_id']
assert tag == 'networkis:candidate-d6f3ebf19610'
assert image == 'sha256:82bc49fa4c144d6f9937c2f6af7cecf8d863dd8ead9f4e33656bf9e69500fed5'
assert review['immutable_index_verified'] and review['immutable_config_verified'] and review['all_layers_present']

def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()

archive = Path(review['archive'])
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == review['archive_sha256']
assert archive.stat().st_size == review['archive_bytes']
receipts = []
for parent in (ROOT / 'backend/test-output', ROOT / 'work'):
    for path in parent.rglob('receipt.json'):
        receipt = json.loads(path.read_text(encoding='utf-8-sig'))
        if receipt.get('image_id') == image:
            assert receipt['status'] == 'FAIL', str(path)
            receipts.append({'path': str(path), 'status': receipt['status'],
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
assert receipts
inspect = json.loads(call('image', 'inspect', tag))[0]
assert inspect['Id'] == image and inspect['RepoTags'] == [tag]
ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *ids)) if ids else []
assert all(c['Image'] != image for c in containers)
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == review['protected_running_image']
audit = {'captured_at': datetime.now(timezone.utc).isoformat(), 'image': image, 'tag': tag,
         'archive': str(archive), 'archive_sha256': review['archive_sha256'],
         'receipts': receipts, 'containers': [{'id': c['Id'], 'name': c['Name'], 'image': c['Image']} for c in containers],
         'authorization': 'AGENTS.md: standing scoped authorization for archived unused FAIL candidates',
         'command': [docker, 'image', 'rm', '--no-prune', tag]}
(HERE / 'fresh-removal-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
assert call('image', 'inspect', tag, '--format', '{{.Id}}') == image
result = subprocess.run(audit['command'], capture_output=True, text=True, encoding='utf-8', check=True)
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == review['protected_running_image']
assert subprocess.run([docker, 'image', 'inspect', tag], capture_output=True).returncode != 0
(HERE / 'removal-result.json').write_text(json.dumps({'status': 'REMOVED', 'image': image,
    'tag': tag, 'exit_code': result.returncode, 'output': result.stdout, 'production_unchanged': True}, indent=2), encoding='utf-8')
print(json.dumps({'status': 'REMOVED', 'image': image, 'tag': tag, 'production_unchanged': True}))
