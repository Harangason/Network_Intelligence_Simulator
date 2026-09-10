"""Reviewable, atomic reassignment of systems and their physical communication."""
from collections import defaultdict, deque
from copy import deepcopy
import hashlib
import json
import re

from .models import EngineeringValidationError
from .network_scene import build_network_scene, confirmed_groups
from .physical_ports import topology_port_findings
from .bus_settings import normalize_bus_limits
from .topology_sync import BUS_TO_INTERFACE_TYPE
from .routing.network_sync import BUS_PROTOCOLS

INACTIVE = {'REJECTED', 'SUPERSEDED', 'DEPRECATED', 'OUTDATED'}


def _refs(route, signals=None):
    p = route.get('payload') or {}
    parents = [(signals or {}).get(str(s), {}).get('message_id') for s in p.get('signal_ids', [])]
    return set(filter(None, [p.get('message_id'), *p.get('message_ids', []), *parents]))


def plan_assignment(state, objects, routes, request):
    topology = deepcopy(state['topology'])
    scene = topology.get('scene') or {}
    nodes = {n['id']: n for n in topology.get('nodes', [])}
    hardware = {str(h['id']): h for h in objects['HardwareNode']}
    by_hw = {str(n.get('engineeringId')): n for n in nodes.values()}
    raw = request.get('node_ids')
    if not isinstance(raw, list) or not raw or any(not isinstance(n, str) or n not in nodes for n in raw):
        raise EngineeringValidationError('Bitte vorhandene Geräte oder Systemrahmen markieren.')
    selected = set(raw)
    if any(nodes[n].get('kind') == 'gateway' for n in selected):
        raise EngineeringValidationError('Ein zentrales Gateway kann nicht in einen Systemrahmen verschoben werden.')
    kind, target_id = request.get('target_kind'), request.get('target_id')
    bus_move = kind == 'bus'
    source_network = request.get('source_network_id')
    targets = scene.get('buses' if bus_move else 'clusters' if kind == 'cluster' else 'frames', [])
    target = next((t for t in targets if t['id'] == target_id), None)
    if kind not in {'cluster', 'frame', 'bus'} or not target:
        raise EngineeringValidationError('Das gewählte Ziel existiert nicht mehr.')
    if bus_move:
        if len(selected) != 1:
            raise EngineeringValidationError('Zum Umhängen bitte genau ein Gerät auswählen.')
        source_bus = next((b for b in scene.get('buses', []) if b['id'] == source_network), None)
        node_id = next(iter(selected))
        if not source_bus or not any(b['nodeId'] == node_id for b in source_bus['branches']):
            raise EngineeringValidationError('Das Gerät besitzt keinen Anschluss am Ausgangsbus.')
        cluster = next((c for c in scene['clusters'] if node_id in c['memberIds']), None)
        if not cluster or not any(b['nodeId'] in cluster['memberIds'] for b in target['branches']):
            raise EngineeringValidationError('Der Zielbus muss im selben Cluster liegen.')
        if source_network == target_id:
            raise EngineeringValidationError('Das Gerät ist bereits am gewählten Bus angeschlossen.')
        if source_bus['technology'] != target['technology']:
            raise EngineeringValidationError('Zum Umhängen einen Bus desselben Typs wählen. Den Bustyp separat ändern.')
        if (source_bus['local'] != target['local'] or
                (source_bus['local'] and (source_bus['frameId'] != target['frameId'] or node_id == source_bus['frameId']))):
            raise EngineeringValidationError('Lokale Geräte können nur zwischen Bussen ihres Systemrahmens umgehängt werden.')
        if any(b['nodeId'] == node_id for b in target['branches']):
            raise EngineeringValidationError('Das Gerät besitzt bereits einen Anschluss am Zielbus; die Ports dürfen nicht doppelt zugeordnet werden.')
        target = {**target, 'label': target['name'], 'clusterId': cluster['id']}
    if kind == 'frame' and nodes[target_id].get('kind') != 'ecu':
        raise EngineeringValidationError('Ein Systemrahmen benötigt ein Steuergerät als Eigentümer.')
    prompt = (state.get('context', {}).get('wizard_request') or {}).get('prompt', '')
    _, owners = confirmed_groups(topology, prompt)
    # Selecting a controller always includes its descendants, even when offscreen.
    while not bus_move:
        expanded = selected | {n for n, owner in owners.items() if owner in selected}
        if expanded == selected:
            break
        selected = expanded
    if kind == 'frame' and target_id in selected:
        raise EngineeringValidationError('Ein System kann nicht in sich selbst oder einen eigenen Bestandteil verschoben werden.')
    roots = selected - {n for n in selected if owners.get(n) in selected}
    cluster_id = target_id if kind == 'cluster' else target['clusterId']
    cluster = next(c for c in scene['clusters'] if c['id'] == cluster_id)
    old_cluster = {n: c for c in scene['clusters'] for n in c['memberIds']}
    roots = {n for n in roots if bus_move or (kind == 'frame' and owners.get(n) != target_id) or
             (kind == 'cluster' and (old_cluster.get(n, {}).get('id') != cluster_id or n in owners))}
    if not roots:
        raise EngineeringValidationError('Die Auswahl gehört bereits vollständig zum gewählten Ziel.')
    def selected_root(node_id):
        while node_id not in roots and node_id in owners:
            node_id = owners[node_id]
        return node_id in roots
    selected = {n for n in selected if selected_root(n)}
    changes, creations = {}, []
    effective = {kind: {str(o['id']): deepcopy(o) for o in rows} for kind, rows in objects.items()}

    def patch(obj_type, identifier, values):
        effective[obj_type][identifier].update(deepcopy(values))
        changes.setdefault((obj_type, identifier), {}).update(deepcopy(values))

    def create(obj_type, key, values):
        identifier = '$assignment-' + hashlib.sha256((obj_type + key).encode()).hexdigest()[:20]
        if identifier not in effective[obj_type]:
            values = {**deepcopy(values), 'source': 'manual', 'review_state': 'reviewed', 'approval_state': 'approved',
                      'provenance': {**values.get('provenance', {}), 'origin': 'network-assignment'}}
            creations.append({'object_type': obj_type, 'local_ref': identifier, 'data': values})
            effective[obj_type][identifier] = {**values, 'id': identifier}
        return identifier

    membership = []
    for node_id in sorted(selected):
        if bus_move:
            continue
        node = nodes[node_id]
        hw_id = str(node.get('engineeringId') or '')
        if hw_id not in hardware:
            raise EngineeringValidationError(f"{node['name']} besitzt keine kanonische Modellreferenz.")
        identity = deepcopy(hardware[hw_id].get('identity') or {})
        identity.update(cluster_id=cluster_id, cluster_name=cluster['label'], cluster_source='network-editor')
        node.update(clusterId=cluster_id, clusterName=cluster['label'])
        if node_id in roots:
            owner_id = nodes[target_id]['engineeringId'] if kind == 'frame' else None
            identity.update(system_owner_id=owner_id, system_owner_source='network-editor')
            identity.pop('systemOwnerId', None)
            node.update(systemOwnerId=owner_id, systemOwnerSource='network-editor')
        patch('HardwareNode', hw_id, {'identity': identity})
        membership.append({'id': node_id, 'name': node['name'], 'from_cluster': old_cluster.get(node_id, {}).get('label', 'Nicht zugeordnet'),
                           'from_frame': nodes.get(owners.get(node_id), node).get('name'), 'to_cluster': cluster['label'],
                           'to_frame': target['label'] if kind == 'frame' else node['name'] if node_id in roots else nodes.get(owners.get(node_id), node)['name']})

    networks = deepcopy(state['parameters'].get('networks') or [])
    declared = {str(n['id']): n for n in networks}
    limits = normalize_bus_limits((state.get('context', {}).get('engineering_wizard_settings') or {}).get('bus_participant_limits') or {})
    participants = defaultdict(set)
    for n in nodes.values():
        for p in n.get('ports', []):
            participants[p.get('physicalNetworkId')].add(n['id'])
    assigned_networks = {}
    bus_changes = []
    rewired_routes = set()

    def choose_network(bus, root):
        if bus_move:
            if target_id not in declared:
                raise EngineeringValidationError('Der Zielbus ist nicht in den Parametern hinterlegt.')
            limit = limits.get(bus, 0)
            if limit and len(participants[target_id] | {root}) > limit:
                raise EngineeringValidationError('Die eingestellte Teilnehmergrenze des Zielbusses wäre überschritten.')
            return target_id
        cache_key = (bus, root)
        if cache_key in assigned_networks:
            return assigned_networks[cache_key]
        candidates = []
        for b in scene['buses']:
            if b['technology'] != bus:
                continue
            match = b.get('local') and b.get('frameId') == target_id if kind == 'frame' else (
                not b.get('local') and any(br['nodeId'] in target['memberIds'] for br in b['branches']))
            if match:
                candidates.append(b['id'])
        candidates.extend(n['id'] for n in networks if n.get('assignment_target') == target_id and n.get('technology') == bus)
        for network_id in sorted(set(candidates), key=lambda key: (len(participants[key]), key)):
            limit = limits.get(bus, 0)
            if not limit or len(participants[network_id] | {root}) <= limit:
                break
        else:
            ordinal = 1
            network_id = f'assigned-{target_id}-{bus}-{ordinal}'
            while network_id in declared:
                ordinal += 1
                network_id = f'assigned-{target_id}-{bus}-{ordinal}'
            network = {'id': network_id, 'name': f"{target['label']} {BUS_PROTOCOLS[bus].replace('_', '-')} {ordinal:02}",
                       'technology': bus, 'protocol': BUS_PROTOCOLS[bus], 'assignment_target': target_id, 'cluster_id': cluster_id}
            from .naming import is_ethernet, new_bus_name
            if is_ethernet(bus):
                network.update(name=new_bus_name(network_id, networks, technology=bus, context=target['label']),
                               name_source='generated', name_context=target['label'])
            networks.append(network)
            declared[network_id] = network
        participants[network_id].add(root)
        assigned_networks[cache_key] = network_id
        return network_id

    def channel(node, bus, network, existing=None):
        name = declared[network].get('name') or network
        if existing:
            port = existing
            identifier = str(port.get('hardwareInterfaceId'))
            if identifier not in effective['HardwareNetworkInterface']:
                raise EngineeringValidationError('Ein markiertes Gerät besitzt keinen gültigen physischen Anschluss.')
            hwi = effective['HardwareNetworkInterface'][identifier]
            patch('HardwareNetworkInterface', identifier, {'network_ref': network, 'name': name,
                  'capabilities': {**hwi.get('capabilities', {}), 'network_id': network}, 'static_load': None, 'runtime_load': None})
        else:
            port = next((p for p in node['ports'] if p.get('physicalNetworkId') == network and p['bus'] == bus), None)
            if port:
                return port
            channels = [h for h in effective['HardwareNetworkInterface'].values() if str(h.get('hardware_node_id')) == node['engineeringId'] and h.get('technology') == BUS_TO_INTERFACE_TYPE[bus]]
            compatible = next((h for h in channels if h.get('network_ref') == network), None)
            identifier = str(compatible['id']) if compatible else create('HardwareNetworkInterface', node['id'] + network, {
                'hardware_node_id': node['engineeringId'], 'technology': BUS_TO_INTERFACE_TYPE[bus], 'name': name,
                'network_ref': network, 'channel_index': max([0, *[h.get('channel_index') or 0 for h in channels]]) + 1,
                'physical_port_ref': 'assignment-' + hashlib.sha256((node['id'] + network).encode()).hexdigest()[:16]})
            port = {'id': 'assignment-port-' + hashlib.sha256((node['id'] + network).encode()).hexdigest()[:20],
                    'hardwareInterfaceId': identifier, 'engineeringId': identifier, 'bus': bus, 'side': 'bottom', 'offset': .5}
            node['ports'].append(port)
        port.update(physicalNetworkId=network, physicalNetworkName=name, name=name)
        return port

    # Only the external attachment changes; internal buses travel with a whole frame.
    old_owners = {}
    for root in sorted(roots):
        node = nodes[root]
        old_owners[root] = owners.get(root)
        external = [e for e in topology['edges'] if (e['source'] == root and e['target'] not in selected) or
                    (e['target'] == root and e['source'] not in selected)]
        if bus_move:
            external = [e for e in external if e.get('physicalNetworkId') == source_network]
            if not external:
                raise EngineeringValidationError('Der Ausgangsbus besitzt keine gespeicherte Verbindung zu diesem Gerät.')
        for edge in external:
            rewired_routes.update(filter(None, [edge.get('routingEntryId'), *edge.get('routingEntryIds', [])]))
            bus = edge['bus']
            network = choose_network(bus, root)
            hub = nodes[target['frameId']] if bus_move and target['local'] else nodes[target_id] if kind == 'frame' else next((nodes[b['nodeId']] for b in
                next((b for b in scene['buses'] if b['id'] == network), {}).get('branches', []) if nodes[b['nodeId']]['kind'] == 'gateway'), None)
            if hub is None and not bus_move:
                hub = next((n for n in nodes.values() if n['kind'] == 'gateway'), None)
            if hub is None:
                raise EngineeringValidationError('Für das Zielcluster fehlt ein Gateway.')
            own_side = 'source' if edge['source'] == root else 'target'
            other_side = 'target' if own_side == 'source' else 'source'
            own_port = next(p for p in node['ports'] if p['id'] == edge[own_side + 'Port'])
            old_network = own_port['physicalNetworkId']
            channel(node, bus, network, own_port)
            hub_port = channel(hub, bus, network)
            participants[network].add(hub['id'])
            edge.update({other_side: hub['id'], other_side + 'Port': hub_port['id'],
                         'physicalNetworkId': network, 'physicalNetworkName': declared[network].get('name') or network,
                         'sourceInterfaceName': declared[network].get('name') or network,
                         'targetInterfaceName': declared[network].get('name') or network})
            bus_changes.append({'device': node['name'], 'from': declared.get(old_network, {}).get('name', old_network),
                                'to': declared[network].get('name', network), 'technology': BUS_PROTOCOLS[bus]})
    connected = {e[side + 'Port'] for e in topology['edges'] for side in ('source', 'target')}
    for n in nodes.values():
        n['ports'] = [p for p in n['ports'] if p['id'] in connected]

    active = [deepcopy(r) for r in routes if r.get('status') not in INACTIVE]
    affected = set()
    moved_hw = {nodes[n]['engineeringId'] for n in selected}
    if bus_move and target['local']:
        # A multicast command needs one source attachment per physical bus.
        # Retain its existing recipients and create a route for the moved branch.
        for route in list(active):
            if str(route['source']['node_id']) != nodes[target['frameId']]['engineeringId']:
                continue
            moved = [d for d in route['destinations'] if str(d['node_id']) in moved_hw and d.get('network_id') == source_network]
            if not moved or len(moved) == len(route['destinations']):
                continue
            branch = deepcopy(route)
            branch.update(id='$assignment-route-' + hashlib.sha256((str(route['id']) + target_id).encode()).hexdigest()[:20],
                          destinations=deepcopy(moved), _assignment_new=True)
            route['destinations'] = [d for d in route['destinations'] if d not in moved]
            for item in (route, branch):
                item['name'] = item['source'].get('node_name', '') + ' → ' + ', '.join(d.get('node_name', '') for d in item['destinations'])
            active.append(branch)
            affected.add(str(route['id']))
    old_to_new = {nodes[root]['engineeringId']: (nodes[owner]['engineeringId'], nodes[target_id]['engineeringId'])
                  for root, owner in old_owners.items() if owner and kind == 'frame'}
    message_map, signal_map = {}, {}

    def logical_interface(node_id, protocol):
        candidates = sorted((i for i in effective['Interface'].values() if str(i.get('hardware_node_id')) == node_id and i.get('interface_type') == protocol), key=lambda i: str(i['id']))
        if candidates:
            return str(candidates[0]['id'])
        node = by_hw[node_id]
        return create('Interface', node_id + protocol, {'name': node['name'], 'hardware_node_id': node_id,
                      'function_id': node.get('engineeringFunctionId'), 'interface_type': protocol})

    for route in active:
        source_id = str(route['source']['node_id'])
        destination_ids = {str(d['node_id']) for d in route['destinations']}
        endpoints = [route['source'], *route['destinations']]
        directly_affected = (any(str(e.get('node_id')) in moved_hw and e.get('network_id') == source_network for e in endpoints)
                             if bus_move else source_id in moved_hw or bool(destination_ids & moved_hw))
        if not directly_affected and str(route['id']) not in rewired_routes and str(route['id']) not in affected:
            continue
        affected.add(str(route['id']))
        for dest in route['destinations']:
            if source_id in old_to_new and str(dest['node_id']) == old_to_new[source_id][0]:
                dest.update(node_id=old_to_new[source_id][1], node_name=by_hw[old_to_new[source_id][1]]['name'])
                dest['interface_id'] = logical_interface(dest['node_id'], dest['protocol'])
        command_targets = {old_to_new[d][1] for d in destination_ids if d in old_to_new and old_to_new[d][0] == source_id}
        if command_targets:
            moved_destinations = [d for d in route['destinations'] if str(d['node_id']) in old_to_new and old_to_new[str(d['node_id'])][0] == source_id]
            if len(moved_destinations) < len(route['destinations']):
                # Preserve the original command for the remaining recipients and
                # migrate only the selected branch of a multicast route.
                branch = deepcopy(route)
                branch.update(id='$assignment-route-' + hashlib.sha256((str(route['id']) + target_id).encode()).hexdigest()[:20],
                              destinations=deepcopy(moved_destinations), _assignment_new=True)
                active.append(branch)
                route['destinations'] = [d for d in route['destinations'] if d not in moved_destinations]
                route['name'] = route['source'].get('node_name', '') + ' → ' + ', '.join(d.get('node_name', '') for d in route['destinations'])
                continue
            new_source = next(iter(command_targets))
            interface_id = logical_interface(new_source, route['source']['protocol'])
            route['source'].update(node_id=new_source, node_name=by_hw[new_source]['name'], interface_id=interface_id)
            for message_id in sorted(_refs(route, effective['Signal'])):
                key = (message_id, new_source)
                if key not in message_map:
                    message = effective['Message'][message_id]
                    clone = deepcopy(message)
                    clone.update(interface_id=interface_id, hardware_interface_id=None)
                    old_name, new_name = by_hw[source_id]['name'], by_hw[new_source]['name']
                    if clone.get('name', '').startswith(old_name):
                        clone['name'] = new_name + clone['name'][len(old_name):]
                    message_map[key] = create('Message', message_id + new_source, clone)
                    for signal in list(effective['Signal'].values()):
                        if str(signal.get('message_id')) == message_id:
                            signal_map[(str(signal['id']), new_source)] = create('Signal', str(signal['id']) + new_source,
                                {**signal, 'message_id': message_map[key]})
            explicit_messages = _refs(route)
            route['payload']['message_ids'] = [message_map[(m, new_source)] for m in sorted(explicit_messages)]
            route['payload']['message_id'] = route['payload']['message_ids'][0] if route['payload']['message_ids'] else None
            route['payload']['signal_ids'] = [signal_map.get((s, new_source), s) for s in route['payload'].get('signal_ids', [])]
        route['name'] = route['source'].get('node_name', '') + ' → ' + ', '.join(d.get('node_name', '') for d in route['destinations'])

    # Rebuild paths on the resulting physical graph, then bind every route endpoint.
    adjacency = defaultdict(list)
    for e in topology['edges']:
        adjacency[e['source']].append((e['target'], e))
        adjacency[e['target']].append((e['source'], e))
    def route_path(source, destination, source_bus=None, destination_bus=None):
        queue = deque([(source, [], {source})])
        while queue:
            current, path, visited = queue.popleft()
            if current == destination:
                return path
            for neighbor, edge in sorted(adjacency[current], key=lambda p: p[1]['id']):
                if not path and source_bus and edge['physicalNetworkId'] != source_bus:
                    continue
                if neighbor == destination and destination_bus and edge['physicalNetworkId'] != destination_bus:
                    continue
                if neighbor not in visited:
                    queue.append((neighbor, [*path, edge], visited | {neighbor}))
        raise EngineeringValidationError('Die neue Zuordnung besitzt keinen vollständigen physischen Kommunikationspfad.')
    for e in topology['edges']:
        ids = set(filter(None, [e.get('routingEntryId'), *e.get('routingEntryIds', [])]))
        if not ids.intersection(affected):
            continue
        ids -= affected
        e['routingEntryIds'] = sorted(ids)
        e['routingEntryId'] = next(iter(sorted(ids)), None)
        e['routingMetadata'] = {k: v for k, v in (e.get('routingMetadata') or {}).items() if k not in affected}
    route_changes = []
    for route in active:
        if str(route['id']) not in affected:
            continue
        paths, hops, gateways, transformations = [], [], [], []
        source_node = by_hw[str(route['source']['node_id'])]
        def endpoint_bus(endpoint, node, opposite_moved):
            if not bus_move:
                return None
            network = endpoint.get('network_id')
            if network == source_network and (node['id'] in selected or
                    (opposite_moved and (node['kind'] == 'gateway' or (target['local'] and node['id'] == target['frameId'])))):
                return target_id
            return network
        source_bus = endpoint_bus(route['source'], source_node, any(str(d['node_id']) in moved_hw for d in route['destinations']))
        for destination in route['destinations']:
            dest_node = by_hw[str(destination['node_id'])]
            destination_bus = endpoint_bus(destination, dest_node, source_node['id'] in selected)
            path = route_path(source_node['id'], dest_node['id'], source_bus, destination_bus)
            if not path:
                raise EngineeringValidationError('Quelle und Empfänger dürfen nach der Zuordnung nicht identisch sein.')
            paths.extend(path)
            for endpoint, node, edge in [(route['source'], source_node, path[0]), (destination, dest_node, path[-1])]:
                side = 'source' if edge['source'] == node['id'] else 'target'
                port = next(p for p in node['ports'] if p['id'] == edge[side + 'Port'])
                endpoint.update(port_id=port['hardwareInterfaceId'], physical_port_ref=port['id'], network_id=port['physicalNetworkId'],
                                network_name=port['physicalNetworkName'], protocol=BUS_PROTOCOLS[port['bus']])
            current = source_node['id']
            branch_hops = [{'node_id': source_node['engineeringId'], 'name': source_node['name']}]
            for index, edge in enumerate(path):
                current = edge['target'] if edge['source'] == current else edge['source']
                node = nodes[current]
                if index < len(path) - 1 and path[index + 1]['physicalNetworkId'] == edge['physicalNetworkId']:
                    continue
                hop = {'node_id': node['engineeringId'], 'name': node['name']}
                branch_hops.append(hop)
                if node['kind'] == 'gateway' and index < len(path) - 1:
                    gateways.append(hop)
                    if path[index + 1]['bus'] != edge['bus']:
                        transformations.append({'type': 'PROTOCOL_TRANSLATION', 'from_protocol': BUS_PROTOCOLS[edge['bus']], 'to_protocol': BUS_PROTOCOLS[path[index + 1]['bus']], 'reason': 'Bestätigte Systemzuordnung'})
            for hop in branch_hops:
                if hop not in hops:
                    hops.append(hop)
        route['route'] = {**route.get('route', {}), 'hops': hops, 'gateways': gateways, 'transformations': transformations}
        for edge in paths:
            edge['routingEntryIds'] = sorted(set(edge.get('routingEntryIds') or []) | {str(route['id'])})
            edge['routingEntryId'] = edge['routingEntryIds'][0]
            edge.setdefault('routingMetadata', {})[str(route['id'])] = {'approvalState': 'PENDING', 'protocol': route['source']['protocol'], 'name': route['name']}
        route_changes.append(route)

    affected_messages = set().union(*(_refs(r, effective['Signal']) for r in route_changes), *(_refs(r, effective['Signal']) for r in routes if str(r['id']) in affected))
    for message_id in affected_messages:
        if message_id not in effective['Message']:
            continue
        consumers, bindings, producers = set(), {}, set()
        for r in active:
            if message_id in _refs(r, effective['Signal']):
                producers.add(str(r['source']['node_id']))
                consumers.update(str(d['node_id']) for d in r['destinations'])
                bindings[str(r['source']['port_id'])] = r['source']['network_id']
        message = effective['Message'][message_id]
        config = deepcopy(message.get('configuration') or {})
        for field in ('communication_contract', 'transport_unit'):
            if field in config:
                config[field].update(consumer_refs=sorted(consumers))
                if len(producers) == 1:
                    config[field]['producer_ref'] = next(iter(producers))
        data = {'configuration': config}
        if bindings:
            primary = message.get('hardware_interface_id')
            data['hardware_interface_id'] = primary if primary in bindings else sorted(bindings)[0]
            config['physical_transmit_bindings'] = [{'hardware_interface_id': h, 'network_id': n, 'source': 'confirmed-network-assignment'} for h, n in sorted(bindings.items())]
        patch('Message', message_id, data)
        for signal in list(effective['Signal'].values()):
            if str(signal.get('message_id')) != message_id:
                continue
            communication = deepcopy(signal.get('communication') or {})
            communication['consumers'] = sorted(consumers)
            if len(producers) == 1:
                communication['producer'] = next(iter(producers))
            config = deepcopy(signal.get('configuration') or {})
            source = by_hw.get(next(iter(producers), ''))
            if not bus_move and source and (source['id'] in selected or message_id.startswith('$assignment-')):
                config['functional_owner'] = target['label'] if kind == 'frame' else source['name']
            bindings = deepcopy(signal.get('protocol_bindings') or [])
            if len(producers) == 1:
                for binding in bindings:
                    binding['source_ref'] = next(iter(producers))
            patch('Signal', str(signal['id']), {'communication': communication, 'configuration': config, 'protocol_bindings': bindings})

    # Messages without a route still belong to their physical transmitter.
    # Preserve their communication contract while moving explicit bus bindings.
    moved_ports = {identifier for (obj_type, identifier), data in changes.items()
                   if obj_type == 'HardwareNetworkInterface' and 'network_ref' in data}
    for message_id, message in list(effective['Message'].items()):
        config = deepcopy(message.get('configuration') or {})
        bindings = config.get('physical_transmit_bindings') or []
        if str(message.get('hardware_interface_id')) not in moved_ports and not any(
                str(b.get('hardware_interface_id')) in moved_ports for b in bindings):
            continue
        affected_messages.add(message_id)
        for binding in bindings:
            hwi = effective['HardwareNetworkInterface'].get(str(binding.get('hardware_interface_id')))
            if hwi and str(hwi['id']) in moved_ports:
                binding['network_id'] = hwi['network_ref']
        if config != message.get('configuration'):
            patch('Message', message_id, {'configuration': config})

    # Keep CAN/LIN identifiers unique when merging physical buses.
    occupied = defaultdict(set)
    messages = effective['Message']
    ordered = sorted(messages, key=lambda m: (m in affected_messages, m))
    for identifier in ordered:
        message = messages[identifier]
        refs = {str(effective['HardwareNetworkInterface'].get(str(message.get('hardware_interface_id')), {}).get('network_ref') or '')}
        refs.update(b.get('network_id') for b in (message.get('configuration') or {}).get('physical_transmit_bindings', []))
        refs.discard('')
        refs.discard(None)
        try:
            value = int(str(message.get('message_id_hex') or ''), 16)
        except ValueError:
            continue
        if identifier in affected_messages and any(value in occupied[r] for r in refs):
            limit = 59 if any(str(declared.get(r, {}).get('technology')).lower() == 'lin' for r in refs) else 0x1fffffff
            value = 0
            while value <= limit and any(value in occupied[r] for r in refs):
                value += 1
            if value > limit:
                raise EngineeringValidationError('Der Zielbus besitzt keine freien Nachrichtenkennungen.')
            patch('Message', identifier, {'message_id_hex': hex(value)})
        for ref in refs:
            occupied[ref].add(value)
    findings = topology_port_findings(topology, list(effective['HardwareNode'].values()), list(effective['HardwareNetworkInterface'].values()))
    if findings:
        raise EngineeringValidationError('; '.join(f['message'] for f in findings[:4]))
    displaced = {n for n in selected} | {n for f in scene.get('frames', []) if f['id'] in selected for n in f['memberIds']}
    manual = {k: v for k, v in scene.get('manualPositions', {}).items() if k not in displaced}
    topology = build_network_scene(topology, prompt, positions=manual)
    for creation in creations:
        creation['data'] = {**creation['data'], **changes.pop((creation['object_type'], creation['local_ref']), {})}
    context = state.get('context') or {}
    fingerprint = hashlib.sha256(json.dumps([state['topology'], state['parameters'],
        {key: context.get(key) for key in ('wizard_request', 'engineering_wizard_settings', 'equipment_assignment_feedback')},
        objects, routes, request], sort_keys=True, default=str).encode()).hexdigest()
    preview = {'token': fingerprint, 'target_name': target['label'], 'members': membership, 'connections': bus_changes,
               'routes': len(route_changes), 'messages': len(affected_messages), 'new_objects': len(creations),
               'new_commands': len(message_map), 'new_routes': sum(bool(r.get('_assignment_new')) for r in route_changes), 'node_ids': sorted(selected)}
    return {'preview': preview, 'topology': topology, 'networks': networks, 'changes': changes, 'creations': creations,
            'routes': route_changes, 'membership': membership}


