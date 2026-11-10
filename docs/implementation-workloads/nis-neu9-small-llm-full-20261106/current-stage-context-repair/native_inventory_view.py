"""Authored 251-record context comprehension counter, never Original acceptance."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import httpx
from jsonschema import Draft202012Validator
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.reference_token_budget import ReferenceTokenBudget
from backend.tests.test_reference_current_stage_context import authored_port_context
from backend.tests.test_reference_reasoner import effective_reference_context

OUT = Path(__file__).resolve().parent / 'native-inventory-view'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    OUT.mkdir(exist_ok=False)
    admission = json.loads(subprocess.check_output([sys.executable, str(OUT.parent.parent / 'read_provider.py'),
        '--model', 'qwen3.5:9b'], encoding='utf-8'))
    save('admission.json', admission)
    context = authored_port_context()
    # This is intentionally a reader counter, not a planner or hand-written
    # Original model. The synthetic records are only inputs to a comprehension check.
    context['planning_stage'] = 'Read the actual current inventory; do not generate a model'
    context['instruction'] = ('Report the actual current inventory counts by kind, the exact selected IDs, '
        'and whether actual existing actuators are missing. Describe whether the stored UNKNOWN_PHY '
        'finding is still unresolved. Do not fill any missing data or generate hardware or ports.')
    before = json.dumps(context, ensure_ascii=False, sort_keys=True)
    save('authored-context.json', context)
    schema = {'type': 'object', 'properties': {
        'counts': {'type': 'object', 'properties': {kind: {'type': 'integer', 'minimum': 0}
            for kind in ('CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR')},
            'required': ['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR'], 'additionalProperties': False},
        'selected_ids': {'type': 'array', 'items': {'type': 'string'}},
        'existing_actuators_missing': {'type': 'boolean'},
        'unknown_phy_still_open': {'type': 'boolean'}},
        'required': ['counts', 'selected_ids', 'existing_actuators_missing', 'unknown_phy_still_open'],
        'additionalProperties': False}
    async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
        budget = ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'qwen3.5:9b', 131072)
        messages, _, _ = await budget.select(r._reference_context_messages, [], None, context,
            'Read the supplied synthetic NIS context exactly; answer only the requested factual JSON.', 131072)
        assert effective_reference_context(messages) == context
        payload = {'model': 'qwen3.5:9b', 'messages': messages, 'format': schema, 'stream': True,
            'think': False, 'keep_alive': '10m',
            'options': {'temperature': 0, 'num_predict': 8192, 'num_ctx': await budget.admit(messages)}}
        save('request.json', payload)
        with (OUT / 'events.ndjson').open('w', encoding='utf-8') as log:
            def progress(event):
                log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **event}) + '\n'); log.flush()
            body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, progress)
        save('response.json', body)
        await budget.verify_response(messages, body)
        decoded = json.loads(body['message']['content'])
        Draft202012Validator(schema).validate(decoded)
        assert decoded['counts'] == {'CONTROLLER': 50, 'GATEWAY': 1, 'SENSOR': 100, 'ACTUATOR': 100}
        assert decoded['selected_ids'] == context['device_ids_for_this_stage']
        assert decoded['existing_actuators_missing'] is False
        assert decoded['unknown_phy_still_open'] is True
        assert json.dumps(context, ensure_ascii=False, sort_keys=True) == before
        assert body['done'] is True and body['done_reason'] == 'stop'
        save('result.json', {'status': 'PASS', 'actual_response': decoded,
            'model': 'qwen3.5:9b', 'prompt_tokens': body['prompt_eval_count'], 'output_tokens': body['eval_count'],
            'reasoner_sha256': hashlib.sha256((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
            'canonical_writes': False, 'original_acceptance': False, 'simulation_acceptance': False})
        print(json.dumps(decoded), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
