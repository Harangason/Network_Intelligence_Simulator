"""MQTT-SN1.2 own datagram framing, gateway/topic scope, QoSminus1 and sleep regressions."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.mqtt_sn import rules as SN

def actual(kind='CONNECT',variable=5,length_bytes=1):
    x={'sn_'+k:'synthetic-actual-'+k for k in SN.REQUIRED}
    total=length_bytes+1+variable
    x.update(sn_version='V1_2',sn_transport='UDP_IPV4',sn_port=20000,sn_binding_profile='REGISTERED',
        sn_endpoint_role='CLIENT',sn_direction='CLIENT_TO_GATEWAY',sn_discovery='PRECONFIGURED',
        sn_packet_kind=kind,sn_phase='NEW',sn_bidirectional_datagram=True,sn_protocol_fragmentation=False,
        sn_network_packet_max=65535,sn_length_bytes=length_bytes,sn_variable_bytes=variable,
        sn_length_value=total,sn_packet_bytes=total,sn_msg_type=SN.KINDS[kind],
        sn_protocol_id=1,sn_keepalive_s=30,sn_client_id='A',sn_client_id_bytes=1,sn_client_characters=1,
        sn_will=False,sn_clean_session=False,sn_flags=0)
    return x

def status(x):return registry.validate_parameters('mqtt_sn',x)['status']

def publish(qos=1,topic='NORMAL',body=8,length_bytes=1):
    x=actual('PUBLISH',5+body,length_bytes);type_={'NORMAL':0,'PREDEFINED':1,'SHORT':2}[topic]
    x.update(sn_topic_kind=topic,sn_topic_type=type_,sn_qos=qos,sn_dup=False,sn_retain=False,
        sn_flags=32*(3 if qos==-1 else qos)+type_,sn_msg_id=9 if qos in(1,2)else 0,payload_bytes=body)
    if topic=='SHORT':x.update(sn_short_topic='é',sn_short_topic_bytes=2)
    else:x.update(sn_topic_id=12,sn_mapping_known=True,sn_mapping_source='synthetic-accepted-map',
        sn_mapping_client_ref=x['sn_client_ref'],sn_mapping_gateway_ref=x['sn_gateway_ref'])
    if qos==-1:x.update(sn_gateway_address='192.0.2.20',sn_preconfigured_gateway_source='synthetic-known-gateway')
    return x

def response(kind,variable=5):
    x=actual(kind,variable);x.update(sn_phase='RESPONSE',sn_endpoint_role='GATEWAY',sn_direction='GATEWAY_TO_CLIENT',
        sn_return_code=0,sn_msg_id=9,sn_request_msg_id=9,sn_pending_match=True,
        sn_request_client_ref=x['sn_client_ref'],sn_request_gateway_ref=x['sn_gateway_ref'])
    return x

def test_mqtt_sn_no_foreign_radio_can_or_ethernet_defaults_or_mqtt5_fields():
    fields=registry.parameter_fields('mqtt_sn');keys=[v['key']for v in fields]
    assert len(keys)==len(set(keys));assert not set(SN.REMOVED)&set(keys)
    assert registry.parameter_defaults_review('mqtt_sn')['values']=={}
    assert registry.profile('mqtt_sn')['domain']=='generic_networking'
    assert registry.profile('mqtt_sn')['capacity_evidence']['status']=='MODEL_MISSING'
    assert status(actual())=='VALID'
    for patch in ({'bitrate':250000},{'mtu_bytes':1500},{'queue_size':256},{'retry_limit':3},
        {'mq_receive_maximum':65535},{'mq_topic_alias':1},{'mq_clean_start':True},
        {'local_timing_evidence':{'technology':'CAN'}},{'sn_version':'V2_0'},{'sn_protocol_fragmentation':True}):
        assert status({**actual(),**patch})=='INVALID'
    for key in ('sn_port','sn_client_id','sn_gateway_id','sn_topic_id','sn_keepalive_s','sn_sleep_s','sn_network_packet_max'):
        field=next(v for v in fields if v['key']==key)
        assert 'default'not in field;assert not field.get('conditional_defaults')

@pytest.mark.parametrize('field',registry.parameter_fields('mqtt_sn'),ids=lambda f:f['key'])
def test_mqtt_sn_every_declared_type_and_own_bounds(field):
    wrong='not-a-number'if field['type']=='number'else 1
    assert status({**actual(),field['key']:wrong})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('qos',[-1,0,1,2])
@pytest.mark.parametrize('topic',['NORMAL','PREDEFINED','SHORT'])
def test_mqtt_sn_publish_native_qos_flag_identifier_topic_forms_and_complete_lengths(qos,topic):
    x=publish(qos,topic)
    if qos==-1 and topic=='NORMAL':assert status(x)=='INVALID';return
    assert status(x)=='VALID'
    for patch in ({'sn_flags':x['sn_flags']^8},{'sn_topic_type':3},{'sn_variable_bytes':x['sn_variable_bytes']+1},
        {'sn_packet_bytes':x['sn_packet_bytes']+1},{'sn_msg_id':9 if qos in(-1,0)else 0}):
        assert status({**x,**patch})=='INVALID'
    if qos==-1:
        y=x.copy();y.pop('sn_preconfigured_gateway_source');assert status(y)=='UNVERIFIED'
        assert status({**x,'sn_endpoint_role':'GATEWAY','sn_direction':'GATEWAY_TO_CLIENT'})=='INVALID'
    if topic!='SHORT':
        for patch in ({'sn_topic_id':0},{'sn_topic_id':65535},{'sn_mapping_known':False},
            {'sn_mapping_client_ref':'other-client'},{'sn_mapping_gateway_ref':'other-gateway'}):
            assert status({**x,**patch})=='INVALID'
    else:
        for text in ('a','abc','🌡','+#'):
            assert status({**x,'sn_short_topic':text,'sn_short_topic_bytes':len(text.encode())})=='INVALID'

@pytest.mark.parametrize('length_bytes,body',[(1,0),(1,248),(3,0),(3,246),(3,65526)])
def test_mqtt_sn_short_or_extended_header_includes_itself_and_supports_extended_small_frames(length_bytes,body):
    x=publish(body=body,length_bytes=length_bytes);assert status(x)=='VALID'
    # Extended form may encode small messages; forcing minimal encoding would reject legal1.2 input.
    if length_bytes==3:assert x['sn_packet_bytes']==9+body
    else:assert x['sn_packet_bytes']==7+body
    y={**x,'payload_bytes':body+1,'sn_variable_bytes':6+body,'sn_packet_bytes':x['sn_packet_bytes']+1,'sn_length_value':x['sn_length_value']+1}
    if body in(248,65526):assert status(y)=='INVALID'
    assert status({**x,'sn_network_packet_max':x['sn_packet_bytes']-1})=='INVALID'

@pytest.mark.parametrize('length_bytes',[1,3])
def test_mqtt_sn_actual_encoded_header_length_type_and_publish_flags(length_bytes):
    x=publish(body=2,length_bytes=length_bytes)
    prefix=bytes([x['sn_length_value']])if length_bytes==1 else b'\x01'+x['sn_length_value'].to_bytes(2,'big')
    packet=prefix+bytes([12,x['sn_flags']])+b'\x00\x0c\x00\x09AB'
    x['sn_packet_hex']=packet.hex();assert status(x)=='VALID'
    for position in (0,length_bytes,length_bytes+1):
        altered=bytearray(packet);altered[position]^=1
        assert status({**x,'sn_packet_hex':altered.hex()})=='INVALID'

def test_mqtt_sn_legacy_zigbee_60octets_is_binding_specific_not_every_radio_or_modern_aps():
    x={**publish(body=53),'sn_transport':'ZIGBEE_APS','sn_binding_profile':'IBM_2013_ZIGBEE_APS','sn_network_packet_max':60}
    assert x['sn_packet_bytes']==60;assert status(x)=='VALID'
    assert status({**x,'sn_network_packet_max':128})=='INVALID'
    x.update(sn_binding_profile='REGISTERED',sn_network_packet_max=128);assert status(x)=='VALID'
    assert status({**x,'sn_bidirectional_datagram':False})=='INVALID'
    y=actual();y.pop('sn_port');assert status(y)=='UNVERIFIED'

@pytest.mark.parametrize('will',[False,True])
@pytest.mark.parametrize('clean',[False,True])
def test_mqtt_sn_connect_native_protocol_flags_utf8_character_count_and_separate_will_exchange(will,clean):
    x=actual();name='é'*23
    x.update(sn_client_id=name,sn_client_id_bytes=46,sn_client_characters=23,sn_will=will,sn_clean_session=clean,
        sn_flags=8*will+4*clean,sn_variable_bytes=50,sn_packet_bytes=52,sn_length_value=52)
    assert status(x)=='VALID'
    for patch in ({'sn_protocol_id':4},{'sn_flags':16},{'sn_client_characters':24},{'sn_client_characters':22},{'sn_client_id_bytes':23},
        {'sn_client_id':'','sn_client_id_bytes':0,'sn_client_characters':0}):assert status({**x,**patch})=='INVALID'

@pytest.mark.parametrize('kind',['WILLTOPIC','WILLTOPICUPD'])
def test_mqtt_sn_empty_will_deletes_both_stored_fields_header_only_and_nonempty_has_native_flags(kind):
    x=actual(kind,0);x.pop('sn_flags');x.update(sn_will_delete=True);assert status(x)=='VALID'
    assert status({**x,'sn_flags':0})=='INVALID'
    assert status({**x,'sn_length_bytes':3,'sn_packet_bytes':4,'sn_length_value':4})=='INVALID'
    x.update(sn_will_delete=False,sn_will_topic='ventil',sn_will_topic_bytes=6,sn_qos=2,sn_retain=True,
        sn_flags=80,sn_variable_bytes=7,sn_length_value=9,sn_packet_bytes=9)
    assert status(x)=='VALID';assert status({**x,'sn_flags':96})=='INVALID'

@pytest.mark.parametrize('kind',['REGACK','PUBACK','PUBREC','PUBREL','PUBCOMP','SUBACK','UNSUBACK'])
def test_mqtt_sn_acknowledgements_match_client_gateway_transaction_and_topic_when_applicable(kind):
    sizes={'REGACK':5,'PUBACK':5,'PUBREC':2,'PUBREL':2,'PUBCOMP':2,'SUBACK':6,'UNSUBACK':2}
    x=response(kind,sizes[kind]);x.update(sn_topic_id=12,sn_request_topic_id=12)
    if kind=='SUBACK':x.update(sn_flags=32,sn_qos=1,sn_wildcard_subscription=False)
    assert status(x)=='VALID'
    for patch in ({'sn_msg_id':10},{'sn_pending_match':False},{'sn_request_client_ref':'other-client'},
        {'sn_request_gateway_ref':'other-gateway'}):assert status({**x,**patch})=='INVALID'
    if kind=='PUBACK':assert status({**x,'sn_topic_id':13})=='INVALID'
    if kind=='SUBACK':
        assert status({**x,'sn_wildcard_subscription':True})=='INVALID'
        assert status({**x,'sn_wildcard_subscription':True,'sn_topic_id':0})=='VALID'

def test_mqtt_sn_register_client_zero_id_gateway_assigned_and_accepted_id_not_reserved():
    x=actual('REGISTER',5);x.update(sn_msg_id=10,sn_topic_id=0,sn_topic_name='A',sn_topic_name_bytes=1)
    assert status(x)=='VALID'
    assert status({**x,'sn_topic_id':12})=='INVALID'
    x.update(sn_endpoint_role='GATEWAY',sn_direction='GATEWAY_TO_CLIENT',sn_topic_id=65534);assert status(x)=='VALID'
    assert status({**x,'sn_topic_id':65535})=='INVALID'
    for key in ('sn_register_outstanding','sn_publish_outstanding','sn_subscription_outstanding','sn_connected_gateways'):
        assert status({**actual(),key:1})=='VALID';assert status({**actual(),key:2})=='INVALID'

@pytest.mark.parametrize('kind',['SUBSCRIBE','UNSUBSCRIBE'])
@pytest.mark.parametrize('topic',['NORMAL','PREDEFINED','SHORT'])
def test_mqtt_sn_subscription_forms_have_one_native_topic_and_identifier(kind,topic):
    x=actual(kind,6 if topic=='NORMAL'else 5);type_={'NORMAL':0,'PREDEFINED':1,'SHORT':2}[topic]
    x.update(sn_msg_id=9,sn_topic_kind=topic,sn_topic_type=type_,sn_flags=(32 if kind=='SUBSCRIBE'else 0)+type_,sn_qos=1,sn_dup=False)
    if topic=='NORMAL':x.update(sn_topic_filter='a/#',sn_topic_filter_bytes=3)
    elif topic=='PREDEFINED':x.update(sn_topic_id=12)
    else:x.update(sn_short_topic='é',sn_short_topic_bytes=2)
    assert status(x)=='VALID';assert status({**x,'sn_flags':255})=='INVALID'
    if topic=='NORMAL':assert status({**x,'sn_topic_filter':'a#','sn_topic_filter_bytes':2})=='INVALID'

def test_mqtt_sn_discovery_requires_actual_broadcast_gateway_advertisement_and_client_gwinfo_address():
    x=actual('SEARCHGW',1);x.update(sn_direction='CLIENT_BROADCAST',sn_discovery='BROADCAST',sn_broadcast_supported=True,sn_radius=0)
    assert status(x)=='VALID';assert status({**x,'sn_broadcast_supported':False})=='INVALID'
    x=actual('ADVERTISE',3);x.update(sn_endpoint_role='GATEWAY',sn_direction='GATEWAY_BROADCAST',
        sn_broadcast_supported=True,sn_gateway_server_connected=True,sn_gateway_id=1,sn_advertise_s=1800)
    assert status(x)=='VALID';assert status({**x,'sn_gateway_server_connected':False})=='INVALID'
    x=actual('GWINFO',1);x.update(sn_endpoint_role='GATEWAY',sn_direction='GATEWAY_BROADCAST',sn_broadcast_supported=True,
        sn_gateway_id=1,sn_gwinfo_address_present=False);assert status(x)=='VALID'
    x.update(sn_endpoint_role='CLIENT',sn_direction='CLIENT_BROADCAST');assert status(x)=='INVALID'
    x.update(sn_gwinfo_address_present=True,sn_gateway_address='synthetic-node-address',sn_gateway_address_bytes=3,
        sn_variable_bytes=4,sn_packet_bytes=6,sn_length_value=6);assert status(x)=='VALID'

def test_mqtt_sn_sleep_duration_and_awake_ping_id_do_not_use_generic_mqtt_keepalive_rule():
    x=actual('DISCONNECT',2);x.update(sn_duration_present=True,sn_sleep_s=65535,
        sn_client_state='ASLEEP',sn_watchdog_duration_s=65535,sn_watchdog_bound_s=72088.5,
        sn_timer_profile='IBM_1_2_RECOMMENDED',sn_timer_source='synthetic-actual-timer-policy')
    assert status(x)=='VALID';assert status({**x,'sn_watchdog_bound_s':98302.5})=='INVALID'
    x=actual('PINGREQ',1);x.update(sn_client_state='AWAKE',sn_client_id_present=True);assert status(x)=='VALID'
    assert status({**x,'sn_client_id_present':False,'sn_variable_bytes':0,'sn_packet_bytes':2,'sn_length_value':2})=='INVALID'
    x=actual('DISCONNECT',0);x.update(sn_duration_present=False);assert status(x)=='VALID'
    assert status({**x,'sn_sleep_s':30})=='INVALID'

@pytest.mark.parametrize('duration,bound',[(30,45),(59,88.5),(61,67.1),(120,132)])
def test_mqtt_sn_literature_timer_tolerance_is_duration_scoped_and_exact_60_is_not_invented(duration,bound):
    x={**actual(),'sn_timer_profile':'IBM_1_2_RECOMMENDED','sn_client_state':'ACTIVE','sn_keepalive_s':duration,
        'sn_watchdog_duration_s':duration,'sn_watchdog_bound_s':bound,'sn_timer_source':'synthetic-device-policy'}
    assert status(x)=='VALID';assert status({**x,'sn_watchdog_bound_s':bound+1})=='INVALID'
    x.update(sn_keepalive_s=60,sn_watchdog_duration_s=60,sn_watchdog_bound_s=70);assert status(x)=='VALID'
    assert status({**x,'sn_watchdog_bound_s':59})=='INVALID'

def test_mqtt_sn_recommended_ranges_proposals_are_not_actual_addresses_or_capacity():
    fields={v['key']:v for v in registry.parameter_fields('mqtt_sn')}
    for key,value in [('sn_retry_s',10),('sn_retry_limit',3),('sn_search_delay_s',5),('sn_advertise_misses',2)]:
        proposal=fields[key]['conditional_defaults'][0]
        assert proposal['when']=={'sn_timer_profile':'IBM_1_2_RECOMMENDED'}
        assert proposal['value']==value;assert proposal['source']==SN.P
    assert not fields['sn_advertise_s'].get('conditional_defaults');assert not fields['sn_wait_s'].get('conditional_defaults')
    x={**actual(),'sn_timer_profile':'IBM_1_2_RECOMMENDED','sn_retry_s':15,'sn_retry_limit':5,
        'sn_wait_s':300.1,'sn_advertise_s':901,'sn_advertise_misses':3}
    assert status(x)=='VALID'
    for patch in ({'sn_wait_s':300},{'sn_advertise_s':900},{'sn_retry_s':9},{'sn_retry_limit':2},
        {'sn_advertise_misses':4},{'sn_retry_attempt':6}):assert status({**x,**patch})=='INVALID'
    x.update(sn_timer_profile='REGISTERED',sn_timer_source='synthetic-custom-policy',sn_retry_s=9);assert status(x)=='VALID'

def test_mqtt_sn_gateway_transparent_and_aggregating_backend_resources_do_not_become_capacity_proof():
    x={**actual(),'sn_gateway_kind':'TRANSPARENT','sn_active_clients':10,'sn_backend_connections':10,
        'sn_gateway_backend_source':'synthetic-actual-broker-mapping'}
    assert status(x)=='VALID';assert status({**x,'sn_backend_connections':1})=='INVALID'
    assert status({**x,'sn_qos_minus1_supported':True})=='INVALID'
    assert status({**x,'sn_qos_minus1_supported':True,'sn_backend_connections':11})=='VALID'
    x.update(sn_gateway_kind='AGGREGATING',sn_backend_connections=1);assert status(x)=='VALID'
    assert status({**x,'sn_backend_connections':0})=='INVALID'

def test_mqtt_sn_forwarder_prefix_length_excludes_inner_message_and_radius_has_only_two_bits():
    x=actual('ENCAPSULATED',7);x.update(sn_endpoint_role='FORWARDER',sn_direction='FORWARDER_TO_GATEWAY',
        sn_length_value=5,sn_packet_bytes=9,sn_variable_bytes=7,sn_wireless_node_id_bytes=2,
        sn_wireless_node_id_hex='1234',sn_inner_packet_bytes=4,sn_inner_msg_type=SN.KINDS['PINGRESP'],
        sn_forward_ctrl=0,sn_forward_radius=0,sn_packet_hex='05fe00123401000417')
    assert status(x)=='VALID'
    for patch in ({'sn_length_value':9},{'sn_packet_bytes':5},{'sn_forward_ctrl':4},
        {'sn_forward_radius':255},{'sn_inner_msg_type':254},{'sn_wireless_node_id_hex':'12'}):
        assert status({**x,**patch})=='INVALID'

def test_mqtt_sn_missing_actual_evidence_stays_unverified_and_literature_does_not_fill_it():
    for key in SN.REQUIRED:
        x=actual();x.pop('sn_'+key);assert status(x)!='VALID'
    x=publish();x.pop('sn_mapping_source');assert status(x)=='UNVERIFIED'
    assert registry.profile('mqtt_sn')['capacity_evidence']['status']=='MODEL_MISSING'

def test_mqtt_sn_confirmed_high_gateway_id_unicode_client_zero_publish_id_and_timer_survive_rejected_foreign_defaults():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x=publish(qos=-1,topic='SHORT');x.update(sn_gateway_id=255,sn_client_id='é',sn_client_id_bytes=2,sn_client_characters=1,
        sn_timer_profile='REGISTERED',sn_timer_source='synthetic-timer-policy',sn_retry_s=22)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'mqtt_sn','technology_parameters':{'mqtt_sn':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['mqtt_sn']['values']['bitrate']=250000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
