"""Repair physical transport references while preserving authored communication intent."""
from collections import defaultdict, deque
from copy import deepcopy
from itertools import islice, product
import hashlib
import json

from .models import EngineeringValidationError
from .db import ConcurrentUpdateError
from .routing.network_sync import BUS_PROTOCOLS
from .routing.forwarding import forwarding_permitted, forwarding_rule
from .communication_intent import FunctionalArchitecture

INACTIVE = {'REJECTED', 'SUPERSEDED', 'DEPRECATED'}
KINDS = ('HardwareNode', 'HardwareNetworkInterface', 'Function', 'Interface', 'Message', 'Signal')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def protocol(value):
    value = str(value or '').lower().replace(' ', '_').replace('-', '_')
    return BUS_PROTOCOLS.get(value, {'ethernet': 'ETHERNET'}.get(value, value.upper()))


def message_refs(route, signals):
    payload = route.get('payload') or {}
    return set(filter(None, [payload.get('message_id'), *payload.get('message_ids', []),
        *(signals.get(str(s), {}).get('message_id') for s in payload.get('signal_ids', []))]))


def extra_bindings(message):
    values = (message.get('configuration') or {}).get('physical_transmit_bindings') or []
    return values if isinstance(values, list) and all(isinstance(v, dict) for v in values) else []


