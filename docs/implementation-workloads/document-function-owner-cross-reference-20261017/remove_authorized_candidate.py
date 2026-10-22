"""Remove the one archived mixed-status image explicitly authorized by the user."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
TAG = 'networkis:candidate-48a0fca755d0'
IMAGE = 'sha256:2c985cd09254dfd705c2564552f6b174d49e2530bf25fa93b386813e44861d23'
authorization = {
    'tag': TAG, 'image_id': IMAGE,
    'user_request': 'Genau dieses archivierte Image entfernen und Release fortsetzen',
    'question_item': 'call_2667aef133ac4670b0d400a4da2d5b3a/0',
    'scope': 'One exact archived image only, no force or pruning; new release still needs its own complete PASS.',
    'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
}
plan = json.loads((OUT / 'removal-plan.json').read_text(encoding='utf-8'))
assert plan['tag'] == TAG and plan['image_id'] == IMAGE
audit_path = Path(plan['archive_audit']['path'])
assert hashlib.file_digest(audit_path.open('rb'), 'sha256').hexdigest() == plan['archive_audit']['sha256']
audit = json.loads(audit_path.read_text(encoding='utf-8'))
assert audit['status'] == 'ARCHIVED_VERIFIED' and audit['tag'] == TAG and audit['image'] == IMAGE
assert len(audit['verified_blobs']) == 24
assert audit['immutable_index_verified'] and audit['immutable_config_verified'] and audit['all_layers_verified']
archive_path = Path(audit['archive']['path'])
assert archive_path.stat().st_size == audit['archive_bytes']
assert hashlib.file_digest(archive_path.open('rb'), 'sha256').hexdigest() == audit['archive']['sha256']

# Reuse the complete read-only inventory. Its output never removes anything.
subprocess.run([__import__('sys').executable, str(OUT / 'inventory_failed_candidates.py')], check=True)
inventory = json.loads((OUT / 'candidate-inventory.json').read_text(encoding='utf-8'))
assert not inventory['receipt_errors']
row = next(item for item in inventory['images'] if item['image_id'] == IMAGE)
assert row['tags'] == [TAG]
assert row['protected_reasons'] == ['NOT_EXCLUSIVELY_KNOWN_FAIL_RECEIPTS']
assert {item['status'] for item in row['receipts']} == {'FAIL', 'PREPARED'}
assert IMAGE not in {inventory['production'], inventory['rollback']}
assert not any(item['image_id'] == IMAGE for item in inventory['containers'])

spec = importlib.util.spec_from_file_location('existing_archive_checks', OUT.parent / 'document-clarification-repair-20261016/archive_for_review.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
checks.TAG = TAG
checks.IMAGE = IMAGE
fresh = checks.inventory()  # Fresh all-container, exact tag and receipt checks immediately before removal.
assert fresh['production'] == plan['protected_production'] == inventory['production']
assert checks.call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
command = [checks.DOCKER, 'image', 'rm', '--no-prune', TAG]
record = {**authorization, 'archive': audit['archive'], 'command': command,
          'fresh_inventory': fresh, 'protected_rollback': inventory['rollback']}
(OUT / 'fresh-removal-audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
assert checks.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == fresh['production']
assert subprocess.run([checks.DOCKER, 'image', 'inspect', TAG], capture_output=True).returncode != 0
report = {'status': 'REMOVED', 'tag': TAG, 'image_id': IMAGE, 'removed_count': 1,
          'command': command, 'exit_code': result.returncode, 'output': result.stdout,
          'archive_retained': archive_path.is_file(), 'production_unchanged': True,
          'authorization': authorization}
(OUT / 'removal-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False), flush=True)
