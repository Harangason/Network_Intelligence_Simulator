"""Read-only inventory for the one necessary next candidate slot."""
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']

def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()

ids = call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split()
images = json.loads(call('image', 'inspect', *sorted(set(ids))))
container_ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *container_ids)) if container_ids else []
used = {row['Image'] for row in containers}
production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
receipts = defaultdict(list)
for parent in [ROOT / 'backend/test-output', ROOT / 'work']:
    for path in parent.rglob('receipt.json'):
        raw = path.read_bytes()
        row = json.loads(raw.decode('utf-8-sig'))
        if row.get('image_id'):
            receipts[row['image_id']].append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'status': row.get('status')})
audits = defaultdict(list)
for path in (ROOT / 'docs/implementation-workloads').rglob('*audit.json'):
    try:
        row = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError):
        continue
    if isinstance(row, dict) and row.get('status') == 'ARCHIVED_VERIFIED' and row.get('archive') and row.get('image'):
        if Path(row['archive']['path']).is_file():
            audits[row['image']].append(str(path))
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Read-only inventory, no archive verification or removal permission inferred.',
          'production': production, 'image_count': len(images), 'container_count': len(containers),
          'container_image_ids': sorted(used), 'pure_fail_candidates': [], 'mixed_unused_candidates': []}
for image in images:
    related = receipts[image['Id']]
    states = {r['status'] for r in related}
    tags = image.get('RepoTags') or []
    if image['Id'] == production or image['Id'] in used or not related or len(tags) != 1 or not tags[0].startswith('networkis:candidate-'):
        continue
    row = {'tag': tags[0], 'image_id': image['Id'], 'created': image['Created'], 'states': sorted(states),
           'receipts': related, 'existing_archive_audits': audits[image['Id']]}
    if states == {'FAIL'}:
        result['pure_fail_candidates'].append(row)
    elif states <= {'FAIL', 'PREPARED'} and 'FAIL' in states:
        result['mixed_unused_candidates'].append(row)
(OUT / 'storage-inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'image_count': result['image_count'], 'pure_fail_candidates': result['pure_fail_candidates'],
                  'mixed_unused_count': len(result['mixed_unused_candidates'])}))
