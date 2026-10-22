"""Read-only inventory of potential archived-FAIL cleanup candidates; no removal."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']


def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()


containers = [json.loads(line) for line in call('ps', '-a', '--no-trunc', '--format', '{{json .}}').splitlines() if line]
container_ids = [row['ID'] for row in containers]
inspected = json.loads(call('inspect', *container_ids)) if container_ids else []
used = {row['Image'] for row in inspected}
production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
receipts = {}
errors = []
for directory in (ROOT / 'backend/test-output', ROOT / 'work'):
    for path in directory.rglob('receipt.json'):
        try:
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
            receipts.setdefault(receipt.get('image_id'), []).append({'path': str(path), 'status': receipt.get('status')})
        except (OSError, ValueError) as error:
            errors.append({'path': str(path), 'error': str(error)})
images = [json.loads(line) for line in call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{json .}}').splitlines() if line]
eligible_for_archive_review = []
mixed_for_explicit_review = []
for row in images:
    related = receipts.get(row['ID'], [])
    statuses = {receipt['status'] for receipt in related}
    if row['ID'] not in used and row['ID'] != production and statuses == {'FAIL'} and row['Tag'].startswith('candidate-'):
        eligible_for_archive_review.append({'image_id': row['ID'], 'tag': row['Repository'] + ':' + row['Tag'], 'created': row['CreatedAt'], 'receipts': related})
    elif row['ID'] not in used and row['ID'] != production and 'FAIL' in statuses and statuses <= {'FAIL', 'PREPARED'} and row['Tag'].startswith('candidate-'):
        mixed_for_explicit_review.append({'image_id': row['ID'], 'tag': row['Repository'] + ':' + row['Tag'], 'created': row['CreatedAt'], 'receipts': related})
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'READ_ONLY_PLAN',
          'image_count': len({row['ID'] for row in images}), 'production': production,
          'container_images': sorted(used), 'receipt_errors': errors,
          'eligible_for_archive_review': eligible_for_archive_review,
          'mixed_for_explicit_review': mixed_for_explicit_review,
          'removals': 0, 'authorization': 'Standing AGENTS pure-FAIL rule requires full recoverable archive verification and fresh usage/tag checks before any exact removal.'}
(OUT / 'failed-candidate-inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'image_count': result['image_count'], 'receipt_errors': errors, 'archive_review_candidates': [{k: row[k] for k in ('tag', 'image_id', 'created')} for row in eligible_for_archive_review], 'mixed_candidates': [{k: row[k] for k in ('tag', 'image_id', 'created')} for row in mixed_for_explicit_review]}), flush=True)
assert not errors, 'Unreadable receipt protects storage inventory'
