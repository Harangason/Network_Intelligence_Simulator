"""Prepare one unused mixed FAIL/PREPARED candidate; never remove it."""
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
inventory = json.loads((OUT / 'candidate-inventory.json').read_text(encoding='utf-8'))
tag = 'networkis:candidate-48a0fca755d0'
image = 'sha256:2c985cd09254dfd705c2564552f6b174d49e2530bf25fa93b386813e44861d23'
candidate = next(row for row in inventory['images'] if row['tags'] == [tag])
assert candidate['image_id'] == image
assert not inventory['receipt_errors']
assert candidate['protected_reasons'] == ['NOT_EXCLUSIVELY_KNOWN_FAIL_RECEIPTS']
assert {row['status'] for row in candidate['receipts']} == {'FAIL', 'PREPARED'}
path = OUT.parent / 'document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('existing_recoverable_archive_verifier', path)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
archive.OUT = OUT / 'archive-review-48a0fca755d0'
archive.OUT.mkdir(exist_ok=False)
archive.TAG = tag
archive.IMAGE = image
archive.ARCHIVE = ROOT / 'work/archived-candidates/document-function-owner-cross-reference-20261017/candidate-48a0fca755d0.tar'
archive.prepare()
