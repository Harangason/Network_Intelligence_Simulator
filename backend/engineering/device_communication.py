"""Minimum communication contracts shared by project review and agent validation."""
from .device_classification import DeviceClassificationRegistry

ECU_STATES = {'OFF': 0, 'INIT': 1, 'READY': 2, 'ACTIVE': 3, 'DEGRADED': 4, 'ERROR': 5}
EXECUTION_STATES = {'IDLE': 0, 'ACCEPTED': 1, 'EXECUTING': 2, 'COMPLETED': 3, 'FAILED': 4}


def actuator_command_template(node):
    """Explicit generic simulator roles only; never guess arbitrary device commands."""
    name = str(node.get('name') or '')
    if name.endswith(('Schaltausgang', 'SchaltausgangActuator')):
        return {'length_bits': 1, 'data_type': 'boolean', 'unit': 'code', 'factor': 1,
                'min_value': 0, 'max_value': 1, 'semantic': {'semantic_type': 'BOOLEAN', 'meaning': 'Angeforderter Schaltzustand'},
                'data': {'enum_values': {'OFF': 0, 'ON': 1}, 'default_value': 'OFF'}}
    if name.endswith(('Stellglied', 'StellgliedActuator')):
        return {'length_bits': 10, 'data_type': 'unsigned', 'unit': '%', 'factor': 0.1,
                'min_value': 0, 'max_value': 100, 'semantic': {'semantic_type': 'NUMERIC', 'meaning': 'Angeforderte relative Stellposition'},
                'data': {'minimum': 0, 'maximum': 100, 'resolution': 0.1}}
    return None


