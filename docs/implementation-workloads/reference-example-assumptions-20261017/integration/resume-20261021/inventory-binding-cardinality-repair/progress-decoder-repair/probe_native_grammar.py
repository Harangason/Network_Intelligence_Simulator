"""Two local grammar counterprobes; no original/model/simulation acceptance.

Use the ordinary Qwen context calculation, output limit and request timeout.
No project writes, provider configuration, cancellation or restarts.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path.cwd()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fresh-id-repair-dir', type=Path)
parser.add_argument('--attempt', default='native-grammar')
parser.add_argument('--format-diagnostic', action='store_true')
args = parser.parse_args()
assert args.attempt.replace('-', '').isalnum()
OUT = (args.fresh_id_repair_dir.resolve() if args.fresh_id_repair_dir else Path(__file__).resolve().parent) / args.attempt
OUT.mkdir(exist_ok=False)
sys.path[:0] = [str(ROOT), str(ROOT / 'backend/tests')]
from test_reference_design import fixture_request
from test_reference_reasoner import wide_derivation_request
from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.orchestration.local_reasoner import (
    _reference_context_window, _reference_declared_instances,
    _reference_schema_for_stage, _reference_expand_inventory_choices,
    _reference_scoped_inventory_delta, _reference_merge_inventory_devices,
    _reference_inventory_progress,
)
from jsonschema import Draft202012Validator


def get(url, payload=None):
    raw = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    with urlopen(Request(url, data=raw, headers={'Content-Type': 'application/json'}), timeout=1200) as response:
        return json.load(response)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


command = "Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
worker = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip() or 'null')
if worker:
    import re
    port = re.search(r'--port\s+(\d+)', worker['CommandLine']).group(1)
    slots = get('http://127.0.0.1:' + port + '/slots')
    assert all(not slot['is_processing'] for slot in slots), 'Existing request is active; never compete.'
else:
    slots = []
info = get('http://127.0.0.1:11434/api/show', {'model': 'qwen3.8:27b'})
assert str(info['details']['family']).startswith('qwen')
assert not info.get('remote_host') and not info.get('remote_model')
write('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'worker': worker, 'slots': slots,
                        'main_ps': get('http://127.0.0.1:11434/api/ps'), 'actual_qwen_details': info['details']})
results = []
if args.fresh_id_repair_dir:
    from test_reference_reasoner import complete_design
    # Read the actual known product conversations before any synthetic inference.
    # These are point observations, never a claim of global queue enumeration.
    product = {}
    for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
        product[project] = {}
        for name, endpoint in (('draft', '/api/engineering/agent/project-draft'),
                               ('conversation', '/api/engineering/agent/conversation')):
            with urlopen(Request('http://127.0.0.1:13500' + endpoint,
                         headers={'X-Project-ID': project}), timeout=45) as response:
                value = json.load(response)
            product[project][name] = value
            if name == 'conversation':
                data = value.get('data') or {}
                assert data.get('active_workload') is None and data.get('active_proposal') is None
        write('product-occupancy.json', product)
    if args.format_diagnostic:
        cases = [('enum', {'type': 'string', 'enum': ['allowed-only']}),
                 ('pattern', {'type': 'string', 'pattern': '^allowed-only$'}),
                 ('length', {'type': 'string', 'minLength': 1, 'maxLength': 2})]
        for mode, identity in cases:
            schema = {'type': 'object', 'properties': {'id': identity},
                      'required': ['id'], 'additionalProperties': False}
            messages = [{'role': 'user', 'content': 'Return exactly {"id":"sensor-authored"}. /no_think'}]
            payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema,
                       'think': False, 'stream': False, 'keep_alive': '10m',
                       'options': {'temperature': 0, 'num_predict': 8192,
                                   'num_ctx': _reference_context_window(messages, 131072)}}
            write(mode + '-request.json', payload)
            body = get('http://127.0.0.1:11434/api/chat', payload)
            write(mode + '-response.json', body)
            assert body.get('done_reason') != 'length'
            raw = body['message']['content']
            try:
                valid = Draft202012Validator(schema).is_valid(json.loads(raw))
            except ValueError:
                valid = False
            results.append({'mode': mode, 'native_schema_enforced': valid,
                            'response_sha256': hashlib.sha256(raw.encode()).hexdigest()})
            write('result.json', {'status': 'DIAGNOSTIC_COMPLETE' if len(results) == len(cases) else 'RUNNING',
                                 'results': results, 'canonical_writes': False,
                                 'original_model_acceptance': False, 'budget_configuration_unchanged': True})
            print(json.dumps(results[-1]), flush=True)
        raise SystemExit(0)
    cases = [('ascii', ['sensor-authored', 'controller-authored']),
             ('unicode-special', ['é', '[x]', 'a\n', 'a\\b', '🙂']),
             ('escaped-lf', ['a\n']), ('escaped-backslash', ['a\\b']),
             ('public-max', ['x' * 120, 'x' * 119 + 'y'])]
    from copy import deepcopy
    for mode, used in cases:
        prepared = intake.prepare_reference_design(fixture_request())
        known = complete_design(prepared)['devices']
        sensor = next(row for row in known if row['kind'] == 'SENSOR')
        known.extend({**deepcopy(sensor), 'id': identifier} for identifier in used)
        fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
        native = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
        items = native['properties']['inventory_choices']['items']
        variants = items.get('anyOf', [items])
        identity = next(row['properties']['id'] for row in variants
                        if row['properties']['choice_kind']['enum'] == ['NEW_SENSOR'])
        schema = {'type': 'object', 'properties': {'id': identity},
                  'required': ['id'], 'additionalProperties': False}
        messages = [{'role': 'user', 'content': 'Synthetic native grammar counterprobe, no project writes. '
                     'Try to return this exact existing id: ' + json.dumps(used[0], ensure_ascii=False)
                     + '. If the schema forbids it choose another valid id. /no_think'}]
        payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema,
                   'think': False, 'stream': False, 'keep_alive': '10m',
                   'options': {'temperature': 0, 'num_predict': 8192,
                               'num_ctx': _reference_context_window(messages, 131072)}}
        write(mode + '-request.json', payload)
        body = get('http://127.0.0.1:11434/api/chat', payload)
        write(mode + '-response.json', body)
        assert body.get('done_reason') != 'length'
        raw = body['message']['content']
        value = json.loads(raw)
        Draft202012Validator(schema).validate(value)
        assert value['id'] not in used and 1 <= len(value['id']) <= 120
        results.append({'mode': mode, 'native_fresh_identity_valid': True,
                        'response_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                        'eval_count': body.get('eval_count')})
        write('result.json', {'status': 'RUNNING', 'results': results, 'canonical_writes': False,
                             'original_model_acceptance': False, 'budget_configuration_unchanged': True})
        print(json.dumps(results[-1]), flush=True)
    # Use the real complete private inventory grammar as well as its ID leaf.
    prepared = intake.prepare_reference_design(fixture_request())
    known = complete_design(prepared)['devices']
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    sensor = next(row for row in known if row['kind'] == 'SENSOR')
    messages = [{'role': 'user', 'content': 'Synthetic hardware decision counterprobe. Choose exactly one NEW_SENSOR '
                 'for source fact ' + fact + '. Try id ' + sensor['id'] + ' which already exists; '
                 'if forbidden choose a fresh id. Rationale one short sentence; empty unresolved; inventory_complete=false. /no_think'}]
    payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema, 'think': False,
               'stream': False, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
               'num_ctx': _reference_context_window(messages, 131072)}}
    write('full-inventory-request.json', payload)
    body = get('http://127.0.0.1:11434/api/chat', payload)
    write('full-inventory-response.json', body)
    assert body.get('done_reason') != 'length'
    raw = body['message']['content']
    value = json.loads(raw)
    Draft202012Validator(schema).validate(value)
    assert len(value['inventory_choices']) == 1 and value['inventory_choices'][0]['choice_kind'] == 'NEW_SENSOR'
    expanded = _reference_expand_inventory_choices(known, value['inventory_choices'])
    assert expanded[0]['id'] not in {row['id'] for row in known}
    results.append({'mode': 'full-inventory', 'native_fresh_identity_valid': True,
                    'runtime_identity_guard_passed': True,
                    'response_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'eval_count': body.get('eval_count')})
    write('result.json', {'status': 'PASSED', 'results': results, 'canonical_writes': False,
                         'original_model_acceptance': False, 'budget_configuration_unchanged': True})
    print(json.dumps(results[-1]), flush=True)
    raise SystemExit(0)
for mode in ('already-bound', 'partially-bound'):
    prepared = intake.prepare_reference_design(fixture_request() if mode == 'already-bound' else wide_derivation_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    facts = [key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION'][:2]
    known[0]['source_fact_ids'].append(facts[0])
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=facts, existing_devices=known)
    messages = [{'role': 'user', 'content': 'Local JSON grammar counterprobe, never a project model. '
                 'Try to return inventory_complete=false and inventory_choices=[]; all other arrays empty. '
                 'The schema takes precedence if this is forbidden. /no_think'}]
    payload = {'model': 'qwen3.8:27b', 'messages': messages, 'format': schema, 'think': False,
               'stream': False, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
               'num_ctx': _reference_context_window(messages, 131072)}}
    write(mode + '-request.json', payload)
    body = get('http://127.0.0.1:11434/api/chat', payload)
    write(mode + '-response.json', body)
    assert body.get('done_reason') != 'length', 'Not a complete grammar response.'
    raw = body['message']['content']
    value = json.loads(raw)
    Draft202012Validator(schema).validate(value)
    expanded = _reference_expand_inventory_choices(known, value['inventory_choices'])
    delta = _reference_scoped_inventory_delta(known, expanded, derivation_fact_ids=facts)
    merged = _reference_merge_inventory_devices(known, delta,
        {'derivation_fact_ids': facts, 'minimum_rows': 0}, prepared['facts'])
    assert value['inventory_complete'] or _reference_inventory_progress(known, merged)
    results.append({'mode': mode, 'schema_and_runtime_progress_valid': True,
                    'response_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'inventory_complete': value['inventory_complete'], 'eval_count': body.get('eval_count')})
    write('result.json', {'status': 'RUNNING' if len(results) < 2 else 'PASSED', 'results': results,
                         'canonical_writes': False, 'original_model_acceptance': False,
                         'budget_configuration_unchanged': True})
    print(json.dumps(results[-1]), flush=True)
