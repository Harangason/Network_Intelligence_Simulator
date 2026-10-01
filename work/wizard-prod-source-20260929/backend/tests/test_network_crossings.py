from copy import deepcopy

from backend.engineering.network_crossings import with_wire_crossings
from backend.engineering.network_scene import build_network_scene, model_signature, _spread_coordinates


def wire(bus, *pairs):
    return {'id': bus, 'path': '', 'branches': [{'nodeId': f'{bus}-{i}', 'portId': f'{bus}-{i}', 'path': '',
            'points': [{'x': x, 'y': y} for x, y in points]} for i, points in enumerate(pairs)]}


def test_crossing_uses_bridge_and_gap_without_modifying_connection_points():
    scene = {'buses': [wire('A', [(0, 50), (100, 50)]), wire('B', [(50, 0), (50, 100)])]}
    before = deepcopy(scene)
    result = with_wire_crossings(scene)
    assert result['wireBridges'] == [{'busId': 'A', 'branch': 0, 'path': 'M 44 50 A 6 6 0 0 1 56 50'}]
    assert result['buses'][0]['branches'][0]['displayPath'] == 'M 0 50 L 44 50 M 56 50 L 100 50'
    assert scene == before
    assert result == with_wire_crossings(result)


def test_same_bus_junctions_do_not_get_jumps_and_reversed_paths_keep_endpoints():
    scene = {'buses': [wire('A', [(0, 50), (100, 50)], [(50, 0), (100, 0)], [(100, 100), (100, 100)])]}
    assert with_wire_crossings(scene)['wireBridges'] == []
    scene = {'buses': [wire('A', [(100, 50), (0, 50)]), wire('B', [(50, 0), (50, 100)])]}
    result = with_wire_crossings(scene)
    assert result['buses'][0]['branches'][0]['displayPath'] == 'M 100 50 L 56 50 M 44 50 L 0 50'


def test_close_crossings_merge_and_vertical_t_touch_gets_a_vertical_jump():
    scene = {'buses': [wire('A', [(0, 50), (100, 50)]), wire('B', [(50, 0), (50, 100)]), wire('C', [(58, 0), (58, 100)])]}
    assert with_wire_crossings(scene)['wireBridges'] == [{'busId': 'A', 'branch': 0, 'path': 'M 44 50 A 10 6 0 0 1 64 50'}]
    scene = {'buses': [wire('A', [(0, 50), (50, 50)]), wire('B', [(50, 0), (50, 100)])]}
    bridges = with_wire_crossings(scene)['wireBridges']
    assert all(b['busId'] == 'B' and b['path'] == 'M 50 44 A 6 6 0 0 1 50 56' for b in bridges)
    assert len(bridges) == 1


def test_port_spreading_does_not_collapse_clamped_ports():
    assert _spread_coordinates([-100, -80, -60, -40], 18, 178) == [18, 42, 66, 90]
    assert _spread_coordinates([1000, 2000, 3000, 4000], 18, 178) == [106, 130, 154, 178]


def test_many_ports_on_existing_small_ecu_stay_separate_and_manual_port_is_preserved():
    nodes = [{'id': 'ECU', 'name': 'ECU', 'kind': 'ecu', 'ports': []}]
    edges = []
    for i in range(12):
        network, port = f'bus-{12-i}', f'p{i}'
        nodes[0]['ports'].append({'id': port, 'bus': 'lin', 'physicalNetworkId': network})
        nodes.append({'id': f'S{i}', 'name': f'S{i}', 'kind': 'sensor', 'systemOwnerId': 'ECU',
                      'ports': [{'id': f's{i}', 'bus': 'lin', 'physicalNetworkId': network}]})
        edges.append({'id': f'e{i}', 'source': 'ECU', 'target': f'S{i}', 'sourcePort': port,
                      'targetPort': f's{i}', 'physicalNetworkId': network, 'bus': 'lin'})
    original = {'nodes': nodes, 'edges': edges}
    initial = build_network_scene(original)
    owner = initial['nodes'][0]
    positions = {'ECU': {'x': owner['x'], 'y': owner['y'], 'width': 196, 'height': 104}}
    scene = build_network_scene(initial, positions=positions)
    ports = scene['nodes'][0]['ports']
    assert len({p['offset'] for p in ports}) == 12
    assert all(0 <= p['offset'] <= 1 for p in ports)
    positions['ECU']['ports'] = {'p1': {'side': 'left', 'offset': .33}}
    manual = build_network_scene(scene, positions=positions)
    port = next(p for p in manual['nodes'][0]['ports'] if p['id'] == 'p1')
    assert (port['side'], port['offset']) == ('left', .33)
    assert model_signature(manual) == model_signature(original)
