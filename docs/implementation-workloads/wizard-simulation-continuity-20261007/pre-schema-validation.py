"""Validate the effective proposal graph, including updates, before human review."""
from backend.nis.infrastructure.persistence.repository import ENTITY_SPECS
from backend.nis.infrastructure.persistence.repository import parent_link_for_payload
from backend.nis.engineering.signals.signal_audit import inspect_message_signals
from backend.nis.engineering.signals.message_packing import valid_payload_bytes
from backend.nis.engineering.capacity.calculators import estimate_frame
from backend.nis.engineering.capacity.calculators import utilization_percent
from backend.nis.engineering.capacity.calculators import serial_evidence_missing_fields
from backend.nis.agent.tools.model import objects
from backend.nis.agent.tools.model import networks
from backend.nis.domain.device_classification import DeviceClassificationRegistry
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY


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
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    from backend.nis.engineering.scope_rules import normalize_engineering_scope_rules
    from backend.nis.engineering.scope_rules import hardware_scope_category
    from backend.nis.engineering.scope_rules import communication_system_allows_interface
    workflow_state = WorkflowStatusService(current_project_id()).get()
    raw_rules = (workflow_state.get('context') or {}).get('engineering_scope_rules')
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
                    from backend.nis.domain.core.models import DirectSignalBinding
                    from backend.nis.communication.catalog import DIRECT_IO_TECHNOLOGIES
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
                from backend.nis.communication.catalog import DIRECT_IO_TECHNOLOGIES
                if str(logical.get('interface_type') or '').lower() in DIRECT_IO_TECHNOLOGIES:
                    raise ValueError('DIRECT_IO_MESSAGE_CREATED: Direkte I/O-Signale dürfen keine Message besitzen.')
                owner_ref = logical.get('hardware_node_id')
                if logical.get('function_id'):
                    owner_ref = parent('Function', logical['function_id']).get('hardware_node_id')
                owner = graph['HardwareNode'].get(str(owner_ref), {})
                from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
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
    findings.extend(_capacity_findings(graph, affected_ports, declared, workflow_state, touched))
    affected_networks = {str(graph['HardwareNetworkInterface'][identifier].get('network_ref')) for identifier in affected_ports}
    for check in review_simulation_capacity(workflow_state, effective_model=(graph, declared)):
        if check['network_id'] in affected_networks and check['status'] in {'OVERLOAD', 'PARAMETER_CONFLICT'}:
            findings.append({'severity': 'ERROR', 'code': 'SIMULATION_CAPACITY_' + check['status'],
                'object_type': 'Network', 'object_id': check['network_id'], 'network_id': check['network_id'],
                'technology': check['technology'], 'message': check['reason'], 'hardware_evidence': False})
    from backend.nis.engineering.network.physical_ports import topology_port_findings
    for index, change in enumerate(changes):
        if change['object_type'] == 'NetworkTopology':
            findings.extend({**finding, 'index': index} for finding in topology_port_findings(
                (change.get('data') or {}).get('topology') or {},
                list(graph['HardwareNode'].values()), list(graph['HardwareNetworkInterface'].values())))
    from backend.nis.engineering.communication.device_communication import communication_findings
    for finding in communication_findings(graph):
        key = (finding['object_type'], finding['object_id'])
        if key in touched or (key[0] == 'Message' and key[1] in affected_messages):
            findings.append({**finding, 'index': touched.get(key)})
    from backend.nis.engineering.communication.wizard_communication import contract_findings
    for finding in contract_findings(graph):
        if (finding['kind'], finding['id']) in touched:
            findings.append(finding)
    return findings


