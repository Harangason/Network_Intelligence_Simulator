"""Actual small-model ownership grammar probes; authored data, no original acceptance."""
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
from backend.tests.test_reference_owner_evidence_schema import owner_case, expanded
from backend.nis.agent.orchestration import local_reasoner as r, project_intake as intake
from backend.nis.agent.orchestration.reference_token_budget import ReferenceTokenBudget

OUT = Path(__file__).resolve().parent / 'native-grammar'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    OUT.mkdir(exist_ok=False)
    async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
        ps = (await client.get('http://127.0.0.1:11434/api/ps')).json()
        save('before-loaded-models.json', ps)
        if not ps.get('models'):
            warm = await client.post('http://127.0.0.1:11434/api/generate', json={
                'model': 'qwen3.5:9b', 'stream': False, 'keep_alive': '10m',
                'options': {'num_ctx': 131072, 'num_predict': 0}})
            warm.raise_for_status()
            save('empty-load.json', warm.json())
        results = []
        for kind in ('SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT'):
            admission = json.loads(subprocess.check_output([
                sys.executable, str(OUT.parent.parent / 'read_provider.py'), '--model', 'qwen3.5:9b'],
                encoding='utf-8'))
            save(kind + '-admission.json', admission)
            prepared, controller, target, schema, codec, _ = owner_case(kind, False, compact=True)
            messages = [
                {'role': 'system', 'content': 'Authored isolated grammar counterprobe. Return only JSON under the supplied schema. No real hardware or simulation acceptance.'},
                {'role': 'user', 'content': json.dumps({
                    'instruction': 'Resolve both offered slots as NEW_' + kind + '. First slot has no owner: owner_device_id=null; field_references={device_type:[]}. '
                    'Second slot is owned by the existing controller C, with field_references={function_hosts:[owner-review]}. '
                    'Select the complete alternative matching each owner. Preserve all offered identities and sources. '
                    'Short rationale; no additional purpose, containment or physical assertions. If required, context_kind=PASSIVE. '
                    'devices=[], unresolved=[], inventory_complete=true.',
                    'target': target, 'existing_controller': controller,
                    'source_fact': prepared['facts'][target['fact_id']],
                    'authorized_reference': prepared['reference_sources']['owner-review']}, ensure_ascii=False)}]
            budget = ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'qwen3.5:9b',
                                          131072, bridge_url='http://127.0.0.1:13503/tokenize-chat')
            payload = {'model': 'qwen3.5:9b', 'messages': messages, 'format': schema, 'think': False,
                       'stream': True, 'keep_alive': '10m', 'options': {
                           'temperature': 0, 'num_predict': 8192, 'num_ctx': await budget.admit(messages)}}
            save(kind + '-request.json', payload)
            with (OUT / (kind + '-events.ndjson')).open('w', encoding='utf-8') as log:
                def progress(value):
                    log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value}) + '\n')
                    log.flush()
                response = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, progress)
            save(kind + '-response.json', response)
            assert response['done'] is True and response.get('done_reason') != 'length'
            assert response['model'] == 'qwen3.5:9b'
            value = intake.document_response_json(response['message']['content'])
            Draft202012Validator(schema).validate(value)
            normalized = intake.ReferenceDesignProposal.model_validate(
                expanded(prepared, controller, target, codec, value)).model_dump(mode='json')
            findings = intake._validate_reference_inventory(normalized, prepared, (), partial=True)
            first, second = normalized['devices'][1:]
            assert first['owner_device_id'] is None and 'function_hosts' not in first['field_references']
            assert second['owner_device_id'] == 'C' and second['field_references'] == {'function_hosts': ['owner-review']}
            assert [row['name'] for row in (first, second)] == target['names']
            assert len({row['id'] for row in normalized['devices']}) == 3
            assert all(row['source_fact_ids'] == [target['fact_id']] and row['kind'] == kind for row in (first, second))
            save(kind + '-validated.json', {'proposal': normalized, 'partial_inventory_findings': findings})
            results.append({'kind': kind, 'status': 'PASS', 'metrics': {key: response.get(key) for key in
                            ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration', 'total_duration')}})
            print(json.dumps(results[-1]), flush=True)
        save('result.json', {'status': 'PASS', 'cases': results, 'model': 'qwen3.5:9b',
                            'actual_generation_requests': 3, 'original_acceptance': False, 'canonical_writes': False,
                            'source_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()})


asyncio.run(main())
