"""Validate the effective proposal graph, including updates, before human review."""
from ..repository import ENTITY_SPECS, parent_link_for_payload
from ..signal_audit import inspect_message_signals
from ..message_packing import valid_payload_bytes
from ..capacity.calculators import estimate_frame, utilization_percent
from .model import objects, networks
from ..device_classification import DeviceClassificationRegistry
from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY


def _network_supports_interface(network_technology, interface_technology):
    registry = DEFAULT_TECHNOLOGY_REGISTRY
    network_id = registry.normalize_id(network_technology)
    interface_id = registry.normalize_id(interface_technology)
    if network_id == interface_id:
        return True
    profile = registry.profile(interface_id)
    stack = tuple(profile.get('default_stack') or ())
    return profile.get('layer') == 'APPLICATION' and bool(stack) and stack[0] == network_id


def validate_effective_model(changes):
    graph = {kind: {str(row['id']): row for row in objects(kind)} for kind in ENTITY_SPECS}
    touched, findings = {}, []
    declared = {str(row['id']): row for row in networks()}
    for index, change in enumerate(changes):
        kind = change['object_type']
        if kind == 'Network' and change['action'] == 'CREATE':
            declared[str(change['data']['id'])] = change['data']
        if kind not in graph:
            continue
        identifier = str(change.get('object_id') or '$'+change['local_ref'])
        touched[(kind, identifier)] = index
        if change['action'] == 'DELETE':
            graph[kind].pop(identifier, None)
        else:
            graph[kind][identifier] = {**graph[kind].get(identifier, {}), **change.get('data', {}), 'id': identifier}

    def parent(kind, identifier):
        value = graph[kind].get(str(identifier))
        if value is None:
            raise ValueError(f'{kind}-Referenz fehlt im aktiven Modell: {identifier}')
        return value

    # Changes to parents can invalidate existing messages just as direct edits do.
    for identifier, message in graph['Message'].items():
        logical = graph['Interface'].get(str(message.get('interface_id')), {})
        related = [('Interface', str(message.get('interface_id'))), ('HardwareNetworkInterface', str(message.get('hardware_interface_id'))), ('Function', str(logical.get('function_id')))]
        related.extend(('HardwareNetworkInterface', str(binding.get('hardware_interface_id'))) for binding in
            (message.get('configuration') or {}).get('physical_transmit_bindings') or [] if isinstance(binding, dict))
        if any(ref in touched for ref in related):
            touched.setdefault(('Message', identifier), next(touched[ref] for ref in related if ref in touched))
    from ..workflow.service import WorkflowStatusService
    from ..project_context import current_project_id
    from ..scope_rules import normalize_engineering_scope_rules, hardware_scope_category, communication_system_allows_interface
    raw_rules = (WorkflowStatusService(current_project_id()).get().get('context') or {}).get('engineering_scope_rules')
    rules = normalize_engineering_scope_rules(raw_rules) if raw_rules else None
    affected_messages, affected_ports = set(), set()
    for (kind, identifier), index in touched.items():
        item = graph[kind].get(identifier)
        if item is None:
            continue
        try:
            if kind == 'HardwareNode':
                registry = DeviceClassificationRegistry()
                valid, reason = registry.validate_device_suitability(
                    name=str(item.get('name') or ''), device_type=str(item.get('device_type') or ''),
                    device_class=int(item.get('device_class') or 0),
                    data_complexity=str(item.get('data_complexity') or 'SERVICE_DATA'))
                if not valid:
                    raise ValueError(reason)
            if kind == 'Function' and item.get('lifecycle_state') not in {'deprecated', 'superseded'}:
                hardware = parent('HardwareNode', item['hardware_node_id'])
                profile = DeviceClassificationRegistry().resolve_profile(
                    name=hardware.get('name', ''), device_type=hardware.get('device_type', ''),
                    device_class=hardware.get('device_class'))
                if not profile.requires_function_model:
                    raise ValueError('Klasse 0–2: Interface direkt an Hardware anbinden; keine künstliche Funktion erzeugen.')
            if rules and kind in {'Interface', 'HardwareNetworkInterface'}:
                if not communication_system_allows_interface(rules['communication_systems'], item.get('interface_type') or item.get('technology')):
                    raise ValueError('Die Kommunikationstechnologie ist durch die Projektregeln nicht zugelassen.')
            if rules and kind == 'HardwareNode':
                category = hardware_scope_category(item.get('device_type'))
                limit = rules['hardware_counts'].get(category)
                count = sum(hardware_scope_category(row.get('device_type')) == category for row in graph[kind].values())
                if limit is not None and count > limit:
                    raise ValueError(f'Projektregel überschritten: {count} statt höchstens {limit} {category}.')
            link = parent_link_for_payload(kind, item)
            if link:
                parent(link[1], item.get(link[0]))
            if item.get('name') and any(other['id'] != identifier and str(other.get('name') or '').strip().casefold() == str(item['name']).strip().casefold() and (not link or str(other.get(link[0])) == str(item.get(link[0]))) for other in graph[kind].values()):
                raise ValueError('Ein Objekt mit diesem Namen existiert bereits im gleichen Elternobjekt.')
            if kind == 'Signal':
                direct_binding = (item.get('configuration') or {}).get('direct_signal_binding')
                if bool(item.get('message_id')) == bool(direct_binding):
                    raise ValueError('Signal benötigt genau eine Message oder einen DirectSignalBinding.')
                if direct_binding:
                    from ..core.models import DirectSignalBinding
                    from ...communication.technologies.catalog import DIRECT_IO_TECHNOLOGIES
                    binding = DirectSignalBinding(**direct_binding)
                    if binding.signal_type.lower() not in DIRECT_IO_TECHNOLOGIES or item.get('protocol_bindings'):
                        raise ValueError('DIRECT_IO_MESSAGE_CREATED: Direktsignal darf keine Transportbindung besitzen.')
                    port = parent('HardwareNetworkInterface', binding.physical_port_ref)
                    if str(port.get('hardware_node_id')) != str(binding.source_hardware_node_ref):
                        raise ValueError('DirectSignalBinding-Quelle passt nicht zum physischen Port.')
                    if str(port.get('technology') or '').lower() != binding.signal_type.lower():
                        raise ValueError('DirectSignalBinding-Technologie passt nicht zum physischen Port.')
                    if binding.destination_hardware_node_ref:
                        parent('HardwareNode', binding.destination_hardware_node_ref)
                    else:
                        findings.append({'severity': 'OPEN', 'code': 'DIRECT_IO_DESTINATION_UNVERIFIED',
                                         'index': index, 'object_id': identifier,
                                         'message': 'Empfänger des Direktsignals muss bestätigt werden.'})
                else:
                    affected_messages.add(str(item['message_id']))
            if kind == 'Message':
                affected_messages.add(identifier)
                logical = parent('Interface', item['interface_id'])
                from ...communication.technologies.catalog import DIRECT_IO_TECHNOLOGIES
                if str(logical.get('interface_type') or '').lower() in DIRECT_IO_TECHNOLOGIES:
                    raise ValueError('DIRECT_IO_MESSAGE_CREATED: Direkte I/O-Signale dürfen keine Message besitzen.')
                owner_ref = logical.get('hardware_node_id')
                if logical.get('function_id'):
                    owner_ref = parent('Function', logical['function_id']).get('hardware_node_id')
                owner = graph['HardwareNode'].get(str(owner_ref), {})
                from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
                technology = DEFAULT_TECHNOLOGY_REGISTRY.profile(str(logical.get('interface_type') or ''))
                if (str(owner.get('data_complexity') or '').upper() in
                    {'IMAGE', 'IMAGE_STREAM', 'AUDIO', 'AUDIO_STREAM', 'POINT_CLOUD'}
                        and not technology.get('capabilities', {}).get('supports_streams')):
                    raise ValueError('DATA_COMPLEXITY_TECHNOLOGY_MISMATCH: Streamdaten benötigen einen geeigneten Anschluss.')
                if valid_payload_bytes(logical['interface_type'], int(item.get('dlc') or 0)) != int(item.get('dlc') or 0):
                    raise ValueError('Die Nutzlast ist für diese Technologie keine gültige Framegröße.')
                if item.get('hardware_interface_id'):
                    port_id = str(item['hardware_interface_id'])
                    physical = parent('HardwareNetworkInterface', port_id)
                    hardware_id = parent('Function', logical['function_id'])['hardware_node_id'] if logical.get('function_id') else logical.get('hardware_node_id')
                    if str(physical['hardware_node_id']) != str(hardware_id) or physical['technology'] != logical['interface_type']:
                        raise ValueError('Physisches und logisches Interface benötigen dieselbe Hardware und Technologie.')
                    affected_ports.add(port_id)
                for binding in (item.get('configuration') or {}).get('physical_transmit_bindings') or []:
                    physical = parent('HardwareNetworkInterface', binding['hardware_interface_id'])
                    hardware_id = parent('Function', logical['function_id'])['hardware_node_id'] if logical.get('function_id') else logical.get('hardware_node_id')
                    if (str(physical['hardware_node_id']) != str(hardware_id)
                            or physical['technology'] != logical['interface_type']
                            or not binding.get('network_id') or str(physical.get('network_ref') or '') != str(binding['network_id'])):
                        raise ValueError('Zusätzliche Sendebindungen benötigen dieselbe Hardware, Technologie und ein passendes physisches Netz.')
                    affected_ports.add(str(binding['hardware_interface_id']))
                if item.get('message_id_hex'):
                    value = int(str(item['message_id_hex']), 16)
                    if not 0 <= value <= 0x1fffffff:
                        raise ValueError('Nachrichten-Identifier liegt außerhalb des gültigen Bereichs.')
                    if any(other['id'] != identifier and str(other.get('interface_id')) == str(item['interface_id']) and other.get('message_id_hex') and int(str(other['message_id_hex']), 16) == value for other in graph[kind].values()):
                        raise ValueError('Nachrichten-Identifier ist auf dem Interface bereits belegt.')
            if kind == 'HardwareNetworkInterface':
                affected_ports.add(identifier)
                if item.get('network_ref'):
                    network = declared.get(str(item['network_ref']))
                    if network is None or not _network_supports_interface(network['technology'], item['technology']):
                        raise ValueError('Netzwerk fehlt oder verwendet eine andere Technologie.')
        except (ValueError, KeyError, TypeError) as error:
            findings.append({'severity': 'ERROR', 'index': index, 'message': str(error)})
    for identifier in affected_messages:
        message = graph['Message'].get(identifier)
        if not message:
            continue
        signals = [item for item in graph['Signal'].values() if str(item.get('message_id')) == identifier]
        for report in inspect_message_signals(signals, message):
            for check in report['checks']:
                if check['severity'] in {'ERROR', 'OPEN'}:
                    findings.append({'severity': 'ERROR', 'object_id': identifier, 'message': check['text']})
    for identifier in affected_ports:
        port = graph['HardwareNetworkInterface'][identifier]
        parameters = {key: port[key] for key in ('bitrate', 'data_bitrate') if port.get(key)}
        messages = [item for item in graph['Message'].values()
            if str(item.get('hardware_interface_id')) == identifier or any(str(binding.get('hardware_interface_id')) == identifier
                for binding in (item.get('configuration') or {}).get('physical_transmit_bindings') or [])]
        frames = [(item, estimate_frame(port['technology'], int(item.get('dlc') or 0), parameters)) for item in messages]
        if any(frame.is_generic_estimate or not frame.transmission_time_available for _, frame in frames):
            findings.append({'severity': 'ERROR', 'object_id': identifier, 'code': 'CAPACITY_UNVERIFIED',
                'message': 'Interface-Auslastung nicht nachgewiesen: explizite Raten oder Übertragungsmodell fehlen.'})
            continue
        load = sum(utilization_percent(frame.transmission_time_s, float(item.get('cycle_ms') or 10)) for item, frame in frames)
        if load > float(port.get('target_load_limit') or 60):
            findings.append({'severity': 'ERROR', 'object_id': identifier, 'message': f'Interface-Auslastung {load:.2f}% überschreitet die zulässige Zielauslastung.'})
    from ..physical_ports import topology_port_findings
    for index, change in enumerate(changes):
        if change['object_type'] == 'NetworkTopology':
            findings.extend({**finding, 'index': index} for finding in topology_port_findings(
                (change.get('data') or {}).get('topology') or {},
                list(graph['HardwareNode'].values()), list(graph['HardwareNetworkInterface'].values())))
    from ..device_communication import communication_findings
    for finding in communication_findings(graph):
        key = (finding['object_type'], finding['object_id'])
        if key in touched or (key[0] == 'Message' and key[1] in affected_messages):
            findings.append({**finding, 'index': touched.get(key)})
    from ..wizard_communication import contract_findings
    for finding in contract_findings(graph):
        if (finding['kind'], finding['id']) in touched:
            findings.append(finding)
    return findings