def _capacity_findings(graph, affected_ports, declared, workflow_state, touched):
    """One capacity check for proposal preview and current parameter review."""
    findings = []
    messages_by_port = {}
    resolved_scopes = {}
    for message in graph['Message'].values():
        bindings = {str(message.get('hardware_interface_id'))}
        bindings.update(str(binding.get('hardware_interface_id')) for binding in
                        (message.get('configuration') or {}).get('physical_transmit_bindings') or [])
        for identifier in bindings:
            messages_by_port.setdefault(identifier, []).append(message)
    for identifier in sorted(affected_ports):
        port = graph['HardwareNetworkInterface'][identifier]
        from backend.nis.engineering.capacity.service import parameters_for_protocol, simulation_parameters_for_protocol
        from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
        from backend.nis.engineering.capacity.transmission import profile
        from backend.nis.engineering.capacity.dimensioning import transmission_contract
        confirmed = workflow_state.get('parameters') or {}
        network = declared.get(str(port.get('network_ref')), {})
        network_parameters = network if _network_supports_interface(network.get('technology'), port['technology']) else {}
        scoped = {**(network_parameters.get('configuration') or {}), **network_parameters, **(port.get('configuration') or {}), **{key: value for key, value in port.items() if value is not None}}
        import json
        scope_key = (port['technology'], port.get('network_ref'), json.dumps({key: value for key, value in scoped.items()
            if key not in {'id', 'name', 'hardware_node_id', 'network_ref', 'version', 'created_at', 'updated_at', 'target_load_limit', 'port_index'}}, sort_keys=True, default=str))
        if scope_key not in resolved_scopes:
            actual = parameters_for_protocol(port['technology'], confirmed, scoped, port.get('network_ref'), confirmed)
            resolved_scopes[scope_key] = (actual, simulation_parameters_for_protocol(port['technology'], confirmed, scoped, port.get('network_ref'), confirmed))
        parameters, scenario = resolved_scopes[scope_key]
        messages = messages_by_port.get(identifier, [])
        frames = [(item, estimate_frame(port['technology'], int(item.get('dlc') or 0), parameters)) for item in messages]
        scenario_frames = [(item, estimate_simulation_frame(port['technology'], int(item.get('dlc') or 0), scenario)) for item in messages]
        scenario_usable = bool(scenario_frames) and all(not frame.is_generic_estimate and frame.transmission_time_available for _, frame in scenario_frames)
        if frames and DEFAULT_TECHNOLOGY_REGISTRY.profile(port['technology']).get('capacity_evidence', {}).get('status') == 'NOT_APPLICABLE':
            findings.append({'severity': 'ERROR', 'object_id': identifier,
                'object_name': port.get('name'), 'code': 'DIRECT_IO_MESSAGE_CREATED',
                'message': 'Direkte I/O-Signale dürfen keine Bus-Message erzeugen. Signal direkt an den physischen Port binden; Gerätetiming getrennt prüfen.'})
            continue
        if frames and (not parameters.get('_rate_evidenced') or any(frame.is_generic_estimate or not frame.transmission_time_available for _, frame in frames)):
            technology = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(port['technology'])
            required = ['arbitration_bitrate', 'data_bitrate'] if technology.upper() == 'CAN_FD' else ['local_timing_evidence'] if technology.upper() in {'I2C', 'SPI'} else ['bitrate']
            missing = [key for key in required if not parameters.get(key)] or ['confirmed_rate_evidence_or_transmission_model']
            if technology.upper() in {'I2C', 'SPI'}:
                missing = serial_evidence_missing_fields(technology.upper(), parameters, max(int(item.get('dlc') or 0) for item in messages))
            elif (DEFAULT_TECHNOLOGY_REGISTRY.profile(technology).get('capacity_evidence') or {}).get('status') == 'MODEL_MISSING':
                missing = ['technology_specific_capacity_model']
            node = graph['HardwareNode'].get(str(port.get('hardware_node_id')), {})
            if technology.upper() in {'I2C', 'SPI'}:
                message = 'Geräte-/Transaktionsnachweis fehlt. Im Anschluss des Geräts prüfen: ' + ', '.join(missing) + '. Eine bestätigte Busfrequenz allein belegt keine Kapazität.'
            elif missing == ['technology_specific_capacity_model']:
                message = 'Für diese Technologie ist noch kein ausführbares Kapazitätsmodell registriert. Standardparameter allein ersetzen dieses Modell nicht.'
            else:
                message = 'Interface-Auslastung nicht nachgewiesen: ' + ', '.join(missing) + '. Parameter für diese Technologie prüfen und bestätigen.'
            scenario_saved = bool(scenario.get('_simulation_assumption_fields'))
            if scenario_saved and scenario_usable:
                message = 'Gespeicherte Simulationsparameter sind verwendbar. Der Geräte-/Implementierungsnachweis für diesen Anschluss fehlt; die Simulationsannahme bestätigt keine Hardware.'
                details = [item for item in parameters.get('_rate_findings', [])
                           if item.get('code') == 'TECHNOLOGY_PARAMETER_MISSING'
                           and next((field['value_role'] for field in DEFAULT_TECHNOLOGY_REGISTRY.parameter_fields(technology)
                                     if field['native_key'] == (item.get('parameter') or item['message'].split()[0])), None) in {'EVIDENCE', 'REFERENCE'}]
                missing = [item.get('parameter') or item['message'].split()[0] for item in details] or ['hardware_rate_evidence']
            else:
                details = scenario.get('_simulation_parameter_findings', []) if scenario_saved else parameters.get('_rate_findings', [])
            findings.append({'severity': 'INFO' if scenario_saved and scenario_usable else 'ERROR', 'index': touched.get(('HardwareNetworkInterface', identifier)),
                'object_id': identifier, 'object_type': 'HardwareNetworkInterface', 'object_name': port.get('name') or identifier,
                'node_name': node.get('name'), 'network_id': port.get('network_ref'), 'network_name': network.get('name') or network.get('id'),
                'technology': technology, 'missing_fields': missing, 'parameter_findings': details, 'repair_action': 'REVIEW_TECHNOLOGY_PARAMETERS',
                'code': 'CAPACITY_DEVICE_EVIDENCE_MISSING' if scenario_saved and scenario_usable else 'CAPACITY_UNVERIFIED',
                'simulation_parameters_usable': scenario_usable, 'hardware_evidence': False,
                'message': message})
            continue
        releases = [(item, frame, profile(transmission_contract(item), item.get('cycle_ms'))) for item, frame in frames]
        if any(release['errors'] for _, _, release in releases):
            findings.append({'severity': 'ERROR', 'object_id': identifier, 'object_name': port.get('name'), 'code': 'CAPACITY_TRAFFIC_UNVERIFIED',
                'message': 'Sendeabstand oder Auslöser fehlt; Übertragungsmodus prüfen.'})
            continue
        load = sum(utilization_percent(frame.transmission_time_s, release['period_ms']) for _, frame, release in releases)
        if load > float(port.get('target_load_limit') or 60):
            findings.append({'severity': 'ERROR', 'object_id': identifier, 'message': f'Interface-Auslastung {load:.2f}% überschreitet die zulässige Zielauslastung.'})
    return findings


