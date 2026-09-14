"""Capability is not a controller, channel, interface, connector or network."""
from .models import PortDecision
from ..physical_ports import technology_id


def finding(code, message, **refs):
    return {'severity': 'ERROR', 'code': code, 'message': message, **refs}


def connection_findings(graph, port, network):
    if not port: return [finding('PORT_MISSING', 'Der physische Anschluss fehlt.')]
    if not network: return [finding('NETWORK_MEMBERSHIP_INVALID', 'Das Zielnetz fehlt im kanonischen Modell.')]
    errors = []
    if technology_id(port['technology']) != technology_id(network.get('technology')):
        errors.append(finding('PORT_TECHNOLOGY_MISMATCH', 'Anschluss und Zielnetz verwenden verschiedene Technologien.'))
    if port.get('network_ref') and port['network_ref'] != network['id']:
        errors.append(finding('PORT_ALREADY_CONNECTED', 'Der Anschluss ist bereits mit einem anderen Netz verbunden.', network_ref=port['network_ref']))
    if port.get('connection_status') == 'OUTDATED':
        errors.append(finding('PORT_OUTDATED', 'Der Anschluss ist veraltet.'))
    canonical = graph.hni.get(port.get('hardware_interface_ref'))
    if canonical and (str(canonical.get('physical_port_ref')) != str(port.get('id'))
            or str(canonical.get('network_ref') or '') != str(port.get('network_ref') or '')):
        errors.append(finding('PORT_PROJECTION_MISMATCH', 'Portressource und HardwareInterface widersprechen sich.'))
    members = {p['hardware_node_ref'] for hw in graph.hardware for p in graph.find_ports(hw) if p.get('network_ref') == network['id']}
    new_member = port['hardware_node_ref'] not in members
    if new_member and (network.get('allow_new_participants') is False or network.get('expansion_allowed') is False):
        errors.append(finding('NETWORK_MEMBERSHIP_INVALID', 'Das Netz darf laut Projektvorgabe nicht erweitert werden.'))
    if new_member and network.get('max_participants') is not None and len(members) >= int(network['max_participants']):
        errors.append(finding('NETWORK_MEMBERSHIP_INVALID', 'Die Teilnehmergrenze des Netzes ist erreicht.'))
    interface = graph.hni.get(port.get('hardware_interface_ref'), {})
    for field in ('bitrate', 'data_bitrate'):
        if interface.get(field) and network.get(field) and float(interface[field]) != float(network[field]):
            errors.append(finding('PORT_NETWORK_MISMATCH', f'{field} des Anschlusses passt nicht zum Zielnetz.'))
    return errors


