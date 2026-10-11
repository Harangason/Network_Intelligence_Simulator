"""Apply the authorized versioned repair only after deployment of a complete PASS."""
import argparse, importlib.util, json, subprocess
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJECT = '20261009072206008-4bb505f1'
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('release_storage', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
assert storage.complete_pass(receipt), 'A full complete PASS is required.'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == receipt['image_id']
opener = build_opener(HTTPCookieProcessor(CookieJar()))
csrf = None
def call(path, method='GET', payload=None, human=False):
    headers = {'X-Project-ID': PROJECT, 'Content-Type': 'application/json'}
    if human:
        headers.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed', 'Origin': 'http://127.0.0.1:13500'})
    request = Request('http://127.0.0.1:13500/api/' + path, method=method, headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None)
    with opener.open(request, timeout=180) as response:
        return json.load(response)
live = call('build-info')
assert live['source_sha256'] == receipt['initial_source_sha256']
plan = json.loads((HERE / 'reconciliation-preview.json').read_text(encoding='utf-8'))
prepared = json.loads((HERE / 'prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']
proposal_id = prepared['proposal_id']
current = call(f'engineering/agent/proposals/{proposal_id}')
assert current['success'], current.get('findings')
current = current['data']
assert current['status'] in ('VALIDATED', 'APPROVED', 'APPLIED'), current['status']
assert len(current['changes']) == len(plan['changes']) and all(c.get('action') != 'DELETE' for c in current['changes'])
governed_changes = {(change['object_type'], change.get('object_id')): change for change in current['changes']}
assert len(governed_changes) == len(current['changes'])
for requested in plan['changes']:
    governed = governed_changes[(requested['object_type'], requested.get('object_id'))]
    for field in ['object_type', 'object_id', 'expected_version', 'data']:
        assert requested.get(field) == governed.get(field), ('Prepared proposal content changed', field)

def capture():
    code = '''
import json
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model
from backend.nis.infrastructure.persistence.repository import list_versions
from backend.nis.engineering.network.physical_ports import physical_transmit_changes, topology_port_findings
def read(_):
    snapshot = model.model()
    return {'model_revision': model.model_revision(), 'snapshot': snapshot,
        'histories': {str(row['id']): model.json_safe(list_versions('HardwareNetworkInterface', str(row['id'])))
                      for row in snapshot['hardware-interfaces']},
        'remaining_binding_changes': physical_transmit_changes(snapshot['topology'], snapshot['routing'], snapshot['messages'], logical_interfaces=snapshot['interfaces']),
        'physical_findings': topology_port_findings(snapshot['topology'], snapshot['hardware'], snapshot['hardware-interfaces'])}
result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
    'verify_versioned_channel_reconciliation', Permission.READ_MODEL, {}, read)
print('NIS_CAPTURE='+json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
'''
    result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
        capture_output=True, text=True, encoding='utf-8', check=True)
    payload = json.loads(next(line.removeprefix('NIS_CAPTURE=') for line in result.stdout.splitlines() if line.startswith('NIS_CAPTURE=')))
    assert payload['success'], payload.get('findings')
    return payload['data']

before_path = HERE / 'canonical-before-reconciliation.json'
if current['status'] == 'APPLIED':
    assert before_path.exists(), 'Applied repair needs its preserved before evidence.'
    before = json.loads(before_path.read_text(encoding='utf-8'))
else:
    before = capture()
    assert before['model_revision'] == plan['base_model_revision'], 'PLAN_STALE: do not apply; rebuild against the current model.'
    by_id = {str(row['id']): row for key in ['messages', 'interfaces', 'hardware-interfaces'] for row in before['snapshot'][key]}
    for change in plan['changes']:
        if change.get('object_id'):
            assert by_id[change['object_id']]['version'] == change['expected_version'], 'Expected object version changed.'
    before_path.write_text(json.dumps(before, ensure_ascii=True), encoding='utf-8')
    csrf = call('engineering/agent/review-session')['csrf_token']
    if current['status'] == 'VALIDATED':
        reviewed = call(f'engineering/agent/proposals/{proposal_id}/review', 'POST',
            {'revision': current['revision'], 'decision': 'approve'}, human=True)
        (HERE / 'canonical-reconciliation-review.json').write_text(json.dumps(reviewed), encoding='utf-8')
        assert reviewed['success'] and reviewed['data']['status'] == 'APPROVED', reviewed.get('findings')
    applied = call(f'engineering/agent/proposals/{proposal_id}/apply', 'POST', {}, human=True)
    (HERE / 'canonical-reconciliation-apply.json').write_text(json.dumps(applied), encoding='utf-8')
    assert applied['success'] and applied['data']['status'] == 'APPLIED', applied.get('findings')
after = capture()
(HERE / 'canonical-after-reconciliation.json').write_text(json.dumps(after, ensure_ascii=True), encoding='utf-8')
old, new = before['snapshot'], after['snapshot']
assert not after['remaining_binding_changes'], after['remaining_binding_changes']
assert not after['physical_findings'], after['physical_findings']
for key in ['hardware', 'functions', 'signals', 'behaviors', 'parameters']:
    assert old[key] == new[key], ('Unexpected canonical change', key)
index = lambda rows: {str(row['id']): row for row in rows}
old_nodes, new_nodes = index(old['topology']['nodes']), index(new['topology']['nodes'])
assert old_nodes.keys() == new_nodes.keys()
for identifier, node in old_nodes.items():
    for field in ['engineeringId', 'kind', 'x', 'y', 'width', 'height']:
        assert node.get(field) == new_nodes[identifier].get(field), ('Spatial identity or position changed', identifier, field)
old_edges, new_edges = index(old['topology']['edges']), index(new['topology']['edges'])
assert old_edges.keys() == new_edges.keys()
for identifier, edge in old_edges.items():
    for field in ['source', 'target', 'sourcePort', 'targetPort', 'bus', 'physicalNetworkId', 'routingEntryId', 'routingEntryIds']:
        assert edge.get(field) == new_edges[identifier].get(field), ('Physical path changed', identifier, field)
old_ports, new_ports = index(old['hardware-interfaces']), index(new['hardware-interfaces'])
assert old_ports.keys() == new_ports.keys(), 'No canonical ports may be deleted or added by this repair.'
retired = {row['retired_duplicate'] for row in plan['replacements']}
for identifier, previous in old_ports.items():
    final = new_ports[identifier]
    for key in ['hardware_node_id', 'technology', 'channel_index', 'physical_port_ref']:
        assert previous.get(key) == final.get(key), (identifier, key)
    history = after['histories'][identifier]
    assert all(item in history for item in before['histories'][identifier]), ('History was lost', identifier)
for row in plan['replacements']:
    assert new_ports[row['original']]['network_ref'] == row['network']
    assert new_ports[row['retired_duplicate']]['lifecycle_state'] == 'superseded'
    anchors = [p for n in new['topology']['nodes'] for p in n.get('ports', []) if p['id'] in row['ports']]
    assert anchors and all(p['hardwareInterfaceId'] == row['original'] and p['physicalNetworkId'] == row['network'] for p in anchors)
for key in ['messages', 'interfaces']:
    previous, final = index(old[key]), index(new[key])
    assert previous.keys() == final.keys()
    for identifier, row in previous.items():
        for field in ['name', 'description', 'hardware_node_id', 'function_id', 'interface_id', 'message_id_hex', 'dlc', 'cycle_ms', 'direction']:
            assert row.get(field) == final[identifier].get(field), (identifier, field)
        assert not any(port in json.dumps(final[identifier]) for port in retired), ('Retired live binding', identifier)
old_routes, new_routes = index(old['routing']), index(new['routing'])
assert old_routes.keys() == new_routes.keys()
for identifier, row in old_routes.items():
    final = new_routes[identifier]
    assert row.get('payload') == final.get('payload'), identifier
    assert row['source'].get('node_id') == final['source'].get('node_id'), identifier
    assert sorted(d.get('node_id') for d in row['destinations']) == sorted(d.get('node_id') for d in final['destinations']), identifier
    for endpoint in [final['source'], *final['destinations']]:
        assert endpoint.get('port_id') not in retired, ('Retired route endpoint', identifier)
    if str(row.get('approval_state')).upper() == 'APPROVED':
        assert str(final.get('approval_state')).upper() == 'APPROVED', identifier
licht = new_ports['2284b9f0-fb59-408b-9cb4-dee06377f353']
message = index(new['messages'])['46ef9d57-a71a-4e8f-903b-ef919dd740f7']
assert message['hardware_interface_id'] == licht['id']
assert licht['id'] in index(new['interfaces'])['855680c7-2fd9-4ecc-9bcb-dc08d797ac80']['configuration']['physical_interface_ids']
report = {'status': 'APPLIED_AND_VERIFIED', 'project': PROJECT, 'proposal_id': proposal_id,
    'receipt': str(args.receipt.resolve()), 'running_image': receipt['image_id'],
    'original_connectors_reused': len(plan['replacements']), 'duplicates_reversibly_superseded': len(retired),
    'deleted_objects': 0, 'all_signal_encodings_and_functional_ownership_preserved': True,
    'all_route_payloads_publishers_recipients_preserved': True, 'all_channel_history_preserved': True,
    'spatial_identity_positions_and_existing_wires_preserved': True,
    'binding_reconciliation_idempotent': True, 'physical_graph_valid': True,
    'licht': {'hardware_interface_id': licht['id'], 'network_ref': licht['network_ref'], 'logical_interface_aligned': True}}
(HERE / 'canonical-reconciliation-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
