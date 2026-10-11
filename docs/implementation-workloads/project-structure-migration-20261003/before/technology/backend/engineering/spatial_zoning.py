"""Explicit installation zones, independent of functional ownership and protocol.

The project architecture rule separates local buses by location across domains.
It is not a protocol restriction. Unknown locations never acquire a guessed zone.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import re

from backend.knowledge.semantic_vocabulary import engineering_tokens
from .models import EngineeringValidationError
from .network_scene import confirmed_groups, build_network_scene

from .spatial_architecture import (VERSION, DERIVED_SOURCES, LABELS, LOCAL_BUSES,
    architecture_from, installation_zone, location_decision, zone_label)


def driving_side_from_prompt(prompt):
    match = re.search(r'^- Lenkungsseite:\s*(LHD|RHD)\s*$', prompt, re.M)
    return match[1] if match else None


def node_decisions(topology, hardware=(), prompt='', driving_side=None, parameters=None):
    _, owners = confirmed_groups(topology, prompt)
    architecture = architecture_from(parameters, prompt)
    hw = {str(h['id']): h for h in hardware}
    nodes = {n['id']: n for n in topology.get('nodes', [])}
    decisions = {key: location_decision(n['name'], hw.get(str(n.get('engineeringId')), {}).get('identity'),
                    driving_side, architecture, n.get('engineeringId')) for key, n in nodes.items()}
    # Functional ownership alone does not establish physical co-location.
    return decisions, owners


def node_zones(topology, hardware=(), prompt='', driving_side=None, parameters=None):
    decisions, owners = node_decisions(topology, hardware, prompt, driving_side, parameters)
    return {key: value['zone_id'] for key, value in decisions.items()}, owners


def spatial_assessment(state, hardware=()):
    parameters = state.get('parameters') or {}
    prompt = (state.get('context', {}).get('wizard_request') or {}).get('prompt', '')
    architecture = architecture_from(parameters, prompt)
    side = (parameters.get('spatial_zoning') or {}).get('driving_side') or driving_side_from_prompt(prompt)
    topology = state.get('topology') or {}
    decisions, owners = node_decisions(topology, hardware, prompt, side, parameters)
    items = [{'hardware_id': n.get('engineeringId'), 'name': n['name'],
              'functional_owner_id': owners.get(n['id']), **decisions[n['id']]}
             for n in topology.get('nodes', [])]
    items.sort(key=lambda item: item['name'].casefold())
    return {'version': VERSION, 'architecture': architecture, 'driving_side': side,
            'decisions': items, 'known_devices': sum(d['zone_id'] != 'UNKNOWN' for d in items),
            'unresolved_devices': [d['name'] for d in items if d['zone_id'] == 'UNKNOWN' and d['functional_owner_id']],
            'conflicts': zone_findings(topology, hardware, prompt=prompt, driving_side=side, parameters=parameters)}


def zone_findings(topology, hardware=(), *, prompt='', driving_side=None, parameters=None):
    zones, owners = node_zones(topology, hardware, prompt, driving_side, parameters)
    backbones = {n['id'] for n in (parameters or {}).get('networks', []) if n.get('spatial_scope') == 'backbone'}
    buses = defaultdict(set)
    for edge in topology.get('edges', []):
        if edge.get('bus') in LOCAL_BUSES and edge.get('physicalNetworkId') not in backbones:
            buses[edge.get('physicalNetworkId')].update((edge['source'], edge['target']))
    findings = []
    for network, members in buses.items():
        endpoints = [key for key in members if key in owners]
        if not endpoints: continue  # Controller backbones span zones by design.
        positions = {zones[key] for key in endpoints}
        if len(positions) > 1:
            findings.append({'code': 'MIXED_INSTALLATION_ZONES', 'severity': 'ERROR', 'network_id': network,
                'zones': sorted(positions), 'message': f'{network}: lokale Teilnehmer aus getrennten Einbauzonen.'})
    return findings


def plan_zoning(state, objects, routes, driving_side=None):
    topology = deepcopy(state.get('topology'))
    if (not isinstance(topology, dict) or not isinstance(topology.get('nodes'), list)
            or not isinstance(topology.get('edges'), list)):
        raise EngineeringValidationError('Vor der räumlichen Zonierung muss eine gültige Netzwerktopologie vorliegen.')
    prompt = (state.get('context', {}).get('wizard_request') or {}).get('prompt', '')
    policy = {'enabled': True, 'version': VERSION, 'driving_side': driving_side,
              'local_bus_types': sorted(LOCAL_BUSES), 'unknown_location': 'separate_unresolved'}
    architecture = architecture_from(state.get('parameters'), prompt)
    policy['reference_frame'] = architecture['reference_frame']
    decisions, owners = node_decisions(topology, objects['HardwareNode'], prompt, driving_side, state.get('parameters'))
    zones = {key: value['zone_id'] for key, value in decisions.items()}
    nodes = {n['id']: n for n in topology['nodes']}
    physical = {str(p['id']): deepcopy(p) for p in objects['HardwareNetworkInterface']}
    networks = deepcopy(state['parameters'].get('networks') or [])
    declared = {n['id']: n for n in networks}
    changes, creations, divisions = {}, [], []
    def patch(kind, key, values):
        changes.setdefault((kind, key), {}).update(deepcopy(values))
        if kind == 'HardwareNetworkInterface': physical[key].update(deepcopy(values))
    for hw in objects['HardwareNode']:
        node = next((n for n in nodes.values() if n.get('engineeringId') == str(hw['id'])), None)
        if not node: continue
        identity = deepcopy(hw.get('identity') or {})
        if identity.get('installation_zone_source') in {None, *DERIVED_SOURCES} and not (
                identity.get('installation_zone') and identity.get('installation_zone_source') is None):
            identity.update(installation_zone=zones[node['id']], installation_zone_source=VERSION)
        identity['installation_reference_frame'] = architecture['reference_frame']
        identity['spatial_decision'] = decisions[node['id']]
        if identity != hw.get('identity'): patch('HardwareNode', str(hw['id']), {'identity': identity})
        node['installationZone'] = zones[node['id']]
    groups = defaultdict(list)
    for edge in topology['edges']:
        if edge.get('bus') in LOCAL_BUSES and declared.get(edge['physicalNetworkId'], {}).get('spatial_scope') != 'backbone':
            groups[edge['physicalNetworkId']].append(edge)
    touched_routes = set()
    for old_network, edges in sorted(groups.items()):
        members = {e[s] for e in edges for s in ('source', 'target')}
        endpoints = members & owners.keys()
        if not endpoints: continue
        anchors = {owners[n] for n in endpoints}
        if len(anchors) != 1 or not members <= endpoints | anchors:
            raise EngineeringValidationError('Lokaler Bus besitzt mehrere System-Owner; vor der Zonierung fachlich zuordnen.')
        owner = next(iter(anchors))
        buckets = defaultdict(list)
        for edge in edges:
            positions = {zones[n] for n in (edge['source'], edge['target']) if n != owner}
            if len(positions) != 1:
                raise EngineeringValidationError('Direkte Querverbindung zwischen Einbauzonen kann nicht automatisch getrennt werden.')
            buckets[next(iter(positions))].append(edge)
        if set(buckets) == {'UNKNOWN'}: continue
        old = declared.get(old_network)
        if not old: raise EngineeringValidationError(f'Netzparameter fehlen: {old_network}')
        # Retain the original identity for one branch; split, never merge buses.
        retained = 'UNKNOWN' if 'UNKNOWN' in buckets else sorted(buckets)[0]
        port_targets = defaultdict(set)
        target_data = {}
        for zone, subset in sorted(buckets.items()):
            target = old_network if zone == retained else 'zone-' + sha256((old_network + ':' + zone).encode()).hexdigest()[:18]
            short = f"{nodes[owner]['name']} {edges[0]['bus'].replace('_', ' ').upper()} {zone_label(zone, architecture)}"
            existing_name = old.get('name') if old.get('installation_zone') == zone else None
            name = existing_name or short
            occupied_names = {n['name'] for n in networks if n['id'] not in {target, old_network}}
            ordinal = 2
            while name in occupied_names:
                name = f'{short} {ordinal:02d}'; ordinal += 1
            target_data[target] = {**old, 'id': target, 'name': name, 'installation_zone': zone,
                                   'zoning_source': VERSION, 'system_owner_id': nodes[owner]['engineeringId']}
            if target != old_network:
                if target in declared: raise EngineeringValidationError('Zonen-Netzkennung bereits anderweitig belegt.')
                networks.append(target_data[target]); declared[target] = target_data[target]
            else:
                old.update(target_data[target])
            for edge in subset:
                for side in ('source', 'target'): port_targets[edge[side + 'Port']].add(target)
            if len(buckets) > 1:
                divisions.append({'from_network': old_network, 'network_id': target, 'name': name, 'zone': zone,
                    'devices': sorted(nodes[n]['name'] for e in subset for n in (e['source'], e['target']) if n != owner)})
        port_map = {}
        for node in nodes.values():
            for port in list(node['ports']):
                targets = port_targets.get(port['id'])
                if not targets: continue
                original = deepcopy(port)
                hw = deepcopy(physical[str(port['hardwareInterfaceId'])])
                reuse = old_network if old_network in targets else sorted(targets)[0]
                for target in sorted(targets):
                    data = target_data[target]
                    if target == reuse:
                        current = port; identifier = str(hw['id'])
                    else:
                        digest = sha256((node['id'] + target).encode()).hexdigest()[:18]
                        current = {**original, 'id': 'zone-port-' + digest}
                        identifier = '$zone-channel-' + digest
                        # A new master channel is a planned hardware resource.
                        channel = max([0, *[int(p.get('channel_index') or 0) for p in physical.values()
                            if str(p.get('hardware_node_id')) == str(hw['hardware_node_id'])
                            and p.get('technology') == hw['technology'] and p.get('controller_ref') == hw.get('controller_ref')]]) + 1
                        physical[identifier] = {**hw, 'id': identifier, 'channel_index': channel, 'physical_port_ref': 'zone-' + digest}
                        node['ports'].append(current)
                        creations.append({'object_type': 'HardwareNetworkInterface', 'local_ref': identifier,
                            'data': {k: physical[identifier].get(k) for k in ('hardware_node_id', 'technology', 'controller_ref', 'channel_index',
                                'physical_port_ref', 'bitrate', 'data_bitrate', 'target_load_limit', 'warning_load_limit', 'hard_load_limit')}})
                    values = {'network_ref': target, 'name': data['name'], 'static_load': None, 'runtime_load': None,
                        'capabilities': {**hw.get('capabilities', {}), 'network_id': target, 'installation_zone': data['installation_zone']}}
                    if any(physical[identifier].get(k) != v for k, v in values.items()): patch('HardwareNetworkInterface', identifier, values)
                    current.update(hardwareInterfaceId=identifier, engineeringId=identifier,
                        physicalNetworkId=target, physicalNetworkName=data['name'], name=data['name'])
                    port_map[original['id'], target] = current
        for zone, subset in buckets.items():
            target = old_network if zone == retained else 'zone-' + sha256((old_network + ':' + zone).encode()).hexdigest()[:18]
            for edge in subset:
                before = deepcopy(edge)
                edge.update(physicalNetworkId=target, physicalNetworkName=target_data[target]['name'])
                for side in ('source', 'target'):
                    p = port_map[edge[side + 'Port'], target]
                    edge[side + 'Port'] = p['id']; edge[side + 'InterfaceName'] = p['name']
                if edge != before: touched_routes.update([edge.get('routingEntryId'), *edge.get('routingEntryIds', [])])
    # Direct multicast commands are one logical message, with separate physical
    # source bindings/routes when recipients now live on distinct local buses.
    route_changes = []
    from .routing.network_sync import enrich_route_from_linked_topology
    for route in routes:
        if str(route['id']) not in touched_routes or route.get('status') in {'REJECTED', 'SUPERSEDED', 'DEPRECATED', 'OUTDATED'}: continue
        linked = [e for e in topology['edges'] if str(route['id']) in {e.get('routingEntryId'), *e.get('routingEntryIds', [])}]
        source_node = next(n for n in nodes.values() if n.get('engineeringId') == str(route['source']['node_id']))
        incident = [e for e in linked if source_node['id'] in (e['source'], e['target'])]
        source_networks = {e['physicalNetworkId'] for e in incident}
        if len(source_networks) <= 1:
            route_changes.append(enrich_route_from_linked_topology(route, topology)); continue
        if any(source_node['id'] not in (e['source'], e['target']) for e in linked):
            raise EngineeringValidationError('Mehrkanal-Multicast mit Gateway benötigt einen expliziten Pfad je Quelle.')
        for index, network in enumerate(sorted(source_networks)):
            subset = [e for e in linked if e['physicalNetworkId'] == network]
            hw_ids = {nodes[e[s]]['engineeringId'] for e in subset for s in ('source', 'target')}
            branch = deepcopy(route)
            branch['destinations'] = [d for d in branch['destinations'] if str(d['node_id']) in hw_ids]
            if not branch['destinations']: raise EngineeringValidationError('Multicast-Ziel kann keiner Zone zugeordnet werden.')
            branch['id'] = str(route['id']) if index == 0 else '$zone-route-' + sha256((str(route['id']) + network).encode()).hexdigest()[:18]
            branch['name'] = source_node['name'] + ' → ' + ', '.join(d.get('node_name', '') for d in branch['destinations'])
            for edge in subset:
                edge['routingEntryIds'] = [branch['id'] if r == str(route['id']) else r for r in edge.get('routingEntryIds', [])]
                if edge.get('routingEntryId') == str(route['id']): edge['routingEntryId'] = branch['id']
                metadata = edge.get('routingMetadata', {})
                if str(route['id']) in metadata: metadata[branch['id']] = metadata.pop(str(route['id']))
            route_changes.append(enrich_route_from_linked_topology(branch, {**topology, 'edges': subset}))
    effective_routes = [r for r in routes if str(r['id']) not in {str(c['id']) for c in route_changes}] + route_changes
    for message in objects['Message']:
        primary = physical.get(str(message.get('hardware_interface_id')))
        config = deepcopy(message.get('configuration') or {})
        bindings = {}
        for r in effective_routes:
            p = r.get('payload') or {}
            if str(message['id']) in {p.get('message_id'), *p.get('message_ids', [])}:
                bindings[str(r['source'].get('port_id'))] = r['source'].get('network_id')
        if not bindings and primary: bindings[str(primary['id'])] = primary.get('network_ref')
        old_bindings = config.get('physical_transmit_bindings') or []
        affected = str(message.get('hardware_interface_id')) in {key for kind, key in changes if kind == 'HardwareNetworkInterface'}
        affected = affected or any(b.get('hardware_interface_id') in {key for kind, key in changes if kind == 'HardwareNetworkInterface'} for b in old_bindings)
        affected = affected or any(key.startswith('$zone-channel-') for key in bindings)
        if affected and bindings:
            primary_id = str(message.get('hardware_interface_id'))
            primary_id = primary_id if primary_id in bindings else sorted(bindings)[0]
            config['physical_transmit_bindings'] = [{'hardware_interface_id': key, 'network_id': net, 'source': VERSION} for key, net in sorted(bindings.items())]
            values = {'hardware_interface_id': primary_id, 'configuration': config}
            if any(message.get(k) != v for k, v in values.items()): patch('Message', str(message['id']), values)
    for creation in creations: creation['data'].update(changes.pop((creation['object_type'], creation['local_ref']), {}))
    from .physical_ports import topology_port_findings
    errors = topology_port_findings(topology, objects['HardwareNode'], list(physical.values()))
    errors += zone_findings(topology, objects['HardwareNode'], prompt=prompt, driving_side=driving_side, parameters=state.get('parameters'))
    if errors: raise EngineeringValidationError('; '.join(e['message'] for e in errors[:5]))
    from .intelligence.resource_policy import resource_decision, planning_policy, planning_inventory
    resources = resource_decision(state['topology'], topology, planning_inventory(state), planning_policy(state))
    for item in resources['resources']:
        limit = item['hard_limit'] if item['hard_limit'] is not None else item['baseline_count'] if resources['mode'] == 'FIXED_INVENTORY' else None
        if limit is not None and item['planned_count'] > limit:
            raise EngineeringValidationError('Zonierung überschreitet den verbindlichen Hardware-Ressourcenbestand.')
    topology = build_network_scene(topology, prompt, positions=(state['topology'].get('scene') or {}).get('manualPositions'))
    fingerprint = sha256(json.dumps([state['versions'], objects, routes, policy], sort_keys=True, default=str).encode()).hexdigest()
    return {'token': fingerprint, 'policy': policy, 'divisions': divisions, 'resources': resources,
        'architecture': architecture, 'decisions': decisions, 'topology': topology, 'networks': networks, 'changes': changes, 'creations': creations, 'routes': route_changes,
        'unresolved_devices': sorted(nodes[n]['name'] for n in owners if zones[n] == 'UNKNOWN')}