def _parameter_review_graph(workflow_state, changes=None):
    """One effective physical model for parameter review and native sizing."""
    graph = {kind: {str(row['id']): row for row in objects(kind)}
             for kind in ('HardwareNode', 'HardwareNetworkInterface', 'Message')}
    declared = {str(row['id']): row for row in workflow_state['parameters'].get('networks', [])}
    if changes is not None:
        for change in changes:
            kind = change['object_type']
            if kind == 'Network':
                identifier = str(change.get('object_id') or (change.get('data') or {}).get('id'))
                if change['action'] == 'DELETE':
                    declared.pop(identifier, None)
                else:
                    declared[identifier] = {**declared.get(identifier, {}), **change.get('data', {}), 'id': identifier}
            if kind in graph:
                identifier = str(change.get('object_id') or '$' + change['local_ref'])
                if change['action'] == 'DELETE':
                    graph[kind].pop(identifier, None)
                else:
                    graph[kind][identifier] = {**graph[kind].get(identifier, {}), **change.get('data', {}), 'id': identifier}
    return graph, declared


def review_parameter_findings(workflow_state, changes=None, *, simulation_checks=None):
    """Review canonical ports or an explicitly selected pending proposal overlay."""
    from backend.nis.communication.catalog import PARAMETER_UI_ALIASES
    graph, declared = _parameter_review_graph(workflow_state, changes)
    findings = _capacity_findings(graph, set(graph['HardwareNetworkInterface']), declared, workflow_state, {})
    for check in simulation_checks if simulation_checks is not None else review_simulation_capacity(workflow_state, changes):
        if check['status'] == 'INVALID' and any(
                finding.get('code') == 'CAPACITY_UNVERIFIED'
                and finding.get('network_id') == check['network_id']
                and finding.get('technology') == check['technology']
                and finding.get('simulation_parameters_usable') is False
                for finding in findings):
            # The physical-port finding already carries these unresolved native
            # parameters. Keep the scenario INVALID, without counting the same
            # missing configuration a second time as a network finding.
            continue
        if check['status'] in {'OVERLOAD', 'INVALID', 'TRAFFIC_UNRESOLVED', 'PARAMETER_CONFLICT'}:
            findings.append({'severity': 'ERROR', 'code': 'SIMULATION_CAPACITY_' + check['status'],
                'object_type': 'Network', 'object_id': check['network_id'], 'network_id': check['network_id'],
                'network_name': check['network_name'], 'technology': check['technology'],
                'parameter_fields': check['parameter_fields'], 'message': check['reason'], 'hardware_evidence': False})
    for finding in findings:
        port = graph['HardwareNetworkInterface'].get(str(finding.get('object_id')), {})
        technology = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(port.get('technology') or finding.get('technology'))
        profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology)
        schema = profile.get('parameter_schema') or {}
        aliases = profile.get('parameter_aliases') or {}
        fields = list(finding.get('parameter_fields') or [])
        for detail in finding.get('parameter_findings') or []:
            for key in schema:
                import re
                if re.search(r'(?<![A-Za-z0-9_])' + re.escape(key) + r'(?![A-Za-z0-9_])', detail.get('message') or ''):
                    fields.append(PARAMETER_UI_ALIASES.get(key, key))
        for key in finding.get('missing_fields') or []:
            native = aliases.get(key, next((native for native, ui in PARAMETER_UI_ALIASES.items() if ui == key), key))
            ui = PARAMETER_UI_ALIASES.get(native, native)
            if native in schema or ui in schema:
                fields.append(ui)
            elif key == 'bitrate':
                fields.extend(PARAMETER_UI_ALIASES.get(name, name) for name, spec in schema.items()
                              if spec.get('unit') == 'bit/s' and spec.get('scope') == 'network')
        if not fields and finding.get('missing_fields') == ['confirmed_rate_evidence_or_transmission_model']:
            fields = [PARAMETER_UI_ALIASES.get(key, key) for key, spec in schema.items()
                      if spec.get('unit') == 'bit/s' and spec.get('scope') == 'network']
        finding.update(technology=technology, network_id=port.get('network_ref') or finding.get('network_id'),
                       node_name=graph['HardwareNode'].get(str(port.get('hardware_node_id')), {}).get('name'),
                       parameter_fields=list(dict.fromkeys(fields)))
    return findings


