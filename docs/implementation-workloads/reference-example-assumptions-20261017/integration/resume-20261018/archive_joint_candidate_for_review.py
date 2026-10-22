"""Archive one unused historical failed candidate; no image removal operation."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/archive-review-43d202d1dbde'
OUT.mkdir(exist_ok=True)
SOURCE = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('canonical_archive_review_owner', SOURCE)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.OUT = OUT
owner.TAG = 'networkis:candidate-43d202d1dbde'
owner.IMAGE = 'sha256:8addd0edb77baf9daec17b3cae1c8c917e3e768d6e3d8508fb964ea6171c98e0'
owner.ARCHIVE = ROOT / 'work/archived-candidates/reference-example-assumptions-20261017/candidate-43d202d1dbde.tar'
for directory in (ROOT / 'backend/test-output', ROOT / 'work'):
    for receipt in directory.rglob('receipt.json'):
        json.loads(receipt.read_text(encoding='utf-8-sig'))
production = owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
owner.prepare()
record = {'status': 'ARCHIVE_ONLY', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'tag': owner.TAG, 'image_id': owner.IMAGE, 'removals': 0,
          'production_unchanged': owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == production,
          'archive_owner_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'removal_authorized': False,
          'reason': 'Mixed historical PREPARED/FAIL evidence lies outside pure-FAIL standing cleanup; retain archive and await exact human authorization.'}
(OUT / 'archive-only-result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record), flush=True)
