"""Two controlled decoder probes, not an original/model/simulation success.

Keep the exact JSON instruction and change only the grammar structure: isolate
the existing-binding branch, then expand the same union without a nested $ref.
Never modifies product source, project data, model settings or running services.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
source = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
base = json.loads((OUT / 'existing-binding-full-explicit-json-compiler-request.json').read_text(encoding='utf-8'))
original = base['format']
alternatives = original['properties']['inventory_choices']['items']['anyOf']
binding = next(row for row in alternatives if 'device_id' in row.get('properties', {}))
new_ref = next(row['$ref'] for row in alternatives if '$ref' in row)
new_definition = original['$defs'][new_ref.rsplit('/', 1)[-1]]
assert 'anyOf' in new_definition
schemas = []
single = deepcopy(original)
single['properties']['inventory_choices']['items'] = deepcopy(binding)
schemas.append(('binding-branch-only', single))
flat = deepcopy(original)
flat['properties']['inventory_choices']['items'] = {
    'anyOf': [*deepcopy(new_definition['anyOf']), deepcopy(binding)]}
schemas.append(('flat-inline-choice-union', flat))
results = []
for name, schema in schemas:
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    payload = {**base, 'format': schema}
    response_path = OUT / (name + '-diagnostic-response.json')
    assert not response_path.exists()
    (OUT / (name + '-diagnostic-request.json')).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    began = time.monotonic()
    req = Request('http://127.0.0.1:11434/api/chat', data=json.dumps(payload).encode(),
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=180) as response:
        status, raw = response.status, response.read()
    response_path.write_bytes(raw)
    body = json.loads(raw)
    record = {'name': name, 'http_status': status, 'seconds': time.monotonic() - began,
              'done_reason': body.get('done_reason'), 'eval_count': body.get('eval_count'),
              'response_sha256': hashlib.sha256(raw).hexdigest(),
              'request_sha256': hashlib.sha256((OUT / (name + '-diagnostic-request.json')).read_bytes()).hexdigest()}
    if status == 200 and body.get('done_reason') == 'stop':
        value = json.loads(body['message']['content'])
        Draft202012Validator(schema).validate(value)
        selected = value['inventory_choices'][0]
        record['selected_keys'] = list(selected)
        record['selected_branch'] = 'EXISTING_BINDING' if 'device_id' in selected else 'NEW_DEVICE'
        record['expected_binding_selected'] = (
            selected.get('device_id') == binding['properties']['device_id']['enum'][0]
            and selected.get('source_fact_ids') == binding['properties']['source_fact_ids']['items']['enum'])
    results.append(record)
    (OUT / 'choice-union-structural-diagnostic.json').write_text(json.dumps({
        'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__,
        'reasoner_source_sha256': source_sha, 'results': results,
        'product_source_changed': False, 'canonical_writes': False,
        'original_or_model_or_simulation_pass': False}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record), flush=True)
