"""One-token local grammar acceptance only; no original plan/model/simulation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage
from backend.nis.agent.orchestration.project_intake import prepare_reference_design
from backend.nis.engineering.projects.project_context import activate_project, reset_project

OUT = Path(__file__).resolve().parent
case = OUT.parents[1] / 'native-36f-vehicle'
state = json.loads((case / 'state.json').read_text(encoding='utf-8'))
token = activate_project(state['project_id'])
try:
    prepared = prepare_reference_design(json.loads((case / 'plan-reference/request.json').read_text(encoding='utf-8')))
finally:
    reset_project(token)
base = 'http://127.0.0.1:11434/api'
model = 'qwen3.8:27b'


def post(path, payload, timeout=180):
    request = Request(base + path, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


status, raw = post('/show', {'model': model})
assert status == 200
info = json.loads(raw)
assert not info.get('remote_host') and not info.get('remote_model')
assert str(info['details']['family']).startswith('qwen')
assert info['model_info']['general.parameter_count']
functions = tuple(key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION')[:4]
stages = [
    ('participants', {'devices'}, {}),
    ('port-intent', {'ports', 'measurements', 'commands'}, {'port_intent': True}),
    ('parameter-batch', {'ports'}, {'port_ids': ('SCHEMA_ONLY_NOT_A_MODEL_PORT',)}),
    ('function-batch', {'functions', 'functional_dependencies'}, {'function_ids': functions}),
]
results = []
for name, allowed, options in stages:
    schema = _reference_schema_for_stage(prepared, allowed, **options)
    schema_file = OUT / (name + '-decoder-schema.json')
    assert not schema_file.exists()
    schema_file.write_text(json.dumps(schema, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    payload = {'model': model, 'messages': [{'role': 'user', 'content': 'Return the beginning of a JSON object.'}],
               'format': schema, 'think': False, 'stream': False, 'keep_alive': '5m',
               'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 1}}
    started = time.monotonic()
    status, raw = post('/chat', payload)
    (OUT / (name + '-compiler-response.json')).write_bytes(raw)
    results.append({'stage': name, 'http_status': status, 'seconds': time.monotonic() - started,
                    'schema_sha256': hashlib.sha256(schema_file.read_bytes()).hexdigest(),
                    'response_sha256': hashlib.sha256(raw).hexdigest(),
                    'scope': __doc__, 'one_token_only': True,
                    'parameter_id_is_explicit_grammar_fixture_not_canonical_model': name == 'parameter-batch'})
    (OUT / 'stage-grammar-probes.json').write_text(json.dumps({
        'at_utc': datetime.now(timezone.utc).isoformat(), 'model': model,
        'scope': __doc__, 'results': results, 'canonical_writes': False,
        'original_workflow_pass': False, 'simulation_pass': False}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results[-1]), flush=True)
    assert status == 200, 'Native stage grammar does not compile; no original planning acceptance.'
