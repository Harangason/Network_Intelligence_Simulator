from copy import deepcopy
import json
import pytest
from backend.engineering.spatial_zoning import installation_zone, plan_zoning, zone_findings
from backend.engineering.models import EngineeringValidationError


@pytest.mark.parametrize('name,side,zone', [
    ('RearLeftSuspensionTravel', None, 'RL'), ('FederwegHintenRechts', None, 'RR'),
    ('FrontRightDamperPosition', None, 'FR'), ('Fahrersitz', 'LHD', 'FL'),
    ('BeifahrertuerStellglied', 'LHD', 'FR'), ('Beifahrersitz', 'RHD', 'FL'),
    ('Fahrerassistenz', 'LHD', 'UNKNOWN'), ('Fahrwerk', 'LHD', 'UNKNOWN'),
    ('FondtuerLinks', 'LHD', 'RL'), ('Fahrersitz', None, 'UNKNOWN'),
    ('OilTemperature', 'LHD', 'UNKNOWN'), ('SurroundLeftCamera', 'LHD', 'L')])
def test_positions_use_complete_tokens(name, side, zone):
    assert installation_zone(name, driving_side=side) == zone


def fixture(multicast=False, names=None):
    names = names or ['Daempferregelung', 'FrontLeftSuspensionTravel', 'FrontLeftDamperPosition', 'RearRightSuspensionTravel']
    objects = {k: [] for k in ('HardwareNode', 'HardwareNetworkInterface', 'Message', 'Interface', 'Signal')}
    topology = {'nodes': [], 'edges': []}
    routes = []
    for i, name in enumerate(names):
        key = str(i)
        identity = {'system_owner_id': '0'} if i else {}
        objects['HardwareNode'].append({'id': key, 'name': name, 'identity': identity})
        objects['HardwareNetworkInterface'].append({'id': 'h'+key, 'name': 'Old', 'hardware_node_id': key,
            'network_ref': 'old-can-fd-name', 'technology': 'LIN', 'channel_index': 1, 'bitrate': 19200,
            'physical_port_ref': 'connector-'+key, 'capabilities': {}})
        topology['nodes'].append({'id': key, 'engineeringId': key, 'name': name, 'kind': 'sensor' if i else 'ecu',
            'systemOwnerId': '0' if i else None, 'ports': [{'id': 'p'+key, 'hardwareInterfaceId': 'h'+key,
                'engineeringId': 'h'+key, 'bus': 'lin', 'physicalNetworkId': 'old-can-fd-name'}]})
        if not i: continue
        route_id = 'r' if multicast else 'r'+key
        topology['edges'].append({'id': 'e'+key, 'source': key, 'target': '0', 'sourcePort': 'p'+key, 'targetPort': 'p0',
            'bus': 'lin', 'physicalNetworkId': 'old-can-fd-name', 'physicalNetworkName': 'Old',
            'routingEntryId': route_id, 'routingEntryIds': [route_id], 'routingMetadata': {route_id: {'name': name}}})
        def endpoint(node):
            return {'node_id': node, 'node_name': names[int(node)], 'port_id': 'h'+node, 'network_id': 'old-can-fd-name', 'protocol': 'LIN'}
        message_id = 'm' if multicast else 'm'+key
        if not multicast:
            objects['Message'].append({'id': message_id, 'hardware_interface_id': 'h'+key, 'configuration': {}})
            routes.append({'id': route_id, 'revision': 1, 'name': name, 'source': endpoint(key), 'destinations': [endpoint('0')],
                'payload': {'message_id': message_id}, 'route': {}, 'status': 'APPROVED', 'approval_state': 'APPROVED'})
    if multicast:
        objects['Message'].append({'id': 'm', 'hardware_interface_id': 'h0', 'configuration': {}})
        routes = [{'id': 'r', 'revision': 1, 'name': 'Command', 'source': endpoint('0'),
            'destinations': [endpoint(str(i)) for i in range(1,4)], 'payload': {'message_id': 'm'},
            'route': {}, 'status': 'APPROVED', 'approval_state': 'APPROVED'}]
    state = {'versions': {'engineering_model': 1}, 'parameters': {'networks': [
        {'id': 'old-can-fd-name', 'name': 'Old', 'technology': 'LIN', 'bitrate': 19200}]}, 'context': {}, 'topology': topology}
    return state, objects, routes


