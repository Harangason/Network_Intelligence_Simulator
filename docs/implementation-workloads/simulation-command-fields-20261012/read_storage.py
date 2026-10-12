"""Read-only inventory to identify an unused failed candidate; deletes nothing."""
import json,subprocess
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
docker=json.loads((root/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
def command(*args):return subprocess.check_output([docker,*args],text=True,encoding='utf-8').strip()
ids=command('image','ls','networkis','-q','--no-trunc').split()
images=json.loads(command('image','inspect',*sorted(set(ids))))
containers=command('ps','-aq','--no-trunc').split()
used={row['Image'] for row in json.loads(command('inspect',*containers))} if containers else set()
receipts=[]
for path in (root/'backend/test-output/release-gates').rglob('receipt.json'):
    try:
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        value['receipt_path']=str(path)
        receipts.append(value)
    except (ValueError,OSError):pass
failed=[]
for image in images:
    matching=[r for r in receipts if r.get('image_id')==image['Id']]
    if image['Id'] not in used and matching and all(r.get('status')=='FAIL' for r in matching):
        failed.append({'image_id':image['Id'],'tags':image['RepoTags'],'created':image['Created'],'receipt':matching[-1]['receipt_path']})
proof={'image_count':len(images),'production':command('inspect','NetworkIS','--format','{{.Image}}'),'container_image_ids':sorted(used),'unused_failed':sorted(failed,key=lambda row:row['created'],reverse=True)}
(here/'storage-inventory.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
