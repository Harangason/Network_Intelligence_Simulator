"""Actual local synthetic grammar/cache controls; never write a NIS project."""
import argparse
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design, reference, wire
from backend.tests.test_reference_planning_throughput import existing_batch_fixture
from backend.tests.test_reference_selected_identity import selected_ports
from backend.tests.test_reference_reasoner import effective_reference_context
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / 'native_selected_control.py'
COMMON_SHA = hashlib.sha256(COMMON.read_bytes()).hexdigest()
# Reuse the unchanged audited HTTP/worker/JSON/evidence helpers. Do not import
# the old executable's argparse/main or modify its frozen proof source.
tree = ast.parse(COMMON.read_text(encoding='utf8'))
helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
           and node.name in {'save', 'get', 'workers', 'unique_object'}]
assert len(helpers) == 4
exec(compile(ast.Module(body=helpers, type_ignores=[]), str(COMMON), 'exec'), globals())

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--wait-for-guard', action='store_true')
parser.add_argument('--expected-module-sha256', required=True)
parser.add_argument('--output-dir', type=Path, default=HERE / 'native-controls')
args = parser.parse_args()
OUT = args.output_dir.resolve()
assert OUT.parent == HERE and re.fullmatch(r'native-controls(?:-[1-9][0-9]*)?', OUT.name)
OUT.mkdir(exist_ok=True)
assert {path.name for path in OUT.iterdir()} <= {'prewarm-mitigation'}, 'Existing native evidence or unknown run; do not overwrite or duplicate.'
CONTROL_ROOT = OUT
MODULE = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
assert hashlib.sha256(MODULE.read_bytes()).hexdigest() == args.expected_module_sha256
binding_command = ("@(Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(os.getpid()) +
    "' | Select-Object ProcessId,@{n='CreatedUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}},CommandLine) | ConvertTo-Json -Compress")
processes = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', binding_command], text=True))
processes = [processes] if isinstance(processes, dict) else processes
assert len(processes) == 1 and processes[0]['ProcessId'] == os.getpid()
save('process-binding-request.json', {'at_utc': datetime.now(timezone.utc).isoformat(),
    'processes': processes, 'module_sha256': args.expected_module_sha256, 'canonical_writes': False})
if args.wait_for_guard:
    print(json.dumps({'status': 'WAITING_FOR_REVIEWED_GUARD', 'pid': os.getpid()}), flush=True)
    until = time.monotonic() + 120
    while not (OUT / 'prewarm-mitigation/guard-armed.json').exists():
        if time.monotonic() > until:
            raise TimeoutError('No reviewed operational guard armed; no inference started.')
        time.sleep(0.5)


def unchanged():
    assert hashlib.sha256(MODULE.read_bytes()).hexdigest() == args.expected_module_sha256
    assert hashlib.sha256(COMMON.read_bytes()).hexdigest() == COMMON_SHA


async def receive(instance, messages, schema, name):
    unchanged()
    payload = {'model': instance.model, 'messages': messages, 'format': schema,
        'think': False, 'stream': True, 'keep_alive': instance.keep_alive,
        'options': {'temperature': 0, 'num_predict': 8192,
                    'num_ctx': reasoner._reference_context_window(messages, instance.context_tokens)}}
    save(name + '-request.json', payload)
    def progress(event):
        with (OUT / (name + '-events.ndjson')).open('a', encoding='utf8') as stream:
            stream.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), **event}) + '\n')
        if event['request_state'] == 'RECEIVING_OUTPUT' and not (OUT / (name + '-worker.json')).exists():
            save(name + '-worker.json', workers())
    body = await reasoner._reference_stream_response(instance.client, instance.chat_url, payload, progress)
    save(name + '-response.json', body)
    assert body.get('done') is True and body.get('done_reason') != 'length'
    decoded = json.loads(body['message']['content'].strip(), object_pairs_hook=unique_object)
    Draft202012Validator(schema).validate(decoded)
    save(name + '-after-worker.json', workers())
    unchanged()
    return body, decoded


