"""Replay R01/R02 over HTTP against a gate-owned disposable application."""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[2]
receipt = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
base = receipt['base_url']
assert base.startswith('http://127.0.0.1:') and ':13500' not in base
assert receipt['containers']['app'].startswith('nis-e2e-app-')
prompts = json.loads((root/'tests/fixtures/industry60-intake-regressions.json').read_text(encoding='utf-8'))
folder = Path(sys.argv[2]) if len(sys.argv) > 2 else root/'.tool-checker/evidence/industry60-intake-fixes'
folder.mkdir(parents=True, exist_ok=True)

def call(project, path, payload=None):
    req = urllib.request.Request(base+path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', 'X-Project-ID': project})
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read().decode()

for case, prompt in prompts.items():
    project = 'nis-e2e-intake-fix-' + case.lower() + '-' + uuid.uuid4().hex[:8]
    payload = {'messages': [{'id': uuid.uuid4().hex, 'role': 'user', 'parts': [{'type':'text','text':prompt}]}],
               'context': {'active_project_id': project}}
    wire = call(project, '/api/agent/chat', payload)
    history = json.loads(call(project, '/api/agent/history?projectId='+project))
    response = json.loads(call(project, '/api/engineering/agent/project-draft'))
    draft = response['data']
    # RESULT.text is a compact preview; the persisted CHAT output is the full reply.
    text = '\n'.join(output['content'] for msg in history['messages'] if msg['role'] == 'assistant'
                     for part in msg['parts'] for output in part.get('data',{}).get('outputs',[])
                     if output.get('output_type') == 'CHAT' and isinstance(output.get('content'), str))
    (folder/(case+'.json')).write_text(json.dumps({'project':project, 'request':payload, 'wire':wire,
        'history':history, 'draft':draft, 'image':receipt['image_id']}, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = text.split('Geräte im Entwurf:')[1]
    assert all(d['name'] in summary for d in draft['devices'])
    if case == 'S01-A':
        assert len(draft['devices']) == 8
        assert 'respary' not in text and '→' not in text
    else:
        drives = [d for d in draft['devices'] if d['role'] == 'ACTUATOR']
        assert len(drives) == 10 and all(d['technology'] == 'EtherCAT' for d in drives)
        assert all(d['technology'] is None for d in draft['devices'] if d['role'] == 'SENSOR')
    print(case+' HTTP + persisted reply/draft PASS: '+project, flush=True)
