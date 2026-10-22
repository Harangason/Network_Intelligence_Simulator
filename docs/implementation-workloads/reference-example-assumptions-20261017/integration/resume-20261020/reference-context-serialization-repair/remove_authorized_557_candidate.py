"""Freshly verify and remove exactly the human-authorized unused archived image."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'archive-review-55794a287afa'
TAG = 'networkis:candidate-55794a287afa'
IMAGE = 'sha256:dec19679fed8d27cdea1d921dd0a1ceda880404fe9fc4cfa7326493e4db4a12e'
PRODUCTION = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
assert not (OUT / 'authorized-removal.json').exists(), 'Inspect prior completed removal; do not repeat.'
old = json.loads((OUT / 'archive-audit.json').read_text())
assert old['tag'] == TAG and old['image'] == IMAGE
assert len(old['verified_blobs']) == 26 and {r['status'] for r in old['receipts']} == {'PREPARED'}
source = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('nis_exact_archive_recheck', source)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.ROOT, owner.OUT, owner.TAG, owner.IMAGE = ROOT, OUT, TAG, IMAGE
owner.ARCHIVE = Path(old['archive']['path'])
assert owner.ref(owner.ARCHIVE)['sha256'] == old['archive']['sha256']
# The existing verifier rechecks all manifest/configuration/layer hashes and
# fresh complete container references; it never removes an image itself.
owner.prepare()
audit = json.loads((OUT / 'archive-audit.json').read_text())
assert audit['archive'] == old['archive'] and audit['verified_blobs'] == old['verified_blobs']
assert {r['status'] for r in audit['receipts']} == {'PREPARED'}
assert owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
rollback = 'networkis:candidate-c557b3914eac'
rollback_id = owner.call('image', 'inspect', rollback, '--format', '{{.Id}}')
assert rollback_id == 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478'
authorization = {'question_id': 'call_c616eb5ba92b4c2f88b6bf805757ffc9',
    'answer': 'Genau dieses archivierte Image entfernen und fortsetzen',
    'scope': TAG, 'container_removal_authorized_or_performed': False}
(OUT / 'human-authorized-removal-precheck.json').write_text(json.dumps({
    'at_utc': datetime.now(timezone.utc).isoformat(), 'authorization': authorization,
    'fresh_archive_audit': owner.ref(OUT / 'archive-audit.json'),
    'production': PRODUCTION, 'rollback': rollback_id}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
fresh = owner.inventory()
assert fresh['production'] == PRODUCTION
subprocess.run([owner.DOCKER, 'image', 'rm', '--no-prune', TAG], check=True)
assert owner.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
assert owner.call('image', 'inspect', rollback, '--format', '{{.Id}}') == rollback_id
remaining = set(owner.call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split())
assert IMAGE not in remaining
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'EXACT_AUTHORIZED_IMAGE_REMOVED',
    'authorization': authorization, 'image': IMAGE, 'tag': TAG, 'archive_retained': old['archive'],
    'all26_archive_components_freshly_verified': True, 'fresh_all_container_references_empty': True,
    'production_unchanged': True, 'rollback_unchanged': True, 'remaining_nis_images': len(remaining),
    'image_removal_flags': ['--no-prune'], 'force_bulk_pruning_or_other_removal': False}
(OUT / 'authorized-removal.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record), flush=True)