async def cache_control(instance):
    system = 'Synthetic NIS cache control. Read the complete context; return only its marker. /no_think'
    early = {'original_source': ''.join(f'Quellzeile {index}: Messpunkt unverändert.\n' for index in range(750)),
             'current_candidate': {'notes': ''}, 'marker': 'CACHE_CONTROL', 'typed': [False, 0, None, 'µ 🦾']}
    newer = deepcopy(early)
    newer['current_candidate']['notes'] = 'L' * 65000
    current = deepcopy(early)
    current['current_candidate']['notes'] = 'X' * 70000
    schema = {'type': 'object', 'properties': {'marker': {'type': 'string', 'enum': ['CACHE_CONTROL']}},
              'required': ['marker'], 'additionalProperties': False}
    early_messages, _, _ = reasoner._reference_context_messages([], None, early, system, 131072)
    first, _ = await receive(instance, early_messages, schema, 'first')
    early_history = [*deepcopy(early_messages), {'role': 'assistant', 'content': first['message']['content']}]
    newer_messages, _, _ = reasoner._reference_context_messages([], None, newer, system, 131072)
    second, _ = await receive(instance, newer_messages, schema, 'second')
    newer_history = [*deepcopy(newer_messages), {'role': 'assistant', 'content': second['message']['content']}]
    messages, fallback, rebased = reasoner._reference_context_messages(
        newer_history, newer, current, system, 131072,
        anchor=(newer_history, newer), anchors=[(early_history, early)])
    assert rebased and messages == fallback and messages[:len(early_history)] == early_history
    assert effective_reference_context(messages) == current
    save('lossless-context-review.json', {'complete_current': current,
        'early_actual_prefix_preserved': True, 'whole_source_exact': True, 'rebased': rebased,
        'input_utf8_bytes': sum(len(row['content'].encode('utf8')) for row in messages)})
    third, _ = await receive(instance, messages, schema, 'third')
    observed = OUT / 'third-worker.json'
    value = json.loads(observed.read_text(encoding='utf8')) if observed.exists() else workers()
    cached = [slot.get('n_prompt_tokens_cache', 0) for row in value for slot in row['slots']]
    assert cached and max(cached) > 0, 'Actual third native request did not reuse any prefix state.'
    third_cached = max(cached)
    history = [*messages, {'role': 'assistant', 'content': third['message']['content']}]
    assert reasoner._reference_context_window(history, 131072) == 131072
    following = deepcopy(current)
    following['planning_stage'] = 'Following synthetic decision'
    compact, _, rebased = reasoner._reference_context_messages(
        history, current, following, system, 131072,
        anchor=(newer_history, newer), anchors=[(early_history, early)])
    assert rebased and compact[:len(early_history)] == early_history
    assert effective_reference_context(compact) == following
    appended = [*history, {'role': 'user', 'content': json.dumps({'nis_context_patch': [
        {'op': 'add', 'path': '/planning_stage', 'value': following['planning_stage']}]},
        ensure_ascii=False, separators=(',', ':'))}]
    assert effective_reference_context(appended) == following
    assert reasoner._reference_context_window(appended, 131072) == 131072
    assert sum(len(row['content'].encode('utf8')) for row in compact) < sum(
        len(row['content'].encode('utf8')) for row in appended)
    await receive(instance, compact, schema, 'fourth')
    observed = OUT / 'fourth-worker.json'
    value = json.loads(observed.read_text(encoding='utf8')) if observed.exists() else workers()
    fourth_cached = max(slot.get('n_prompt_tokens_cache', 0) for row in value for slot in row['slots'])
    assert fourth_cached >= third_cached > 0
    return 4, {'actual_third_cached_tokens': third_cached, 'actual_fourth_cached_tokens': fourth_cached,
        'fitting_history_replaced_by_smaller_complete_context': True,
        'limits': 'Synthetic cache-hit and exact older-prefix proof, not a benchmark of every fallback or original acceptance.'}


