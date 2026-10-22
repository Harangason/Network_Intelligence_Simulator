"""Finish two grammar-only fixtures without repeating the completed probes.

The first union fixture selected a schema-valid new row rather than the requested
known-ID branch. Preserve that response and the original assertion; supply an
exact JSON example on the identical production schema for this contrastive check.
No project, original workflow, model, simulation or release approval is produced.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


prior = json.loads((OUT / 'native-private-schema-checks.json').read_text(encoding='utf-8'))
assert len(prior['results']) == 10
source = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
assert sha(source) == prior['reasoner_file_sha256']
request = json.loads((OUT / 'existing-binding-full-compiler-request.json').read_text(encoding='utf-8'))
schema = request['format']
binding = next(row for row in schema['properties']['inventory_choices']['items']['anyOf']
               if 'device_id' in row.get('properties', {}))
device = binding['properties']['device_id']['enum'][0]
fact = binding['properties']['source_fact_ids']['items']['enum'][0]
example = {'devices': [], 'inventory_complete': True, 'inventory_choices': [{
    'source_fact_ids': [fact], 'rationale': 'schema probe',
    'field_references': {}, 'device_id': device}]}
jobs = [
    ('existing-binding-full-explicit-json', schema,
     'Grammar fixture only, no project/model. Return exactly this JSON value, '
     'preserving device_id as a binding (never id as a new device): '
     + json.dumps(example), 256),
    ('empty-derived-full', json.loads((OUT / 'derived-decoder-schema.json').read_text(encoding='utf-8')),
     'Grammar fixture only, no project/model, no extra hardware: return devices [], '
     'inventory_choices [] and inventory_complete true; all other lists empty.', 128),
]
results = list(prior['results'])
for name, decoder, prompt, limit in jobs:
    assert sha(source) == prior['reasoner_file_sha256']
    schema_path = OUT / (name + '-decoder-schema.json')
    response_path = OUT / (name + '-compiler-response.json')
    assert not response_path.exists(), 'Never overwrite an earlier fixture response.'
    schema_path.write_text(json.dumps(decoder, sort_keys=True, ensure_ascii=False), encoding='utf-8')
    payload = {**request, 'format': decoder, 'messages': [{'role': 'user', 'content': prompt}],
               'options': {**request['options'], 'num_predict': limit}}
    (OUT / (name + '-compiler-request.json')).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    began = time.monotonic()
    req = Request('http://127.0.0.1:11434/api/chat', data=json.dumps(payload).encode(),
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=180) as response:
        status, raw = response.status, response.read()
    response_path.write_bytes(raw)
    body = json.loads(raw)
    assert status == 200 and body.get('done_reason') == 'stop'
    value = json.loads(body['message']['content'])
    Draft202012Validator(decoder).validate(value)
    assert value.get('devices', []) == [] and value['inventory_complete'] is True
    if name == 'existing-binding-full-explicit-json':
        assert len(value['inventory_choices']) == 1
        selected = value['inventory_choices'][0]
        assert selected['device_id'] == device and selected['source_fact_ids'] == [fact]
        assert set(selected) == {'device_id', 'source_fact_ids', 'rationale', 'field_references'}
    else:
        assert value['inventory_choices'] == []
    row = {'name': name, 'http_status': status, 'seconds': time.monotonic() - began,
           'one_token_compiler_only': False, 'completed_grammar_fixture_only': True,
           'schema_sha256': sha(schema_path), 'response_sha256': sha(response_path),
           'eval_count': body.get('eval_count')}
    results.append(row)
    record = {**prior, 'at_utc': datetime.now(timezone.utc).isoformat(), 'results': results,
              'scope': __doc__, 'initial_wrong_branch_fixture_preserved': True,
              'single_uninterrupted_probe_run_claimed': False}
    (OUT / 'native-private-schema-checks-completed.json').write_text(
        json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(row), flush=True)
