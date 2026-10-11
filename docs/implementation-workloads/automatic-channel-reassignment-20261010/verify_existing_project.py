"""Read-only verification using the exact delivered product model and planner."""
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
work = json.loads((folder / 'workload.json').read_text())
receipt = json.loads(Path(work['active_release_receipt']).read_text())
assert receipt['status'] == 'PASS'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']
code = '''
import json
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model
from backend.nis.engineering.network.physical_ports import physical_transmit_changes

def verify(_):
    snapshot = model.model()
    changes = physical_transmit_changes(snapshot['topology'], snapshot['routing'], snapshot['messages'])
    remaining = [row for row in changes if 'hardware_interface_id' in row['data']]
    assert not remaining, remaining
    messages = {str(row['id']): row for row in snapshot['messages']}
    ports = {str(row['id']): row for row in snapshot['hardware-interfaces']}
    licht = messages['46ef9d57-a71a-4e8f-903b-ef919dd740f7']
    primary = str(licht['hardware_interface_id'])
    connected = [port for node in snapshot['topology']['nodes'] for port in node.get('ports', [])
                 if str(port.get('hardwareInterfaceId')) == primary]
    assert connected and all(row['physicalNetworkId'] == ports[primary]['network_ref'] for row in connected)
    bindings = licht['configuration']['physical_transmit_bindings']
    assert any(row['hardware_interface_id'] == primary for row in bindings)
    assert ports[primary]['hardware_node_id'] == '17c07ffe-22a5-4a6a-a071-e91169ede1c4'
    return {'project': '20261009072206008-4bb505f1', 'remaining_primary_repairs': len(remaining),
            'canonical_messages': len(messages), 'licht': {'id': str(licht['id']),
            'hardware_interface_id': primary, 'network_ref': ports[primary]['network_ref'],
            'connected_topology_ports': len(connected)},
            'scope': 'Read-only check of delivered canonical planner; unused physical resources remain visible.'}

result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
                 'verify_approved_sender_alignment', Permission.READ_MODEL, {}, verify)
print('NIS_VERIFY_RESULT=' + result.model_dump_json(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
                        text=True, encoding='utf-8', capture_output=True, check=True)
records = [line.removeprefix('NIS_VERIFY_RESULT=') for line in result.stdout.splitlines() if line.startswith('NIS_VERIFY_RESULT=')]
assert len(records) == 1
payload = json.loads(records[0])
assert payload['success'], payload.get('findings')
report = {**payload['data'], 'running_image': running, 'receipt': work['active_release_receipt']}
before = json.loads((folder / 'existing-project-before-alignment.json').read_text())
after = json.loads((folder / 'existing-project-after-alignment.json').read_text())
old_messages = {str(row['id']): row for row in before['messages']}
new_messages = {str(row['id']): row for row in after['messages']}
assert old_messages.keys() == new_messages.keys()
for identifier, old in old_messages.items():
    new = new_messages[identifier]
    for key in ('name', 'description', 'interface_id', 'message_id_hex', 'dlc', 'cycle_ms', 'direction', 'configuration'):
        assert old.get(key) == new.get(key), (identifier, key)
old_routes = {str(row['id']): row for row in before['routes']}
new_routes = {str(row['id']): row for row in after['routes']}
assert old_routes.keys() == new_routes.keys()
for identifier, old in old_routes.items():
    new = new_routes[identifier]
    assert old.get('payload') == new.get('payload'), identifier
    assert (old.get('source') or {}).get('node_id') == (new.get('source') or {}).get('node_id'), identifier
    assert sorted(str(row.get('node_id')) for row in old.get('destinations', [])) == sorted(str(row.get('node_id')) for row in new.get('destinations', [])), identifier
    if str(old.get('approval_state', '')).upper() == 'APPROVED':
        assert str(new.get('approval_state', '')).upper() == 'APPROVED', identifier
snapshots = lambda workflow: {str(row['id']): row.get('job_id') for row in workflow.get('simulation_snapshots', [])}
assert snapshots(before['workflow']) == snapshots(after['workflow'])
report['preservation'] = {'message_count': len(new_messages), 'route_count': len(new_routes),
                          'all_message_contents_unchanged': True, 'route_payloads_publishers_recipients_unchanged': True,
                          'prior_route_approvals_preserved': True, 'simulation_snapshot_jobs_preserved': True}
(folder / 'production-functional-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