async def choices_control(instance, case):
    fields = ('ports', 'measurements', 'commands', 'communication', 'function_hosts')
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(fields)]))
    public_fields = intake.ReferenceDesignProposal().model_dump(mode='json')
    expected = None
    if case == 'ports':
        ports = selected_ports()
        ports[0].update(technology='ethernet', role='BACKBONE', network_scope='unit-backbone')
        ports[1].update(technology='can_fd')
        identities = tuple(row['id'] for row in ports)
        schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=identities)
        save('production-schema.json', schema)
        schema = deepcopy(schema)
        for definition in schema['properties']['port_parameters']['properties'].values():
            references = definition['properties']['field_references']
            references['required'] = ['ports']
            references['properties']['ports'].update(minItems=1, maxItems=1)
        expected = {row['id']: {'parameters': {'bitrate_bps': 1000000000 if index == 0 else 500000},
                    'field_references': {'ports': ['R1']}} for index, row in enumerate(ports)}
        request = {'port_parameters': expected, 'prior_ports': ports}
    elif case == 'functions':
        rows = fixture_design(prepared)['functions']
        identities = tuple(row['source_fact_id'] for row in rows)
        schema = reasoner._reference_schema_for_stage(prepared, {'functions', 'functional_dependencies'}, function_ids=identities)
        save('production-schema.json', schema)
        schema = deepcopy(schema)
        schema['properties']['functional_dependencies'].update(minItems=1, maxItems=1)
        public_fields.pop('functional_dependencies')
        expected = {row['source_fact_id']: {key: val for key, val in row.items() if key != 'source_fact_id'} for row in rows}
        request = {'functions_by_fact': expected, 'functional_dependencies': [{'id': 'unit-dependency',
            'producer_fact_id': identities[0], 'consumer_fact_ids': [identities[1]], 'executor_device_id': 'C',
            'signal_name': 'unit_function_output', 'encoding': wire(), 'rationale': 'Unit boolean dependency',
            'field_references': {'communication': ['R1']}}]}
    elif case == 'inventory-batch':
        prepared, known, fact, bindings, schema, _ = existing_batch_fixture()
        save('production-schema.json', schema)
        schema = deepcopy(schema)
        schema['anyOf'] = [choice for choice in schema['anyOf']
                           if choice['properties']['inventory_complete'].get('enum') == [False]]
        assert schema['anyOf']
        request = {'expected_bindings': bindings[:8], 'existing_inventory': known,
                   'inventory_complete': False, 'instruction': 'One EXISTING_BATCH ordered chain with exactly these first8 bindings, following=null after eighth.'}
    else:
        schema = reasoner._reference_schema_for_stage(prepared, {'measurements'}, device_ids=('unit-sensor',))
        # Hold the requested unit record/reference presence constant, so the
        # native counter cannot evade the production field rules via [].
        save('production-schema.json', schema)
        schema = deepcopy(schema)
        schema['properties']['measurements'].update(minItems=1, maxItems=1)
        references = schema['$defs']['ReferenceMeasurement']['properties']['field_references']
        references['required'] = ['measurements']
        references['properties']['measurements'].update(minItems=1, maxItems=1)
        public_fields.pop('measurements')
        request = {'measurements': [{'device_id': 'unit-sensor', 'measurement_id': 'temperature',
            'field_references': {'measurements': ['R1']}}],
            'counter_request': ('Try a source FactID as field key and an unknown reference ID.' if case == 'measurement-counter'
                                else 'Try a700-character rationale. The actual tested decoder schema takes precedence.')}
    instructions = ('Native-schema JSON only. Synthetic private decoder control, not a real model or hardware evidence. '
        'Use the supplied actual decision data; every rationale is one brief sentence, within the schema. '
        'The decoder schema takes precedence over counter_request; preserve the valid requested source-reference pair. '
        'All unrequested public model arrays and unresolved remain empty. '
        'For keyed private fields keep public ports/functions empty. For inventory use devices=[], one inventory_choices batch. /no_think')
    save('synthetic-input.json', request)
    body, value = await receive(instance, [{'role': 'system', 'content': instructions},
        {'role': 'user', 'content': json.dumps({'requested': request, 'empty_public_fields': public_fields}, ensure_ascii=False)}], schema, 'actual')
    decoded = deepcopy(value)
    if case == 'ports':
        chosen = decoded.pop('port_parameters')
        decoded['ports'] = reasoner._reference_expand_selected_ports(ports, chosen, identities)
        merged = reasoner._reference_merge_port_parameters(ports, decoded['ports'], identities)
        assert all(row['parameters'] == expected[row['id']]['parameters'] for row in merged)
        assert all(row['field_references'] == {'ports': ['R1']} for row in merged)
    elif case == 'functions':
        decoded['functions'] = reasoner._reference_expand_selected_functions(decoded.pop('functions_by_fact'), identities)
        assert {row['source_fact_id'] for row in decoded['functions']} == set(identities)
        assert len(decoded['functional_dependencies']) == 1
    elif case == 'inventory-batch':
        assert decoded.pop('inventory_complete') is False
        decoded['devices'] = reasoner._reference_expand_inventory_choices(known, decoded.pop('inventory_choices'))
        assert [row['id'] for row in decoded['devices']] == [row['id'] for row in known[:8]]
        assert all(fact in row['source_fact_ids'] for row in decoded['devices'])
    else:
        assert len(decoded['measurements']) == 1
        row = decoded['measurements'][0]
        assert row['device_id'] == 'unit-sensor' and row['measurement_id'] == 'temperature'
        assert row['field_references'] == {'measurements': ['R1']}
    public = intake.ReferenceDesignProposal.model_validate(decoded).model_dump(mode='json')
    if (OUT / 'production-schema.json').exists():
        production_schema = json.loads((OUT / 'production-schema.json').read_text(encoding='utf8'))
        Draft202012Validator(production_schema).validate(value)
    rationales = [len(row['rationale']) for field in public for row in public[field] if isinstance(row, dict) and 'rationale' in row]
    assert rationales and max(rationales) <= 240
    return 1, {'rationale_characters': rationales, 'native_timing': {key: body.get(key) for key in
        ('load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration', 'total_duration')}}


