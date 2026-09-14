"""One explicit communication plan for model review and route generation.

Device ownership defines measurements, commands and feedback. Controller status
has a declared monitoring destination, not an incidental HMI preview selection.
All defaults remain part of the model proposal and require its review.
"""
from copy import deepcopy
import json
import re

VERSION = 1
KINDS = ('HardwareNode', 'Function', 'Interface', 'HardwareNetworkInterface', 'Message', 'Signal')


def hmi_message_choices(clusters, graph):
    """Resolve explicit display switches to whole canonical messages, never guessed payloads."""
    names = {str(node['name']).casefold(): str(key) for key, node in graph['HardwareNode'].items()}
    signals = {}
    for signal in graph.get('Signal', {}).values():
        signals.setdefault(str(signal.get('message_id')), set()).update(
            str(signal[field]).casefold() for field in ('name', 'display_name', 'signal_name') if signal.get(field))
    choices = {}
    for cluster in clusters:
        for route in cluster.get('hmi_routes') or []:
            if 'excluded_signals' not in route:
                continue  # Older reviewed requests keep their original meaning.
            enabled = {str(name).casefold() for name in route.get('signals') or []}
            disabled = {str(name).casefold() for name in route.get('excluded_signals') or []}
            if enabled & disabled:
                raise ValueError('HMI-Auswahl enthält widersprüchliche Ein/Aus-Werte.')
            source, target = names.get(str(route.get('source', '')).casefold()), names.get(str(route.get('target', '')).casefold())
            if not source or not target:
                if enabled:
                    raise ValueError(f'HMI-Auswahl: {route.get("source")} → {route.get("target")} fehlt im Modell.')
                continue
            found = set()
            for key, message in graph['Message'].items():
                interface = graph['Interface'].get(str(message.get('interface_id')), {})
                function = graph.get('Function', {}).get(str(interface.get('function_id')), {})
                producer = str(interface.get('hardware_node_id') or function.get('hardware_node_id') or '')
                if producer != source:
                    continue
                payload = signals.get(str(key), set())
                selected = enabled & payload
                found.update(selected)
                if selected and disabled & payload:
                    raise ValueError(f'{message["name"]}: Ein- und ausgeschaltete HMI-Werte teilen eine Nachricht. Für die Auswahl ist eine eigene Nachricht mit expliziter Kodierung erforderlich.')
                choice = bool(selected)
                pair = (str(key), target)
                if pair in choices and choices[pair] != choice:
                    raise ValueError(f'{message["name"]}: widersprüchliche HMI-Auswahl für {route.get("target")}.')
                choices[pair] = choice
            if enabled - found:
                raise ValueError('HMI-Auswahl: eingeschaltete Signale fehlen am Quell-Controller: ' + ', '.join(sorted(enabled - found)))
    return choices


