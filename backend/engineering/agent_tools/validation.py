"""Validate the effective proposal graph, including updates, before human review."""
from ..repository import ENTITY_SPECS, parent_link_for_payload
from ..signal_audit import inspect_message_signals
from ..message_packing import valid_payload_bytes
from ..capacity.calculators import estimate_frame, utilization_percent
from .model import objects, networks


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
                affected_messages.add(str(item['message_id']))
            if kind == 'Message':
                affected_messages.add(identifier)
                logical = parent('Interface', item['interface_id'])
                if valid_payload_bytes(logical['interface_type'], int(item.get('dlc') or 0)) != int(item.get('dlc') or 0):
                    raise ValueError('Die Nutzlast ist für diese Technologie keine gültige Framegröße.')
                if item.get('hardware_interface_id'):
                    port_id = str(item['hardware_interface_id'])
                    physical = parent('HardwareNetworkInterface', port_id)
                    hardware_id = parent('Function', logical['function_id'])['hardware_node_id'] if logical.get('function_id') else logical.get('hardware_node_id')
                    if str(physical['hardware_node_id']) != str(hardware_id) or physical['technology'] != logical['interface_type']:
                        raise ValueError('Physisches und logisches Interface benötigen dieselbe Hardware und Technologie.')
                    affected_ports.add(port_id)
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
                    if network is None or network['technology'] != item['technology']:
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
        load = sum(utilization_percent(estimate_frame(port['technology'], int(item.get('dlc') or 0), parameters).transmission_time_s, float(item.get('cycle_ms') or 10)) for item in graph['Message'].values() if str(item.get('hardware_interface_id')) == identifier)
        if load > float(port.get('target_load_limit') or 60):
            findings.append({'severity': 'ERROR', 'object_id': identifier, 'message': f'Interface-Auslastung {load:.2f}% überschreitet die zulässige Zielauslastung.'})
    return findings