class RepairPlanner:
    def __init__(self, state, objects, routes, history=(), *, propose_forwarding=False, detection_graph=None, preferred_ports=None):
        self.state, self.objects = state, objects
        latest = {}
        for route in routes:
            key = route.get('route_code') or str(route['id'])
            if key not in latest or route.get('revision', 0) > latest[key].get('revision', 0): latest[key] = route
        self.routes = [r for r in latest.values() if r.get('status') not in INACTIVE]
        self.propose_forwarding = propose_forwarding
        self.preferred_ports = preferred_ports or {}
        self.hardware = {str(o['id']): o for o in objects['HardwareNode']}
        self.ports = {str(o['id']): o for o in objects['HardwareNetworkInterface']}
        self.messages = {str(o['id']): o for o in objects['Message']}
        self.signals = {str(o['id']): o for o in objects['Signal']}
        self.all_objects = {str(o['id']): o for rows in objects.values() for o in rows}
        self.networks = {n['id']: n for n in state['parameters'].get('networks', [])}
        self.history = history
        self.aliases = {key: p for p in self.ports.values() for key in (str(p['id']), p.get('physical_port_ref')) if key}
        self.drawings, self.active, self.graph = {}, {}, defaultdict(list)
        self.members, self.old_members = defaultdict(set), defaultdict(set)
        for item in history:
            if item.get('network_id') and item.get('node_id'):
                self.old_members[item['network_id']].add(item['node_id'])
        for node in state['topology'].get('nodes', []):
            for drawing in node.get('ports', []):
                port = self.ports.get(str(drawing.get('hardwareInterfaceId')))
                if port and str(port['hardware_node_id']) == str(node.get('engineeringId')):
                    self.aliases[drawing['id']] = port
                    if port.get('network_ref') in self.networks and port['network_ref'] == drawing.get('physicalNetworkId'):
                        self.drawings[drawing['id']] = (port, drawing)
        for edge in state['topology'].get('edges', []):
            left, right = self.drawings.get(edge.get('sourcePort')), self.drawings.get(edge.get('targetPort'))
            if not left or not right:
                continue
            a, b = left[0], right[0]
            if a['network_ref'] != b['network_ref'] or protocol(a['technology']) != protocol(b['technology']):
                continue
            if edge.get('physicalNetworkId') and edge['physicalNetworkId'] != a['network_ref']:
                continue
            for port, drawing in (left, right):
                identifier = str(port['id'])
                self.active.setdefault(identifier, {**port, 'drawing_id': drawing['id']})
                self.members[port['network_ref']].add(str(port['hardware_node_id']))
            self.graph[str(a['id'])].append((str(b['id']), edge['id']))
            self.graph[str(b['id'])].append((str(a['id']), edge['id']))
        # Proposals may ask for a specific Ethernet forwarding task on an ECU.
        # It becomes usable only after the user selects that proposal.
        for hw in self.hardware.values():
            ports = [p for p in self.active.values() if str(p['hardware_node_id']) == str(hw['id'])]
            for a in ports:
                for b in ports:
                    permitted = forwarding_permitted(hw, a, b)
                    proposed = propose_forwarding and hw.get('device_type') == 'ECU' and protocol(a['technology']) == protocol(b['technology']) == 'ETHERNET'
                    if a['network_ref'] != b['network_ref'] and (permitted or proposed):
                        self.graph[str(a['id'])].append((str(b['id']), None))
        self.bindings, self.endpoint_keys, self.message_keys = {}, {}, {}
        self.detection_graph = detection_graph
        architecture = FunctionalArchitecture(objects)
        self.functional_routes = {str(r['id']): architecture.project(r, message_refs(r, self.signals)) for r in self.routes}

    def owner(self, item):
        seen = set()
        while item and str(item['id']) not in seen:
            seen.add(str(item['id']))
            if item.get('object_type') == 'HardwareNode':
                return str(item['id'])
            key = next((item.get(k) for k in ('interface_id', 'function_id', 'hardware_node_id', 'message_id') if item.get(k)), None)
            item = self.all_objects.get(str(key))
        return None

    def resolve(self, value):
        return self.aliases.get(str(value or ''))

    def scope(self, net, *, old=False):
        members = self.old_members.get(net, set()) if old else self.members.get(net, set())
        if not members:
            members = {str(p['hardware_node_id']) for p in self.ports.values() if p.get('network_ref') == net}
        gateways = [self.hardware[m] for m in members if self.hardware.get(m, {}).get('device_type') == 'Gateway']
        if gateways or self.networks.get(net, {}).get('network_role') == 'backbone':
            return ('system', tuple(sorted(str(g['id']) for g in gateways)))
        owners = {str((self.hardware.get(m, {}).get('identity') or {}).get('system_owner_id') or m) for m in members}
        return ('cluster', tuple(sorted(owners))) if owners else ('unknown', ())

    def binding(self, raw_id, node_id, tech, network, context):
        port = self.resolve(raw_id)
        identifier = str(port['id']) if port else f'missing:{context}'
        if port and str(port['hardware_node_id']) != node_id:
            identifier += '@' + str(node_id)
        candidates = [p for p in self.active.values()
            if str(p['hardware_node_id']) == node_id and protocol(p['technology']) == protocol(tech)]
        if identifier in self.active and self.active[identifier]['network_ref'] == network and candidates:
            candidates = [self.active[identifier]]
        if node_id in self.preferred_ports:
            candidates = [self.active[k] for k in self.preferred_ports[node_id] if k in self.active and protocol(self.active[k]['technology']) == protocol(tech)]
        candidates.sort(key=lambda p: (str(p['id']) != identifier, str(p['id'])))
        candidates = [p for p in candidates if str(p['hardware_node_id']) == node_id and protocol(p['technology']) == protocol(tech)]
        entry = self.bindings.setdefault(identifier, {'id': identifier, 'port': port, 'node_id': node_id,
            'networks': set(), 'candidates': candidates})
        entry['candidates'] = [p for p in entry['candidates'] if any(str(p['id']) == str(c['id']) for c in candidates)]
        if network:
            entry['networks'].add(network)
        elif port:
            # History is evidence for the old membership, never a guessed reconnection.
            entry['networks'].update(h['network_id'] for h in self.history if h.get('port_id') == str(port['id']))
        return identifier

    def collect(self):
        for route in self.routes:
            projected, _, communication = self.functional_routes[str(route['id'])]
            removed_path = any(issue.get('code') == 'PHYSICAL_PATH_REMOVED' for issue in
                [*(route.get('validation') or {}).get('errors', []), *(route.get('validation') or {}).get('warnings', [])])
            resolved = [self.resolve(e.get('port_id') or e.get('physical_port_ref')) for e in [route['source'], *route['destinations']]]
            stored_paths = (route.get('route') or {}).get('physical_paths') or []
            if stored_paths:
                removed_path = removed_path or any(not self.path_is_current(p, graph=self.detection_graph) for p in stored_paths)
                removed_path = removed_path or any((p.get('ports') or [None])[0] != str((resolved[0] or {}).get('id')) for p in stored_paths)
                removed_path = removed_path or {str((p or {}).get('id')) for p in resolved[1:]} != {(p.get('ports') or [None])[-1] for p in stored_paths}
            if all(resolved) and not removed_path:
                removed_path = any(not self.paths(str(resolved[0]['id']), str(p['id']), graph=self.detection_graph) for p in resolved[1:])
            primary_mismatch = any(str((resolved[0] or {}).get('id')) not in
                {str(self.messages.get(str(mid), {}).get('hardware_interface_id')), *(str(b.get('hardware_interface_id')) for b in extra_bindings(self.messages.get(str(mid), {})))}
                for mid in message_refs(route, self.signals))
            for index, endpoint in enumerate([projected['source'], *projected['destinations']]):
                port = self.resolve(endpoint.get('port_id') or endpoint.get('physical_port_ref'))
                if (not port or str(port['id']) not in self.active or str(port['hardware_node_id']) != str(endpoint['node_id'])
                        or port.get('network_ref') != endpoint.get('network_id') or removed_path or communication['changed'] or index == 0 and primary_mismatch):
                    key = self.binding(endpoint.get('port_id') or endpoint.get('physical_port_ref'), str(endpoint['node_id']),
                        endpoint.get('protocol') or (port or {}).get('technology'), endpoint.get('network_id'), f'{route["id"]}:{index}')
                    self.endpoint_keys[(str(route['id']), index)] = key
        source_keys = {(str((self.resolve(r['source'].get('port_id') or r['source'].get('physical_port_ref')) or {}).get('id')), self.functional_routes[str(r['id'])][0]['source']['node_id']): self.endpoint_keys[(str(r['id']), 0)]
            for r in self.routes if (str(r['id']), 0) in self.endpoint_keys}
        for message in self.messages.values():
            values = [{'hardware_interface_id': message.get('hardware_interface_id')},
                      *extra_bindings(message)]
            for index, value in enumerate(values):
                port = self.resolve(value.get('hardware_interface_id'))
                owner = self.owner(message)
                if port and (str(port['id']), owner) in source_keys:
                    self.message_keys[(str(message['id']), index)] = source_keys[(str(port['id']), owner)]
                    continue
                if port and str(port['id']) in self.active and str(port['hardware_node_id']) == owner and (not value.get('network_id') or port.get('network_ref') == value['network_id']):
                    continue
                interface = self.all_objects.get(str(message.get('interface_id')), {})
                key = self.binding(value.get('hardware_interface_id'), self.owner(message),
                    (port or {}).get('technology') or interface.get('interface_type'), value.get('network_id'), f'{message["id"]}:{index}')
                self.message_keys[(str(message['id']), index)] = key

    def identifier_conflicts(self, changes, port_changes=()):
        """Never silently move an explicit frame ID onto an occupied CAN/LIN bus."""
        patches = {c['id']: c['data'] for c in changes}
        port_patches = {c['id']: c['data'] for c in port_changes}
        before, after = defaultdict(set), defaultdict(set)
        for message in self.messages.values():
            for buckets, row in ((before, message), (after, {**message, **patches.get(str(message['id']), {})})):
                try:
                    frame_id = int(str(row.get('message_id_hex') or ''), 16)
                except ValueError:
                    continue
                for ref in [row.get('hardware_interface_id'), *(b.get('hardware_interface_id') for b in extra_bindings(row))]:
                    port = self.resolve(ref)
                    if port and buckets is after: port = {**port, **port_patches.get(str(port['id']), {})}
                    if port and port.get('network_ref') and protocol(port.get('technology')) in {'CAN', 'CAN_FD', 'CAN_XL', 'LIN'}:
                        buckets[(port['network_ref'], frame_id)].add(str(row['id']))
        return [f"{self.networks.get(net, {}).get('name', net)}: Nachrichten-ID {hex(identifier)} ist bereits belegt."
            for (net, identifier), ids in after.items() if len(ids) > 1 and ids != before[(net, identifier)]]

    def path_is_current(self, path, *, graph=None):
        """Check the exact saved wires, including parallel wires and directed forwarding."""
        ports, claimed = path.get('ports') or [], set(path.get('edges') or [])
        graph = self.graph if graph is None else graph
        if not ports or len(ports) != len(set(ports)) or any(p not in self.active for p in ports):
            return False
        used = set()
        for a, b in zip(ports, ports[1:]):
            edges = [e for n, e in graph.get(a, []) if n == b]
            selected = claimed.intersection(e for e in edges if e)
            if not edges or (None not in edges and len(selected) != 1):
                return False
            used.update(selected)
        return used == claimed

    def paths(self, source, target, *, graph=None):
        """Bounded shortest physical paths; no fallback through unconnected devices."""
        queue, visits, found, distance = deque([(source, [source], [])]), defaultdict(int), [], None
        visits[source] = 1
        while queue and len(found) < 2:
            current, ports, edges = queue.popleft()
            if distance is not None and len(ports) > distance:
                break
            if current == target:
                found.append({'ports': ports, 'edges': [e for e in edges if e]})
                distance = len(ports)
                continue
            if len(ports) >= 24:
                continue
            for neighbor, edge in sorted((graph if graph is not None else self.graph).get(current, []), key=lambda pair: (pair[0], pair[1] or '')):
                if neighbor not in ports and visits[neighbor] < 2:
                    visits[neighbor] += 1
                    queue.append((neighbor, [*ports, neighbor], [*edges, edge]))
        return found

    def endpoint(self, endpoint, replacement):
        port = replacement or self.active.get(str((self.resolve(endpoint.get('port_id') or endpoint.get('physical_port_ref')) or {}).get('id')))
        if not port:
            return None
        return {**endpoint, 'port_id': str(port['id']), 'physical_port_ref': port['drawing_id'],
                'network_id': port['network_ref'], 'network_name': self.networks[port['network_ref']].get('name'),
                'protocol': protocol(port['technology'])}

    def comparison(self, changes):
        def label(endpoint):
            return f"{self.hardware.get(str(endpoint['node_id']), {}).get('name', 'Gerät')} [{self.networks.get(endpoint.get('network_id'), {}).get('name', endpoint.get('network_id') or 'Bus fehlt')}]"
        originals = {str(r['id']): r for r in self.routes}
        return [{'id': c['id'], 'code': originals[c['id']]['route_code'], 'name': originals[c['id']]['name'],
            'before': ' → '.join([label(originals[c['id']]['source']), *[g.get('name', str(g.get('node_id'))) if isinstance(g, dict) else str(g) for g in originals[c['id']]['route'].get('gateways', [])], *[label(e) for e in originals[c['id']]['destinations']]]),
            'after': ' → '.join([label(c['source']), *[g['name'] for g in c['route']['gateways'] if g['node_id'] != c['source']['node_id']], *[label(e) for e in c['destinations']]]),
            'functions': self.functional_routes[c['id']][2]}
            for c in changes]

    def build(self):
        self.collect()
        parent = {k: k for k in self.bindings}
        def root(k):
            while parent[k] != k:
                k = parent[k]
            return k
        route_keys, message_keys = {}, {}
        for message in self.messages:
            message_keys[message] = {k for (mid, _), k in self.message_keys.items() if mid == message}
        for route in self.routes:
            rid = str(route['id'])
            keys = {k for (r, _), k in self.endpoint_keys.items() if r == rid}
            for mid in message_refs(route, self.signals):
                keys.update(message_keys.get(str(mid), set()))
            route_keys[rid] = keys
        for keys in [*route_keys.values(), *message_keys.values()]:
            for key in keys:
                parent[root(key)] = root(sorted(keys)[0])
        components = defaultdict(set)
        for key in parent:
            components[root(key)].add(key)
        groups = []
        for keys in components.values():
            ordered = sorted(keys)
            affected_routes = [r for r in self.routes if route_keys[str(r['id'])] & keys]
            affected_messages = [m for m in self.messages.values() if message_keys[str(m['id'])] & keys]
            group = {'id': digest(ordered)[:20], 'status': 'BLOCKED', 'options': [],
                'routes': [{'id': str(r['id']), 'name': r['name'], 'code': r['route_code']} for r in affected_routes],
                'messages': [{'id': str(m['id']), 'name': m['name']} for m in affected_messages],
                'connections': [{'device': self.hardware.get(self.bindings[k]['node_id'], {}).get('name', 'Gerät fehlt'),
                    'old_port': (self.bindings[k]['port'] or {}).get('name', 'Anschluss fehlt')} for k in ordered]}
            functional_issues = sorted({issue for r in affected_routes for issue in self.functional_routes[str(r['id'])][2]['issues']})
            if functional_issues:
                group['reason'] = ' '.join(functional_issues) + ' Bitte die Funktionszuordnung klären; ein erreichbares Nachbargerät ersetzt keinen Kommunikationspartner.'
                groups.append(group)
                continue
            size = 1
            for k in ordered:
                size *= len(self.bindings[k]['candidates'])
            if size > 128:
                group['reason'] = 'Zu viele mögliche Anschlüsse. Bitte die gewünschte Verbindung im Netzwerkeditor eingrenzen.'
                groups.append(group)
                continue
            if not affected_routes:
                group['reason'] = 'Für diese Nachricht fehlt die bisherige Empfängerroute. Bitte die gewünschte Kommunikation festlegen; der Agent erfindet keine Empfänger.'
                groups.append(group)
                continue
            conflicts = []
            # Saved routing intent remains evidence even if the old gateway port
            # itself has been deleted and no current channel carries that bus.
            previous_gateways = {str(g.get('node_id') if isinstance(g, dict) else g)
                for r in affected_routes for g in (r.get('route') or {}).get('gateways', [])}
            previous_system_path = any(self.hardware.get(g, {}).get('device_type') == 'Gateway' for g in previous_gateways)
            for combination in product(*(self.bindings[k]['candidates'] for k in ordered)):
                mapping = dict(zip(ordered, combination))
                planned_routes, alternatives = [], []
                valid = True
                for route in affected_routes:
                    rid = str(route['id'])
                    projected = self.functional_routes[rid][0]
                    endpoints = [self.endpoint(e, mapping.get(self.endpoint_keys.get((rid, i)))) for i, e in enumerate([projected['source'], *projected['destinations']])]
                    if not all(endpoints):
                        valid = False; break
                    path_options = [self.paths(endpoints[0]['port_id'], e['port_id']) for e in endpoints[1:]]
                    if any(not paths for paths in path_options):
                        valid = False; break
                    # Validate message publisher references against the proposed source.
                    for mid in message_refs(route, self.signals):
                        m = self.messages.get(str(mid), {})
                        primary = mapping.get(self.message_keys.get((str(mid), 0)))
                        primary_id = str(primary['id']) if primary else str(m.get('hardware_interface_id') or '')
                        extras = extra_bindings(m)
                        permitted = {primary_id, *(str(mapping.get(self.message_keys.get((str(mid), i + 1)), {}).get('id') or b.get('hardware_interface_id')) for i, b in enumerate(extras))}
                        if endpoints[0]['port_id'] not in permitted or (m.get('interface_id') and str(m['interface_id']) != str(endpoints[0].get('interface_id'))):
                            valid = False
                    planned_routes.append((route, endpoints))
                    alternatives.extend(path_options)
                if not valid:
                    continue
                for path_set in islice(product(*alternatives), 128):
                    updates, path_index = [], 0
                    for original, endpoints in planned_routes:
                        paths = path_set[path_index:path_index + len(endpoints) - 1]
                        path_index += len(endpoints) - 1
                        gateways, edges = [], set()
                        for path in paths:
                            edges.update(path['edges'])
                            for a, b in zip(path['ports'], path['ports'][1:]):
                                left, right = self.active[a], self.active[b]
                                if left['network_ref'] != right['network_ref']:
                                    hw = self.hardware[str(left['hardware_node_id'])]
                                    gateway = {'node_id': str(hw['id']), 'name': hw['name']}
                                    if gateway not in gateways: gateways.append(gateway)
                        hops = [{'node_id': e['node_id'], 'name': self.hardware[str(e['node_id'])]['name']} for e in endpoints]
                        ordered_hops = list({str(h['node_id']): h for h in [hops[0], *gateways, *hops[1:]]}.values())
                        updates.append({'id': str(original['id']), 'source': endpoints[0], 'destinations': endpoints[1:],
                            'route': {**original['route'], 'hops': ordered_hops, 'gateways': gateways, 'physical_paths': list(paths), 'functional_intent': self.functional_routes[str(original['id'])][1]},
                            'edge_ids': sorted(edges), 'expected_revision': original['revision']})
                    questions = []
                    for key, new in mapping.items():
                        old = self.bindings[key]
                        old_scopes = {self.scope(n, old=True) for n in old['networks']}
                        new_scope = self.scope(new['network_ref'])
                        system_to_cluster = previous_system_path and new_scope[0] == 'cluster'
                        if not old_scopes or any(scope != new_scope for scope in old_scopes) or system_to_cluster:
                            questions.append(f"{self.hardware.get(old['node_id'], {}).get('name', 'Gerät')}: bisher "
                                + ('System-/Gateway-Verbindung' if previous_system_path or any(s[0] == 'system' for s in old_scopes) else 'anderer oder ungeklärter Anschlussbereich')
                                + f", jetzt {self.networks[new['network_ref']].get('name', new['network_ref'])} ({'innerhalb eines Clusters' if new_scope[0] == 'cluster' else 'Systemnetz'}). Soll dieser neue Weg die bisherige Kommunikation übernehmen?")
                    message_changes = []
                    for m in affected_messages:
                        mid = str(m['id']); data = {}; configuration = deepcopy(m.get('configuration') or {})
                        for (message_id, index), key in self.message_keys.items():
                            if message_id != mid: continue
                            new = mapping[key]
                            if index == 0: data['hardware_interface_id'] = str(new['id'])
                            else:
                                configuration['physical_transmit_bindings'][index - 1].update(hardware_interface_id=str(new['id']), network_id=new['network_ref'])
                        if configuration != (m.get('configuration') or {}): data['configuration'] = configuration
                        data = {k: v for k, v in data.items() if v != m.get(k)}
                        if data: message_changes.append({'id': mid, 'data': data, 'expected_version': m['version']})
                    hardware_changes = {}
                    for path in path_set:
                        for a, b in zip(path['ports'], path['ports'][1:]):
                            left, right = self.active[a], self.active[b]
                            hw = self.hardware[str(left['hardware_node_id'])]
                            if left['hardware_node_id'] != right['hardware_node_id'] or left['network_ref'] == right['network_ref'] or forwarding_permitted(hw, left, right): continue
                            change = hardware_changes.setdefault(str(hw['id']), {'id': str(hw['id']), 'expected_version': hw['version'], 'data': {'identity': deepcopy(hw.get('identity') or {})}})
                            rules = change['data']['identity'].setdefault('communication_forwarding', [])
                            rule = forwarding_rule(left, right)
                            if rule not in rules: rules.append(rule)
                            question = f"{hw['name']} muss von {self.networks[left['network_ref']].get('name')} nach {self.networks[right['network_ref']].get('name')} weiterleiten. Mit der neuen Führung diese konkrete Ethernet-Weiterleitung als Entwicklungsanforderung bestätigen?"
                            if question not in questions: questions.append(question)
                    interface_changes = {}
                    for change in updates:
                        for endpoint in [change['source'], *change['destinations']]:
                            interface = self.all_objects.get(str(endpoint.get('interface_id')))
                            if interface and str(interface.get('hardware_node_id')) != str(endpoint['node_id']):
                                interface_changes[str(interface['id'])] = {'id': str(interface['id']), 'expected_version': interface['version'], 'data': {'hardware_node_id': endpoint['node_id']}}
                    option = {'bindings': {k: str(p['id']) for k, p in mapping.items()}, 'route_changes': updates, 'interface_changes': list(interface_changes.values()),
                        'message_changes': message_changes, 'hardware_changes': list(hardware_changes.values()), 'questions': questions, 'action': 'adopt',
                        'label': ' · '.join(f"{self.hardware[str(p['hardware_node_id'])]['name']}: {self.networks[p['network_ref']].get('name', p['network_ref'])} / Kanal {p.get('channel_index', '?')}" for p in combination)}
                    collision = self.identifier_conflicts(message_changes)
                    if collision:
                        conflicts.extend(collision)
                        continue
                    option['id'] = digest(option)[:20]
                    option['comparison'] = self.comparison(updates)
                    if not any(o['id'] == option['id'] for o in group['options']): group['options'].append(option)
                    if len(group['options']) >= 16: break
                if len(group['options']) >= 16: break
            if group['options']:
                group['status'] = 'QUESTION'
                group['reason'] = 'Die neue Führung erreicht alle bisherigen Empfänger. Bitte mit der bisherigen Führung vergleichen und auswählen.'
            else:
                local_candidates = [p for k in ordered for p in self.bindings[k]['candidates'] if self.scope(p['network_ref'])[0] == 'cluster']
                was_system = previous_system_path or any(self.scope(n, old=True)[0] == 'system' for k in ordered for n in self.bindings[k]['networks'])
                group['reason'] = ('Die bisherige Systemverbindung wurde getrennt; die neuen Clusteranschlüsse erreichen nicht alle bisherigen Empfänger. Soll die Systemkommunikation erhalten bleiben? Dann den System-/Gateway-Anschluss im Netzwerkeditor wiederherstellen und erneut prüfen.'
                    if was_system and local_candidates else 'Kein durchgängiger kompatibler Ersatzweg zu allen bisherigen Empfängern. Bitte die physische Verbindung im Netzwerkeditor ergänzen.')
            if conflicts and not group['options']:
                group['reason'] = ' '.join(sorted(set(conflicts))) + ' Bestehende Nachrichten-IDs bleiben unverändert.'
            groups.append(group)
        flows = [{'id': str(r['id']), 'code': r['route_code'], **self.functional_routes[str(r['id'])][2]} for r in self.routes]
        return {'token': digest([self.state['topology'], self.state['parameters'], self.objects, self.routes, self.history]), 'groups': groups,
            'architecture': {'hardware_nodes': len(self.hardware), 'physical_networks': len(self.networks), 'functions': len(self.objects['Function']),
                'communications': len(flows), 'resolved': sum(not f['issues'] for f in flows),
                'device_io': sum(any(p.get('partner_type') == 'hardware_io' for p in [f['source'], *f['destinations']]) for f in flows),
                'unresolved': [f for f in flows if f['issues']], 'flows': flows}}


