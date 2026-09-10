from copy import deepcopy
import json
import pytest

from backend.engineering.network_assignment import plan_assignment, confirmed_context
from backend.engineering.network_scene import build_network_scene, confirmed_groups
from backend.engineering.models import EngineeringValidationError


def fixture():
    nodes = [{'id': n, 'engineeringId': n, 'name': n, 'kind': k, 'ports': []} for n,k in
             [('Gateway','gateway'),('A','ecu'),('B','ecu'),('Sensor','sensor'),('X','actuator'),('Y','actuator'),('Z','sensor')]]
    by_id = {n['id']:n for n in nodes}
    objects = {k:[] for k in ('HardwareNode','HardwareNetworkInterface','Interface','Message','Signal')}
    edges = []
    for a,b,network,bus in [('Gateway','A','CAN_A','can_fd'),('Gateway','B','CAN_B','can_fd'),
                          ('A','Sensor','LIN_A','lin'),('A','X','LIN_A','lin'),('A','Y','LIN_A','lin'),('B','Z','LIN_B','lin')]:
        for key in (a,b):
            pid=key+network
            if any(p['id']==pid for p in by_id[key]['ports']):continue
            by_id[key]['ports'].append({'id':pid,'name':network,'hardwareInterfaceId':pid,'engineeringId':pid,'physicalNetworkId':network,'physicalNetworkName':network,'bus':bus})
            objects['HardwareNetworkInterface'].append({'id':pid,'hardware_node_id':key,'name':network,'network_ref':network,'technology':'LIN' if bus=='lin' else 'CAN_FD','channel_index':len(by_id[key]['ports']),'capabilities':{}})
            objects['Interface'].append({'id':'i'+pid,'name':pid,'hardware_node_id':key,'interface_type':'LIN' if bus=='lin' else 'CAN_FD','configuration':{}})
        edges.append({'id':a+b,'source':a,'target':b,'sourcePort':a+network,'targetPort':b+network,'physicalNetworkId':network,'bus':bus,'routingEntryIds':[]})
    for node in nodes:
        owner='A' if node['id'] in {'Sensor','X','Y'} else 'B' if node['id']=='Z' else None
        identity={'system_owner_id':owner,'system_owner_source':'wizard-confirmed'} if owner else {}
        node.update(systemOwnerId=owner)
        objects['HardwareNode'].append({'id':node['id'],'name':node['name'],'identity':identity,'device_type':node['kind']})
    routes=[]
    for source,dest,message,network,edge_ids in [('A','B','status','CAN_A',['GatewayA','GatewayB']),
          ('Sensor','A','measurement','LIN_A',['ASensor']),('X','A','ackX','LIN_A',['AX']),('Y','A','ackY','LIN_A',['AY']),
          ('A','X','command','LIN_A',['AX']),('A','Y','command','LIN_A',['AY'])]:
        identifier=source+dest
        for edge in edges:
            if edge['id'] in edge_ids:edge['routingEntryIds'].append(identifier)
        protocol='CAN_FD' if network.startswith('CAN') else 'LIN'
        routes.append({'id':identifier,'name':source+' → '+dest,'revision':1,'status':'APPROVED','approval_state':'APPROVED',
            'source':{'node_id':source,'node_name':source,'interface_id':'i'+source+network,'port_id':source+network,'network_id':network,'protocol':protocol},
            'destinations':[{'node_id':dest,'node_name':dest,'interface_id':'i'+dest+('CAN_B' if dest=='B' else network),'port_id':dest+('CAN_B' if dest=='B' else network),'network_id':'CAN_B' if dest=='B' else network,'protocol':protocol}],
            'payload':{'message_id':message,'message_ids':[message],'signal_ids':[message+'Signal']},'route':{},'validation':{'valid':True}})
        if not any(m['id']==message for m in objects['Message']):
            objects['Message'].append({'id':message,'name':message,'interface_id':'i'+source+network,'hardware_interface_id':source+network,'message_id_hex':hex(len(objects['Message'])+1),'dlc':2,'cycle_ms':20,
                'configuration':{'transport_unit':{'producer_ref':source,'consumer_refs':[dest]},'communication_contract':{'producer_ref':source,'consumer_refs':[dest]}}})
            objects['Signal'].append({'id':message+'Signal','name':message+'Signal','message_id':message,'length_bits':8,'factor':.1,'unit':'C','start_bit':0,'communication':{},'configuration':{}})
    graph=[{'cluster_id':'first','label':'Antrieb','controllers':[{'ecu':'A','sensors':['Sensor'],'actuators':['X','Y']}]},
           {'cluster_id':'second','label':'Komfort','controllers':[{'ecu':'B','sensors':['Z']}]}]
    prompt='- Systemcluster-Graph: '+json.dumps(graph)
    topology=build_network_scene({'nodes':nodes,'edges':edges},prompt)
    networks=[{'id':n,'name':n,'technology':t} for n,t in [('CAN_A','can_fd'),('CAN_B','can_fd'),('LIN_A','lin'),('LIN_B','lin')]]
    return {'topology':topology,'parameters':{'networks':networks},'context':{'wizard_request':{'prompt':prompt,'version':1}}},objects,routes


