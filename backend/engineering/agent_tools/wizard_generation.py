"""Create a reviewable model from the same deterministic catalogs as the wizard."""
from __future__ import annotations

import json
import hashlib
from difflib import SequenceMatcher
from pathlib import Path
import shutil
import subprocess
import re

from . import model, proposal_service
from .. import proposals as proposal_store
from ..device_classification import DeviceClassificationRegistry
from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from ..routing.generation import RoutingGenerationService
from ..routing.validation import PROTOCOL_CAPACITY


_TOPOLOGY_BUS_BY_PROTOCOL = {
    'CAN': 'can_fd',
    'CAN_FD': 'can_fd',
    'CAN_XL': 'can_fd',
    'LIN': 'lin',
    'FLEXRAY': 'flexray',
    'ETHERNET': 'automotive_ethernet',
    'SOME_IP': 'automotive_ethernet',
    'SOMEIP': 'automotive_ethernet',
}


def _technology_contract(interface_type: str) -> dict:
    """Resolve wizard vocabulary through the central registry without protocol switches."""
    technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(interface_type)
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
    stack = tuple(profile.get('default_stack') or (technology_id,))
    resolved = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(stack)
    return {
        'technology_id': technology_id,
        'stack': list(stack),
        'layer': profile['layer'],
        'transport_unit_type': profile['transport_unit'],
        'hardware_interface': profile['hardware_interface'],
        'implementation_status': profile['implementation_status'],
        'capabilities': profile['capabilities'],
        'binding': type(resolved['binding']).__name__,
        'generator': type(resolved['generator']).__name__,
        'validator_chain': [type(item).__name__ for item in resolved['validators']],
        'timing_model': type(resolved['timing_model']).__name__,
        'load_calculator': type(resolved['load_calculator']).__name__,
    }


def _network_protocol(interface_type: str) -> str:
    """Translate model-facing interface labels to canonical network protocols."""
    key = re.sub(r'[^A-Z0-9]+', '_', str(interface_type or '').upper()).strip('_')
    aliases = {
        'CANFD': 'CAN_FD',
        'FLEXRAY': 'FLEXRAY',
        'AUTOMOTIVE_ETHERNET': 'ETHERNET',
        'SOMEIP': 'SOME_IP',
        'PROFINET': 'PROFINET',
        'ETHERCAT': 'ETHERCAT',
        'MODBUSTCP': 'MODBUS',
        'MODBUS_TCP': 'MODBUS',
        'MODBUSRTU': 'MODBUS',
        'MODBUS_RTU': 'MODBUS',
        'OPCUA': 'OPC_UA',
        'ROS2': 'ROS_2',
    }
    protocol = aliases.get(key, key)
    return protocol if protocol in PROTOCOL_CAPACITY else 'CUSTOM'


def extract_specification(prompt: str) -> dict:
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js wird für den vorhandenen Wizard-Generator benötigt.')
    script = Path(__file__).resolve().parents[3] / 'frontend' / 'scripts' / 'extract-wizard-specification.mjs'
    result = subprocess.run(
        [node, '--experimental-strip-types', str(script)],
        input=json.dumps({'prompt': prompt}), text=True, encoding='utf-8',
        capture_output=True, timeout=60, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )
    if result.returncode:
        raise ValueError('Die Wizard-Spezifikation konnte nicht abgeleitet werden: ' + result.stderr[-1000:])
    return json.loads(result.stdout)


