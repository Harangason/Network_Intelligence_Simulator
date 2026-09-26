"""Reviewed acquisition from explicit model contracts; no invented device protocol."""
from copy import deepcopy
import re
from uuid import uuid4, uuid5, NAMESPACE_URL

from ..project_context import current_project_id
from ..repository import ENTITY_SPECS
from ..models import EngineeringValidationError
from ..goal_execution.store import RESOURCE_MODELS
from . import model as access


TABLES = {kind: ENTITY_SPECS[kind].table for kind in
          ('HardwareNode', 'Function', 'Interface', 'HardwareNetworkInterface', 'Message', 'Signal')}


def proposed_model(changes):
    """Build an isolated prospective graph with deterministic, nonpersisted IDs."""
    from .proposal_service import _resolve
    model = access.model()
    snapshot = {'project_id': current_project_id(), 'topology': deepcopy(model['topology']),
                'parameters': deepcopy(model['parameters']), 'tables': {
                    TABLES[kind]: deepcopy(model[section]) for section, kind in access.SECTIONS.items()}}
    snapshot['tables']['engineering_routing_entries'] = deepcopy(model['routing'])
    resources = deepcopy(model['communication_resources'])
    refs = {}
    for change in changes:
        local = change['local_ref']; data = change.get('data') or {}
        if local in refs:
            raise EngineeringValidationError('Doppelte Referenz in der Abfrageplanung.')
        if change.get('action', 'CREATE') != 'CREATE':
            _validate_extension_update(change, model)
            refs[local] = change['object_id']
            continue
        refs[local] = (str(data.get('id') or data.get('connection_id'))
                       if change['object_type'] in RESOURCE_MODELS else
                       str(uuid5(NAMESPACE_URL, current_project_id() + ':acquisition-preview:' + local)))
    for change in changes:
        kind = change['object_type']; data = _resolve(deepcopy(change['data']), refs)
        identifier = refs[change['local_ref']]
        if kind in TABLES:
            rows = snapshot['tables'][TABLES[kind]]
            if change.get('action') == 'UPDATE':
                target = next(row for row in rows if str(row['id']) == identifier)
                target.update(data)
                continue
            row = {**data, 'id': identifier, 'project_id': current_project_id(), 'object_type': kind, 'version': 1}
            if kind == 'Interface' and row.get('function_id'):
                function = next((f for f in snapshot['tables'][TABLES['Function']] if str(f['id']) == row['function_id']), None)
                if function is None:
                    raise EngineeringValidationError('Die Funktion der geplanten Schnittstelle fehlt.')
                row['hardware_node_id'] = function['hardware_node_id']
            rows.append(row)
        elif kind in RESOURCE_MODELS:
            value = RESOURCE_MODELS[kind].model_validate(data).model_dump(mode='json')
            existing = resources.setdefault(kind, [])
            if any(str(row.get('id') or row.get('connection_id')) == identifier for row in existing):
                raise EngineeringValidationError('Kommunikationsressource bereits vorhanden.')
            existing.append(value)
        elif kind == 'NetworkTopology':
            snapshot['topology'] = data['topology']
        elif kind == 'RoutingEntry':
            snapshot['tables']['engineering_routing_entries'].append({**data, 'id': identifier,
                'project_id': current_project_id(), 'route_code': 'preview-' + change['local_ref'], 'status': 'DRAFT'})
        else:
            raise EngineeringValidationError('Nicht unterstützte Änderung im Abfragevorschlag: ' + kind)
    return snapshot, resources, refs


def validate_preview(changes):
    from ..goal_execution.graph import ModelGraphService
    from ..goal_execution.commands import checked_port
    snapshot, resources, refs = proposed_model(changes)
    effective = {section: snapshot['tables'][TABLES[kind]] for section, kind in access.SECTIONS.items()}
    effective.update(parameters=snapshot['parameters'], topology=snapshot['topology'])
    graph = ModelGraphService(effective, resources)
    for change in changes:
        if change['object_type'] == 'HardwareNetworkInterface':
            checked_port(graph, graph.hni[refs[change['local_ref']]])
    from ..capacity.transmission import bus_request_pairs
    streams = []
    for message in graph.messages.values():
        contract = ((message.get('configuration') or {}).get('communication_contract') or {})
        interface = graph.interfaces.get(str(message.get('interface_id')), {})
        port = graph.hni.get(str(message.get('hardware_interface_id')), {})
        streams.append({'message_id': str(message['id']), 'producer': str(interface.get('hardware_node_id') or ''),
            'consumers': [str(graph.functions[value]['hardware_node_id']) if value in graph.functions else value
                          for value in contract.get('consumer_refs') or []],
            'network_id': port.get('network_ref'), 'protocol': port.get('technology'),
            'cycle_ms': message.get('cycle_ms'), 'transmission_contract': contract.get('transmission') or {}})
    try:
        bus_request_pairs(streams)
    except ValueError as error:
        raise EngineeringValidationError(str(error)) from error
    return snapshot, refs


def _gap(code, message, **evidence):
    return {'code': code, 'severity': 'OPEN', 'message': message, 'evidence': evidence}


