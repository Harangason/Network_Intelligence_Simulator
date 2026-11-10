"""Authored stage-switch counter; no original acceptance or model writes."""
import argparse
import asyncio
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
from backend.tests.test_reference_port_intent_allocation import prepared_schema
from backend.tests.test_reference_reasoner import effective_reference_context

OUT_ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--focus-control', action='store_true')
parser.add_argument('--history-rounds', type=int, default=0)
args = parser.parse_args()
OUT = OUT_ROOT / args.name
assert OUT.parent == OUT_ROOT


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


async def main():
    OUT.mkdir(exist_ok=False)
    prepared, _ = prepared_schema()
    owners = ('controller-a', 'controller-b', 'controller-c', 'controller-offline')
    source = ('Independent authored test, not real hardware: controller-a requires exactly two parallel physical CAN '
              'connections to bench-a; controller-b requires one physical CAN connection to bench-b; '
              'controller-c requires one physical CAN connection to bench-c. All use LOCAL role. '
              'controller-offline performs local computation only and explicitly has no physical network connections. '
              'These are synthetic planning requirements, never physical qualification evidence.')
    context = {'original_source': source, 'original_facts': prepared['facts'],
        'planning_stage': 'Inventar der deklarierten Teilnehmer',
        'inventory_target_for_this_stage': {'fact_id': 'authored-inventory', 'names': list(owners)},
        'derivation_fact_ids_for_this_stage': None, 'output_fields_for_this_stage': ['devices'],
        'device_ids_for_this_stage': [], 'port_ids_for_this_stage': [],
        'function_fact_ids_for_this_stage': [], 'producer_device_ids_for_this_stage': [],
        'current_candidate': intake.ReferenceDesignProposal().model_dump(mode='json'),
        'instruction': 'Inventory only. All model arrays except devices remain empty. No ports in this inventory stage.'}
    system = 'Independent NIS native stage-switch test. Follow the current planning stage and the complete authored source; return only schema-valid JSON.'
    messages, _, _ = r._reference_context_messages([], None, context, system, 131072)
    # Explicitly authored prior replies, not claimed native generations or original evidence.
    devices = [{'id': owner, 'name': owner, 'kind': 'CONTROLLER', 'quantity': 1,
                'source_fact_ids': [], 'source_member_bindings': {}, 'owner_device_id': None,
                'context_kind': None, 'contained_device_ids': [], 'purpose': source,
                'rationale': 'Authored counter participant.', 'field_references': {}} for owner in owners]
    previous = deepcopy(context)
    prior_reply = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'devices': devices}
    history = [*messages, {'role': 'assistant', 'content': json.dumps(prior_reply, ensure_ascii=False)}]
    for index in range(args.history_rounds):
        following = deepcopy(previous)
        following['current_candidate']['devices'] = [*devices, *[
            {**deepcopy(devices[0]), 'id': f'authored-other-{n}', 'name': f'authored-other-{n}',
             'purpose': 'Independent additional inventory participant; its demand is outside the selected four-device group.'}
            for n in range((index + 1) * 8)]]
        following['inventory_target_for_this_stage']['names'] = [f'authored-other-{n}' for n in range(index*8, (index+1)*8)]
        continuation, _, _ = r._reference_context_messages(history, previous, following, system, 131072)
        reply = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
                 'devices': following['current_candidate']['devices'][-8:]}
        history = [*continuation, {'role': 'assistant', 'content': json.dumps(reply, ensure_ascii=False)}]
        previous = following
    current = deepcopy(context)
    current.update(planning_stage='Vollständiger Anschlussbedarf der ausgewählten Teilnehmer',
        inventory_target_for_this_stage=None, output_fields_for_this_stage=['ports'],
        device_ids_for_this_stage=list(owners),
        instruction='For ALL four selected devices now return complete physical port_groups_by_device and port_plan_complete=true. '
        'Preserve the exact authored connection counts and network scopes from original_source. '
        'parameters remains {}; use technology can, role LOCAL and empty field_references. '
        'Empty connections is correct ONLY for the explicitly offline participant. All ordinary model arrays remain empty.')
    current['current_candidate']['devices'] = previous['current_candidate']['devices'] if args.history_rounds else devices
    messages, _, _ = r._reference_context_messages(history, previous, current, system, 131072)
    assert effective_reference_context(messages) == current
    if args.focus_control:
        wire = json.loads(messages[-1]['content'])
        wire['nis_current_selection'] = {key: deepcopy(current[key]) for key in
            ('planning_stage', 'output_fields_for_this_stage', 'instruction', 'device_ids_for_this_stage',
             'port_ids_for_this_stage', 'function_fact_ids_for_this_stage', 'producer_device_ids_for_this_stage')}
        messages[-1]['content'] = json.dumps(wire, ensure_ascii=False, separators=(',', ':'))
        assert effective_reference_context(messages) == current
    schema = r._reference_schema_for_stage(prepared, {'ports'}, port_groups=True, device_ids=owners)
    payload = {'model': 'qwen3.5:9b', 'messages': messages, 'format': schema, 'think': False,
        'stream': True, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
            'num_ctx': r._reference_context_window(messages, 131072)}}
    save('context.json', current)
    save('request.json', payload)
    save('admission.json', json.loads(subprocess.check_output([sys.executable, str(OUT_ROOT.parent/'read_provider.py'),
         '--model', 'qwen3.5:9b'], text=True)))
    with (OUT/'events.ndjson').open('w', encoding='utf8') as log:
        def report(value):
            log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value})+'\n'); log.flush()
        async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
            body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
    save('response.json', body)
    value = intake.document_response_json(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    ports = r._reference_expand_port_groups([], value['port_groups_by_device'], owners, value['port_plan_complete'])
    counts = {owner: sum(p['device_id'] == owner for p in ports) for owner in owners}
    expected = dict(zip(owners, (2, 1, 1, 0)))
    correct = counts == expected and all(p['technology'] == 'can' and p['role'] == 'LOCAL'
        and p['network_scope'] == 'bench-'+p['device_id'].rsplit('-', 1)[-1] for p in ports)
    result = {'status': 'PASS' if correct else 'FAIL', 'counts': counts, 'expected': expected,
        'focus_control': args.focus_control, 'actual_inference_requests': 1,
        'authored_history_rounds': args.history_rounds,
        'authored_prior_replies': True, 'original_acceptance': False, 'canonical_writes': False,
        'source_sha256': hashlib.sha256((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
        'metrics': {k: body.get(k) for k in ('prompt_eval_count','eval_count','prompt_eval_duration','eval_duration','total_duration')}}
    save('result.json', result); print(json.dumps(result), flush=True)
    assert correct, counts


asyncio.run(main())