def inspect_port_decision(graph, hardware_ref, technology, target_network_ref):
    decision = PortDecision(hardware_node_ref=hardware_ref, technology=technology, target_network_ref=target_network_ref or '')
    if hardware_ref not in graph.hardware:
        decision.status = 'BLOCKED'; decision.findings = [finding('HARDWARE_NODE_MISSING', 'Hardware wurde im aktiven Projekt nicht gefunden.')]
        return decision.model_dump()
    ports = graph.find_ports_by_technology(hardware_ref, technology)
    network = graph.networks.get(target_network_ref) if target_network_ref else None
    if target_network_ref and network is None:
        decision.status = 'BLOCKED'
        decision.findings = [finding('NETWORK_NOT_FOUND', 'Das Zielnetz existiert im aktuellen Projekt nicht.')]
        return decision.model_dump()
    available = [p for p in ports if p.get('network_ref') == target_network_ref or not p.get('network_ref')]
    available.sort(key=lambda p: (p.get('network_ref') != target_network_ref, p['id']))
    for port in available:
        errors = connection_findings(graph, port, network) if network else []
        if not errors:
            from .commands import checked_port, ExecutionBlocked
            interface = graph.hni.get(port['hardware_interface_ref'])
            if not interface:
                errors = [finding('PORT_INTERFACE_MISSING', 'Dem physischen Anschluss fehlt sein kanonisches HardwareInterface.')]
            else:
                try:
                    checked_port(graph, interface, require_network=False)
                except ExecutionBlocked as error:
                    errors = error.findings
        if not errors:
            decision.existing_interface_ref, decision.existing_port_ref = port['hardware_interface_ref'], port['id']
            decision.controller_ref = port.get('controller_ref')
            decision.options.append({'id': 'REUSE', 'label': 'Vorhandenen Anschluss verwenden', 'port_ref': port['id']})
            decision.recommended_option = 'REUSE'
            decision.engineering_impact = 'NONE'
            return decision.model_dump()
        decision.findings.extend(errors)
    caps = [c for c in graph.find_communication_capabilities(hardware_ref) if technology_id(c.get('technology')) == technology_id(technology)]
    if not caps or not all(c.get('supported') is True for c in caps):
        decision.findings.append(finding('COMMUNICATION_CAPABILITY_MISSING', 'Die benötigte Technologie-Fähigkeit ist nicht bestätigt. Hardware-Daten oder einen bestehenden Alternativpfad wählen.'))
    controllers = [c for c in graph.find_communication_controllers(hardware_ref)
                   if technology_id(c.get('technology')) == technology_id(technology) and c.get('status', 'ACTIVE') == 'ACTIVE']
    if not controllers:
        decision.findings.append(finding('COMMUNICATION_CONTROLLER_MISSING', 'Es ist kein passender aktiver Kommunikationscontroller modelliert.'))
    occupied = [p for p in ports if p.get('network_ref') and p['network_ref'] != target_network_ref]
    if occupied:
        decision.findings.append(finding('PORT_ALREADY_CONNECTED', 'Vorhandene Anschlüsse sind mit anderen Netzen verbunden.', port_refs=[p['id'] for p in occupied]))
    else:
        decision.findings.append(finding('PORT_MISSING', 'Für das Zielnetz existiert noch kein passender physischer Anschluss.'))
    if caps and all(c.get('supported') is True for c in caps) and controllers:
        maximum = min(c.get('max_ports', 0) for c in caps)
        channel_limit = min(c.get('max_channels', 0) for c in caps)
        controller_limit = min(c.get('controller_count', 0) for c in caps)
        occupied_channels = sum(len(graph.find_port_capacity(c['id'])['used_channels']) for c in controllers)
        for controller in sorted(controllers, key=lambda c: c['id']):
            free = graph.find_free_channels(controller['id'])
            interfaces = graph.find_hardware_interfaces(hardware_ref)
            incomplete = sorted([i for i in interfaces if technology_id(i['technology']) == technology_id(technology)
                and not i.get('physical_port_ref') and i.get('network_ref') in {None, '', target_network_ref}
                and i.get('controller_ref') == controller['id'] and type(i.get('channel_index')) is int
                and 1 <= i['channel_index'] <= controller['max_channels']
                and not any(p['hardware_interface_ref'] == str(i['id']) for p in ports)
                and not any(other['id'] != i['id'] and other.get('controller_ref') == controller['id']
                    and other.get('channel_index') == i['channel_index'] for other in interfaces)], key=lambda i: str(i['id']))
            # An HNI may already own a channel while its physical connector is
            # missing. Completing that port must not reserve a second channel.
            completing = incomplete[0] if incomplete and occupied_channels <= channel_limit else None
            if len(ports) >= maximum or len(controllers) > controller_limit:
                free = []; completing = None
            elif occupied_channels >= channel_limit:
                free = []
            if completing: free = [completing['channel_index']]
            if not free: continue
            prototype = {'hardware_node_ref': hardware_ref, 'technology': technology, 'network_ref': None,
                **({'hardware_interface_ref': str(completing['id']), 'network_ref': completing.get('network_ref')} if completing else {})}
            errors = connection_findings(graph, prototype, network) if target_network_ref else []
            for capability in caps:
                rates = capability.get('supported_bitrates') or []
                if rates and network and network.get('bitrate') and float(network['bitrate']) not in map(float, rates):
                    errors.append(finding('PORT_NETWORK_MISMATCH', 'Der Controller unterstützt die Bitrate des Zielnetzes nicht.'))
            decision.findings.extend(errors)
            if not errors:
                decision.controller_ref = controller['id']; decision.available_channels = free
                free_interfaces = [i for i in graph.find_hardware_interfaces(hardware_ref)
                    if technology_id(i['technology']) == technology_id(technology) and not i.get('physical_port_ref') and not i.get('network_ref')
                    and not i.get('controller_ref') and not i.get('channel_index')]
                if len(free_interfaces) == 1: decision.existing_interface_ref = str(free_interfaces[0]['id'])
                if completing: decision.existing_interface_ref = str(completing['id'])
                decision.options.append({'id': 'CREATE_AND_CONNECT_PORT', 'label': f'{technology}-Port anlegen und mit {network.get("name", network["id"]) if network else "Zielnetz"} verbinden',
                    'controller_ref': controller['id'], 'channel_index': free[0], 'hardware_interface_ref': decision.existing_interface_ref})
                decision.recommended_option = 'CREATE_AND_CONNECT_PORT'
                break
        if not decision.available_channels:
            decision.findings.extend([finding('NO_FREE_CHANNEL', 'Es ist kein freier bestätigter Controllerkanal verfügbar.'),
                finding('HARDWARE_INTERFACE_CAPACITY_EXCEEDED', 'Die bestätigte Hardwaregrenze erlaubt keinen zusätzlichen Anschluss.')])
    if not decision.options: decision.status = 'BLOCKED'
    return decision.model_dump()
