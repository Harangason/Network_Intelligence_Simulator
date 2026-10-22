"""Native compiler/arity fixtures only; never an original/model/simulation PASS."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

WORKLOAD = Path(__file__).resolve().parent
ROOT = WORKLOAD.parents[5]
OUT = WORKLOAD / 'final-native-schemas'
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage, _reference_declared_instances
from backend.nis.agent.orchestration.project_intake import prepare_reference_design, reference_inventory_members
from backend.nis.engineering.projects.project_context import activate_project, reset_project

case = WORKLOAD.parents[1] / 'native-binding-vehicle'
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
known, _ = _reference_declared_instances(prepared, prepared['facts'])
binding_fact = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'CATEGORY' and fact['role'] == 'CONTROLLER')


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
    'existing-source-binding': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
        'fact_id': binding_fact, 'member': None, 'minimum_rows': 1}, existing_devices=known),
    'existing-derived-binding': _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=derived, existing_devices=known),
    **{field: _reference_schema_for_stage(prepared, {field}, device_ids=('SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT',),
                                         port_intent=field == 'ports') for field in ('ports', 'measurements', 'commands')},
}
singleton = _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
    'fact_id': declared, 'minimum_rows': 1, 'names': ['SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT']})
jobs = [(name, schema, 'Return the beginning of a JSON object.', 1) for name, schema in schemas.items()]
binding_value = {'devices': [], 'inventory_complete': True, 'inventory_choices': [{
    'choice_kind': 'EXISTING', 'source_fact_ids': [binding_fact], 'rationale': 'schema probe',
    'field_references': {}, 'device_id': known[0]['id']}]}
def new_role_value(kind):
    return {'devices': [], 'inventory_complete': True, 'inventory_choices': [{
        'choice_kind': 'NEW_' + kind, 'rationale': 'schema probe', 'id': 'SCHEMA_ONLY_NEW_' + kind,
        'name': 'Schema ' + kind.lower(), 'kind': kind, 'quantity': 1,
        'source_fact_ids': [derived[0]], 'source_member_bindings': {},
        'owner_device_id': known[0]['id'], 'field_references': {}}]}
jobs.extend([
    ('singleton-full', singleton, 'Grammar fixture only, no project/model. Return devices [], inventory_complete true and inventory_choices with one NEW_CONTROLLER object (choice_kind NEW_CONTROLLER) with id SCHEMA_ONLY_D, the sole allowed name/fact, kind CONTROLLER, quantity1 and rationale schema probe. All other lists empty.', 256),
    ('existing-binding-full', schemas['existing-source-binding'], 'Grammar fixture only, no project/model. Return exactly this JSON, using the existing-ID alternative with choice_kind EXISTING: ' + json.dumps(binding_value), 256),
    ('new-sensor-nonfirst-full', schemas['existing-derived-binding'], 'Grammar fixture only, no project/model. Return exactly this JSON, using NEW_SENSOR rather than a controller or binding: ' + json.dumps(new_role_value('SENSOR')), 384),
    ('new-actuator-nonfirst-full', schemas['existing-derived-binding'], 'Grammar fixture only, no project/model. Return exactly this JSON, using NEW_ACTUATOR rather than a controller or binding: ' + json.dumps(new_role_value('ACTUATOR')), 384),
    ('empty-derived-full', schemas['derived'], 'Grammar fixture only, no project/model and no extra hardware needed. Return devices [], inventory_choices [] and inventory_complete true; all other lists empty.', 128),
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
        from jsonschema import Draft202012Validator
        Draft202012Validator(schema).validate(value)
        assert value.get('devices', []) == []
        if name == 'singleton-full':
            assert len(value['inventory_choices']) == 1
            chosen = value['inventory_choices'][0]
            assert chosen['choice_kind'] == 'NEW_CONTROLLER'
            assert chosen['source_fact_ids'] == [declared]
            assert chosen['kind'] == 'CONTROLLER' and chosen['quantity'] == 1
        elif name == 'existing-binding-full':
            assert len(value['inventory_choices']) == 1
            choice = value['inventory_choices'][0]
            assert choice['choice_kind'] == 'EXISTING'
            assert choice['device_id'] == known[0]['id'] and choice['source_fact_ids'] == [binding_fact]
            assert set(choice) == {'choice_kind', 'device_id', 'source_fact_ids', 'rationale', 'field_references'}
        elif name in {'new-sensor-nonfirst-full', 'new-actuator-nonfirst-full'}:
            assert len(value['inventory_choices']) == 1
            chosen = value['inventory_choices'][0]
            kind = 'SENSOR' if name == 'new-sensor-nonfirst-full' else 'ACTUATOR'
            assert chosen['choice_kind'] == 'NEW_' + kind and chosen['kind'] == kind
            assert chosen['source_fact_ids'] == [derived[0]] and chosen['quantity'] == 1
            assert chosen['owner_device_id'] == known[0]['id']
        else:
            assert value['inventory_choices'] == []
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
