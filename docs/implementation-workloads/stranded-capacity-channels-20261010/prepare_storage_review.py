"""Fresh read-only inventory and a concrete recoverable retention exception."""
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

folder = Path(__file__).resolve().parent
root = folder.parents[2]
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
archive = json.loads((folder / 'previous-production-archive.json').read_text())
target = Path(archive['archive'])
with target.open('rb') as source:
    assert hashlib.file_digest(source, 'sha256').hexdigest() == archive['sha256']
assert target.stat().st_size == archive['bytes']
assert archive['immutable_index_verified'] and archive['immutable_config_verified'] and archive['all_layers_present']
ids = subprocess.check_output([docker, 'ps', '-aq', '--no-trunc'], text=True).split()
containers = json.loads(subprocess.check_output([docker, 'inspect', *ids], text=True)) if ids else []
inventory = [{'name': row['Name'].lstrip('/'), 'id': row['Id'], 'image': row['Image']} for row in containers]
assert not any(row['image'] == archive['image_id'] for row in inventory)
running = next(row['image'] for row in inventory if row['name'] == 'NetworkIS')
assert running == 'sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1'
assert subprocess.check_output([docker, 'image', 'inspect', archive['tag'], '--format', '{{.Id}}'], text=True).strip() == archive['image_id']
receipt = root / 'backend/test-output/release-gates/studio-toolbar-performance-resumed/79b52a3c4edf/receipt.json'
previous_pass = json.loads(receipt.read_text())
assert previous_pass['status'] == 'PASS' and previous_pass['image_id'] == archive['image_id']
health = {}
for base in ('http://127.0.0.1:13500', 'http://192.168.178.10:13500'):
    with urlopen(base + '/api/ready', timeout=30) as response:
        health[base] = json.load(response)
    assert health[base]['status'] == 'ready'
ref = lambda p: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
review = {'status': 'WAITING_FOR_USER_RETENTION_EXCEPTION', 'image_id': archive['image_id'], 'tag': archive['tag'],
          'delete_count': 1, 'deleted': False, 'archive': archive, 'archive_evidence': ref(folder / 'previous-production-archive.json'),
          'previous_complete_pass': ref(receipt), 'complete_container_inventory': inventory,
          'protected_current_production': running, 'health': health,
          'reason': '100 immutable NIS images block a changed-source release. This archived predecessor remains protected by the seven-day retention rule and pending feature audit.',
          'proposal': 'After explicit approval, refresh inventory and archive hashes, remove only this exact unused image without force or prune. Keep its complete archive and PASS receipt. Then pass the full gate, deploy its exact tested image and apply the reversible canonical channel reconciliation.'}
(folder / 'storage-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
print(json.dumps({'status': review['status'], 'archive_verified': True, 'unused_by_all_containers': True,
                  'current_production_ready_local_and_lan': True, 'delete_count': 1, 'deleted': False}))
