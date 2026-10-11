from contextlib import nullcontext
from copy import deepcopy
import json

import pytest

from backend.engineering.bus_settings import branch_capacity, normalize_bus_limits, limits_from_prompt
from backend.engineering.network_scene import build_network_scene, bus_junctions, model_signature
from backend.engineering.workflow import service as workflow
from backend.engineering.agent_tools import wizard_generation as wizard


def fixture_topology():
    nodes = [{'id': name, 'name': name, 'kind': kind, 'ports': [], 'x': 0, 'y': 0}
             for name, kind in [('Gateway', 'gateway'), ('Motor', 'ecu'), ('Getriebe', 'ecu'), ('Temperatur', 'sensor'), ('Ventil', 'actuator')]]
    edges = []
    by_id = {n['id']: n for n in nodes}
    for left, right, network, bus in [('Gateway', 'Motor', 'Antrieb_01', 'can_fd'), ('Gateway', 'Getriebe', 'Antrieb_01', 'can_fd'), ('Motor', 'Temperatur', 'Motor-LIN', 'lin'), ('Motor', 'Ventil', 'Motor-LIN', 'lin')]:
        for name in (left, right):
            port = {'id': name + network, 'bus': bus, 'physicalNetworkId': network, 'hardwareInterfaceId': name + network}
            if port not in by_id[name]['ports']:
                by_id[name]['ports'].append(port)
        edges.append({'id': left+right, 'source': left, 'target': right, 'sourcePort': left+network, 'targetPort': right+network, 'bus': bus, 'physicalNetworkId': network})
    prompt = '- Systemcluster-Graph: ' + json.dumps([{'cluster_id': 'antrieb', 'label': 'Antrieb', 'controllers': [{'ecu': 'Motor', 'sensors': ['Temperatur'], 'actuators': ['Ventil']}, {'ecu': 'Getriebe'}]}])
    return {'nodes': nodes, 'edges': edges}, prompt


def test_bus_scene_matches_physical_participants_without_inventing_connections():
    topology, prompt = fixture_topology()
    saved = build_network_scene(topology, prompt)
    assert len(saved['scene']['buses']) == 2
    assert len(saved['scene']['frames']) == 2
    backbone, local = sorted(saved['scene']['buses'], key=lambda b: b['local'])
    assert {b['nodeId'] for b in backbone['branches']} == {'Gateway', 'Motor', 'Getriebe'}
    assert {b['nodeId'] for b in local['branches']} == {'Motor', 'Temperatur', 'Ventil'}
    assert local['frameId'] == 'Motor'
    assert backbone['participantCount'] == local['participantCount'] == 3
    assert saved['edges'] == topology['edges']
    assert 'scene' not in topology
    assert model_signature(saved) == model_signature(topology)
    assert build_network_scene(saved, prompt) == saved


def test_multiple_clusters_never_share_backbone_lanes():
    topology, prompt = fixture_topology()
    graph = json.loads(prompt.split(': ', 1)[1])
    gateway = topology['nodes'][0]
    for name in ['Fahrwerk', 'Komfort', 'Klima']:
        network = name + '_01'
        port = {'id': name+'Port', 'bus': 'can_fd', 'physicalNetworkId': network}
        gateway['ports'].append({'id': 'G'+network, 'bus': 'can_fd', 'physicalNetworkId': network})
        topology['nodes'].append({'id': name, 'name': name, 'kind': 'ecu', 'ports': [port]})
        topology['edges'].append({'id': 'G'+name, 'source': 'Gateway', 'target': name, 'sourcePort': 'G'+network, 'targetPort': port['id'], 'physicalNetworkId': network, 'bus': 'can_fd'})
        graph.append({'cluster_id': name, 'controllers': [{'ecu': name}]})
    scene = build_network_scene(topology, '- Systemcluster-Graph: '+json.dumps(graph))['scene']
    backbones = [bus for bus in scene['buses'] if not bus['local']]
    assert len({bus['branches'][0]['points'][-1]['x'] for bus in backbones}) == len(backbones) == 4


