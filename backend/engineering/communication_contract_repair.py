"""Recover absent routes from explicit canonical consumers, never from neighbors."""
from copy import deepcopy
from .communication_intent import FunctionalArchitecture
from .communication_repair import protocol, digest
from .routing.payload_scope import message_scope


def add_contract_options(planner, group):
    if group['routes']:
        return
    architecture = FunctionalArchitecture(planner.objects)
    creations, changes, comparisons, recipients, gaps = [], [], [], [], []
    for reference in group['messages']:
        message = planner.messages[reference['id']]
        scope = message_scope(message)
        if not scope['consumer_refs']:
            gaps.append(f"{message['name']}: keine expliziten Empfänger im Kommunikationsvertrag.")
            continue
        old = planner.resolve(message.get('hardware_interface_id')) or {}
        logical = planner.all_objects.get(str(message.get('interface_id')), {})
        technology = protocol(old.get('technology') or logical.get('interface_type'))
        source, _, source_view = architecture.resolve({'node_id': planner.owner(message),
            'interface_id': message.get('interface_id'), 'protocol': technology}, message_ids=[str(message['id'])])
        if source_view['issue']:
            gaps.append(f"{message['name']}: {source_view['issue']}")
            continue
        targets = []
        for identifier in scope['consumer_refs']:
            item = planner.all_objects.get(identifier, {})
            kind = item.get('object_type')
            endpoint = {'node_id': identifier if kind == 'HardwareNode' else planner.owner(item), 'protocol': technology}
            if kind == 'Function': endpoint['function_id'] = identifier
            if kind == 'Interface': endpoint['interface_id'] = identifier
            if kind not in {'HardwareNode', 'Function', 'Interface'}:
                gaps.append(f"{message['name']}: Empfängerreferenz {identifier} fehlt oder ist kein Kommunikationspartner.")
                continue
            target, _, view = architecture.resolve(endpoint)
            recipients.append({'message': message['name'], 'reference': identifier,
                               'function': view['function'], 'hardware': view['hardware']})
            if view['issue'] or not target.get('interface_id'):
                gaps.append(f"{message['name']} → {view['hardware']}: {view['issue'] or 'Kommunikationsschnittstelle nicht eindeutig.'}")
            else:
                targets.append(target)
        if len(targets) != len(scope['consumer_refs']):
            continue
        sources = sorted((port for port in planner.active.values()
            if str(port['hardware_node_id']) == source['node_id'] and protocol(port['technology']) == technology),
            key=lambda port: (str(port['id']) != str(old.get('id')), str(port['id'])))
        selected = None
        for port in sources:
            paths = []
            for target in targets:
                candidates = [(path, destination) for destination in planner.active.values()
                    if str(destination['hardware_node_id']) == target['node_id'] and protocol(destination['technology']) == technology
                    for path in planner.paths(str(port['id']), str(destination['id']))
                    if all(protocol(planner.active[p]['technology']) == technology for p in path['ports'])]
                if not candidates: break
                paths.append(min(candidates, key=lambda pair: (len(pair[0]['ports']), str(pair[1]['id']), pair[0]['ports'])))
            if len(paths) == len(targets):
                selected = port, paths
                break
        if selected is None:
            gaps.append(f"{message['name']}: Die gespeicherten Empfänger sind bekannt; ein kompatibler Anschlussweg zu allen Empfängern fehlt.")
            continue
        port, paths = selected
        if str(port['id']) != str(message.get('hardware_interface_id')):
            changes.append({'id': str(message['id']), 'expected_version': message['version'],
                            'data': {'hardware_interface_id': str(port['id'])}})
        for target, (path, destination) in zip(targets, paths):
            src = planner.endpoint(source, port)
            dst = planner.endpoint(target, destination)
            gateways = []
            for a, b in zip(path['ports'], path['ports'][1:]):
                left, right = planner.active[a], planner.active[b]
                if left['network_ref'] != right['network_ref']:
                    node = planner.hardware[str(left['hardware_node_id'])]
                    entry = {'node_id': str(node['id']), 'name': node['name']}
                    if entry not in gateways: gateways.append(entry)
            name = f"{planner.hardware[src['node_id']]['name']} → {planner.hardware[dst['node_id']]['name']}"
            transmission = (message.get('configuration') or {}).get('communication_contract', {}).get('transmission', {})
            period = transmission.get('period_ms') or message.get('cycle_ms')
            timing = {'cycle_time_ms': period} if period and transmission.get('mode', 'CYCLIC') == 'CYCLIC' else {}
            route = {'name': name, 'description': 'Empfänger aus dem bestehenden Kommunikationsvertrag wieder verknüpft; Funktionsfristen separat prüfen.',
                'source': src, 'destinations': [dst], 'payload': {'message_ids': [str(message['id'])],
                    'signal_ids': [str(s['id']) for s in planner.signals.values() if str(s.get('message_id')) == str(message['id'])]},
                'route': {'hops': [{'node_id': src['node_id']}, *gateways, {'node_id': dst['node_id']}],
                          'gateways': gateways, 'transformations': [], 'physical_paths': [path]},
                'timing': timing, 'routing_policy': {'routing_type': 'UNICAST'}, 'origin': 'NETWORK_EDITOR'}
            _, intent, flow = architecture.project(route, [str(message['id'])])
            if flow['issues']:
                gaps.extend(flow['issues']); continue
            route['route']['functional_intent'] = intent
            identifier = digest([message['id'], target])[:20]
            creations.append({'data': route, 'edge_ids': path['edges']})
            comparisons.append({'id': identifier, 'code': 'Neue Route', 'name': name,
                'before': 'Empfänger im Kommunikationsvertrag; Routing-Eintrag fehlt',
                'after': ' → '.join([planner.hardware[src['node_id']]['name'], *[g['name'] for g in gateways], planner.hardware[dst['node_id']]['name']]),
                'functions': flow})
    group['declared_recipients'] = recipients
    if gaps:
        group['reason'] = ' '.join(dict.fromkeys(gaps))
        return
    if not creations:
        return
    conflicts = planner.identifier_conflicts(changes)
    if conflicts:
        group['reason'] = ' '.join(conflicts)
        return
    option = {'action': 'adopt', 'label': 'Fehlende Routing-Einträge aus den gespeicherten Empfängern wiederherstellen',
              'questions': ['Die gezeigten Empfänger und Wege aus dem bestehenden Kommunikationsvertrag übernehmen? Funktionsfristen bleiben separat zu prüfen.'],
              'route_changes': [], 'message_changes': changes, 'create_routes': creations, 'comparison': comparisons}
    option['id'] = digest(option)[:20]
    group['options'].append(option)
    group['status'] = 'QUESTION'
    group['reason'] = 'Die Empfänger sind im kanonischen Kommunikationsvertrag gespeichert. Die fehlenden Routing-Einträge können über vorhandene kompatible Anschlüsse wiederhergestellt werden.'
