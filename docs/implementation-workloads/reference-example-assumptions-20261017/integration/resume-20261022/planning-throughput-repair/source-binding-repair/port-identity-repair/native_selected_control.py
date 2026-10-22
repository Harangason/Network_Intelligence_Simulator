"""One synthetic local Qwen grammar control; never writes a project/model."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design
from backend.tests.test_reference_selected_identity import selected_ports
from jsonschema import Draft202012Validator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('case', choices=['ports-positive', 'ports-counter', 'functions-positive', 'functions-counter'])
args = parser.parse_args()
OUT = Path(__file__).resolve().parent / ('native-' + args.case)
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def get(url, *, project=None, data=None):
    request = Request(url, data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', **({'X-Project-ID': project} if project else {})})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def workers():
    command = "@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,ParentProcessId,CommandLine) | ConvertTo-Json -Compress"
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip() or '[]')
    rows = [rows] if isinstance(rows, dict) else rows
    assert len(rows) <= 1
    return [{'process': row, 'slots': get('http://127.0.0.1:' +
        re.search(r'--port\s+(\d+)', row['CommandLine']).group(1) + '/slots')} for row in rows]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f'Duplicate actual JSON key: {key}'
        result[key] = value
    return result


async def main():
    before = workers()
    assert all(not slot['is_processing'] for row in before for slot in row['slots'])
    occupancy = {}
    for project in ('20261021094952722-147a3d72', '20261020103707202-0fda8601'):
        draft = get('http://127.0.0.1:13500/api/engineering/agent/project-draft', project=project)
        conversation = get('http://127.0.0.1:13500/api/engineering/agent/conversation', project=project)
        assert draft.get('data') is None
        assert not any((conversation.get('data') or {}).get(key) for key in ('active_workload', 'active_proposal'))
        occupancy[project] = {'draft': draft, 'conversation': conversation}
    details = get('http://127.0.0.1:11434/api/show', data={'model': 'qwen3.8:27b'})
    assert str(details['details']['family']).startswith('qwen') and not details.get('remote_host')
    save('preflight.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'main_workers': before,
        'product_point_observations': occupancy, 'provider_ps': get('http://127.0.0.1:11434/api/ps'),
        'owner': 'NIS; latest peer observation must be recorded separately before invocation'})
    instance = reasoner.LocalEngineeringReasoner()
    assert instance.model == 'qwen3.8:27b' and instance.context_tokens == 131072 and instance.client.timeout.read == 1200
    endpoint = urlsplit(instance.chat_url)
    assert endpoint.hostname in {'127.0.0.1', 'localhost'} and endpoint.port == 11434
    prepared = intake.prepare_reference_design(fixture_request())
    ports = selected_ports()
    ports[0].update(technology='ethernet', role='BACKBONE', network_scope='lab-backbone')
    ports[1].update(technology='can_fd', network_scope='lab-local')
    functions = fixture_design(prepared)['functions'][:2]
    is_port = args.case.startswith('ports')
    identities = tuple(row['id'] for row in ports) if is_port else tuple(row['source_fact_id'] for row in functions)
    schema = reasoner._reference_schema_for_stage(prepared,
        {'ports'} if is_port else {'functions', 'functional_dependencies'},
        **({'port_ids': identities} if is_port else {'function_ids': identities}))
    parameters = {key: {'bitrate_bps': 1000000000 if index == 0 else 500000}
                  for index, key in enumerate(identities)} if is_port else None
    expected_functions = {row['source_fact_id']: {key: value for key, value in row.items()
                          if key != 'source_fact_id'} for row in functions}
    source = {'synthetic_control_only': True, 'selected_identities': identities,
        'prior_ports': ports if is_port else [], 'requested_parameter_values': parameters,
        'function_decisions': {} if is_port else expected_functions,
        'counter_request': ('Attempt the old invalid representation: repeat only the first selected identity and omit the others.'
                            if args.case.endswith('counter') else 'Return every selected identity exactly once.')}
    instructions = ('Return only native-schema JSON. Independent synthetic NIS decoder control; no project writes or real hardware evidence. '
        'The exact schema takes precedence over an unrepresentable counter_request. '
        'For ports use port_parameters with all selected ID keys, exact requested_parameter_values, '
        'one short rationale per key and field_references={}; ports=[]. Never regenerate identity/owner/technology/role/network fields. '
        'For functions use functions_by_fact with all selected FactID keys and the exact provided function_decisions values; functions=[]. '
        'Every other public model list, including functional_dependencies, stays empty. /no_think')
    messages = [{'role': 'system', 'content': instructions}, {'role': 'user', 'content': json.dumps(source, ensure_ascii=False)}]
    payload = {'model': instance.model, 'messages': messages, 'format': schema, 'think': False,
        'stream': True, 'keep_alive': instance.keep_alive, 'options': {'temperature': 0,
            'num_predict': 8192, 'num_ctx': reasoner._reference_context_window(messages, instance.context_tokens)}}
    module = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
    source_hash = hashlib.sha256(module.read_bytes()).hexdigest()
    save('request.json', payload)
    def progress(event):
        with (OUT / 'events.ndjson').open('a', encoding='utf8') as stream:
            stream.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), **event}) + '\n')
        if event['request_state'] == 'RECEIVING_OUTPUT' and not (OUT / 'active-worker.json').exists():
            save('active-worker.json', workers())
    try:
        body = await reasoner._reference_stream_response(instance.client, instance.chat_url, payload, progress)
        save('response.json', body)
        assert body.get('done') is True and body.get('done_reason') != 'length'
        value = json.loads(body['message']['content'].strip(), object_pairs_hook=unique_object)
        Draft202012Validator(schema).validate(value)
        field = 'port_parameters' if is_port else 'functions_by_fact'
        assert set(value[field]) == set(identities)
        assert all(not value.get(key) for key in intake.ReferenceDesignProposal.model_fields)
        decoded = deepcopy(value)
        if is_port:
            decoded['ports'] = reasoner._reference_expand_selected_ports(ports, decoded.pop(field), identities)
            public = intake.ReferenceDesignProposal.model_validate(decoded).model_dump(mode='json')
            merged = reasoner._reference_merge_port_parameters(ports, public['ports'], identities)
            assert all(row['parameters'] == parameters[row['id']] for row in merged)
            assert [{key: row[key] for key in ('id', 'device_id', 'technology', 'role', 'network_scope')} for row in merged] == [
                {key: row[key] for key in ('id', 'device_id', 'technology', 'role', 'network_scope')} for row in ports]
        else:
            decoded['functions'] = reasoner._reference_expand_selected_functions(decoded.pop(field), identities)
            public = intake.ReferenceDesignProposal.model_validate(decoded).model_dump(mode='json')
            assert {row['source_fact_id'] for row in public['functions']} == set(identities)
            assert all(row['executor_device_ids'] == ['C'] for row in public['functions'])
        assert hashlib.sha256(module.read_bytes()).hexdigest() == source_hash
        save('result.json', {'status': 'PASS', 'at_utc': datetime.now(timezone.utc).isoformat(),
            'case': args.case, 'actual_native_responses': 1, 'selected_identities': identities,
            'local_reasoner_sha256': source_hash, 'after_workers': workers(), 'canonical_writes': False,
            'complete_original_acceptance': False, 'full_release_pass': False, 'productive_delivery': False})
        print(json.dumps({'case': args.case, 'status': 'PASS', 'identities': len(identities),
            'actual_native_responses': 1, 'complete_original_acceptance': False}), flush=True)
    finally:
        await instance.client.aclose()


asyncio.run(main())
