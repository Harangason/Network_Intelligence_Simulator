"""One real selected small-model decoder probe; authored inventory, no model writes."""
import asyncio
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import httpx
from jsonschema import Draft202012Validator

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import ReferenceDesignProposal, document_response_json
from backend.tests.test_reference_binding_schema_capacity import large_binding_case

DIR = Path(__file__).resolve().parent
GOAL = DIR.parent
parser = argparse.ArgumentParser()
parser.add_argument('--model', choices=['llama3.1:8b', 'qwen3.5:9b'], default='llama3.1:8b')
parser.add_argument('--shared-fields-counter', action='store_true')
parser.add_argument('--direct-selection-instruction', action='store_true')
parser.add_argument('--plain-selection-counter', action='store_true')
parser.add_argument('--output-name', default='native-251')
args = parser.parse_args()
OUT = DIR / args.output_name
assert OUT.resolve().parent == DIR.resolve()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    settings = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf-8'))['local_implementation_agent']
    assert settings['enabled_models'] == ['llama3.1:8b'] and settings['preferred_models']['fallback'] is None
    OUT.mkdir(exist_ok=False)
    if args.model == 'qwen3.5:9b':
        authorization = GOAL / 'human-small-model-decision-20261107.json'
        decision = json.loads(authorization.read_text(encoding='utf8'))
        assert decision['verified_directly'] is True and 'qwen3.5:9b' in decision['human_message']
        save('task-model-override.json', dict(model=args.model, fallback=None,
            authorization=str(authorization), sha256=hashlib.sha256(authorization.read_bytes()).hexdigest()))
    save('admission.json', json.loads(subprocess.check_output(
        [sys.executable, str(GOAL / 'read_provider.py'), '--model', args.model], text=True)))
    prepared, known, fact, _, _, _ = large_binding_case()
    facts = [fact]
    for index in range(1, 16):
        key = f'F-authored-function-{index:02}'
        prepared['facts'][key] = deepcopy(prepared['facts'][fact])
        prepared['fact_id_map'][key] = f'authored-source-function-{index:02}'
        facts.append(key)
    expected = [known[i]['id'] for i in (0, 1, 17, 63, 127, 200, 249, 250)]
    schema = r._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=facts, existing_devices=known)
    original_schema = deepcopy(schema)
    if args.shared_fields_counter:
        # Independent diagnostic transformation, not an application repair.
        definitions, by_value = {}, {}
        for name, node in schema['$defs'].items():
            if not name.startswith('NativeReferenceBinding_'):
                continue
            for alternative in node['anyOf']:
                fields = next(iter(alternative['properties'].values()))['properties']
                for field in ('source_fact_ids', 'rationale', 'field_references'):
                    value = json.dumps(fields[field], sort_keys=True, separators=(',', ':'))
                    if value not in by_value:
                        key = 'IndependentBindingField_' + str(len(by_value))
                        by_value[value] = key
                        definitions[key] = deepcopy(fields[field])
                    fields[field] = {'$ref': '#/$defs/' + by_value[value]}
        restored = deepcopy(schema)
        def restore(value):
            if isinstance(value, dict):
                reference = value.get('$ref', '').removeprefix('#/$defs/')
                if reference in definitions:
                    return deepcopy(definitions[reference])
                return {key: restore(item) for key, item in value.items()}
            return [restore(item) for item in value] if isinstance(value, list) else value
        assert restore(restored) == original_schema
        assert not set(definitions) & schema['$defs'].keys()
        schema['$defs'].update(definitions)
        save('independent-field-sharing-proof.json', dict(unique_fields=len(definitions),
            expanded_schema_exactly_equal_to_unchanged_product=True, product_code_changed=False))
    current = {'original_source': 'Independent synthetic binding counter only. No hardware or safety qualification.',
               'planning_stage': 'Authored functional binding counter',
               'inventory_target_for_this_stage': None,
               'derivation_fact_ids_for_this_stage': facts,
               'current_candidate': {'devices': known},
               'existing_inventory_for_this_stage': [{key: row[key] for key in ('id', 'name', 'kind')} for row in known],
               'instruction': 'Return one EXISTING_BATCH with exactly these eight existing IDs, in the given order: '
                   + ', '.join(expected) + '. For each add only the source fact ' + fact
                   + '. Use a short rationale and empty field_references. Each binding node has exactly one ID key; '
                   'its fields are source_fact_ids, rationale, field_references and following. following is the next node '
                   'or null after the eighth. All original existing identities and bindings remain unchanged. '
                   'devices=[], unresolved=[], inventory_complete=true. No new devices.'}
    messages, _, _ = r._reference_context_messages([], None, current,
        'This is an independently authored decoder counterprobe, not a real design. Return only matching JSON.', 131072)
    if args.direct_selection_instruction:
        messages.append({'role': 'user', 'content': current['instruction']})
    if args.plain_selection_counter:
        messages = [{'role': 'system', 'content': 'Independent synthetic decoder control. Follow the user instruction and return only matching JSON.'},
                    {'role': 'user', 'content': json.dumps({
                        'existing_inventory': [{key: row[key] for key in ('id', 'name', 'kind', 'source_fact_ids')} for row in known],
                        'available_fact_ids': facts, 'instruction': current['instruction']}, ensure_ascii=False)}]
    payload = dict(model=args.model, messages=messages, format=schema, think=False,
                   stream=True, keep_alive='10m', options=dict(temperature=0, num_predict=8192,
                       num_ctx=r._reference_context_window(messages, 131072)))
    save('request.json', payload)
    with (OUT / 'events.ndjson').open('w', encoding='utf-8') as events:
        def report(value):
            events.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(), **value))+'\n')
            events.flush()
        with (OUT / 'raw-provider-stream.ndjson').open('wb') as raw:
            class Capture(httpx.AsyncByteStream):
                def __init__(self, stream): self.stream = stream
                async def __aiter__(self):
                    async for chunk in self.stream:
                        raw.write(chunk); raw.flush()
                        yield chunk
                async def aclose(self): await self.stream.aclose()
            async def capture(response):
                save('response-headers.json', dict(status=response.status_code, headers=dict(response.headers)))
                response.stream = Capture(response.stream)
            try:
                async with httpx.AsyncClient(timeout=1200, trust_env=False, event_hooks={'response': [capture]}) as client:
                    body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
            except Exception as error:
                save('result.json', dict(status='FAIL', error=str(error),
                    independent_shared_fields_counter=args.shared_fields_counter, original_acceptance=False))
                raise
    save('response.json', body)
    assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == args.model
    value = document_response_json(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    Draft202012Validator(original_schema).validate(value)
    rows = r._reference_expand_inventory_choices(known, value['inventory_choices'])
    rows = ReferenceDesignProposal.model_validate({'devices': rows}).model_dump(mode='json')['devices']
    rows = r._reference_scoped_inventory_delta(known, rows, derivation_fact_ids=facts)
    merged = r._reference_merge_inventory_devices(known, rows,
        {'derivation_fact_ids': facts, 'minimum_rows': 0}, prepared['facts'])
    assert [row['id'] for row in rows] == expected
    assert len(merged) == 251 and [row['id'] for row in merged] == [row['id'] for row in known]
    for before, after in zip(known, merged, strict=True):
        assert all(after[key] == old for key, old in before.items()
                   if key not in {'source_fact_ids', 'rationale', 'field_references'})
        assert set(after['source_fact_ids']) == set(before['source_fact_ids']) | ({fact} if before['id'] in expected else set())
    assert r._reference_inventory_progress(known, merged)
    result = dict(status='PASS', actual_inference_requests=1, model=body['model'],
        existing_devices=251, native_bindings=8, available_facts=16, expected_ids=expected,
        schema_bytes=len(json.dumps(schema, ensure_ascii=False, separators=(',', ':')).encode()),
        public_validation_scoped_merge_preserved=True, original_acceptance=False, simulation_acceptance=False,
        source_sha256=hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
        independent_shared_fields_counter=args.shared_fields_counter,
        direct_selection_instruction=args.direct_selection_instruction,
        plain_selection_counter=args.plain_selection_counter,
        metrics={key: body.get(key) for key in ('prompt_eval_count','eval_count','prompt_eval_duration','eval_duration','total_duration')})
    save('result.json', result)
    print(json.dumps(result), flush=True)


asyncio.run(main())