def communication_plan(prompt, graph):
    match = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])', prompt, re.M)
    if not match:
        return {}
    clusters = json.loads(match.group(1))
    nodes = graph['HardwareNode']
    hmi_choices = hmi_message_choices(clusters, graph)
    names = {str(n['name']).casefold(): key for key, n in nodes.items()}
    owners, displays = {}, {}
    for cluster in clusters:
        for controller in cluster.get('controllers') or []:
            owner = names.get(str(controller.get('ecu', '')).casefold())
            for endpoint in [*(controller.get('sensors') or []), *(controller.get('actuators') or [])]:
                identifier = names.get(str(endpoint).casefold())
                if not identifier or not owner:
                    raise ValueError(f'Kommunikationsplanung: Zuordnung {endpoint} → {controller.get("ecu")} fehlt.')
                if identifier in owners and owners[identifier] != owner:
                    raise ValueError(f'Kommunikationsplanung: {endpoint} besitzt mehrere Controller.')
                owners[identifier] = owner
        for route in [*(route for route in cluster.get('hmi_routes') or [] if 'excluded_signals' not in route), *(cluster.get('functional_routes') or [])]:
            source, target = names.get(str(route.get('source', '')).casefold()), names.get(str(route.get('target', '')).casefold())
            if source and target and source != target:
                displays.setdefault(source, set()).add(target)
    # Stable, visible simulation default. Prefer a dedicated diagnostic device.
    monitors = sorted(nodes, key=lambda key: (
        0 if str(nodes[key]['name']).casefold() in {'diagnose', 'diagnostics'} else
        1 if nodes[key].get('device_type') == 'Gateway' else 2,
        str(nodes[key]['name']).casefold(),
    ))
    controller_types = {'ECU', 'Gateway', 'PLC', 'IndustrialPC', 'DomainController'}
    monitors = [key for key in monitors if nodes[key].get('device_type') in controller_types]
    result = {}
    for identifier, message in graph['Message'].items():
        interface = graph['Interface'].get(str(message.get('interface_id')), {})
        function = graph['Function'].get(str(interface.get('function_id')), {})
        producer = str(interface.get('hardware_node_id') or function.get('hardware_node_id') or '')
        if producer not in nodes:
            raise ValueError(f'Kommunikationsplanung: Producer für {message["name"]} fehlt.')
        config = deepcopy(message.get('configuration') or {})
        transport = config.setdefault('transport_unit', {})
        targets = set(map(str, transport.get('consumer_refs') or []))
        if targets:
            role, basis = 'EXPLICIT', 'Bestehende explizite Empfängerzuordnung'
        elif producer in owners:
            targets.add(owners[producer])
            role = 'FEEDBACK' if nodes[producer].get('device_type') == 'ActuatorController' else 'MEASUREMENT'
            basis = 'Bestätigte Gerätezuordnung im Systemcluster'
        elif nodes[producer].get('device_type') in controller_types:
            target = next((key for key in monitors if key != producer), None)
            if target:
                targets.add(target)
            targets.update(displays.get(producer, set()))
            # Approved automotive functional dependency: exhaust treatment
            # reports to engine control as well as diagnostic/display users.
            if str(nodes[producer]['name']).casefold() == 'abgasnachbehandlung' and 'motorsteuerung' in names:
                targets.add(names['motorsteuerung'])
            role, basis = 'DEVICE_STATUS', 'Statusüberwachung: Diagnose, sonst Gateway, sonst Controller'
        else:
            role, basis = 'UNRESOLVED', 'Kein bestätigter Empfänger'
        selected_displays = []
        for (message_id, target), enabled in hmi_choices.items():
            if message_id != str(identifier):
                continue
            if enabled:
                targets.add(target)
            else:
                targets.discard(target)
            selected_displays.append({'target_ref': target, 'enabled': enabled})
        if selected_displays:
            config['hmi_routing_selection'] = selected_displays
        if producer in targets or any(key not in nodes for key in targets):
            raise ValueError(f'Kommunikationsplanung: {message["name"]} benötigt einen gültigen externen Empfänger.')
        if not targets:
            role, basis = 'UNRESOLVED', 'Status-Empfänger muss vor der Modellfreigabe ergänzt werden.'
        # Preserve the original role when a previously planned message is read.
        previous = config.get('communication_contract') or {}
        if previous.get('version') == VERSION:
            role, basis = previous['role'], previous['basis']
        transport.update(producer_ref=producer, consumer_refs=sorted(targets))
        config['communication_contract'] = {'version': VERSION, 'role': role, 'basis': basis,
            'producer_ref': producer, 'consumer_refs': sorted(targets)}
        if previous.get('scope'):
            config['communication_contract']['scope'] = previous['scope']
        result[identifier] = config
    return result


def attach_new_message_contracts(prompt, changes, existing):
    graph = {kind: {str(row['id']): row for row in existing.get(kind, [])} for kind in KINDS}
    for change in changes:
        kind = change['object_type']
        if kind in graph:
            key = str(change.get('object_id') or '$' + change['local_ref'])
            graph[kind][key] = {**graph[kind].get(key, {}), **change['data']}
    plan = communication_plan(prompt, graph)
    for change in changes:
        if change['object_type'] == 'Message' and change.get('action', 'CREATE') == 'CREATE':
            key = '$' + change['local_ref']
            if key in plan:
                change['data']['configuration'] = plan[key]


def contract_findings(graph):
    findings = []
    for key, message in graph['Message'].items():
        config = message.get('configuration') or {}
        contract = config.get('communication_contract')
        if not contract:
            continue  # Imported models use their own contracts.
        transport = config.get('transport_unit') or {}
        consumers = transport.get('consumer_refs') or []
        if (not consumers or any(str(ref) not in graph['HardwareNode'] for ref in consumers)
                or transport.get('producer_ref') in consumers
                or sorted(consumers) != sorted(contract.get('consumer_refs') or [])):
            findings.append({'kind': 'Message', 'id': key, 'code': 'COMMUNICATION_CONTRACT_INVALID',
                'message': f'{message["name"]}: Empfänger fehlen oder widersprechen dem Kommunikationsplan.', 'severity': 'ERROR'})
    return findings
