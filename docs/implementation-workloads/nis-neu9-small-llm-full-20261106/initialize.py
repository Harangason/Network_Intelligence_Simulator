"""Create only normal isolated project metadata and byte-bound native-driver state."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from uuid import uuid4

goal = Path(__file__).resolve().parent
root = goal.parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--receipt',type=Path)
parser.add_argument('--output',type=Path)
parser.add_argument('--model',choices=['llama3.1:8b','qwen3.5:9b'],default='llama3.1:8b')
args=parser.parse_args()
model_authorization = None
if args.model == 'qwen3.5:9b':
    authorization = goal/'human-small-model-decision-20261107.json'
    decision = json.loads(authorization.read_text(encoding='utf8'))
    assert decision['verified_directly'] is True and args.model in decision['human_message']
    model_authorization = {'path': str(authorization), 'sha256': hashlib.sha256(authorization.read_bytes()).hexdigest()}
out = args.output.resolve() if args.output else goal
assert out.is_relative_to(goal)
receipt_path = args.receipt.resolve() if args.receipt else root / 'backend/test-output/release-gates/neu9-small-native-20261106/bbed983bcf0e/receipt.json'
assert receipt_path.is_relative_to(root/'backend/test-output/release-gates')
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
work = json.loads((goal / 'workload.json').read_text(encoding='utf-8'))
expected_source = work['frozen_source']['source_sha256'] if args.receipt else work['current_source']
assert receipt['status'] == 'PREPARED' and receipt['initial_source_sha256'] == expected_source
if args.receipt:
    for name,digest in work['frozen_files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest
source = Path(work['source']['path'])
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == work['source']['sha256']
assert len(raw) == work['source']['bytes'] and len(raw.decode('utf-8')) == work['source']['characters']
assert not (out / 'state.json').exists()
out.mkdir(parents=True,exist_ok=True)
project = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S') + ('%03d' % (datetime.now(timezone.utc).microsecond // 1000)) + '-' + uuid4().hex[:8]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
payload = {'engineering_wizard_settings': {'project_name': 'neu 9.txt – vollständige kleine LLM-Prüfung', 'model_type': 'custom'}}
req = urllib.request.Request(receipt['base_url'] + '/api/engineering/workflow/context?view=summary',
      data=json.dumps(payload).encode(), method='PATCH', headers={'Content-Type':'application/json','X-Project-ID':project})
(out / 'project-metadata-request.json').write_text(json.dumps({'project_id':project,'payload':payload},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with opener.open(req, timeout=30) as response:
    body = response.read()
    assert response.status == 200
(out / 'project-metadata-response.json').write_bytes(body)
answer = goal / 'lin-count-human-answer.txt'
state = {'source':str(source), 'original_sha256':hashlib.sha256(raw).hexdigest(), 'original_chars':len(raw.decode('utf-8')),
         'project_id':project, 'base_url':receipt['base_url'], 'image_id':receipt['image_id'], 'image_tag':receipt['image_tag'],
         'source_sha256':receipt['release']['source_sha256'], 'candidate_status':'PREPARED', 'status':'READY_FOR_NATIVE_INTAKE',
         'receipt':str(receipt_path), 'containers':receipt['containers'],
         'expected_model':args.model, 'model_authorization':model_authorization,
         'reference_sources':[{'path':str(answer), 'source_sha256':hashlib.sha256(answer.read_bytes()).hexdigest(),
                               'role':'USER_CLARIFICATION', 'allowed_fields':['quantity']}],
         'scope':'New complete real small-model neu9 request. Isolated current normal product image; no imported/generated model, synthetic profile or source reduction.'}
(out / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'status':state['status'],'project_id':project,'base_url':receipt['base_url'],'source_sha256':state['original_sha256'],'source_chars':state['original_chars']}))
