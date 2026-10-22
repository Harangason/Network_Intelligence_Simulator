"""Remove only the previously reviewed candidate after the user's finish instruction."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
REVIEW = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/archive-review-43d202d1dbde'
TAG = 'networkis:candidate-43d202d1dbde'
IMAGE = 'sha256:8addd0edb77baf9daec17b3cae1c8c917e3e768d6e3d8508fb964ea6171c98e0'
PRODUCTION = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
audit = json.loads((REVIEW / 'archive-audit.json').read_text())
assert audit['tag'] == TAG and audit['image'] == IMAGE and len(audit['verified_blobs']) == 23
archive = Path(audit['archive']['path'])
assert archive.stat().st_size == audit['archive_bytes']
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == audit['archive']['sha256']
source = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('audited_archive_owner', source)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.TAG, owner.IMAGE, owner.ARCHIVE = TAG, IMAGE, archive
owner.OUT = REVIEW / 'fresh-review'
owner.OUT.mkdir(exist_ok=True)
assert owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
receipt_count = 0
for parent in (ROOT / 'backend/test-output', ROOT / 'work'):
    for path in parent.rglob('receipt.json'):
        json.loads(path.read_text(encoding='utf-8-sig'))
        receipt_count += 1
owner.prepare()
fresh_archive = json.loads((owner.OUT / 'archive-audit.json').read_text())
assert fresh_archive['archive']['sha256'] == audit['archive']['sha256']
assert fresh_archive['verified_blobs'] == audit['verified_blobs']
fresh = owner.inventory()
assert fresh['production'] == PRODUCTION
assert {row['status'] for row in fresh['receipts']} == {'FAIL', 'PREPARED'}
assert all(row['image'] != IMAGE for row in fresh['containers'])
assert owner.call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
authorization = {'verbatim_user_instruction': 'Stelle die arbeiten fertig',
    'source': 'Direct human follow-up in this chat after the final answer named precisely this image and the pending removal as the blocker.',
    'interpretation': 'Contextual authorization to carry out the concretely reviewed necessary step; restricted to this exact recoverably archived image.',
    'scope': 'No force, no pruning, no other image, production and rollback protected.',
    'at_utc': datetime.now(timezone.utc).isoformat()}
command = [owner.DOCKER, 'image', 'rm', '--no-prune', TAG]
record = {'authorization': authorization, 'tag': TAG, 'image_id': IMAGE,
          'archive': audit['archive'], 'verified_blobs': 23, 'fresh_inventory': fresh,
          'all_receipts_readable': True, 'receipt_count': receipt_count, 'command': command}
(REVIEW / 'fresh-removal-audit.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
assert owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
assert subprocess.run([owner.DOCKER, 'image', 'inspect', TAG], capture_output=True).returncode != 0
report = {'status': 'REMOVED', 'tag': TAG, 'image_id': IMAGE, 'removed_count': 1,
          'command': command, 'exit_code': result.returncode, 'output': result.stdout,
          'archive_retained': archive.is_file(), 'production_unchanged': True, 'authorization': authorization,
          'image_count_after': len(set(owner.call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split()))}
(REVIEW / 'removal-result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report), flush=True)
