"""One real configured-model grammar probe, no original/model/simulation acceptance."""
import asyncio
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

OUT = Path(__file__).resolve().parent / 'native-grammar'
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


async def main():
    settings = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf8'))['local_implementation_agent']
    model = settings['preferred_models']['reasoning']
    assert model == 'llama3.1:8b' and settings['enabled_models'] == [model]
    assert settings['preferred_models']['fallback'] is None
    # Reuse the established dynamic main-worker-only admission reader. It asserts idle.
    admission = json.loads(subprocess.check_output([sys.executable, str(OUT.parents[1] / 'read_provider.py')], text=True))
    save('admission.json', admission)
    prepared, target, schema, _ = batch_case(8)
    messages = [{'role': 'system', 'content': 'This is a synthetic grammar counterprobe, never a real hardware design. Return only JSON matching the supplied schema.'},
                {'role': 'user', 'content': json.dumps({'instruction':
                    'Produce each of these eight independent synthetic sensor decisions in inventory_choices under its exact name. '
                    'Use quantity1, the offered distinct ID, the one source fact, empty field_references and member bindings, '
                    'null owner/context/purpose, empty contained_device_ids. Short rationale. All eight slots required. '
                    'devices=[], unresolved=[], inventory_complete=true. No physical or safety qualification is claimed.',
                    'target': target, 'synthetic_source_fact': prepared['facts'][target['fact_id']]}, ensure_ascii=False)}]
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
    rows = r._reference_expand_inventory_choices([], value['inventory_choices'], inventory_target=target)
    rows = ReferenceDesignProposal.model_validate({'devices': rows}).model_dump(mode='json')['devices']
    rows = r._reference_scoped_inventory_delta([], rows, inventory_target=target)
    merged = r._reference_merge_inventory_devices([], rows, target, prepared['facts'])
    assert len(merged) == len({row['id'] for row in merged}) == 8
    assert [row['name'] for row in merged] == target['names']
    assert value['inventory_complete'] is True and r._reference_inventory_progress([], merged)
    result = {'status': 'PASS', 'model': model, 'actual_inference_requests': 1, 'native_devices': len(merged),
              'schema_and_public_validation_and_scoped_merge': True,
              'source_code_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
              'original_acceptance': False, 'simulation_acceptance': False,
              'metrics': {key: body.get(key) for key in ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration', 'total_duration')}}
    save('result.json', result)
    print(json.dumps(result), flush=True)


asyncio.run(main())
