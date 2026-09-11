from copy import deepcopy

from backend.engineering.communication_intent import FunctionalArchitecture
from backend.engineering.communication_repair import RepairPlanner
from backend.tests.test_communication_repair import sample, SQL, sql_sample


def move_function(data, role):
    state, objects, routes, history = data
    host = 'new-' + role
    objects['HardwareNode'].append({'id':host,'name':host,'object_type':'HardwareNode','device_type':'ECU','version':1})
    function = next(f for f in objects['Function'] if f['id'] == role+'-function')
    function['hardware_node_id'] = host
    objects['HardwareNetworkInterface'].append({'id':host+'-port','name':host+'-port','hardware_node_id':host,'technology':'CAN_FD','network_ref':'replacement','version':1})
    state['topology']['nodes'].append({'id':host,'engineeringId':host,'name':host,'kind':'ecu','ports':[{'id':host+'-drawing','hardwareInterfaceId':host+'-port','physicalNetworkId':'replacement','bus':'can_fd'}]})
    partner = 'receiver' if role=='producer' else 'producer'
    state['topology']['edges'].append({'id':host+'-edge','source':host,'target':partner,'sourcePort':host+'-drawing','targetPort':partner+'-drawing','physicalNetworkId':'replacement','bus':'can_fd'})
    return data


def test_current_function_host_replaces_old_hardware_but_keeps_partner_and_signal_ids():
    data=move_function(sample(),'receiver')
    before=deepcopy(data)
    plan=RepairPlanner(*data).build()
    option=plan['groups'][0]['options'][0]
    route=option['route_changes'][0]
    assert route['destinations'][0]['node_id']=='new-receiver'
    assert route['destinations'][0]['interface_id']=='receiver-interface'
    assert route['route']['functional_intent']['destinations'][0]['function_id']=='receiver-function'
    assert route['route']['physical_paths'][0]['edges']==['new-receiver-edge']
    assert option['interface_changes'][0]['data']=={'hardware_node_id':'new-receiver'}
    assert data==before, 'Preview never changes the architecture'
    assert option['comparison'][0]['functions']['destinations'][0]['function']=='receiver-function'


def test_moving_one_publisher_does_not_move_other_functions_messages_sharing_old_port():
    data=move_function(sample(),'producer');state,objects,routes,history=data
    objects['Function'].append({'id':'stays','name':'stays','object_type':'Function','hardware_node_id':'producer'})
    objects['Interface'].append({'id':'stays-if','name':'stays-if','object_type':'Interface','hardware_node_id':'producer','function_id':'stays','interface_type':'CAN_FD'})
    objects['Message'][0]['hardware_interface_id']='producer-port'
    objects['Message'].append({**deepcopy(objects['Message'][0]),'id':'stays-message','interface_id':'stays-if','message_id_hex':'0x101'})
    routes[0]['source'].update(port_id='producer-port',network_id='replacement')
    option=RepairPlanner(*data).build()['groups'][0]['options'][0]
    assert option['route_changes'][0]['source']['node_id']=='new-producer'
    assert [c['id'] for c in option['message_changes']]==['message']
    assert option['message_changes'][0]['data']['hardware_interface_id']=='new-producer-port'


def test_architecture_never_chooses_a_function_by_device_or_route_name_when_ambiguous():
    state,objects,routes,history=sample()
    objects['Function'].append({'id':'another','name':'Existing communication','object_type':'Function','hardware_node_id':'receiver'})
    routes[0]['destinations'][0]['interface_id']=None
    plan=RepairPlanner(state,objects,routes,history).build()
    assert plan['architecture']['resolved']==0
    assert plan['groups'][0]['status']=='BLOCKED'
    assert not plan['groups'][0]['options']


def test_recorded_partner_survives_a_network_editor_end_replacement():
    state,objects,routes,history=sample()
    architecture=FunctionalArchitecture(objects)
    _,intent,_=architecture.project(routes[0],{'message'})
    routes[0]['route']['functional_intent']=intent
    routes[0]['destinations'][0].update(node_id='producer',interface_id='producer-interface',port_id='producer-port')
    option=RepairPlanner(state,objects,routes,history).build()['groups'][0]['options'][0]
    assert option['route_changes'][0]['destinations'][0]['node_id']=='receiver'
    assert option['route_changes'][0]['destinations'][0]['interface_id']=='receiver-interface'


def test_co_located_functions_are_not_falsely_routed_over_an_external_bus():
    state,objects,routes,history=sample()
    objects['Function'][1]['hardware_node_id']='producer'
    plan=RepairPlanner(state,objects,routes,history).build()
    assert plan['groups'][0]['status']=='BLOCKED'
    assert 'lokale Kommunikation' in plan['groups'][0]['reason']


