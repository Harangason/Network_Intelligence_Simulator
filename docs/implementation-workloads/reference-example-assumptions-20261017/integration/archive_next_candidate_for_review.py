"""Recoverable archive only; this script contains no image removal operation."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REVIEW = OUT.parent / 'archive-review-66a892b0b219'
REVIEW.mkdir(exist_ok=True)
source = OUT.parent.parent / 'document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('existing_archive_owner', source)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.OUT = REVIEW
owner.TAG = 'networkis:candidate-66a892b0b219'
owner.IMAGE = 'sha256:b5031a7ec0dbbafe2c178d468aa15534260dadba5c27547806246ee35a9dbc99'
owner.ARCHIVE = ROOT / 'work/archived-candidates/reference-example-assumptions-20261017/candidate-66a892b0b219.tar'

# Do not classify unreadable receipts as evidence of an unused failed image.
errors = []
receipt_count = 0
for directory in (ROOT / 'backend/test-output', ROOT / 'work'):
    for path in directory.rglob('receipt.json'):
        receipt_count += 1
        try:
            json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as error:
            errors.append({'path': str(path), 'error': str(error)})
assert not errors, errors
live = owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert live == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
owner.prepare()
record = {'status': 'ARCHIVE_ONLY', 'removals': 0, 'at_utc': datetime.now(timezone.utc).isoformat(),
          'image_budget': len(set(owner.call('image', 'ls', '--no-trunc', '--format', '{{.ID}}', 'networkis').split())),
          'all_receipts_readable': True, 'receipt_count': receipt_count, 'production_unchanged': owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == live,
          'owner_script': {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
          'removal_authorized': False, 'reason': 'Mixed PREPARED/FAIL status is outside standing pure-FAIL cleanup authorization.'}
(REVIEW / 'archive-only-result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
