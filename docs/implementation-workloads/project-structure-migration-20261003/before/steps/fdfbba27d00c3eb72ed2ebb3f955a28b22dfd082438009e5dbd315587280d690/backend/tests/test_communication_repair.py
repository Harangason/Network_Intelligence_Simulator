"""Reconnection preserves communication intent, and never guesses a cluster move."""
from copy import deepcopy
import os
import pytest

from backend.engineering.communication_repair import RepairPlanner, KINDS, public_plan


def sample(*, system=False):
    objects = {k: [] for k in KINDS}
    def add(kind, identifier, **fields):
        row = {'id': identifier, 'name': identifier, 'object_type': kind, 'version': 1, **fields}
        objects[kind].append(row)
        return row
    for node in ('producer', 'receiver'):
        add('HardwareNode', node, device_type='Gateway' if system and node == 'receiver' else 'ECU', identity={'system_owner_id': 'receiver'})
        add('Function', node + '-function', hardware_node_id=node)
        add('Interface', node + '-interface', function_id=node + '-function', hardware_node_id=node, interface_type='CAN_FD')
    add('HardwareNetworkInterface', 'old-port', hardware_node_id='producer', technology='CAN_FD', network_ref='', channel_index=1)
    for node in ('producer', 'receiver'):
        add('HardwareNetworkInterface', node + '-port', hardware_node_id=node, technology='CAN_FD', network_ref='replacement', channel_index=2)
    message = add('Message', 'message', interface_id='producer-interface', hardware_interface_id='old-port', dlc=2, cycle_ms=20,
        message_id_hex='0x100', configuration={'explicit': True, 'communication_contract': {'consumer': 'receiver'}})
    add('Signal', 'signal', message_id='message', start_bit=1, length_bits=10, factor=0.1, offset=0,
        data_type='unsigned', endianness='little_endian', minimum=0, maximum=100)
    topology = {'nodes': [{'id': node, 'engineeringId': node, 'name': node, 'kind': 'gateway' if system and node == 'receiver' else 'ecu',
        'ports': [{'id': node + '-drawing', 'hardwareInterfaceId': node + '-port', 'engineeringId': node + '-port', 'physicalNetworkId': 'replacement', 'bus': 'can_fd'}]}
        for node in ('producer', 'receiver')],
        'edges': [{'id': 'new-edge', 'source': 'producer', 'target': 'receiver', 'sourcePort': 'producer-drawing', 'targetPort': 'receiver-drawing', 'bus': 'can_fd', 'physicalNetworkId': 'replacement'}]}
    state = {'topology': topology, 'parameters': {'networks': [{'id': net, 'name': net, 'technology': 'CAN_FD', 'bitrate': 500000, 'data_bitrate': 2000000} for net in ('original', 'replacement')]}}
    route = {'id': 'route', 'name': 'Existing communication', 'route_code': 'RT-OLD', 'revision': 1, 'status': 'OUTDATED', 'approval_state': 'PENDING',
        'source': {'node_id': 'producer', 'interface_id': 'producer-interface', 'port_id': 'old-port', 'network_id': 'original', 'protocol': 'CAN_FD'},
        'destinations': [{'node_id': 'receiver', 'interface_id': 'receiver-interface', 'port_id': 'receiver-port', 'network_id': 'replacement', 'protocol': 'CAN_FD'}],
        'payload': {'message_id': 'message', 'signal_ids': ['signal']}, 'route': {'hops': ['producer', 'receiver'], 'gateways': [], 'transformations': [], 'priority': 'HIGH'},
        'timing': {'cycle_time_ms': 20, 'timeout_ms': 100, 'freshness_ms': 100, 'max_latency_ms': 20, 'jitter_limit_ms': 5},
        'routing_policy': {'routing_type': 'UNICAST', 'redundancy': 'NONE', 'conditions': []}}
    history = [{'port_id': 'old-port', 'network_id': 'original', 'node_id': 'producer'},
        {'port_id': 'former-receiver', 'network_id': 'original', 'node_id': 'receiver'}]
    return state, objects, [route], history


