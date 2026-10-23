"""One authored native port-intent decoder counterprobe; no project writes."""
import argparse
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
parser = argparse.ArgumentParser()
parser.add_argument('--attempt', default='native-grammar')
parser.add_argument('--owner-first-diagnostic', action='store_true')
parser.add_argument('--repeat-original-prompt', action='store_true')
args=parser.parse_args()
assert args.attempt.replace('-', '').isalnum()
OUT = Path(__file__).resolve().parent / args.attempt
OUT.mkdir(exist_ok=False)
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage, _reference_context_window, _reference_expand_port_intents
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
owners=('owner-a','owner-b')
schema = _reference_schema_for_stage(prepared, {'ports'}, port_intent=True, device_ids=owners)
known=[{'id':'port-'+hashlib.sha256(b'owner-a').hexdigest()[:24]+'-1','device_id':'earlier-owner'},
       {'id':'port-idc-eth-01','device_id':'another-earlier-owner'}]
known_before=json.loads(json.dumps(known))
technology=prepared['catalog']['technology_ids'][0]
messages=[{'role':'user','content':'Authored native port identity counterprobe, no project writes. '
    'Return port_intents containing exactly two '+technology+' LOCAL physical port records: '
    'one for owner-a and one for owner-b. Each has network_scope authored-network, parameters {}, '
    'a short rationale and empty field_references. Select device_id first. Never supply id; '
    'NIS assigns new IDs afterward. All ordinary model arrays, including ports, remain empty. /no_think'}]
payload={'model':'qwen3.8:27b','messages':messages,'format':schema,'think':False,'stream':False,
         'keep_alive':'10m','options':{'temperature':0,'num_predict':8192,
                                      'num_ctx':_reference_context_window(messages,131072)}}
write('request.json',payload)
write('started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'actual_model_requests':1})
response=get('http://127.0.0.1:11434/api/chat',payload)
write('response.json',response)
assert response.get('done_reason')!='length'
value=json.loads(response['message']['content'])
Draft202012Validator(schema).validate(value)
intents=value.pop('port_intents')
assert value.get('ports',[])==[] and len(intents)==2
assert {row['device_id'] for row in intents}==set(owners)
assert all('id' not in row and row['technology']==technology and not row['parameters'] for row in intents)
value['ports']=_reference_expand_port_intents(known,intents,owners)
public=intake.ReferenceDesignProposal.model_validate(value).model_dump(mode='json')
Draft202012Validator(intake.reference_design_schema(prepared)).validate(public)
ids=[row['id'] for row in public['ports']]
assert len(set(ids))==2 and not set(ids)&{row['id'] for row in known}
for before,after in zip(intents,public['ports']):
    expected=intake.ReferencePort.model_validate({'id':'authored-comparison',**before}).model_dump(mode='json')
    assert {key:item for key,item in after.items() if key!='id'}=={key:item for key,item in expected.items() if key!='id'}
assert known==known_before and hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
write('normal-public-port-records.json',public['ports'])
result={'status':'PASSED','at_utc':datetime.now(timezone.utc).isoformat(),'actual_model_requests':1,
        'native_id_free_schema_and_public_contract_valid':True,'fresh_unique_owner_bound_port_ids':ids,
        'all_native_technical_decisions_preserved':True,'known_ports_unmodified':True,
        'source_sha256':source_hash,'eval_count':response.get('eval_count'),'canonical_writes':False,
        'original_model_acceptance':False,'provider_model_context_output_timeout_unchanged':True}
write('result.json',result)
print(json.dumps(result),flush=True)