def load_plan():
    from .pagination import all_pages
    from .repository import list_objects
    from .routing.repository import list_routes
    from .workflow.service import WorkflowStatusService
    from .project_context import current_project_id
    from .db import get_connection
    state = WorkflowStatusService(current_project_id()).get()
    objects = {kind: all_pages(list_objects, kind) for kind in KINDS}
    routes = all_pages(list_routes)
    with get_connection() as connection:
        rows = connection.execute("SELECT DISTINCT object_id::text AS port_id, snapshot->>'network_ref' AS network_id, "
            "snapshot->>'hardware_node_id' AS node_id FROM engineering_object_versions WHERE project_id=%s "
            "AND object_type='HardwareNetworkInterface' AND COALESCE(snapshot->>'network_ref','')<>'' "
            "ORDER BY port_id, network_id, node_id", (current_project_id(),)).fetchall()
    return RepairPlanner(state, objects, routes, rows), state


def complete_plan(planner):
    plan = planner.build()
    proposed = RepairPlanner(planner.state, planner.objects, planner.routes, planner.history, propose_forwarding=True, detection_graph=planner.graph)
    alternatives = {g['id']: g for g in proposed.build()['groups']}
    from .communication_restore import restoration_option
    from .communication_contract_repair import add_contract_options
    for group in plan['groups']:
        add_contract_options(planner, group)
        if not group['options'] and alternatives.get(group['id'], {}).get('options'):
            group['options'] = alternatives[group['id']]['options']
            group['reason'] = 'Die neue Verkabelung erreicht die bisherigen Empfänger mit einer zusätzlich zu bestätigenden Weiterleitung.'
        restore, reason = restoration_option(planner, group)
        group['restore_unavailable'] = reason
        if restore: group['options'].append(restore)
        group['options'].sort(key=lambda o: (o.get('action') == 'restore', sum(len(c['data']['identity'].get('communication_forwarding', [])) for c in o.get('hardware_changes', [])), sum(len(p['ports']) for c in o['route_changes'] for p in c['route'].get('physical_paths', []))))
        if group['options']: group['status'] = 'QUESTION'
    return plan


