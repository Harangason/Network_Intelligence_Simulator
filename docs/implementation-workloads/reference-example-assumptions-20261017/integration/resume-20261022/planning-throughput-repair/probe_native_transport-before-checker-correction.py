"""Sequential local native transport/grammar controls, never project acceptance."""
import asyncio
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_planning_throughput import context_with_repeated_records, unpack_context_message, existing_batch_fixture
from jsonschema import Draft202012Validator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--final', action='store_true')
parser.add_argument('--anchored', action='store_true')
args = parser.parse_args()
args.final = args.final or args.anchored
OUT = Path(__file__).resolve().parent / ('native-anchored-transport' if args.anchored else 'native-final-transport' if args.final else 'native-transport')
assert not OUT.exists(), 'Do not duplicate an uncertain native request.'
OUT.mkdir()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def get(url, payload=None, project=None):
    raw = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(url, data=raw, headers={'Content-Type': 'application/json', **({'X-Project-ID': project} if project else {})}), timeout=20) as response:
        return json.load(response)


def current_worker():
    command = "@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip() or '[]')
    rows = [rows] if isinstance(rows, dict) else rows
    assert len(rows) <= 1
    return [{'process': row, 'slots': get('http://127.0.0.1:' + re.search(r'--port\s+(\d+)', row['CommandLine']).group(1) + '/slots')} for row in rows]