def test_junctions_distinguish_straight_continuations_elbows_and_real_branches():
    def branch(*points):
        return {'points': [{'x': x, 'y': y} for x, y in points]}
    branches = [branch((100, 0), (100, 28), (100, 28)),
                branch((0, 100), (100, 100)), branch((0, 200), (100, 200))]
    assert bus_junctions(branches) == [{'x': 100, 'y': 100}]
    branches.append(branch((200, 200), (100, 200)))
    assert bus_junctions(branches) == [{'x': 100, 'y': 100}, {'x': 100, 'y': 200}]
    assert bus_junctions([]) == []


def test_saved_scene_omits_inline_owner_dots_and_keeps_true_connections():
    topology, prompt = fixture_topology()
    saved = build_network_scene(topology, prompt)
    for bus in saved['scene']['buses']:
        owner = bus['frameId'] or 'Gateway'
        attachment = next(b['points'][-1] for b in bus['branches'] if b['nodeId'] == owner)
        assert attachment not in bus['junctions']
        assert len(bus['junctions']) == 1
        # The 11px rotated glyphs and 2px outline fit between baseline and bus.
        assert bus['label']['x'] - 13 - attachment['x'] >= (6 if bus['local'] else 12)
    assert saved['edges'] == topology['edges']


def test_gateway_ownership_keeps_controller_frame_and_direct_endpoint_visible():
    topology, prompt = fixture_topology()
    topology['nodes'][1]['systemOwnerId'] = 'Gateway'
    topology['nodes'][3]['systemOwnerId'] = 'Gateway'
    saved = build_network_scene(topology)
    frames = {frame['id']: frame for frame in saved['scene']['frames']}
    assert {'Motor', 'Temperatur'} <= frames.keys()
    assert all(node['width'] >= 72 and node['height'] >= 72 for node in saved['nodes'])
    assert saved['edges'] == topology['edges']


def test_agent_keeps_large_specification_and_project_bus_limits():
    from backend.engineering.bus_settings import with_project_limits
    from backend.agent_core.context.agent_context import AgentContext
    from backend.engineering.agent_tools.services import TOOLS
    from backend.engineering.agent_tools.run_status import restore_wizard_continuation_prompt
    prompt = ('Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Lauf-ID: request-12345678\n'
              'per Wizard-Uebernehmen bestaetigt\n' + 'x'*31000)
    frozen = with_project_limits(prompt, {'engineering_wizard_settings': {'bus_participant_limits': {'lin': 128}}})
    assert limits_from_prompt(frozen)['lin'] == 128
    assert with_project_limits(frozen, {'engineering_wizard_settings': {'bus_participant_limits': {'lin': 4}}}) == frozen
    assert AgentContext(active_project_id='test', current_requirement=frozen).current_requirement == frozen
    assert TOOLS['generate_wizard_model'].input_model.model_validate({'prompt': frozen}).prompt == frozen
    restored = restore_wizard_continuation_prompt('Lauf-ID: request-12345678\nWeiter', {'run_id': 'request-12345678', 'agent_prompt': frozen})
    assert frozen in restored


def test_manual_layout_survives_rebuild_without_changing_routing_or_workflow_status():
    topology, prompt = fixture_topology()
    initial = build_network_scene(topology, prompt)
    positions = {'Motor': {'x': 510, 'y': 610, 'width': 196, 'height': 104, 'ports': {'MotorAntrieb_01': {'side': 'right', 'offset': .7}}}}
    saved = build_network_scene(initial, prompt, positions=positions)
    assert next(n for n in saved['nodes'] if n['id'] == 'Motor')['x'] == 510
    assert saved == build_network_scene(saved, prompt, positions=saved['scene']['manualPositions'])
    assert workflow.is_topology_layout_only_change(initial, saved)
    assert model_signature(initial) == model_signature(saved)
    assert next(f for f in initial['scene']['frames'] if f['id']=='Getriebe') == next(f for f in saved['scene']['frames'] if f['id']=='Getriebe')


