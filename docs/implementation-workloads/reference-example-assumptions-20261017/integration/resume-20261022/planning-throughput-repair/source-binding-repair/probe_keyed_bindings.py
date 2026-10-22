"""One sequential native decoder control; never original-project acceptance."""
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
from backend.tests.test_reference_planning_throughput import existing_batch_fixture
from jsonschema import Draft202012Validator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boundary', action='store_true', help='Independent nine-ID counterprobe against the unchanged eight-ID bound.')
parser.add_argument('--ordered', action='store_true', help='Use the structurally bounded ordered-node decoder control.')
args = parser.parse_args()
OUT = Path(__file__).resolve().parent / (('native-ordered-boundary' if args.boundary else 'native-ordered-bindings') if args.ordered else ('native-keyed-boundary' if args.boundary else 'native-keyed-bindings'))
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def get(url, data=None, project=None):
    payload = None if data is None else json.dumps(data).encode()
    with urlopen(Request(url, data=payload, headers={'Content-Type': 'application/json',
            **({'X-Project-ID': project} if project else {})}), timeout=20) as response:
        return json.load(response)


def workers():
    command = "@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip() or '[]')
    rows = [rows] if isinstance(rows, dict) else rows
    assert len(rows) <= 1
    return [{'process': row, 'slots': get('http://127.0.0.1:' + re.search(r'--port\s+(\d+)', row['CommandLine']).group(1) + '/slots')} for row in rows]


async def main():
    baseline = workers()
    assert all(not slot['is_processing'] for row in baseline for slot in row['slots'])
    occupancy = {}
    for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
        draft = get('http://127.0.0.1:13500/api/engineering/agent/project-draft', project=project)
        conversation = get('http://127.0.0.1:13500/api/engineering/agent/conversation', project=project)
        assert draft.get('data') is None
        assert not any((conversation.get('data') or {}).get(key) for key in ('active_workload', 'active_proposal'))
        occupancy[project] = {'draft': draft, 'conversation': conversation}
    details = get('http://127.0.0.1:11434/api/show', {'model': 'qwen3.8:27b'})
    assert str(details['details']['family']).startswith('qwen') and not details.get('remote_host')
    save('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'main_workers': baseline,
        'product_point_observations': occupancy, 'provider_ps': get('http://127.0.0.1:11434/api/ps'),
        'peer_cursor': 'feeceba5-4dfa-4a35-bb19-db39e2a27afe:12', 'owner': 'NIS'})
    instance = reasoner.LocalEngineeringReasoner()
    assert instance.model == 'qwen3.8:27b' and instance.context_tokens == 131072 and instance.client.timeout.read == 1200
    prepared, known, fact, _, _, _ = existing_batch_fixture()
    known = known[:9 if args.boundary else 2]
    other = 'F-independent-second-function'
    prepared['facts'][other] = deepcopy(prepared['facts'][fact])
    prepared['fact_id_map'][other] = 'independent-source-identity-second-function'
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'},
        derivation_fact_ids=[fact, other], existing_devices=known)
    messages = [{'role': 'system', 'content': 'Local NIS private decoder counterprobe, no project writes. Return only schema JSON. '
        'Return inventory_complete=true, inventory_choices containing one EXISTING_BATCH. '
        + ('bindings is a node with exactly ONE existing ID key. Its value has source_fact_ids, rationale, field_references and following. '
           'following is null or the next one-ID node. Select IDs in the given existing_ids order, no duplicates. '
           'For the nine-ID counterprobe the user requests all9 but the native limit8takes precedence: use exactly8 nodes, eighth following=null. '
           if args.ordered else 'Its bindings object must contain each requested existing device ID exactly once. ')
        +
        'For each ID combine BOTH requested source_fact_ids in one list and give one short rationale sentence and field_references={}. '
        'No NEW hardware. All other model lists empty. /no_think'},
        {'role': 'user', 'content': json.dumps({'existing_ids': [row['id'] for row in known],
            'requested_source_fact_ids': [fact, other], 'source': 'Two independent functional obligations share two known processors.'}, ensure_ascii=False)}]
    payload = {'model': instance.model, 'messages': messages, 'format': schema, 'think': False,
        'stream': True, 'keep_alive': instance.keep_alive, 'options': {'temperature': 0, 'num_predict': 8192,
            'num_ctx': reasoner._reference_context_window(messages, instance.context_tokens)}}
    source_hash = hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()
    save('request.json', payload)
    def progress(event):
        with (OUT / 'events.ndjson').open('a', encoding='utf8') as stream:
            stream.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), **event}) + '\n')
        if event['request_state'] == 'RECEIVING_OUTPUT' and not (OUT / 'active-worker.json').exists():
            save('active-worker.json', workers())
    try:
        body = await reasoner._reference_stream_response(instance.client, instance.chat_url, payload, progress)
        save('response.json', body)
        assert body.get('done_reason') != 'length'
        value = intake.document_response_json(body['message']['content'])
        Draft202012Validator(schema).validate(value)
        assert value['inventory_complete'] is True
        choices = value['inventory_choices']
        assert len(choices) == 1 and choices[0]['choice_kind'] == 'EXISTING_BATCH'
        if args.ordered:
            selected, node = {}, choices[0]['bindings']
            while node is not None:
                assert isinstance(node, dict) and len(node) == 1
                identity, fields = next(iter(node.items()))
                assert identity not in selected
                selected[identity] = {key: item for key, item in fields.items() if key != 'following'}
                node = fields['following']
            if args.boundary:
                assert len(selected) == 8
        else:
            selected = choices[0]['bindings']
        if args.boundary:
            assert 1 <= len(selected) <= 8, 'Native schema allowed more than eight binding keys.'
            assert set(selected) <= {row['id'] for row in known}
        else:
            assert set(selected) == {row['id'] for row in known}
        assert all(set(row['source_fact_ids']) == {fact, other} for row in selected.values())
        expanded = reasoner._reference_expand_inventory_choices(known, choices)
        assert {row['id'] for row in expanded} == set(selected)
        assert all(row['name'] == next(old['name'] for old in known if old['id'] == row['id']) for row in expanded)
        assert source_hash == hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()
        save('result.json', {'status': 'PASS', 'at_utc': datetime.now(timezone.utc).isoformat(),
            'actual_native_responses': 1, 'identities': len(expanded), 'fact_bindings': 2 * len(expanded), 'local_reasoner_sha256': source_hash,
            'nine_id_boundary_counterprobe': args.boundary,
            'numeric_limits_unchanged': True, 'after_workers': workers(),
            'original_acceptance': False, 'canonical_writes': False})
        print(f'PASS: actual native keyed{len(expanded)} identities/{2 * len(expanded)} fact bindings; no original acceptance', flush=True)
    finally:
        await instance.client.aclose()


asyncio.run(main())
