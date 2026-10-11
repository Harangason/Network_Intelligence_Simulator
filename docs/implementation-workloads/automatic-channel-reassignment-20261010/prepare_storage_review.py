"""Prepare a recoverable, exact image proposal. Never remove an image."""
import hashlib
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
prior = root / 'docs/implementation-workloads/studio-toolbar-trace-defaults-20261009/archive_failed_candidate.py'
script = prior.read_text(encoding='utf-8')
replacements = {
    'networkis:candidate-fc5d3079141e': 'networkis:candidate-debee1861880',
    'sha256:3048f5cf236bb6e9ba6439249ed4f5e2fc4d2bc9c032b8ebb3367b3123103cba': 'sha256:ff5438ce73a20ea32e82c18f9a24002b0eda00787c60afa3593df2774d031a39',
    'failed-candidate-fc5d3079141e.tar': 'previous-production-debee1861880.tar',
    'failed-candidate-archive.json': 'previous-production-archive.json',
    '67e8443a1a65ab15334f0cdec6edd854945201b2e004981a5a8868bb42be41db': '513dc8c58b2fb43a13ab25859ed262d9ef1efedbf218c11d8329fdffb811af16',
    'Own failed candidate from this task; current production and historical images excluded':
        'Previous production image, archived for a user-reviewed retention exception. Current ad0de59d production remains protected. No deletion authorized by this script.'}
for old, new in replacements.items():
    assert old in script
    script = script.replace(old, new)
archive_script = folder / 'archive_previous_production.py'
archive_script.write_text(script, encoding='utf-8')
subprocess.run([str(root / 'backend/.venv/Scripts/python.exe'), str(archive_script)], check=True)
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
container_ids = subprocess.check_output([docker, 'ps', '-aq', '--no-trunc'], text=True).split()
containers = json.loads(subprocess.check_output([docker, 'inspect', *container_ids], text=True)) if container_ids else []
identity = replacements['sha256:3048f5cf236bb6e9ba6439249ed4f5e2fc4d2bc9c032b8ebb3367b3123103cba']
inventory = [{'name': row['Name'].lstrip('/'), 'container_id': row['Id'], 'image_id': row['Image']} for row in containers]
assert not any(row['image_id'] == identity for row in inventory)
running = next(row['image_id'] for row in inventory if row['name'] == 'NetworkIS')
assert running == 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da'
receipt = root / 'backend/test-output/release-gates/delivery-6b4cf647fec0/7473a63fa289/receipt.json'
assert json.loads(receipt.read_text())['status'] == 'PASS'
archive_proof = folder / 'previous-production-archive.json'
review = {'status': 'WAITING_FOR_USER_RETENTION_EXCEPTION', 'image_id': identity,
          'tag': replacements['networkis:candidate-fc5d3079141e'], 'delete_count': 1,
          'reason': '100 immutable NIS images prevent building a changed application. The previous production image is younger than seven days and protected by the regular retention policy.',
          'archive': json.loads(archive_proof.read_text()), 'complete_container_inventory': inventory,
          'protected_current_production': running, 'previous_pass_receipt': str(receipt),
          'previous_pass_receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
          'proposal': 'After explicit user approval, refresh inventory and archive hashes, remove only this exact unused immutable image without force, then build and fully test the new candidate. Retain archive and all receipts.',
          'deleted': False}
(folder / 'storage-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
print(json.dumps({'review': str(folder / 'storage-review.json'), 'archive_verified': True, 'deleted': False}))
