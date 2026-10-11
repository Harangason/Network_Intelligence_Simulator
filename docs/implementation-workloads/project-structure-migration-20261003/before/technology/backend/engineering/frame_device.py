"""Plan explicit device creation within an existing functional system frame."""
from copy import deepcopy
from uuid import uuid4

from .models import EngineeringValidationError


DEVICE_TYPES = {'ecu': 'ECU', 'sensor': 'SensorController', 'actuator': 'ActuatorController'}


def plan_frame_device(state: dict, payload: dict, hardware: list[dict]) -> dict:
    from .structure_rules import normalize_hardware_name

    kind = payload.get('kind')
    raw_name = payload.get('name')
    if kind not in DEVICE_TYPES:
        raise EngineeringValidationError('Bitte ECU, Sensor oder Aktor wählen.')
    if not isinstance(raw_name, str) or not raw_name.strip() or len(raw_name.strip()) > 160:
        raise EngineeringValidationError('Bitte einen Gerätenamen mit 1 bis 160 Zeichen eingeben.')
    name = normalize_hardware_name(raw_name.strip())
    if any(str(h['name']).casefold() == name.casefold() for h in hardware):
        raise EngineeringValidationError('Ein Gerät mit diesem Namen existiert bereits. Bitte einen eindeutigen Namen wählen.')
    topology = deepcopy(state['topology'])
    scene = topology.get('scene') or {}
    frame = next((f for f in scene.get('frames', []) if f['id'] == payload.get('frame_id')), None)
    nodes = {n['id']: n for n in topology['nodes']}
    owner = nodes.get(frame['id']) if frame else None
    canonical = next((h for h in hardware if str(h['id']) == str((owner or {}).get('engineeringId'))), None)
    if not frame or not canonical or owner.get('kind') != 'ecu':
        raise EngineeringValidationError('Der Systemrahmen besitzt kein gültiges Steuergerät. Bitte die Ansicht neu laden.')
    cluster = next((c for c in scene.get('clusters', []) if c['id'] == frame.get('clusterId')), None)
    if not cluster:
        raise EngineeringValidationError('Der Zielcluster wurde nicht gefunden. Bitte die Ansicht neu laden.')

    node_id = 'node-' + uuid4().hex
    identity = {'topology_id': 'studio-network', 'topology_node_id': node_id,
                'system_owner_id': str(canonical['id']), 'system_owner_source': 'network-editor',
                'cluster_id': cluster['id'], 'cluster_name': cluster['label'], 'cluster_source': 'network-editor'}
    # Functional membership does not establish the new device's physical position.
    data = {'name': name, 'device_type': DEVICE_TYPES[kind], 'domain': canonical.get('domain'),
            'identity': identity, 'provenance': {'origin': 'network-editor-frame', 'frame_id': frame['id']}}
    members = [nodes[n] for n in frame['memberIds']]
    node = {'id': node_id, 'name': name, 'kind': kind, 'ports': [],
            'systemOwnerId': str(canonical['id']), 'systemOwnerSource': 'network-editor',
            'clusterId': cluster['id'], 'clusterName': cluster['label'],
            'x': frame['left'] + 20, 'y': max(n['y'] + n['height'] for n in members) + 28,
            'width': 180, 'height': 104}
    # Preserve existing card positions; make room below this frame if necessary.
    positions = {n['id']: {key: n[key] for key in ('x', 'y', 'width', 'height')} for n in nodes.values()}
    bottom = node['y'] + node['height'] + 26
    for other in sorted(scene['frames'], key=lambda f: f['top']):
        if (other['id'] == frame['id'] or other['top'] < frame['top'] or
                other['left'] >= frame['left'] + frame['width'] or other['left'] + other['width'] <= frame['left']):
            continue
        shift = max(0, bottom + 40 - other['top'])
        if not shift:
            break
        for identifier in other['memberIds']:
            positions[identifier]['y'] += shift
        bottom = other['top'] + shift + other['height']
    positions[node_id] = {key: node[key] for key in ('x', 'y', 'width', 'height')}
    topology['nodes'].append(node)
    return {'hardware': data, 'node': node, 'topology': topology, 'positions': positions, 'frame': frame}