def test_communication_repair_unique_replacement_preserves_authored_intent():
    data = sample(); before = deepcopy(data)
    plan = RepairPlanner(*data).build()
    assert data == before
    assert len(plan['groups']) == 1
    group = plan['groups'][0]
    assert group['status'] == 'QUESTION'
    option = group['options'][0]
    assert option['message_changes'] == [{'id': 'message', 'data': {'hardware_interface_id': 'producer-port'}, 'expected_version': 1}]
    change = option['route_changes'][0]
    assert change['source']['interface_id'] == 'producer-interface'
    assert change['source']['port_id'] == 'producer-port'
    assert change['destinations'][0]['node_id'] == 'receiver'
    assert change['edge_ids'] == ['new-edge']
    assert not {'payload', 'timing', 'routing_policy'} & set(change)
    assert 'route_changes' not in public_plan(plan)['groups'][0]['options'][0]


def test_communication_repair_system_to_cluster_requires_explicit_choice():
    state, objects, routes, history = sample()
    objects['HardwareNode'].append({'id': 'system', 'name': 'System', 'object_type': 'HardwareNode', 'device_type': 'Gateway'})
    history.append({'port_id': 'former-system', 'network_id': 'original', 'node_id': 'system'})
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert group['status'] == 'QUESTION'
    assert 'System-/Gateway' in group['options'][0]['questions'][0]
    assert 'innerhalb eines Clusters' in group['options'][0]['questions'][0]


def test_communication_repair_never_uses_unreachable_receiver_or_other_device_port():
    state, objects, routes, history = sample()
    state['topology']['edges'] = []
    assert all(g['status'] == 'BLOCKED' and not g['options'] for g in RepairPlanner(state, objects, routes, history).build()['groups'])
    state, objects, routes, history = sample()
    objects['HardwareNetworkInterface'][1]['hardware_node_id'] = 'receiver'
    assert RepairPlanner(state, objects, routes, history).build()['groups'][0]['status'] == 'BLOCKED'


def test_communication_repair_deleted_gateway_port_still_requires_system_question():
    state, objects, routes, history = sample()
    objects['HardwareNode'].append({'id': 'system', 'name': 'System', 'object_type': 'HardwareNode', 'device_type': 'Gateway'})
    routes[0]['route']['gateways'] = [{'node_id': 'system'}]
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert group['status'] == 'QUESTION'
    assert 'System-/Gateway' in group['options'][0]['questions'][0]


def test_communication_repair_recreated_edge_with_same_ports_is_repaired():
    state, objects, routes, history = sample()
    objects['Message'][0]['hardware_interface_id'] = 'producer-port'
    routes[0]['source'].update(port_id='producer-port', network_id='replacement')
    routes[0]['validation'] = {'warnings': [{'code': 'PHYSICAL_PATH_REMOVED'}]}
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert group['status'] == 'QUESTION'
    assert group['options'][0]['route_changes'][0]['edge_ids'] == ['new-edge']
    assert not group['options'][0]['message_changes']


def test_communication_repair_healthy_bindings_and_unused_ports_are_ignored():
    state, objects, routes, history = sample()
    objects['Message'][0]['hardware_interface_id'] = 'producer-port'
    routes[0]['source'].update(port_id='producer-port', network_id='replacement')
    assert not RepairPlanner(state, objects, routes, history).build()['groups']


def test_saved_signal_path_replacement_is_detected_even_when_endpoints_still_reachable():
    state, objects, routes, history = sample()
    objects['Message'][0]['hardware_interface_id'] = 'producer-port'
    routes[0]['source'].update(port_id='producer-port', network_id='replacement')
    routes[0]['route']['physical_paths'] = [{'ports': ['producer-port', 'receiver-port'], 'edges': ['removed-edge']}]
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert group['options'][0]['route_changes'][0]['route']['physical_paths'][0]['edges'] == ['new-edge']
    assert group['status'] == 'QUESTION'


def test_saved_path_requires_one_exact_wire_and_allows_parallel_connections():
    state, objects, routes, history = sample()
    state['topology']['edges'].append({**state['topology']['edges'][0], 'id': 'parallel-edge'})
    planner = RepairPlanner(state, objects, routes, history)
    path = {'ports': ['producer-port', 'receiver-port'], 'edges': ['new-edge']}
    assert planner.path_is_current(path)
    assert not planner.path_is_current({**path, 'edges': ['deleted-edge']})
    assert not planner.path_is_current({**path, 'edges': ['new-edge', 'parallel-edge']})
    assert not planner.path_is_current({'ports': ['missing-port'], 'edges': []})


def test_communication_repair_orphan_message_needs_recipient_intent():
    state, objects, _, history = sample()
    group = RepairPlanner(state, objects, [], history).build()['groups'][0]
    assert group['status'] == 'BLOCKED'
    assert 'Empfängerroute' in group['reason']