def test_whole_frame_moves_children_and_backbone_but_keeps_internal_buses():
    state,objects,routes=fixture()
    before=deepcopy((state,objects,routes))
    request={'node_ids':['A'],'target_kind':'cluster','target_id':'second'}
    plan=plan_assignment(state,objects,routes,request)
    assert set(plan['preview']['node_ids'])=={'A','Sensor','X','Y'}
    assert next(e for e in plan['topology']['edges'] if e['id']=='GatewayA')['physicalNetworkId']=='CAN_B'
    assert next(e for e in plan['topology']['edges'] if e['id']=='AX')['physicalNetworkId']=='LIN_A'
    assert all(m['to_cluster']=='Komfort' for m in plan['membership'])
    assert next(f for f in plan['topology']['scene']['frames'] if f['id']=='A')['clusterId']=='second'
    assert not plan['creations']
    assert (state,objects,routes)==before
    assert plan_assignment(state,objects,routes,request)['preview']['token']==plan['preview']['token']


def test_actuator_move_clones_shared_command_and_preserves_other_consumer():
    state,objects,routes=fixture()
    next(s for s in objects['Signal'] if s['id']=='commandSignal')['protocol_bindings']=[{'source_ref':'A','technology_binding_ref':'lin','unit':'C'}]
    plan=plan_assignment(state,objects,routes,{'node_ids':['X'],'target_kind':'frame','target_id':'B'})
    assert plan['preview']['new_commands']==1
    assert next(e for e in plan['topology']['edges'] if e['id']=='AX')['source']=='B'
    assert next(e for e in plan['topology']['edges'] if e['id']=='AX')['physicalNetworkId']=='LIN_B'
    command=next(r for r in plan['routes'] if r['id']=='AX')
    assert command['source']['node_id']=='B'
    assert command['source']['port_id']=='BLIN_B'
    assert command['payload']['message_id'].startswith('$assignment-')
    assert all(r['id']!='AY' for r in plan['routes'])
    assert plan['changes']['Message','command']['configuration']['transport_unit']['consumer_refs']==['Y']
    assert plan['changes']['Message','ackX']['configuration']['transport_unit']['consumer_refs']==['B']
    signal=next(c for c in plan['creations'] if c['object_type']=='Signal')['data']
    assert signal['factor']==.1 and signal['unit']=='C' and signal['length_bits']==8
    assert signal['protocol_bindings'][0]['source_ref']=='B'
    assert signal['configuration']['functional_owner']=='B'


