"""S01-A: persist the user's explicitly approved test assumptions on isolated HTTP."""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import uuid

ROOT = Path(__file__).resolve().parents[2]
receipt = json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
base = receipt['base_url']
assert base.startswith('http://127.0.0.1:') and ':13500' not in base
assert receipt['containers']['app'].startswith('nis-e2e-app-')
project = 'nis-e2e-completion-s01-' + uuid.uuid4().hex[:8]
folder = ROOT / '.tool-checker/evidence/industry60-completion/S01-A' / project
folder.mkdir(parents=True, exist_ok=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
headers = {'X-Project-ID': project, 'Content-Type': 'application/json'}
def call(name, path, data=None):
    request = urllib.request.Request(base + path, headers=headers,
        data=None if data is None else json.dumps(data).encode())
    try:
        with opener.open(request, timeout=180) as response:
            status, body = response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read().decode()
    (folder / (name + '.json')).write_text(json.dumps({'project': project, 'status': status,
        'request': data, 'response': body, 'image': receipt['image_id']}, ensure_ascii=False, indent=2), encoding='utf8')
    print(name, status, flush=True)
    return json.loads(body) if not name.endswith('chat') else body

prompt = json.loads((ROOT / 'tests/fixtures/industry60-intake-regressions.json').read_text(encoding='utf8'))['S01-A']
call('initial-chat', '/api/agent/chat', {'messages': [{'id': uuid.uuid4().hex, 'role': 'user',
    'parts': [{'type': 'text', 'text': prompt}]}], 'context': {'active_project_id': project}})
draft = call('draft', '/api/engineering/agent/project-draft')['data']
token = call('review-session', '/api/engineering/agent/review-session')['csrf_token']
headers.update({'X-Review-CSRF': token, 'X-Human-Review': 'confirmed'})
owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
updates = []
for device in draft['devices']:
    if device['role'] == 'CONTROLLER':
        updates.append({'device_id': device['id'], 'technologies': ['SPI', 'I2C', 'GPIO', 'PWM', 'CAN_FD']})
        continue
    update = {'device_id': device['id'], 'owner_id': owner['id']}
    if device['role'] == 'ACTUATOR':
        name = device['name'].lower()
        relay = 'relais' in name
        motor = 'motor' in name
        maximum = 1 if relay else 6000 if motor else 100
        update['command'] = {'length_bits': 1 if relay else 13 if motor else 7,
            'data_type': 'boolean' if relay else 'unsigned', 'unit': 'code' if relay else 'rpm' if motor else '%',
            'factor': 1, 'min_value': 0, 'max_value': maximum,
            'semantic': {'semantic_type': 'BOOLEAN' if relay else 'NUMERIC'},
            'data': {'enum_values': {'OFF': 0, 'ON': 1}} if relay else {'minimum': 0, 'maximum': maximum, 'resolution': 1}}
        if relay:
            update['technology'] = 'GPIO'
    updates.append(update)
result = call('resolved-assumptions', '/api/engineering/agent/project-draft', {'action': 'RESOLVE',
    'operation_id': uuid.uuid4().hex, 'revision': draft['revision'], 'devices': updates,
    'allow_simulation_defaults': True})
call('resolved-draft', '/api/engineering/agent/project-draft')
print(json.dumps(result.get('data', {}).get('draft', {}).get('issues', []), ensure_ascii=False), flush=True)
resolved = result['data']['draft']
assert not resolved['issues'], resolved['issues']
workflow = call('workflow-request', '/api/engineering/agent/project-draft/workflow-request', {
    'draft_id': resolved['draft_id'], 'revision': resolved['revision'], 'run_id': str(uuid.uuid4()),
    'project_name': 'S01-A approved isolated test', 'scope_ids': ['engineering_model', 'routing', 'network_editor',
    'parameters', 'capacity_timing', 'validation', 'simulation', 'results_analysis', 'data_science_intelligence']})['data']
(folder / 'approved-workflow.txt').write_text(workflow['prompt'], encoding='utf8')
(folder / 'approved-workflow.json').write_text(json.dumps({'wizard_context': workflow['context'],
    'test_assumptions': 'User-approved S01-A ownership/commands/connections; technology simulation defaults, not confirmed physical hardware.'}, ensure_ascii=False), encoding='utf8')
print(json.dumps({'project': project, 'evidence': str(folder), 'base_url': base}), flush=True)