def test_communication_repair_id_collision_blocks_without_changing_encodings():
    state, objects, routes, history = sample()
    objects['Message'].append({**objects['Message'][0], 'id': 'occupied', 'hardware_interface_id': 'receiver-port', 'interface_id': 'receiver-interface'})
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert group['status'] == 'BLOCKED'
    assert '0x100' in group['reason']
    assert all(m['message_id_hex'] == '0x100' for m in objects['Message'])


def test_communication_repair_only_gateway_can_bridge_channels():
    state, objects, routes, history = sample()
    objects['HardwareNode'].append({'id': 'remote', 'name': 'Remote', 'object_type': 'HardwareNode', 'device_type': 'ECU'})
    for node in ('receiver', 'remote'):
        objects['HardwareNetworkInterface'].append({'id': node + '-remote', 'hardware_node_id': node, 'technology': 'CAN_FD', 'network_ref': 'remote', 'name': node})
    state['parameters']['networks'].append({'id': 'remote', 'name': 'remote'})
    state['topology']['nodes'][1]['ports'].append({'id': 'bridge', 'hardwareInterfaceId': 'receiver-remote', 'physicalNetworkId': 'remote'})
    state['topology']['nodes'].append({'id': 'remote', 'engineeringId': 'remote', 'ports': [{'id': 'remote', 'hardwareInterfaceId': 'remote-remote', 'physicalNetworkId': 'remote'}]})
    state['topology']['edges'].append({'id': 'remote-edge', 'sourcePort': 'bridge', 'targetPort': 'remote', 'physicalNetworkId': 'remote'})
    planner = RepairPlanner(state, objects, routes, history)
    assert not planner.paths('producer-port', 'remote-remote')
    objects['HardwareNode'][1]['device_type'] = 'Gateway'
    assert RepairPlanner(state, objects, routes, history).paths('producer-port', 'remote-remote')[0]['edges'] == ['new-edge', 'remote-edge']


SQL = pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Separate test database required')


def sql_sample(*, question=False):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.project_context import activate_project
    from backend.engineering.repository import create_object, update_object
    from backend.engineering.routing.repository import create_route
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.db import get_connection
    from psycopg.types.json import Jsonb
    client = _client()
    project = client.environ_base['HTTP_X_PROJECT_ID']
    activate_project(project)
    state, objects, routes, _ = sample()
    ids = {}
    def mapped(value):
        if isinstance(value, dict): return {k: mapped(v) for k, v in value.items()}
        if isinstance(value, list): return [mapped(v) for v in value]
        return ids.get(value, value) if isinstance(value, str) else value
    # Existing historical channel -> removal -> replacement are real audited versions.
    for kind in KINDS:
        for obj in objects[kind]:
            data = mapped({k: v for k, v in obj.items() if k not in {'id', 'version', 'object_type'}})
            if obj['id'] == 'old-port': data['network_ref'] = 'original'
            created = create_object(kind, data)
            ids[obj['id']] = str(created['id'])
    old = update_object('HardwareNetworkInterface', ids['old-port'], {'network_ref': ''})
    if question:
        gateway = create_object('HardwareNode', {'name': 'System', 'device_type': 'Gateway'})
        create_object('HardwareNetworkInterface', {'name': 'Old system', 'hardware_node_id': str(gateway['id']), 'technology': 'CAN_FD', 'network_ref': 'original'})
    # Explicit shared owner in fixture uses a forward reference; make it canonical.
    for node in ('producer', 'receiver'):
        update_object('HardwareNode', ids[node], {'identity': {'system_owner_id': ids['receiver']}})
    route = create_route(mapped({k: v for k, v in routes[0].items() if k not in {'id', 'revision', 'route_code', 'status'}}))
    ids['route'] = str(route['id'])
    workflow = WorkflowStatusService(project)
    workflow.get()
    # Test fixture stores the already edited editor state; no production project touched.
    with get_connection() as connection:
        connection.execute('UPDATE engineering_workflow_projects SET topology=%s, parameters=%s WHERE project_id=%s',
            (Jsonb(mapped(state['topology'])), Jsonb(state['parameters']), project))
        connection.execute("UPDATE engineering_routing_entries SET status='OUTDATED' WHERE project_id=%s AND id=%s", (project, ids['route']))
    return client, ids


