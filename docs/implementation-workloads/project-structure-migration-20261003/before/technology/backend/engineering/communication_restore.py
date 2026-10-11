"""Restore proven previous bus memberships without replacing the whole project."""
from copy import deepcopy
from uuid import uuid5, NAMESPACE_URL
from .communication_repair import RepairPlanner, digest, protocol, INACTIVE


def restoration_option(planner, group):
    affected = {r['id'] for r in group['routes']}
    originals = [r for r in planner.routes if str(r['id']) in affected]
    networks = {e.get('network_id') for r in originals for e in [r['source'], *r['destinations']]
        if e.get('network_id') and (planner.resolve(e.get('port_id')) or {}).get('network_ref') != e.get('network_id')}
    if not networks:
        return None, 'Kein abweichender früherer Bus mit belegten Anschlüssen vorhanden.'
    if len(networks) != 1:
        return None, 'Mehrere frühere Busse betroffen. Die frühere Verkabelung muss zunächst im Netzwerkeditor präzisiert werden.'
    network = next(iter(networks))
    if network not in planner.networks:
        return None, 'Die technische Definition des früheren Busses fehlt.'
    # Previous endpoint records plus audited membership identify exact channels.
    refs = {str(e.get('port_id')) for r in planner.routes for e in [r['source'], *r['destinations']] if e.get('network_id') == network}
    refs = {str(p['id']) for ref in refs if (p := planner.resolve(ref))}
    anchors = {str(h['port_id']) for h in planner.history if h['network_id'] == network
        and planner.hardware.get(str(h['node_id']), {}).get('device_type') == 'Gateway' and str(h['port_id']) in planner.ports}
    creates = []
    if not anchors:
        gateways = {str(g.get('node_id') if isinstance(g, dict) else g) for r in originals for g in r['route'].get('gateways', [])
            if planner.hardware.get(str(g.get('node_id') if isinstance(g, dict) else g), {}).get('device_type') == 'Gateway'}
        if len(gateways) == 1 and refs:
            gateway = next(iter(gateways)); technology = planner.ports[next(iter(refs))]['technology']
            identifier = str(uuid5(NAMESPACE_URL, gateway + ':' + network + ':restore-channel'))
            if identifier in planner.ports: return None, 'Die geplante Anschlusskennung ist bereits vergeben.'
            creates.append({'id': identifier, 'data': {'hardware_node_id': gateway, 'technology': technology,
                'name': planner.networks[network].get('name', network), 'network_ref': network,
                'capabilities': {'restoration': {'source': 'communication-repair-choice', 'hardware_resource_status': 'PLANNING_REQUIRED', 'previous_network_id': network}},
                'channel_index': 1 + max([0, *[p.get('channel_index') or 0 for p in planner.ports.values() if str(p['hardware_node_id']) == gateway and p['technology'] == technology]])}})
            anchors.add(identifier)
    if len(anchors) != 1:
        return None, 'Die frühere System-/Gateway-Anbindung ist nicht eindeutig in der Anschlusshistorie belegt.'
    refs.update(anchors)
    if any(not any(str(h['port_id']) == ref and h['network_id'] == network for h in planner.history) for ref in refs - {c['id'] for c in creates}):
        return None, 'Für mindestens einen früheren Anschluss fehlt die bestätigte Bushistorie.'
    state, objects = deepcopy(planner.state), deepcopy(planner.objects)
    objects['HardwareNetworkInterface'].extend({'id': c['id'], 'version': 1, 'object_type': 'HardwareNetworkInterface', **c['data']} for c in creates)
    nodes = {str(n.get('engineeringId')): n for n in state['topology']['nodes']}
    ports = {str(p['id']): p for p in objects['HardwareNetworkInterface']}
    if any(str(ports[r]['hardware_node_id']) not in nodes for r in refs):
        return None, 'Ein früheres Gerät fehlt im aktuellen Netzwerkeditor.'
    if len({protocol(ports[r]['technology']) for r in refs}) != 1:
        return None, 'Die früheren Anschlüsse haben inzwischen unterschiedliche Technologien.'
    bus = {'ETHERNET': 'automotive_ethernet', 'CAN': 'can', 'CAN_FD': 'can_fd', 'CAN_XL': 'can_xl', 'LIN': 'lin', 'FLEXRAY': 'flexray'}.get(protocol(ports[next(iter(refs))]['technology']))
    if not bus: return None, 'Diese Technologie benötigt eine manuelle Wiederherstellung.'
    name = planner.networks[network].get('name', network)
    drawings, changes = {}, []
    for ref in sorted(refs):
        port = ports[ref]; node = nodes[str(port['hardware_node_id'])]
        drawing = next((p for p in node['ports'] if str(p.get('hardwareInterfaceId')) == ref), None)
        if drawing is None:
            drawing = {'id': 'restore-port-' + ref, 'hardwareInterfaceId': ref, 'engineeringId': ref, 'side': 'bottom', 'offset': .5}
            node['ports'].append(drawing)
        drawing.update(bus=bus, physicalNetworkId=network, physicalNetworkName=name)
        drawing.setdefault('name', port['name'])
        drawings[ref] = (node, drawing)
        data = {'network_ref': network, 'capabilities': {**(port.get('capabilities') or {}), 'network_id': network}}
        port.update(data)
        if ref not in {c['id'] for c in creates}: changes.append({'id': ref, 'expected_version': port['version'], 'data': data})
    drawn = {p['id'] for _, p in drawings.values()}
    state['topology']['edges'] = [e for e in state['topology']['edges'] if not drawn.intersection([e.get('sourcePort'), e.get('targetPort')])]
    hub, hub_port = drawings[next(iter(anchors))]
    for ref, (node, port) in drawings.items():
        if node['id'] == hub['id']: continue
        state['topology']['edges'].append({'id': 'restore-edge-' + digest([network, hub_port['id'], port['id']])[:20],
            'source': hub['id'], 'sourcePort': hub_port['id'], 'target': node['id'], 'targetPort': port['id'], 'bus': bus,
            'physicalNetworkId': network, 'physicalNetworkName': name, 'sourceInterfaceName': hub_port['name'], 'targetInterfaceName': port['name']})
    routes = deepcopy(planner.routes)
    impacted = set()
    for r in routes:
        if any(str((planner.resolve(e.get('port_id')) or {}).get('id')) in refs for e in [r['source'], *r['destinations']]):
            impacted.add(str(r['id']))
            r['validation'] = {'warnings': [{'code': 'PHYSICAL_PATH_REMOVED'}]}
    preferred = {}
    for ref in refs: preferred.setdefault(str(ports[ref]['hardware_node_id']), []).append(ref)
    restored = RepairPlanner(state, objects, routes, planner.history, preferred_ports=preferred)
    replanned = restored.build()
    options = []
    for part in replanned['groups']:
        if not impacted.intersection(r['id'] for r in part['routes']): continue
        if len(part['options']) != 1:
            return None, 'Die frühere Anbindung kann nicht für alle betroffenen Nachrichten eindeutig wiederhergestellt werden. ' + part['reason']
        options.append(part['options'][0])
    if not options: return None, 'Kein vollständig überprüfbarer früherer Signalweg vorhanden.'
    route_changes = list({c['id']: c for o in options for c in o['route_changes']}.values())
    messages = list({c['id']: c for o in options for c in o['message_changes']}.values())
    conflicts = planner.identifier_conflicts(messages, changes)
    if conflicts:
        return None, ' '.join(conflicts) + ' Bestehende Nachrichten-IDs bleiben unverändert.'
    option = {'action': 'restore', 'label': 'Frühere Systemanbindung über ' + name,
        'questions': ['Die früheren Systemanschlüsse werden aus der belegten Historie wieder verbunden. Alle unten aufgeführten Routen erhalten diese Führung; ihre Funktionen und Empfänger bleiben erhalten.'],
        'topology': state['topology'], 'create_ports': creates, 'port_changes': changes, 'hardware_changes': [], 'message_changes': messages, 'route_changes': route_changes,
        'interface_changes': list({c['id']: c for o in options for c in o.get('interface_changes', [])}.values()),
        'comparison': planner.comparison(route_changes)}
    if creates:
        option['questions'].append('Der frühere Gateway-Kanal ist nicht erhalten. Am weiterhin in den alten Routen belegten Gateway wird dafür ein zusätzlicher physischer Anschluss angelegt; dessen Hardware-Ressource ist ein neuer Planungsbedarf.')
    option['id'] = digest(option)[:20]
    return option, ''
