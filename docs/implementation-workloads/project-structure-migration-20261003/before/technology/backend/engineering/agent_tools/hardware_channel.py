"""A single explicitly requested hardware channel, with no inferred transport."""
from copy import deepcopy
from uuid import uuid4

from backend.agent_core.runtime.hardware_intent import hardware_channel_intent
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from ..models import INTERFACE_TYPES, EngineeringValidationError
from ..goal_execution.graph import ModelGraphService
from ..goal_execution.typing import type_reference
from ..goal_execution.commands import checked_port, ExecutionBlocked
from ..goal_execution.store import save_resource
from ..project_context import current_project_id


def _technology(value):
    normalized = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(str(value))
    DEFAULT_TECHNOLOGY_REGISTRY.profile(normalized)
    return normalized


def _interface_type(technology):
    if DEFAULT_TECHNOLOGY_REGISTRY.profile(technology)['layer'] not in {'PHYSICAL', 'DATA_LINK'}:
        raise ValueError('Ein Anwendungsprotokoll definiert keinen eigenen physischen Hardwarekanal.')
    for candidate in INTERFACE_TYPES:
        if DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(candidate) == technology:
            return candidate
    raise ValueError('Für die angeforderte Technologie ist kein eigener Hardwarekanal registriert.')


def inspect_request(arguments):
    intent = hardware_channel_intent(arguments['request'])
    if not intent:
        return {'supported': False}
    graph = ModelGraphService.load()
    result = {'supported': True, 'project_id': current_project_id(), 'model_revision': graph.revision,
              'requested_channel': intent['channel_index'], 'request': arguments['request']}

    def blocked(code, message):
        return {**result, 'status': 'BLOCKED', 'reason': message,
                'findings': [{'code': code, 'severity': 'ERROR', 'message': message}]}

    try:
        technology = _technology(intent['technology'])
        canonical = _interface_type(technology)
    except (KeyError, ValueError):
        return blocked('HARDWARE_CHANNEL_TECHNOLOGY_UNSUPPORTED',
                       'Für die angeforderte Technologie ist kein eigener bestätigter Hardwarekanal verfügbar.')
    result['technology'] = canonical
    typed = type_reference(graph, intent['hardware_reference'])
    result['target_resolution'] = typed.model_dump(mode='json')
    if typed.clarification_required or typed.engineering_type != 'HardwareNode':
        return blocked('HARDWARE_REFERENCE_UNRESOLVED', 'Die Hardware ist im aktuellen Projekt nicht eindeutig aufgelöst. Kanonische Hardware auswählen.')
    hardware_id = typed.matched_object_ref
    result.update(hardware_id=hardware_id, hardware_name=graph.hardware[hardware_id]['name'])
    try:
        caps = [c for c in graph.find_communication_capabilities(hardware_id) if _technology(c.get('technology')) == technology]
        controllers = [c for c in graph.find_communication_controllers(hardware_id)
                       if _technology(c.get('technology')) == technology and c.get('status') == 'ACTIVE']
    except (KeyError, ValueError):
        return blocked('HARDWARE_CAPABILITY_INVALID', 'Die gespeicherte Hardwarefähigkeit enthält eine unbekannte Technologie.')
    result['capabilities'] = caps
    if not caps or any(c.get('supported') is not True for c in caps):
        return blocked('COMMUNICATION_CAPABILITY_MISSING', 'Die angeforderte Kommunikationsfähigkeit ist für diese Hardware nicht bestätigt.')
    if any(type(c.get(k)) is not int or c[k] < 0 for c in caps for k in ('controller_count', 'max_channels', 'max_ports')):
        return blocked('HARDWARE_CAPACITY_UNKNOWN', 'Die bestätigten Controller-, Kanal- oder Portgrenzen fehlen.')
    if not controllers or any(type(c.get('max_channels')) is not int or c['max_channels'] < 0 for c in controllers):
        return blocked('COMMUNICATION_CONTROLLER_MISSING', 'Ein aktiver Controller mit bestätigter Kanalgrenze fehlt.')
    capacities = [graph.find_port_capacity(c['id']) for c in controllers]
    result['controller_capacities'] = capacities
    channel = intent['channel_index']
    existing = [i for i in graph.find_hardware_interfaces(hardware_id)
                if i.get('channel_index') == channel and _technology(i['technology']) == technology]
    if existing:
        if len(existing) != 1:
            return blocked('HARDWARE_CHANNEL_AMBIGUOUS', 'Die Kanalnummer gehört zu mehreren Anschlüssen. Controller ausdrücklich auswählen.')
        try:
            checked_port(graph, existing[0], require_network=False)
        except ExecutionBlocked as error:
            return blocked(error.findings[0]['code'], str(error))
        return {**result, 'status': 'ALREADY_PRESENT', 'controller_id': existing[0]['controller_ref'],
                'existing_interface_id': str(existing[0]['id'])}
    candidates = [c for c, capacity in zip(controllers, capacities) if channel in capacity['available_channels']]
    if len(candidates) > 1:
        return blocked('HARDWARE_CONTROLLER_AMBIGUOUS', 'Mehrere Controller können diesen Kanal bereitstellen. Controller ausdrücklich auswählen.')
    controller = candidates[0] if candidates else controllers[0] if len(controllers) == 1 else None
    if controller:
        result['controller_id'] = controller['id']
        result['controller_capacity'] = graph.find_port_capacity(controller['id'])
    occupied = sum(len(c['used_channels']) for c in capacities)
    ports = [p for p in graph.find_ports(hardware_id) if _technology(p['technology']) == technology]
    if (not candidates or any(len(controllers) > c['controller_count'] or occupied >= c['max_channels']
                              or len(ports) >= c['max_ports'] for c in caps)):
        return blocked('HARDWARE_INTERFACE_CAPACITY_EXCEEDED',
                       f'Die bestätigte Hardwaregrenze erlaubt keinen zusätzlichen Kanal {channel}; kein passender freier Kanal ist verfügbar.')
    return {**result, 'status': 'READY'}