@SQL
def test_communication_repair_sql_apply_reload_idempotence_and_preserved_intent():
    client, ids = sql_sample()
    base = '/api/engineering/'
    before = {kind: client.get(base + kind + '/' + ids[key]).get_json() for kind, key in
        [('messages', 'message'), ('signals', 'signal'), ('functions', 'producer-function'), ('interfaces', 'producer-interface')]}
    old_route = client.get(base + 'routing/' + ids['route']).get_json()
    plan = client.post(base + 'workflow/communication-repair/preview', json={}).get_json()
    assert plan['groups'][0]['status'] == 'QUESTION', plan
    group = plan['groups'][0]
    result = client.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'choices': {group['id']: group['options'][0]['id']}})
    assert result.status_code == 200, result.get_json()
    assert result.get_json()['applied']
    for kind, key in [('signals', 'signal'), ('functions', 'producer-function'), ('interfaces', 'producer-interface')]:
        assert client.get(base + kind + '/' + ids[key]).get_json() == before[kind]
    message = client.get(base + 'messages/' + ids['message']).get_json()
    assert message['hardware_interface_id'] == ids['producer-port']
    for field in ('interface_id', 'configuration', 'dlc', 'cycle_ms', 'message_id_hex'):
        assert message[field] == before['messages'][field]
    updated = client.get(base + 'routing/' + ids['route']).get_json()
    for field in ('payload', 'timing', 'routing_policy'):
        assert updated[field] == old_route[field]
    assert updated['source']['port_id'] == ids['producer-port']
    assert updated['approval_state'] == 'PENDING' and updated['validation']['valid']
    assert ids['message'] in client.get(base + 'hardware-interfaces/' + ids['producer-port']).get_json()['message_refs']
    again = client.post(base + 'workflow/communication-repair/preview', json={}).get_json()
    assert not again['groups'], again
    assert client.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'automatic': True}).status_code == 409


@SQL
def test_communication_repair_sql_system_question_never_auto_applies():
    client, ids = sql_sample(question=True)
    base = '/api/engineering/'
    before = client.get(base + 'messages/' + ids['message']).get_json()
    plan = client.post(base + 'workflow/communication-repair/preview', json={}).get_json()
    assert plan['groups'][0]['status'] == 'QUESTION', plan
    response = client.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'automatic': True})
    assert response.status_code == 200 and not response.get_json()['applied']
    assert client.get(base + 'messages/' + ids['message']).get_json() == before
    group = plan['groups'][0]
    response = client.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'choices': {group['id']: group['options'][0]['id']}})
    assert response.status_code == 200 and response.get_json()['applied'], response.get_json()


@SQL
def test_communication_repair_sql_failure_rolls_back_and_cross_project_token_rejected(monkeypatch):
    from backend.engineering.routing.validation import RoutingValidator
    from backend.tests.test_engineering_api import _client
    client, ids = sql_sample()
    base = '/api/engineering/'
    before = client.get(base + 'messages/' + ids['message']).get_json()
    workflow = client.get(base + 'workflow').get_json()
    plan = client.post(base + 'workflow/communication-repair/preview', json={}).get_json()
    monkeypatch.setattr(RoutingValidator, 'validate', lambda *a, **kw: {'valid': False, 'errors': [{'message': 'Injected validation failure'}]})
    group = plan['groups'][0]
    result = client.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'choices': {group['id']: group['options'][0]['id']}})
    assert result.status_code == 400, result.get_json()
    assert client.get(base + 'messages/' + ids['message']).get_json() == before
    assert client.get(base + 'workflow').get_json()['topology'] == workflow['topology']
    other = _client()
    assert other.post(base + 'workflow/communication-repair/apply', json={'token': plan['token'], 'automatic': True}).status_code == 409

def test_repair_ignores_superseded_route_rows_but_retains_latest_broken_intent():
    state, objects, routes, history = sample()
    routes.append({**deepcopy(routes[0]), 'id': 'historic', 'revision': 0, 'source': {'node_id': 'missing'}})
    group = RepairPlanner(state, objects, routes, history).build()['groups'][0]
    assert [r['id'] for r in group['routes']] == ['route']
    routes.append({**deepcopy(routes[0]), 'id': 'newest', 'revision': 2, 'status': 'REJECTED'})
    assert not RepairPlanner(state, objects, routes, history).routes


