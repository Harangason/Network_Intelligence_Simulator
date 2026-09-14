"""Controlled canonical operations for a previously authorized connection plan.

These functions are not generic model write tools. The executor supplies the
persisted plan and calls them inside one project transaction.
"""
from copy import deepcopy
from uuid import uuid4
from .graph import ModelGraphService
from .ports import inspect_port_decision, connection_findings
from ..physical_ports import _interface_technology, technology_id, topology_port_findings
from ..repository import create_object, update_object
from ..project_context import current_project_id
from ..workflow.service import WorkflowStatusService
from ..agent_tools.model import json_safe


class ExecutionBlocked(ValueError):
    def __init__(self, code, message, evidence=None):
        super().__init__(message)
        self.findings = [{'code': code, 'severity': 'ERROR', 'message': message, 'evidence': evidence or {}}]


def checked_port(graph, interface, *, require_network=True, role=None):
    owner, tech = str(interface['hardware_node_id']), technology_id(interface['technology'])
    caps = [c for c in graph.find_communication_capabilities(owner) if technology_id(c['technology']) == tech]
    controllers = [c for c in graph.find_communication_controllers(owner) if c['id'] == interface.get('controller_ref')]
    if not caps or any(c['supported'] is not True for c in caps):
        raise ExecutionBlocked('COMMUNICATION_CAPABILITY_MISSING', 'Technologie-Fähigkeit ist nicht bestätigt.')
    if len(controllers) != 1 or controllers[0].get('status', 'ACTIVE') != 'ACTIVE':
        raise ExecutionBlocked('COMMUNICATION_CONTROLLER_MISSING', 'Aktiver Controller des Anschlusses fehlt.')
    controller = controllers[0]
    tech_controllers = [c for c in graph.find_communication_controllers(owner) if technology_id(c['technology']) == tech]
    tech_ports = graph.find_ports_by_technology(owner, tech)
    channels = {(i.get('controller_ref'), i.get('channel_index')) for i in graph.find_hardware_interfaces(owner)
        if technology_id(i['technology']) == tech and i.get('channel_index')}
    if any(len(tech_controllers) > c['controller_count'] or len(tech_ports) > c['max_ports'] or len(channels) > c['max_channels'] for c in caps):
        raise ExecutionBlocked('HARDWARE_INTERFACE_CAPACITY_EXCEEDED', 'Die vorhandenen Anschlüsse überschreiten bestätigte Hardwaregrenzen.')
    net = graph.networks.get(interface.get('network_ref'), {})
    if net and any(c.get('supported_bitrates') and net.get('bitrate') not in c['supported_bitrates'] for c in caps):
        raise ExecutionBlocked('CONTROLLER_BITRATE_MISMATCH', 'Die Netzbitrate ist für die Hardware nicht bestätigt.')
    if technology_id(controller['technology']) != tech:
        raise ExecutionBlocked('CONTROLLER_TECHNOLOGY_MISMATCH', 'Controller und Anschluss verwenden verschiedene Technologien.')
    channel = interface.get('channel_index')
    if type(channel) is not int or not 1 <= channel <= controller['max_channels']:
        raise ExecutionBlocked('HARDWARE_INTERFACE_CAPACITY_EXCEEDED', 'Kanal liegt außerhalb der bestätigten Controllergrenze.')
    peers = graph.find_hardware_interfaces(owner)
    if any(str(p['id']) != str(interface['id']) and p.get('controller_ref') == controller['id'] and p.get('channel_index') == channel for p in peers):
        raise ExecutionBlocked('DUPLICATE_PHYSICAL_CHANNEL', 'Der Controllerkanal ist mehrfach belegt.')
    if not interface.get('physical_port_ref') or (require_network and not interface.get('network_ref')):
        raise ExecutionBlocked('PORT_MISSING', 'Physischer Anschluss oder Netzbindung fehlt.')
    port = next((p for p in graph.find_ports(owner) if p['hardware_interface_ref'] == str(interface['id'])), None)
    if role and port and port.get('direction') not in {'BIDIRECTIONAL', 'OUTPUT' if role == 'source' else 'INPUT'}:
        raise ExecutionBlocked('PORT_DIRECTION_MISMATCH', 'Der physische Anschluss unterstützt die benötigte Kommunikationsrichtung nicht.')
    errors = connection_findings(graph, port, graph.networks.get(interface['network_ref'])) if interface.get('network_ref') else []
    if errors: raise ExecutionBlocked(errors[0]['code'], errors[0]['message'])
    return port


