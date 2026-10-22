"""Verify exact deployed image, module identities and read-only document API."""
import hashlib,http.cookiejar,json,subprocess,sys,time,urllib.request
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[2]
receipt_path=Path(sys.argv[1]);receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status']=='PASS'
native=json.loads((OUT/'native-large-document.json').read_text(encoding='utf-8'));assert native['status']=='PASSED'
DOCKER=json.loads((ROOT/'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
def call(*a):return subprocess.check_output([DOCKER,*a],text=True,encoding='utf-8').strip()
image=call('inspect','NetworkIS','--format','{{.Image}}');assert image==receipt['image_id']
code="import hashlib,json,sys; from pathlib import Path; from backend.nis.agent.orchestration.project_intake import document_segments, DOCUMENT_SOURCE_MAX_CHARS; paths=json.loads(sys.argv[1]); text='Prüfung der vollständigen Quelle.\\n'*3000; parts=document_segments(text); assert ''.join(p['text'] for p in parts)==text and len(parts)>8; print(json.dumps({'module_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},'source_max_chars':DOCUMENT_SOURCE_MAX_CHARS,'segments':len(parts),'source_complete':True}))"
modules=json.loads(call('exec','NetworkIS','python','-c',code,json.dumps(list(native['module_hashes']))))
assert modules['module_hashes']==native['module_hashes'] and modules['source_max_chars']==1000000
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
base='http://127.0.0.1:13500'
ready=json.load(opener.open(base+'/api/ready',timeout=15));build=json.load(opener.open(base+'/api/build-info',timeout=15))
assert ready['status']=='ready' and build['source_sha256']==receipt['release']['source_sha256']
session=json.load(opener.open(base+'/api/engineering/agent/review-session',timeout=15))
source='Controller (NISPROBE)\nAnschluss: UART\n'
payload={'source':source,'source_name':'Read-only production delivery verification','source_request_id':'delivery-document-20261016'}
request=urllib.request.Request(base+'/api/engineering/agent/document-intake',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/x-ndjson','X-Human-Review':'confirmed','X-Review-CSRF':session['csrf_token'],'X-Project-ID':'20261016084924562-131ed051'})
events=[];started=time.monotonic()
with opener.open(request,timeout=1200) as response:
 assert response.status==200
 for line in response:
  if line.strip():
   event=json.loads(line);events.append(event)
   if event.get('type')!='HEARTBEAT':print(json.dumps(event,ensure_ascii=True),flush=True)
result=events[-1]['result'];assert result['success'],result
proposal=result['data'];assert proposal['source_complete'] and proposal['canonical_writes'] is False and proposal['approval_required']
assert proposal['source_sha256']==hashlib.sha256(source.encode()).hexdigest()
assert proposal['source_request_id']==payload['source_request_id']
assert call('inspect','NetworkIS','--format','{{.Image}}')==image
report={'status':'PASSED','image_id':image,'source_sha256':build['source_sha256'],'ready':ready,'build':build,'module_verification':modules,'seconds':time.monotonic()-started,'events':events,'canonical_writes':False,'native_full_source_evidence':{'path':str((OUT/'native-large-document.json').resolve()),'sha256':hashlib.sha256((OUT/'native-large-document.json').read_bytes()).hexdigest()}}
(OUT/'production-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASSED','image':image,'canonical_writes':False}),flush=True)
