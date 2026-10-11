"""Detached plan only: preserve original connectors, retire generated duplicates."""
from copy import deepcopy
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
root = folder.parents[2]
sys.path.insert(0, str(root))
from backend.nis.engineering.network.physical_ports import physical_transmit_changes, topology_port_findings
from backend.nis.engineering.network.network_scene import build_network_scene

inspection = json.loads((folder / 'canonical-inspection.json').read_text(encoding='utf-8'))['data']
snapshot = inspection['snapshot']
topology = deepcopy(snapshot['topology'])
interfaces = {str(p['id']): deepcopy(p) for p in snapshot['hardware-interfaces']}
changes, replacements = [], []
for candidate in inspection['candidates']:
    original = candidate['port']
    assert original['source'] == 'ai_generated' and original['lifecycle_state'] == 'draft'
    assert set(candidate['other_references']) <= {'interfaces'}, 'Unknown live resource reference: do not merge.'
    replacement = min(candidate['replacement_channels'], key=lambda p: (p['network_ref'], p['id']))
    assert replacement['lifecycle_state'] == 'draft' and replacement['source'] == 'ai_generated'
    assert replacement['capabilities']['source'] == 'reviewed-physical-topology'
    assert original['hardware_node_id'] == replacement['hardware_node_id'] and original['technology'] == replacement['technology']
    affected_ports = []
    for node in topology['nodes']:
        for port in node.get('ports', []):
            if port.get('hardwareInterfaceId') == replacement['id']:
                assert node['engineeringId'] == original['hardware_node_id']
                assert port['physicalNetworkId'] == replacement['network_ref']
                port.update(hardwareInterfaceId=original['id'], engineeringId=original['id'], name=original['name'])
                affected_ports.append(port['id'])
    assert affected_ports
    capabilities = deepcopy(original.get('capabilities') or {})
    if 'network_id' in capabilities:
        capabilities['network_id'] = replacement['network_ref']
    if 'topology_port_id' in capabilities:
        capabilities['topology_port_id'] = min(affected_ports)
    original_delta = {'network_ref': replacement['network_ref'], 'capabilities': capabilities}
    retirement = {'lifecycle_state': 'superseded', 'provenance': {**(replacement.get('provenance') or {}),
        'physical_channel_reconciliation': {'canonical_id': original['id'], 'reason': 'Complete capacity split: original connector retained'}}}
    for row, delta in ((original, original_delta), (replacement, retirement)):
        changes.append({'action': 'UPDATE', 'object_type': 'HardwareNetworkInterface', 'object_id': row['id'],
                        'expected_version': row['version'], 'data': delta})
        interfaces[row['id']].update(delta)
    replacements.append({'hardware': original['hardware_node_id'], 'original': original['id'],
                         'retired_duplicate': replacement['id'], 'network': replacement['network_ref'],
                         'name': original['name'], 'ports': affected_ports})

ports = {p['id']: p for n in topology['nodes'] for p in n.get('ports', [])}
for edge in topology['edges']:
    for side in ('source', 'target'):
        port = ports[edge[side+'Port']]
        if any(port['id'] in p['ports'] for p in replacements):
            edge[side+'InterfaceName'] = port['name']
positions = {node['id']: {key: node[key] for key in ('x', 'y', 'width', 'height') if key in node}
             for node in topology['nodes']}
topology = build_network_scene(topology, positions=positions)
findings = topology_port_findings(topology, snapshot['hardware'], list(interfaces.values()))
assert not findings, findings
binding_changes = physical_transmit_changes(topology, snapshot['routing'], snapshot['messages'], logical_interfaces=snapshot['interfaces'])
changes.extend(binding_changes)
changes.append({'object_type': 'NetworkTopology', 'data': {'name': 'Ursprüngliche Hardwareanschlüsse konsistent weiterverwenden', 'topology': topology}})
effective_messages = {str(m['id']): deepcopy(m) for m in snapshot['messages']}
effective_logical = {str(i['id']): deepcopy(i) for i in snapshot['interfaces']}
for change in binding_changes:
    target = effective_messages if change['object_type'] == 'Message' else effective_logical
    target[change['object_id']].update(change['data'])
retired_ids = {row['retired_duplicate'] for row in replacements}
for row in [*effective_messages.values(), *effective_logical.values()]:
    assert not any(identifier in json.dumps(row) for identifier in retired_ids), (row['id'], 'Live reference to a retired duplicate')
assert not physical_transmit_changes(topology, snapshot['routing'], list(effective_messages.values()), logical_interfaces=list(effective_logical.values()))
report = {'status': 'DETACHED_PREVIEW', 'project': snapshot['project_id'], 'base_model_revision': inspection['model_revision'],
          'replacements': replacements, 'changes': changes,
          'checks': {'original_connector_ids_preserved': True, 'original_versions_and_relations_preserved': True,
                     'retirement_is_explicit_and_reversible': True, 'no_deleted_objects': True,
                     'no_live_message_or_logical_reference_to_retired_duplicates': True, 'physical_graph_valid': True,
                     'binding_reconciliation_idempotent': True},
          'scope': 'Local detached preview; no production object changes or tested-release claim.'}
(folder / 'reconciliation-preview.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'status': report['status'], 'original_connectors_reused': len(replacements),
                  'duplicates_to_retire': len(retired_ids), 'message_updates': sum(c['object_type']=='Message' for c in binding_changes),
                  'logical_updates': sum(c['object_type']=='Interface' for c in binding_changes), 'deleted': 0}))
