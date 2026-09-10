from copy import deepcopy
import pytest

from backend.engineering.network_assignment import plan_assignment, confirmed_context
from backend.engineering.network_scene import build_network_scene
from backend.engineering.models import EngineeringValidationError
from backend.tests.test_network_assignment import fixture


def same_cluster():
    state, objects, routes = fixture()
    for n in state['topology']['nodes']:
        if n['id'] in {'B', 'Z'}:
            n.update(clusterId='first', clusterName='Antrieb')
    state['topology'] = build_network_scene(state['topology'], state['context']['wizard_request']['prompt'])
    return state, objects, routes


def request(node='A', source='CAN_A', target='CAN_B'):
    return {'node_ids':[node], 'target_kind':'bus', 'source_network_id':source, 'target_id':target}


def test_controller_transfer_preserves_membership_and_internal_bus_and_updates_route():
    state, objects, routes = same_cluster()
    before = deepcopy((state, objects, routes))
    plan = plan_assignment(state, objects, routes, request())
    assert not plan['membership']
    assert not any(kind == 'HardwareNode' for kind, _ in plan['changes'])
    assert confirmed_context(state, plan['topology'], plan) == state['context']
    assert plan['preview']['node_ids'] == ['A']
    assert {r['id'] for r in plan['routes']} == {'AB'}
    route = plan['routes'][0]
    assert route['source']['port_id'] == 'ACAN_A'
    assert route['source']['network_id'] == 'CAN_B'
    assert route['source']['interface_id'] == 'iACAN_A'
    assert route['destinations'][0]['node_id'] == 'B'
    assert plan['changes']['HardwareNetworkInterface','ACAN_A']['network_ref'] == 'CAN_B'
    before_edges = {e['id']:e for e in state['topology']['edges']}
    for e in plan['topology']['edges']:
        if e['id'] in {'ASensor','AX','AY'}:
            assert e == before_edges[e['id']]
    assert before == (state, objects, routes)
    assert plan['preview']['token'] == plan_assignment(state, objects, routes, request())['preview']['token']


def test_transfer_checks_message_collisions_and_reuses_gateway_target_port():
    state, objects, routes = same_cluster()
    objects['Message'].append({'id':'occupied', 'interface_id':'iBCAN_B', 'hardware_interface_id':'BCAN_B',
                              'message_id_hex':objects['Message'][0]['message_id_hex'], 'configuration':{}})
    plan = plan_assignment(state, objects, routes, request())
    assert plan['changes']['Message','status']['message_id_hex'] != objects['Message'][0]['message_id_hex']
    assert not plan['creations']
    assert next(e for e in plan['topology']['edges'] if e['id']=='GatewayA')['sourcePort'] == 'GatewayCAN_B'


def test_unrouted_messages_keep_contract_and_follow_physical_port():
    state, objects, routes = same_cluster()
    objects['Message'].extend([
        {'id':'unrouted', 'interface_id':'iACAN_A', 'hardware_interface_id':'ACAN_A', 'message_id_hex':'0x77',
         'configuration':{'communication_contract':{'consumer_refs':['B']}, 'physical_transmit_bindings':[
             {'hardware_interface_id':'ACAN_A','network_id':'CAN_A'}]}},
        {'id':'occupied', 'interface_id':'iBCAN_B', 'hardware_interface_id':'BCAN_B', 'message_id_hex':'0x77', 'configuration':{}},
    ])
    plan = plan_assignment(state, objects, routes, request())
    message = plan['changes']['Message','unrouted']
    assert message['configuration']['physical_transmit_bindings'][0]['network_id'] == 'CAN_B'
    assert message['configuration']['communication_contract']['consumer_refs'] == ['B']
    assert message['message_id_hex'] != '0x77'
    assert plan['preview']['messages'] == 2


@pytest.mark.parametrize('mutation, message', [
    ('foreign', 'selben Cluster'), ('same', 'bereits'), ('technology', 'desselben Typs'),
    ('full', 'Teilnehmergrenze'), ('existing', 'bereits einen Anschluss'), ('local', 'Systemrahmens'),
])
def test_invalid_bus_transfer_never_mutates_inputs(mutation, message):
    state, objects, routes = same_cluster()
    req = request()
    if mutation == 'foreign': state, objects, routes = fixture()
    elif mutation == 'same': req['target_id']='CAN_A'
    elif mutation == 'technology': next(b for b in state['topology']['scene']['buses'] if b['id']=='CAN_B')['technology']='lin'
    elif mutation == 'full': state['context']['engineering_wizard_settings']={'bus_participant_limits':{'can_fd':2}}
    elif mutation == 'existing': next(b for b in state['topology']['scene']['buses'] if b['id']=='CAN_B')['branches'].append({'nodeId':'A'})
    elif mutation == 'local': req=request('Sensor','LIN_A','LIN_B')
    before=deepcopy((state,objects,routes))
    with pytest.raises(EngineeringValidationError,match=message): plan_assignment(state,objects,routes,req)
    assert before==(state,objects,routes)


