"""Execute only the human-approved exception for this task's archived image."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
report = json.loads((folder / 'failed-candidate-archive.json').read_text())
authorization = json.loads((folder / 'candidate-exchange-authorization.json').read_text())
identity = report['image_id']
assert identity == 'sha256:3048f5cf236bb6e9ba6439249ed4f5e2fc4d2bc9c032b8ebb3367b3123103cba'
assert authorization['approved'] is True and authorization['image_id'] == identity
assert authorization['archive_sha256'] == report['sha256']
assert authorization['scope'] == 'ONE_ARCHIVED_OWN_FAILED_IMAGE'
assert report['immutable_index_verified'] and report['all_layers_present']
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
image = json.loads(control('image', 'inspect', identity))[0]
assert image['Id'] == identity and image.get('RepoTags') == [report['tag']]
before = set(control('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').splitlines())
assert identity in before and len(before) == 100
evidence = {'captured_at': datetime.now(timezone.utc).isoformat(),
            'scope': authorization['scope'], 'authorization': authorization,
            'archive': report, 'container_inventory_complete': True,
            'containers': inventory, 'production_image_id': production['image_id'],
            'networkis_images_before': sorted(before), 'removed': False}
path = folder / 'candidate-exchange-evidence.json'
path.write_text(json.dumps(evidence, indent=2))
# No force, no prune, no wildcard; Docker independently refuses references.
subprocess.run([docker, 'image', 'rm', identity], check=True)
after = set(control('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').splitlines())
assert after == before - {identity}
assert control('inspect', 'NetworkIS', '--format', '{{.Image}}') == production['image_id']
evidence.update(removed=True, networkis_images_after=sorted(after),
                completed_at=datetime.now(timezone.utc).isoformat())
path.write_text(json.dumps(evidence, indent=2))
print(json.dumps({'removed': identity, 'remaining_networkis_images': len(after),
                  'production_unchanged': True, 'archive_preserved': report['archive']}))
