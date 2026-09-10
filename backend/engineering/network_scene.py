"""Deterministic, persisted physical bus drawing shared by wizard and editor.

The scene never invents connectivity: a trunk is keyed by physicalNetworkId and
every branch retains its canonical hardware-interface and route references.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
import re
from .network_crossings import with_wire_crossings

SCENE_VERSION = 4
BUS_LANE_SPACING = 44
BUS_LABEL_OFFSET = 26
LOCAL_BUS_LABEL_OFFSET = 20


def _spread_coordinates(desired, low, high):
    """Keep geometric order while spreading clamped ports within the device edge."""
    if not desired:
        return []
    gap = min(24, (high - low) / max(1, len(desired) - 1))
    values = []
    for target in desired:
        values.append(max(low, min(high, target), values[-1] + gap if values else low))
    if values[-1] > high:
        values[-1] = high
        for index in range(len(values) - 2, -1, -1):
            values[index] = min(values[index], values[index + 1] - gap)
    return [max(low, min(high, value)) for value in values]


def model_signature(topology: dict) -> str:
    nodes = [{k: v for k, v in n.items() if k not in {'x', 'y', 'width', 'height', 'ports'}} | {
        'ports': [{k: v for k, v in p.items() if k not in {'side', 'offset'}} for p in n.get('ports', [])]
    } for n in topology.get('nodes', [])]
    return hashlib.sha256(json.dumps({'nodes': nodes, 'edges': topology.get('edges', [])},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def confirmed_groups(topology: dict, prompt: str) -> tuple[list[dict], dict[str, str]]:
    nodes = topology.get('nodes', [])
    by_name = {n['name'].casefold(): n for n in nodes}
    by_id = {n['id']: n for n in nodes}
    engineering = {n.get('engineeringId'): n['id'] for n in nodes if n.get('engineeringId')}
    match = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    graph = json.loads(match.group(1)) if match else []
    clusters, owners, assigned = [], {}, set()
    for cluster in graph:
        controllers = []
        for group in cluster.get('controllers', []):
            anchor = by_name.get(str(group.get('ecu', '')).casefold())
            if not anchor or anchor['id'] in assigned:
                continue
            controllers.append(anchor['id'])
            assigned.add(anchor['id'])
            for name in [*group.get('sensors', []), *group.get('actuators', [])]:
                node = by_name.get(str(name).casefold())
                if node:
                    owners[node['id']] = anchor['id']
        if controllers:
            clusters.append({'id': str(cluster.get('cluster_id') or cluster.get('bus_name') or len(clusters)),
                             'label': cluster.get('label') or 'Cluster', 'anchors': controllers})
    # Explicit model ownership precedes the questionnaire. No name-based guessing.
    explicitly_owned = set()
    for node in nodes:
        if node.get('kind') == 'gateway':
            continue
        owner = node.get('systemOwnerId')
        owner = owner if owner in by_id else engineering.get(owner)
        if owner and owner != node['id']:
            explicitly_owned.add(node['id'])
            if by_id[owner].get('kind') == 'gateway':
                owners.pop(node['id'], None)
            else:
                owners[node['id']] = owner
        elif node.get('systemOwnerSource') == 'network-editor':
            explicitly_owned.add(node['id'])
            owners.pop(node['id'], None)
    for node in nodes:
        if node.get('kind') not in {'sensor', 'actuator'} or node['id'] in owners or node['id'] in explicitly_owned:
            continue
        neighbors = set()
        for edge in topology.get('edges', []):
            other = edge['target'] if edge['source'] == node['id'] else edge['source'] if edge['target'] == node['id'] else None
            if other in by_id and by_id[other].get('kind') == 'ecu':
                neighbors.add(other)
        if len(neighbors) == 1:
            owners[node['id']] = next(iter(neighbors))
    remaining = [n['id'] for n in nodes if n['id'] not in assigned and n['id'] not in owners and n.get('kind') != 'gateway']
    if remaining:
        clusters.append({'id': 'additional', 'label': 'Weitere Systeme', 'anchors': remaining})
    # Explicit project corrections take precedence over the original wizard text.
    for node_id in owners:
        seen, parent = {node_id}, owners[node_id]
        while parent in owners:
            if parent in seen:
                raise ValueError('Zyklische Systemzuordnung ist nicht zulässig.')
            seen.add(parent)
            parent = owners[parent]
    declared = {c['id']: c for c in clusters}
    previous = {n: c['id'] for c in clusters for n in c['anchors']}
    for c in clusters:
        c['anchors'] = []
    for node in nodes:
        if node['id'] in owners or node.get('kind') == 'gateway':
            continue
        key = node.get('clusterId') or previous.get(node['id']) or 'additional'
        if key not in declared:
            cluster = {'id': key, 'label': node.get('clusterName') or 'Weitere Systeme', 'anchors': []}
            declared[key] = cluster
            clusters.append(cluster)
        declared[key]['anchors'].append(node['id'])
    for c in clusters:
        c['anchors'].sort(key=lambda key: (by_id[key].get('name', '').casefold(), key))
    clusters = [c for c in clusters if c['anchors']]
    return clusters, owners


def short_bus_name(network_id: str, declared: str, technology: str = '') -> str:
    # Keep user names verbatim; shorten only generated identifiers, never identity.
    if declared and declared != network_id:
        return declared
    local = re.match(r'^.+-IO-(.+)-(can-fd|can-xl|can|lin|automotive-ethernet|flexray)-S(\d+)(?:-CAP-S(\d+))?$', network_id, re.I)
    if local:
        owner = local[1].replace('-', ' ')
        bus = (technology or local[2]).replace('_', '-').upper()
        return f"{owner[0].upper()}{owner[1:]} {bus} {local[3]}" + (f'.{local[4]}' if local[4] else '')
    backbone = re.match(r'^(.+?)(?:_\d+)?-S(\d+)(?:-CAP-S(\d+))?$', network_id)
    return f'{backbone[1]}_{backbone[2]}' + (f'.{backbone[3]}' if backbone[3] else '') if backbone else network_id


def _bounds(points: list[dict]) -> dict:
    return {'left': min(p['x'] for p in points), 'top': min(p['y'] for p in points),
            'width': max(p['x'] for p in points) - min(p['x'] for p in points),
            'height': max(p['y'] for p in points) - min(p['y'] for p in points)}


def _path(points: list[dict]) -> str:
    distinct = [p for i, p in enumerate(points) if not i or p != points[i - 1]]
    return ' '.join(f"{'M' if i == 0 else 'L'} {round(p['x'], 2)} {round(p['y'], 2)}" for i, p in enumerate(distinct))


def bus_junctions(branches: list[dict]) -> list[dict]:
    """Dots denote three-way connections, never a straight continuation or elbow."""
    anchors = [b['points'][-1] for b in branches if b['points']]
    if not anchors:
        return []
    trunk = [{'x': anchors[0]['x'], 'y': min(p['y'] for p in anchors)},
             {'x': anchors[0]['x'], 'y': max(p['y'] for p in anchors)}]
    segments = [tuple(trunk), *[(a, b) for branch in branches
                               for a, b in zip(branch['points'], branch['points'][1:])]]
    junctions = []
    for x, y in dict.fromkeys((p['x'], p['y']) for p in anchors):
        directions = set()
        for a, b in segments:
            if a['x'] == b['x'] == x and min(a['y'], b['y']) <= y <= max(a['y'], b['y']):
                if min(a['y'], b['y']) < y:
                    directions.add('north')
                if max(a['y'], b['y']) > y:
                    directions.add('south')
            if a['y'] == b['y'] == y and min(a['x'], b['x']) <= x <= max(a['x'], b['x']):
                if min(a['x'], b['x']) < x:
                    directions.add('west')
                if max(a['x'], b['x']) > x:
                    directions.add('east')
        if len(directions) >= 3:
            junctions.append({'x': x, 'y': y})
    return junctions


def build_network_scene(topology: dict, prompt: str = '', *, positions: dict | None = None, bus_routes: dict | None = None) -> dict:
    """Return topology and complete scene; no IO and no client-size dependency."""
    result = deepcopy(topology)
    previous_scene = result.pop('scene', None) or {}
    if bus_routes is None:
        bus_routes = previous_scene.get('manualBusRoutes', {})
    if not isinstance(bus_routes, dict):
        raise ValueError('Manuelle Linienführungen müssen ein Objekt sein.')
    nodes = result.get('nodes', [])
    if not nodes:
        return result
    by_id = {n['id']: n for n in nodes}
    clusters, owners = confirmed_groups(result, prompt)
    endpoints = defaultdict(list)
    for node_id, owner in owners.items():
        while owner in owners:
            owner = owners[owner]
        if node_id in by_id and owner in by_id:
            endpoints[owner].append(by_id[node_id])
    for values in endpoints.values():
        values.sort(key=lambda n: (n.get('kind') == 'actuator', n.get('name', '').casefold(), n['id']))
    buses = {}
    port_bus = {}
    for edge in result.get('edges', []):
        network = edge.get('physicalNetworkId')
        if not network:
            raise ValueError(f"Verbindung {edge.get('id')} besitzt keine physische Buszuordnung.")
        bus = buses.setdefault(network, {'id': network, 'name': short_bus_name(network, edge.get('physicalNetworkName', ''), edge['bus']),
                                        'nameSource': edge.get('physicalNetworkNameSource'),
                                        'technology': edge['bus'], 'members': {}, 'edgeIds': [], 'routeIds': set()})
        if bus['technology'] != edge['bus']:
            raise ValueError(f'Bus {network} enthält widersprüchliche Technologien.')
        bus['edgeIds'].append(edge['id'])
        bus['routeIds'].update(edge.get('routingEntryIds') or [])
        if edge.get('routingEntryId'):
            bus['routeIds'].add(edge['routingEntryId'])
        for side in ('source', 'target'):
            node = by_id.get(edge.get(side))
            port_id = edge.get(side + 'Port')
            port = next((p for p in (node or {}).get('ports', []) if p['id'] == port_id), None)
            if not node or not port or port.get('bus') != bus['technology'] or port.get('physicalNetworkId') != network:
                raise ValueError(f'Bus {network}: Anschluss und Verbindung stimmen nicht überein.')
            if (node['id'], port_id) in port_bus and port_bus[node['id'], port_id] != network:
                raise ValueError('Ein physischer Anschluss darf nicht mehrere getrennte Busse verbinden.')
            port_bus[node['id'], port_id] = network
            bus['members'][node['id'], port_id] = {'nodeId': node['id'], 'portId': port_id,
                                                'hardwareInterfaceId': port.get('hardwareInterfaceId')}

    local_counts = defaultdict(int)
    for bus in buses.values():
        roots = {owners.get(node_id, node_id) for node_id, _ in bus['members']}
        if len(roots) == 1:
            local_counts[next(iter(roots))] += 1
    # Reserve a real corridor for all local bus lanes, including their labels.
    frame_width = max(600, 400 + 28 * (max(local_counts.values(), default=1) - 1) + 36)
    cluster_width, column_gap = frame_width * 2 + 276, 220
    frames, domains, frame_by_node = [], [], {}
    band_top = 260
    band_height = 0
    for cluster_index, cluster in enumerate(clusters):
        # Separate horizontal corridors prevent overlapping domain backbones.
        cluster_left = 36 + cluster_index * (cluster_width + 120)
        row_top, row_height = band_top + 70, 0
        cluster_members = []
        for index, anchor_id in enumerate(cluster['anchors']):
            if index and index % 2 == 0:
                row_top += row_height + 80
                row_height = 0
            anchor = by_id[anchor_id]
            children = endpoints[anchor_id]
            left = cluster_left + 28 + (index % 2) * (frame_width + column_gap)
            anchor_width = max(196, 28 * (local_counts[anchor_id] - 1) + 36)
            anchor.update(x=left + (frame_width - anchor_width) / 2, y=row_top + 46, width=anchor_width, height=104)
            row = 0
            placed = set()
            for left_zone, right_zone in (('FL', 'FR'), ('RL', 'RR')):
                columns = [[n for n in children if n.get('installationZone') == zone] for zone in (left_zone, right_zone)]
                for column, values in enumerate(columns):
                    for index_in_zone, node in enumerate(values):
                        node.update(x=left + 20 + column * (frame_width - 220), y=row_top + 204 + (row + index_in_zone) * 132, width=180, height=104)
                        placed.add(node['id'])
                row += max(map(len, columns))
            remaining_children = [n for n in children if n['id'] not in placed]
            for child_index, node in enumerate(remaining_children):
                node.update(x=left + 20 + (child_index % 2) * (frame_width - 220),
                            y=row_top + 204 + (row + child_index // 2) * 132, width=180, height=104)
            row += math.ceil(len(remaining_children) / 2)
            height = max(200, 224 + row * 132)
            members = [anchor_id, *[n['id'] for n in children]]
            frame = {'id': anchor_id, 'memberIds': members, 'label': anchor['name'], 'kind': anchor.get('kind', 'ecu'),
                     'count': len(members), 'inputs': sum(n.get('kind') == 'sensor' for n in children),
                     'outputs': sum(n.get('kind') == 'actuator' for n in children), 'processors': int(anchor.get('kind') in {'ecu', 'gateway'}) + sum(n.get('kind') == 'ecu' for n in children),
                     'left': left, 'top': row_top, 'width': frame_width, 'height': height, 'clusterId': cluster['id']}
            frames.append(frame)
            for member in members:
                frame_by_node[member] = frame
            cluster_members.extend(members)
            row_height = max(row_height, height)
        height = row_top + row_height + 30 - band_top
        domains.append({'id': cluster['id'], 'label': cluster['label'], 'memberIds': cluster_members,
                        'left': cluster_left, 'top': band_top, 'width': cluster_width, 'height': height, 'busLabel': ''})
        band_height = max(band_height, height)
    canvas_width = max([1348, *[d['left'] + d['width'] + 36 for d in domains]])
    gateways = sorted((n for n in nodes if n.get('kind') == 'gateway'), key=lambda n: n['name'])
    for index, gateway in enumerate(gateways):
        gateway.update(x=36, y=40 + index * 100, width=canvas_width - 72, height=88)
    # Explicit manual positions survive reopening and subsequent model revisions.
    for node_id, position in (positions or {}).items():
        if node_id not in by_id:
            continue
        if not isinstance(position, dict):
            raise ValueError('Jede Knotenposition muss ein Objekt sein.')
        for key in ('x', 'y', 'width', 'height'):
            value = position.get(key)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or (key in {'width', 'height'} and value < 72):
                    raise ValueError('Layoutkoordinaten müssen endliche, nichtnegative Zahlen sein.')
                by_id[node_id][key] = value
    if positions:
        for frame in frames:
            if not any(node_id in positions for node_id in frame['memberIds']):
                continue
            children = [by_id[key] for key in frame['memberIds']]
            left, top = min(n['x'] for n in children) - 20, min(n['y'] for n in children) - 46
            frame.update(left=left, top=top, width=max(n['x'] + n['width'] for n in children) + 20 - left,
                         height=max(n['y'] + n['height'] for n in children) + 26 - top)
        for domain in domains:
            if not any(node_id in positions for node_id in domain['memberIds']):
                continue
            children = [f for f in frames if f['clusterId'] == domain['id']]
            left, top = min(f['left'] for f in children) - 28, min(f['top'] for f in children) - 70
            domain.update(left=left, top=top, width=max(f['left'] + f['width'] for f in children) + 28 - left,
                          height=max(f['top'] + f['height'] for f in children) + 30 - top)

    domain_by_node = {node_id: d for d in domains for node_id in d['memberIds']}
    local_indices, backbone_indices = defaultdict(int), defaultdict(int)
    scene_buses = []
    ports = {(n['id'], p['id']): p for n in nodes for p in n.get('ports', [])}
    local_flags = {}
    for network, bus in buses.items():
        ids = {key[0] for key in bus['members']}
        local_flags[network] = all(key in frame_by_node for key in ids) and len({frame_by_node[key]['id'] for key in ids if key in frame_by_node}) == 1
    local_lanes = {}
    routing_warnings = []
    for frame in frames:
        networks = [key for key in buses if local_flags[key] and any(node_id == frame['id'] for node_id, _ in buses[key]['members'])]
        center = frame['left'] + frame['width'] / 2
        children = [by_id[key] for key in frame['memberIds'] if key != frame['id']]
        left = max([frame['left'] + 18, *[n['x'] + n['width'] + 12 for n in children if n['x'] + n['width'] / 2 < center]])
        right = min([frame['left'] + frame['width'] - 18, *[n['x'] - 12 for n in children if n['x'] + n['width'] / 2 >= center]])
        def lane_order(network):
            participants = [by_id[key] for key, _ in buses[network]['members'] if key != frame['id']]
            xs = [n['x'] + n['width'] / 2 for n in participants]
            # Shallow left branches outside; deep branches inside. Mirror on right.
            side = -1 if xs and max(xs) < center else 1 if xs and min(xs) >= center else 0
            return side, side * -min((n['y'] for n in participants), default=0), network
        networks.sort(key=lane_order)
        gaps = max(0, len(networks) - 1)
        spacing = max(24, min(28, (right - left) / gaps)) if gaps else 28
        span = gaps * spacing
        lane_center = (left + right) / 2
        if networks and right - left < span:
            routing_warnings.append(f"{frame['label']}: Der Platz zwischen den Geräten reicht für {len(networks)} getrennte Buslinien nicht aus. Geräte auseinanderziehen oder Leitungen manuell führen.")
        for index, network in enumerate(networks):
            local_lanes[network] = (lane_center - span / 2 + index * spacing, index, len(networks))
    routing_targets = {}
    for network, bus in sorted(buses.items()):
        member_ids = {key[0] for key in bus['members']}
        common_frames = {frame_by_node[key]['id'] for key in member_ids if key in frame_by_node}
        local = len(common_frames) == 1 and all(key in frame_by_node for key in member_ids)
        if local:
            frame = frame_by_node[next(iter(member_ids))]
            lane = local_indices[frame['id']]
            local_indices[frame['id']] += 1
            trunk_x = local_lanes.get(network, (frame['left'] + frame['width'] / 2, lane, 1))[0]
            owner_id = frame['id']
        else:
            domain = next((domain_by_node[key] for key in sorted(member_ids) if key in domain_by_node), None)
            domain_id = domain['id'] if domain else 'gateway'
            lane = backbone_indices[domain_id]
            backbone_indices[domain_id] += 1
            trunk_x = (domain['left'] + 28 + frame_width + 50 if domain else 200) + lane * BUS_LANE_SPACING
            owner_id = None
        routing_targets[network] = (trunk_x, owner_id, local)
    bottom_groups = defaultdict(list)
    for network, bus in buses.items():
        trunk_x, owner_id, _ = routing_targets[network]
        for node_id, port_id in bus['members']:
            if node_id == owner_id or by_id[node_id].get('kind') == 'gateway':
                bottom_groups[node_id].append((trunk_x, port_id))
    bottom_positions = {}
    for node_id, group in bottom_groups.items():
        group.sort()
        node = by_id[node_id]
        xs = _spread_coordinates([x for x, _ in group], node['x'] + 18, node['x'] + node['width'] - 18)
        for index, ((target, port_id), px) in enumerate(zip(group, xs)):
            # Nested fan-outs get distinct bend heights, respecting left/right order.
            level = index if target < px - .001 else len(group) - 1 - index if target > px + .001 else 0
            bottom_positions[node_id, port_id] = px, node['y'] + node['height'] + 28 + 12 * level
    manual_routes = {}
    for network, bus in sorted(buses.items()):
        trunk_x, owner_id, local = routing_targets[network]
        member_ids = {key[0] for key in bus['members']}
        override = bus_routes.get(network, {})
        if not isinstance(override, dict) or set(override) - {'trunkX', 'branchY'}:
            raise ValueError('Ungültige manuelle Buslinienführung.')
        branch_y = override.get('branchY', {})
        if not isinstance(branch_y, dict):
            raise ValueError('Manuelle Abzweige müssen ein Objekt sein.')
        values = [*branch_y.values(), *([override['trunkX']] if 'trunkX' in override else [])]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1000000 for value in values):
            raise ValueError('Linienkoordinaten müssen endliche Zahlen zwischen 0 und 1000000 sein.')
        branch_y = {port_id: value for port_id, value in branch_y.items() if any(key[1] == port_id for key in bus['members'])}
        if override:
            manual_routes[network] = {**({'trunkX': override['trunkX']} if 'trunkX' in override else {}), **({'branchY': branch_y} if branch_y else {})}
        automatic_trunk_x = trunk_x
        trunk_x = override.get('trunkX', trunk_x)
        branches, anchors = [], []
        for (node_id, port_id), member in sorted(bus['members'].items()):
            node, port = by_id[node_id], ports[node_id, port_id]
            if (node_id, port_id) in bottom_positions:
                side, py = 'bottom', node['y'] + node['height']
                px, joint_y = bottom_positions[node_id, port_id]
            else:
                side = 'right' if node['x'] + node['width'] / 2 < automatic_trunk_x else 'left'
                px = node['x'] + node['width'] if side == 'right' else node['x']
                def target_order(port_id):
                    peer_bus = buses[port_bus[node_id, port_id]]
                    ys = [by_id[peer]['y'] + by_id[peer]['height'] / 2 for peer, _ in peer_bus['members'] if peer != node_id and by_id[peer].get('kind') != 'gateway']
                    return sum(ys) / len(ys) if ys else node['y'], port_id
                siblings = sorted((p['id'] for p in node.get('ports', [])
                                  if (node_id, p['id']) in port_bus
                                  and routing_targets[port_bus[node_id, p['id']]][1] != node_id
                                  and ('right' if node['x'] + node['width'] / 2 < routing_targets[port_bus[node_id, p['id']]][0] else 'left') == side), key=target_order)
                offset = (siblings.index(port_id) + 1) / (len(siblings) + 1) if port_id in siblings else .5
                py = node['y'] + 18 + (node['height'] - 36) * offset
                joint_y = py
            offset = (px - node['x'] - 18) / (node['width'] - 36) if side == 'bottom' else (py - node['y'] - 18) / (node['height'] - 36)
            manual_ports = (positions or {}).get(node_id, {}).get('ports') or {}
            if not isinstance(manual_ports, dict):
                raise ValueError('Manuelle Anschlüsse müssen ein Objekt sein.')
            manual_port = manual_ports.get(port_id)
            if manual_port is not None and not isinstance(manual_port, dict):
                raise ValueError('Jede Anschlussposition muss ein Objekt sein.')
            if manual_port:
                side = manual_port.get('side')
                offset = manual_port.get('offset')
                if side not in {'left', 'right', 'top', 'bottom'} or not isinstance(offset, (int, float)) or not math.isfinite(offset) or not 0 <= offset <= 1:
                    raise ValueError('Ungültige manuelle Anschlussposition.')
                px = node['x'] + (0 if side == 'left' else node['width'] if side == 'right' else 18 + (node['width'] - 36) * offset)
                py = node['y'] + (0 if side == 'top' else node['height'] if side == 'bottom' else 18 + (node['height'] - 36) * offset)
                joint_y = py + (28 if side == 'bottom' else -28 if side == 'top' else 0)
            port.update(side=side, offset=offset)
            joint_y = branch_y.get(port_id, joint_y)
            if side == 'bottom':
                joint_y = max(py + 18, joint_y)
            elif side == 'top':
                joint_y = max(0, min(py - 18, joint_y))
            if port_id in branch_y:
                manual_routes[network]['branchY'][port_id] = joint_y
            points = [{'x': px, 'y': py}]
            if side in {'bottom', 'top'}:
                points.append({'x': px, 'y': joint_y})
            elif abs(joint_y - py) > .001:
                escape_x = px + (24 if side == 'right' else -24)
                points.extend([{'x': escape_x, 'y': py}, {'x': escape_x, 'y': joint_y}])
            points.append({'x': trunk_x, 'y': joint_y})
            branches.append({**member, 'path': _path(points), 'bounds': _bounds(points), 'points': points})
            anchors.append({'x': trunk_x, 'y': joint_y})
        trunk = [{'x': trunk_x, 'y': min(p['y'] for p in anchors)}, {'x': trunk_x, 'y': max(p['y'] for p in anchors)}]
        scene_buses.append({**{k: v for k, v in bus.items() if k not in {'members', 'routeIds'}},
                            'labelText': bus['name'][len(by_id[owner_id]['name']):].strip()
                                if bus.get('nameSource') != 'user' and owner_id and bus['name'].startswith(by_id[owner_id]['name'] + ' ') else bus['name'],
                            'routeIds': sorted(bus['routeIds']), 'participantCount': len(member_ids),
                            'local': local, 'frameId': owner_id, 'path': _path(trunk), 'bounds': _bounds([*trunk, *[p for b in branches for p in b['points']]]),
                            'label': {'x': trunk_x + (LOCAL_BUS_LABEL_OFFSET if local else BUS_LABEL_OFFSET), 'y': trunk[0]['y'] + 16},
                            'branches': branches, 'junctions': bus_junctions(branches)})
    scene = {'version': SCENE_VERSION, 'modelSignature': model_signature(result), 'frames': frames, 'clusters': domains,
             'buses': scene_buses, 'manualPositions': positions or {}, 'manualBusRoutes': manual_routes, 'routingVersion': 3, 'routingWarnings': routing_warnings,
             'width': max(canvas_width, max(n['x'] + n['width'] for n in nodes) + 36, max((b['bounds']['left'] + b['bounds']['width'] + 60 for b in scene_buses), default=0)),
             'height': max([300, *[d['top'] + d['height'] + 60 for d in domains], *[n['y'] + n['height'] + 60 for n in nodes], *[b['bounds']['top'] + b['bounds']['height'] + 60 for b in scene_buses]])}
    scene = with_wire_crossings(scene)
    scene['revision'] = hashlib.sha256(json.dumps(scene, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result['scene'] = scene
    return result
