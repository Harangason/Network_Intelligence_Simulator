"""Canonical physical channels for topology proposals and persisted-model checks."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

from ..communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from .models import INTERFACE_TYPES
from .physical_segments import physical_port_networks
from .routing.validation import PROTOCOL_CAPACITY
from .naming import new_bus_name, ethernet_context, is_ethernet


def technology_id(value):
    normalized = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(str(value or ''))
    return 'ethernet' if normalized == 'automotive_ethernet' else normalized


def _interface_technology(bus):
    normalized = technology_id(bus)
    for candidate in INTERFACE_TYPES:
        if technology_id(candidate) == normalized:
            return candidate
    raise ValueError(f'Für {bus} ist kein kanonischer Hardwarekanal definiert.')


def _new_channel_name(preferred, hardware_id, technology, channel_index, canonical):
    """A split connector is a new object, not a second copy of its old name."""
    used = {str(row.get('name') or '').strip().casefold() for row in canonical.values()
            if str(row.get('hardware_node_id')) == hardware_id}
    name = str(preferred).strip()
    if name.casefold() not in used:
        return name
    base = f'{name} · {technology} Kanal {channel_index}'
    name, suffix = base, 2
    while name.casefold() in used:
        name = f'{base} ({suffix})'
        suffix += 1
    return name


def topology_port_findings(topology, hardware, interfaces):
    """Validate persisted IDs or the effective proposal graph with $local_refs."""
    hw = {str(row['id']): row for row in hardware}
    physical = {str(row['id']): row for row in interfaces}
    findings, ports, networks_by_interface, channels, connectors = [], {}, {}, {}, {}

    def error(code, text, **refs):
        findings.append({'severity': 'ERROR', 'code': code, 'message': text, **refs})

    for node in topology.get('nodes') or []:
        if not isinstance(node, dict):
            error('INVALID_TOPOLOGY_NODE', 'Topologieknoten muss ein Objekt sein.')
            continue
        node_id, hardware_id = str(node.get('id') or ''), str(node.get('engineeringId') or '')
        if hardware_id not in hw:
            error('UNKNOWN_TOPOLOGY_HARDWARE', 'Topologieknoten besitzt keine gültige Hardware-Referenz.', node_id=node_id)
        for port in node.get('ports') or []:
            if not isinstance(port, dict):
                error('INVALID_TOPOLOGY_PORT', 'Topologie-Port muss ein Objekt sein.', node_id=node_id)
                continue
            port_id = str(port.get('id') or '')
            if port_id in ports:
                error('DUPLICATE_TOPOLOGY_PORT', 'Topologie-Port-ID ist mehrfach vergeben.', port_id=port_id)
            ports[port_id] = (node_id, port)
            interface_id = str(port.get('hardwareInterfaceId') or '')
            interface = physical.get(interface_id)
            if interface is None:
                error('UNKNOWN_PHYSICAL_CHANNEL', 'Topologie-Port benötigt einen vorhandenen Hardwarekanal.', port_id=port_id)
                continue
            if str(interface.get('hardware_node_id')) != hardware_id:
                error('PHYSICAL_CHANNEL_OWNER', 'Hardwarekanal gehört zu einem anderen Gerät.', port_id=port_id)
            if technology_id(interface.get('technology')) != technology_id(port.get('bus')):
                error('PHYSICAL_CHANNEL_TECHNOLOGY', 'Port-Bus und Hardwarekanal verwenden unterschiedliche Technologien.', port_id=port_id)
            network = str(port.get('physicalNetworkId') or '')
            if not network or str(interface.get('network_ref') or '') != network:
                error('PHYSICAL_CHANNEL_NETWORK', 'Physisches Netz und Netzwerkbindung des Hardwarekanals stimmen nicht überein.', port_id=port_id)
            networks_by_interface.setdefault(interface_id, set()).add(network)
            if len(networks_by_interface[interface_id]) > 1:
                error('PHYSICAL_CHANNEL_SHARED_NETWORKS', 'Unabhängige Netze benötigen getrennte Hardwarekanäle.', hardware_interface_id=interface_id)
            channel = interface.get('channel_index')
            if not isinstance(channel, int) or isinstance(channel, bool) or channel < 1:
                error('PHYSICAL_CHANNEL_INDEX', 'Physischer Hardwarekanal benötigt eine positive Kanalnummer.', hardware_interface_id=interface_id)
            else:
                key = (hardware_id, technology_id(interface.get('technology')), str(interface.get('controller_ref') or ''), channel)
                if key in channels and channels[key] != interface_id:
                    error('DUPLICATE_PHYSICAL_CHANNEL', 'Mehrere Hardware-Interfaces belegen denselben Controllerkanal.', hardware_interface_id=interface_id)
                channels[key] = interface_id
            connector = str(interface.get('physical_port_ref') or '')
            if connector:
                key = (hardware_id, connector)
                if key in connectors and connectors[key] != interface_id:
                    error('DUPLICATE_PHYSICAL_CONNECTOR', 'Mehrere Hardware-Interfaces belegen denselben physischen Anschluss.', hardware_interface_id=interface_id)
                connectors[key] = interface_id
    for edge in topology.get('edges') or []:
        if not isinstance(edge, dict):
            error('INVALID_TOPOLOGY_EDGE', 'Physische Kante muss ein Objekt sein.')
            continue
        endpoints = [ports.get(str(edge.get(side + 'Port') or '')) for side in ('source', 'target')]
        if not all(endpoints):
            error('UNKNOWN_EDGE_PORT', 'Physische Kante verweist auf einen fehlenden Port.', edge_id=edge.get('id'))
            continue
        for side, endpoint in zip(('source', 'target'), endpoints):
            node_id, port = endpoint
            if node_id != str(edge.get(side) or ''):
                error('EDGE_PORT_OWNER', 'Kantenendpunkt und Portgerät stimmen nicht überein.', edge_id=edge.get('id'))
            if technology_id(port.get('bus')) != technology_id(edge.get('bus')):
                error('EDGE_PORT_TECHNOLOGY', 'Kante und Endpunkt verwenden unterschiedliche Technologien.', edge_id=edge.get('id'))
            if str(port.get('physicalNetworkId') or '') != str(edge.get('physicalNetworkId') or ''):
                error('EDGE_PORT_NETWORK', 'Eine physische Kante muss innerhalb eines gemeinsamen Netzes liegen.', edge_id=edge.get('id'))
    return findings


def _free_port_rebindings(previous, current):
    """Retain channel identity on explicit attachment or disconnection of a connector."""
    old = {str(p['id']): (str(n.get('engineeringId') or ''), p)
           for n in (previous or {}).get('nodes') or [] for p in n.get('ports') or []}
    connected = {str(e.get(side + 'Port') or '') for e in (previous or {}).get('edges') or [] for side in ('source', 'target')}
    now_connected = {str(e.get(side + 'Port') or '') for e in current.get('edges') or [] for side in ('source', 'target')}
    allowed = set()
    for node in current.get('nodes') or []:
        for port in node.get('ports') or []:
            identifier = str(port['id'])
            owner, before = old.get(identifier, ('', {}))
            interface = str(before.get('hardwareInterfaceId') or '')
            if not interface:
                continue
            if owner != str(node.get('engineeringId') or '') or interface != port.get('hardwareInterfaceId') or technology_id(before.get('bus')) != technology_id(port.get('bus')):
                continue
            if identifier in connected and identifier not in now_connected:
                if not any(p.get('hardwareInterfaceId') == interface and p['id'] in now_connected
                           for n in current.get('nodes') or [] for p in n.get('ports') or []):
                    allowed.add((identifier, interface))
                continue
            if identifier in connected or identifier not in now_connected:
                continue
            # Another alias or participant means this is an existing network, not a spare connector.
            if any(key != identifier and (other.get('hardwareInterfaceId') == interface or
                   (before.get('physicalNetworkId') and other.get('physicalNetworkId') == before['physicalNetworkId']))
                   for key, (_, other) in old.items()):
                continue
            allowed.add((identifier, interface))
    return allowed


def materialize_physical_ports(topology, hardware, interfaces, networks, *, routes=(), messages=(), prune_unconnected=True, previous_topology=None):
    """Return a topology and explicit ordered changes; never mutate canonical state.

    Each (device, technology, physical network) gets one actual channel. Existing
    compatible bindings are reused, unbound channels can be assigned, and added
    hardware resources remain visible in the same proposal as the topology.
    """
    updated = deepcopy(topology)
    rebindings = _free_port_rebindings(previous_topology, topology)
    hw = {str(row['id']): row for row in hardware}
    canonical = {str(row['id']): deepcopy(row) for row in interfaces}
    declared = {str(row['id']): {**row, 'name': row.get('name') or str(row['id'])} for row in networks}
    network_changes, channel_changes, assignments, used_channels, used_connectors = [], [], {}, set(), set()
    # Capacity splitting keeps obsolete canvas ports. They are no longer physical
    # participants and must not reserve phantom channels after the split.
    connected = {str(edge.get(side + 'Port') or '') for edge in updated.get('edges') or [] for side in ('source', 'target')}
    if prune_unconnected:
        for node in updated.get('nodes') or []:
            node['ports'] = [port for port in node.get('ports') or [] if str(port.get('id') or '') in connected]
    inferred = physical_port_networks(updated)
    for node in updated.get('nodes') or []:
        hardware_id = str(node.get('engineeringId') or '')
        if hardware_id not in hw:
            raise ValueError(f'Topologieknoten {node.get("name")} besitzt keine gültige Hardware-Referenz.')
        owner = (hw[hardware_id].get('identity') or {}).get('system_owner_id')
        if owner:
            node['systemOwnerId'] = str(owner)
        identity = hw[hardware_id].get('identity') or {}
        if identity.get('installation_zone'):
            node['installationZone'] = identity['installation_zone']
        if identity.get('cluster_id'):
            node.update(clusterId=identity['cluster_id'], clusterName=identity.get('cluster_name'))
        if identity.get('system_owner_source') == 'network-editor':
            node.update(systemOwnerId=identity.get('system_owner_id'), systemOwnerSource='network-editor')
        for port in node.get('ports') or []:
            port_id, bus = str(port['id']), str(port.get('bus') or '')
            technology = _interface_technology(bus)
            network_id = str(port.get('physicalNetworkId') or inferred.get(port_id) or '')
            if not network_id:
                raise ValueError(f'Port {port_id} besitzt kein bestimmbares physisches Netz.')
            port['physicalNetworkId'] = network_id
            if network_id in declared and technology_id(declared[network_id].get('technology')) != technology_id(technology):
                raise ValueError(f'Physisches Netz {network_id} besitzt widersprüchliche Technologien.')
            if network_id not in declared:
                protocol = next((value for value in PROTOCOL_CAPACITY if technology_id(value) == technology_id(technology)), None)
                if protocol is None:
                    raise ValueError(f'Netzprotokoll für {technology} ist nicht verfügbar.')
                context = ethernet_context({'id': network_id}, updated, hardware)
                # Generated Ethernet channels inherit the canonical network
                # name. Reserve existing connector labels as well so this
                # inheritance cannot introduce a duplicate child object.
                name_reservations = [*declared.values(), *canonical.values()] if is_ethernet(protocol) else declared.values()
                data = {'id': network_id, 'name': new_bus_name(network_id, name_reservations, technology=protocol, context=context), 'technology': protocol}
                if is_ethernet(protocol):
                    data.update(name_source='generated', name_context=context)
                declared[network_id] = data
                network_changes.append({'object_type': 'Network', 'local_ref': 'physical-network-' + sha256(network_id.encode()).hexdigest()[:16], 'data': data})
            key = (hardware_id, technology_id(technology), network_id)
            if key not in assignments:
                candidates = sorted((row for row in canonical.values() if str(row.get('hardware_node_id')) == hardware_id
                    and technology_id(row.get('technology')) == key[1]
                    and str(row['id']) not in assignments.values()
                    and (not row.get('network_ref') or str(row['network_ref']) == network_id
                         or (port_id, str(row['id'])) in rebindings)), key=lambda row: (
                        (port_id, str(row['id'])) not in rebindings,
                        str(row.get('network_ref') or '') != network_id,
                        str(row['id']) != str(port.get('hardwareInterfaceId') or ''),
                        bool(row.get('network_ref')), str(row['id'])))
                existing = candidates[0] if candidates else None
                digest = sha256('\n'.join(key).encode()).hexdigest()[:16]
                controller = str((existing or {}).get('controller_ref') or '')
                channel_scope = (hardware_id, key[1], controller)
                current_index = (existing or {}).get('channel_index')
                occupied = [int(row.get('channel_index') or 0) for row in canonical.values() if (
                    str(row.get('hardware_node_id')), technology_id(row.get('technology')), str(row.get('controller_ref') or '')) == channel_scope]
                index = current_index if isinstance(current_index, int) and current_index > 0 and (*channel_scope, current_index) not in used_channels else max(occupied or [0]) + 1
                connector = str((existing or {}).get('physical_port_ref') or f'physical-port-{digest}')
                if (hardware_id, connector) in used_connectors:
                    connector = f'physical-port-{digest}'
                data = {'network_ref': network_id, 'channel_index': index, 'physical_port_ref': connector}
                if existing and is_ethernet(technology) and port.get('nameSource') != 'user' and (existing.get('capabilities') or {}).get('name_source') != 'user' and existing.get('name') in (network_id, f'{bus}-Port'):
                    data.update(name=declared[network_id]['name'], capabilities={**(existing.get('capabilities') or {}),
                        'name_source': 'network', 'name_network_id': network_id})
                if existing:
                    identifier = str(existing['id'])
                    delta = {name: value for name, value in data.items() if existing.get(name) != value}
                    if delta:
                        channel_changes.append({'action': 'UPDATE', 'object_type': 'HardwareNetworkInterface', 'object_id': identifier,
                            'local_ref': 'physical-channel-' + digest, 'data': delta})
                    canonical[identifier].update(data)
                else:
                    identifier = '$physical-channel-' + digest
                    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(key[1])
                    original = canonical.get(str(port.get('hardwareInterfaceId') or ''))
                    if (original and str(original.get('hardware_node_id')) == hardware_id
                            and technology_id(original.get('technology')) == key[1]):
                        data.update({field: original[field] for field in ('target_load_limit', 'warning_load_limit', 'hard_load_limit')
                                     if original.get(field) is not None})
                    inherited_name = is_ethernet(technology) and port.get('nameSource') != 'user' and port.get('name') in (None, '', network_id, declared[network_id]['name'], f'{bus}-Port')
                    preferred_name = declared[network_id]['name'] if inherited_name else port.get('name') or declared[network_id]['name']
                    name = _new_channel_name(preferred_name, hardware_id, technology, index, canonical)
                    if inherited_name and name != preferred_name:
                        raise ValueError(f'Netzname {preferred_name} kollidiert mit einem vorhandenen Anschluss von {hw[hardware_id].get("name", hardware_id)}. Bitte den bestehenden Anschluss eindeutig benennen.')
                    data.update({'name': name, 'hardware_node_id': hardware_id,
                        'technology': technology, 'capabilities': {**(profile.get('capabilities') or {}), 'source': 'reviewed-physical-topology',
                            **({'name_source': 'network', 'name_network_id': network_id} if inherited_name else {})}})
                    channel_changes.append({'object_type': 'HardwareNetworkInterface', 'local_ref': identifier[1:], 'data': data})
                    canonical[identifier] = {**data, 'id': identifier}
                used_channels.add((*channel_scope, index))
                used_connectors.add((hardware_id, connector))
                assignments[key] = identifier
            port.update({'hardwareInterfaceId': assignments[key], 'engineeringId': assignments[key],
                         'physicalNetworkName': declared[network_id]['name'], 'name': canonical[assignments[key]].get('name') or port.get('name') or declared[network_id]['name']})
            name_source = (canonical[assignments[key]].get('capabilities') or {}).get('name_source')
            if name_source in ('network', 'user'):
                port['nameSource'] = name_source
            if declared[network_id].get('name_source') in ('user', 'generated'):
                port['physicalNetworkNameSource'] = declared[network_id]['name_source']
            port.pop('requestedTechnology', None)
    port_map = {str(port['id']): port for node in updated.get('nodes') or [] for port in node.get('ports') or []}
    for edge in updated.get('edges') or []:
        left, right = (port_map.get(str(edge.get(side + 'Port') or ''), {}) for side in ('source', 'target'))
        if not left or not right or left['physicalNetworkId'] != right['physicalNetworkId']:
            raise ValueError(f'Kante {edge.get("id")} verbindet widersprüchliche physische Netze.')
        for side, endpoint in (('source', left), ('target', right)):
            if endpoint.get('nameSource') == 'network':
                edge[side + 'InterfaceName'] = endpoint['name']
        edge['physicalNetworkId'] = left['physicalNetworkId']
        edge['physicalNetworkName'] = declared[left['physicalNetworkId']]['name']
        if declared[left['physicalNetworkId']].get('name_source') in ('user', 'generated'):
            edge['physicalNetworkNameSource'] = declared[left['physicalNetworkId']]['name_source']
    findings = topology_port_findings(updated, hardware, list(canonical.values()))
    if findings:
        raise ValueError('; '.join(item['message'] for item in findings[:5]))
    return updated, network_changes + channel_changes + physical_transmit_changes(updated, routes, messages)


def physical_transmit_changes(topology, routes, messages):
    """Declare every reviewed source channel when a message spans several buses."""
    nodes = {str(node['id']): node for node in topology.get('nodes') or []}
    ports = {str(port['id']): port for node in nodes.values() for port in node.get('ports') or []}
    by_message = {}
    for route in routes:
        if str(route.get('approval_state') or '').upper() != 'APPROVED':
            continue
        source_id = str((route.get('source') or {}).get('node_id') or '')
        payload = route.get('payload') or {}
        message_ids = {str(identifier) for identifier in [payload.get('message_id'), *(payload.get('message_ids') or [])] if identifier}
        for edge in topology.get('edges') or []:
            linked = {str(identifier) for identifier in [edge.get('routingEntryId'), *(edge.get('routingEntryIds') or [])] if identifier}
            if str(route['id']) not in linked:
                continue
            for side in ('source', 'target'):
                if str((nodes.get(str(edge.get(side))) or {}).get('engineeringId') or '') != source_id:
                    continue
                port = ports.get(str(edge.get(side + 'Port') or '')) or {}
                identifier, network = str(port.get('hardwareInterfaceId') or ''), str(port.get('physicalNetworkId') or '')
                if identifier and network:
                    for message_id in message_ids:
                        by_message.setdefault(message_id, set()).add((identifier, network))
    changes = []
    for message in messages:
        bindings = by_message.get(str(message['id']))
        if not bindings:
            continue
        configuration = deepcopy(message.get('configuration') or {})
        primary = str(message.get('hardware_interface_id') or '')
        if all(identifier == primary for identifier, _ in bindings) and not configuration.get('physical_transmit_bindings'):
            continue
        expected = [{'hardware_interface_id': identifier, 'network_id': network, 'source': 'approved-topology'} for identifier, network in sorted(bindings)]
        if configuration.get('physical_transmit_bindings') == expected:
            continue
        configuration['physical_transmit_bindings'] = expected
        changes.append({'action': 'UPDATE', 'object_type': 'Message', 'object_id': str(message['id']),
            'local_ref': 'physical-message-' + str(message['id']), 'data': {'configuration': configuration}})
    return changes


def create_physical_port_repair_proposal():
    """Create a reviewable migration in the caller's project RequestUnit."""
    from .agent_tools import model, proposal_service
    snapshot = model.model()
    topology, changes = materialize_physical_ports(snapshot['topology'], snapshot['hardware'],
        snapshot['hardware-interfaces'], model.networks(), routes=snapshot['routing'], messages=snapshot['messages'])
    if not changes and topology == snapshot['topology']:
        return {'status': 'UNCHANGED', 'changes': []}
    proposal = proposal_service.create('PHYSICAL_CHANNEL_REPAIR', [*changes, {'object_type': 'NetworkTopology', 'data': {
        'name': 'Physische Hardwarekanäle zuordnen', 'topology': topology}}],
        'Jedes unabhängige physische Netz erhält einen eigenen Hardwarekanal mit passender Technologie. '
        'Die aufgeführten Kanalergänzungen und Netzwerkbindungen benötigen gemeinsame Freigabe.',
        assumptions=['Zusätzliche Kanäle sind geplante Hardware-Ressourcen; ihre Bereitstellung ist Teil der Freigabe.'])
    return proposal_service.validate(proposal['proposal_id'])