def _validate_extension_update(change, model):
    """A continuation may only append paired source references to its function."""
    if change.get('action') != 'UPDATE' or change.get('object_type') != 'Function' or set(change.get('data') or {}) != {'configuration'}:
        raise EngineeringValidationError('Nur die Quellenliste einer bestehenden Abfragefunktion darf erweitert werden.')
    fn = next((f for f in model['functions'] if str(f['id']) == change.get('object_id')), None)
    hardware = next((h for h in model['hardware'] if fn and str(h['id']) == str(fn['hardware_node_id'])), {})
    old = (fn or {}).get('configuration') or {}; new = change['data']['configuration']
    fields = {'actuator_refs', 'source_signal_refs'}
    if (not hardware.get('identity', {}).get('periodic_acquisition_requester') or old.get('acquisition_mode') != 'REQUEST_RESPONSE'
            or not isinstance(new, dict) or set(new) != set(old)
            or any(new[key] != value for key, value in old.items() if key not in fields)):
        raise EngineeringValidationError('Die bestehende Abfragekonfiguration darf nicht ersetzt werden.')
    additions = []
    for key in fields:
        previous = old.get(key); values = new.get(key)
        if (not isinstance(previous, list) or not previous or not isinstance(values, list)
                or values[:len(previous)] != previous or len(values) <= len(previous)
                or len(set(values)) != len(values)):
            raise EngineeringValidationError('Die Abfrageerweiterung muss vorhandene Quellen erhalten und neue eindeutig ergänzen.')
        additions.append(len(values) - len(previous))
    if len(set(additions)) != 1:
        raise EngineeringValidationError('Aktoren und Positionsquellen müssen paarweise erweitert werden.')
    signals = {str(s['id']): s for s in model['signals']}
    messages = {str(m['id']): m for m in model['messages']}
    interfaces = {str(i['id']): i for i in model['interfaces']}
    for actor, source in zip(new['actuator_refs'], new['source_signal_refs'], strict=True):
        signal = signals.get(source) or {}; message = messages.get(str(signal.get('message_id'))) or {}
        interface = interfaces.get(str(message.get('interface_id'))) or {}
        if signal.get('configuration', {}).get('physical_quantity') != 'position' or str(interface.get('hardware_node_id')) != actor:
            raise EngineeringValidationError('Die Positionsquelle gehört nicht zum angegebenen Aktor.')


def _continuation(graph, state, goal, period):
    """Resolve durable completion to current canonical identities, never prose."""
    from . import proposal_service
    from ..routing.validation import RoutingValidator
    prior = state.get('engineering_workloads', {}).get(goal.get('follow_up_of')) or {}
    result = prior.get('result') or {}; acquisition = result.get('periodic_acquisition') or {}
    if (prior.get('project_id') != current_project_id() or prior.get('status') != 'COMPLETED'
            or prior.get('goal', {}).get('goal_type') != 'PERIODIC_ACQUISITION'
            or result.get('completion', {}).get('completed') is not True or acquisition.get('period_ms') != period
            or not result.get('proposal_id')):
        raise EngineeringValidationError('Für die Fortsetzung fehlt eine abgeschlossene Abfrage im aktuellen Projekt.')
    proposal = proposal_service.get(result['proposal_id'])
    if proposal.get('status') != 'APPLIED' or proposal.get('workload_id') != prior.get('workload_id'):
        raise EngineeringValidationError('Der vorherige Abfragevorschlag ist nicht übernommen.')
    requester = graph.hardware.get(acquisition.get('requester_id')) or {}
    fn = graph.functions.get(acquisition.get('function_id')) or {}
    config = fn.get('configuration') or {}
    if (not requester.get('identity', {}).get('periodic_acquisition_requester')
            or str(fn.get('hardware_node_id')) != acquisition.get('requester_id')
            or config.get('acquisition_mode') != 'REQUEST_RESPONSE' or config.get('cycle_time_ms') != period
            or config.get('actuator_refs') != acquisition.get('actuator_ids')
            or config.get('source_signal_refs') != acquisition.get('source_signal_ids')):
        raise EngineeringValidationError('Die vorhandene Abfrage wurde geändert oder ist nicht vollständig vorhanden.')
    interfaces = [i for i in graph.interfaces.values() if str(i.get('function_id')) == str(fn['id'])]
    ports = [p for p in graph.hni.values() if str(p.get('hardware_node_id')) == str(requester['id'])]
    if len(interfaces) != 1 or len(ports) != 1:
        raise EngineeringValidationError('Der Anschluss der vorhandenen Abfrage ist nicht eindeutig.')
    from ..goal_execution.commands import checked_port
    checked_port(graph, ports[0])
    routes = {str(r['id']): r for r in graph.model['routing']}
    if not acquisition.get('route_ids'):
        raise EngineeringValidationError('Die vorhandenen Abfragewege fehlen.')
    for identifier in acquisition['route_ids']:
        route = routes.get(identifier)
        if not route or route.get('approval_state') != 'APPROVED' or not RoutingValidator().validate(route, exclude_route_id=identifier)['valid']:
            raise EngineeringValidationError('Ein vorhandener Abfrageweg ist nicht mehr gültig.')
    for actor, source in zip(acquisition['actuator_ids'], acquisition['source_signal_ids'], strict=True):
        signal = graph.signals.get(source) or {}; message = graph.messages.get(str(signal.get('message_id'))) or {}
        interface = graph.interfaces.get(str(message.get('interface_id'))) or {}
        replies = [m for m in graph.messages.values() if (m.get('configuration') or {}).get('generation_role') == 'ACQUISITION_RESPONSE'
                   and m['configuration'].get('acquisition_exchange', {}).get('source_signal_ref') == source
                   and m['configuration'].get('communication_contract', {}).get('consumer_refs') == [str(requester['id'])]]
        if str(interface.get('hardware_node_id')) != actor or len(replies) != 1 or replies[0].get('cycle_ms') != period:
            raise EngineeringValidationError('Die vorhandene Positionsabfrage stimmt nicht mehr mit ihren Quellen überein.')
        request = graph.messages.get(replies[0]['configuration']['communication_contract']['transmission'].get('request_message_ref')) or {}
        if request.get('interface_id') != interfaces[0]['id'] or request.get('cycle_ms') != period:
            raise EngineeringValidationError('Die vorhandene zyklische Positionsanfrage fehlt oder wurde geändert.')
        contract = message.get('configuration', {}).get('request_response_acquisition') or {}
        response_signals = [s for s in graph.signals.values() if str(s.get('message_id')) == str(replies[0]['id'])]
        encoding = ('start_bit', 'length_bits', 'byte_order', 'data_type', 'unit', 'factor', 'offset_value', 'min_value', 'max_value', 'semantic', 'data')
        if (contract.get('confirmed') is not True or len(response_signals) != 1
                or any(response_signals[0].get(k) != signal.get(k) for k in encoding)
                or int(str(contract.get('request_frame_id')), 16) != int(str(request.get('message_id_hex')), 16)
                or int(str(contract.get('response_frame_id')), 16) != int(str(replies[0].get('message_id_hex')), 16)):
            raise EngineeringValidationError('Kodierung oder bestätigter Gerätevertrag der bestehenden Abfrage wurde geändert.')
    return {**deepcopy(acquisition), 'prior_workload_id': prior['workload_id'], 'logical_id': str(interfaces[0]['id']),
            'port_id': str(ports[0]['id']), 'configuration': deepcopy(config)}


