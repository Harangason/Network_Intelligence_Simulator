from copy import deepcopy
import os

import pytest

from backend.engineering.frame_device import plan_frame_device
from backend.engineering.models import EngineeringValidationError
from backend.engineering.network_scene import build_network_scene
from backend.tests.test_network_scene import fixture_topology


def fixture():
    topology, prompt = fixture_topology()
    hardware = []
    for node in topology['nodes']:
        node['engineeringId'] = node['id'] + '-hardware'
        hardware.append({'id': node['engineeringId'], 'name': node['name'], 'domain': 'robotics'})
    return {'topology': build_network_scene(topology, prompt), 'context': {'wizard_request': {'prompt': prompt}}}, hardware


@pytest.mark.parametrize('kind', ['ecu', 'sensor', 'actuator'])
def test_creation_keeps_membership_connections_and_unrelated_positions(kind):
    state, hardware = fixture()
    before = deepcopy(state)
    plan = plan_frame_device(state, {'frame_id': 'Motor', 'kind': kind, 'name': 'Zusatzgerät'}, hardware)
    node = plan['node']
    node['engineeringId'] = 'new-hardware'
    result = build_network_scene(plan['topology'], state['context']['wizard_request']['prompt'], positions=plan['positions'])
    assert state == before
    assert result['edges'] == before['topology']['edges']
    assert node['systemOwnerId'] == 'Motor-hardware'
    assert plan['hardware']['identity']['system_owner_source'] == 'network-editor'
    assert 'installation_zone' not in plan['hardware']['identity']
    assert plan['hardware']['domain'] == 'robotics'
    frame = next(f for f in result['scene']['frames'] if f['id'] == 'Motor')
    assert node['id'] in frame['memberIds']
    assert not any(f['id'] == node['id'] for f in result['scene']['frames'])
    assert frame['left'] <= node['x'] < node['x'] + node['width'] <= frame['left'] + frame['width']
    assert frame['top'] <= node['y'] < node['y'] + node['height'] <= frame['top'] + frame['height']
    for old in before['topology']['nodes']:
        current = next(n for n in result['nodes'] if n['id'] == old['id'])
        assert (current['x'], current['y']) == (old['x'], old['y'])


@pytest.mark.parametrize('patch', [{'kind': 'gateway'}, {'frame_id': 'missing'}, {'frame_id': 'Gateway'},
                                  {'name': '  '}, {'name': 'Motor'}, {'name': 'x' * 161}])
def test_invalid_creation_is_rejected(patch):
    state, hardware = fixture()
    with pytest.raises(EngineeringValidationError):
        plan_frame_device(state, {'frame_id': 'Motor', 'kind': 'sensor', 'name': 'Messgerät', **patch}, hardware)


def test_growing_frame_moves_following_frames_out_of_the_way():
    state, hardware = fixture()
    topology = state['topology']
    frame, following = topology['scene']['frames'][:2]
    following.update(left=frame['left'], top=frame['top'] + frame['height'] + 10)
    plan = plan_frame_device(state, {'frame_id': frame['id'], 'kind': 'sensor', 'name': 'Zusatzgerät'}, hardware)
    assert all(plan['positions'][key]['y'] > next(n['y'] for n in topology['nodes'] if n['id'] == key)
               for key in following['memberIds'])


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Requires separate test SQL database')
def test_api_creation_reload_conflict_and_rollback(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.models import EngineeringValidationError

    client = _client()
    owner = client.post('/api/engineering/hardware-nodes', json={'name': 'Flugregelung', 'domain': 'aerospace', 'device_type': 'ECU'}).get_json()
    topology = build_network_scene({'nodes': [{'id': 'owner', 'name': owner['name'], 'engineeringId': owner['id'],
        'kind': 'ecu', 'x': 0, 'y': 0, 'ports': []}], 'edges': []})
    state = client.put('/api/engineering/workflow/topology', json={'topology': topology}).get_json()
    # Prepare a scene also when the project has no connections yet.
    state = client.put('/api/engineering/workflow/network-view', json={'expected_token': state['edit_tokens']['topology']}).get_json()
    for kind, name in [('ecu', 'Zusatzsteuerung'), ('sensor', 'Vibrationsmessung'), ('actuator', 'Rotorklappe')]:
        request = {'frame_id': 'owner', 'kind': kind, 'name': name, 'expected_token': state['edit_tokens']['topology']}
        before = client.get('/api/engineering/hardware-nodes').get_json()
        original = WorkflowStatusService.save_topology
        with monkeypatch.context() as patch:
            def fail(*args, **kwargs):
                original(*args, **kwargs)
                raise EngineeringValidationError('Injected error after SQL writes')
            patch.setattr(WorkflowStatusService, 'save_topology', fail)
            failed = client.post('/api/engineering/workflow/frame-device', json=request)
        assert failed.status_code == 400, failed.get_json()
        assert client.get('/api/engineering/hardware-nodes').get_json() == before
        assert client.get('/api/engineering/workflow/network-view').get_json()['topology'] == state['topology']
        created = client.post('/api/engineering/workflow/frame-device', json=request)
        assert created.status_code == 201, created.get_json()
        state = created.get_json()
        node = state['created_device']
        assert node['id'] in state['topology']['scene']['frames'][0]['memberIds']
        hw = client.get('/api/engineering/hardware-nodes/' + node['engineeringId']).get_json()
        assert hw['identity']['system_owner_id'] == owner['id']
        assert hw['identity']['cluster_id'] == state['topology']['scene']['frames'][0]['clusterId']
        assert hw['lifecycle_state'] == 'draft'
        assert client.get('/api/engineering/workflow/network-view').get_json()['topology'] == state['topology']
        stale = client.post('/api/engineering/workflow/frame-device', json=request)
        assert stale.status_code == 409
        duplicate = client.post('/api/engineering/workflow/frame-device', json={**request, 'expected_token': state['edit_tokens']['topology']})
        assert duplicate.status_code == 400
