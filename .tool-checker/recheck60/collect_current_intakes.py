"""Current per-case draft/clarification evidence, no architecture decisions or PASS claims."""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
receipt = json.loads(Path(sys.argv[1]).read_text())
base = receipt['base_url']
assert receipt['status'] in {'PREPARED', 'DIAGNOSTIC_ONLY'} and receipt['containers']['app'].startswith('nis-e2e-app-')
assert base.startswith('http://127.0.0.1:') and ':13500' not in base
manifest = json.loads((ROOT / '.tool-checker/industry60-recheck.normalized.json').read_text(encoding='utf8'))
folder = ROOT / '.tool-checker/evidence/industry60-completion/intakes' / receipt['release']['build_id']
folder.mkdir(parents=True, exist_ok=True)
summary = []
for case in manifest['test_cases']:
    if '-' not in case['test_id']:
        continue
    path = folder / (case['test_id'] + '.json')
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf8'))
    else:
        project = 'nis-e2e-completion-' + case['test_id'].lower() + '-' + uuid.uuid4().hex[:8]
        def call(endpoint, data=None):
            request = urllib.request.Request(base + endpoint,
                data=None if data is None else json.dumps(data).encode(),
                headers={'Content-Type': 'application/json', 'X-Project-ID': project})
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read().decode()
        payload = {'messages': [{'id': uuid.uuid4().hex, 'role': 'user',
            'parts': [{'type': 'text', 'text': case['input']}]}], 'context': {'active_project_id': project}}
        wire = call('/api/agent/chat', payload)
        draft = json.loads(call('/api/engineering/agent/project-draft'))
        history = json.loads(call('/api/agent/history?projectId=' + project))
        saved = {'case': case['test_id'], 'project': project, 'image': receipt['image_id'],
                 'input': case['input'], 'wire': wire, 'draft': draft, 'history': history}
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf8')
    data = saved['draft'].get('data') or {}
    item = {'case': case['test_id'], 'devices': len(data.get('devices') or []),
            'issues': data.get('issues'), 'project': saved['project']}
    summary.append(item)
    print(case['test_id'], item['devices'], 'devices', len(item['issues'] or []), 'issues', flush=True)
(folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
