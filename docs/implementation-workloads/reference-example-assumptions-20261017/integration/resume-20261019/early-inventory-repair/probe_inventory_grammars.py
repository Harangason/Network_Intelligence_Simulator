"""Four one-token native decoder probes; never an original/model/simulation PASS."""
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
from backend.nis.agent.orchestration.project_intake import prepare_reference_design
from backend.nis.engineering.projects.project_context import activate_project, reset_project

case = OUT.parents[1] / 'native-io-vehicle'
state = json.loads((case / 'state.json').read_text(encoding='utf-8'))
token = activate_project(state['project_id'])
try:
    prepared = prepare_reference_design(json.loads((case / 'plan-reference/request.json').read_text(encoding='utf-8')))
finally:
    reset_project(token)


def post(path, payload):
    req = Request('http://127.0.0.1:11434/api' + path,
                  data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=180) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


model = 'qwen3.8:27b'
status, raw = post('/show', {'model': model})
assert status == 200
info = json.loads(raw)
assert not info.get('remote_host') and not info.get('remote_model')
assert str(info['details']['family']).startswith('qwen')
assert info['model_info']['general.parameter_count']
results = []
for field in ('devices', 'ports', 'measurements', 'commands'):
    # Deliberate grammar fixture, not a proposed or imported participant.
    schema = _reference_schema_for_stage(prepared, {field},
        inventory_target={'fact_id': next(iter(prepared['facts'])), 'minimum_rows': 1} if field == 'devices' else None,
        device_ids=() if field == 'devices' else ('SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT',), port_intent=field == 'ports')
    schema_file = OUT / (field + '-decoder-schema.json')
    assert not schema_file.exists()
    schema_file.write_text(json.dumps(schema, sort_keys=True, ensure_ascii=False), encoding='utf-8')
    started = time.monotonic()
    status, raw = post('/chat', {'model': model,
        'messages': [{'role': 'user', 'content': 'Return the beginning of a JSON object.'}],
        'format': schema, 'think': False, 'stream': False, 'keep_alive': '5m',
        'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 1}})
    response_file = OUT / (field + '-compiler-response.json')
    response_file.write_bytes(raw)
    results.append({'field': field, 'http_status': status, 'seconds': time.monotonic() - started,
        'schema_sha256': hashlib.sha256(schema_file.read_bytes()).hexdigest(),
        'response_sha256': hashlib.sha256(raw).hexdigest(), 'one_token_only': True,
        'owner_id_is_explicit_compiler_fixture_not_canonical_model': True})
    (OUT / 'native-io-grammar-probes.json').write_text(json.dumps({
        'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__, 'model': model,
        'results': results, 'canonical_writes': False, 'native_original_plan_pass': False,
        'simulation_pass': False, 'productive_delivery': False}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results[-1]), flush=True)
    assert status == 200, 'Native IO grammar compiler rejected schema.'