def prepare(arguments):
    """Only complete, explicitly modeled CAN-FD request/response definitions apply.

    Other transports keep their existing partial draft or explicit data gaps;
    an application protocol must never become a CAN-FD frame implicitly.
    """
    from . import conversation, proposal_service
    from ..goal_execution.graph import ModelGraphService
    from ..goal_execution.commands import checked_port
    from ..physical_ports import technology_id
    graph = ModelGraphService.load()
    templates = [h for h in graph.hardware.values()
                 if isinstance((h.get('identity') or {}).get('acquisition_controller_template'), dict)
                 and h['identity']['acquisition_controller_template'].get('confirmed') is True]
    if not templates:
        return {'supported': False, 'findings': [_gap('ACQUISITION_TEMPLATE_MISSING',
            'Für die vollständige Abfrage fehlt eine bestätigte Controller- und Kommunikationsvorlage.')]}
    state = conversation.read()
    work = state.get('engineering_workloads', {}).get(arguments['workload_id']) or {}
    goal = work.get('goal') or {}
    if (work.get('project_id') != current_project_id() or goal.get('goal_type') != 'PERIODIC_ACQUISITION'
            or goal.get('goal_id') != arguments['workload_id']
            or state.get('active_engineering_workload_id') != arguments['workload_id']):
        raise EngineeringValidationError('Die Abfrage benötigt den aktuellen gespeicherten Engineering-Auftrag.')
    periods = [p.get('seconds') for p in goal.get('timing_constraints', []) if p.get('kind') == 'PERIOD']
    if len(periods) != 1 or type(periods[0]) not in (int, float) or not 0 < periods[0] <= 3600:
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_PERIOD_REQUIRED', 'Abfrageintervall ausdrücklich festlegen.')]}
    followup = bool(re.fullmatch(r'\s*(?:bitte\s+)?(?:mach|mache)\s+das\s+auch\s+f(?:ü|ue)r\s+die\s+(?:anderen|restlichen)\s+(?:aktoren|stellglieder)[.!]?\s*', goal.get('original_request', ''), re.IGNORECASE))
    continuation = None
    if goal.get('follow_up_of'):
        if not followup:
            return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_CONTINUATION_AMBIGUOUS', 'Den Umfang der Abfragefortsetzung eindeutig bestätigen.')]}
        try:
            continuation = _continuation(graph, state, goal, periods[0] * 1000)
        except (ValueError, KeyError, LookupError) as error:
            return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_CONTEXT_INVALID', str(error))]}
    elif followup:
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_CONTEXT_MISSING', 'Eine abgeschlossene Abfrage als Kontext auswählen.')]}
    if not continuation and not any(word in goal.get('original_request', '').casefold() for word in ('stellgliedposition', 'aktorposition')):
        return {'supported': False}
    intent = re.fullmatch(r'\s*(?:bitte\s+)?(?:lege|erstelle)\s+eine\s+ecu\s+(?:an,?\s*)?die\s+(?:mir\s+)?die\s+'
                         r'(?:stellgliedpositionen|aktorpositionen)\s+im\s+system\s+alle\s+(?P<seconds>\d+(?:[.,]\d+)?)\s+'
                         r'sekunden\s+abfragt[.!]?\s*', goal.get('original_request', ''), re.IGNORECASE)
    if not continuation and (not intent or float(intent['seconds'].replace(',', '.')) != periods[0]):
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_INTENT_AMBIGUOUS',
            'Der vollständige Abfrageauftrag muss eindeutig und ohne zusätzliche oder verneinte Änderungen formuliert sein.')]}
    if len(templates) != 1:
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_TEMPLATE_AMBIGUOUS', 'Mehrere Controller-Vorlagen erfordern eine Auswahl.')]}
    template = templates[0]; settings = template['identity']['acquisition_controller_template']
    ports = [p for p in graph.hni.values() if str(p['hardware_node_id']) == str(template['id'])
             and str(p['id']) == settings.get('hardware_interface_ref')]
    if len(ports) != 1 or technology_id(ports[0]['technology']) != 'can_fd':
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_TRANSPORT_UNSUPPORTED',
            'Die vollständige Abfrageplanung unterstützt derzeit explizite CAN-FD-Anfrage/Antwort-Verträge; die gewählte Technologie wird nicht ersetzt.')]}
    template_port = ports[0]; checked_port(graph, template_port)
    if continuation and graph.hni[continuation['port_id']].get('network_ref') != template_port['network_ref']:
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_CONTEXT_INVALID', 'Die bestehende Abfrage gehört nicht mehr zum bestätigten Netz.')]}
    cycle = settings.get('status_cycle_ms'); consumer = settings.get('status_consumer_ref')
    if type(cycle) not in (int, float) or not 0 < cycle <= 3600000 or consumer not in graph.functions:
        return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_STATUS_REQUIRED', 'Statuszyklus und Status-Empfänger der neuen ECU sind nicht bestätigt.')]}
    actuator_ids = {key for key, h in graph.hardware.items() if h.get('device_type') == 'ActuatorController'
                    and h.get('lifecycle_state') not in {'deprecated', 'superseded'}}
    definitions, gaps = [], []
    for actuator_id in sorted(actuator_ids):
        if continuation and actuator_id in continuation['actuator_ids']:
            continue
        sources = []
        for signal in graph.signals.values():
            if (signal.get('configuration') or {}).get('physical_quantity') != 'position':
                continue
            message = graph.messages.get(str(signal.get('message_id')), {})
            interface = graph.interfaces.get(str(message.get('interface_id')), {})
            owner = str(interface.get('hardware_node_id') or graph.functions.get(str(interface.get('function_id')), {}).get('hardware_node_id') or '')
            if owner == actuator_id:
                sources.append((signal, message, interface))
        if len(sources) != 1:
            gaps.append(_gap('ACQUISITION_POSITION_UNRESOLVED', 'Genau eine bestätigte Positionsdatenquelle je Stellglied auswählen.', actuator_id=actuator_id)); continue
        signal, message, interface = sources[0]
        contract = (message.get('configuration') or {}).get('request_response_acquisition') or {}
        if not isinstance(contract, dict):
            gaps.append(_gap('ACQUISITION_CONTRACT_MISSING', 'Der bestätigte Anfrage-Antwort-Vertrag ist ungültig.', actuator_id=actuator_id)); continue
        port = graph.hni.get(str(message.get('hardware_interface_id')))
        if (contract.get('confirmed') is not True or not isinstance(contract.get('request_signal'), dict)
                or not contract.get('request_frame_id') or not contract.get('response_frame_id')
                or not isinstance(contract.get('functional_requirements'), dict)
                or contract['functional_requirements'].get('confirmed') is not True
                or type(contract.get('response_processing_ms')) not in (int, float)
                or not 0 <= contract['response_processing_ms'] < periods[0] * 1000
                or type(contract.get('response_minimum_interval_ms')) not in (int, float)
                or not 0 < contract['response_minimum_interval_ms'] <= periods[0] * 1000
                or not port or port.get('network_ref') != template_port['network_ref']
                or technology_id(port['technology']) != 'can_fd'
                or technology_id(interface.get('interface_type')) != 'can_fd'):
            gaps.append(_gap('ACQUISITION_CONTRACT_MISSING', 'Bestätigte Anfragekodierung, Antwortkennung, Zeitbedingungen und gemeinsame CAN-FD-Anbindung fehlen.', actuator_id=actuator_id, signal_id=signal['id'])); continue
        checked_port(graph, port, role='source')
        definitions.append({'actuator_id': actuator_id, 'signal': signal, 'message': message,
                            'interface': interface, 'port': port, 'contract': contract})
    if not definitions:
        if continuation and not gaps:
            return {'supported': True, 'proposal': None, 'findings': [_gap('ACQUISITION_ALREADY_COVERED',
                'Alle vorhandenen Aktoren sind bereits in dieser Abfrage enthalten. Es werden keine doppelten Konfigurationen angelegt.')]}
        return {'supported': True, 'proposal': None, 'findings': gaps or [_gap('ACQUISITION_NO_ACTUATORS', 'Keine Stellglieder im aktuellen Projekt gefunden.')]}
    changes = build_changes(graph, template, settings, template_port, definitions, periods[0] * 1000, goal, continuation=continuation)
    proposal = proposal_service.create('PERIODIC_ACQUISITION', changes, goal['original_request'],
        workload_id=goal['goal_id'], assumptions=[g['message'] for g in gaps],
        evidence=[{'source': 'explicit_periodic_acquisition', 'engineering_goal_id': goal['goal_id'],
            'source_revision': access.model_revision(), 'controller_template_ref': str(template['id']),
            'actuator_ids': sorted(actuator_ids), 'resolved_actuator_ids': [d['actuator_id'] for d in definitions],
            'source_signal_ids': [str(d['signal']['id']) for d in definitions], 'period_ms': periods[0] * 1000,
            'data_gaps': gaps, 'transport_scope': 'CAN_FD_REQUEST_RESPONSE', 'continuation': continuation}])
    return {'supported': True, 'proposal': proposal, 'findings': gaps}