def test_wire_coordinates_round_trip_and_do_not_change_endpoints_or_model():
    topology, prompt = fixture_topology()
    initial = build_network_scene(topology, prompt)
    bus = next(b for b in initial['scene']['buses'] if b['local'])
    branch = next(b for b in bus['branches'] if b['nodeId'] == 'Temperatur')
    routes = {bus['id']: {'trunkX': branch['points'][-1]['x'] + 48,
                          'branchY': {branch['portId']: branch['points'][-1]['y'] + 30}}}
    saved = build_network_scene(initial, prompt, bus_routes=routes)
    changed = next(b for b in saved['scene']['buses'] if b['id'] == bus['id'])
    for before, after in zip(bus['branches'], changed['branches']):
        assert after['points'][0] == before['points'][0]
        assert after['points'][-1]['x'] == routes[bus['id']]['trunkX']
        assert all(a['x'] == b['x'] or a['y'] == b['y'] for a, b in zip(after['points'], after['points'][1:]))
    assert len(next(b for b in changed['branches'] if b['nodeId'] == 'Temperatur')['points']) == 4
    assert saved['scene']['manualBusRoutes'] == routes
    assert saved == build_network_scene(saved, prompt)
    assert saved['edges'] == topology['edges']
    assert model_signature(saved) == model_signature(initial)
    assert workflow.is_topology_layout_only_change(initial, saved)
    assert build_network_scene(saved, prompt, bus_routes={}) == initial


@pytest.mark.parametrize('routes', [[], {'Motor-LIN': []}, {'Motor-LIN': {'trunkX': float('nan')}},
    {'Motor-LIN': {'trunkX': True}}, {'Motor-LIN': {'trunkX': -1}}, {'Motor-LIN': {'branchY': []}},
    {'Motor-LIN': {'branchY': {'TemperaturMotor-LIN': float('inf')}}}])
def test_invalid_wire_coordinates_rejected(routes):
    topology, prompt = fixture_topology()
    with pytest.raises(ValueError):
        build_network_scene(topology, prompt, bus_routes=routes)