def local_buses():
    state,objects,routes=same_cluster()
    nodes={n['id']:n for n in state['topology']['nodes']}
    # Add a second existing local bus of A, attached to Z. No ownership changes
    # are allowed as part of the later transfer of Sensor from LIN_A to LIN_B.
    p=next(p for p in nodes['B']['ports'] if p['id']=='BLIN_B')
    nodes['B']['ports'].remove(p)
    nodes['A']['ports'].append(p)
    nodes['Z'].update(systemOwnerId='A')
    next(h for h in objects['HardwareNode'] if h['id']=='Z')['identity']['system_owner_id']='A'
    next(h for h in objects['HardwareNetworkInterface'] if h['id']=='BLIN_B').update(hardware_node_id='A', channel_index=3)
    edge=next(e for e in state['topology']['edges'] if e['id']=='BZ')
    edge['source']='A'
    state['topology']=build_network_scene(state['topology'],state['context']['wizard_request']['prompt'])
    return state, objects, routes


def test_local_sensor_moves_only_between_buses_of_same_owner():
    state, objects, routes = local_buses()
    plan=plan_assignment(state,objects,routes,request('Sensor','LIN_A','LIN_B'))
    assert not plan['membership']
    measurement=next(r for r in plan['routes'] if r['id']=='SensorA')
    assert measurement['source']['network_id']==measurement['destinations'][0]['network_id']=='LIN_B'
    assert measurement['destinations'][0]['node_id']=='A'
    assert measurement['destinations'][0]['port_id']=='BLIN_B'
    assert next(n for n in plan['topology']['nodes'] if n['id']=='Sensor')['systemOwnerId']=='A'


def test_local_multicast_command_splits_physical_transmission_and_keeps_other_recipient():
    state, objects, routes = local_buses()
    command = next(r for r in routes if r['id']=='AX')
    other = next(r for r in routes if r['id']=='AY')
    command['destinations'].extend(other['destinations'])
    routes.remove(other)
    plan = plan_assignment(state, objects, routes, request('X','LIN_A','LIN_B'))
    old = next(r for r in plan['routes'] if r['id']=='AX')
    new = next(r for r in plan['routes'] if r.get('_assignment_new'))
    assert old['source']['port_id']=='ALIN_A'
    assert [d['node_id'] for d in old['destinations']]==['Y']
    assert new['source']['port_id']=='BLIN_B'
    assert [d['node_id'] for d in new['destinations']]==['X']
    assert old['payload']==new['payload']
    assert {b['network_id'] for b in plan['changes']['Message','command']['configuration']['physical_transmit_bindings']}=={'LIN_A','LIN_B'}


def test_transfer_cannot_silently_use_shorter_route_on_another_device_port():
    state, objects, routes = same_cluster()
    for n in state['topology']['nodes']:
        if n['id'] not in {'A','B'}: continue
        port = {'id':n['id']+'CAN_C','bus':'can_fd','physicalNetworkId':'CAN_C','physicalNetworkName':'CAN_C',
                'hardwareInterfaceId':n['id']+'CAN_C','engineeringId':n['id']+'CAN_C'}
        n['ports'].append(port)
        objects['HardwareNetworkInterface'].append({'id':port['id'],'hardware_node_id':n['id'],'technology':'CAN_FD','channel_index':3,'network_ref':'CAN_C'})
    state['topology']['edges'].append({'id':'shorter','source':'A','target':'B','sourcePort':'ACAN_C','targetPort':'BCAN_C','bus':'can_fd','physicalNetworkId':'CAN_C'})
    state['parameters']['networks'].append({'id':'CAN_C','name':'CAN_C','technology':'can_fd'})
    state['topology']=build_network_scene(state['topology'],state['context']['wizard_request']['prompt'])
    plan=plan_assignment(state,objects,routes,request())
    route=next(r for r in plan['routes'] if r['id']=='AB')
    assert route['source']['network_id']=='CAN_B'
    assert route['source']['port_id']=='ACAN_A'
    assert route['destinations'][0]['network_id']=='CAN_B'
