"""Execute the user's single archived-image exception, with fresh protection checks."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
report = json.loads((folder / 'previous-production-archive.json').read_text())
identity = report['image_id']
assert identity == 'sha256:ff5438ce73a20ea32e82c18f9a24002b0eda00787c60afa3593df2774d031a39'
authorization = {'approved': True, 'image_id': identity, 'archive_sha256': report['sha256'],
                 'scope': 'ONE_ARCHIVED_PREVIOUS_PRODUCTION_IMAGE',
                 'user_reply': 'dann mach das produktiv, das nervt mich',
                 'context': 'Reply to the concrete pending request to replace archived candidate-debee1861880, preserving current ad0de59d production and all archives/receipts.',
                 'recorded_at': datetime.now(timezone.utc).isoformat()}
(folder / 'image-exchange-authorization.json').write_text(json.dumps(authorization, indent=2), encoding='utf-8')
assert report['immutable_index_verified'] and report['immutable_config_verified'] and report['all_layers_present']
with Path(report['archive']).open('rb') as archive:
    assert hashlib.file_digest(archive, 'sha256').hexdigest() == report['sha256']

docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
def control(*args):
    return subprocess.check_output([docker, *args], text=True).strip()
container_ids = control('ps', '-a', '--no-trunc', '--format', '{{.ID}}').splitlines()
containers = json.loads(control('inspect', *container_ids)) if container_ids else []
inventory = [{'name': item['Name'], 'container_id': item['Id'], 'image_id': item['Image']} for item in containers]
assert inventory and not any(item['image_id'] == identity for item in inventory)
production = next(item for item in inventory if item['name'] == '/NetworkIS')
assert production['image_id'] == 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da'
image = json.loads(control('image', 'inspect', identity))[0]
assert image['Id'] == identity and image.get('RepoTags') == [report['tag']]
before = set(control('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').splitlines())
assert identity in before and len(before) == 100
evidence = {'captured_at': datetime.now(timezone.utc).isoformat(), 'authorization': authorization,
            'archive': report, 'container_inventory_complete': True, 'containers': inventory,
            'production_image_id': production['image_id'], 'networkis_images_before': sorted(before), 'removed': False}
path = folder / 'image-exchange-evidence.json'
path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
# Exact identity only; no force, pruning, filesystem deletion or wildcard.
subprocess.run([docker, 'image', 'rm', identity], check=True)
after = set(control('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').splitlines())
assert after == before - {identity}
assert control('inspect', 'NetworkIS', '--format', '{{.Image}}') == production['image_id']
evidence.update(removed=True, networkis_images_after=sorted(after), completed_at=datetime.now(timezone.utc).isoformat())
path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps({'removed': identity, 'remaining_networkis_images': len(after), 'production_unchanged': True,
                  'archive_preserved': report['archive']}), flush=True)