def test_basic_sensor_io_is_preserved_without_inventing_a_function_object():
    state,objects,routes,history=sample()
    objects['HardwareNode'][0]['device_type']='SensorController'
    objects['Function']=objects['Function'][1:]
    objects['Interface'][0]['function_id']=None
    plan=RepairPlanner(state,objects,routes,history).build()
    assert plan['architecture']['resolved']==1 and plan['architecture']['device_io']==1
    option=plan['groups'][0]['options'][0]
    intent=option['route_changes'][0]['route']['functional_intent']['source']
    assert intent['partner_type']=='hardware_io' and intent['hardware_node_id']=='producer'


@SQL
def test_sql_function_migration_updates_transport_and_preserves_other_communication():
    from backend.engineering.repository import create_object,update_object,get_object
    from backend.engineering.routing.repository import get_route
    from backend.engineering.db import get_connection
    from backend.engineering.project_context import current_project_id
    from psycopg.types.json import Jsonb
    client,ids=sql_sample()
    base='/api/engineering/workflow/communication-repair/'
    host=create_object('HardwareNode',{'name':'New receiver ECU','device_type':'ECU'})
    host_id=str(host['id'])
    update_object('Function',ids['receiver-function'],{'hardware_node_id':host_id})
    port=create_object('HardwareNetworkInterface',{'name':'New receiver CAN','hardware_node_id':host_id,'technology':'CAN_FD','network_ref':'replacement'})
    with get_connection() as connection:
        row=connection.execute('SELECT topology FROM engineering_workflow_projects WHERE project_id=%s',(current_project_id(),)).fetchone()
        topology=row['topology'];old=topology['nodes'][0]
        topology['nodes'].append({'id':host_id,'engineeringId':host_id,'name':host['name'],'kind':'ecu','ports':[{'id':'new-drawing','hardwareInterfaceId':str(port['id']),'bus':'can_fd','physicalNetworkId':'replacement'}]})
        topology['edges'].append({'id':'new-host-wire','source':old['id'],'target':host_id,'sourcePort':old['ports'][0]['id'],'targetPort':'new-drawing','physicalNetworkId':'replacement','bus':'can_fd'})
        connection.execute('UPDATE engineering_workflow_projects SET topology=%s WHERE project_id=%s',(Jsonb(topology),current_project_id()))
    before_signal=get_object('Signal',ids['signal']);before_route=get_route(ids['route'])
    plan=client.post(base+'preview',json={}).get_json();group=plan['groups'][0]
    option=next(o for o in group['options'] if o['action']=='adopt')
    response=client.post(base+'apply',json={'token':plan['token'],'choices':{group['id']:option['id']}})
    assert response.status_code==200,response.get_json()
    changed=get_route(ids['route'])
    assert changed['destinations'][0]['node_id']==host_id
    assert changed['destinations'][0]['function_id']==ids['receiver-function']
    assert str(get_object('Interface',ids['receiver-interface'])['hardware_node_id'])==host_id
    assert get_object('Signal',ids['signal'])==before_signal
    assert changed['payload']==before_route['payload'] and changed['timing']==before_route['timing']
    assert changed['validation']['valid'] and changed['approval_state']=='PENDING'
    assert not client.post(base+'preview',json={}).get_json()['groups']


@SQL
def test_sql_network_edit_retains_established_function_partner_until_repair():
    from backend.engineering.routing.repository import get_route,update_route
    client,ids=sql_sample()
    original=get_route(ids['route'])
    assert original['route']['functional_intent']['destinations'][0]['function_id']==ids['receiver-function']
    update_route(ids['route'],{'destinations':[{**original['destinations'][0],'node_id':ids['producer'],
        'interface_id':ids['producer-interface'],'port_id':ids['producer-port']}],'modified_by':'network-editor'})
    changed=get_route(ids['route'])
    assert changed['route']['functional_intent']['destinations'][0]['function_id']==ids['receiver-function']
    base='/api/engineering/workflow/communication-repair/'
    plan=client.post(base+'preview',json={}).get_json();group=plan['groups'][0]
    option=next(o for o in group['options'] if o['action']=='adopt')
    result=client.post(base+'apply',json={'token':plan['token'],'choices':{group['id']:option['id']}})
    assert result.status_code==200,result.get_json()
    restored=get_route(ids['route'])
    assert restored['destinations'][0]['node_id']==ids['receiver']
    assert restored['destinations'][0]['interface_id']==ids['receiver-interface']
    assert restored['route']['functional_intent']['destinations'][0]['function_id']==ids['receiver-function']
