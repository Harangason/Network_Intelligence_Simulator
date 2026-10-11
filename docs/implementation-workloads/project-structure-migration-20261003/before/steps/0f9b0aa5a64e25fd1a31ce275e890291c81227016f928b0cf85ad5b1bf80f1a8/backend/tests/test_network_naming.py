from copy import deepcopy
import os
import pytest
from backend.engineering.network_naming import rename_network


@pytest.mark.parametrize('name', ['', '   ', 'line\nbreak', 'a' * 121, None])
def test_rejects_invalid_bus_names(name):
    with pytest.raises(ValueError):
        rename_network({'parameters': {'networks': [{'id': 'bus'}]}, 'topology': {}}, 'bus', name)


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Separate SQL database required')
def test_bus_name_persists_without_changing_ids_ports_routes_or_layout(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    c = _client()
    nodes = []
    for key in ('owner', 'sensor'):
        hw = c.post('/api/engineering/hardware-nodes', json={'name': key, 'device_type': 'ECU' if key == 'owner' else 'SensorController'}).get_json()
        nodes.append({'id': key, 'name': key, 'kind': 'ecu' if key == 'owner' else 'sensor', 'engineeringId': hw['id'], 'x': 0, 'y': 0,
            'ports': [{'id': key, 'name': key + ' LIN', 'bus': 'lin', 'side': 'bottom', 'offset': .5, 'physicalNetworkId': 'bus'}]})
    r = c.put('/api/engineering/workflow/topology', json={'topology': {'nodes': nodes, 'edges': [{'id': 'edge', 'source': 'owner', 'target': 'sensor', 'sourcePort': 'owner', 'targetPort': 'sensor', 'bus': 'lin', 'physicalNetworkId': 'bus'}]}})
    assert r.status_code == 200, r.get_json()
    before = c.get('/api/engineering/workflow').get_json()
    assert c.get('/api/engineering/workflow/network-view').get_json()['edit_tokens'] == before['edit_tokens']
    channel_ids = [n['ports'][0]['hardwareInterfaceId'] for n in before['topology']['nodes']]
    channels = [c.get('/api/engineering/hardware-interfaces/' + key).get_json() for key in channel_ids]
    def request(name, state=before, network='bus'):
        return c.put('/api/engineering/workflow/bus-name', json={'network_id': network, 'name': name, 'expected_token': state['edit_tokens']['topology'], 'expected_parameters_token': state['edit_tokens']['parameters']})
    assert request('Valid', network='foreign').status_code == 400
    assert c.put('/api/engineering/workflow/bus-name', json={'network_id': 'bus', 'name': 'Valid'}).status_code == 400
    original = WorkflowStatusService.rename_network
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError('Injected post-write failure')
        patch.setattr(WorkflowStatusService, 'rename_network', fail)
        assert request('owner LIN Nord').status_code == 400
    assert c.get('/api/engineering/workflow').get_json()['topology'] == before['topology']
    assert c.get('/api/engineering/workflow').get_json()['parameters'] == before['parameters']
    r = request('  owner LIN Nord  ')
    assert r.status_code == 200, r.get_json()
    after = r.get_json()
    assert request('Stale').status_code == 409
    assert after['versions'] == before['versions']
    assert after['statuses'] == before['statuses']
    expected_parameters = deepcopy(before['parameters'])
    next(n for n in expected_parameters['networks'] if n['id'] == 'bus').update(name='owner LIN Nord', name_source='user')
    assert after['parameters'] == expected_parameters
    expected_topology = deepcopy(before['topology'])
    for n in expected_topology['nodes']:
        for p in n['ports']:
            p.update(physicalNetworkName='owner LIN Nord', physicalNetworkNameSource='user')
    expected_topology['edges'][0].update(physicalNetworkName='owner LIN Nord', physicalNetworkNameSource='user')
    assert after['topology']['nodes'] == expected_topology['nodes']
    assert after['topology']['edges'] == expected_topology['edges']
    scene = after['topology']['scene']
    assert scene['buses'][0]['labelText'] == scene['buses'][0]['name'] == 'owner LIN Nord'
    for field in ('path', 'branches', 'bounds', 'label', 'participantCount', 'edgeIds'):
        assert scene['buses'][0][field] == before['topology']['scene']['buses'][0][field]
    for field in ('manualPositions', 'manualBusRoutes'):
        assert scene[field] == before['topology']['scene'][field]
    assert [c.get('/api/engineering/hardware-interfaces/' + key).get_json() for key in channel_ids] == channels
    # Rebuilding the scene must not strip the explicitly chosen owner prefix.
    r = c.put('/api/engineering/workflow/network-view', json={'expected_token': after['edit_tokens']['topology'], 'positions': {}})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['topology']['scene']['buses'][0]['labelText'] == 'owner LIN Nord'
    current = c.get('/api/engineering/workflow').get_json()
    # Unrelated relationship saves and materialization preserve this bus label.
    t = deepcopy(current['topology']); t['edges'][0]['description'] = 'Updated description'
    r = c.put('/api/engineering/workflow/topology', json={'topology': t, 'expected_token': current['edit_tokens']['topology']})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['topology']['scene']['buses'][0]['labelText'] == 'owner LIN Nord'


def test_legacy_names_aliases_and_custom_names_are_scoped_to_physical_network():
    state = {'parameters': {'networks': [{'id': 'camera', 'name': 'ETH_Camera'}, {'id': 'backbone', 'name': 'ETH_Backbone'}]},
             'topology': {'nodes': [{'id': 'owner', 'ports': [
                 {'id': 'a', 'name': 'camera', 'physicalNetworkId': 'camera', 'hardwareInterfaceId': 'a'},
                 {'id': 'alias', 'name': 'camera', 'physicalNetworkId': 'camera', 'hardwareInterfaceId': 'a'},
                 {'id': 'custom', 'name': 'ETH_Camera', 'nameSource': 'user', 'physicalNetworkId': 'camera'},
                 {'id': 'other', 'name': 'backbone', 'physicalNetworkId': 'backbone'},
             ]}], 'edges': [{'id': 'edge', 'sourcePort': 'alias', 'targetPort': 'custom', 'physicalNetworkId': 'camera',
                            'sourceInterfaceName': 'camera', 'targetInterfaceName': 'ETH_Camera'}]}}
    original = deepcopy(state)
    params, topology = rename_network(state, 'camera', 'ETH_Camera_02')
    assert state == original
    assert [p['name'] for p in topology['nodes'][0]['ports']] == ['ETH_Camera_02', 'ETH_Camera_02', 'ETH_Camera', 'backbone']
    assert topology['edges'][0]['sourceInterfaceName'] == 'ETH_Camera_02'
    assert topology['edges'][0]['targetInterfaceName'] == 'ETH_Camera'
    _, second = rename_network({'parameters': params, 'topology': topology}, 'camera', 'Another label')
    assert [p['name'] for p in second['nodes'][0]['ports']] == ['Another label', 'Another label', 'ETH_Camera', 'backbone']
    bad = deepcopy(original)
    bad['topology']['nodes'][0]['ports'][1]['physicalNetworkId'] = 'backbone'
    with pytest.raises(ValueError, match='mehreren Netzen'):
        rename_network(bad, 'camera', 'Invalid')


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Separate SQL database required')
def test_inherited_names_persist_everywhere_with_custom_override_and_rollback(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    c = _client()
    nodes = []
    for key in ('owner', 'camera', 'radar'):
        hw = c.post('/api/engineering/hardware-nodes', json={'name': key, 'domain': 'robotics', 'device_type': 'ECU'}).get_json()
        nodes.append({'id': key, 'name': key, 'kind': 'ecu', 'engineeringId': hw['id'], 'x': 0, 'y': 0,
                      'ports': [{'id': key, 'name': 'bus', 'bus': 'automotive_ethernet', 'side': 'bottom', 'offset': .5, 'physicalNetworkId': 'bus'}]})
    response = c.put('/api/engineering/workflow/topology', json={'topology': {'nodes': nodes, 'edges': [
        {'id': key, 'source': 'owner', 'target': key, 'sourcePort': 'owner', 'targetPort': key,
         'bus': 'automotive_ethernet', 'physicalNetworkId': 'bus'} for key in ('camera', 'radar')]}})
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    topology = deepcopy(state['topology'])
    topology['nodes'][0]['ports'].append({**topology['nodes'][0]['ports'][0], 'id': 'owner-alias'})
    topology['edges'][1]['sourcePort'] = 'owner-alias'
    response = c.put('/api/engineering/workflow/topology', json={'topology': topology, 'expected_token': state['edit_tokens']['topology']})
    assert response.status_code == 200, response.get_json()
    before = response.get_json()
    channel_ids = {p['hardwareInterfaceId'] for n in before['topology']['nodes'] for p in n['ports']}
    channels = {key: c.get('/api/engineering/hardware-interfaces/' + key).get_json() for key in channel_ids}
    def rename(name, state):
        return c.put('/api/engineering/workflow/bus-name', json={'network_id': 'bus', 'name': name,
            'expected_token': state['edit_tokens']['topology'], 'expected_parameters_token': state['edit_tokens']['parameters']})
    original = WorkflowStatusService.rename_network
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError('Injected failure after canonical and workflow writes')
        patch.setattr(WorkflowStatusService, 'rename_network', fail)
        assert rename('ETH_Camera', before).status_code == 400
    assert c.get('/api/engineering/workflow').get_json()['topology'] == before['topology']
    assert {key: c.get('/api/engineering/hardware-interfaces/' + key).get_json() for key in channel_ids} == channels
    state = before
    for name in ('ETH_Camera', 'ETH_Camera_02'):
        response = rename(name, state)
        assert response.status_code == 200, response.get_json()
        state = response.get_json()
        assert state['versions'] == before['versions']
        assert state['statuses'] == before['statuses']
        for node in state['topology']['nodes']:
            for p in node['ports']:
                assert p['name'] == name and p['nameSource'] == 'network'
                channel = c.get('/api/engineering/hardware-interfaces/' + p['hardwareInterfaceId']).get_json()
                assert channel['name'] == name and channel['capabilities']['name_source'] == 'network'
                assert channel['network_ref'] == channels[p['hardwareInterfaceId']]['network_ref']
        assert all(e['sourceInterfaceName'] == e['targetInterfaceName'] == name for e in state['topology']['edges'])
    # A deliberate interface edit becomes independent, even when equal to a prior bus name.
    topology = deepcopy(state['topology'])
    topology['nodes'][1]['ports'][0].update(name='ETH_Camera', nameSource='user')
    topology['edges'][0]['targetInterfaceName'] = 'ETH_Camera'
    response = c.put('/api/engineering/workflow/topology', json={'topology': topology, 'expected_token': state['edit_tokens']['topology']})
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    response = rename('ETH_Final', state)
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    assert state['topology']['nodes'][1]['ports'][0]['name'] == 'ETH_Camera'
    assert state['topology']['nodes'][1]['ports'][0]['nameSource'] == 'user'
    assert state['topology']['edges'][0]['targetInterfaceName'] == 'ETH_Camera'
    # Ordinary saves/materialization cannot restore stale generated names.
    response = c.put('/api/engineering/workflow/topology', json={'topology': state['topology'], 'expected_token': state['edit_tokens']['topology']})
    assert response.status_code == 200, response.get_json()
    assert [p['name'] for n in response.get_json()['topology']['nodes'] for p in n['ports']] == ['ETH_Final', 'ETH_Final', 'ETH_Camera', 'ETH_Final']


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Separate SQL database required')
def test_ethernet_creation_names_and_project_normalization_are_persistent(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    c = _client()
    nodes = []
    for key in ('Kameraverarbeitung', 'FrontCamera'):
        hw = c.post('/api/engineering/hardware-nodes', json={'name': key, 'domain': 'robotics', 'device_type': 'ECU' if key == 'Kameraverarbeitung' else 'SensorController'}).get_json()
        nodes.append({'id': key, 'engineeringId': hw['id'], 'name': key, 'kind': 'ecu' if key == 'Kameraverarbeitung' else 'sensor', 'x': 0, 'y': 0,
                      'ports': [{'id': key, 'name': 'hash-ethernet', 'bus': 'automotive_ethernet', 'side': 'bottom', 'offset': .5, 'physicalNetworkId': 'hash-ethernet'}]})
    response = c.put('/api/engineering/workflow/topology', json={'topology': {'nodes': nodes, 'edges': [{
        'id': 'edge', 'source': nodes[0]['id'], 'target': nodes[1]['id'], 'sourcePort': nodes[0]['id'], 'targetPort': nodes[1]['id'],
        'bus': 'automotive_ethernet', 'physicalNetworkId': 'hash-ethernet'}]}})
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    net = next(n for n in state['parameters']['networks'] if n['id'] == 'hash-ethernet')
    assert net['name'] == 'ETH_Kameraverarbeitung_01'
    for node in state['topology']['nodes']:
        port = node['ports'][0]
        assert port['name'] == net['name'] and port['nameSource'] == 'network'
        assert c.get('/api/engineering/hardware-interfaces/' + port['hardwareInterfaceId']).get_json()['name'] == net['name']
    # An unconnected legacy network is retained and receives a neutral stored label.
    params = deepcopy(state['parameters'])
    params['networks'].append({'id': 'network-automotive_ethernet-free-abcdef', 'name': 'network-automotive_ethernet-free-abcdef_01', 'technology': 'ETHERNET'})
    response = c.patch('/api/engineering/workflow/parameters', json={'parameters': params, 'expected_token': state['edit_tokens']['parameters']})
    assert response.status_code == 200, response.get_json()
    state = c.get('/api/engineering/workflow').get_json()
    def normalize(state):
        return c.put('/api/engineering/workflow/ethernet-names', json={'expected_token': state['edit_tokens']['topology'], 'expected_parameters_token': state['edit_tokens']['parameters']})
    original = WorkflowStatusService.normalize_ethernet_names
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError('Injected failure after normalization')
        patch.setattr(WorkflowStatusService, 'normalize_ethernet_names', fail)
        assert normalize(state).status_code == 400
    assert c.get('/api/engineering/workflow').get_json()['parameters'] == state['parameters']
    response = normalize(state)
    assert response.status_code == 200, response.get_json()
    after = response.get_json()
    assert after['parameters']['networks'][-1]['name'] == 'ETH_Netz_01'
    assert after['versions'] == state['versions']
    assert after['topology']['nodes'] == state['topology']['nodes']
    assert normalize(state).status_code == 409
    again = normalize(after)
    assert again.status_code == 200
    assert again.get_json()['parameters'] == after['parameters']