def accept_pure(state, objects, routes, plan):
    state = {**state, 'topology': plan['topology'], 'parameters': {**state['parameters'], 'networks': plan['networks']}}
    objects = deepcopy(objects)
    for c in plan['creations']: objects[c['object_type']].append({**c['data'], 'id': c['local_ref']})
    for (kind, key), values in plan['changes'].items():
        next(o for o in objects[kind] if o['id'] == key).update(values)
    updated = {r['id']: r for r in routes}
    updated.update({r['id']: r for r in plan['routes']})
    return state, objects, list(updated.values())


def test_split_preserves_function_protocol_payload_and_is_idempotent():
    state, objects, routes = fixture()
    before = deepcopy((state, objects, routes))
    plan = plan_zoning(state, objects, routes, 'LHD')
    assert (state, objects, routes) == before
    assert len(plan['creations']) == 1
    assert len(plan['networks']) == 2
    assert {n['installation_zone'] for n in plan['networks']} == {'FL', 'RR'}
    assert all(n['technology'] == 'LIN' and n['bitrate'] == 19200 for n in plan['networks'])
    assert {r['id']: r['payload'] for r in plan['routes']} == {r['id']: r['payload'] for r in routes}
    assert all(r['destinations'][0]['node_id'] == '0' for r in plan['routes'])
    new = accept_pure(state, objects, routes, plan)
    assert zone_findings(new[0]['topology'], new[1]['HardwareNode']) == []
    repeat = plan_zoning(*new, 'LHD')
    assert not repeat['divisions'] and not repeat['creations'] and not repeat['changes'] and not repeat['routes']


def test_multicast_command_preserves_recipients_and_all_physical_sources():
    state, objects, routes = fixture(multicast=True)
    plan = plan_zoning(state, objects, routes, 'LHD')
    assert len(plan['routes']) == 2
    assert sorted(d['node_id'] for r in plan['routes'] for d in r['destinations']) == ['1', '2', '3']
    assert len({r['source']['network_id'] for r in plan['routes']}) == 2
    assert all(all(d['network_id'] == r['source']['network_id'] for d in r['destinations']) for r in plan['routes'])
    assert len(plan['changes']['Message', 'm']['configuration']['physical_transmit_bindings']) == 2


def test_fixed_inventory_and_conflicting_positions_fail_without_mutation():
    state, objects, routes = fixture()
    state['parameters']['network_resource_policy'] = {'hard_limits': {'LIN': 1}}
    with pytest.raises(EngineeringValidationError, match='Ressourcenbestand'): plan_zoning(state, objects, routes)
    with pytest.raises(EngineeringValidationError, match='widersprüchliche'): installation_zone('FrontLeftRightWheel')
    assert installation_zone('RearRightWheel', {'installation_zone': 'FL', 'installation_zone_source': 'manual'}) == 'FL'


def test_wizard_allocates_by_owner_protocol_and_zone_before_capacity():
    from backend.engineering.agent_tools.wizard_generation import _confirmed_local_io_memberships, _local_io_physical_network
    endpoints = ['RearLeftSuspensionTravel', 'FrontLeftDamperPosition', 'RearRightSuspensionTravel', 'RearLeftDamperPosition']
    graph = [{'bus_name': 'Fahrwerk', 'controllers': [{'ecu': 'Daempferregelung', 'sensors': endpoints}]}]
    prompt = '- Systemcluster-Graph: ' + json.dumps(graph)
    def allocate(items):
        graph[0]['controllers'][0]['sensors'] = items
        memberships = _confirmed_local_io_memberships('- Systemcluster-Graph: '+json.dumps(graph), {n.casefold(): 'lin' for n in items})
        return {n: _local_io_physical_network('lin', memberships, {'name': n}, {'name': 'Daempferregelung'}) for n in items}
    mapping = allocate(endpoints)
    assert mapping == allocate(list(reversed(endpoints)))
    assert mapping[endpoints[0]] == mapping[endpoints[3]]
    assert len({value[0] for value in mapping.values()}) == 3
