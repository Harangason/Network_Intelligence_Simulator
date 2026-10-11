"""Human fact capture in the current goal; never an LLM hardware-write tool."""
from copy import deepcopy
from pydantic import Field
from .models import Contract, CommunicationCapability, CommunicationController
from .graph import ModelGraphService
from .store import get_goal, save_goal, save_resource
from ..physical_ports import technology_id, _interface_technology
from ..db import ConcurrentUpdateError, get_connection, _request_unit, flush_model_changes


class PortAssignment(Contract):
    interface_ref: str
    controller_ref: str
    channel_index: int = Field(ge=1)


class HardwareFacts(Contract):
    expected_revision: str = Field(min_length=1)
    evidence: str = Field(min_length=3, max_length=2000)
    capability: CommunicationCapability
    controllers: list[CommunicationController] = Field(max_length=64)
    assignments: list[PortAssignment] = Field(default_factory=list, max_length=256)


def scope(goal, graph):
    owners = set(goal.get('host_refs', []))
    for candidate in goal.get('strategies', []):
        owners.update(str(graph.hni[p]['hardware_node_id']) for p in candidate.get('path', {}).get('ports', []) if p in graph.hni)
    return owners & graph.hardware.keys()


def inspect(workload_id):
    goal, graph = get_goal(workload_id), ModelGraphService.load()
    owners = scope(goal, graph)
    technologies = {i['technology'] for owner in owners for i in graph.find_hardware_interfaces(owner)}
    technologies.update(d['technology'] for d in goal.get('port_decisions', []))
    return {'workload_id': workload_id, 'model_revision': graph.revision, 'status': goal['status'],
        'hardware': [{'id': owner, 'name': graph.hardware[owner]['name'],
            'capabilities': graph.find_communication_capabilities(owner),
            'controllers': graph.find_communication_controllers(owner),
            'interfaces': graph.find_hardware_interfaces(owner)} for owner in sorted(owners)],
        'technologies': sorted({_interface_technology(t) for t in technologies})}