def load_assignment(state, request):
    from .pagination import all_pages
    from .repository import list_objects
    from .routing.repository import list_routes
    objects = {kind: all_pages(list_objects, kind) for kind in ('HardwareNode', 'HardwareNetworkInterface', 'Interface', 'Message', 'Signal')}
    return plan_assignment(state, objects, all_pages(list_routes), request)


def assignment_request(payload):
    return {key: payload.get(key) for key in ('node_ids', 'target_kind', 'target_id', 'source_network_id') if key in payload}


def confirmed_context(state, topology, plan):
    """Keep the wizard, agent evidence and exported project aligned with the edit."""
    context = deepcopy(state.get('context') or {})
    if not plan['membership']:
        return context
    nodes = {n['id']: n for n in topology['nodes']}
    scene = topology['scene']
    request = context.get('wizard_request') or {}
    prompt = request.get('prompt') or ''
    match = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    original = json.loads(match[1]) if match else []
    existing = {c.get('cluster_id'): c for c in original}
    graph = []
    for cluster in scene['clusters']:
        groups = []
        for frame in scene['frames']:
            if frame['clusterId'] != cluster['id']:
                continue
            groups.append({'ecu': nodes[frame['id']]['name'],
                           'sensors': [nodes[n]['name'] for n in frame['memberIds'] if nodes[n]['kind'] == 'sensor'],
                           'actuators': [nodes[n]['name'] for n in frame['memberIds'] if nodes[n]['kind'] == 'actuator']})
        graph.append({**existing.get(cluster['id'], {}), 'cluster_id': cluster['id'], 'label': cluster['label'], 'controllers': groups})
    line = '- Systemcluster-Graph: ' + json.dumps(graph, ensure_ascii=False)
    prompt = prompt[:match.start()] + line + prompt[match.end():] if match else prompt + '\n' + line
    context['wizard_request'] = {**request, 'prompt': prompt, 'sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'version': int(request.get('version') or 0) + 1}
    from datetime import datetime, timezone
    evidence = [{'source': 'network-editor', 'accepted': True, 'recorded_at': datetime.now(timezone.utc).isoformat(),
                 'endpoint_name': m['name'], 'controller_name': m['to_frame'], 'cluster_id': nodes[m['id']].get('clusterId'),
                 'cluster_name': m['to_cluster']} for m in plan['membership']]
    context['equipment_assignment_feedback'] = [*context.get('equipment_assignment_feedback', []), *evidence]
    return context
