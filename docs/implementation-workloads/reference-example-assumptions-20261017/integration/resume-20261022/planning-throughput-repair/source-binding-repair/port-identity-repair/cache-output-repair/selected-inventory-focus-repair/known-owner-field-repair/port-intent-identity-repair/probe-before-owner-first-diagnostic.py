"""One authored native port-intent decoder counterprobe; no project writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent / 'native-grammar'
OUT.mkdir(exist_ok=False)
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage, _reference_context_window
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference
from jsonschema import Draft202012Validator

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def get(url, payload=None, headers=None):
    raw = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    with urlopen(Request(url, data=raw, headers={'Content-Type':'application/json', **(headers or {})}), timeout=1200) as response:
        return json.load(response)

source = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
write('waiting.json', {'pid':os.getpid(), 'at_utc':datetime.now(timezone.utc).isoformat(),
                      'source_sha256':source_hash, 'actual_model_requests':0})
print(json.dumps({'status':'WAITING_FOR_EXACT_PROCESS_GUARD','pid':os.getpid()}), flush=True)
deadline = time.monotonic() + 120
while not (OUT / 'go.json').exists():
    assert time.monotonic() < deadline, 'No actual process-bound guard GO received; no inference sent.'
    time.sleep(0.5)
go = json.loads((OUT / 'go.json').read_text())
assert go['pid'] == os.getpid() and go['source_sha256'] == source_hash
command = "$mainId=@(Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique);if($mainId.Count -ne 1){throw 'Ambiguous main provider'};[ordered]@{main_owner=$mainId[0];workers=@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq $mainId[0] -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine)} | ConvertTo-Json -Depth 5 -Compress"
provider = json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True))
for worker in provider['workers']:
    port = re.search(r'--port\s+(\d+)', worker['CommandLine']).group(1)
    worker['slots'] = get('http://127.0.0.1:' + port + '/slots')
    assert all(not row['is_processing'] for row in worker['slots']), 'Actual model request active; do not compete.'
product = {}
for project in ('20261021094952722-147a3d72','20261020103707202-0fda8601'):
    headers={'X-Project-ID':project}
    product[project] = {name:get('http://127.0.0.1:13500' + endpoint,headers=headers)
                       for name,endpoint in (('draft','/api/engineering/agent/project-draft'),
                                             ('conversation','/api/engineering/agent/conversation'))}
    conversation = product[project]['conversation'].get('data') or {}
    assert conversation.get('active_workload') is None and conversation.get('active_proposal') is None
info = get('http://127.0.0.1:11434/api/show',{'model':'qwen3.8:27b'})
assert str(info['details']['family']).startswith('qwen') and not info.get('remote_host') and not info.get('remote_model')
write('preflight.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'provider':provider,'product':product,
                        'main_ps':get('http://127.0.0.1:11434/api/ps'),'qwen_details':info['details'],
                        'product_observation_is_not_global_queue_enumeration':True})
prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
first = _reference_schema_for_stage(prepared, {'ports'}, port_intent=True, device_ids=('owner-a','owner-b'))
variant = first['$defs']['ReferencePort']['anyOf'][0]
used = variant['properties']['id']['pattern'][1:].split('[',1)[0] + '01'
known = [{'id':used}, {'id':'port-idc-eth-01'}]
schema = _reference_schema_for_stage(prepared, {'ports'}, port_intent=True,
                                    device_ids=('owner-a','owner-b'), existing_ports=known)
messages = [{'role':'user','content':'Authored native JSON grammar counterprobe, no project writes. '
    'Return exactly two new CAN LOCAL port intents: one for owner-a and one for owner-b. '
    'Use network_scope authored-network, parameters {}, one short rationale each, empty field_references. '
    'All other model arrays empty. These IDs already exist and must never be reused: '
    + json.dumps([row['id'] for row in known]) + '. Choose fresh IDs permitted by the schema. /no_think'}]
payload = {'model':'qwen3.8:27b','messages':messages,'format':schema,'think':False,'stream':False,
           'keep_alive':'10m','options':{'temperature':0,'num_predict':8192,
                                        'num_ctx':_reference_context_window(messages,131072)}}
write('request.json',payload)
write('started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'actual_model_requests':1})
response=get('http://127.0.0.1:11434/api/chat',payload)
write('response.json',response)
assert response.get('done_reason') != 'length'
value=json.loads(response['message']['content'])
Draft202012Validator(schema).validate(value)
Draft202012Validator(intake.reference_design_schema(prepared)).validate(value)
assert len(value['ports'])==2 and {row['device_id'] for row in value['ports']}=={'owner-a','owner-b'}
ids=[row['id'] for row in value['ports']]
assert len(set(ids))==2 and not set(ids)&{row['id'] for row in known}
assert all(not row['parameters'] for row in value['ports'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
result={'status':'PASSED','at_utc':datetime.now(timezone.utc).isoformat(),'actual_model_requests':1,
        'schema_and_public_contract_valid':True,'fresh_unique_owner_bound_port_ids':ids,
        'source_sha256':source_hash,'eval_count':response.get('eval_count'),'canonical_writes':False,
        'original_model_acceptance':False,'provider_model_context_output_timeout_unchanged':True}
write('result.json',result)
print(json.dumps(result),flush=True)
