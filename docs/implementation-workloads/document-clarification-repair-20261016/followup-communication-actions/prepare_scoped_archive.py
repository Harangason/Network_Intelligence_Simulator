"""Reuse the existing archive verifier for one unused mixed-status image; no removal."""
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TAG = 'networkis:candidate-07cb57d47f91'
IMAGE = 'sha256:546b52bb93489ee991a7ba69f268cda1c082c3c26510c1b6da74bb1f26942698'
inventory = json.loads((OUT / 'candidate-inventory.json').read_text(encoding='utf-8'))
assert not inventory['receipt_errors']
row = next(item for item in inventory['images'] if item['image_id'] == IMAGE)
assert row['tags'] == [TAG]
assert row['protected_reasons'] == ['NOT_EXCLUSIVELY_KNOWN_FAIL_RECEIPTS']
assert {item['status'] for item in row['receipts']} == {'FAIL', 'PREPARED'}
assert IMAGE not in {inventory['production'], inventory['rollback']}

path = OUT.parent / 'archive_for_review.py'
spec = importlib.util.spec_from_file_location('existing_candidate_archive_verifier', path)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
archive.OUT = OUT / 'archive-review-07cb57d47f91'
archive.OUT.mkdir(exist_ok=False)
archive.TAG = TAG
archive.IMAGE = IMAGE
archive.ARCHIVE = ROOT / 'work/archived-candidates/document-clarification-repair-followup-20261017/candidate-07cb57d47f91.tar'
archive.prepare()