def ensure_destination(graph, workload, strategy, actor):
    destination = workload['host_refs'][1]
    option = strategy['option']
    if strategy.get('path'):
        return graph.hni[strategy['target_port']]
    decision = inspect_port_decision(graph, destination, strategy['technology'], strategy['network_ref'])
    if not decision['options']:
        raise ExecutionBlocked('PORT_PLAN_INVALID', 'Die Anschlussentscheidung ist nicht mehr umsetzbar.', decision)
    if option['id'] == 'REUSE':
        if decision.get('existing_interface_ref') != strategy.get('target_port'):
            raise ExecutionBlocked('PLAN_STALE', 'Der vorgesehene Anschluss hat sich geändert.')
        interface = graph.hni[strategy['target_port']]
    else:
        candidate = next((o for o in decision['options'] if o['id'] == 'CREATE_AND_CONNECT_PORT'), None)
        if candidate != option:
            raise ExecutionBlocked('PLAN_STALE', 'Der bestätigte Controllerkanal ist nicht mehr frei.')
        net = graph.networks[strategy['network_ref']]
        values = {'name': net.get('name') or net['id'], 'hardware_node_id': destination,
            'technology': _interface_technology(strategy['technology']), 'controller_ref': option['controller_ref'],
            'channel_index': option['channel_index'], 'physical_port_ref': f'physical-port-{uuid4()}',
            'network_ref': net['id'], 'bitrate': net.get('bitrate'), 'data_bitrate': net.get('data_bitrate'),
            'provenance': {'generator': 'authorized-engineering-goal', 'workload_id': workload['workload_id']},
            'source': 'ai_generated', 'modified_by': actor}
        existing = option.get('hardware_interface_ref')
        interface = update_object('HardwareNetworkInterface', existing, values) if existing else create_object('HardwareNetworkInterface', values)
    if interface.get('network_ref') != strategy['network_ref']:
        interface = update_object('HardwareNetworkInterface', str(interface['id']), {'network_ref': strategy['network_ref'], 'modified_by': actor})
    interface = json_safe(interface)
    persist_port_resources(graph, interface, actor, workload['workload_id'])
    return interface


def persist_port_resources(graph, interface, actor, workload_id):
    from .store import save_resource
    current = next((p for p in graph.resources.get('PhysicalPort', []) if p['id'] == interface['physical_port_ref']), {})
    port = {**current, 'id': interface['physical_port_ref'], 'hardware_node_ref': str(interface['hardware_node_id']),
        'controller_ref': interface['controller_ref'], 'hardware_interface_ref': interface['id'],
        'technology': interface['technology'], 'channel_index': interface['channel_index'],
        'network_ref': interface['network_ref'], 'connection_status': 'CONNECTED',
        'direction': current.get('direction', 'BIDIRECTIONAL'),
        'provenance': current.get('provenance', {'workload_id': workload_id})}
    if port != current: save_resource('PhysicalPort', port)
    connection_id = f'connection:{interface["physical_port_ref"]}:{interface["network_ref"]}'
    old = next((c for c in graph.resources.get('NetworkConnection', []) if c['connection_id'] == connection_id), {})
    connection = {**old, 'connection_id': connection_id,
        'port_ref': interface['physical_port_ref'], 'network_ref': interface['network_ref'],
        'technology_binding_ref': interface['id'], 'created_by': old.get('created_by', actor), 'status': 'ACTIVE',
        'provenance': old.get('provenance', {'workload_id': workload_id})}
    if connection != old: save_resource('NetworkConnection', connection)