def prepare(arguments):
    from . import proposal_service
    result = inspect_request(arguments)
    if not result.get('supported') or result.get('status') != 'READY':
        return result
    if result['model_revision'] != arguments['expected_model_revision']:
        raise EngineeringValidationError('Die Hardware oder ihre Ressourcen wurden seit der Prüfung geändert.')
    data = {'name': f"{result['hardware_name']}_{result['technology']}_{result['requested_channel']}",
            'hardware_node_id': result['hardware_id'], 'technology': result['technology'],
            'controller_ref': result['controller_id'], 'channel_index': result['requested_channel'],
            'physical_port_ref': 'physical-port-' + str(uuid4()),
            'provenance': {'source': 'explicit_hardware_channel', 'workload_id': arguments['workload_id']}}
    proposal = proposal_service.create('HARDWARE_CHANNEL', [
        {'object_type': 'HardwareNetworkInterface', 'action': 'CREATE', 'local_ref': 'channel', 'data': data}],
        arguments['request'], evidence=[{'source': 'explicit_hardware_channel',
            'engineering_goal_id': arguments['workload_id'], 'hardware_id': result['hardware_id'],
            'controller_id': result['controller_id'], 'channel_index': result['requested_channel'],
            'model_revision': result['model_revision']}], workload_id=arguments['workload_id'])
    return {**result, 'proposal': proposal}


def validate_changes(changes):
    if len(changes) != 1:
        raise EngineeringValidationError('Ein Kanalauftrag darf genau einen Hardwareanschluss ergänzen.')
    change = changes[0]
    data = deepcopy(change.get('data') or {})
    if change.get('action') != 'CREATE' or change.get('object_type') != 'HardwareNetworkInterface' or data.get('network_ref'):
        raise EngineeringValidationError('Der Kanalauftrag darf ausschließlich einen unverbundenen Hardwareanschluss ergänzen.')
    graph = ModelGraphService.load()
    capacity = graph.find_port_capacity(data.get('controller_ref'))
    if data.get('channel_index') not in capacity.get('available_channels', []):
        raise EngineeringValidationError('Der freigegebene Controllerkanal ist nicht mehr verfügbar.')
    data['id'] = '$' + change['local_ref']
    candidate = deepcopy(graph.model)
    candidate.setdefault('hardware-interfaces', []).append(data)
    prospective = ModelGraphService(candidate, graph.resources, state=graph.state, relations=graph.relations)
    checked_port(prospective, data, require_network=False)


def persist_port(interface, workload_id):
    save_resource('PhysicalPort', {'id': interface['physical_port_ref'],
        'hardware_node_ref': str(interface['hardware_node_id']), 'controller_ref': interface['controller_ref'],
        'hardware_interface_ref': str(interface['id']), 'technology': interface['technology'],
        'channel_index': interface['channel_index'], 'direction': 'BIDIRECTIONAL',
        'network_ref': None, 'connection_status': 'FREE',
        'provenance': {'source': 'explicit_hardware_channel', 'workload_id': workload_id}})
