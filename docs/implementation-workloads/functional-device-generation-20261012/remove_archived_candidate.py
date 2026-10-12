"""Remove one audited unused FAIL candidate under the recorded standing authorization."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
review_path=next(HERE.glob('failed-candidate-*-storage-review.json'))
review=json.loads(review_path.read_text())
assert 'Standing authorization for archived failed-candidate cleanup' in (ROOT/'AGENTS.md').read_text()
assert review['deleted'] is False
assert review['immutable_index_verified'] and review['immutable_config_verified'] and review['all_layers_present']
with Path(review['archive']).open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest()==review['archive_sha256']
assert hashlib.sha256(Path(review['failed_receipt']).read_bytes()).hexdigest()==review['failed_receipt_sha256']
image=review['image_id'];tag=review['tag']
matching=[]
for folder in ('backend/test-output/release-gates', 'docs/implementation-workloads', 'work'):
 for p in (ROOT/folder).rglob('receipt.json'):
    r=json.loads(p.read_text(encoding='utf-8-sig'))
    if r.get('image_id')==image: matching.append({'path':str(p),'status':r['status']})
assert matching and all(r['status']=='FAIL' for r in matching)
docker=review['requested_action'][0]
def command(*args):return subprocess.check_output([docker,*args],text=True,encoding='utf-8').strip()
assert command('image','inspect',tag,'--format','{{.Id}}')==image
assert command('inspect','NetworkIS','--format','{{.Image}}')==review['protected_running_image']
protected_tags=['networkis:candidate-baff4e76f405','networkis:candidate-4bfc55bac818','networkis:candidate-bb493012fb1c','networkis:candidate-e0cc8540367f','networkis:candidate-e7cc98f3e6fb']
protected={t:command('image','inspect',t,'--format','{{.Id}}') for t in protected_tags}
assert image not in protected.values()
ids=command('ps','-aq','--no-trunc').split()
containers=json.loads(command('inspect',*ids)) if ids else []
assert not any(c['Image']==image for c in containers)
result=command('image','rm','--no-prune',tag)
assert command('inspect','NetworkIS','--format','{{.Image}}')==review['protected_running_image']
review.update(deleted=True,deleted_at=datetime.now(timezone.utc).isoformat(),deletion_result=result,
 authorization='Standing user authorization recorded in canonical AGENTS.md; no repeated question',
 receipt_statuses=matching,protected_images=protected,fresh_container_images=[{'id':c['Id'],'image':c['Image']} for c in containers])
review_path.write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'AUTHORIZED_IMAGE_REMOVED','tag':tag,'image':image}))
