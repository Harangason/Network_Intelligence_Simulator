"""Read-only NIS image/receipt inventory for the existing scoped FAIL authorization."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']


def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()


production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert production == 'sha256:eaab97030ad994dc8a00e8fc6f38ada67c38e915e316deda63d231902843537b'
rollback_receipt = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/first-release-pass-receipt.json'
rollback = json.loads(rollback_receipt.read_text(encoding='utf-8'))
assert rollback['status'] == 'PASS'
assert rollback['image_id'] == 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478'
ids = sorted(set(call('image', 'ls', '--no-trunc', '--format', '{{.ID}}', 'networkis').split()))
images = json.loads(call('image', 'inspect', *ids))
container_ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *container_ids)) if container_ids else []
used = {item['Image'] for item in containers}
receipts = []
errors = []
for parent in (ROOT / 'backend/test-output', ROOT / 'work'):
    for path in parent.rglob('receipt.json'):
        try:
            raw = path.read_bytes()
            receipt = json.loads(raw.decode('utf-8-sig'))
            receipts.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                             'status': receipt.get('status'), 'image_id': receipt.get('image_id')})
        except (OSError, ValueError, TypeError) as error:
            errors.append({'path': str(path), 'error': str(error)})
rows = []
for image in images:
    matches = [item for item in receipts if item['image_id'] == image['Id']]
    tags = image.get('RepoTags') or []
    reasons = []
    if image['Id'] == production:
        reasons.append('PRODUCTION')
    if image['Id'] == rollback['image_id']:
        reasons.append('VERIFIED_ROLLBACK_PASS')
    if image['Id'] in used:
        reasons.append('RUNNING_OR_STOPPED_CONTAINER_REFERENCE')
    if not matches or {item['status'] for item in matches} != {'FAIL'}:
        reasons.append('NOT_EXCLUSIVELY_KNOWN_FAIL_RECEIPTS')
    if len(tags) != 1 or not tags[0].startswith('networkis:candidate-'):
        reasons.append('NOT_SINGLE_EXACT_CANDIDATE_TAG')
    if errors:
        reasons.append('RECEIPT_INVENTORY_READ_ERROR')
    rows.append({'image_id': image['Id'], 'tags': tags, 'created': image['Created'],
                 'receipts': matches, 'protected_reasons': reasons,
                 'eligible_for_archive_review_only': not reasons})
rows.sort(key=lambda item: item['created'])
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'READ_ONLY_INVENTORY',
          'production': production, 'rollback': rollback['image_id'], 'image_count': len(ids),
          'receipt_count': len(receipts), 'receipt_errors': errors,
          'containers': [{'id': item['Id'], 'name': item['Name'], 'image_id': item['Image']} for item in containers],
          'images': rows, 'removals': 0,
          'scope': 'Archive-review candidates only. Removal still requires a complete verified recoverable archive and fresh all-container/tag/receipt checks under AGENTS.md.'}
(OUT / 'candidate-inventory.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
eligible = [item for item in rows if item['eligible_for_archive_review_only']]
print(json.dumps({'image_count': len(ids), 'receipt_errors': errors, 'eligible_count': len(eligible),
                  'eligible': [{'image_id': item['image_id'], 'tags': item['tags'],
                                'receipts': item['receipts']} for item in eligible[:4]]}))
