"""SQL regression for partial coordinate saves, restricted to the test copy."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

project = json.loads(Path('backend/runtime/crossing-test.json').read_text())['project']
assert project.startswith('network-project-crossing-test-')
url = 'http://127.0.0.1:15050/api/engineering/workflow/network-view'
headers = {'X-Project-ID': project, 'Content-Type': 'application/json'}


def request(payload=None):
    with urlopen(Request(url, headers=headers, method='PUT' if payload is not None else 'GET',
                         data=json.dumps(payload).encode() if payload is not None else None), timeout=30) as response:
        return json.load(response)


initial = request()
node = next(n for n in initial['topology']['nodes'] if n['name'] == 'Bremsregelung')
port = node['ports'][0]
placement = {'side': 'bottom', 'offset': .33}
saved = request({'positions': {node['id']: {'ports': {port['id']: placement}}}, 'expected_token': initial['edit_tokens']['topology']})
moved = request({'positions': {node['id']: {'x': node['x'] + 3}}, 'expected_token': saved['edit_tokens']['topology']})
assert moved['topology']['scene']['manualPositions'][node['id']]['ports'][port['id']] == placement
saved_node = next(n for n in moved['topology']['nodes'] if n['id'] == node['id'])
saved_port = next(p for p in saved_node['ports'] if p['id'] == port['id'])
assert saved_port['side'] == placement['side'] and saved_port['offset'] == placement['offset']
assert saved_node['x'] == node['x'] + 3
assert moved['versions'] == initial['versions']
assert moved['topology']['edges'] == initial['topology']['edges']
print('SQL: coordinate-only update preserves the manual port and workflow versions.')
