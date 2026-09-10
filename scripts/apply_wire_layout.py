"""Recalculate a project's drawing with a saved backup and optimistic locking."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.network_scene import model_signature
from scripts.verify_wire_layout import crossings

project = sys.argv[1]
assert project == 'network-project-20260910042736034-d11591d0'
url = 'http://127.0.0.1:15050/api/engineering/workflow/network-view'
headers = {'X-Project-ID': project, 'Content-Type': 'application/json'}
with urlopen(Request(url, headers=headers), timeout=30) as response:
    before = json.load(response)
backup = Path('backend/runtime/wire-layout-project-before.json')
with backup.open('x', encoding='utf-8') as out:
    json.dump(before, out, ensure_ascii=False)
positions = {node['id']: {key: node[key] for key in ('x', 'y', 'width', 'height')} for node in before['topology']['nodes']}
payload = {'positions': positions, 'expected_token': before['edit_tokens']['topology'], 'reset_wires': True}
with urlopen(Request(url, headers=headers, data=json.dumps(payload).encode(), method='PUT'), timeout=30) as response:
    after = json.load(response)
assert model_signature(before['topology']) == model_signature(after['topology'])
assert before['topology']['edges'] == after['topology']['edges']
assert before['versions'] == after['versions']
assert positions == {node['id']: {key: node[key] for key in ('x', 'y', 'width', 'height')} for node in after['topology']['nodes']}
owner = next(node['id'] for node in after['topology']['nodes'] if node['name'] == 'Bremsregelung')
report = {'project': project, 'modelUnchanged': True, 'devicePositionsUnchanged': True, 'versionsUnchanged': True,
          'before': crossings([bus for bus in before['topology']['scene']['buses'] if bus['frameId'] == owner]),
          'after': crossings([bus for bus in after['topology']['scene']['buses'] if bus['frameId'] == owner]),
          'routingWarnings': after['topology']['scene']['routingWarnings']}
Path('backend/runtime/wire-layout-project-after.json').write_text(json.dumps(after, ensure_ascii=False), encoding='utf-8')
Path('backend/runtime/wire-layout-project-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