def test_signal_payload_rebinds_parent_message_without_changing_payload_type():
    state,objects,routes=fixture()
    command=next(r for r in routes if r['id']=='AX')
    command['payload']={'payload_type':'SIGNAL','signal_ids':['commandSignal']}
    plan=plan_assignment(state,objects,routes,{'node_ids':['X'],'target_kind':'frame','target_id':'B'})
    updated=next(r for r in plan['routes'] if r['id']=='AX')
    assert updated['payload']['payload_type']=='SIGNAL'
    assert updated['payload']['message_id'] is None
    assert updated['payload']['signal_ids'][0].startswith('$assignment-')
    created=next(c for c in plan['creations'] if c['object_type']=='Message')
    assert created['data']['hardware_interface_id']=='BLIN_B'
    assert created['data']['configuration']['transport_unit']['consumer_refs']==['X']


def test_multicast_move_splits_only_selected_recipient_and_keeps_remaining_command():
    state,objects,routes=fixture()
    remaining=next(r for r in routes if r['id']=='AY')
    command=next(r for r in routes if r['id']=='AX')
    command['destinations'].extend(remaining['destinations'])
    routes.remove(remaining)
    plan=plan_assignment(state,objects,routes,{'node_ids':['X'],'target_kind':'frame','target_id':'B'})
    preserved=next(r for r in plan['routes'] if r['id']=='AX')
    assert preserved['source']['node_id']=='A'
    assert [d['node_id'] for d in preserved['destinations']]==['Y']
    new=next(r for r in plan['routes'] if r.get('_assignment_new'))
    assert new['source']['node_id']=='B'
    assert [d['node_id'] for d in new['destinations']]==['X']
    assert new['payload']['message_id']!=preserved['payload']['message_id']
    assert plan['changes']['Message','command']['configuration']['transport_unit']['consumer_refs']==['Y']
    assert plan['preview']['new_routes']==1


def test_nested_controller_and_explicit_cluster_survive_scene_rebuild_and_wizard_context():
    state,objects,routes=fixture()
    plan=plan_assignment(state,objects,routes,{'node_ids':['A'],'target_kind':'frame','target_id':'B'})
    frame=next(f for f in plan['topology']['scene']['frames'] if f['id']=='B')
    assert {'A','Sensor','X','Y','B','Z'}==set(frame['memberIds'])
    assert frame['processors']==2
    context=confirmed_context(state,plan['topology'],plan)
    rebuilt=build_network_scene(plan['topology'],context['wizard_request']['prompt'])
    assert set(next(f for f in rebuilt['scene']['frames'] if f['id']=='B')['memberIds'])==set(frame['memberIds'])
    assert context['equipment_assignment_feedback'][-1]['accepted'] is True


@pytest.mark.parametrize('assignment',[
    {'node_ids':['A'],'target_kind':'frame','target_id':'A'},
    {'node_ids':['A'],'target_kind':'cluster','target_id':'missing'},
    {'node_ids':['missing'],'target_kind':'cluster','target_id':'second'},
    {'node_ids':['Gateway'],'target_kind':'cluster','target_id':'second'},
])
def test_invalid_assignment_is_rejected_before_writes(assignment):
    with pytest.raises(EngineeringValidationError):plan_assignment(*fixture(),assignment)


def test_cycles_rejected_and_empty_manual_owner_does_not_reinfer_old_owner():
    state,objects,routes=fixture()
    topology=deepcopy(state['topology'])
    by_id={n['id']:n for n in topology['nodes']}
    by_id['X'].update(systemOwnerId=None,systemOwnerSource='network-editor',clusterId='second',clusterName='Komfort')
    _,owners=confirmed_groups(topology,state['context']['wizard_request']['prompt'])
    assert 'X' not in owners
    by_id['A']['systemOwnerId']='B'
    by_id['B']['systemOwnerId']='A'
    with pytest.raises(ValueError,match='Zyklische'):confirmed_groups(topology,'')
