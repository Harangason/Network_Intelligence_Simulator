"""Actual isolated NIS document disconnect with local Qwen; no accepted model."""
import argparse
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
import re
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request, urlopen
from uuid import uuid4

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--kind', choices=['document', 'reference'], required=True)
parser.add_argument('--checkpoint', required=True)
args = parser.parse_args()
state = json.loads(args.state.read_text())
base, project = state['base_url'], state['project_id']
assert urlsplit(base).hostname == '127.0.0.1' and urlsplit(base).port not in {13500, 15050, None}
assert re.fullmatch('[a-z0-9-]+', args.checkpoint)
out = Path(__file__).resolve().parent / ('native-' + args.kind + '-disconnect-' + args.checkpoint)
out.mkdir(exist_ok=False)
opener = build_opener(HTTPCookieProcessor(CookieJar()))

def get(route):
    with opener.open(Request(base + route, headers={'X-Project-ID': project}), timeout=30) as response:
        return json.load(response)

def slots():
    # Ollama can replace its runner/port when the normal product context changes.
    # Discover only local listening llama-server processes; never change them.
    command = '$nisRunnerIds = @(Get-Process -Name llama-server -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id); @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $nisRunnerIds } | Select-Object -ExpandProperty LocalPort -Unique) | ConvertTo-Json -Compress'
    raw = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip()
    ports = json.loads(raw) if raw else []
    if isinstance(ports, int):
        ports = [ports]
    result = []
    for port in ports:
        try:
            with urlopen(f'http://127.0.0.1:{port}/slots', timeout=5) as response:
                data = json.load(response)
        except OSError:
            continue  # A replaced runner is expected during model loading.
        result.extend({'port': port, 'id': row['id'], 'is_processing': row['is_processing']} for row in data)
    return result

assert get('/api/build-info')['source_sha256'] == state['source_sha256']
docker = json.loads((Path.cwd() / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
app_name = 'nis-e2e-app-' + state['image_tag'].removeprefix('networkis:candidate-')
app = json.loads(subprocess.check_output([docker, 'inspect', app_name]))[0]
assert app['Image'] == state['image_id']
selected_env = dict(item.split('=', 1) for item in app['Config']['Env'] if item.startswith(('LOCAL_AI_MODEL=', 'LOCAL_AI_BASE_URL=')))
assert selected_env.get('LOCAL_AI_MODEL', 'qwen3.8:27b') == 'qwen3.8:27b'
assert selected_env['LOCAL_AI_BASE_URL'] == 'http://host.docker.internal:11434/v1'
with urlopen('http://127.0.0.1:11434/api/tags', timeout=5) as response:
    installed = json.load(response)['models']
assert any(row['name'] == 'qwen3.8:27b' and row['digest'] == 'aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813' for row in installed)
before = get('/api/engineering/projects/export')
assert all(not rows for rows in before['source_data'].values())
assert all(not row['is_processing'] for row in slots()), 'Do not compete with another inference'
source_bytes = Path(state['source']).read_bytes()
assert hashlib.sha256(source_bytes).hexdigest() == state['original_sha256']
session = get('/api/engineering/agent/review-session')
payload = {'source': source_bytes.decode('utf8'), 'source_name': Path(state['source']).name, 'source_request_id': uuid4().hex}
route = '/api/engineering/agent/document-intake'
if args.kind == 'reference':
    assert hashlib.sha256(Path(state['document_response']).read_bytes()).hexdigest() == state['reviewed_document_response_sha256']
    root = Path.cwd()
    adapter = out.parent.parents[1] / 'resume-20261018/native_original_review_adapter.mjs'
    reviewed = json.loads(subprocess.check_output(['C:/Program Files/nodejs/node.exe', '--experimental-strip-types', str(adapter), str(root), state['source'], state['document_response']], text=True, encoding='utf8', cwd=root))
    references = []
    for index, reference in enumerate(state.get('reference_sources', [])):
        text = Path(reference['path']).read_bytes().decode('utf8')
        assert hashlib.sha256(text.encode()).hexdigest() == reference['source_sha256']
        references.append({'id': 'reference-' + str(index), 'name': Path(reference['path']).name, 'role': reference['role'], 'text': text, 'source_sha256': reference['source_sha256'], 'allowed_fields': reference['allowed_fields']})
    payload = {'mode': 'EXAMPLE_PROJECT', 'prompt': reviewed['prompt'], 'source_request_id': uuid4().hex, 'reference_sources': references}
    route = '/api/engineering/agent/document-reference-design'
(out / 'request.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf8')
request = Request(base + route, data=json.dumps(payload, ensure_ascii=False).encode(), headers={'X-Project-ID': project, 'Content-Type': 'application/json', 'Accept': 'application/x-ndjson', 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session['csrf_token']})
began = time.monotonic()
observations = []
def observe(row):
    observations.append(row)
    (out / 'observations.json').write_text(json.dumps(observations, indent=2), encoding='utf8')

with opener.open(request, timeout=90) as response:
    first = json.loads(response.readline())
    assert first['type'] == 'PROGRESS'
    (out / 'first-progress.json').write_text(json.dumps(first), encoding='utf8')
    while time.monotonic() - began < 180:
        observed = slots()
        observe({'seconds': time.monotonic() - began, 'slots': observed})
        if any(row['is_processing'] for row in observed):
            break
        time.sleep(0.5)
    else:
        raise AssertionError('No actual local Qwen request observed before disconnect')
# Closing the actual client stream must stop the pending native request.
closed = time.monotonic()
while time.monotonic() - closed < 30:
    observed = slots()
    observe({'seconds_after_close': time.monotonic() - closed, 'slots': observed})
    if not any(row['is_processing'] for row in observed):
        break
    time.sleep(0.5)
else:
    raise AssertionError('Native request still processing 30 seconds after client close')
for _ in range(4):
    time.sleep(5)
    observed = slots()
    observe({'seconds_after_close': time.monotonic() - closed, 'slots': observed})
    assert not any(row['is_processing'] for row in observed), 'Abandoned worker started a later source section'
after = get('/api/engineering/projects/export')
if args.kind == 'reference':
    draft = get('/api/engineering/agent/project-draft')['data']
    assert draft['reference_generation']['status'] == 'CANCELED'
    assert draft['status'] == 'REFERENCE_CANCELED'
    assert get('/api/engineering/agent/document-reference-design')['data'] is None
    (out / 'canceled-draft.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf8')
for bundle in (before, after):
    bundle.pop('generated_at', None)
assert before == after, 'Canceled intake must not mutate the source-only canonical project'
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_NATIVE_HTTP_DISCONNECT', 'kind': args.kind, 'project_id': project, 'image_id': state['image_id'], 'source_sha256': state['source_sha256'], 'original_sha256': state['original_sha256'], 'model': 'qwen3.8:27b', 'model_digest': 'aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813', 'actual_model_selection': selected_env, 'observations': observations, 'canonical_model_unchanged': True, 'full_intake_model_simulation_or_release_pass': False}
(out / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
print(json.dumps({key: record[key] for key in ('status', 'project_id', 'canonical_model_unchanged')}), flush=True)
