"""Two sequential real small-model counters; authored source, no model writes."""
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
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import ReferenceDesignProposal, document_response_json
from backend.tests.test_reference_inventory_closure import closure_case

DIR = Path(__file__).resolve().parent
GOAL = DIR.parent
OUT = DIR / 'native-counter-02'
MODEL = 'qwen3.5:9b'


def save(folder, name, value):
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    authorization = GOAL / 'human-small-model-decision-20261107.json'
    decision = json.loads(authorization.read_text(encoding='utf-8'))
    assert decision['verified_directly'] is True and MODEL in decision['human_message']
    settings = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf-8'))['local_implementation_agent']
    assert settings['preferred_models']['fallback'] is None
    OUT.mkdir(exist_ok=False)
    save(OUT, 'authorization.json', {'path': str(authorization), 'sha256': hashlib.sha256(authorization.read_bytes()).hexdigest(), 'model': MODEL})
    results = []
    for mode in ('closed', 'missing-last-instance'):
        folder = OUT / mode
        folder.mkdir()
        admission = json.loads(subprocess.check_output([
            sys.executable, str(GOAL / 'read_provider.py'), '--model', MODEL], text=True))
        assert admission['loaded_models'] in ([], [MODEL]) and admission['busy_slots'] == 0
        save(folder, 'admission.json', admission)
        prepared, complete, target = closure_case()
        known = complete if mode == 'closed' else complete[:-1]
        if mode != 'closed':
            target.update(names=[complete[-1]['name']], minimum_rows=1)
        schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=known)
        context = {'original_source': prepared['source_evidence']['source_text'],
                   'planning_stage': 'Authored finite source-inventory counter',
                   'original_facts': prepared['facts'], 'inventory_target_for_this_stage': target,
                   'current_candidate': {'devices': known},
                   'existing_inventory_for_this_stage': [{key: row[key] for key in ('id', 'name', 'kind')} for row in known],
                   'instruction': ('The three source instances are already fully bound. Return inventory_choices=[] and inventory_complete=true. '
                       'No new identity, no repeated binding.' if mode == 'closed' else
                       'Supply the one missing original sensor under its requested literal name, using the offered fresh ID. '
                       'Preserve both existing instances. Use null owner, null purpose, empty field_references, a short rationale and inventory_complete=true.')
                       + ' Keep devices=[] and unresolved=[]. This is an authored counter, not a real hardware qualification.'}
        messages, _, _ = r._reference_context_messages([], None, context,
            'Independent native decoder counter. Return JSON matching the supplied normal product schema.', 131072)
        payload = dict(model=MODEL, messages=messages, format=schema, think=False, stream=True,
                       keep_alive='10m', options=dict(temperature=0, num_predict=8192,
                           num_ctx=r._reference_context_window(messages, 131072)))
        save(folder, 'request.json', payload)
        with (folder / 'events.ndjson').open('w', encoding='utf-8') as events, (folder / 'raw-provider-stream.ndjson').open('wb') as raw:
            def progress(value):
                events.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value}) + '\n')
                events.flush()
            class Capture(httpx.AsyncByteStream):
                def __init__(self, stream): self.stream = stream
                async def __aiter__(self):
                    async for chunk in self.stream:
                        raw.write(chunk); raw.flush()
                        yield chunk
                async def aclose(self): await self.stream.aclose()
            async def capture(response):
                save(folder, 'response-headers.json', {'status': response.status_code, 'headers': dict(response.headers)})
                response.stream = Capture(response.stream)
            async with httpx.AsyncClient(timeout=1200, trust_env=False, event_hooks={'response': [capture]}) as client:
                body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, progress)
        save(folder, 'response.json', body)
        assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == MODEL
        value = document_response_json(body['message']['content'])
        Draft202012Validator(schema).validate(value)
        assert value['inventory_complete'] is True and value['unresolved'] == []
        expanded = r._reference_expand_inventory_choices(known, value['inventory_choices'], inventory_target=target)
        public = ReferenceDesignProposal.model_validate({'devices': expanded}).model_dump(mode='json')['devices']
        delta = r._reference_scoped_inventory_delta(known, public, inventory_target=target)
        merged = r._reference_merge_inventory_devices(known, delta, target, prepared['facts'])
        assert len(merged) == 3 and merged[:len(known)] == known
        assert [row['name'] for row in merged] == [row['name'] for row in complete]
        assert len({row['id'] for row in merged}) == 3
        assert len(delta) == (0 if mode == 'closed' else 1)
        assert r._reference_inventory_progress(known, merged) == (mode != 'closed')
        result = {'mode': mode, 'status': 'PASS', 'model': body['model'], 'new_devices': len(delta),
                  'preserved_existing_devices': len(known), 'final_devices': 3,
                  'metrics': {key: body.get(key) for key in ('prompt_eval_count', 'eval_count', 'total_duration')}}
        save(folder, 'result.json', result)
        results.append(result)
        print(json.dumps(result), flush=True)
    save(OUT, 'result.json', {'status': 'PASS', 'actual_inference_requests': 2, 'model': MODEL,
        'counters': results, 'schema_public_validation_scoped_merge_preserved': True,
        'source_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
        'original_acceptance': False, 'simulation_acceptance': False})


asyncio.run(main())