def test_seven_zonal_buses_have_separate_lanes_and_owner_ports():
    topology = {'nodes': [{'id': 'ECU', 'name': 'ECU', 'kind': 'ecu', 'ports': []}], 'edges': []}
    for i, zone in enumerate(['FL', 'FR', 'RL', 'RR', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN']):
        name = f'Sensor{i}'
        # Deliberately shuffled network names must not determine the spatial order.
        network = f'bus-{6-i}'
        topology['nodes'][0]['ports'].append({'id': f'owner{i}', 'bus': 'lin', 'physicalNetworkId': network})
        topology['nodes'].append({'id': name, 'name': name, 'kind': 'sensor', 'systemOwnerId': 'ECU', 'installationZone': zone,
                                 'ports': [{'id': name, 'bus': 'lin', 'physicalNetworkId': network}]})
        topology['edges'].append({'id': name, 'source': 'ECU', 'target': name, 'sourcePort': f'owner{i}', 'targetPort': name, 'bus': 'lin', 'physicalNetworkId': network})
    saved = build_network_scene(topology)
    buses = saved['scene']['buses']
    assert not saved['scene']['routingWarnings']
    xs = sorted(b['branches'][0]['points'][-1]['x'] for b in buses)
    assert min(b-a for a, b in zip(xs, xs[1:])) >= 28
    owner_points = [next(branch['points'][0] for branch in bus['branches'] if branch['nodeId'] == 'ECU') for bus in buses]
    assert len({(p['x'], p['y']) for p in owner_points}) == 7
    for bus in buses:
        owner_branch = next(branch for branch in bus['branches'] if branch['nodeId'] == 'ECU')
        assert owner_branch['points'][0]['x'] == owner_branch['points'][-1]['x']
        x = owner_branch['points'][-1]['x']
        for node in saved['nodes'][1:]:
            assert not node['x'] < x < node['x'] + node['width']


def test_wire_save_and_reset_preserve_versions_and_device_positions(monkeypatch):
    topology, prompt = fixture_topology()
    initial = build_network_scene(topology, prompt)
    state = {'topology': initial, 'context': {'wizard_request': {'prompt': prompt}}, 'versions': {'routing': 7, 'capacity': 4}}
    class Connection:
        def execute(self, query, params):
            if query.startswith('UPDATE'):
                state['topology'] = json.loads(params[0])
            return self
        def fetchone(self):
            return state
    service = workflow.WorkflowStatusService('scene-wire-test')
    monkeypatch.setattr(workflow, 'get_connection', lambda: nullcontext(Connection()))
    monkeypatch.setattr(service, '_get_locked', lambda connection: state)
    token = service.network_view()['edit_tokens']['topology']
    saved = service.prepare_network_view(expected_token=token, bus_routes={'Motor-LIN': {'trunkX': 400}})
    assert saved['versions'] == {'routing': 7, 'capacity': 4}
    with pytest.raises(workflow.WorkflowConflictError):
        service.prepare_network_view(expected_token=token, bus_routes={})
    assert service.network_view() == saved
    with pytest.raises(ValueError):
        service.prepare_network_view(expected_token=saved['edit_tokens']['topology'], bus_routes={'Motor-LIN': {'trunkX': -3}})
    assert service.network_view() == saved
    reset = service.prepare_network_view(expected_token=saved['edit_tokens']['topology'], reset_wires=True)
    assert reset['topology'] == initial


def test_coordinate_only_save_keeps_existing_manual_port_positions(monkeypatch):
    topology, prompt = fixture_topology()
    positions = {'Motor': {'x': 600, 'y': 500, 'ports': {'MotorAntrieb_01': {'side': 'right', 'offset': .7}}}}
    state = {'topology': build_network_scene(topology, prompt, positions=positions), 'context': {'wizard_request': {'prompt': prompt}}}
    class Connection:
        def execute(self, query, params):
            state['topology'] = json.loads(params[0])
    service = workflow.WorkflowStatusService('scene-port-merge-test')
    monkeypatch.setattr(workflow, 'get_connection', lambda: nullcontext(Connection()))
    monkeypatch.setattr(service, '_get_locked', lambda connection: state)
    monkeypatch.setattr(service, 'network_view', lambda: state)
    service.prepare_network_view(positions={'Motor': {'x': 620}})
    assert state['topology']['scene']['manualPositions']['Motor'] == {**positions['Motor'], 'x': 620}
    port = next(p for n in state['topology']['nodes'] if n['id'] == 'Motor' for p in n['ports'] if p['id'] == 'MotorAntrieb_01')
    assert (port['side'], port['offset']) == ('right', .7)


@pytest.mark.parametrize('positions', [{'Motor': 2}, {'Motor': {'width': 0}}, {'Motor': {'x': float('nan')}}, {'Motor': {'ports': []}}, {'Motor': {'ports': {'MotorAntrieb_01': {'side': 'right', 'offset': 2}}}}])
def test_invalid_manual_layout_is_rejected(positions):
    topology, prompt = fixture_topology()
    if positions == {'Motor': {'ports': []}}:
        positions = {'Motor': {'ports': ['invalid']}}
    with pytest.raises(ValueError):
        build_network_scene(topology, prompt, positions=positions)


def test_mismatched_physical_bus_is_rejected():
    topology, prompt = fixture_topology()
    topology['nodes'][0]['ports'][0]['physicalNetworkId'] = 'Other'
    with pytest.raises(ValueError, match='stimmen nicht'):
        build_network_scene(topology, prompt)


def test_persisted_scene_endpoint_is_atomic_conflict_checked_and_read_only_on_get(monkeypatch):
    topology, prompt = fixture_topology()
    state = {'topology': topology, 'context': {'wizard_request': {'prompt': prompt}}, 'versions': {'routing': 3}}
    writes = []
    class Connection:
        def execute(self, query, params):
            if query.startswith('UPDATE'):
                writes.append(query)
                state['topology'] = json.loads(params[0])
            return self
        def fetchone(self):
            return state
    service = workflow.WorkflowStatusService('scene-test')
    monkeypatch.setattr(workflow, 'get_connection', lambda: nullcontext(Connection()))
    monkeypatch.setattr(service, '_get_locked', lambda connection: state)
    old_token = service.network_view()['edit_tokens']['topology']
    assert not writes
    saved = service.prepare_network_view(expected_token=old_token)
    assert len(writes) == 1
    assert saved['topology']['scene']['buses']
    assert saved['versions'] == {'routing': 3}
    assert service.network_view() == saved
    assert len(writes) == 1
    with pytest.raises(workflow.WorkflowConflictError):
        service.prepare_network_view(expected_token=old_token, positions={'Motor': {'x': 900}})
    assert len(writes) == 1


def test_saving_removed_last_connection_or_node_drops_obsolete_drawing(monkeypatch):
    topology, prompt = fixture_topology()
    state = {'topology': build_network_scene(topology, prompt), 'parameters': {},
             'context': {'wizard_request': {'prompt': prompt}}, 'statuses': {'network_editor': 'COMPLETE'}}
    class Connection:
        def execute(self, query, params):
            state['topology'] = json.loads(params[0])
    service = workflow.WorkflowStatusService('delete-scene-test')
    monkeypatch.setattr(workflow, 'get_connection', lambda: nullcontext(Connection()))
    monkeypatch.setattr(service, '_get_locked', lambda connection: deepcopy(state))
    monkeypatch.setattr(service, '_topology_artifact_check', lambda topology: {'status': 'IN_PROGRESS'})
    monkeypatch.setattr(service, 'mark_changed', lambda *a, **kw: state)
    without_edges = {**state['topology'], 'edges': []}
    saved = service.save_topology(without_edges)
    assert saved['topology']['nodes']
    assert saved['topology']['scene']['buses'] == []
    saved = service.save_topology({**saved['topology'], 'nodes': []})
    assert saved['topology'] == {'nodes': [], 'edges': []}


@pytest.mark.parametrize('value', [1, -1, 2.5, True, 100001, '64'])
def test_invalid_bus_limit_is_rejected(value):
    with pytest.raises(ValueError):
        normalize_bus_limits({'lin': value})


def test_defaults_support_more_than_fifty_lin_nodes_and_no_hidden_six_controller_limit():
    limits = normalize_bus_limits({'LIN': 128, 'CAN_FD': 0})
    assert branch_capacity(limits, 'lin') == 127
    assert branch_capacity(limits, 'CAN-FD') >= 1000
    assert branch_capacity(normalize_bus_limits(), 'detected:ethernet') == 255
    prompt = '- Netzarchitektur-ID: gateway_ecu_segments\n- Systemcluster-Graph: ' + json.dumps([{'bus_name': 'Antrieb_01', 'controllers': [{'ecu': f'ECU{i}'} for i in range(9)]}])
    memberships = wizard._confirmed_segment_memberships(prompt)
    assert {value[0][0] for value in memberships.values()} == {'Antrieb_01-S01'}


def test_local_limits_count_each_bus_type_separately_and_include_owner():
    graph = [{'bus_name': 'Antrieb_01', 'controllers': [{'ecu': 'Motor', 'sensors': [f'S{i}' for i in range(140)]}]}]
    prompt = '- Bus-Teilnehmergrenzen: {"lin":65,"can_fd":128}\n- Systemcluster-Graph: ' + json.dumps(graph)
    technologies = {f's{i}': 'lin' if i % 2 == 0 else 'can_fd' for i in range(140)}
    memberships = wizard._confirmed_local_io_memberships(prompt, technologies)
    def segment(index):
        return wizard._local_io_physical_network(technologies[f's{index}'], memberships, {'name': f'S{index}'}, {'name': 'Motor'})[0]
    assert segment(126).endswith('lin-S01')
    assert segment(128).endswith('lin-S02')
    assert segment(139).endswith('can-fd-S01')
    assert limits_from_prompt(prompt)['lin'] == 65
