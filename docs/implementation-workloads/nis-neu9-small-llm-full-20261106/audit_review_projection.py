"""Controlled private-schema -> public -> actual Wizard review audit; NO INFERENCE."""
import asyncio
import argparse
import faulthandler
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx

out = Path(__file__).resolve().parent
root = out.parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', default='controlled-review')
parser.add_argument('--phase', choices=['semantics','coverage'], default='semantics')
parser.add_argument('--selection', choices=['all','required'], default='all')
args = parser.parse_args()
import re
assert re.fullmatch('[a-z0-9-]+', args.name)
faulthandler.dump_traceback_later(120, exit=True)
sys.path.insert(0, str(root))
goal = json.loads((out / 'workload.json').read_text(encoding='utf-8'))
source_path = Path(goal['source']['path'])
source = source_path.read_bytes().decode('utf-8')
assert hashlib.sha256(source.encode()).hexdigest() == goal['source']['sha256']
directory = out / ('function-coverage-repair' if args.phase=='coverage' else 'source-semantics-repair') / args.name
directory.mkdir(exist_ok=False)
os.environ['LOCAL_AI_MODEL'] = 'llama3.1:8b'
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, document_system_scope

position, last_start = 0, 0
fragments, payloads = [], []

def transport(request):
    global position, last_start
    if request.url.path.endswith('/show'):
        return httpx.Response(200, json={'details': {'family': 'llama', 'format': 'gguf'},
            'model_info': {'general.parameter_count': 8030261312}, 'capabilities': ['completion', 'tools']})
    assert request.url.path.endswith('/chat'), 'All requests are intercepted; external requests forbidden'
    payload = json.loads(request.content)
    data = json.loads(payload['messages'][1]['content'])
    fragment = ''.join(data['source_lines'].values())
    if 'validation_feedback' in data:
        assert fragments[-1] == fragment
        start = last_start
    else:
        start = position
        assert source[start:start + len(fragment)] == fragment
        last_start, position = start, start + len(fragment)
        fragments.append(fragment)
    units = {unit['source_ref']: unit for unit in document_component_sources(
        document_source_references(fragment), scope_prefix=source[:start])}
    schema = payload['format']['properties']
    claims = {}
    keys = schema['components']['required'] if args.selection=='required' else schema['components']['properties']
    for key in keys:
        branch = schema['components']['properties'][key]
        policy = units[key]['policy']
        if policy is None:
            kinds, roles = branch['properties']['kind']['enum'], branch['properties']['role']['enum']
            policy = {'kind': 'FUNCTION' if 'FUNCTION' in kinds else kinds[0],
                      'role': 'OTHER' if 'OTHER' in roles else roles[0], 'quantity': None}
        claims[key] = policy
    assert len(claims) <= 24
    assert payload['options']['num_ctx'] == 16384 and payload['options']['num_predict'] == 3000
    payloads.append(payload)
    wire = {'summary': 'CONTROLLED fake transport, not native acceptance.', 'components': claims,
            'technologies': {key: branch['enum'][0] for key, branch in schema['technologies']['properties'].items()},
            'proposed_task': 'Controlled review consistency; do not apply.', 'assumptions': [],
            'open_questions': ['Which concrete devices cover the source categories?']}
    return httpx.Response(200, json={'message': {'content': json.dumps(wire, ensure_ascii=False)}})

async def run():
    reasoner = LocalEngineeringReasoner()
    await reasoner.client.aclose()
    reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        return await reasoner.interpret_document(source, 'CONTROLLED-FAKE-TRANSPORT-NOT-NATIVE')
    finally:
        await reasoner.client.aclose()

proposal = asyncio.run(run())
assert ''.join(fragments) == source and position == len(source)
proposal_path = directory / 'controlled-proposal-NOT-NATIVE.json'
proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
adapter = root / 'docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261018/native_original_review_adapter.mjs'
raw = subprocess.check_output(['C:/Program Files/nodejs/node.exe', '--experimental-strip-types', str(adapter),
                              str(root), str(source_path), str(proposal_path)], cwd=root)
(directory / 'actual-product-review-projection.json').write_bytes(raw)
equipment = json.loads(raw)['equipment']
totals = {role: sum(row['quantity'] for row in equipment['devices'] if row['role'] == role)
          for role in ['SENSOR', 'ACTUATOR', 'CONTROLLER', 'GATEWAY']}
assert totals == {'SENSOR': 100, 'ACTUATOR': 100, 'CONTROLLER': 50, 'GATEWAY': 1}, totals
assert not any(any(token in row['label'] for token in ['MotorRPM', 'MotorCurrent', 'Gateway Load', 'Gateway Delay'])
               for row in equipment['questions'])
assert equipment['source_text'] == source
assert proposal['canonical_writes'] is False and proposal['source_complete'] is True
functions = [fact for fact in proposal['interpretation']['components'] if fact['kind'] == 'FUNCTION']
assert all(not re.search(r'[-\u2010-\u2014\u2212]$', fact['name'].rstrip()) for fact in functions)
assert any('Motorstromüberwachung' in fact['name'] for fact in functions)
assert not any(re.fullmatch(r'(?:`{3,}|~{3,})[^`~]*', fact['source_quote'].strip())
               for fact in proposal['interpretation']['components'])
profiles = {tuple(document_system_scope(fact.get('source_context', [])))
            for fact in proposal['interpretation']['components'] if fact['kind'] in {'INSTANCE', 'CATEGORY', 'FUNCTION'}}
assert profiles == {()}, profiles
report = {'at': datetime.now(timezone.utc).isoformat(), 'status': 'CONTROLLED_CONSISTENCY_PASS',
          'scope': 'Fake transport only. Actual product private preparation, public validation and unmodified frontend review functions. No native LLM/model/job/simulation acceptance.',
          'source_sha256': goal['source']['sha256'], 'source_chars': len(source), 'source_complete': True,
          'component_key_selection': args.selection,
          'device_groups': len(equipment['devices']), 'quantities': totals, 'quantity_sum': sum(totals.values()),
          'function_facts': len(functions), 'no_dangling_function_fragments': True,
          'explicit_monitoring_function_preserved': True, 'no_structure_only_claims': True,
          'source_system_profiles': [list(profile) for profile in sorted(profiles)],
          'requests_intercepted': len(payloads), 'actual_inference_requests': 0, 'canonical_writes': False}
(directory / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
faulthandler.cancel_dump_traceback_later()
print(json.dumps(report))
