"""Restore controller backbone bindings from canonical version history, atomically."""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.db import RequestUnit, get_connection, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.agent_tools import model
from backend.engineering.repository import create_object, update_object
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.physical_ports import topology_port_findings

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
project = 'network-project-20260909082213746-780a13ef'
token = activate_project(project)
unit = RequestUnit(project)
try:
    workflow = WorkflowStatusService(project)
    state = workflow.get()
    topology = deepcopy(state['topology'])
    hardware = model.objects('HardwareNode')
    nodes = {str(n['id']): n for n in hardware}
    physical = model.objects('HardwareNetworkInterface')
    ports = {str(p['id']): p for p in physical}
    networks = {str(n['id']): n for n in model.networks()}
    interfaces = {str(i['id']): i for i in model.objects('Interface')}
    with get_connection() as connection:
        versions = connection.execute("SELECT object_id, snapshot FROM engineering_object_versions WHERE project_id = %s AND object_type = 'HardwareNetworkInterface' AND version = 1", (project,)).fetchall()
    original = {str(v['object_id']): v['snapshot'] for v in versions}
    changes, skipped = [], []
    gateway = next(n for n in hardware if n['device_type'] == 'Gateway' and n['name'] == 'System')

    def ensure_port(node_id, network, technology):
        existing = next((p for p in physical if str(p['hardware_node_id']) == node_id and p.get('network_ref') == network and p['technology'] == technology), None)
        if existing:
            return existing
        data = {'name': networks[network]['name'], 'hardware_node_id': node_id, 'network_ref': network,
                'technology': technology, 'channel_index': 1 + max([int(p.get('channel_index') or 0) for p in physical if str(p['hardware_node_id']) == node_id and p['technology'] == technology] or [0]),
                'physical_port_ref': 'restored-backbone-' + uuid4().hex,
                'source': 'ai_generated', 'review_state': 'reviewed', 'approval_state': 'approved',
                'provenance': {'source': 'canonical-version-history', 'reason': 'Original backbone was incorrectly reused for local IO.'}}
        port = create_object('HardwareNetworkInterface', data) if args.apply else {**data, 'id': 'planned-' + uuid4().hex}
        physical.append(port)
        return port

    def canvas_port(port):
        node = next(n for n in topology['nodes'] if str(n.get('engineeringId')) == str(port['hardware_node_id']))
        existing = next((p for p in node['ports'] if str(p.get('hardwareInterfaceId')) == str(port['id'])), None)
        if existing:
            return node, existing
        data = {'id': 'topology-port-' + str(port['id']), 'name': networks[port['network_ref']]['name'],
                'bus': {'CAN_FD': 'can_fd', 'ETHERNET': 'automotive_ethernet', 'Ethernet': 'automotive_ethernet'}.get(port['technology'], port['technology'].lower()),
                'hardwareInterfaceId': str(port['id']), 'engineeringId': str(port['id']),
                'physicalNetworkId': port['network_ref'], 'physicalNetworkName': networks[port['network_ref']]['name'], 'side': 'right', 'offset': 0.5}
        node['ports'].append(data)
        return node, data

    for message in model.objects('Message'):
        interface = interfaces.get(str(message.get('interface_id')), {})
        owner = nodes.get(str(interface.get('hardware_node_id')), {})
        if owner.get('device_type') in (None, 'Gateway', 'SensorController', 'ActuatorController'):
            continue
        old = original.get(str(message.get('hardware_interface_id')), {})
        current = ports.get(str(message.get('hardware_interface_id')), {})
        network = str(old.get('network_ref') or '')
        if not network or '-IO-' in network or '-IO-' not in str(current.get('network_ref') or ''):
            continue
        # Only original primary channels qualify, never generated actuator commands.
        if old.get('channel_index') != 1:
            continue
        compatible = [p for p in physical if str(p['hardware_node_id']) == str(owner['id']) and p['technology'] == old['technology'] and (p.get('network_ref') == network or str(p.get('network_ref') or '').startswith(network + '-S'))]
        if owner['name'] == 'Motorsteuerung':
            network = 'Antriebsstrang_01-S01'  # User-confirmed connection to Abgasnachbehandlung / Antrieb_36.
        elif len(compatible) == 1:
            network = compatible[0]['network_ref']
        elif len(compatible) > 1:
            skipped.append({'hardware': owner['name'], 'reason': 'Multiple backbone segments require explicit selection'})
            continue
        if network not in networks:
            skipped.append({'hardware': owner['name'], 'reason': 'Original network not declared', 'network': network})
            continue
        port = ensure_port(str(owner['id']), network, old['technology'])
        peer = ensure_port(str(gateway['id']), network, old['technology'])
        left, lp = canvas_port(port)
        right, rp = canvas_port(peer)
        if not any({e.get('sourcePort'), e.get('targetPort')} == {lp['id'], rp['id']} for e in topology['edges']):
            topology['edges'].append({'id': 'restored-backbone-' + str(port['id']), 'name': owner['name'] + ' — ' + gateway['name'],
                'source': left['id'], 'target': right['id'], 'sourcePort': lp['id'], 'targetPort': rp['id'],
                'bus': lp['bus'], 'physicalNetworkId': network, 'physicalNetworkName': networks[network]['name'],
                'direction': 'BIDIRECTIONAL', 'origin': 'CANONICAL_HISTORY_RESTORATION', 'relationType': 'CONNECTED_VIA', 'engineeringRelationId': 'restored-backbone-' + str(port['id']), 'routingEntryIds': [], 'routingMetadata': {}})
        config = deepcopy(message.get('configuration') or {})
        # A prior implicit primary binding is repaired; explicit multi-bus contracts are retained for review.
        if config.get('physical_transmit_bindings') and str(port['id']) not in {str(b.get('hardware_interface_id')) for b in config['physical_transmit_bindings']}:
            raise ValueError('Explicit transmit contract requires review: ' + message['name'])
        if args.apply:
            update_object('Message', str(message['id']), {'expected_version': message['version'], 'hardware_interface_id': str(port['id'])})
        changes.append({'hardware': owner['name'], 'message': message['name'], 'message_id': str(message['id']), 'before': current.get('network_ref'), 'after': network, 'bus': networks[network]['name']})
    findings = topology_port_findings(topology, hardware, physical)
    if findings:
        raise ValueError(json.dumps(findings))
    if args.apply:
        workflow.save_topology(topology, actor='backbone-history-repair')
        workflow.mark_changed('engineering_model', reason='Historisch bestätigte Backbone-Anschlüsse wiederhergestellt', actor='backbone-history-repair')
        unit.finish(True)
    print(json.dumps({'applied': args.apply, 'changes': changes, 'skipped': skipped, 'physical_findings': findings, 'port_count': len(physical)}, ensure_ascii=False))
finally:
    unit.close()
    reset_project(token)
    close_pool()