def _bus_message_groups(graph):
    """Shared media count each frame once; switched links count each TX port."""
    ports = graph['HardwareNetworkInterface']
    grouped = {}
    independent_media = {}
    for message in graph['Message'].values():
        identifiers = {str(message.get('hardware_interface_id'))}
        identifiers.update(str(binding.get('hardware_interface_id')) for binding in
                           (message.get('configuration') or {}).get('physical_transmit_bindings') or [])
        for identifier in identifiers:
            port = ports.get(identifier)
            if not port or not port.get('network_ref'):
                continue
            technology = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(port['technology'])
            if technology not in independent_media:
                independent_media[technology] = DEFAULT_TECHNOLOGY_REGISTRY.profile(
                    technology, fields=('medium_access_model',)).get('medium_access_model') == 'FULL_DUPLEX_SWITCHED'
            independent = independent_media[technology]
            key = (str(port['network_ref']), technology, identifier if independent else '')
            grouped.setdefault(key, {})[str(message['id'])] = message
    return grouped


def review_simulation_capacity(workflow_state, changes=None, *, effective_model=None):
    """Nominal capacity of the exact saved scenario; never selects a faster rate."""
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
    from backend.nis.engineering.capacity.transmission import profile
    from backend.nis.engineering.capacity.dimensioning import transmission_contract
    from backend.nis.communication.catalog import PARAMETER_UI_ALIASES
    graph, declared = effective_model or _parameter_review_graph(workflow_state, changes)
    parameters = workflow_state['parameters']
    results = []
    resolved_scopes = {}
    for (network_id, technology, port_id), messages in sorted(_bus_message_groups(graph).items()):
        network = declared.get(network_id, {})
        native_network = network if _network_supports_interface(network.get('technology'), technology) else {}
        load, reasons, fields, rates_seen, declared_conflict = 0.0, [], [], [], False
        rate_fields = [field for field in DEFAULT_TECHNOLOGY_REGISTRY.parameter_fields(technology)
                       if field.get('scope') == 'network' and field.get('unit') == 'bit/s']
        for message in messages.values():
            bound_ids = [str(message.get('hardware_interface_id')), *[str(binding.get('hardware_interface_id')) for binding in
                (message.get('configuration') or {}).get('physical_transmit_bindings') or []]]
            port = next((graph['HardwareNetworkInterface'][identifier] for identifier in bound_ids
                         if identifier in graph['HardwareNetworkInterface']
                         and str(graph['HardwareNetworkInterface'][identifier].get('network_ref')) == network_id), {})
            if port_id:
                port = graph['HardwareNetworkInterface'][port_id]
            try:
                network_facts = DEFAULT_TECHNOLOGY_REGISTRY.normalize_parameters(technology, {**(native_network.get('configuration') or {}), **native_network})
                port_facts = DEFAULT_TECHNOLOGY_REGISTRY.normalize_parameters(technology, {**(port.get('configuration') or {}), **{key: value for key, value in port.items() if value is not None}})
            except (ValueError, TypeError) as error:
                reasons.append(str(error))
                network_facts, port_facts = {}, {}
            declared_conflict |= any(field['native_key'] in port_facts and field['native_key'] in network_facts
                                     and port_facts[field['native_key']] != network_facts[field['native_key']] for field in rate_fields)
            scoped = {**(native_network.get('configuration') or {}), **native_network, **(port.get('configuration') or {}),
                      **{key: value for key, value in port.items() if value is not None}}
            import json
            scope_key = (technology, network_id, json.dumps({key: value for key, value in scoped.items()
                if key not in {'id', 'name', 'hardware_node_id', 'network_ref', 'version', 'created_at', 'updated_at', 'target_load_limit', 'port_index'}}, sort_keys=True, default=str))
            if scope_key not in resolved_scopes:
                resolved_scopes[scope_key] = simulation_parameters_for_protocol(technology, parameters, scoped, network_id, parameters)
            scenario = resolved_scopes[scope_key]
            rates_seen.append({field['key']: scenario.get(field['key'], scenario.get(field['native_key'])) for field in rate_fields})
            for finding in scenario.get('_simulation_parameter_findings', []):
                fields.append(PARAMETER_UI_ALIASES.get(finding.get('parameter') or finding['message'].split()[0], finding.get('parameter') or finding['message'].split()[0]))
                reasons.append(finding['message'])
            release = profile(transmission_contract(message), message.get('cycle_ms'))
            frame = estimate_simulation_frame(technology, int(message.get('dlc') or 0), scenario)
            if release['errors'] or not release['period_ms']:
                reasons.append('Sendeabstand oder Auslöser fehlt; Übertragungsmodus prüfen.')
            elif frame.is_generic_estimate or not frame.transmission_time_available:
                reasons.append('Das native Frame-/PHY-Modell kann die gespeicherte Simulationskonfiguration nicht berechnen.')
            else:
                load += utilization_percent(frame.transmission_time_s, release['period_ms'])
        conflict = declared_conflict or any(rates != rates_seen[0] for rates in rates_seen[1:])
        limits = [float(port.get('target_load_limit') or 60) for port in graph['HardwareNetworkInterface'].values()
                  if str(port.get('network_ref')) == network_id and (not port_id or str(port['id']) == port_id)]
        target = min([float(parameters.get('target_bus_load_percent') or 60), *limits])
        status = 'PARAMETER_CONFLICT' if conflict else 'INVALID' if reasons else 'OVERLOAD' if load > target else 'FEASIBLE_UNDER_ASSUMPTIONS'
        if conflict:
            reasons.append('Anschlüsse desselben physischen Busses haben widersprüchliche Busgeschwindigkeiten.')
            fields.extend(field['key'] for field in rate_fields)
        if status == 'OVERLOAD':
            reasons.append(f'Modellierte Buslast {load:.2f}% überschreitet die Zielauslastung {target:g}%. Geschwindigkeit, Sendeabstände und Topologie auslegen.')
            fields.extend(field['key'] for field in rate_fields)
        results.append({'network_id': network_id, 'network_name': network.get('name') or network_id,
            'technology': technology, 'port_id': port_id or None, 'message_count': len(messages),
            'status': status, 'rates': rates_seen[0] if rates_seen else {}, 'unit': 'bit/s',
            'load_percent': round(load, 6) if not reasons or status == 'OVERLOAD' else None,
            'target_load_percent': target, 'hardware_evidence': False, 'functional_timing_accepted': False,
            'parameter_fields': list(dict.fromkeys(fields)), 'reason': '; '.join(dict.fromkeys(reasons)) or 'Gespeicherte Simulationsvorgaben verwendet; Geräte-, Schedule- und funktionaler Timingnachweis bleiben getrennt.'})
    return results


