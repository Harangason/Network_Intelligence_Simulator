"""One-token local grammar probes; no original model, writes, or workflow PASS."""
import copy
import hashlib
import json
from pathlib import Path
import time
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from backend.nis.agent.orchestration.project_intake import reference_design_schema

OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:11434/api'
MODEL = 'qwen3.8:27b'
with urlopen(Request(BASE + '/show', data=json.dumps({'model': MODEL}).encode(), headers={'Content-Type': 'application/json'}), timeout=30) as r:
    info = json.load(r)
assert not info.get('remote_host') and not info.get('remote_model')
assert str(info.get('details', {}).get('family', '')).startswith('qwen')
source_schema = reference_design_schema()

def project(value, remove_strings=False):
    if isinstance(value, dict):
        return {k: project(v, remove_strings) for k, v in value.items()
                if not (k == 'maxItems' or remove_strings and k == 'maxLength')}
    if isinstance(value, list):
        return [project(v, remove_strings) for v in value]
    return value

results = json.loads((OUT / 'native-grammar-probes.json').read_text())
assert len(results) == 2 and all(r['http_status'] == 400 for r in results)
for name, schema in [('array-and-string-upper-bounds-projection', project(source_schema, True))]:
    schema_raw = json.dumps(schema, ensure_ascii=False, sort_keys=True).encode()
    (OUT / (name + '-schema.json')).write_bytes(schema_raw)
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'Return a JSON object with empty arrays.'}],
               'format': schema, 'think': False, 'stream': False, 'options': {'num_ctx': 4096, 'num_predict': 1, 'temperature': 0}}
    started = time.monotonic()
    try:
        with urlopen(Request(BASE + '/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=180) as r:
            status, raw = r.status, r.read()
    except HTTPError as e:
        status, raw = e.code, e.read()
    (OUT / (name + '-response.json')).write_bytes(raw)
    row = {'probe': name, 'http_status': status, 'elapsed_seconds': time.monotonic() - started,
           'model': MODEL, 'format_sha256': hashlib.sha256(schema_raw).hexdigest(),
           'scope': 'Grammar compiler acceptance only, one generated token; no semantic plan, no original workflow or simulation acceptance.'}
    results.append(row)
    (OUT / 'native-grammar-probes.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(row), flush=True)
assert results[0]['http_status'] in {400, 500}
assert results[1]['http_status'] in {400, 500}
assert results[2]['http_status'] == 200, 'Upper-bound projection still does not compile; diagnose before editing source.'
