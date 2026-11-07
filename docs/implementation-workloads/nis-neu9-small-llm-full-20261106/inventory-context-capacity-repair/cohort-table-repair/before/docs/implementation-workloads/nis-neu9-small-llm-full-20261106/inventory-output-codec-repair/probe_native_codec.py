"""One real configured-model grammar probe, no original/model/simulation acceptance."""
import asyncio
import argparse
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
from backend.tests.test_reference_inventory_batch import batch_case
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import ReferenceDesignProposal, document_response_json

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path)
parser.add_argument('--packed-context', action='store_true')
args = parser.parse_args()
OUT = (args.output or Path(__file__).resolve().parent / 'native-grammar').resolve()
GOAL = Path(__file__).resolve().parents[1]
assert OUT.is_relative_to(GOAL)
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


async def main():
    settings = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf8'))['local_implementation_agent']
    model = settings['preferred_models']['reasoning']
    assert model == 'llama3.1:8b' and settings['enabled_models'] == [model]
    assert settings['preferred_models']['fallback'] is None
    # Reuse the established dynamic main-worker-only admission reader. It asserts idle.
    admission = json.loads(subprocess.check_output([sys.executable, str(GOAL / 'read_provider.py')], text=True))
    save('admission.json', admission)
    prepared, target, full_schema, _ = batch_case(8)
    schema, codec = r._reference_compact_inventory_schema(full_schema)
    save("request-local-codec.json", codec)
    messages = [{'role': 'system', 'content': 'This is a synthetic grammar counterprobe, never a real hardware design. Return only JSON matching the supplied schema.'},
                {'role': 'user', 'content': json.dumps({'instruction':
                    'Produce each of these eight independent synthetic sensor decisions in inventory_choices under its exact name. '
                    'The schema omits fixed identity, quantity and source fields; NIS restores those exact offered constants. Use empty field_references, '
                    'null owner and purpose. Short rationale. All eight slots required. '
                    'devices=[], unresolved=[], inventory_complete=true. No physical or safety qualification is claimed.',
                    'target': target, 'synthetic_source_fact': prepared['facts'][target['fact_id']]}, ensure_ascii=False)}]
    existing = []
    if args.packed_context:
        from backend.tests.test_reference_inventory_context_capacity import authored_context, read_selection
        current = authored_context(12, 2)
        existing = current['current_candidate']['devices']
        current['inventory_target_for_this_stage'] = target
        current.update(json.loads(messages[-1]['content']))
        current['instruction'] += ' The twelve authored existing controllers remain present and unchanged. They are not the eight requested new sensors.'
        messages, _, _ = r._reference_context_messages([], None, current, messages[0]['content'], 131072)
        selection = json.loads(messages[-1]['content'])['nis_current_selection']
        assert isinstance(selection['existing_inventory'], dict) and len(read_selection(selection)) == 12
        full_schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=existing)
        schema, codec = r._reference_compact_inventory_schema(full_schema)
        save('request-local-codec.json', codec)
    payload = {'model': model, 'messages': messages, 'format': schema, 'think': False,
               'stream': True, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
                   'num_ctx': r._reference_context_window(messages, 131072)}}
    save('request.json', payload)
    with (OUT / 'events.ndjson').open('w', encoding='utf8') as log:
        def report(value):
            log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value}) + '\n'); log.flush()
        async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
            body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
    save('response.json', body)
    assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == model
    value = document_response_json(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    rows = r._reference_expand_inventory_choices(existing, value['inventory_choices'], inventory_target=target, inventory_codec=codec)
    rows = ReferenceDesignProposal.model_validate({'devices': rows}).model_dump(mode='json')['devices']
    rows = r._reference_scoped_inventory_delta(existing, rows, inventory_target=target)
    merged = r._reference_merge_inventory_devices(existing, rows, target, prepared['facts'])
    assert len(merged) == len({row['id'] for row in merged}) == len(existing) + 8
    assert merged[:len(existing)] == existing
    assert [row['name'] for row in merged[len(existing):]] == target['names']
    assert value['inventory_complete'] is True and r._reference_inventory_progress(existing, merged)
    result = {'status': 'PASS', 'model': model, 'actual_inference_requests': 1, 'native_devices': len(merged) - len(existing),
              'preserved_existing_devices': len(existing), 'packed_context': args.packed_context,
              'schema_and_public_validation_and_scoped_merge': True,
              'source_code_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
              'original_acceptance': False, 'simulation_acceptance': False,
              'metrics': {key: body.get(key) for key in ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration', 'total_duration')}}
    save('result.json', result)
    print(json.dumps(result), flush=True)


asyncio.run(main())
