"""Physical route indexes are local to a calculation, not a stale topology cache."""
from copy import deepcopy

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.routing import transport_segments as transport
from backend.tests.test_transport_integrity import gateway_config


def test_one_index_retains_gateway_direction_ports_and_independent_results(gateway_config, monkeypatch):
    config = gateway_config
    route = config['engineering_model']['routes'][0]
    target = route['destinations'][0]
    original = deepcopy(config)
    calls = []
    original_networks = transport.physical_port_networks
    def counted(topology):
        calls.append(True)
        return original_networks(topology)
    monkeypatch.setattr(transport, 'physical_port_networks', counted)
    resolver = transport.PhysicalRouteResolver(config['topology'])
    for _ in range(10):
        segments = resolver.resolve(route, target)
        assert [(item['source']['node_id'], item['target']['node_id']) for item in segments] == [('source', 'gateway'), ('gateway', 'target')]
        assert [(item['source']['network_id'], item['target']['network_id']) for item in segments] == [('input-bus', 'input-bus'), ('output-bus', 'output-bus')]
        assert [item['source']['protocol'] for item in segments] == ['CAN_FD', 'LIN']
        assert [item['topology_edge_ids'] for item in segments] == [['edge-in'], ['edge-out']]
        assert segments[-1]['target']['interface_id'] == 'target-if'
        segments[0]['source']['interface_id'] = 'caller-edit'
        segments[0]['topology_edge_ids'].append('caller-edge')
    assert calls == [True]
    assert config == original


def test_next_operation_rebuilds_same_topology_after_edit(gateway_config):
    config = gateway_config
    route = config['engineering_model']['routes'][0]
    target = route['destinations'][0]
    assert transport.physical_route_segments(route, target, config['topology'])[-1]['target']['network_id'] == 'output-bus'
    for node in config['topology']['nodes']:
        for port in node['ports']:
            if port['physicalNetworkId'] == 'output-bus': port['physicalNetworkId'] = 'reassigned-local-lin'
    config['topology']['edges'][1]['physicalNetworkId'] = 'reassigned-local-lin'
    assert transport.physical_route_segments(route, target, config['topology'])[-1]['target']['network_id'] == 'reassigned-local-lin'


def test_route_alias_index_preserves_isolation_between_paths(gateway_config):
    config = gateway_config
    route = config['engineering_model']['routes'][0]
    for edge in config['topology']['edges']:
        edge['routingEntryIds'] = [route['id'], 'second-route']
        edge.pop('routingEntryId')
    resolver = transport.PhysicalRouteResolver(config['topology'])
    expected = resolver.resolve(route, route['destinations'][0])
    assert resolver.resolve({**route, 'id': 'second-route'}, route['destinations'][0]) == expected
    with pytest.raises(EngineeringValidationError, match='Gateway-Segmente'):
        resolver.resolve({**route, 'id': 'foreign-route'}, route['destinations'][0])


def test_unlinked_local_path_does_not_build_port_networks(monkeypatch):
    def unexpected(_): raise AssertionError('local logical fallback needs no physical index')
    monkeypatch.setattr(transport, 'physical_port_networks', unexpected)
    route = {'id': 'local', 'source': {'node_id': 'source', 'network_id': 'local-bus', 'protocol': 'LIN'}}
    target = {'node_id': 'target'}
    assert transport.PhysicalRouteResolver().resolve(route, target) == [{
        'source': route['source'], 'target': {**target, 'network_id': 'local-bus', 'protocol': 'LIN'}}]
