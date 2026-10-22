"""Native compiler/arity fixtures only; never an original/model/simulation PASS."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage
from backend.nis.agent.orchestration.project_intake import prepare_reference_design, reference_inventory_members
from backend.nis.engineering.projects.project_context import activate_project, reset_project

case = OUT.parents[1] / 'native-scoped-vehicle'
state = json.loads((case / 'state.json').read_text(encoding='utf8'))
token = activate_project(state['project_id'])
try:
    prepared = prepare_reference_design(json.loads((case / 'plan-reference/request.json').read_text(encoding='utf8')))
finally:
    reset_project(token)
source_file = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
source_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
declared = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE' and fact['role'] == 'CONTROLLER')
member_fact = next(key for key, fact in prepared['facts'].items() if reference_inventory_members(fact))
member = reference_inventory_members(prepared['facts'][member_fact])[0]
derived = [key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}]


def post(path, body):
    request = Request('http://127.0.0.1:11434/api' + path, data=json.dumps(body, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=180) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


status, raw = post('/show', {'model': 'qwen3.8:27b'})
assert status == 200
info = json.loads(raw)
assert not info.get('remote_host') and not info.get('remote_model')
assert info['details']['family'].startswith('qwen') and info['model_info']['general.parameter_count']
(OUT / 'compiler-model-show.json').write_bytes(raw)
schemas = {
    'declared': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={'fact_id': declared, 'minimum_rows': 1}),
    'literal-member': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
        'fact_id': member_fact, 'member': member, 'minimum_rows': 1}),
    'literal-covered-closure': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
        'fact_id': member_fact, 'member': member, 'minimum_rows': 0}),
    'derived': _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=derived),
    **{field: _reference_schema_for_stage(prepared, {field}, device_ids=('SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT',),
                                         port_intent=field == 'ports') for field in ('ports', 'measurements', 'commands')},
}
singleton = _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
    'fact_id': declared, 'minimum_rows': 1, 'names': ['SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT']})
jobs = [(name, schema, 'Return the beginning of a JSON object.', 1) for name, schema in schemas.items()]
jobs.extend([
    ('singleton-full', singleton, 'Grammar test only, no project or model. Return one controller with id SCHEMA_ONLY_D and rationale "schema probe". Use the sole allowed name/fact, quantity 1, inventory_complete true. No extra device or placeholder.', 256),
    ('empty-derived-full', schemas['derived'], 'Grammar test only, no project or model and no additional hardware needed. Return devices [] and inventory_complete true, all other lists empty.', 128),
])
results = []
for name, schema, prompt, limit in jobs:
    assert hashlib.sha256(source_file.read_bytes()).hexdigest() == source_hash
    started = time.monotonic()
    schema_file = OUT / (name + '-decoder-schema.json')
    schema_file.write_text(json.dumps(schema, sort_keys=True, ensure_ascii=False), encoding='utf8')
    payload = {'model': 'qwen3.8:27b', 'messages': [{'role': 'user', 'content': prompt}],
        'format': schema, 'think': False, 'stream': False, 'keep_alive': '5m',
        'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': limit}}
    (OUT / (name + '-compiler-request.json')).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf8')
    status, raw = post('/chat', payload)
    (OUT / (name + '-compiler-response.json')).write_bytes(raw)
    assert status == 200, raw[:500]
    body = json.loads(raw)
    if limit > 1:
        assert body.get('done_reason') == 'stop', 'Grammar fixture did not complete.'
        value = json.loads(body['message']['content'])
        assert value['inventory_complete'] is True
        if name == 'singleton-full':
            assert len(value['devices']) == 1
            assert value['devices'][0]['source_fact_ids'] == [declared]
            assert value['devices'][0]['kind'] == 'CONTROLLER' and value['devices'][0]['quantity'] == 1
        else:
            assert value['devices'] == []
    results.append({'name': name, 'http_status': status, 'seconds': time.monotonic() - started,
        'one_token_compiler_only': limit == 1, 'completed_grammar_fixture_only': limit > 1,
        'schema_sha256': hashlib.sha256(schema_file.read_bytes()).hexdigest(),
        'response_sha256': hashlib.sha256(raw).hexdigest(), 'eval_count': body.get('eval_count')})
    (OUT / 'native-private-schema-checks.json').write_text(json.dumps({
        'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__,
        'reasoner_file_sha256': source_hash, 'results': results, 'model': 'qwen3.8:27b',
        'canonical_writes': False, 'original_workflow_pass': False, 'model_or_simulation_pass': False,
        'full_release_pass': False, 'productive_delivery': False}, indent=2) + '\n', encoding='utf8')
    print(json.dumps(results[-1]), flush=True)
