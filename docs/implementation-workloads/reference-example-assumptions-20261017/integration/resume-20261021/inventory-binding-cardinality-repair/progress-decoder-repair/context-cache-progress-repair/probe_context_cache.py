"""Two sequential ordinary local Qwen calls; cache diagnostic, not original acceptance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'native-cache'
sys.path[:0] = [str(ROOT), str(ROOT / 'backend/tests')]
from test_reference_design import fixture_request
from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.orchestration.local_reasoner import (
    _reference_context_messages, _reference_context_window, _reference_declared_instances,
    _reference_schema_for_stage, _reference_expand_inventory_choices,
    _reference_scoped_inventory_delta, _reference_merge_inventory_devices,
)
from jsonschema import Draft202012Validator

def get(url, payload=None, headers=None):
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    with urlopen(Request(url, data=raw, headers={'Content-Type': 'application/json', **(headers or {})}), timeout=1200) as response:
        return json.load(response)

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def worker():
    script = "@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', script], text=True).strip() or '[]')
    rows = rows if isinstance(rows, list) else [rows]
    assert len(rows) <= 1
    if not rows:
        return {'worker': None, 'slots': []}
    row = rows[0]
    port = re.search(r'--port\s+(\d+)', row['CommandLine']).group(1)
    return {'worker': row, 'slots': get('http://127.0.0.1:' + port + '/slots')}

assert not OUT.exists(), 'Never duplicate an uncertain native diagnostic.'
before = worker()
assert all(not slot['is_processing'] for slot in before['slots']), 'Never compete with active inference.'
project_states = []
for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
    draft = get('http://127.0.0.1:13500/api/engineering/agent/project-draft', headers={'X-Project-ID': project})
    assert draft.get('data') is None, 'Product draft present; inspect before inference.'
    project_states.append({'project': project, 'draft': draft.get('data')})
details = get('http://127.0.0.1:11434/api/show', {'model': 'qwen3.8:27b'})
assert str(details['details']['family']).startswith('qwen')
assert not details.get('remote_host') and not details.get('remote_model')
OUT.mkdir()
write('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), **before,
    'product_project_point_observations': project_states, 'provider_ps': get('http://127.0.0.1:11434/api/ps'),
    'model_details': details['details'], 'inference_owner': 'NIS; fresh existing-peer confirmation required by operator'})
prepared = intake.prepare_reference_design(fixture_request())
known, _ = _reference_declared_instances(prepared, prepared['facts'])
facts = [key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION'][:2]
known[0]['source_fact_ids'].extend(facts)
schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=facts, existing_devices=known)
system = ('Native local NIS context-cache diagnostic. No project model writes. All requested source facts '
          'are already bound to the known controller. Return inventory_complete=true, inventory_choices=[], '
          'all other arrays empty, in the actual supplied schema. Keep the complete source context. /no_think')
context = {'original_source': prepared['source_evidence']['source_text'], 'original_facts': prepared['facts'],
    'registered_catalogs': prepared['catalog'], 'current_candidate': {'devices': known},
    'planning_stage': 'Hardware cache diagnostic', 'derivation_fact_ids_for_this_stage': facts,
    'output_fields_for_this_stage': ['devices'], 'diagnostic_sequence': 1}
history, previous, results = [], None, []
for sequence in (1, 2):
    context = {**context, 'diagnostic_sequence': sequence}
    messages, _, rebased = _reference_context_messages(history, previous, context, system, 131072)
    if sequence == 2:
        assert messages[:len(history)] == history and not rebased
    payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema, 'think': False,
        'stream': False, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
        'num_ctx': _reference_context_window(messages, 131072)}}
    write(f'{sequence}-request.json', payload)
    body = get('http://127.0.0.1:11434/api/chat', payload)
    write(f'{sequence}-response.json', body)
    assert body.get('done_reason') != 'length'
    value = json.loads(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    assert value['inventory_complete'] is True and value['inventory_choices'] == []
    expanded = _reference_expand_inventory_choices(known, value['inventory_choices'])
    delta = _reference_scoped_inventory_delta(known, expanded, derivation_fact_ids=facts)
    assert _reference_merge_inventory_devices(known, delta, {'derivation_fact_ids': facts, 'minimum_rows': 0}, prepared['facts']) == known
    history = [*messages, {'role': 'assistant', 'content': body['message']['content']}]
    previous = context
    observed = worker()
    write(f'{sequence}-worker-after.json', observed)
    results.append({'sequence': sequence, 'response_sha256': hashlib.sha256(body['message']['content'].encode()).hexdigest(),
        **{key: body.get(key) for key in ('prompt_eval_count', 'eval_count', 'load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')},
        'worker_pid': observed['worker']['ProcessId'] if observed['worker'] else None})
    write('result.json', {'status': 'RUNNING' if sequence == 1 else 'RESPONSES_VALID_CACHE_EVIDENCE_REQUIRES_REVIEW',
        'results': results, 'canonical_writes': False, 'original_acceptance': False,
        'maximum_context': 131072, 'output': 8192, 'timeout_seconds': 1200})
    print(json.dumps(results[-1]), flush=True)
