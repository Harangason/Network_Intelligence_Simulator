"""Archive one unused mixed PREPARED/FAIL candidate for review; never remove it."""
import hashlib,json,shutil,subprocess,sys,tarfile,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[2]
DOCKER=json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
TAG='networkis:candidate-e4af20244aaf'
IMAGE='sha256:a3d3a49496842b1186d6691af7bd75931d13dd2973454d45907b32bbb1e6efa0'
ARCHIVE=ROOT/'work/archived-candidates/document-clarification-repair-20261016/candidate-e4af20244aaf.tar'
def call(*a):return subprocess.check_output([DOCKER,*a],text=True,encoding='utf-8').strip()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
def inventory():
 ids=call('ps','-aq','--no-trunc').split();rows=json.loads(call('inspect',*ids)) if ids else []
 assert all(c['Image']!=IMAGE for c in rows),'Container reference protects candidate'
 image=json.loads(call('image','inspect',TAG))[0]
 assert image['Id']==IMAGE and image['RepoTags']==[TAG],image.get('RepoTags')
 receipts=[]
 for parent in (ROOT/'backend/test-output',ROOT/'work'):
  for p in parent.rglob('receipt.json'):
   try:r=json.loads(p.read_text(encoding='utf-8-sig'))
   except (OSError,ValueError):continue
   if r.get('image_id')==IMAGE:
    assert r['status'] in {'FAIL','PREPARED'},str(p)
    receipts.append({**ref(p),'status':r['status']})
 assert receipts,'Unknown release status is protected'
 production=call('inspect','NetworkIS','--format','{{.Image}}');assert production!=IMAGE
 return {'captured_epoch':time.time(),'production':production,'receipts':receipts,'containers':[{'id':r['Id'],'name':r['Name'],'image':r['Image']} for r in rows]}
def prepare():
 ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
 observed=inventory();assert shutil.disk_usage(ARCHIVE.parent).free>20*1024**3
 if not ARCHIVE.exists():subprocess.run([DOCKER,'image','save','--output',str(ARCHIVE),TAG],check=True)
 verified=set()
 with tarfile.open(ARCHIVE) as tar:
  def verify(desc):
   digest=desc['digest'];assert digest.startswith('sha256:')
   if digest in verified:return
   member=tar.getmember('blobs/sha256/'+digest.split(':')[1]);assert member.isfile() and member.size==desc['size']
   with tar.extractfile(member) as stream:assert 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()==digest
   verified.add(digest)
   if desc.get('mediaType','').endswith(('index.v1+json','manifest.v1+json','manifest.v2+json','manifest.list.v2+json')):
    data=json.load(tar.extractfile(member))
    for child in data.get('manifests',[]):verify(child)
    if 'config' in data:verify(data['config'])
    for child in data.get('layers',[]):verify(child)
  index=json.load(tar.extractfile('index.json'));verify(next(d for d in index['manifests'] if d['digest']==IMAGE))
  manifest=json.load(tar.extractfile('manifest.json'));entry=next(e for e in manifest if TAG in e['RepoTags'])
  config=tar.extractfile(entry['Config']).read();config_hash=hashlib.sha256(config).hexdigest()
  assert entry['Config']=='blobs/sha256/'+config_hash and 'sha256:'+config_hash in verified
  assert all(tar.getmember(layer).isfile() and 'sha256:'+layer.split('/')[-1] in verified for layer in entry['Layers'])
 archive_ref=ref(ARCHIVE)
 for i,r in enumerate(observed['receipts']):shutil.copy2(r['path'],OUT/f'archived-receipt-{i}.json')
 audit={'status':'ARCHIVED_VERIFIED','tag':TAG,'image':IMAGE,'archive':archive_ref,'archive_bytes':ARCHIVE.stat().st_size,'verified_blobs':sorted(verified),'immutable_index_verified':True,'immutable_config_verified':True,'all_layers_verified':True,**observed,'authorization':'ARCHIVE_ONLY; candidate also has PREPARED receipts. Exact removal requires separate user authorization under AGENTS.md and release_storage.py.','restore_command':[DOCKER,'image','load','--input',str(ARCHIVE)]}
 (OUT/'archive-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps({'status':audit['status'],'archive':archive_ref,'verified_blobs':len(verified)}),flush=True)
if __name__=='__main__': prepare()
