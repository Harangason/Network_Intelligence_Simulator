from copy import deepcopy
import os

import pytest

from backend.engineering.physical_ports import _free_port_rebindings, materialize_physical_ports


def test_spare_channel_rebind_preserves_physical_identity_and_rejects_aliases():
    hardware = [{'id': key} for key in ['owner', 'sensor']]
    interfaces = [{'id': key + '-channel', 'hardware_node_id': key, 'technology': 'CAN_FD',
                   'network_ref': key + '-net', 'channel_index': 3, 'physical_port_ref': key + '-connector'} for key in ['owner', 'sensor']]
    previous = {'nodes': [{'id': key, 'engineeringId': key, 'ports': [{'id': key + '-port', 'bus': 'can_fd',
                'hardwareInterfaceId': key + '-channel', 'physicalNetworkId': key + '-net'}]} for key in ['owner', 'sensor']], 'edges': []}
    current = deepcopy(previous)
    current['nodes'][1]['ports'][0]['physicalNetworkId'] = 'owner-net'
    current['edges'] = [{'id': 'new', 'source': 'owner', 'sourcePort': 'owner-port', 'target': 'sensor', 'targetPort': 'sensor-port', 'bus': 'can_fd'}]
    result, changes = materialize_physical_ports(current, hardware, interfaces,
        [{'id': key + '-net', 'technology': 'CAN_FD'} for key in ['owner', 'sensor']], previous_topology=previous)
    assert result['nodes'][1]['ports'][0]['hardwareInterfaceId'] == 'sensor-channel'
    change = next(c for c in changes if c.get('object_id') == 'sensor-channel')
    assert change['data'] == {'network_ref': 'owner-net'}
    assert not any(c.get('action') != 'UPDATE' for c in changes)
    alias = deepcopy(previous['nodes'][1]['ports'][0]); alias['id'] = 'alias'
    previous['nodes'][1]['ports'].append(alias)
    assert ('sensor-port', 'sensor-channel') not in _free_port_rebindings(previous, current)


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Requires separate test SQL database')
def test_api_attachment_retains_channel_reload_and_rolls_back_failure(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.models import EngineeringValidationError

    client = _client()
    nodes = []
    for key in ['owner', 'sensor', 'test']:
        hardware = client.post('/api/engineering/hardware-nodes', json={'name': key, 'domain': 'robotics', 'device_type': 'ECU' if key == 'owner' else 'SensorController'}).get_json()
        nodes.append({'id': key, 'name': key, 'engineeringId': hardware['id'], 'kind': 'ecu' if key == 'owner' else 'sensor',
                      'x': 30, 'y': 40, 'ports': [{'id': key + '-port', 'name': 'CAN FD', 'bus': 'can_fd', 'side': 'right', 'offset': .5,
                                                'physicalNetworkId': 'spare' if key == 'test' else 'local'}]})
    topology = {'nodes': nodes, 'edges': [{'id': 'existing', 'source': 'owner', 'sourcePort': 'owner-port', 'target': 'sensor', 'targetPort': 'sensor-port', 'bus': 'can_fd', 'physicalNetworkId': 'local'}]}
    response = client.put('/api/engineering/workflow/topology', json={'topology': topology})
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    before = deepcopy(state['topology'])
    spare = next(n for n in before['nodes'] if n['id'] == 'test')['ports'][0]
    physical_url = '/api/engineering/hardware-interfaces/' + spare['hardwareInterfaceId']
    physical = client.get(physical_url).get_json()
    updated = deepcopy(before)
    next(n for n in updated['nodes'] if n['id'] == 'test')['ports'][0]['physicalNetworkId'] = 'local'
    updated['edges'].append({'id': 'new', 'source': 'test', 'sourcePort': 'test-port', 'target': 'owner', 'targetPort': 'owner-port',
                             'bus': 'can_fd', 'physicalNetworkId': 'local', 'relationType': 'CONNECTED_VIA', 'direction': 'BIDIRECTIONAL'})
    request = {'topology': updated, 'expected_token': state['edit_tokens']['topology']}
    original = WorkflowStatusService.save_topology
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise EngineeringValidationError('Injected failure after channel and topology writes')
        patch.setattr(WorkflowStatusService, 'save_topology', fail)
        failed = client.put('/api/engineering/workflow/topology', json=request)
    assert failed.status_code == 400, failed.get_json()
    assert client.get(physical_url).get_json() == physical
    assert client.get('/api/engineering/workflow').get_json()['topology'] == before
    saved = client.put('/api/engineering/workflow/topology', json=request)
    assert saved.status_code == 200, saved.get_json()
    reloaded = client.get('/api/engineering/workflow').get_json()['topology']
    after = next(n for n in reloaded['nodes'] if n['id'] == 'test')['ports'][0]
    assert after['hardwareInterfaceId'] == spare['hardwareInterfaceId']
    assert after['physicalNetworkId'] == 'local'
    actual = client.get(physical_url).get_json()
    assert actual['network_ref'] == 'local'
    assert actual['channel_index'] == physical['channel_index']
    assert actual['physical_port_ref'] == physical['physical_port_ref']
    assert len(reloaded['edges']) == 2
    assert any(b['id'] == 'local' and b['participantCount'] == 3 for b in reloaded['scene']['buses'])
