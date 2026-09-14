"""Human-authored resource facts, validated against the canonical hardware model."""
from .graph import ModelGraphService
from .store import RESOURCE_MODELS, save_resource
from ..db import ConcurrentUpdateError
from ..physical_ports import technology_id


def record_hardware_fact(kind, body, expected_revision):
    if kind not in {'CommunicationCapability', 'CommunicationController'}:
        raise ValueError('Ports und Netzverbindungen werden durch einen geprüften Anschlussplan angelegt.')
    graph = ModelGraphService.load()
    if not expected_revision or graph.revision != expected_revision:
        raise ConcurrentUpdateError('Die Hardwaredaten wurden inzwischen geändert. Aktuellen Modellstand laden.')
    value = RESOURCE_MODELS[kind].model_validate(body).model_dump(mode='json')
    owner, tech = value['hardware_node_ref'], technology_id(value['technology'])
    if owner not in graph.hardware: raise ValueError('Hardware fehlt im aktiven Projekt.')
    existing = next((item for item in graph.resources.get(kind, []) if item['id'] == value['id']), None)
    if existing and (existing['hardware_node_ref'] != owner or technology_id(existing['technology']) != tech):
        raise ValueError('Bestehende Hardwarefakten können nicht auf ein anderes Gerät oder eine andere Technologie übertragen werden.')
    interfaces = [i for i in graph.find_hardware_interfaces(owner) if technology_id(i['technology']) == tech]
    if kind == 'CommunicationCapability':
        controllers = [c for c in graph.find_communication_controllers(owner) if technology_id(c['technology']) == tech]
        ports = graph.find_ports_by_technology(owner, tech)
        channels = {(i.get('controller_ref'), i.get('channel_index')) for i in interfaces if i.get('channel_index')}
        if (interfaces and not value['supported']) or len(ports) > value['max_ports'] or len(channels) > value['max_channels'] or len(controllers) > value['controller_count']:
            raise ValueError('Die bestätigte Hardwaregrenze widerspricht vorhandenen Anschlüssen oder Controllern.')
    else:
        channels = {i['channel_index'] for i in interfaces if i.get('controller_ref') == value['id'] and i.get('channel_index')}
        channels.update(value['active_channels'])
        if any(type(index) is not int or not 1 <= index <= value['max_channels'] for index in channels):
            raise ValueError('Controllerkanäle liegen außerhalb der bestätigten Grenze.')
        if value['status'] != 'ACTIVE' and channels:
            raise ValueError('Ein belegter Controller kann nicht ohne Anschlussänderung deaktiviert werden.')
    value['provenance'] = {**value.get('provenance', {}), 'source': 'human-hardware-fact'}
    return save_resource(kind, value)
