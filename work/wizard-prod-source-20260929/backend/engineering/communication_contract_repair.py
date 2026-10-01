"""Recover absent routes from explicit canonical consumers, never from neighbors."""
from copy import deepcopy
from .communication_intent import FunctionalArchitecture
from .communication_repair import protocol, digest
from .routing.payload_scope import message_scope, payload_scope_issues


def add_contract_options(planner, group, *, require_unique_path=False):
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
        if require_unique_path:
            # A receiver repair must not silently rebind the transmitter.
            sources = [port for port in sources if str(port['id']) == str(old.get('id'))]
        selected = None
        for port in sources:
            paths = []
            for target in targets:
                candidates = [(path, destination) for destination in planner.active.values()
                    if str(destination['hardware_node_id']) == target['node_id'] and protocol(destination['technology']) == technology
                    for path in planner.paths(str(port['id']), str(destination['id']))
                    if all(protocol(planner.active[p]['technology']) == technology for p in path['ports'])]
                if not candidates: break
                if require_unique_path and (len(candidates) != 1 or
                        not _unique_path(planner, candidates[0][0])):
                    gaps.append(f"{message['name']}: mehrere physische Wege; Führung ausdrücklich auswählen.")
                    break
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
            scope_issues = payload_scope_issues(route, planner.messages, planner.signals,
                {str(item['id']): item for item in planner.objects['Interface']})
            if scope_issues:
                gaps.extend(issue['message'] for issue in scope_issues)
                continue
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


def _unique_path(planner, path):
    """Prove uniqueness, including longer paths and parallel physical wires."""
    ports = path['ports']
    for left, right in zip(ports, ports[1:]):
        arcs = [(node, edge) for node, edge in planner.graph[left] if node == right
                and (edge is None or edge in path['edges'])]
        if len(arcs) != 1:
            return False
        removed = arcs[0]
        pending, seen = [ports[0]], set()
        while pending:
            node = pending.pop()
            if node == ports[-1]:
                return False
            if node in seen:
                continue
            seen.add(node)
            pending.extend(target for target, edge in planner.graph[node]
                if not (node == left and (target, edge) == removed))
    return len(ports) > 1 and planner.path_is_current(path)


def scan_signal_recipients(planner, validate_route):
    """Inspect all signals; only explicit consumers authorize a route candidate.

    Existing routes are inspected, never replaced by this narrow missing-route
    repair. Physical binding repair and direct I/O retain their own workflows.
    """
    from .communication_repair import message_refs
    from .routing.payload_scope import external_routing_enabled
    routes_by_message = {}
    for route in planner.routes:
        for mid in {str(value) for value in message_refs(route, planner.signals)}:
            routes_by_message.setdefault(mid, []).append(route)
    findings, scanned, changes = [], [], []
    message_results = {}
    for sid, signal in sorted(planner.signals.items()):
        mid = str(signal.get('message_id') or '')
        message = planner.messages.get(mid)
        status, reason, route_ids = 'REVIEW_REQUIRED', '', []
        code = 'SIGNAL_RECIPIENT_UNRESOLVED'
        if not message:
            reason = 'Kein kanonischer Nachrichtenvertrag; Empfänger im zugehörigen Signal-/I/O-Vertrag prüfen.'
        elif mid in message_results:
            status, code, reason, route_ids = message_results[mid]
        else:
            existing = routes_by_message.get(mid, [])
            if existing:
                checks = [(route, validate_route(route)) for route in existing]
                route_ids = [str(route['id']) for route, checked in checks
                             if route.get('destinations') and checked.get('valid') is True]
                assigned = set()
                for route, checked in checks:
                    if checked.get('valid') is not True:
                        continue
                    for destination in route.get('destinations') or []:
                        assigned.update(str(destination.get(key) or '') for key in ('node_id', 'interface_id', 'function_id'))
                        interface = planner.all_objects.get(str(destination.get('interface_id')), {})
                        assigned.add(str(interface.get('function_id') or ''))
                # A partial or invalid receiver assignment is a review case.
                status = 'COVERED' if (len(route_ids) == len(existing) and
                    set(message_scope(message)['consumer_refs']) <= assigned) else 'REVIEW_REQUIRED'
                code = 'SIGNAL_RECIPIENT_ROUTE_VALID' if status == 'COVERED' else 'SIGNAL_RECIPIENT_ROUTE_INVALID'
                reason = 'Bestehende Empfängerrouten validiert.' if status == 'COVERED' else 'Bestehende Empfängerrouten sind unvollständig oder ungültig; keine Ersatzroute erfunden.'
            elif not external_routing_enabled(message) or any(
                    not external_routing_enabled(item) for item in planner.signals.values()
                    if str(item.get('message_id')) == mid):
                reason = 'Routing ist ausdrücklich deaktiviert; Empfänger und lokale Verwendung fachlich prüfen.'
                code = 'SIGNAL_RECIPIENT_ROUTING_DISABLED'
            elif not message_scope(message)['consumer_refs']:
                reason = 'Kein ausdrücklich gespeicherter Empfänger; Erreichbarkeit bestimmt keinen Kommunikationsbedarf.'
            else:
                group = {'messages': [{'id': mid}], 'routes': [], 'options': []}
                add_contract_options(planner, group, require_unique_path=True)
                options = group['options']
                option = options[0] if len(options) == 1 else {}
                creations = option.get('create_routes') or []
                validations = [validate_route(item['data']) for item in creations]
                if (creations and not option.get('message_changes') and not option.get('route_changes')
                        and all(item.get('valid') is True for item in validations)):
                    status, code = 'REPAIRABLE', 'SIGNAL_DECLARED_RECIPIENT_UNROUTED'
                    reason = 'Empfänger ist ausdrücklich gespeichert; die eindeutige fehlende Route kann geprüft übernommen werden.'
                    start = len(changes)
                    changes.extend({'object_type': 'RoutingEntry', 'action': 'CREATE',
                                    'local_ref': 'recipient-route-' + str(start + index),
                                    'data': item['data']} for index, item in enumerate(creations))
                else:
                    reason = group.get('reason') or 'Der gespeicherte Empfänger besitzt keinen eindeutig validierten Anschlussweg.'
                    code = 'SIGNAL_RECIPIENT_PATH_UNRESOLVED'
            message_results[mid] = status, code, reason, route_ids
        item = {'signal_id': sid, 'signal_name': signal['name'], 'message_id': mid or None,
                'status': status, 'code': code, 'message': reason, 'route_ids': route_ids}
        scanned.append(item)
        if status != 'COVERED':
            findings.append({**item, 'severity': 'WARNING', 'review_required': status == 'REVIEW_REQUIRED'})
    return {'scanned_signal_ids': [item['signal_id'] for item in scanned], 'signals': scanned,
            'findings': findings, 'changes': changes,
            'review_required_signal_ids': [item['signal_id'] for item in scanned if item['status'] == 'REVIEW_REQUIRED'],
            'repairable_signal_ids': [item['signal_id'] for item in scanned if item['status'] == 'REPAIRABLE']}
