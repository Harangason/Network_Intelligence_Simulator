"""Recoverable archive of one superseded, never-started build; NEVER removes an image."""
import hashlib,importlib.util,json,shutil,subprocess,time
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent/'archive-review-53fc717a9d44';OUT.mkdir(exist_ok=False)
SOURCE=ROOT/'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec=importlib.util.spec_from_file_location('existing_archive_verifier',SOURCE);owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
owner.OUT=OUT;owner.TAG='networkis:candidate-53fc717a9d44';owner.IMAGE='sha256:eaf2f531cd0253427fdde28138d083f74c648a5cc889d0d8148c5ee7a724c753';owner.ARCHIVE=ROOT/'work/archived-candidates/reference-example-assumptions-20261017/candidate-53fc717a9d44.tar'
BUILD=Path(__file__).resolve().parent.parent/'functional-hardware-stage-scope-repair/normal-image-build/build.json';build=json.loads(BUILD.read_text(encoding='utf8'));assert build['image_id']==owner.IMAGE and build['no_app_started']
def archive_only_inventory():
 ids=owner.call('ps','-aq','--no-trunc').split();rows=json.loads(owner.call('inspect',*ids)) if ids else [];assert all(c['Image']!=owner.IMAGE for c in rows)
 image=json.loads(owner.call('image','inspect',owner.TAG))[0];assert image['Id']==owner.IMAGE and image['RepoTags']==[owner.TAG]
 matches=[]
 for parent in [ROOT/'backend/test-output',ROOT/'work']:
  for p in parent.rglob('receipt.json'):
   data=json.loads(p.read_text(encoding='utf-8-sig'))
   if data.get('image_id')==owner.IMAGE:matches.append({'path':str(p),'status':data.get('status')})
 assert not matches,'Unexpected receipt; reevaluate exact status before continuing archive.'
 production=owner.call('inspect','NetworkIS','--format','{{.Image}}');assert production!=owner.IMAGE
 return {'captured_epoch':time.time(),'production':production,'receipts':[],'release_status':'BUILT_UNVERIFIED_NO_GATE_RECEIPT','build_record':owner.ref(BUILD),'removal_authorized':False,'containers':[{'id':c['Id'],'name':c['Name'],'image':c['Image']} for c in rows]}
# Only the archive inventory is adapted for a receipt-less build. Its unknown/unverified
# release state remains protected; the recursive immutable/config/layer verifier is reused unchanged.
owner.inventory=archive_only_inventory
owner.prepare()
p=OUT/'archive-audit.json';audit=json.loads(p.read_text(encoding='utf8'));audit['authorization']='ARCHIVE_ONLY. BUILT_UNVERIFIED without FAIL/PREPARED/PASS receipt; exact removal still requires explicit human authorization under AGENTS.md.';audit['removal_authorized']=False;audit['archive_verifier_source']=owner.ref(SOURCE);audit['build_record']=owner.ref(BUILD);p.write_text(json.dumps(audit,indent=2)+'\n',encoding='utf8');shutil.copy2(BUILD,OUT/'archived-build-record.json');print(json.dumps({'status':'ARCHIVED_VERIFIED_PENDING_REMOVAL_AUTHORIZATION','verified_blobs':len(audit['verified_blobs']),'archive_bytes':audit['archive_bytes'],'release_status':audit['release_status'],'removals':0}),flush=True)
