"""Read-only replay of the shared fix on the reported project; no POST or SQL."""
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

folder = Path(__file__).resolve().parent
root = folder.parents[2]
sys.path.insert(0, str(root))
from backend.nis.engineering.network.physical_ports import physical_transmit_changes

base = 'http://127.0.0.1:13500/api/engineering/'
headers = {'X-Project-ID': '20261009072206008-4bb505f1'}
def get(path):
    with urlopen(Request(base + path, headers=headers), timeout=45) as response:
        return json.load(response)
def rows(path):
    items = []
    while True:
        page = get(f'{path}?limit=200&offset={len(items)}')
        chunk = page if isinstance(page, list) else page.get('items', [])
        items.extend(chunk)
        if len(chunk) < 200:
            return items

workflow = get('workflow')
messages, routes, ports = rows('messages'), rows('routing'), rows('hardware-interfaces')
snapshot = {'messages': messages, 'routes': routes, 'ports': ports, 'topology': workflow['topology'],
            'versions': workflow['versions'], 'edit_tokens': workflow['edit_tokens']}
(folder / 'current-project-binding-snapshot.json').write_text(json.dumps(snapshot), encoding='utf-8')
changes = physical_transmit_changes(workflow['topology'], routes, messages)
by_id = {str(p['id']): p for p in ports}
before = {str(m['id']): m for m in messages}
aligned = []
for change in changes:
    if 'hardware_interface_id' not in change['data']:
        continue
    message = before[change['object_id']]
    port = by_id[change['data']['hardware_interface_id']]
    old = by_id.get(str(message.get('hardware_interface_id')), {})
    assert old.get('hardware_node_id') == port.get('hardware_node_id'), message['name']
    assert old.get('technology') == port.get('technology'), message['name']
    assert any(binding['hardware_interface_id'] == str(port['id']) and binding['network_id'] == port['network_ref']
               for binding in change['data']['configuration']['physical_transmit_bindings'])
    aligned.append({'id': change['object_id'], 'name': message['name'], 'old_primary': message.get('hardware_interface_id'),
                    'proposed_primary': port['id'], 'network': port['network_ref']})
assert all(get('workflow')[key] == workflow[key] for key in ('versions', 'edit_tokens')), 'Concurrent project changes: repeat replay.'
report = {'project': headers['X-Project-ID'], 'canonical_messages': len(messages), 'aligned_primaries': len(aligned),
          'changes': aligned, 'unchanged_hardware_ownership_and_technology': True, 'product_mutations': 0,
          'scope': 'Actual current project read-only preview, not deployed behavior or a nine-stage E2E test.'}
(folder / 'current-project-replay.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'aligned_primaries': len(aligned), 'licht': [row for row in aligned if row['name'] == 'Licht'], 'product_mutations': 0}))