def ensure_topology(graph, source, target, actor):
    topology = deepcopy(graph.model.get('topology') or {'nodes': [], 'edges': []})
    nodes = topology.setdefault('nodes', []); edges = topology.setdefault('edges', [])
    endpoints = []
    for interface in (source, target):
        owner = str(interface['hardware_node_id'])
        node = next((n for n in nodes if str(n.get('engineeringId')) == owner), None)
        if node is None:
            hardware = graph.hardware[owner]
            node = {'id': f'topology-node-{owner}', 'engineeringId': owner, 'name': hardware['name'],
                'kind': 'gateway' if hardware['device_type'] == 'Gateway' else 'ecu', 'ports': [], 'x': 0, 'y': 0}
            nodes.append(node)
        ports = node.setdefault('ports', [])
        port = next((p for p in ports if str(p.get('hardwareInterfaceId')) == str(interface['id'])), None)
        if port is None:
            port = {'id': f'topology-port-{interface["id"]}', 'hardwareInterfaceId': str(interface['id'])}
            ports.append(port)
        port.update(name=interface['name'], bus=interface['technology'], physicalNetworkId=interface['network_ref'])
        endpoints.append((node, port))
    (src, sp), (dst, dp) = endpoints
    if not any({e.get('sourcePort'), e.get('targetPort')} == {sp['id'], dp['id']} for e in edges):
        from ..relations import create_relation
        relation = next((r for r in graph.relations if r.get('relation_type') == 'CONNECTED_VIA'
            and r.get('source_type') == r.get('target_type') == 'HardwareNode'
            and {str(r.get('source_id')), str(r.get('target_id'))} == {src['engineeringId'], dst['engineeringId']}), None)
        if relation is None:
            relation = create_relation({'relation_type': 'CONNECTED_VIA', 'source_type': 'HardwareNode', 'source_id': src['engineeringId'],
                'target_type': 'HardwareNode', 'target_id': dst['engineeringId'], 'source': 'ai_generated',
                'approval_state': 'approved', 'review_state': 'reviewed', 'created_by': actor,
                'attributes': {'network_ref': source['network_ref'], 'source_hardware_interface': source['id'], 'target_hardware_interface': target['id']}})
        edges.append({'id': f'goal-edge-{uuid4()}', 'source': src['id'], 'sourcePort': sp['id'],
            'target': dst['id'], 'targetPort': dp['id'], 'bus': source['technology'],
            'engineeringRelationId': str(relation['id']),
            'physicalNetworkId': source['network_ref'], 'direction': 'bidirectional', 'relationshipType': 'CONNECTED_VIA'})
    WorkflowStatusService(current_project_id()).save_topology(topology, actor=actor)


def ensure_receiver_interface(graph, workload, target_port, actor):
    target = workload['target_ref']
    interfaces = graph.find_function_interfaces(target) if target in graph.functions else [i for i in graph.interfaces.values() if str(i.get('hardware_node_id')) == workload['host_refs'][1]]
    matching = [i for i in interfaces if technology_id(i['interface_type']) == technology_id(target_port['technology'])]
    if len(matching) > 1:
        raise ExecutionBlocked('AMBIGUOUS_FUNCTION_INTERFACE', 'Mehrere passende Empfangsschnittstellen erfordern eine gezielte Auswahl.')
    if matching: return matching[0]
    return json_safe(create_object('Interface', {'name': f'{graph.find_object(target)["name"]}_{target_port["technology"]}',
        'hardware_node_id': workload['host_refs'][1], 'function_id': target if target in graph.functions else None,
        'interface_type': target_port['technology'], 'configuration': {'network_ref': target_port['network_ref']},
        'source': 'ai_generated', 'provenance': {'workload_id': workload['workload_id']}, 'created_by': actor}))