def build_changes(graph, template, settings, template_port, definitions, period, goal, *, continuation=None):
    """Build one reviewable atomic delta; preserve every existing object."""
    from ..message_packing import valid_payload_bytes
    from ..signal_audit import occupied_signal_bits
    from ..communication_repair import RepairPlanner
    from ..communication_contract_repair import scan_signal_recipients
    from ..routing.validation import RoutingValidator
    from .proposal_service import order_change_dependencies
    network = graph.networks[template_port['network_ref']]
    occupied_names = {str(h['name']).casefold() for h in graph.hardware.values()}
    name, index = 'StellgliedAbfrageECU', 2
    while name.casefold() in occupied_names:
        name = 'StellgliedAbfrageECU_' + str(index); index += 1
    if continuation:
        name = str(graph.hardware[continuation['requester_id']]['name']) + '_Erweiterung_' + str(len(continuation['actuator_ids']) + 1)
    provenance = {'source': 'explicit_periodic_acquisition', 'workload_id': goal['goal_id'],
                  'controller_template_ref': str(template['id'])}
    changes = []
    def add(kind, ref, data):
        changes.append({'object_type': kind, 'action': 'CREATE', 'local_ref': ref, 'data': data})
    add('HardwareNode', 'requester', {'name': name, 'device_type': 'ECU', 'device_class': template['device_class'],
        'description': goal['original_request'], 'provenance': provenance,
        'identity': {'periodic_acquisition_requester': True, 'controller_template_ref': str(template['id'])}})
    add('Function', 'acquisition', {'name': 'StellgliedPositionAbfrage', 'hardware_node_id': '$requester',
        'description': goal['original_request'], 'provenance': provenance,
        'configuration': {'acquisition_mode': 'REQUEST_RESPONSE', 'cycle_time_ms': period,
            'actuator_refs': [d['actuator_id'] for d in definitions],
            'source_signal_refs': [str(d['signal']['id']) for d in definitions]}})
    controllers = [c for c in graph.resources.get('CommunicationController', []) if c['id'] == template_port['controller_ref']]
    caps = [c for c in graph.resources.get('CommunicationCapability', [])
            if str(c['hardware_node_ref']) == str(template['id']) and str(c['technology']).upper() == 'CAN_FD']
    if len(controllers) != 1 or len(caps) != 1:
        raise EngineeringValidationError('Die Controller-Vorlage benötigt genau einen bestätigten CAN-FD-Controller mit Ressourcenmodell.')
    cap, controller = deepcopy(caps[0]), deepcopy(controllers[0])
    cap.update(id=str(uuid4()), hardware_node_ref='$requester', provenance=provenance)
    controller.update(id=str(uuid4()), hardware_node_ref='$requester', active_channels=[template_port['channel_index']], provenance=provenance)
    add('CommunicationCapability', 'capability', cap); add('CommunicationController', 'controller', controller)
    physical_id = str(uuid4())
    add('HardwareNetworkInterface', 'port', {'name': name + '_CAN_FD', 'hardware_node_id': '$requester',
        'technology': 'CAN_FD', 'controller_ref': '$controller', 'channel_index': template_port['channel_index'],
        'physical_port_ref': physical_id, 'network_ref': network['id'],
        'bitrate': network['bitrate'], 'data_bitrate': network['data_bitrate'], 'provenance': provenance})
    add('PhysicalPort', 'physical-port', {'id': physical_id, 'hardware_node_ref': '$requester',
        'controller_ref': '$controller', 'hardware_interface_ref': '$port', 'technology': 'CAN_FD',
        'channel_index': template_port['channel_index'], 'direction': 'BIDIRECTIONAL',
        'network_ref': network['id'], 'connection_status': 'CONNECTED', 'provenance': provenance})
    add('NetworkConnection', 'network-connection', {'connection_id': str(uuid4()), 'port_ref': '$physical-port',
        'network_ref': network['id'], 'technology_binding_ref': '$port', 'status': 'ACTIVE',
        'created_by': 'engineering-agent', 'provenance': provenance})
    add('Interface', 'logical', {'name': name + '_Abfrage', 'function_id': '$acquisition',
        'interface_type': 'CAN_FD', 'configuration': {'network_ref': network['id']}, 'provenance': provenance})
    topology = deepcopy(graph.model['topology'])
    peers = [(n, p) for n in topology.get('nodes', []) for p in n.get('ports', [])
             if str(p.get('hardwareInterfaceId')) == str(template_port['id'])
             and p.get('physicalNetworkId') == network['id']]
    if len(peers) != 1:
        raise EngineeringValidationError('Die bestätigte Anschlussstelle der Controller-Vorlage ist nicht eindeutig.')
    peer, peer_port = peers[0]; node_id = 'acquisition-node-' + str(uuid4()); drawing_id = 'acquisition-port-' + str(uuid4())
    topology.setdefault('nodes', []).append({'id': node_id, 'engineeringId': '$requester', 'name': name,
        'kind': 'ecu', 'ports': [{'id': drawing_id, 'hardwareInterfaceId': '$port', 'name': name + '_CAN_FD',
            'bus': 'CAN_FD', 'physicalNetworkId': network['id']}], 'x': 0, 'y': 0})
    edge_id = 'acquisition-edge-' + str(uuid4())
    topology.setdefault('edges', []).append({'id': edge_id, 'source': node_id,
        'sourcePort': drawing_id, 'target': peer['id'], 'targetPort': peer_port['id'], 'bus': 'CAN_FD',
        'physicalNetworkId': network['id'], 'direction': 'bidirectional', 'relationshipType': 'CONNECTED_VIA',
        'engineeringSegmentId': edge_id, 'origin': 'CANONICAL_BUS_BINDING'})
    add('NetworkTopology', 'topology', {'name': 'Anschluss der Abfrage-ECU', 'topology': topology,
        'resource_refs': ['$physical-port', '$network-connection']})
    used_identifiers = set()
    for message in graph.messages.values():
        port = graph.hni.get(str(message.get('hardware_interface_id')), {})
        if port.get('network_ref') == network['id'] and message.get('message_id_hex'):
            used_identifiers.add(int(str(message['message_id_hex']), 16))
    new_message_refs = []
    signal_fields = {'name', 'start_bit', 'length_bits', 'byte_order', 'data_type', 'unit', 'factor',
                     'offset_value', 'min_value', 'max_value', 'semantic', 'data', 'quality', 'communication', 'configuration'}
    def transport(ref, title, logical, port, identifier, interval, consumer, signal, requirements, role, correlation=None, minimum_bytes=0, request_ref=None, response_contract=None):
        consumer_function = consumer if consumer == '$acquisition' or consumer in graph.functions else None
        consumer = ('$requester' if consumer == '$acquisition' else
                    str(graph.functions[consumer]['hardware_node_id']) if consumer in graph.functions else consumer)
        producer = ('$requester' if logical == '$logical' else str(graph.interfaces[logical]['hardware_node_id']))
        try:
            frame_id = int(str(identifier), 16)
        except (TypeError, ValueError) as error:
            raise EngineeringValidationError('Explizite CAN-FD-Framekennung fehlt oder ist ungültig.') from error
        if not 0 < frame_id <= 0x7ff or frame_id in used_identifiers:
            raise EngineeringValidationError('Die bestätigte Standard-Framekennung ist ungültig oder bereits belegt.')
        used_identifiers.add(frame_id)
        if any(key not in signal for key in ('start_bit', 'length_bits', 'byte_order', 'data_type', 'factor', 'offset_value')):
            raise EngineeringValidationError('Die Anfrage/Antwort benötigt vollständige explizite Signalkodierung.')
        if signal.get('protocol_bindings'):
            raise EngineeringValidationError('Protokollgebundene Positionsdaten benötigen eine ausdrücklich bestätigte Abbildung.')
        bits = occupied_signal_bits(signal)
        if not bits:
            raise EngineeringValidationError('Die bestätigte Signalkodierung belegt keine gültigen Bits.')
        size = valid_payload_bytes('CAN_FD', max(minimum_bytes, (max(bits) + 8) // 8))
        if size is None:
            raise EngineeringValidationError('Die bestätigte Kodierung passt nicht in einen CAN-FD-Frame.')
        if (requirements.get('confirmed') is not True
                or type(requirements.get('maximum_event_to_response_ms')) not in (float, int)
                or requirements['maximum_event_to_response_ms'] <= 0):
            raise EngineeringValidationError('Bestätigte funktionale Zeitbedingungen fehlen.')
        config = {'generation_role': role, 'maximum_latency_ms': requirements['maximum_event_to_response_ms'],
            'communication_contract': {'scope': 'FUNCTION_OUTPUT', 'consumer_refs': [consumer],
                'transmission': {'mode': 'CYCLIC' if role != 'ACQUISITION_RESPONSE' else 'ON_REQUEST',
                    'period_ms': interval, 'functional_requirements': deepcopy(requirements)}},
            'transport_unit': {'technology_id': 'can_fd', 'payload_bytes': size, 'cycle_ms': interval,
                'consumer_refs': [consumer], 'producer_ref': producer, 'provenance': provenance},
            'acquisition_exchange': {'role': role, 'correlation_id': correlation, 'period_ms': period,
                'consumer_function_ref': consumer_function,
                'source_signal_ref': str(signal['id']) if signal.get('id') else None}}
        if role == 'ACQUISITION_RESPONSE':
            config['communication_contract']['transmission'].update(request_source='bus_message',
                request_message_ref=request_ref, response_processing_ms=response_contract['response_processing_ms'],
                minimum_interval_ms=response_contract['response_minimum_interval_ms'])
        add('Message', ref, {'name': title, 'interface_id': logical, 'hardware_interface_id': port,
            'message_id_hex': hex(frame_id), 'cycle_ms': interval, 'dlc': size, 'direction': 'tx',
            'configuration': config, 'provenance': provenance})
        value = {k: deepcopy(v) for k, v in signal.items() if k in signal_fields}
        value.update(name=title + '_Wert', message_id='$' + ref, provenance={**provenance,
            'source_signal_ref': str(signal['id']) if signal.get('id') else None})
        add('Signal', ref + '-signal', value); new_message_refs.append(ref)
    for index, definition in enumerate(definitions):
        contract = definition['contract']; correlation = str(uuid4()); suffix = str(index)
        transport('request-' + suffix, name + '_Positionsanfrage_' + suffix, '$logical', '$port',
            contract['request_frame_id'], period, str(definition['interface'].get('function_id') or definition['actuator_id']),
            contract['request_signal'], contract['functional_requirements'], 'ACQUISITION_REQUEST', correlation)
        transport('response-' + suffix, name + '_Positionsantwort_' + suffix, str(definition['interface']['id']), str(definition['port']['id']),
            contract['response_frame_id'], period, '$acquisition', definition['signal'], contract['functional_requirements'],
            'ACQUISITION_RESPONSE', correlation, int(definition['message']['dlc']),
            '$request-' + suffix, contract)
    if not continuation:
        transport('status', name + '_Status', '$logical', '$port', settings.get('status_frame_id'), settings['status_cycle_ms'],
            settings['status_consumer_ref'], settings.get('status_signal') or {}, settings.get('status_functional_requirements') or {}, 'DEVICE_STATUS')
    else:
        reused = {'$requester': continuation['requester_id'], '$logical': continuation['logical_id'],
                  '$port': continuation['port_id'], '$acquisition': continuation['function_id']}
        def reuse(value):
            if isinstance(value, dict): return {k: reuse(v) for k, v in value.items()}
            if isinstance(value, list): return [reuse(v) for v in value]
            return reused.get(value, value) if isinstance(value, str) else value
        changes = [reuse(c) for c in changes if c['object_type'] in {'Message', 'Signal'}]
        config = deepcopy(continuation['configuration'])
        config['actuator_refs'] += [d['actuator_id'] for d in definitions]
        config['source_signal_refs'] += [str(d['signal']['id']) for d in definitions]
        changes.insert(0, {'object_type': 'Function', 'action': 'UPDATE', 'local_ref': 'acquisition',
            'object_id': continuation['function_id'], 'data': {'configuration': config}})
    changes = order_change_dependencies(changes)
    snapshot, _, refs = proposed_model(changes)
    objects = {kind: snapshot['tables'][table] for kind, table in TABLES.items()}
    planner = RepairPlanner({'topology': snapshot['topology'], 'parameters': snapshot['parameters']},
                            objects, snapshot['tables']['engineering_routing_entries'])
    validator = RoutingValidator(current_project_id(), model_snapshot=snapshot)
    scanned = scan_signal_recipients(planner, validator.validate)
    expected = {refs[ref] for ref in new_message_refs}
    routes = [c for c in scanned['changes'] if set(c['data']['payload'].get('message_ids') or []) <= expected]
    if len(routes) != len(expected) or {mid for c in routes for mid in c['data']['payload']['message_ids']} != expected:
        raise EngineeringValidationError('Nicht alle bestätigten Abfragen besitzen einen eindeutigen validierten Signalweg: ' + str(scanned['findings']))
    reverse = {value: '$' + key for key, value in refs.items()}
    def localize(value):
        if isinstance(value, dict): return {k: localize(v) for k, v in value.items()}
        if isinstance(value, list): return [localize(v) for v in value]
        return reverse.get(value, value) if isinstance(value, str) else value
    for index, route in enumerate(routes):
        data = localize(route['data']); data.setdefault('route', {})['topology_ref'] = 'workflow-network-topology' if continuation else '$topology'
        changes.append({'object_type': 'RoutingEntry', 'action': 'CREATE', 'local_ref': 'route-' + str(index), 'data': data})
    return order_change_dependencies(changes)


def reconcile_apply(proposal, evidence):
    from datetime import datetime, timezone
    from . import conversation
    from ..db import ConcurrentUpdateError, flush_model_changes
    from ..capacity.service import CapacityTimingService, PreflightService
    from ..routing.repository import get_route
    from ..routing.validation import RoutingValidator
    from ..repository import get_object
    from .proposal_service import _resolve
    state = conversation.read(); goal_id = str(evidence['engineering_goal_id'])
    work = state.get('engineering_workloads', {}).get(goal_id) or {}; goal = work.get('goal') or {}
    if (work.get('project_id') != current_project_id() or goal.get('goal_type') != 'PERIODIC_ACQUISITION'
            or proposal.get('workload_id') != goal_id or proposal.get('proposal_type') != 'PERIODIC_ACQUISITION'
            or proposal.get('status') != 'APPLIED' or not proposal.get('validation_result', {}).get('valid')):
        raise ConcurrentUpdateError('Der Abfragevorschlag gehört nicht zum gespeicherten Auftrag.')
    changes = proposal.get('changes') or []; canonical = proposal.get('canonical_ids') or []
    if not changes or len(changes) != len(canonical):
        raise EngineeringValidationError('Die kanonischen Abfrageobjekte sind nicht vollständig belegt.')
    refs = {change['local_ref']: row['id'] for change, row in zip(changes, canonical)}
    continuation = evidence.get('continuation')
    if continuation:
        previous = state.get('engineering_workloads', {}).get(continuation.get('prior_workload_id')) or {}
        if (goal.get('follow_up_of') != continuation.get('prior_workload_id') or previous.get('status') != 'COMPLETED'
                or previous.get('project_id') != current_project_id()
                or previous.get('result', {}).get('periodic_acquisition', {}).get('requester_id') != continuation.get('requester_id')
                or refs.get('acquisition') != continuation.get('function_id')):
            raise EngineeringValidationError('Die übernommene Erweiterung gehört nicht zur vorhandenen Abfrage.')
        refs['requester'] = continuation['requester_id']
    periods = [p.get('seconds') for p in goal.get('timing_constraints', []) if p.get('kind') == 'PERIOD']
    if len(periods) != 1 or evidence.get('period_ms') != periods[0] * 1000:
        raise EngineeringValidationError('Das übernommene Abfrageintervall weicht vom Auftrag ab.')
    def contains(actual, expected):
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(contains(a, e) for a, e in zip(actual, expected))
        return actual == expected
    route_ids = []
    from ..workflow.service import WorkflowStatusService
    workflow = WorkflowStatusService(current_project_id())
    topology = deepcopy(workflow.get()['topology'])
    edges = {str(edge['id']): edge for edge in topology.get('edges', [])}
    for change, row in zip(changes, canonical):
        kind = change['object_type']
        if row['object_type'] != kind:
            raise EngineeringValidationError('Die übernommenen Objekttypen passen nicht zum Abfragevorschlag.')
        if kind in TABLES:
            actual = access.json_safe(get_object(kind, row['id']))
            if not contains(actual, _resolve(change['data'], refs)):
                raise EngineeringValidationError('Ein übernommenes Abfrageobjekt weicht vom geprüften Vorschlag ab.')
        elif kind == 'RoutingEntry':
            route = get_route(row['id'])
            if not RoutingValidator().validate(route, exclude_route_id=row['id'])['valid']:
                raise EngineeringValidationError('Die übernommene Anfrage-/Antwortroute ist nicht gültig.')
            paths = (route.get('route') or {}).get('physical_paths') or []
            path_edges = {str(edge) for path in paths for edge in path.get('edges', [])}
            if not path_edges or not path_edges.issubset(edges):
                raise EngineeringValidationError('Der geprüfte physische Abfragepfad ist nicht vollständig vorhanden.')
            for edge_id in path_edges:
                edge = edges[edge_id]
                linked = {str(value) for value in edge.get('routingEntryIds') or []}
                linked.add(str(row['id']))
                edge['routingEntryIds'] = sorted(linked)
            route_ids.append(row['id'])
    workflow.save_topology(topology, actor='local-human')
    flush_model_changes(actor='local-human', reason='Geprüfte periodische Abfrage übernommen.')
    for step in ('engineering_model', 'routing', 'network_editor', 'parameters'):
        workflow.refresh_source_status(step, actor='periodic-acquisition')
    capacity = CapacityTimingService(current_project_id()).calculate(persist=True)
    preflight = PreflightService(current_project_id()).run()
    capacity_id = str(capacity.get('id') or capacity.get('snapshot_id') or '')
    preflight_id = str(preflight.get('snapshot_id') or '')
    results = capacity.get('results') or {}; networks = results.get('networks') or []; routes = results.get('routes') or []
    checked = bool(capacity_id and preflight_id and preflight.get('capacity_snapshot_id') == capacity_id)
    exchanges = [exchange for network in networks for exchange in
                 (network.get('communication_schedule') or {}).get('request_exchanges', [])
                 if exchange.get('response_message_id') in refs.values()]
    exchanges_verified = (len(exchanges) == len(evidence.get('resolved_actuator_ids') or [])
                          and all(exchange.get('status') == 'PASS' for exchange in exchanges))
    outcomes = {'requester_exists': bool(refs.get('requester')), 'period_configured': bool(refs.get('acquisition')),
        'data_sources_resolved': not evidence.get('data_gaps') and bool(evidence.get('source_signal_ids')),
        'route_valid': len(route_ids) == len(evidence.get('resolved_actuator_ids') or []) * 2 + (0 if continuation else 1),
        'capacity_evaluated': checked and bool(networks) and all(n.get('capacity_verified') is True for n in networks),
        'timing_evaluated': checked and exchanges_verified and bool(routes) and all(r.get('timing_verified') is True for r in routes),
        'preflight_valid': checked and preflight.get('ready_for_simulation') is True}
    required = goal.get('required_outcomes') or []; missing = [k for k in required if not outcomes.get(k)]
    complete = bool(required) and not missing
    proof = [proposal['proposal_id'], *[r['id'] for r in canonical], capacity_id, preflight_id]
    work['status'] = 'COMPLETED' if complete else 'BLOCKED_WITH_EXPLICIT_CAUSE'
    work['evidence'] = proof
    work['result'] = {**(work.get('result') or {}), 'status': 'APPLIED', 'proposal_id': proposal['proposal_id'],
        'canonical_ids': canonical, 'model_diff': changes, 'model_revision_after': access.model_revision(),
        'completion': {'status': work['status'], 'completed': complete, 'achieved_outcomes': [k for k in required if outcomes.get(k)],
            'missing_outcomes': missing, 'evidence_refs': proof},
        'periodic_acquisition': {'requester_id': refs.get('requester'), 'function_id': refs.get('acquisition'),
            'period_ms': evidence['period_ms'], 'actuator_ids': (continuation or {}).get('actuator_ids', []) + evidence['resolved_actuator_ids'],
            'source_signal_ids': (continuation or {}).get('source_signal_ids', []) + evidence['source_signal_ids'],
            'route_ids': (continuation or {}).get('route_ids', []) + route_ids, 'data_gaps': evidence.get('data_gaps') or []},
        'dependent_results': {'capacity_snapshot_id': capacity_id, 'preflight_snapshot_id': preflight_id,
            'capacity_status': capacity.get('status'), 'preflight_status': preflight.get('preflight_status'),
            'ready_for_simulation': preflight.get('ready_for_simulation')}}
    work['updated_at'] = datetime.now(timezone.utc).isoformat(); conversation.write(state)
    return True
