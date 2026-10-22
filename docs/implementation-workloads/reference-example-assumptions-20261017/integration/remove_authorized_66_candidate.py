"""Exactly scoped human-authorized cleanup after fresh complete archive checks."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REVIEW = OUT.parent / 'archive-review-66a892b0b219'
TAG = 'networkis:candidate-66a892b0b219'
IMAGE = 'sha256:b5031a7ec0dbbafe2c178d468aa15534260dadba5c27547806246ee35a9dbc99'
PRODUCTION = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
audit = json.loads((REVIEW/'archive-audit.json').read_text(encoding='utf-8'))
assert audit['image'] == IMAGE and audit['tag'] == TAG and len(audit['verified_blobs']) == 24
archive = Path(audit['archive']['path'])
assert archive.stat().st_size == audit['archive_bytes']
assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest() == audit['archive']['sha256']
owner_path = ROOT/'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('existing_archive_checks', owner_path)
owner = importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
owner.TAG, owner.IMAGE, owner.ARCHIVE = TAG, IMAGE, archive
owner.OUT = REVIEW/'fresh-review'
owner.OUT.mkdir(exist_ok=True)
assert owner.call('inspect','NetworkIS','--format','{{.Image}}') == PRODUCTION
receipt_count = 0
for parent in (ROOT/'backend/test-output', ROOT/'work'):
    for path in parent.rglob('receipt.json'):
        json.loads(path.read_text(encoding='utf-8-sig'))
        receipt_count += 1
owner.prepare()  # Revalidate the immutable index, config and every layer.
fresh_archive = json.loads((owner.OUT/'archive-audit.json').read_text(encoding='utf-8'))
assert fresh_archive['archive']['sha256'] == audit['archive']['sha256']
assert fresh_archive['verified_blobs'] == audit['verified_blobs']
fresh = owner.inventory()  # All running/stopped containers, exact sole tag, current receipts.
assert fresh['production'] == PRODUCTION
assert {item['status'] for item in fresh['receipts']} == {'FAIL','PREPARED'}
assert all(item['image'] != IMAGE for item in fresh['containers'])
assert owner.call('image','inspect',TAG,'--format','{{.Id}}') == IMAGE
authorization = {'question_item':'call_b703054758cb439d875e98442e4f28d3/0',
    'user_answer':'Genau dieses archivierte Image entfernen und fortsetzen',
    'scope':'Exactly this image only. No force, no prune, no production/rollback removal.',
    'recorded_at_utc':datetime.now(timezone.utc).isoformat()}
command = [owner.DOCKER,'image','rm','--no-prune',TAG]
record = {'authorization':authorization,'tag':TAG,'image_id':IMAGE,
    'archive':audit['archive'],'verified_blobs':len(fresh_archive['verified_blobs']),
    'fresh_inventory':fresh,'all_receipts_readable':True,'receipt_count':receipt_count,'command':command}
(REVIEW/'fresh-removal-audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',check=True)
assert owner.call('inspect','NetworkIS','--format','{{.Image}}') == PRODUCTION
assert subprocess.run([owner.DOCKER,'image','inspect',TAG],capture_output=True).returncode != 0
report = {'status':'REMOVED','tag':TAG,'image_id':IMAGE,'removed_count':1,
    'command':command,'exit_code':result.returncode,'output':result.stdout,
    'archive_retained':archive.is_file(),'production_unchanged':True,'authorization':authorization,
    'image_count_after':len(set(owner.call('image','ls','networkis','--no-trunc','--format','{{.ID}}').split()))}
(REVIEW/'removal-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