def public_plan(plan):
    return {'token': plan['token'], 'architecture': plan.get('architecture'), 'groups': [{**{k: v for k, v in g.items() if k != 'options'},
        'options': [{k: o[k] for k in ('id', 'label', 'questions', 'action', 'comparison') if k in o} for o in g['options']]} for g in plan['groups']]}


def apply_repair(payload):
    from .repository import update_object, get_object, create_object
    from .routing.repository import update_route, get_route, save_validation, create_route
    from .routing.validation import RoutingValidator
    from .workflow.service import WorkflowStatusService
    from .project_context import current_project_id
    from .db import get_connection
    planner, state = load_plan(); plan = complete_plan(planner)
    if not payload.get('token') or payload['token'] != plan['token']:
        raise ConcurrentUpdateError('Das Modell wurde geändert. Bitte den Reparatur-Agenten erneut starten.')
    choices = payload.get('choices') or {}
    if not isinstance(choices, dict): raise EngineeringValidationError('choices muss ein Objekt sein.')
    if any(key not in {g['id'] for g in plan['groups']} for key in choices):
        raise EngineeringValidationError('Die Auswahl gehört nicht zum aktuellen Reparaturplan.')
    selected = []
    for group in plan['groups']:
        identifier = choices.get(group['id'])
        if payload.get('automatic') is True and group['status'] == 'AUTO': identifier = group['options'][0]['id']
        if not identifier: continue
        option = next((o for o in group['options'] if o['id'] == identifier), None)
        if option is None: raise EngineeringValidationError('Der gewählte Ersatzweg ist nicht verfügbar.')
        selected.append((group, option))
    if not selected: return {'applied': [], 'plan': public_plan(plan)}
    if len(selected) > 1:
        raise EngineeringValidationError('Bitte eine Führung nach der anderen übernehmen und anschließend den aktualisierten Plan prüfen.')
    actor = 'communication-repair-agent'
    replacements = {}
    for _, option in selected:
        for creation in option.get('create_ports', []):
            created = create_object('HardwareNetworkInterface', {**creation['data'], 'created_by': actor})
            replacements[creation['id']] = str(created['id'])
    def replace(value):
        if isinstance(value, dict): return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list): return [replace(v) for v in value]
        return replacements.get(value, value) if isinstance(value, str) else value
    selected = [(g, replace(o)) for g, o in selected]
    message_changes = [m for _, option in selected for m in option['message_changes']]
    collisions = planner.identifier_conflicts(message_changes, [p for _, option in selected for p in option.get('port_changes', [])])
    if collisions:
        raise EngineeringValidationError('Reparatur nicht gespeichert: ' + '; '.join(collisions))
    topology = deepcopy(state['topology'])
    route_changes = [r for _, option in selected for r in option['route_changes']]
    for _, option in selected:
        if option.get('topology') is not None: topology = deepcopy(option['topology'])
        for change in option.get('port_changes', []):
            update_object('HardwareNetworkInterface', change['id'], {**change['data'], 'expected_version': change['expected_version'], 'modified_by': actor})
        for change in option.get('hardware_changes', []):
            update_object('HardwareNode', change['id'], {**change['data'], 'expected_version': change['expected_version'], 'modified_by': actor})
        for change in option.get('interface_changes', []):
            update_object('Interface', change['id'], {**change['data'], 'expected_version': change['expected_version'], 'modified_by': actor})
        for change in option['message_changes']:
            update_object('Message', change['id'], {**change['data'], 'expected_version': change['expected_version'], 'modified_by': actor})
    # Keep the physical channel's message index consistent with canonical bindings.
    touched = set()
    effective_messages = dict(planner.messages)
    for change in message_changes:
        old = planner.messages[change['id']]
        new = {**old, **change['data']}
        effective_messages[change['id']] = new
        for m in (old, new):
            touched.update(filter(None, [m.get('hardware_interface_id'), *(b.get('hardware_interface_id') for b in extra_bindings(m))]))
    for identifier in touched:
        if str(identifier) not in planner.ports: continue
        port = get_object('HardwareNetworkInterface', str(identifier))
        refs = sorted(str(m['id']) for m in effective_messages.values() if identifier in
            [m.get('hardware_interface_id'), *(b.get('hardware_interface_id') for b in extra_bindings(m))])
        if sorted(port.get('message_refs') or []) != refs:
            update_object('HardwareNetworkInterface', str(identifier), {'message_refs': refs, 'expected_version': port['version'], 'modified_by': actor})
    for _, option in selected:
        for creation in option.get('create_routes', []):
            created = create_route({**creation['data'], 'created_by': actor})
            change = {'id': str(created['id']), 'source': creation['data']['source'],
                'destinations': creation['data']['destinations'], 'route': creation['data']['route'],
                'expected_revision': created['revision'], 'edge_ids': creation['edge_ids']}
            option['route_changes'].append(change)
            route_changes.append(change)
    for change in route_changes:
        reason = 'Vom Nutzer gewählte Kommunikationsführung; fachliche Kommunikation und Payload unverändert.'
        update_route(change['id'], {**{k: change[k] for k in ('source', 'destinations', 'route', 'expected_revision')}, 'modified_by': actor, 'reason': reason})
        for edge in topology.get('edges', []):
            refs = {str(r) for r in edge.get('routingEntryIds', [])}
            if edge.get('routingEntryId'): refs.add(str(edge['routingEntryId']))
            refs.discard(change['id'])
            if edge['id'] in change['edge_ids']: refs.add(change['id'])
            if refs or edge.get('routingEntryIds'): edge['routingEntryIds'] = sorted(refs)
            if edge.get('routingEntryId') == change['id']: edge['routingEntryId'] = next(iter(sorted(refs)), None)
            if edge['id'] in change['edge_ids'] and not edge.get('routingEntryId'): edge['routingEntryId'] = change['id']
            metadata = edge.get('routingMetadata') or {}
            if edge['id'] in change['edge_ids']:
                metadata[change['id']] = {**metadata.get(change['id'], {}), 'approvalState': 'PENDING'}
                edge['routingMetadata'] = metadata
            else: metadata.pop(change['id'], None)
        with get_connection() as connection:
            connection.execute("DELETE FROM engineering_relations WHERE project_id=%s AND "
                "((relation_type='ROUTES_TO' AND attributes->>'route_id'=%s) OR "
                "(relation_type='USES_ROUTE' AND target_type='RoutingEntry' AND target_id=%s))",
                (current_project_id(), change['id'], change['id']))
    workflow = WorkflowStatusService(current_project_id())
    workflow.mark_changed('engineering_model', 'Physische Kommunikationsbindungen repariert; Folgebewertungen erneuern.', actor=actor)
    workflow.save_topology(topology, actor=actor)
    physical_planner, _ = load_plan()
    validator = RoutingValidator(current_project_id(), physical_planner=physical_planner)
    for change in route_changes:
        validation = validator.validate(get_route(change['id']), exclude_route_id=change['id'])
        if not validation.get('valid'):
            raise EngineeringValidationError('Reparatur nicht gespeichert: ' + '; '.join(e['message'] for e in validation['errors'][:3]))
        save_validation(change['id'], validation, actor=actor)
    workflow.refresh_source_status('routing', actor=actor, reason='Physische Bindungen repariert; geänderte Routen erneut freigeben.')
    after, _ = load_plan()
    return {'applied': [{'id': g['id'], 'routes': len(o['route_changes']), 'messages': len(o['message_changes']), 'label': o['label']} for g, o in selected],
            'plan': public_plan(complete_plan(after))}