def bind_messages(graph, workload, source, actor):
    from ..signal_audit import inspect_message_signals, occupied_signal_bits
    from ..message_packing import valid_payload_bytes
    from ..message_bindings import message_hardware_interface_ids
    affected_networks = {source['network_ref']}
    for mid in workload['message_ids']:
        affected_networks.update(graph.hni[p]['network_ref'] for p in message_hardware_interface_ids(graph.messages[mid])
            if p in graph.hni and graph.hni[p].get('network_ref'))
    used_identifiers = set()
    for other in graph.messages.values():
        if not any(graph.hni.get(p, {}).get('network_ref') in affected_networks for p in message_hardware_interface_ids(other)): continue
        try: used_identifiers.add(int(str(other.get('message_id_hex')), 16))
        except (TypeError, ValueError): pass
    for mid in workload['message_ids']:
        message = deepcopy(graph.messages[mid])
        logical = graph.interfaces[str(message['interface_id'])]
        if technology_id(logical['interface_type']) != technology_id(source['technology']):
            raise ExecutionBlocked('TRANSPORT_MAPPING_REQUIRED', 'Ein Technologiewechsel des Senders benötigt eine explizite Transportabbildung.')
        signals = [s for s in graph.signals.values() if str(s.get('message_id')) == mid]
        updates = {}
        if message.get('dlc') is None:
            occupancy = [occupied_signal_bits(s) for s in signals]
            if not occupancy or any(bits is None for bits in occupancy):
                raise ExecutionBlocked('SIGNAL_ENCODING_MISSING', 'Nutzlast benötigt explizite Bitpositionen, Längen und Byte-Reihenfolge.')
            byte_count = (max(set().union(*occupancy)) + 8) // 8
            size = valid_payload_bytes(source['technology'], byte_count)
            if size is None: raise ExecutionBlocked('PAYLOAD_TOO_LARGE', 'Die explizite Signalbelegung passt nicht in einen Transport dieser Technologie.')
            updates['dlc'] = message['dlc'] = size
        if not message.get('message_id_hex') and technology_id(source['technology']) in {'can', 'can_fd', 'can_xl'}:
            identifier = next((i for i in range(0x100, 0x800) if i not in used_identifiers), None)
            if identifier is None: raise ExecutionBlocked('FRAME_IDENTIFIER_EXHAUSTED', 'Im freigegebenen Identifierbereich ist keine Kennung frei.')
            used_identifiers.add(identifier)
            updates['message_id_hex'] = message['message_id_hex'] = f'0x{identifier:03X}'
        findings = [c for report in inspect_message_signals(signals, message) for c in report['checks'] if c['severity'] in {'ERROR', 'OPEN'}]
        if findings:
            raise ExecutionBlocked('TRANSPORT_INVALID', 'Die vorhandene Signalkodierung ist nicht gültig.', findings)
        config = deepcopy(message.get('configuration') or {})
        if not config.get('transport_unit'):
            config['transport_unit'] = {'publisher_function_ref': logical.get('function_id'),
                'publisher_hardware_ref': source['hardware_node_id'], 'technology_id': technology_id(source['technology']),
                'payload_bytes': message['dlc'], 'cycle_ms': message.get('cycle_ms'),
                'consumer_refs': sorted({workload['target_ref'], *((config.get('communication_contract') or {}).get('consumer_refs') or [])}), 'provenance': {'generator': 'authorized-engineering-goal',
                    'workload_id': workload['workload_id'], 'encoding': 'preserved-canonical-signal-positions'}}
        bindings = config.setdefault('physical_transmit_bindings', [])
        if not any(b.get('hardware_interface_id') == source['id'] and b.get('network_id') == source['network_ref'] for b in bindings):
            bindings.append({'hardware_interface_id': source['id'], 'network_id': source['network_ref'],
                'technology': source['technology'], 'provenance': {'workload_id': workload['workload_id']}})
        if config != (message.get('configuration') or {}): updates['configuration'] = config
        if updates: update_object('Message', mid, {**updates, 'modified_by': actor})


