"""Real SQL route generation through explicitly confirmed local ECU ports."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from backend.engineering.db import get_connection
from backend.engineering.project_context import current_project_id
from backend.engineering.routing.generation import RoutingGenerationService, routing_candidate_batch
from backend.engineering.routing.validation import RoutingValidator


@pytest.fixture
def subnet():
    ids = {key: str(uuid4()) for key in ('sensor', 'motor', 'consumer', 'source', 'input', 'output', 'target', 'si', 'ti', 'message')}
    project = current_project_id()
    rule = {'confirmed': True, 'input_port_id': ids['input'], 'output_port_id': ids['output'],
            'input_network_id': 'local', 'output_network_id': 'remote'}
    ports = [('source', 'sensor', 'local'), ('input', 'motor', 'local'),
             ('output', 'motor', 'remote'), ('target', 'consumer', 'remote')]
    topology = {'nodes': [{'id': key, 'engineeringId': ids[key], 'name': key, 'kind': 'ecu',
        'ports': [{'id': port, 'hardwareInterfaceId': ids[port], 'physicalNetworkId': network, 'bus': 'lin'}
                  for port, owner, network in ports if owner == key]} for key in ('sensor', 'motor', 'consumer')],
        'edges': [{'id': 'local-wire', 'source': 'sensor', 'target': 'motor', 'sourcePort': 'source',
                   'targetPort': 'input', 'physicalNetworkId': 'local', 'bus': 'lin'},
                  {'id': 'remote-wire', 'source': 'motor', 'target': 'consumer', 'sourcePort': 'output',
                   'targetPort': 'target', 'physicalNetworkId': 'remote', 'bus': 'lin'}]}
    with get_connection() as connection:
        for key in ('sensor', 'motor', 'consumer'):
            connection.execute('INSERT INTO engineering_hardware_nodes (id, project_id, name, device_type, identity) '
                'VALUES (%s,%s,%s,%s,%s::jsonb)', (ids[key], project, key, 'ECU',
                json.dumps({'communication_forwarding': [rule]} if key == 'motor' else {})))
        for index, (key, owner, network) in enumerate(ports):
            connection.execute('INSERT INTO engineering_hardware_interfaces '
                '(id, project_id, name, hardware_node_id, technology, network_ref, channel_index) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s)', (ids[key], project, key, ids[owner], 'LIN', network, index + 1))
        for key, owner, port in [('si', 'sensor', 'source'), ('ti', 'consumer', 'target')]:
            connection.execute('INSERT INTO engineering_interfaces '
                '(id, project_id, name, hardware_node_id, interface_type, configuration) '
                'VALUES (%s,%s,%s,%s,%s,%s::jsonb)', (ids[key], project, key, ids[owner], 'LIN',
                    json.dumps({'physical_interface_ids': [ids[port]]})))
        connection.execute('INSERT INTO engineering_messages '
            '(id, project_id, name, interface_id, hardware_interface_id, message_id_hex, cycle_ms, dlc, direction) '
            'VALUES (%s,%s,%s,%s,%s,%s,100,2,%s)',
            (ids['message'], project, 'ExplicitDeviceOutput', ids['si'], ids['source'], '0x10', 'tx'))
        connection.execute('INSERT INTO engineering_workflow_projects (project_id, parameters, topology) VALUES (%s,%s::jsonb,%s::jsonb)',
            (project, json.dumps({'networks': [{'id': net, 'technology': 'LIN'} for net in ('local', 'remote')]}), json.dumps(topology)))
    return ids, rule, topology


def generated(ids):
    return RoutingGenerationService().generate_route(source_node_id=ids['sensor'], destination_node_id=ids['consumer'], message_id=ids['message'])


@pytest.mark.parametrize('technology,bus', [('LIN', 'lin'), ('CAN_FD', 'can_fd'), ('Ethernet', 'automotive_ethernet')])
def test_confirmed_local_ecu_port_pair_generates_valid_exact_path_without_reclassification(subnet, technology, bus):
    ids, _, topology = subnet
    with get_connection() as connection:
        connection.execute('UPDATE engineering_hardware_interfaces SET technology=%s WHERE project_id=%s', (technology, current_project_id()))
        connection.execute('UPDATE engineering_interfaces SET interface_type=%s WHERE project_id=%s', (technology, current_project_id()))
        for node in topology['nodes']:
            for port in node['ports']:
                port['bus'] = bus
        for edge in topology['edges']:
            edge['bus'] = bus
        connection.execute('UPDATE engineering_workflow_projects SET topology=%s::jsonb, parameters=%s::jsonb WHERE project_id=%s',
            (json.dumps(topology), json.dumps({'networks': [{'id': net, 'technology': technology} for net in ('local', 'remote')]}), current_project_id()))
    route = generated(ids)
    assert route['validation']['valid'], route['validation']
    assert route['route']['gateways'] == [{'node_id': ids['motor'], 'name': 'motor'}]
    assert route['route']['physical_paths'] == [{'ports': [ids[key] for key in ('source', 'input', 'output', 'target')],
                                               'edges': ['local-wire', 'remote-wire']}]
    assert route['source']['port_id'] == ids['source']
    assert route['destinations'][0]['port_id'] == ids['target']
    assert route['source']['interface_id'] == ids['si']
    assert route['destinations'][0]['interface_id'] == ids['ti']
    assert [segment['network_id'] for segment in route['route']['transport_segments']] == ['local', 'remote']
    with get_connection() as connection:
        assert connection.execute('SELECT device_type FROM engineering_hardware_nodes WHERE id=%s', (ids['motor'],)).fetchone()['device_type'] == 'ECU'
        assert connection.execute('SELECT count(*) AS n FROM engineering_hardware_interfaces WHERE project_id=%s', (current_project_id(),)).fetchone()['n'] == 4


@pytest.mark.parametrize('fault', ['unconfirmed', 'missing-rule', 'reverse-rule', 'wrong-network', 'missing-wire', 'wrong-wire-network', 'moved-port'])
def test_unconfirmed_stale_or_unwired_ecu_is_not_an_implicit_gateway(subnet, fault):
    ids, rule, topology = subnet
    changed = deepcopy(rule)
    with get_connection() as connection:
        if fault == 'unconfirmed':
            changed['confirmed'] = False
        elif fault == 'reverse-rule':
            changed.update(input_port_id=ids['output'], output_port_id=ids['input'], input_network_id='remote', output_network_id='local')
        elif fault == 'wrong-network':
            changed['output_network_id'] = 'other'
        elif fault == 'missing-wire':
            topology['edges'].pop()
        elif fault == 'wrong-wire-network':
            topology['edges'][-1]['physicalNetworkId'] = 'other'
        elif fault == 'moved-port':
            connection.execute('UPDATE engineering_hardware_interfaces SET network_ref=%s WHERE id=%s', ('other', ids['output']))
        connection.execute('UPDATE engineering_hardware_nodes SET identity=%s::jsonb WHERE id=%s',
            (json.dumps({'communication_forwarding': [] if fault == 'missing-rule' else [changed]}), ids['motor']))
        connection.execute('UPDATE engineering_workflow_projects SET topology=%s::jsonb WHERE project_id=%s',
            (json.dumps(topology), current_project_id()))
    route = generated(ids)
    assert not route['validation']['valid']
    assert not route['route']['gateways']
    assert not route['route'].get('physical_paths')


def test_forwarding_confirmation_does_not_authorize_reverse_direction(subnet):
    ids, _, _ = subnet
    candidates = RoutingGenerationService().find_candidate_paths(ids['consumer'], ids['sensor'])
    assert all(not candidate.get('physical_paths') and not candidate['gateways'] for candidate in candidates)


def test_existing_generated_path_is_invalid_after_confirmation_revocation(subnet):
    ids, _, _ = subnet
    route = generated(ids)
    with get_connection() as connection:
        connection.execute('UPDATE engineering_hardware_nodes SET identity=%s::jsonb WHERE id=%s', ('{}', ids['motor']))
    result = RoutingValidator().validate(route)
    assert not result['valid']
    assert {'PHYSICAL_PATH_REMOVED', 'INVALID_GATEWAY'} <= {item['code'] for item in result['errors']}


def test_unrelated_source_port_cannot_replace_message_publisher(subnet):
    ids, _, _ = subnet
    other = str(uuid4())
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_hardware_interfaces (id, project_id, name, hardware_node_id, technology, network_ref) '
            'VALUES (%s,%s,%s,%s,%s,%s)', (other, current_project_id(), 'other', ids['sensor'], 'LIN', 'other'))
        connection.execute('UPDATE engineering_messages SET hardware_interface_id=%s WHERE id=%s', (other, ids['message']))
    route = generated(ids)
    assert not route['validation']['valid']
    assert route['source']['port_id'] != ids['source']


def test_another_project_cannot_supply_the_ecu_forwarding_confirmation(subnet):
    ids, rule, _ = subnet
    with get_connection() as connection:
        connection.execute('UPDATE engineering_hardware_nodes SET identity=%s::jsonb WHERE id=%s', ('{}', ids['motor']))
        connection.execute('INSERT INTO engineering_hardware_nodes (id, project_id, name, device_type, identity) '
            'VALUES (%s,%s,%s,%s,%s::jsonb)', (str(uuid4()), current_project_id() + '-other', 'foreign motor', 'ECU',
                json.dumps({'communication_forwarding': [rule]})))
    route = generated(ids)
    assert not route['validation']['valid']
    assert not route['route']['gateways']
    assert not route['route'].get('physical_paths')


def test_proposal_batch_builds_one_physical_graph_and_rechecks_after_batch(subnet, monkeypatch):
    from backend.engineering.communication_repair import RepairPlanner
    ids, rule, _ = subnet
    builds = []
    original = RepairPlanner.__init__

    def counted(self, *args, **kwargs):
        builds.append(True)
        original(self, *args, **kwargs)

    monkeypatch.setattr(RepairPlanner, '__init__', counted)
    service = RoutingGenerationService()
    with routing_candidate_batch(service):
        for _ in range(8):
            result = service.generate_route(source_node_id=ids['sensor'], destination_node_id=ids['consumer'], message_id=ids['message'])
            assert result['validation']['valid']
        assert len(builds) == 1, 'Graph must be shared by generation and validation across this proposal'
    assert service._candidate_context is None and service._candidate_planner is None
    with get_connection() as connection:
        connection.execute('UPDATE engineering_hardware_nodes SET identity=%s::jsonb WHERE id=%s', ('{}', ids['motor']))
    result = service.generate_route(source_node_id=ids['sensor'], destination_node_id=ids['consumer'], message_id=ids['message'])
    assert not result['validation']['valid']
    with get_connection() as connection:
        connection.execute('UPDATE engineering_hardware_nodes SET identity=%s::jsonb WHERE id=%s',
            (json.dumps({'communication_forwarding': [rule]}), ids['motor']))
    with routing_candidate_batch(service):
        assert service.generate_route(source_node_id=ids['sensor'], destination_node_id=ids['consumer'], message_id=ids['message'])['validation']['valid']
    assert len(builds) == 2


def test_failed_proposal_batch_releases_cached_physical_state(subnet):
    service = RoutingGenerationService()
    ids, _, _ = subnet
    with pytest.raises(ValueError, match='failed proposal'):
        with routing_candidate_batch(service):
            service.find_candidate_paths(ids['sensor'], ids['consumer'])
            raise ValueError('failed proposal')
    assert service._candidate_context is None
    assert service._candidate_planner is None
