"""Delete exactly one archived failed image, only with fresh explicit human authorization."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
here=Path(__file__).resolve().parent
review_path=here/'failed-candidate-b3017a762dc0-storage-review.json'
review=json.loads(review_path.read_text(encoding='utf-8'))
tag='networkis:candidate-b3017a762dc0'
image='sha256:66df226713c920c8b4f26da98f3415b1c16482ee9f2883a024fb13222f69c90d'
production='sha256:3c3562900fc255344f65bdcf5c4cb2791685bd2532e220ff647c9ad48af48854'
permission=json.loads((here/'retention-authorization-b3017a762dc0.json').read_text(encoding='utf-8'))
assert permission['tag']==tag and permission['image_id']==image
assert permission['approved_in_current_task'] is True
assert permission['authorization']=='Genau dieses archivierte Image entfernen und Release fortsetzen'
assert review['tag']==tag and review['image_id']==image and review['deleted'] is False
assert review['immutable_index_verified'] and review['immutable_config_verified'] and review['all_layers_present']
assert review['verified_blob_count']>=3
with Path(review['archive']).open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest()==review['archive_sha256']
assert hashlib.sha256(Path(review['failed_receipt']).read_bytes()).hexdigest()==review['failed_receipt_sha256']
docker=review['requested_action'][0]
def command(*args):return subprocess.check_output([docker,*args],text=True,encoding='utf-8').strip()
assert command('image','inspect',tag,'--format','{{.Id}}')==image
assert command('inspect','NetworkIS','--format','{{.Image}}')==production
ids=command('ps','-aq','--no-trunc').split()
containers=json.loads(command('inspect',*ids)) if ids else []
assert not any(row['Image']==image for row in containers)
result=command('image','rm','--no-prune',tag)
assert command('inspect','NetworkIS','--format','{{.Image}}')==production
review.update(deleted=True,deleted_at=datetime.now(timezone.utc).isoformat(),deletion_result=result,
    fresh_container_images=[{'id':row['Id'],'image':row['Image']} for row in containers])
review_path.write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'AUTHORIZED_IMAGE_REMOVED','tag':tag,'protected_production':production}))
