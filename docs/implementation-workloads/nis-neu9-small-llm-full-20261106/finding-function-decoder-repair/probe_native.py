"""Two authored native decoder probes; no original acceptance or canonical writes."""
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
from backend.nis.agent.orchestration import local_reasoner as r, project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design
from backend.tests.test_reference_inventory_batch import batch_case

DIR = Path(__file__).resolve().parent
GOAL = DIR.parent
parser = argparse.ArgumentParser()
parser.add_argument('--output-name', default='native-counter')
parser.add_argument('--original-target-projection-control', action='store_true')
parser.add_argument('--function-discriminator-first-control', action='store_true')
parser.add_argument('--functions-only', action='store_true')
args = parser.parse_args()
OUT = DIR / args.output_name
assert OUT.resolve().parent == DIR.resolve()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    OUT.mkdir(exist_ok=False)
    model = 'qwen3.5:9b'
    decision = GOAL / 'human-small-model-decision-20261107.json'
    assert json.loads(decision.read_text(encoding='utf-8'))['verified_directly']
    save('authorization.json', {'path': str(decision), 'sha256': hashlib.sha256(decision.read_bytes()).hexdigest()})
    admission = json.loads(subprocess.check_output([sys.executable, str(GOAL / 'read_provider.py'), '--model', model], text=True))
    assert admission['busy_slots'] == 0 and admission['loaded_models'] in ([], [model])
    save('admission.json', admission)
    prepared, target, full_schema, _ = batch_case(8)
    schema, codec = r._reference_compact_inventory_schema(full_schema)
    inventory_context = {'synthetic_original': prepared['facts'], 'target': target,
        'instruction': 'Synthetic grammar test, not real hardware. Provide all eight requested NEW_SENSOR choices with null owner and purpose, short rationale and empty field references. '
        'Set inventory_complete=true and devices=[]. Keep exactly one unresolved finding: code=MISSING_HARDWARE_EVIDENCE, target_ref=/synthetic/transceiver, '
        'message briefly asks for the missing transceiver evidence. Do not repeat the inventory or enumerate examples in the question. Other arrays empty.'}
    cases = [('inventory-finding', prepared, schema, inventory_context, target, codec)]
    prepared = intake.prepare_reference_design(fixture_request())
    design = intake.ReferenceDesignProposal.model_validate(fixture_design(prepared)).model_dump(mode='json')
    identities = [row['source_fact_id'] for row in design['functions']]
    schema = r._reference_schema_for_stage(prepared, {'functions'}, function_ids=identities)
    context = {'synthetic_original': prepared['source_evidence'], 'facts': prepared['facts'], 'devices': design['devices'],
        'instruction': f'Synthetic grammar test, not real hardware. In functions_by_fact realize {identities[0]} and {identities[1]} atomically on controller C. '
        f'Realize {identities[2]} as a composite of exactly those two functions, with no own executor. '
        'Use concise rationale, empty field_references and all ordinary arrays empty. Explicitly include both executor_device_ids and realized_by_fact_ids in every decision.'}
    cases.append(('functions', prepared, schema, context, design, identities))
    if args.functions_only:
        cases = [cases[-1]]
    results = []
    for name, prepared, schema, context, expected, codec in cases:
        if args.original_target_projection_control:
            original = deepcopy(schema)
            schema['$defs']['ReferenceFinding']['properties']['target_ref'].pop('maxLength')
            restored = deepcopy(schema)
            restored['$defs']['ReferenceFinding']['properties']['target_ref']['maxLength'] = 2000
            assert restored == original
            save(name + '-independent-control.json', {'only_change': 'Restore existing public-to-native target_ref projection; public 2000 bound remains unchanged.', 'product_code_changed': False})
        if args.function_discriminator_first_control and name == 'functions':
            before = deepcopy(schema)
            for choice in schema['properties']['functions_by_fact']['properties'].values():
                for alternative in choice['anyOf']:
                    fields = alternative['properties']
                    alternative['properties'] = {'realization': fields['realization'], **fields}
            assert schema == before  # dictionary order changes, accepted JSON language does not
            save(name + '-order-control.json', {'only_change': 'Discriminator precedes free rationale; equal JSON Schema object.', 'product_code_changed': False})
        messages = [{'role': 'system', 'content': 'Independent synthetic decoder counterprobe. Return only JSON matching the supplied schema. No physical or safety qualification.'},
                    {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}]
        payload = dict(model=model, messages=messages, format=schema, think=False, stream=True, keep_alive='10m',
                       options=dict(temperature=0, num_predict=8192, num_ctx=r._reference_context_window(messages, 131072)))
        save(name + '-request.json', payload)
        with (OUT / (name + '-events.ndjson')).open('w', encoding='utf-8') as log:
            def report(value):
                log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value}) + '\n'); log.flush()
            async def capture_error(response):
                if response.status_code != 200:
                    raw = await response.aread()
                    save(name + '-http-error.json', {'status': response.status_code, 'body': raw.decode('utf-8', errors='replace')})
            async with httpx.AsyncClient(timeout=1200, trust_env=False, event_hooks={'response': [capture_error]}) as client:
                body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
        save(name + '-response.json', body)
        assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == model
        value = intake.document_response_json(body['message']['content'])
        Draft202012Validator(schema).validate(value)
        if name == 'inventory-finding':
            rows = r._reference_expand_inventory_choices([], value['inventory_choices'], inventory_target=expected, inventory_codec=codec)
            expanded = intake.ReferenceDesignProposal.model_validate({'devices': rows, 'unresolved': value['unresolved']}).model_dump(mode='json')
            assert len(expanded['devices']) == 8 and value['inventory_complete'] is True
            assert len(value['unresolved']) == 1 and value['unresolved'][0]['code'] == 'MISSING_HARDWARE_EVIDENCE'
            assert value['unresolved'][0]['target_ref'] == '/synthetic/transceiver'
            assert len(value['unresolved'][0]['message']) <= 240
        else:
            functions = r._reference_expand_selected_functions(value['functions_by_fact'], codec)
            candidate = deepcopy(expected); candidate['functions'] = functions
            checked = intake.validate_reference_design(candidate, prepared)
            assert checked['canonical_writes'] is False
            by_id = {row['source_fact_id']: row for row in functions}
            assert all(by_id[key]['realization'] == 'ATOMIC' and by_id[key]['executor_device_ids'] == ['C'] for key in codec[:2])
            assert by_id[codec[2]]['realization'] == 'COMPOSITE' and by_id[codec[2]]['executor_device_ids'] == []
            assert set(by_id[codec[2]]['realized_by_fact_ids']) == set(codec[:2])
        results.append({'case': name, 'status': 'PASS', 'metrics': {key: body.get(key) for key in
            ('eval_count', 'prompt_eval_count', 'prompt_eval_duration', 'eval_duration', 'total_duration')}})
        save('progress.json', results)
        print(json.dumps(results[-1]), flush=True)
    result = {'status': 'PASS', 'model': model, 'actual_inference_requests': len(results), 'results': results,
        'source_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
        'diagnostic_target_projection_control': args.original_target_projection_control,
        'original_acceptance': False, 'simulation_acceptance': False, 'canonical_writes': False}
    save('result.json', result)
    print(json.dumps(result), flush=True)


asyncio.run(main())