def ensure_routes(graph, workload, strategy, source, target, receiver_interface, actor):
    from ..routing import repository as routes
    from ..routing.validation import RoutingValidator
    from ..routing.generation import INTERFACE_TO_PROTOCOL
    from ..routing.timing import generated_timing
    ids = []
    paths = [strategy['path']] if strategy.get('path') else graph.find_gateways_between(workload['source_ref'], workload['target_ref'])
    path = next((p for p in paths if p['ports'][0] == source['id'] and p['ports'][-1] == target['id']), None)
    if not path: raise ExecutionBlocked('PHYSICAL_PATH_MISSING', 'Die gespeicherte Topologie enthält den vorgesehenen Weg nicht.')
    for port_id in path['ports']:
        checked_port(graph, graph.hni[port_id])
    gateways = []
    for a, b in zip(path['ports'], path['ports'][1:]):
        left, right = graph.hni[a], graph.hni[b]
        if left['network_ref'] != right['network_ref']:
            checked_port(graph, left, role='target')
            checked_port(graph, right, role='source')
            hw = graph.hardware[str(left['hardware_node_id'])]
            gateway = {'node_id': str(hw['id']), 'name': hw['name']}
            if gateway not in gateways: gateways.append(gateway)
            if technology_id(left['technology']) != technology_id(right['technology']):
                raise ExecutionBlocked('GATEWAY_CONVERSION_REQUIRED', 'Protokollumsetzung, Queue und Latenz müssen für den Gateway-Pfad explizit bestätigt sein.')
    def endpoint(port, logical):
        return {'node_id': str(port['hardware_node_id']), 'port_id': str(port['id']), 'interface_id': str(logical),
            'network_id': port['network_ref'], 'protocol': INTERFACE_TO_PROTOCOL.get(port['technology'], 'CUSTOM')}
    for mid in workload['message_ids']:
        message = graph.messages[mid]
        existing = [r for r in graph.find_routes_between(workload['source_ref'], workload['target_ref'])
            if mid in [r.get('payload', {}).get('message_id'), *(r.get('payload', {}).get('message_ids') or [])]]
        # A multicast route includes other functional partners; do not replace it with a unicast route.
        if any(len(r.get('destinations', [])) != 1 for r in existing):
            raise ExecutionBlocked('MULTICAST_DELTA_REQUIRED', 'Der bestehende Multicast-Pfad muss mit allen Empfängern gemeinsam geplant werden.')
        old = existing[0] if len(existing) == 1 else None
        if len(existing) > 1: raise ExecutionBlocked('AMBIGUOUS_EXISTING_ROUTE', 'Mehrere bestehende Routen müssen gezielt zugeordnet werden.')
        timing = old['timing'] if old else generated_timing(message.get('cycle_ms'), message)
        payload = deepcopy(old['payload']) if old else {'message_id': mid, 'signal_ids': [str(s['id']) for s in graph.signals.values() if str(s.get('message_id')) == mid]}
        src, dst = endpoint(source, message['interface_id']), endpoint(target, receiver_interface['id'])
        if old:
            src = {**old.get('source', {}), **src}
            dst = {**old['destinations'][0], **dst}
        data = {'name': old['name'] if old else f'{graph.find_object(workload["source_ref"])["name"]} → {graph.find_object(workload["target_ref"])["name"]}',
            'source': src, 'destinations': [dst], 'payload': payload, 'timing': timing,
            'route': {**(old.get('route', {}) if old else {}), 'hops': [{'node_id': src['node_id']}, *gateways, {'node_id': dst['node_id']}],
                'gateways': gateways, 'physical_paths': [path], 'transformations': deepcopy((old.get('route') or {}).get('transformations') or []) if old else []},
            'routing_policy': old['routing_policy'] if old else {'routing_type': 'UNICAST', 'redundancy': 'NONE', 'conditions': []},
            'description': old.get('description') if old else workload['goal'], 'modified_by': actor}
        if old:
            if all(old.get(k) == data[k] for k in ('source', 'destinations', 'payload', 'route', 'timing')) and old['approval_state'] == 'APPROVED':
                ids.append(str(old['id'])); continue
            row = routes.update_route(str(old['id']), {**data, 'expected_revision': old['revision']})
        else:
            proposal = routes.create_proposal({'prompt': workload['goal'], 'target_objects': workload['desired_state']['target_objects'],
                'generated_routes': [data], 'created_by': actor, 'evidence': [{'authorization': workload['authorization']}]})
            row = routes.accept_proposal_routes(str(proposal['proposal_id']), [0], actor=actor)[0]
        rid = str(row['id'])
        validation = RoutingValidator().validate(json_safe(row), exclude_route_id=rid)
        routes.save_validation(rid, validation, actor)
        if not validation['valid']: raise ExecutionBlocked('ROUTING_INVALID', 'Die geplante Route besteht die technische Prüfung nicht.', validation)
        routes.approve_routes([rid], actor=actor)
        ids.append(rid)
    # Capacity and simulation consume these canonical route-to-edge references.
    # Remove only this route's old path links; physical wiring and other routes remain.
    workflow = WorkflowStatusService(current_project_id())
    topology = deepcopy(workflow.get()['topology'])
    for edge in topology.get('edges', []):
        refs = set(edge.get('routingEntryIds') or [])
        legacy = edge.get('routingEntryId') or edge.get('routing_entry_id')
        if legacy: refs.add(str(legacy))
        refs.difference_update(ids)
        if edge.get('id') in path['edges']: refs.update(ids)
        edge['routingEntryIds'] = sorted(refs)
        if legacy in ids:
            edge.pop('routingEntryId', None); edge.pop('routing_entry_id', None)
    workflow.save_topology(topology, actor=actor)
    return ids
