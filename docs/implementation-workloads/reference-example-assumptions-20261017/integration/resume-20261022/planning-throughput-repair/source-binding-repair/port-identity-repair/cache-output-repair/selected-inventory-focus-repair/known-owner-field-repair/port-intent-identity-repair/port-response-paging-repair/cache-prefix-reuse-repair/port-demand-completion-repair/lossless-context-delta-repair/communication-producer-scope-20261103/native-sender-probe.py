from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import re

from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request

out = Path(r'docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261022/planning-throughput-repair/source-binding-repair/port-identity-repair/cache-output-repair/selected-inventory-focus-repair/known-owner-field-repair/port-intent-identity-repair/port-response-paging-repair/cache-prefix-reuse-repair/port-demand-completion-repair/lossless-context-delta-repair/communication-producer-scope-20261103')
observation = json.loads((out / 'observed-native-failure.json').read_text(encoding='utf8'))
selected = tuple(observation['selected_sender_ids'])
foreign = observation['foreign_sender_ids'][0]
rejected_rows = json.loads(observation['rejected_native_reply']['response'])['communication']
row = next(entry for entry in rejected_rows if entry['producer_device_id'] == foreign)
schema = reasoner._reference_schema_for_stage(
    intake.prepare_reference_design(fixture_request()), {'communication'}, producer_ids=selected,
)
body = intake.ReferenceDesignProposal(communication=[row]).model_dump(mode='json')
validator = Draft202012Validator(schema)
assert [list(e.absolute_path) for e in validator.iter_errors(body)] == [
    ['communication', 0, 'producer_device_id'],
]
messages = [{'role': 'user', 'content':
    'Return exactly one communication row. Copy the provided row and its consumer_device_ids. '
    'Use the provided producer_device_id if admitted by the response schema, otherwise use '
    'one of its permitted sender IDs. Leave the other model arrays empty. /no_think\n'
    + json.dumps(body, ensure_ascii=False, separators=(',', ':'))}]
payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema,
           'think': False, 'stream': False, 'keep_alive': 0,
           'options': {'temperature': 0, 'num_predict': 8192,
                       'num_ctx': reasoner._reference_context_window(messages, 131072)}}

def read(base, path, headers=None):
    with urlopen(Request(base + path, headers=headers or {}), timeout=8) as response:
        return json.load(response)

cmd = r"""$m=@(Get-NetTCPConnection -LocalPort 11434 | Where-Object {$_.OwningProcess -gt 0} | Select-Object -ExpandProperty OwningProcess -Unique); if($m.Count -ne 1){throw 'Unexpected provider ownership'}; $o=Get-CimInstance Win32_Process -Filter ('ProcessId='+$m[0]); if($o.Name -ne 'ollama.exe' -or $o.CommandLine -notmatch '(?:^|\s)serve(?:\s|$)'){throw 'Unexpected provider identity'}; [ordered]@{main=$m[0]; workers=@(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$m[0]+" AND Name='llama-server.exe'") | Select-Object ProcessId,CommandLine); active_nis=@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {$_.CommandLine -match 'native_original_(document|workflow)_driver.py|run-isolated-tests.py'} | Select-Object ProcessId)} | ConvertTo-Json -Depth 5 -Compress"""
owner = json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd],text=True,timeout=15))
assert not owner['active_nis']
for worker in owner['workers']:
    port = re.search(r'--port\s+(\d+)', worker['CommandLine']).group(1)
    assert all(not s['is_processing'] for s in read('http://127.0.0.1:'+port, '/slots'))
for project in ('20261021094952722-147a3d72','20261020103707202-0fda8601'):
    conversation = read('http://127.0.0.1:13500','/api/engineering/agent/conversation',
                        {'X-Project-ID':project})['data'] or {}
    assert conversation.get('active_workload') is None and conversation.get('active_proposal') is None
raw = json.dumps(payload,ensure_ascii=False).encode()
with (out/'native-sender-probe-request.json').open('xb') as f:
    f.write(raw)
print(json.dumps({'scope':'one local native schema probe','started_at':datetime.now(timezone.utc).isoformat(),
                  'provider_pid':owner['main'],'selected':selected}), flush=True)
req = Request('http://127.0.0.1:11434/api/chat', data=raw, headers={'Content-Type':'application/json'})
with urlopen(req,timeout=1200) as response:
    raw_response = response.read()
(out/'native-sender-probe-response.json').write_bytes(raw_response)
response = json.loads(raw_response)
assert response['model']=='qwen3.8:27b' and response['done'] is True and response['done_reason']=='stop'
decoded = json.loads(response['message']['content'])
validator.validate(decoded)
result = intake.ReferenceDesignProposal.model_validate(decoded).model_dump(mode='json')
assert len(result['communication'])==1
record=result['communication'][0]
assert record['producer_device_id'] in selected
assert record['consumer_device_ids']==row['consumer_device_ids']
report={'status':'PASS','observed_foreign_sender':foreign,'selected_sender_ids':selected,
        'actual_sender':record['producer_device_id'],'consumer_ids_exact':True,
        'request_sha256':hashlib.sha256(raw).hexdigest(),
        'response_sha256':hashlib.sha256(raw_response).hexdigest(),
        'prompt_eval_count':response.get('prompt_eval_count'),'eval_count':response.get('eval_count'),
        'actual_model_calls':1,'full_original_acceptance':False,
        'at_utc':datetime.now(timezone.utc).isoformat()}
(out/'native-sender-probe-result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

