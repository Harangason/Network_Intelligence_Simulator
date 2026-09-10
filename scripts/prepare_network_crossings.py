"""Persist drawing bridges while retaining existing manual positions and routes."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.network_scene import model_signature

project = 'network-project-20260910042736034-d11591d0'
url = 'http://127.0.0.1:15050/api/engineering/workflow/network-view'
headers = {'X-Project-ID': project, 'Content-Type': 'application/json'}
with urlopen(Request(url, headers=headers), timeout=30) as response:
    before = json.load(response)
with Path('backend/runtime/network-crossings-project-before.json').open('x', encoding='utf-8') as out:
    json.dump(before, out, ensure_ascii=False)
positions = {n['id']: {key: n[key] for key in ('x', 'y', 'width', 'height')} for n in before['topology']['nodes']}
payload = {'positions': positions, 'expected_token': before['edit_tokens']['topology']}
with urlopen(Request(url, headers=headers, data=json.dumps(payload).encode(), method='PUT'), timeout=30) as response:
    after = json.load(response)
assert model_signature(after['topology']) == model_signature(before['topology'])
assert before['versions'] == after['versions']
assert positions == {n['id']: {key: n[key] for key in ('x', 'y', 'width', 'height')} for n in after['topology']['nodes']}
assert after['topology']['scene']['manualBusRoutes'] == before['topology']['scene'].get('manualBusRoutes', {})
for node_id, position in before['topology']['scene']['manualPositions'].items():
    assert position.get('ports') == after['topology']['scene']['manualPositions'][node_id].get('ports')
Path('backend/runtime/network-crossings-project-after.json').write_text(json.dumps(after, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'project': project, 'bridges': len(after['topology']['scene']['wireBridges']), 'routingVersion': after['topology']['scene']['routingVersion'],
                  'modelAndVersionsUnchanged': True, 'manualPositionsPreserved': True}))