def generate(arguments: dict) -> dict:
    fingerprint = hashlib.sha256(('technology-binding-v3\n' + arguments['prompt']).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        contract = row.get('engineering_contract') or {}
        if (row['proposal_type'] == 'WIZARD_ENGINEERING_MODEL'
                and any(item.get('prompt_sha256') == fingerprint for item in row.get('evidence') or [])
                and (contract.get('validation_result') or {}).get('valid') is True):
            return proposal_service.envelope(row)
    spec = extract_specification(arguments['prompt'])
    changes, refs = [], {}
    kinds = ('HardwareNode', 'Function', 'HardwareNetworkInterface', 'Interface', 'Message', 'Signal')
    existing = {kind: model.objects(kind) for kind in kinds}

    def ensure(kind, name, data, parent=None):
        signature = (kind, name.casefold(), data.get(parent) if parent else None)
        if signature in refs:
            return refs[signature]
        matches = [row for row in existing[kind] if row['name'].casefold() == name.casefold()
                   and (not parent or str(row.get(parent)) == str(data[parent]))]
        if len(matches) > 1:
            raise ValueError(f'Mehrdeutige vorhandene Zuordnung: {kind} {name}')
        if matches:
            if kind == 'HardwareNode' and matches[0].get('device_type') != data['device_type']:
                raise ValueError(f'Gerätetyp des vorhandenen Systems {name} passt nicht zum Auftrag.')
            ref = str(matches[0]['id'])
        else:
            local_ref = f'object-{len(changes)}'
            changes.append({'object_type': kind, 'local_ref': local_ref, 'data': {'name': name, **data}})
            ref = '$' + local_ref
        refs[signature] = ref
        return ref

    declared_networks: dict[str, str] = {}
    for chain in spec['chains']:
        network_ref = str(chain.get('transport_network_ref') or '').strip()
        if not network_ref:
            continue
        protocol = _network_protocol(chain['interface_type'])
        previous = declared_networks.get(network_ref)
        if previous and previous != protocol:
            raise ValueError(f'Netzwerk {network_ref} wurde mit widersprüchlichen Technologien bestätigt.')
        declared_networks[network_ref] = protocol
    for network_ref, protocol in sorted(declared_networks.items()):
        changes.append({
            'object_type': 'Network',
            'local_ref': f'network-{len(changes)}',
            'data': {'id': network_ref, 'name': network_ref, 'technology': protocol},
        })

    for chain in spec['chains']:
        technology_contract = _technology_contract(chain['interface_type'])
        profile = DeviceClassificationRegistry().resolve_profile(
            name=chain['hardware_name'], device_type=chain['device_type'],
            device_class=chain.get('device_class'))
        hw = ensure('HardwareNode', chain['hardware_name'], {
            'device_type': chain['device_type'], 'device_class': profile.device_class,
            'description': chain['hardware_description']})
        fn = None
        if profile.requires_function_model:
            fn = ensure('Function', chain['function_name'], {
                'hardware_node_id': hw, 'domain': spec['domain'], 'description': chain['function_description']}, 'hardware_node_id')
        port = ensure('HardwareNetworkInterface', chain['interface_name'], {
            'hardware_node_id': hw, 'technology': chain['interface_type'], 'channel_index': 1,
            'network_ref': chain.get('transport_network_ref'),
            'capabilities': {
                'hardware_interface': technology_contract['hardware_interface'],
                'technology_stack': technology_contract['stack'],
                **technology_contract['capabilities'],
            }}, 'hardware_node_id')
        interface = ensure('Interface', chain['interface_name'], {
            **({'function_id': fn} if fn else {'hardware_node_id': hw}),
            'interface_type': chain['interface_type']}, 'function_id' if fn else 'hardware_node_id')
        message = ensure('Message', chain['message_name'], {
            'interface_id': interface, 'hardware_interface_id': port,
            **{key: chain[key] for key in ('message_id_hex', 'direction', 'cycle_ms', 'dlc')},
            'configuration': {
                'model_type': 'TransportUnit',
                'technology_binding': technology_contract,
                'transport_unit': {
                    'transport_unit_type': technology_contract['transport_unit_type'],
                    'producer_ref': hw,
                    'consumer_refs': [],
                    'payload_size': chain.get('dlc'),
                    'timing': {'cycle_ms': chain.get('cycle_ms')},
                    'status': 'PROPOSED',
                    'provenance': {'source': 'wizard', 'generator': technology_contract['generator']},
                },
            }}, 'interface_id')
        ensure('Signal', chain['signal_name'], {
            'message_id': message,
            **{key: chain[key] for key in ('start_bit', 'length_bits', 'byte_order', 'data_type',
                'factor', 'offset_value', 'unit', 'min_value', 'max_value', 'configuration',
                'semantic', 'data', 'communication', 'quality') if key in chain},
            'protocol_bindings': [{
                'model_type': 'PayloadElement',
                'element_type': 'SIGNAL',
                'semantic_ref': chain.get('signal_name'),
                'data_type': chain.get('data_type'),
                'size': chain.get('length_bits'),
                'unit': chain.get('unit'),
                'encoding': {
                    'byte_order': chain.get('byte_order'),
                    'factor': chain.get('factor'),
                    'offset': chain.get('offset_value'),
                },
                'source_ref': hw,
                'technology_binding_ref': technology_contract['technology_id'],
            }]}, 'message_id')
    if not changes:
        raise ValueError('Die abgeleiteten Modellobjekte sind bereits vorhanden; vorhandenen Modellstand prüfen.')
    return proposal_service.create('WIZARD_ENGINEERING_MODEL', changes,
        f"Engineering-Modell aus bestätigten Wizard-Vorgaben: {len(changes)} vorgeschlagene Änderungen. "
        "Noch keine Änderungen am kanonischen Modell; Freigabe und Übernahme sind erforderlich.",
        assumptions=['Technische Defaults und ergänzte Geräte stammen aus den Wizard-Branchenkatalogen und müssen geprüft werden.',
                     'Dieses Paket umfasst das Engineering-Modell. Routing, Topologie und Simulation folgen nach der Modellfreigabe.'],
        evidence=[{'source': 'wizard-specification-generator', 'prompt_sha256': fingerprint, 'target_counts': spec['targetCounts'],
                   'communication_system_counts': spec['communicationSystemCounts'],
                   'model_type': spec.get('modelType') or spec.get('domain'),
                   'architecture': 'HardwareNode -> HardwareInterface -> FunctionalInterface -> TechnologyBinding -> TransportUnit -> PayloadElement'}])


def generate_routing(arguments: dict) -> dict:
    """Turn the confirmed cluster ownership graph into one reviewable route proposal.

    This continuation is deliberately deterministic. A completed mass-created
    model must not depend on a language model deciding whether to call hundreds
    of route tools.
    """
    prompt = arguments['prompt']
    fingerprint = hashlib.sha256(('wizard-routing-v2\n' + prompt).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        if (row['proposal_type'] == 'WIZARD_ROUTING'
                and any(item.get('prompt_sha256') == fingerprint for item in row.get('evidence') or [])):
            return proposal_service.envelope(row)
    raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    if not raw:
        raise ValueError('Der bestätigte Systemcluster-Graph fehlt; Routing kann nicht reproduzierbar erzeugt werden.')
    graph = json.loads(raw.group(1))
    nodes = model.objects('HardwareNode')
    interfaces = model.objects('Interface')
    messages = model.objects('Message')
    nodes_by_name = {str(item.get('name', '')).casefold(): item for item in nodes}
    interfaces_by_node: dict[str, list[dict]] = {}
    for item in interfaces:
        node_id = str(item.get('hardware_node_id') or '')
        if node_id:
            interfaces_by_node.setdefault(node_id, []).append(item)
    messages_by_interface: dict[str, list[dict]] = {}
    for item in messages:
        messages_by_interface.setdefault(str(item.get('interface_id') or ''), []).append(item)

    def node(name):
        return nodes_by_name.get(str(name or '').casefold())

    def first_message(node_id: str):
        for interface in interfaces_by_node.get(node_id, []):
            candidates = messages_by_interface.get(str(interface['id']), [])
            if candidates:
                return str(candidates[0]['id'])
        return None

    route_service = RoutingGenerationService()
    gateway = next((item for item in nodes if item.get('device_type') == 'Gateway'), None)
    changes, seen = [], set()

    def add_route(source, destination):
        if not source or not destination or str(source['id']) == str(destination['id']):
            return
        message_id = first_message(str(source['id']))
        key = (str(source['id']), str(destination['id']), message_id)
        if key in seen:
            return
        seen.add(key)
        route = route_service.generate_route(source_node_id=key[0], destination_node_id=key[1], message_id=message_id)
        source_protocol = str(route.get('source', {}).get('protocol') or '')
        destination_protocol = str((route.get('destinations') or [{}])[0].get('protocol') or '')
        if source_protocol != destination_protocol:
            transformation = {
                'type': 'PROTOCOL_TRANSLATION',
                'from_protocol': source_protocol,
                'to_protocol': destination_protocol,
                'reason': 'Explizite Gateway-Übersetzung für den HMI-/Domänenübergang.',
            }
            route['route']['transformations'] = [transformation]
            if gateway:
                gateway_hop = {'node_id': str(gateway['id']), 'name': gateway['name']}
                route['route']['gateways'] = [gateway_hop]
                route['route']['hops'] = [route['route']['hops'][0], gateway_hop, route['route']['hops'][-1]]
        changes.append({'object_type': 'RoutingEntry', 'data': route})

    for cluster in graph:
        for controller in cluster.get('controllers') or []:
            ecu = node(controller.get('ecu'))
            for sensor_name in controller.get('sensors') or []:
                add_route(node(sensor_name), ecu)
            for actuator_name in controller.get('actuators') or []:
                add_route(ecu, node(actuator_name))
        for hmi_route in cluster.get('hmi_routes') or []:
            add_route(node(hmi_route.get('source')), node(hmi_route.get('target')))
    if not changes:
        raise ValueError('Aus dem bestätigten Systemcluster-Graph konnten keine prüfbaren Routen abgeleitet werden.')
    return proposal_service.create(
        'WIZARD_ROUTING', changes,
        f'{len(changes)} Kommunikationsrouten aus den bestätigten Controller-Zuordnungen. '
        'Der kanonische Projektstand bleibt bis zur Freigabe unverändert.',
        assumptions=['Controller-Besitz bestimmt Sensor- und Aktor-Richtung; physische Pfade bleiben Gegenstand der Routing-Prüfung.'],
        evidence=[{'source': 'confirmed-system-cluster-graph', 'prompt_sha256': fingerprint, 'route_count': len(changes)}],
    )


def _topology_bus(value: str | None) -> str:
    key = re.sub(r'[^A-Z0-9]+', '_', str(value or '').upper()).strip('_')
    return _TOPOLOGY_BUS_BY_PROTOCOL.get(key, 'automotive_ethernet')


_SEMANTIC_NETWORK_FAMILIES = (
    ('powertrain', 'Antriebsstrang', ('motor', 'engine', 'antrieb', 'powertrain', 'kraftstoff', 'fuel', 'abgas', 'exhaust', 'getriebe', 'transmission', 'kupplung', 'clutch', 'drehmoment', 'torque', 'elektromotor', 'inverter', 'ladesteuerung')),
    ('energy', 'Energieversorgung', ('energie', 'energy', 'batterie', 'battery', 'bms', 'bordnetz', 'alternator', 'generator', 'spannung', 'voltage', 'strom', 'current')),
    ('chassis', 'Fahrwerk / Fahrdynamik', ('fahrwerk', 'fahrdynamik', 'bremse', 'brems', 'brake', 'lenkung', 'steering', 'suspension', 'daempfer', 'damper', 'reifen', 'tire', 'wheel', 'stabilitaet', 'allrad', 'anhaenger')),
    ('safety', 'Passive Sicherheit', ('airbag', 'restraint', 'rueckhalt', 'crash', 'impact', 'seatbelt', 'gurt')),
    ('driver-assistance', 'Fahrerassistenz', ('adas', 'fahrerassistenz', 'radar', 'kamera', 'camera', 'lidar', 'park', 'parking', 'spur', 'lane', 'ultraschall')),
    ('body-comfort', 'Karosserie / Komfort', ('karosserie', 'body', 'komfort', 'comfort', 'wischer', 'wiper', 'tuer', 'door', 'fenster', 'window', 'sitz', 'seat', 'keyless', 'heckklappe', 'tailgate', 'licht', 'light')),
    ('climate', 'Klima / Thermik', ('klima', 'climate', 'hvac', 'thermal', 'thermo', 'kuehlung', 'kuehl', 'kuehlkreislauf', 'cooling', 'kompressor', 'compressor', 'innenraum', 'cabin', 'refrigerant')),
    ('infotainment', 'Infotainment', ('infotainment', 'display', 'kombiinstrument', 'headup', 'audio', 'sound', 'telematik', 'navigation', 'connectivity', 'konnektivitaet')),
    ('diagnostics', 'Diagnose', ('diagnose', 'diagnostic', 'service', 'uds', 'obd', 'logging', 'trace')),
)


def _semantic_text(value: object) -> str:
    text = str(value or '').casefold()
    for source, target in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(source, target)
    return re.sub(r'[^a-z0-9]+', '', text)


def _semantic_slug(value: object) -> str:
    text = str(value or '').casefold()
    for source, target in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(source, target)
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', text))


def _semantic_physical_network(bus: str, *items: dict) -> tuple[str, str] | None:
    candidates = []
    for item_index, item in enumerate(items):
        name = _semantic_text(item.get('name'))
        is_controller = str(item.get('device_type') or '') not in {'SensorController', 'ActuatorController', 'Gateway'}
        for family_index, (key, label, terms) in enumerate(_SEMANTIC_NETWORK_FAMILIES):
            specificity = max((len(_semantic_text(term)) for term in terms if _semantic_text(term) in name), default=0)
            if specificity:
                candidates.append((10_000 if is_controller else 0, specificity, -family_index, -item_index, key, label))
    if not candidates:
        return None
    _controller, _specificity, _family_index, _item_index, _key, label = max(candidates)
    technology = bus.replace('_', '-')
    display = 'CAN' if bus == 'can_fd' else 'Ethernet' if bus == 'automotive_ethernet' else bus.upper()
    return f'{_semantic_slug(label)}-{technology}-bus', f'{label}-{display}'


def generate_network_topology(arguments: dict) -> dict:
    """Materialize approved logical routes as a reviewable physical topology.

    Every canonical hardware participant is represented exactly once. Physical
    edges are derived only from approved, valid routes; duplicate route
    segments share one edge and retain all contributing route IDs.
    """
    prompt = arguments['prompt']
    hardware = sorted(model.objects('HardwareNode'), key=lambda item: (str(item.get('name', '')).casefold(), str(item['id'])))
    interfaces = model.objects('HardwareNetworkInterface')
    routes = [route for route in model.routes()
              if str(route.get('approval_state') or '').upper() == 'APPROVED'
              and (route.get('validation') or {}).get('valid') is True]
    if len(hardware) < 2:
        raise ValueError('Für eine Netzwerktopologie werden mindestens zwei kanonische Hardwareknoten benötigt.')
    if not routes:
        raise ValueError('Es existieren keine freigegebenen, validen Routen als Grundlage der Netzwerktopologie.')

    hardware_by_id = {str(item['id']): item for item in hardware}
    interfaces_by_node: dict[str, list[dict]] = {}
    for interface in interfaces:
        interfaces_by_node.setdefault(str(interface.get('hardware_node_id') or ''), []).append(interface)
    for values in interfaces_by_node.values():
        values.sort(key=lambda item: (str(item.get('technology', '')), str(item.get('name', '')), str(item['id'])))

    kind_by_type = {
        'Gateway': 'gateway',
        'SensorController': 'sensor',
        'ActuatorController': 'actuator',
    }
    node_data: dict[str, dict] = {}
    port_refs: dict[tuple[str, str, str], str] = {}

    def ensure_port(node_id: str, bus: str, network_id: str = '', network_name: str = '') -> str:
        key = (node_id, bus, network_id)
        if key in port_refs:
            return port_refs[key]
        candidates = interfaces_by_node.get(node_id, [])
        matching = [item for item in candidates if _topology_bus(item.get('technology')) == bus]
        interface = matching[0] if matching else (candidates[0] if candidates else None)
        network_suffix = f'-{network_id}' if network_id else ''
        port_id = f'topology-port-{node_id}-{bus}{network_suffix}'
        port = {
            'id': port_id,
            'name': network_name or str(interface.get('name') if interface else f'{bus}-Port'),
            'bus': bus,
            'side': 'right',
            'offset': 0.5,
        }
        if network_id:
            port['physicalNetworkId'] = network_id
            port['physicalNetworkName'] = network_name
        if interface is not None:
            port.update({
                'engineeringId': str(interface['id']),
                'hardwareInterfaceId': str(interface['id']),
            })
            if not matching:
                port['requestedTechnology'] = bus
        node_data[node_id]['ports'].append(port)
        port_refs[key] = port_id
        return port_id

    for index, item in enumerate(hardware):
        identifier = str(item['id'])
        node_data[identifier] = {
            'id': f'topology-node-{identifier}',
            'name': item['name'],
            'kind': kind_by_type.get(str(item.get('device_type')), 'ecu'),
            'x': 80 + (index % 10) * 220,
            'y': 80 + (index // 10) * 150,
            'ports': [],
            'engineeringId': identifier,
        }

    segments: dict[tuple[str, str, str, str], dict] = {}
    for route in sorted(routes, key=lambda item: (str(item.get('route_code', '')), str(item['id']))):
        source = str((route.get('source') or {}).get('node_id') or '')
        destinations = [str(item.get('node_id') or '') for item in route.get('destinations') or [] if isinstance(item, dict)]
        route_hops = [str(item.get('node_id') or '') for item in (route.get('route') or {}).get('hops') or [] if isinstance(item, dict)]
        source_bus = _topology_bus((route.get('source') or {}).get('protocol'))
        for destination_index, destination in enumerate(destinations):
            if source not in hardware_by_id or destination not in hardware_by_id:
                continue
            destination_bus = _topology_bus(((route.get('destinations') or [])[destination_index] or {}).get('protocol'))
            path = [node_id for node_id in route_hops if node_id in hardware_by_id]
            if not path or path[0] != source or path[-1] != destination:
                path = [source, destination]
            for segment_index, (left, right) in enumerate(zip(path, path[1:])):
                bus = source_bus if segment_index == 0 else destination_bus
                network = _semantic_physical_network(bus, hardware_by_id[left], hardware_by_id[right])
                network_id, network_name = network or ('', '')
                key = (left, right, bus, network_id)
                reverse_key = (right, left, bus, network_id)
                segment = segments.get(key) or segments.get(reverse_key)
                route_id = str(route['id'])
                if segment:
                    segment['routingEntryIds'] = sorted(set([*segment['routingEntryIds'], route_id]))
                    segment['routingMetadata'][route_id] = {
                        'routeId': route_id,
                        'routeCode': str(route.get('route_code') or ''),
                        'name': str(route.get('name') or ''),
                        'source': source,
                        'target': destination,
                        'protocol': str((route.get('source') or {}).get('protocol') or ''),
                        'approvalState': 'APPROVED',
                    }
                    continue
                source_port = ensure_port(left, bus, network_id, network_name)
                target_port = ensure_port(right, bus, network_id, network_name)
                edge_id = f'topology-edge-{len(segments) + 1:04d}'
                segments[key] = {
                    'id': edge_id,
                    'name': f'{hardware_by_id[left]["name"]} — {hardware_by_id[right]["name"]}',
                    'source': node_data[left]['id'],
                    'sourcePort': source_port,
                    'target': node_data[right]['id'],
                    'targetPort': target_port,
                    'bus': bus,
                    **({'physicalNetworkId': network_id, 'physicalNetworkName': network_name} if network_id else {}),
                    'direction': 'BIDIRECTIONAL',
                    'relationType': 'CONNECTED_VIA',
                    'engineeringRelationId': f'{route_id}:segment:{segment_index}',
                    'routingEntryId': route_id,
                    'routingEntryIds': [route_id],
                    'routingMetadata': {route_id: {
                        'routeId': route_id,
                        'routeCode': str(route.get('route_code') or ''),
                        'name': str(route.get('name') or ''),
                        'source': source,
                        'target': destination,
                        'protocol': str((route.get('source') or {}).get('protocol') or ''),
                        'approvalState': 'APPROVED',
                    }},
                    'origin': 'ROUTING_TABLE',
                }

    if not segments:
        raise ValueError('Aus den freigegebenen Routen konnten keine physischen Segmente erzeugt werden.')
    # A physical topology must not leave canonical participants floating merely
    # because they have no dedicated logical route. Attach such nodes to the
    # closest already connected peer on the same bus. These edges deliberately
    # remain distinguishable from route-derived segments.
    connected = {node_id for left, right, _bus, _network in segments for node_id in (left, right)}
    fallback_count = 0
    for node_id, node in node_data.items():
        if node_id in connected:
            continue
        candidate = (interfaces_by_node.get(node_id) or [None])[0]
        if candidate is None:
            raise ValueError(f'Hardwareknoten {hardware_by_id[node_id]["name"]} besitzt kein physisches Interface.')
        bus = _topology_bus(candidate.get('technology'))
        anchors = [other_id for other_id in connected if other_id != node_id and any(
            _topology_bus(interface.get('technology')) == bus for interface in interfaces_by_node.get(other_id, []))]
        if not anchors:
            anchors = [other_id for other_id in connected if other_id != node_id]
        if not anchors:
            raise ValueError(f'Für Hardwareknoten {hardware_by_id[node_id]["name"]} wurde kein physischer Netzpartner gefunden.')
        name = str(hardware_by_id[node_id].get('name') or '')
        anchor = max(anchors, key=lambda other_id: (
            SequenceMatcher(None, name.casefold(), str(hardware_by_id[other_id].get('name') or '').casefold()).ratio(),
            1 if hardware_by_id[other_id].get('device_type') in {'ECU', 'Gateway'} else 0,
            str(hardware_by_id[other_id].get('name') or ''),
        ))
        network = _semantic_physical_network(bus, hardware_by_id[node_id], hardware_by_id[anchor])
        network_id, network_name = network or ('', '')
        source_port = ensure_port(node_id, bus, network_id, network_name)
        target_port = ensure_port(anchor, bus, network_id, network_name)
        fallback_count += 1
        edge_id = f'topology-edge-{len(segments) + 1:04d}'
        relation_id = f'physical-completeness:{node_id}:{anchor}:{bus}'
        segments[(node_id, anchor, bus, network_id)] = {
            'id': edge_id,
            'name': f'{hardware_by_id[node_id]["name"]} — {hardware_by_id[anchor]["name"]}',
            'source': node_data[node_id]['id'],
            'sourcePort': source_port,
            'target': node_data[anchor]['id'],
            'targetPort': target_port,
            'bus': bus,
            **({'physicalNetworkId': network_id, 'physicalNetworkName': network_name} if network_id else {}),
            'direction': 'BIDIRECTIONAL',
            'relationType': 'CONNECTED_VIA',
            'engineeringRelationId': relation_id,
            'routingEntryIds': [],
            'routingMetadata': {},
            'origin': 'WIZARD_PHYSICAL_COMPLETENESS',
        }
        connected.add(node_id)
    topology = {'nodes': list(node_data.values()), 'edges': list(segments.values())}
    state_signature = hashlib.sha256(json.dumps({
        'nodes': [(item['id'], item.get('version')) for item in hardware],
        'interfaces': [(item['id'], item.get('version'), item.get('technology')) for item in interfaces],
        'routes': [(item['id'], item.get('revision'), item.get('approval_state')) for item in routes],
    }, sort_keys=True).encode('utf-8')).hexdigest()
    fingerprint = hashlib.sha256(('wizard-network-v3-semantic-shared-buses\n' + prompt + '\n' + state_signature).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        contract = row.get('engineering_contract') or {}
        if (row['proposal_type'] == 'WIZARD_NETWORK_TOPOLOGY'
                and any(item.get('prompt_sha256') == fingerprint for item in row.get('evidence') or [])
                and (contract.get('validation_result') or {}).get('valid') is True):
            return proposal_service.envelope(row)
    return proposal_service.create(
        'WIZARD_NETWORK_TOPOLOGY',
        [{'object_type': 'NetworkTopology', 'data': {'name': 'Wizard-Netzwerktopologie', 'topology': topology}}],
        f'Physische Netzwerktopologie aus {len(routes)} freigegebenen Routen: '
        f'{len(topology["nodes"])} Geräte und {len(topology["edges"])} deduplizierte Segmente; '
        f'{fallback_count} Teilnehmer wurden ohne künstliche logische Route physisch ergänzt. '
        'Der Workflow-Stand bleibt bis zur menschlichen Freigabe unverändert.',
        assumptions=['Busse folgen den validierten Endpunktprotokollen; gemeinsame physische Segmente bündeln ihre logischen Routen.'],
        evidence=[{'source': 'approved-routing-table', 'prompt_sha256': fingerprint,
                   'route_count': len(routes), 'node_count': len(topology['nodes']), 'edge_count': len(topology['edges']),
                   'physical_completion_edges': fallback_count}],
    )