async def main():
    worker = current_worker()
    assert all(not slot['is_processing'] for row in worker for slot in row['slots'])
    occupancy = {}
    for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
        draft = get('http://127.0.0.1:13500/api/engineering/agent/project-draft', project=project)
        conversation = get('http://127.0.0.1:13500/api/engineering/agent/conversation', project=project)
        assert draft.get('data') is None
        assert not any((conversation.get('data') or {}).get(key) for key in ('active_workload', 'active_proposal'))
        occupancy[project] = {'draft': draft, 'conversation': conversation}
    details = get('http://127.0.0.1:11434/api/show', {'model': 'qwen3.8:27b'})
    assert str(details['details']['family']).startswith('qwen') and not details.get('remote_host') and not details.get('remote_model')
    save('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'workers': worker,
                           'provider_ps': get('http://127.0.0.1:11434/api/ps'), 'product_project_point_observations': occupancy,
                           'peer_cursor': 'feeceba5-4dfa-4a35-bb19-db39e2a27afe:12', 'owner': 'NIS'})
    instance = reasoner.LocalEngineeringReasoner()
    assert instance.model == 'qwen3.8:27b' and instance.context_tokens == 131072 and instance.client.timeout.read == 1200
    results, history, previous, anchor = [], [], None, None
    context = context_with_repeated_records()
    system = ('Local native lossless transport control, no model writes. Read the complete context. '
              'Return only JSON with id, name, owner, source and quantity for the device selected by query_index. '
              'source is the entire original_source verbatim. quantity is the selected record quantity. '
              + ('context is the entire source_context list of the selected record, resolving all exact copies. ' if args.final else '')
              + '/no_think')
    schema = {'type': 'object', 'additionalProperties': False,
              'properties': {**{key: {'type': 'string'} for key in ('id', 'name', 'owner', 'source')}, 'quantity': {'type': 'integer'}},
              'required': ['id', 'name', 'owner', 'source', 'quantity']}
    if args.final:
        schema['properties']['context'] = {'type': 'array', 'items': {'type': 'string'}}
        schema['required'].append('context')
    async def call(name, messages, output_schema):
        payload = {'model': instance.model, 'messages': messages, 'format': output_schema, 'think': False,
                   'stream': True, 'keep_alive': instance.keep_alive,
                   'options': {'temperature': 0, 'num_predict': 8192, 'num_ctx': reasoner._reference_context_window(messages, 131072)}}
        save(name + '-request.json', payload)
        def progress(event):
            with (OUT / 'events.ndjson').open('a', encoding='utf8') as handle:
                handle.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), 'case': name, **event}) + '\n')
            observation = OUT / (name + '-worker.json')
            if event['request_state'] == 'RECEIVING_OUTPUT' and not observation.exists():
                save(observation.name, current_worker())
        body = await reasoner._reference_stream_response(instance.client, instance.chat_url, payload, progress)
        save(name + '-response.json', body)
        assert body.get('done_reason') != 'length'
        value = json.loads(body['message']['content'])
        Draft202012Validator(output_schema).validate(value)
        results.append({'case': name, 'prompt_eval_count': body.get('prompt_eval_count'), 'eval_count': body.get('eval_count'),
                        **{key: body.get(key) for key in ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')}})
        return body, value
    try:
        for index in ((79, 3, 7) if args.final else (79, 3)):
            current = {**deepcopy(context), 'query_index': index}
            if args.anchored:
                current['diagnostic_whitespace'] = ' ' * 88000
                current['diagnostic_cursor'] = {79: 'a', 3: 'b', 7: 'c'}[index] * 6000
            elif args.final:
                # A lossless, compressible synthetic field makes the ordinary
                # byte guard rebase on change without changing any model cap.
                current['diagnostic_whitespace'] = ' ' * (90001 if index == 7 else 90000)
            messages, _, rebased = reasoner._reference_context_messages(history, previous, current, system, 131072, anchor=anchor)
            assert unpack_context_message(json.loads(messages[1]['content'])) == (current if rebased or not previous else previous)
            if history and index != 7:
                assert messages[:len(history)] == history and not rebased
            if index == 7:
                assert rebased
                if args.anchored:
                    assert messages[:len(anchor[0])] == anchor[0] and len(messages) == len(anchor[0]) + 1
                else:
                    assert len(messages) == 2
            body, value = await call('transport-' + str(index), messages, schema)
            row = context['current_candidate']['devices'][index]
            expected = {'id': row['id'], 'name': row['name'], 'owner': row['owner_device_id'],
                        'source': context['original_source'], 'quantity': row['quantity']}
            if args.final:
                expected['context'] = row['source_context']
            assert value == expected, value
            history = [*deepcopy(messages), {'role': 'assistant', 'content': body['message']['content']}]
            previous = current
            if args.anchored and anchor is None:
                anchor = (deepcopy(history), deepcopy(current))
            if args.anchored and index in (3, 7):
                observed = json.loads((OUT / ('transport-' + str(index) + '-worker.json')).read_text(encoding='utf8'))
                assert any(slot['n_prompt_tokens_cache'] > 0 for row in observed for slot in row['slots']), observed
        prepared, known, fact, choices, native_schema, base = existing_batch_fixture()
        known = known[:2]
        native_schema = reasoner._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
        messages = [{'role': 'system', 'content': 'Synthetic local grammar control. Bind BOTH supplied existing participants to the supplied functional fact, with concise rationale and empty field_references. No NEW hardware. inventory_complete=true, all public arrays empty. /no_think'},
                    {'role': 'user', 'content': json.dumps({'known': known, 'functional_fact': fact}, ensure_ascii=False)}]
        body, value = await call('two-existing', messages, native_schema)
        assert {row['device_id'] for row in value['inventory_choices']} == {row['id'] for row in known}
        expanded = reasoner._reference_expand_inventory_choices(known, value['inventory_choices'])
        scoped = reasoner._reference_scoped_inventory_delta(known, expanded, derivation_fact_ids=[fact])
        merged = reasoner._reference_merge_inventory_devices(known, scoped, {'derivation_fact_ids': [fact], 'minimum_rows': 0}, prepared['facts'])
        assert all(fact in row['source_fact_ids'] for row in merged)
        for old, new in zip(known, merged, strict=True):
            assert all(old[key] == new[key] for key in old if key not in ('source_fact_ids', 'field_references', 'rationale'))
        if args.final:
            from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
            ports = [{'id': f'port-{index}', 'device_id': f'participant-{index}', 'technology': 'can', 'role': 'LOCAL',
                      'network_scope': 'synthetic-can', 'parameters': {}, 'rationale': 'Synthetic native parameter probe',
                      'field_references': {}} for index in range(4)]
            selected = tuple(row['id'] for row in ports)
            output_schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=selected)
            messages = [{'role': 'system', 'content': 'Local synthetic four-port parameter control; no project writes. '
                         'Return exactly all supplied ports with identical id/device_id/technology/role/network_scope. '
                         'Set only parameters.bitrate_bps=500000, concise rationale, empty field_references. '
                         'All other proposal arrays empty. No measured or hardware evidence. /no_think'},
                        {'role': 'user', 'content': json.dumps({'ports': ports, 'registered_can': registry.profile('can')}, ensure_ascii=False)}]
            body, value = await call('four-ports', messages, output_schema)
            parsed = intake.ReferenceDesignProposal.model_validate(value).model_dump(mode='json')
            merged_ports = reasoner._reference_merge_port_parameters(ports, parsed['ports'], selected)
            assert all(row['parameters'] == {'bitrate_bps': 500000} for row in merged_ports)
            for port in merged_ports:
                review = registry.validate_parameters('can', port['parameters'])
                assert review['status'] == 'VALID' and not review['findings']
        save('result.json', {'status': 'PASS', 'cases': results, 'original_acceptance': False,
                             'provider_after': current_worker(), 'application_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()})
        print(json.dumps({'status': 'PASS', 'cases': len(results), 'original_acceptance': False}))
    finally:
        await instance.client.aclose()


asyncio.run(main())
