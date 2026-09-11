from copy import deepcopy
import os
import pytest
from backend.engineering.topology_removal import detached_topology


def test_only_newly_disconnected_ports_leave_their_previous_bus():
    ports=[{'id':p,'bus':'can_fd','physicalNetworkId':'can','hardwareInterfaceId':p} for p in ['a','b','c','free']]
    before={'nodes':[{'id':p['id'],'ports':[p]} for p in ports], 'edges':[
        {'id':'ab','sourcePort':'a','targetPort':'b'}, {'id':'ac','sourcePort':'a','targetPort':'c'}]}
    after=deepcopy(before);after['edges']=after['edges'][1:]
    result=detached_topology(before,after)
    assert result['nodes'][1]['ports'][0]['physicalNetworkId']!='can'
    for i in [0,2,3]: assert result['nodes'][i]==before['nodes'][i]
    assert after['nodes']==before['nodes']


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'),reason='Separate SQL database required')
def test_delete_port_bus_reload_reconnect_and_rollback(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.models import EngineeringValidationError
    c=_client();nodes=[]
    for key in ['owner','a','b','spare']:
        hw=c.post('/api/engineering/hardware-nodes',json={'name':key,'domain':'robotics','device_type':'ECU' if key=='owner' else 'SensorController'}).get_json()
        nodes.append({'id':key,'name':key,'engineeringId':hw['id'],'kind':'ecu' if key=='owner' else 'sensor','x':0,'y':0,
                      'ports':[{'id':key,'bus':'can_fd','name':'CAN FD','side':'right','offset':.5,'physicalNetworkId':'spare' if key=='spare' else 'bus'}]})
    topology={'nodes':nodes,'edges':[{'id':key,'source':'owner','sourcePort':'owner','target':key,'targetPort':key,'bus':'can_fd','physicalNetworkId':'bus'} for key in ['a','b']]}
    def save(t,state=None):
        return c.put('/api/engineering/workflow/topology',json={'topology':t,**({'expected_token':state['edit_tokens']['topology']} if state else {})})
    first=save(topology);assert first.status_code==200,first.get_json();state=first.get_json();before=deepcopy(state['topology'])
    channel=before['nodes'][1]['ports'][0]['hardwareInterfaceId'];channel_url='/api/engineering/hardware-interfaces/'+channel
    relation_url='/api/engineering/relations/'+before['edges'][0]['engineeringRelationId']
    before_channel=c.get(channel_url).get_json();before_relation=c.get(relation_url).get_json()
    change=deepcopy(before);change['nodes'][1]['ports']=[];change['edges']=change['edges'][1:]
    original=WorkflowStatusService.save_topology
    with monkeypatch.context() as p:
        def fail(*args,**kwargs):
            original(*args,**kwargs);raise EngineeringValidationError('Injected deletion failure')
        p.setattr(WorkflowStatusService,'save_topology',fail)
        r=save(change,state)
    assert r.status_code==400,r.get_json()
    assert c.get(channel_url).get_json()==before_channel
    assert c.get(relation_url).get_json()==before_relation
    assert c.get('/api/engineering/workflow').get_json()['topology']==before
    r=save(change,state);assert r.status_code==200,r.get_json();state=r.get_json()
    assert c.get(relation_url).status_code==404
    assert not c.get(channel_url).get_json()['network_ref']
    assert 'network_id' not in c.get(channel_url).get_json().get('capabilities', {})
    assert not next(n for n in state['topology']['nodes'] if n['id']=='a')['ports']
    assert state['topology']['scene']['buses'][0]['participantCount']==2
    assert save(change,first.get_json()).status_code==409
    # Deleting the remaining bus releases its channels without deleting/recreating them.
    topology=deepcopy(state['topology']);topology['edges']=[]
    old={n['id']:n['ports'][0] for n in topology['nodes'] if n['ports']}
    r=save(topology,state);assert r.status_code==200,r.get_json();state=r.get_json()
    assert not state['topology']['scene']['buses']
    free={n['id']:n['ports'][0] for n in state['topology']['nodes'] if n['ports']}
    for key in ['owner','b']:
        assert free[key]['hardwareInterfaceId']==old[key]['hardwareInterfaceId']
        assert free[key]['physicalNetworkId']!='bus'
        hwi=c.get('/api/engineering/hardware-interfaces/'+free[key]['hardwareInterfaceId']).get_json()
        assert hwi['network_ref']==free[key]['physicalNetworkId']
    assert free['owner']['physicalNetworkId']!=free['b']['physicalNetworkId']
    assert c.get('/api/engineering/workflow').get_json()['topology']==state['topology']
    topology=deepcopy(state['topology']);next(n for n in topology['nodes'] if n['id']=='b')['ports'][0]['physicalNetworkId']=free['owner']['physicalNetworkId']
    topology['edges']=[{'id':'reconnected','source':'owner','sourcePort':'owner','target':'b','targetPort':'b','bus':'can_fd','physicalNetworkId':free['owner']['physicalNetworkId']}]
    r=save(topology,state);assert r.status_code==200,r.get_json()
    assert len(r.get_json()['topology']['scene']['buses'])==1


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'),reason='Separate SQL database required')
@pytest.mark.parametrize('reference', ['edge', 'source', 'destination'])
def test_last_deleted_edge_invalidates_manual_route_without_deleting_payload(reference):
    from backend.tests.test_engineering_api import _client
    from backend.tests.test_routing import route_payload
    from backend.engineering.routing.repository import create_route, get_route
    from backend.engineering.project_context import activate_project
    from backend.engineering.db import get_connection
    from backend.engineering.topology_removal import retire_removed_connections
    client = _client()
    activate_project(client.environ_base['HTTP_X_PROJECT_ID'])
    payload = route_payload()
    channel = '00000000-0000-0000-0000-000000000051'
    if reference == 'source': payload['source']['port_id'] = channel
    if reference == 'destination': payload['destinations'][0]['port_id'] = channel
    row = create_route(payload)
    unrelated = create_route(route_payload(name='Unaffected route'))
    with get_connection() as connection:
        connection.execute("UPDATE engineering_routing_entries SET approval_state='APPROVED' WHERE id=%s", (row['id'],))
    before = {'nodes': [], 'edges': [{'id': 'removed'}]}
    if reference == 'edge':
        before['edges'][0]['routingEntryIds'] = [str(row['id'])]
    else:
        # No route ID attached to the deleted edge: find the canonical endpoint reference.
        before['nodes'] = [{'ports': [{'id': 'canvas-port', 'hardwareInterfaceId': channel, 'physicalNetworkId': 'bus'}]}]
    retire_removed_connections(before, {'nodes': [], 'edges': []})
    current = get_route(str(row['id']))
    assert current['status']=='OUTDATED'
    assert current['approval_state']=='PENDING'
    assert current['validation']['valid'] is False
    assert any(w['code']=='PHYSICAL_PATH_REMOVED' for w in current['validation']['warnings'])
    assert current['payload']==row['payload']
    assert get_route(str(unrelated['id']))==unrelated


def test_disconnect_membership_preserves_other_connected_drawing_aliases():
    from backend.engineering.topology_removal import removed_endpoint_references
    ports = [{'id': identifier, 'hardwareInterfaceId': 'canonical', 'physicalNetworkId': 'bus'} for identifier in ['a', 'alias']]
    before = {'nodes': [{'ports': ports}], 'edges': [{'id': 'one', 'sourcePort': 'a', 'targetPort': 'alias'}]}
    after = deepcopy(before)
    after['edges'] = [{'id': 'other', 'sourcePort': 'alias', 'targetPort': 'elsewhere'}]
    assert removed_endpoint_references(before, after) == set()
    after['edges'] = []
    assert removed_endpoint_references(before, after) == {'canonical', 'a', 'alias'}
    after = deepcopy(before)
    after['nodes'][0]['ports'][0]['physicalNetworkId'] = 'new-bus'
    after['nodes'][0]['ports'][1]['physicalNetworkId'] = 'new-bus'
    assert removed_endpoint_references(before, after) == {'canonical', 'a', 'alias'}
