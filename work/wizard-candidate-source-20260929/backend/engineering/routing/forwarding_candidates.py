"""Reuse reviewed, directed ECU port transitions in route proposals."""
from ..db import get_connection
from ..project_context import current_project_id


def confirmed_ecu_candidates(source_id, target_id, hardware, limit=5, *, context=None):
    # The common case needs no topology/model read. Presence of a rule is only a
    # search hint; RepairPlanner verifies confirmation, direction and saved wires.
    if not any(node.get('device_type') == 'ECU'
               and (node.get('identity') or {}).get('communication_forwarding')
               for node in hardware.values()):
        return []
    from ..communication_repair import KINDS, RepairPlanner, protocol
    context = context if context is not None else {}
    if 'forwarding_planner' not in context:
        with get_connection() as connection:
            state = connection.execute(
                'SELECT parameters, topology FROM engineering_workflow_projects WHERE project_id = %s',
                (current_project_id(),)).fetchone()
            if not state:
                return []
            ports = connection.execute(
                'SELECT * FROM engineering_hardware_interfaces WHERE project_id = %s',
                (current_project_id(),)).fetchall()
        objects = {kind: [] for kind in KINDS}
        objects.update(HardwareNode=list(hardware.values()), HardwareNetworkInterface=ports)
        context['forwarding_planner'] = RepairPlanner(state, objects, [])
    planner = context['forwarding_planner']
    sources = sorted(key for key, port in planner.active.items() if str(port['hardware_node_id']) == source_id)
    targets = sorted(key for key, port in planner.active.items() if str(port['hardware_node_id']) == target_id)
    candidates = []
    for source in sources:
        for target in targets:
            for path in planner.paths(source, target):
                transitions = [(planner.active[a], planner.active[b]) for a, b in zip(path['ports'], path['ports'][1:])]
                forwarders = [str(left['hardware_node_id']) for left, right in transitions
                              if left['network_ref'] != right['network_ref']]
                if not any(hardware[key].get('device_type') == 'ECU' for key in forwarders):
                    continue
                node_ids = []
                for port_id in path['ports']:
                    node_id = str(planner.active[port_id]['hardware_node_id'])
                    if not node_ids or node_ids[-1] != node_id:
                        node_ids.append(node_id)
                # Leaving and re-entering a device is a routing loop, even when
                # its distinct physical ports made the port walk look acyclic.
                if len(set(node_ids)) != len(node_ids):
                    continue
                connections = [{'source_interface_type': left['technology'], 'target_interface_type': right['technology'],
                                'source_network_id': left['network_ref'], 'target_network_id': right['network_ref'],
                                'source_port_id': str(left['id']), 'target_port_id': str(right['id'])}
                               for left, right in transitions if str(left['hardware_node_id']) != str(right['hardware_node_id'])]
                candidates.append({'nodes': [{'node_id': key, 'name': hardware[key]['name']} for key in node_ids],
                    'connections': connections, 'physical_paths': [path],
                    'gateways': [{'node_id': key, 'name': hardware[key]['name']} for key in dict.fromkeys(forwarders)],
                    'protocol': protocol(planner.active[source]['technology']), 'hop_count': len(connections)})
    return sorted(candidates, key=lambda item: (item['hop_count'], item['physical_paths'][0]['ports']))[:max(1, limit)]
