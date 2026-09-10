"""Preview and apply a physical bus technology change without replacing model IDs.

A transport unit and its logical interface have one technology. Their physical
transmit bindings therefore form an atomic group, even across multiple buses.
The API executes this plan inside the project's RequestUnit transaction.
"""
from copy import deepcopy
import hashlib
import json
import re

from .models import EngineeringValidationError
from .network_scene import short_bus_name
from .topology_sync import BUS_TO_INTERFACE_TYPE
from .routing.network_sync import BUS_PROTOCOLS
from .routing.validation import PROTOCOL_CAPACITY
from .message_packing import CAN_FD_PAYLOAD_CLASSES


def plan_bus_change(state, objects, routes, network_id, bus):
    if bus not in BUS_TO_INTERFACE_TYPE:
        raise EngineeringValidationError('Unbekannter Bustyp.')
    topology = deepcopy(state['topology'])
    networks = deepcopy(state['parameters'].get('networks') or [])
    declared = {str(n['id']): n for n in networks}
    if network_id not in declared:
        raise EngineeringValidationError('Der physische Bus ist noch nicht gespeichert. Bitte zuerst die Verbindung speichern.')
    hwis = {str(n['id']): n for n in objects['HardwareNetworkInterface']}
    interfaces = {str(n['id']): n for n in objects['Interface']}
    messages = {str(n['id']): n for n in objects['Message']}
    logical_networks = {}
    for message in messages.values():
        bindings = [message.get('hardware_interface_id'), *[b.get('hardware_interface_id') for b in
                    (message.get('configuration') or {}).get('physical_transmit_bindings', [])]]
        refs = {str(hwis.get(str(binding), {}).get('network_ref') or '') for binding in bindings}
        logical_networks.setdefault(str(message['interface_id']), set()).update(refs - {''})
    for node in topology.get('nodes', []):
        for port in node.get('ports', []):
            if str(port.get('engineeringId')) in interfaces:
                logical_networks.setdefault(str(port['engineeringId']), set()).add(str(port.get('physicalNetworkId') or ''))
    affected = {network_id}
    while True:
        expanded = affected | set().union(*(refs for refs in logical_networks.values() if refs & affected))
        expanded.discard('')
        if expanded == affected:
            break
        affected = expanded
    if affected - declared.keys():
        raise EngineeringValidationError('Eine gekoppelte Nachricht verweist auf einen nicht definierten Bus.')
    selected_interfaces = {key for key, refs in logical_networks.items() if refs & affected}
    selected_messages = {key for key, m in messages.items() if str(m['interface_id']) in selected_interfaces}
    selected_hwis = {key for key, h in hwis.items() if str(h.get('network_ref')) in affected}
    protocol = BUS_PROTOCOLS[bus]
    interface_type = BUS_TO_INTERFACE_TYPE[bus]
    from .agent_tools.wizard_generation import _technology_contract
    contract = _technology_contract(interface_type)
    rate, max_payload = PROTOCOL_CAPACITY[protocol]
    names = {}
    old_names = {}
    generated_names = set()
    reserved_names = {short_bus_name(key, item.get('name', ''), item.get('technology', '')).casefold()
                      for key, item in declared.items() if key not in affected}
    for key in sorted(affected):
        old_name = declared[key].get('name', '')
        old_default = short_bus_name(key, '', declared[key].get('technology', ''))
        old_names[key] = old_name or old_default
        generated = declared[key].get('name_source') == 'generated' or not old_name or old_name in {key, old_default}
        candidate = short_bus_name(key, '' if generated else old_name, bus)
        if generated:
            generated_names.add(key)
            match = re.match(r'^(.*?)[ _](\d+)$', candidate)
            ordinal = int(match[2]) if match else 1
            base = match[1] if match else candidate
            while candidate.casefold() in reserved_names:
                ordinal += 1
                candidate = f'{base} {ordinal:02}'
        names[key] = candidate
        reserved_names.add(candidate.casefold())
    changes = []
    occupied = {}
    for key, hwi in hwis.items():
        if key not in selected_hwis:
            slot = (str(hwi['hardware_node_id']), hwi['technology'], hwi.get('controller_ref'))
            occupied.setdefault(slot, set()).add(hwi.get('channel_index'))
    for key in sorted(selected_hwis):
        hwi = hwis[key]
        slot = (str(hwi['hardware_node_id']), interface_type, hwi.get('controller_ref'))
        used = occupied.setdefault(slot, set())
        channel = hwi.get('channel_index') or 1
        while channel in used:
            channel += 1
        used.add(channel)
        ref = str(hwi['network_ref'])
        old_default = short_bus_name(ref, '', declared[ref].get('technology', ''))
        name = names[ref] if hwi.get('name') in {ref, old_default, declared[ref].get('name')} else hwi['name']
        changes.append(('HardwareNetworkInterface', key, {'technology': interface_type, 'channel_index': channel,
            'name': name, 'bitrate': rate, 'data_bitrate': 2_000_000 if bus == 'can_fd' else None,
            'capabilities': {**(hwi.get('capabilities') or {}), 'hardware_interface': contract['hardware_interface'],
                             'technology_stack': contract['stack'], **contract['capabilities']},
            'static_load': None, 'runtime_load': None}))
    for key in sorted(selected_interfaces):
        changes.append(('Interface', key, {'interface_type': interface_type}))
    identifiers = {}
    for key in sorted(selected_messages):
        message = messages[key]
        size = int(message.get('dlc') or 0)
        if size > max_payload:
            raise EngineeringValidationError(f"{message['name']}: {size} Byte passen nicht auf {protocol} (maximal {max_payload}). Der Buswechsel wurde nicht ausgeführt.")
        size = next(n for n in CAN_FD_PAYLOAD_CLASSES if n >= size) if bus == 'can_fd' else max(1, size)
        config = deepcopy(message.get('configuration') or {})
        config['technology_binding'] = contract
        config['transport_unit'] = {**config.get('transport_unit', {}), 'transport_unit_type': contract['transport_unit_type'], 'payload_size': size}
        patch = {'dlc': size, 'configuration': config}
        # Keep valid identifiers; allocate deterministically when changing address spaces.
        limit = 59 if bus == 'lin' else 0x1fffffff if bus in {'can', 'can_fd'} else None
        if limit is not None:
            refs = logical_networks[str(message['interface_id'])]
            used = set().union(*(identifiers.get(ref, set()) for ref in refs))
            try:
                identifier = int(str(message.get('message_id_hex') or ''), 16)
            except ValueError:
                identifier = -1
            if not 0 <= identifier <= limit or identifier in used:
                identifier = next((n for n in range(limit + 1) if n not in used), None)
            if identifier is None:
                raise EngineeringValidationError(f'{protocol}: Kein freier Nachrichten-Identifier auf dem gekoppelten Bus verfügbar.')
            patch['message_id_hex'] = hex(identifier)
            for ref in refs:
                identifiers.setdefault(ref, set()).add(identifier)
        changes.append(('Message', key, patch))
    for signal in objects['Signal']:
        if str(signal['message_id']) in selected_messages:
            bindings = [{**binding, 'technology_binding_ref': contract['technology_id']} for binding in signal.get('protocol_bindings') or []]
            changes.append(('Signal', str(signal['id']), {'protocol_bindings': bindings}))
    for network in networks:
        if str(network['id']) in affected:
            if str(network['id']) in generated_names:
                network['name_source'] = 'generated'
            network.update(technology=bus, protocol=protocol, name=names[str(network['id'])], bitrate=rate)
            network.pop('arbitration_bitrate', None)
            network.pop('data_bitrate', None)
            if bus == 'can_fd':
                network['data_bitrate'] = 2_000_000
    for node in topology.get('nodes', []):
        for port in node.get('ports', []):
            ref = str(port.get('physicalNetworkId'))
            if ref in affected:
                if port.get('name') in {ref, old_names[ref]}:
                    port['name'] = names[ref]
                port.update(bus=bus, physicalNetworkName=names[ref])
    route_ids = set()
    for edge in topology.get('edges', []):
        ref = str(edge.get('physicalNetworkId'))
        if ref in affected:
            edge.update(bus=bus, physicalNetworkName=names[ref])
            for field in ('sourceInterfaceName', 'targetInterfaceName'):
                if edge.get(field) in {ref, old_names[ref]}:
                    edge[field] = names[ref]
            route_ids.update(str(r) for r in [edge.get('routingEntryId'), *(edge.get('routingEntryIds') or [])] if r)
    for route in routes:
        payload = route.get('payload') or {}
        refs = {str(r) for r in [payload.get('message_id'), *(payload.get('message_ids') or [])] if r}
        if refs & selected_messages or any(str(e.get('network_id')) in affected for e in [route.get('source') or {}, *route.get('destinations', [])]):
            route_ids.add(str(route['id']))
    active_routes = [r for r in routes if str(r['id']) in route_ids and r.get('status') not in {'REJECTED', 'SUPERSEDED', 'DEPRECATED', 'OUTDATED'}]
    from .routing.endpoint_consistency import align_receive_interfaces
    effective_interfaces = deepcopy(interfaces)
    effective_ports = deepcopy(hwis)
    for kind, key, change in changes:
        if kind == 'Interface':
            effective_interfaces[key].update(change)
        elif kind == 'HardwareNetworkInterface':
            effective_ports[key].update(change)
    repaired_routes = []
    for route in active_routes:
        candidate = deepcopy(route)
        for endpoint in [candidate.get('source') or {}, *candidate.get('destinations', [])]:
            if str(endpoint.get('network_id')) in affected:
                endpoint['protocol'] = protocol
        repaired_routes.append(align_receive_interfaces(candidate, list(effective_interfaces.values()), list(effective_ports.values())))
    # Full input fingerprint makes the preview invalid if any canonical binding changes.
    fingerprint = json.dumps([state['topology'], state['parameters'], objects, routes, network_id, bus], sort_keys=True, default=str)
    preview = {'token': hashlib.sha256(fingerprint.encode()).hexdigest(), 'network_id': network_id, 'bus': bus,
        'networks': [{'id': key, 'name': names[key], 'previous_name': next(n for n in state['parameters']['networks'] if str(n['id']) == key).get('name', key)} for key in sorted(affected)],
        'devices': len({str(hwis[key]['hardware_node_id']) for key in selected_hwis}),
        'messages': len(selected_messages), 'routes': len(active_routes)}
    return {'preview': preview, 'changes': changes, 'topology': topology, 'networks': networks, 'routes': repaired_routes}


def load_bus_change(state, network_id, bus):
    from .pagination import all_pages
    from .repository import list_objects
    from .routing.repository import list_routes
    objects = {kind: all_pages(list_objects, kind) for kind in ('HardwareNetworkInterface', 'Interface', 'Message', 'Signal')}
    return plan_bus_change(state, objects, all_pages(list_routes), network_id, bus)