def record(workload_id, data, *, actor):
    """Record a reviewed batch atomically, then invalidate its old execution authority.

    Existing verified channels cannot be moved by this fact-capture operation.
    Missing legacy controller/channel assignments must be explicitly supplied.
    """
    if _request_unit.get() is None:
        raise RuntimeError('Hardwarefakten benötigen eine Projekttransaktion.')
    value = HardwareFacts.model_validate(data).model_dump(mode='json')
    goal, graph = get_goal(workload_id), ModelGraphService.load()
    if goal['status'] in {'RUNNING', 'FOLLOWUP_PENDING', 'SIMULATION_RUNNING', 'COMPLETE'}:
        raise ValueError('Dieser Auftrag erwartet aktuell keine Hardwaredaten.')
    if graph.revision != value['expected_revision']:
        raise ConcurrentUpdateError('Das Modell wurde geändert. Hardwaredaten neu laden und prüfen.')
    cap = value['capability']; owner = cap['hardware_node_ref']; tech = technology_id(cap['technology'])
    if owner not in scope(goal, graph):
        raise ValueError('Die Hardware gehört nicht zum geprüften Auftragsumfang.')
    if _interface_technology(cap['technology']) not in inspect(workload_id)['technologies']:
        raise ValueError('Die Technologie gehört nicht zum geprüften Auftragsumfang.')
    controllers = value['controllers']
    if len({c['id'] for c in controllers}) != len(controllers):
        raise ValueError('Controllerkennungen müssen eindeutig sein.')
    if any(c['hardware_node_ref'] != owner or technology_id(c['technology']) != tech for c in controllers):
        raise ValueError('Controller müssen zu dieser Hardware und Technologie gehören.')
    existing_controllers = [c for c in graph.find_communication_controllers(owner) if technology_id(c['technology']) == tech]
    if not {c['id'] for c in existing_controllers} <= {c['id'] for c in controllers}:
        raise ValueError('Vorhandene Controller müssen erhalten bleiben.')
    existing_caps = [c for c in graph.find_communication_capabilities(owner) if technology_id(c['technology']) == tech]
    if len(existing_caps) > 1 or existing_caps and cap['id'] != existing_caps[0]['id']:
        raise ValueError('Bestehende Capability eindeutig wiederverwenden; keine zweite Hardwaregrenze anlegen.')
    for kind, values in [('CommunicationCapability', [cap]), ('CommunicationController', controllers)]:
        for item in values:
            old = next((r for r in graph.resources.get(kind, []) if r['id'] == item['id']), None)
            if old and (old['hardware_node_ref'] != owner or technology_id(old['technology']) != tech):
                raise ValueError('Eine Ressourcenkennung darf nicht auf andere Hardware übertragen werden.')
    if len(controllers) > cap['controller_count']:
        raise ValueError('Die Controllerzahl überschreitet die bestätigte Hardwaregrenze.')
    if controllers and not cap['supported']:
        raise ValueError('Ohne Technologie-Fähigkeit können keine Controller bestätigt werden.')
    for controller in controllers:
        if len(controller['active_channels']) != len(set(controller['active_channels'])) or any(not 1 <= ch <= controller['max_channels'] for ch in controller['active_channels']):
            raise ValueError('Reservierte Controllerkanäle sind ungültig oder doppelt angegeben.')
    interfaces = {str(i['id']): i for i in graph.find_hardware_interfaces(owner) if technology_id(i['technology']) == tech}
    assignments = {a['interface_ref']: a for a in value['assignments']}
    if len(assignments) != len(value['assignments']) or assignments.keys() != interfaces.keys():
        raise ValueError('Alle vorhandenen Anschlüsse dieser Technologie müssen genau einmal zugeordnet werden.')
    if interfaces and (not cap['supported'] or len(interfaces) > cap['max_ports'] or len(interfaces) > cap['max_channels']):
        raise ValueError('Vorhandene Anschlüsse überschreiten die bestätigten Hardwaregrenzen.')
    by_id = {c['id']: c for c in controllers}; used = set()
    for ref, assignment in assignments.items():
        original = interfaces[ref]; cid, channel = assignment['controller_ref'], assignment['channel_index']
        controller = by_id.get(cid)
        if not controller or controller['status'] != 'ACTIVE' or channel > controller['max_channels']:
            raise ValueError('Anschlusskanal benötigt einen verfügbaren bestätigten Controller.')
        if (cid, channel) in used:
            raise ValueError('Ein Controllerkanal kann nur einen physischen Anschluss tragen.')
        used.add((cid, channel))
        old_controller = next((c for c in existing_controllers if c['id'] == original.get('controller_ref')), None)
        if old_controller and (cid != original.get('controller_ref') or original.get('channel_index') and channel != original['channel_index']):
            raise ValueError('Ein bereits bestätigter Anschluss darf durch die Faktenerfassung nicht umgehängt werden.')
        net = graph.networks.get(original.get('network_ref'), {})
        if net and cap['supported_bitrates'] and net.get('bitrate') not in cap['supported_bitrates']:
            raise ValueError('Die bestätigten Bitraten widersprechen einem angeschlossenen Netz.')
    reserved = {(c['id'], ch) for c in controllers for ch in c['active_channels']}
    if len(used | reserved) > cap['max_channels']:
        raise ValueError('Belegte und reservierte Kanäle überschreiten die Hardwaregrenze.')
    from ..repository import update_object
    from .commands import persist_port_resources
    from .executor import journal
    unit = _request_unit.get(); dirty = unit.model_changed
    try:
        with get_connection():
            provenance = {'source': 'human-hardware-fact', 'evidence': value['evidence'].strip(), 'actor': actor, 'workload_id': workload_id}
            # Embedded facts are migrated, not shadowed with duplicate definitions.
            info = deepcopy(graph.hardware[owner].get('hardware_information') or {})
            for key in ('communication_capabilities', 'communication_controllers'):
                if key in info: info[key] = [x for x in info[key] if technology_id(x['technology']) != tech]
            if info != (graph.hardware[owner].get('hardware_information') or {}):
                update_object('HardwareNode', owner, {'hardware_information': info, 'modified_by': actor})
            for kind, values in [('CommunicationCapability', [cap]), ('CommunicationController', controllers)]:
                for item in values:
                    item['provenance'] = {**item.get('provenance', {}), **provenance}
                    save_resource(kind, item)
            for ref, assignment in assignments.items():
                original = interfaces[ref]
                update_object('HardwareNetworkInterface', ref, {'controller_ref': assignment['controller_ref'],
                    'channel_index': assignment['channel_index'], 'modified_by': actor})
                # Preserve connector identity, direction and its existing network.
                if original.get('physical_port_ref'):
                    projected = {**original, **{k: assignment[k] for k in ('controller_ref', 'channel_index')}}
                    current = next((p for p in graph.find_ports(owner) if p['hardware_interface_ref'] == ref), {})
                    save_resource('PhysicalPort', {**current, 'controller_ref': assignment['controller_ref'],
                        'channel_index': assignment['channel_index'], 'provenance': {**current.get('provenance', {}), **provenance}})
                    if projected.get('network_ref'):
                        persist_port_resources(ModelGraphService.load(), projected, actor, workload_id)
            goal.update(status='PLAN_STALE', authorization=None, pending_decision=None)
            goal.pop('followup_authorization', None)
            journal(goal, 'HARDWARE_FACTS_CONFIRMED', hardware_ref=owner, technology=tech,
                capability_id=cap['id'], controller_ids=[c['id'] for c in controllers], assignments=value['assignments'], evidence=value['evidence'])
            save_goal(goal)
            flush_model_changes(actor=actor, reason='Bestätigte Hardwarefakten des Anschlussauftrags')
    except Exception:
        unit.model_changed = dirty
        raise
    return {'workload_id': workload_id, 'status': 'PLAN_STALE', 'model_revision': ModelGraphService.load().revision}