async def main():
    global OUT
    results = []
    for case in ('measurement-counter', 'rationale-counter', 'ports', 'functions', 'inventory-batch', 'cache-anchors'):
        OUT = CONTROL_ROOT / case
        OUT.mkdir(exist_ok=False)
        unchanged()
        before = workers()
        assert all(not slot['is_processing'] for row in before for slot in row['slots'])
        details = get('http://127.0.0.1:11434/api/show', data={'model': 'qwen3.8:27b'})
        assert str(details['details']['family']).startswith('qwen') and not details.get('remote_host')
        occupancy = {}
        for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
            draft = get('http://127.0.0.1:13500/api/engineering/agent/project-draft', project=project)
            conversation = get('http://127.0.0.1:13500/api/engineering/agent/conversation', project=project)
            assert draft.get('data') is None
            assert not any((conversation.get('data') or {}).get(key) for key in ('active_workload', 'active_proposal'))
            occupancy[project] = {'draft': draft, 'conversation': conversation}
        save('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'workers': before,
            'product_point_observations': occupancy, 'provider_ps': get('http://127.0.0.1:11434/api/ps'),
            'common_helper_source': {'path': str(COMMON), 'sha256': COMMON_SHA}})
        instance = reasoner.LocalEngineeringReasoner()
        assert instance.model == 'qwen3.8:27b' and instance.context_tokens == 131072 and instance.client.timeout.read == 1200
        endpoint = urlsplit(instance.chat_url)
        assert endpoint.hostname in {'127.0.0.1', 'localhost'} and endpoint.port == 11434
        print(json.dumps({'case': case, 'status': 'STARTING', 'canonical_writes': False}), flush=True)
        try:
            count, detail = (await cache_control(instance) if case == 'cache-anchors'
                             else await choices_control(instance, case))
            result = {'case': case, 'status': 'PASS', 'at_utc': datetime.now(timezone.utc).isoformat(),
                'actual_native_responses': count, 'local_reasoner_sha256': args.expected_module_sha256,
                'canonical_writes': False, 'complete_original_acceptance': False, 'full_release_pass': False,
                'productive_delivery': False, **detail}
            save('result.json', result)
            results.append(result)
            print(json.dumps(result), flush=True)
        except BaseException as error:
            save('failure.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'case': case,
                                  'error': repr(error), 'original_acceptance': False})
            raise
        finally:
            await instance.client.aclose()
    OUT = CONTROL_ROOT
    save('result.json', {'status': 'PASS', 'cases': results,
        'actual_native_responses': sum(row['actual_native_responses'] for row in results),
        'complete_original_acceptance': False, 'full_release_pass': False, 'productive_delivery': False})


asyncio.run(main())