def review_bus_rate_plans(workflow_state, changes=None):
    """Group shared buses once; switched Ethernet is sized per transmitting port."""
    from backend.nis.engineering.capacity.dimensioning import bus_rate_plan
    graph, declared = _parameter_review_graph(workflow_state, changes)
    parameters = workflow_state['parameters']
    grouped = _bus_message_groups(graph)
    results = []
    for (network_id, technology, port_id), messages in sorted(grouped.items()):
        network = declared.get(network_id, {})
        scoped = {**parameters, 'technology_parameters': {**(parameters.get('technology_parameters') or {})}}
        old = scoped['technology_parameters'].get(technology) or {}
        port = graph['HardwareNetworkInterface'].get(port_id, {})
        physical_values = {**(network.get('configuration') or {}), **network,
                           **(port.get('capabilities') or {}), **(port.get('configuration') or {})}
        actual = {key: value for key, value in physical_values.items() if key in DEFAULT_TECHNOLOGY_REGISTRY.parameter_keys(technology)
                  and ((network.get('parameter_provenance') or {}).get(key) or {}).get('source') in {'USER_CONFIRMED', 'EXPLICIT_USER_SPECIFICATION'}}
        scoped['technology_parameters'][technology] = {**old, 'values': {**(old.get('values') or {}), **actual}}
        result = bus_rate_plan(technology, list(messages.values()), scoped, industry=parameters.get('industry'),
                               target_load_percent=float(parameters.get('target_bus_load_percent') or 60))
        results.append({**result, 'network_id': network_id, 'network_name': network.get('name') or network_id,
                        'port_id': port_id or None, 'message_count': len(messages)})
    return results
