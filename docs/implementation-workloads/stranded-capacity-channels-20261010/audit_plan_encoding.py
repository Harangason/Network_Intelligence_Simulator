"""Compare detached topology text to the captured canonical source, retaining old evidence."""
import json, shutil
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
source = json.loads((HERE / 'canonical-inspection.json').read_text(encoding='utf-8'))['data']['snapshot']
plan = json.loads((HERE / 'reconciliation-preview.json').read_text(encoding='utf-8'))
topology = next(change['data']['topology'] for change in plan['changes'] if change['object_type'] == 'NetworkTopology')
differences = []
by_id = {node['id']: node for node in source['topology']['nodes']}
for node in topology['nodes']:
    original = by_id[node['id']]
    if original.get('name') != node.get('name'):
        differences.append({'id': node['id'], 'canonical': original.get('name'), 'planned': node.get('name')})
changes = {row['object_id']: row['data'] for row in plan['changes'] if row['object_type'] == 'HardwareNetworkInterface'}
for original in source['hardware-interfaces']:
    if 'capabilities' in changes.get(original['id'], {}):
        for key, value in original.get('capabilities', {}).items():
            if key not in ('network_id', 'topology_port_id') and changes[original['id']]['capabilities'].get(key) != value:
                differences.append({'id': original['id'], 'field': 'capabilities.' + key, 'canonical': value, 'planned': changes[original['id']]['capabilities'].get(key)})
report = {'captured_at': datetime.now(timezone.utc).isoformat(), 'differences': differences,
    'scope': 'Detached host plan only; Windows default cp1252 decoding of a UTF-8 capture is invalid. No source/application or canonical model mutation.'}
(HERE / 'plan-encoding-audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
for name in ['reconciliation-preview.json', 'prepared-reconciliation-proposal.json']:
    dest = HERE / ('before-encoding-repair-' + name)
    assert not dest.exists()
    shutil.copyfile(HERE / name, dest)
print(json.dumps({'unintended_text_changes_found': len(differences)}))