def complete_new_actuator_messages(changes, existing, command_definitions=None):
    """Complete new generic simulation templates; existing definitions are immutable here."""
    graph = {kind: {str(row['id']): row for row in rows} for kind, rows in existing.items()}
    for change in changes:
        if change.get('action', 'CREATE') == 'CREATE' and change['object_type'] in graph:
            key = '$' + change['local_ref']
            graph[change['object_type']][key] = {**change['data'], 'id': key}
    for change in list(changes):
        if change['object_type'] != 'Message' or change.get('action', 'CREATE') != 'CREATE':
            continue
        message = change['data']
        ref = '$' + change['local_ref']
        transport = (message.get('configuration') or {}).get('transport_unit') or {}
        command = (transport.get('provenance') or {}).get('generator') == 'wizard-local-actuator-command'
        owner = graph['HardwareNode'].get(str(transport.get('producer_ref')), {})
        current = [s for s in graph['Signal'].values() if str(s.get('message_id')) == ref]
        offset = max((int(s.get('start_bit') or 0) + int(s.get('length_bits') or 0) for s in current), default=0)
        candidates = []
        if command and not current:
            for target in transport.get('consumer_refs') or []:
                actuator = graph['HardwareNode'].get(str(target), {})
                template = (command_definitions or {}).get(actuator.get('name')) or actuator_command_template(actuator)
                if template:
                    candidates.append({'name': actuator['name'] + 'Sollwert', **template})
        elif owner.get('device_type') == 'ActuatorController' and actuator_command_template(owner):
            candidates.append({'name': owner['name'] + 'Ausfuehrung', 'length_bits': 3, 'data_type': 'unsigned',
                'factor': 1, 'unit': 'code', 'min_value': 0, 'max_value': 4,
                'semantic': {'semantic_type': 'STATE', 'meaning': 'Ausführung des angeforderten Befehls'},
                'data': {'enum_values': EXECUTION_STATES, 'default_value': 'IDLE', 'invalid_values': [7], 'reserved_values': [5, 6]}})
        if not command and int(owner.get('device_class') or 0) >= 2 and not any(str(s.get('name', '')).endswith(('Status', 'State')) for s in current):
            candidates.append({'name': owner['name'] + 'Status', 'length_bits': 4, 'data_type': 'unsigned',
                'factor': 1, 'unit': 'code', 'min_value': 0, 'max_value': 15,
                'semantic': {'semantic_type': 'STATE', 'meaning': 'Betriebszustand'},
                'data': {'enum_values': ECU_STATES, 'default_value': 'OFF', 'invalid_values': [15], 'reserved_values': list(range(6, 15))}})
        for candidate in candidates:
            if any(s.get('name') == candidate['name'] for s in current):
                continue
            changes.append({'object_type': 'Signal', 'local_ref': f'communication-{len(changes)}', 'data': {
                **candidate, 'message_id': ref, 'start_bit': offset, 'byte_order': 'little_endian', 'offset_value': 0,
                'configuration': {'generation_role': 'DEVICE_STATUS' if candidate['name'].endswith('Status') else 'COMMAND' if command else 'EXECUTION_FEEDBACK',
                    'template': 'canonical-device-status-v1' if candidate['name'].endswith('Status') else 'generic-simulation-actuator-v1', 'requires_hardware_adaptation': True}}})
            offset += candidate['length_bits']
        if candidates:
            from .message_packing import valid_payload_bytes
            required = max(int(message.get('dlc') or 0), (offset + 7) // 8)
            message['dlc'] = valid_payload_bytes(str((message.get('configuration') or {}).get('technology_binding', {}).get('technology_id') or 'CAN_FD'), required)
            if message['dlc'] is None:
                raise ValueError(f"{message['name']}: Befehl und Rückmeldung müssen in passende Nachrichten aufgeteilt werden.")
            transport['payload_size'] = message['dlc']


def communication_findings(graph):
    findings = []
    nodes = graph.get('HardwareNode', {})
    functions = graph.get('Function', {})
    interfaces = graph.get('Interface', {})
    messages = graph.get('Message', {})
    signals = graph.get('Signal', {})
    def owner(message):
        interface = interfaces.get(str(message.get('interface_id')), {})
        return str(interface.get('hardware_node_id') or functions.get(str(interface.get('function_id')), {}).get('hardware_node_id') or '')
    def add(code, kind, item, message):
        findings.append({'code': code, 'object_type': kind, 'object_id': str(item['id']), 'severity': 'ERROR', 'message': message})
    for node_id, node in nodes.items():
        if node.get('lifecycle_state') in ('deprecated', 'superseded'):
            continue
        profile = DeviceClassificationRegistry().resolve_profile(name=node.get('name', ''), device_type=node.get('device_type', 'ECU'), device_class=node.get('device_class'))
        outgoing = [m for m in messages.values() if owner(m) == node_id and m.get('direction') != 'rx']
        output = [s for s in signals.values() if any(str(s.get('message_id')) == str(m['id']) for m in outgoing)]
        if profile.requires_function_model and not any(str(f.get('hardware_node_id')) == node_id for f in functions.values()):
            add('FUNCTION_MISSING', 'HardwareNode', node, f"{node['name']}: Klasse {profile.device_class} benötigt eine Funktion.")
        if profile.requires_status_model and not any((s.get('semantic') or {}).get('meaning') == 'Betriebszustand' or str(s.get('name', '')).lower().endswith(('status', 'state')) for s in output):
            add('DEVICE_STATUS_MISSING', 'HardwareNode', node, f"{node['name']}: Betriebsstatus fehlt.")
        if node.get('device_type') == 'SensorController' and not output:
            add('SENSOR_VALUE_MISSING', 'HardwareNode', node, f"{node['name']}: Messwert oder funktionsbezogenes Signal fehlt.")
        if node.get('device_type') == 'ActuatorController' and not output:
            add('ACTUATOR_FEEDBACK_MISSING', 'HardwareNode', node, f"{node['name']}: Istwert bzw. Ausführungsrückmeldung fehlt.")
    for message_id, message in messages.items():
        provenance = (((message.get('configuration') or {}).get('transport_unit') or {}).get('provenance') or {})
        if provenance.get('generator') != 'wizard-local-actuator-command':
            continue
        command_signals = [s for s in signals.values() if str(s.get('message_id')) == message_id]
        if not command_signals:
            add('COMMAND_SIGNALS_MISSING', 'Message', message, f"{message['name']}: Befehlssignal, Codierung und Wertebereich festlegen; passende Istwert-/Ausführungsrückmeldung am Aktor prüfen.")
    return findings