def forwarding_sample():
    state, objects, routes, history = sample()
    for p in objects['HardwareNetworkInterface']: p['technology'] = 'Ethernet'
    for i in objects['Interface']: i['interface_type'] = 'Ethernet'
    for e in [routes[0]['source'], *routes[0]['destinations']]: e['protocol'] = 'ETHERNET'
    for net in state['parameters']['networks']: net['technology'] = 'ETHERNET'
    relay = {'id': 'relay', 'name': 'Relay ECU', 'device_type': 'ECU', 'object_type': 'HardwareNode', 'version': 1, 'identity': {}}
    objects['HardwareNode'].append(relay)
    state['parameters']['networks'].append({'id': 'backbone', 'name': 'ETH_Backbone_01', 'technology': 'ETHERNET'})
    objects['HardwareNetworkInterface'][-1]['network_ref'] = 'backbone'
    for side, net in [('in', 'replacement'), ('out', 'backbone')]:
        objects['HardwareNetworkInterface'].append({'id': 'relay-'+side, 'name': 'relay-'+side, 'hardware_node_id': 'relay', 'technology': 'Ethernet', 'network_ref': net, 'version': 1})
    state['topology']['nodes'].append({'id': 'relay', 'engineeringId': 'relay', 'kind': 'ecu', 'name': 'Relay ECU', 'ports': [
        {'id': 'relay-'+s, 'hardwareInterfaceId': 'relay-'+s, 'physicalNetworkId': n, 'bus': 'automotive_ethernet'} for s,n in [('in','replacement'),('out','backbone')]]})
    state['topology']['nodes'][1]['ports'][0]['physicalNetworkId'] = 'backbone'
    state['topology']['edges'] = [{'id':'local', 'source':'producer','target':'relay','sourcePort':'producer-drawing','targetPort':'relay-in','physicalNetworkId':'replacement','bus':'automotive_ethernet'},
        {'id':'remote','source':'relay','target':'receiver','sourcePort':'relay-out','targetPort':'receiver-drawing','physicalNetworkId':'backbone','bus':'automotive_ethernet'}]
    return state, objects, routes, history


def test_new_way_requires_confirmed_direction_and_exact_port_pair_on_plain_ecu():
    from backend.engineering.communication_repair import complete_plan
    from backend.engineering.routing.forwarding import forwarding_permitted
    state, objects, routes, history = forwarding_sample()
    before = deepcopy(objects)
    p = RepairPlanner(state, objects, routes, history)
    assert not p.paths('producer-port', 'receiver-port')
    group = complete_plan(p)['groups'][0]
    option = next(o for o in group['options'] if o['action'] == 'adopt')
    assert group['status'] == 'QUESTION'
    change = option['hardware_changes'][0]
    assert change['id'] == 'relay'
    assert 'Weiterleitung' in ' '.join(option['questions'])
    assert option['comparison'][0]['before'] != option['comparison'][0]['after']
    objects['HardwareNode'][-1].update(change['data'])
    p = RepairPlanner(state, objects, routes, history)
    assert p.paths('producer-port', 'receiver-port')
    assert not p.paths('receiver-port', 'producer-port'), 'Opposite direction was not approved'
    relay = objects['HardwareNode'][-1]
    assert relay['device_type'] == 'ECU'
    source,target = p.active['relay-in'],p.active['relay-out']
    assert forwarding_permitted(relay,source,target)
    assert not forwarding_permitted(relay,source,{**target,'network_ref':'different'})
    assert before['Message'] == objects['Message'] and before['Signal'] == objects['Signal']


def test_restore_uses_recorded_gateway_and_updates_all_routes_using_moved_ports():
    from backend.engineering.communication_repair import complete_plan
    state, objects, routes, history = sample(system=True)
    routes[0]['route']['gateways'] = [{'node_id': 'receiver', 'name': 'receiver'}]
    group = complete_plan(RepairPlanner(state,objects,routes,history))['groups'][0]
    restored = next(o for o in group['options'] if o['action']=='restore')
    assert restored['create_ports'], 'Missing historical gateway channel must be an explicit new resource'
    assert restored['port_changes'][0]['data']['network_ref']=='original'
    assert restored['comparison'][0]['after']
    assert restored['route_changes'][0]['source']['network_id']=='original'
    assert any('Planungsbedarf' in q for q in restored['questions'])


def test_restoration_checks_explicit_frame_collisions_after_channel_moves():
    state, objects, routes, history = sample()
    objects['Message'][0]['hardware_interface_id']='old-port'
    objects['HardwareNetworkInterface'][0]['network_ref']='original'
    objects['Message'].append({**deepcopy(objects['Message'][0]), 'id':'occupied','hardware_interface_id':'receiver-port'})
    p=RepairPlanner(state,objects,routes,history)
    assert p.identifier_conflicts([], [{'id':'old-port','data':{'network_ref':'replacement'}}])
