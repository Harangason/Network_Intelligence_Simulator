"""PubSub transport/keyframe/metadata/sequence isolation, not hardware evidence."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.opc_ua_pubsub import rules as P
def actual(binding='UDP',encoding='UADP',role='PUBLISHER'):
 x={'ps_'+k:'synthetic-'+k for k in P.REQUIRED}
 x.update(ps_edition=P.EDITION,ps_binding=binding,ps_encoding=encoding,ps_role=role,
  ps_publisher_type='UINT64',ps_publisher_id='18446744073709551615')
 if binding in('UDP','DTLS'):
  x.update(ps_address='opc.udp://239.0.0.1:4840'if binding=='UDP'else'opc.dtls://server.invalid:4843',
   ps_port=4840 if binding=='UDP' else 4843,ps_ip_version='IPv4',ps_network_mode='MULTICAST'if binding=='UDP'else'UNICAST')
  if binding=='DTLS':x['ps_dtls_version']=1.3
 elif binding=='ETHERNET':x.update(ps_address='opc.eth://01-23-45-67-89-ab',ps_ether_type=0xB62C)
 elif binding=='MQTT':x.update(ps_address='mqtts://broker.invalid',ps_mqtt_actual_version='5.0')
 if role=='SUBSCRIBER':x.update(ps_publisher_filter=x['ps_publisher_id'],ps_membership_reported=True)
 return x
def status(x):return registry.validate_parameters('opc_ua_pubsub',x)['status']

def test_pubsub_is_industry_neutral_not_always_udp_eth_or_physical_can():
 p=registry.profile('opc_ua_pubsub');assert p['default_stack']==['opc_ua_pubsub'];assert p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING';assert status(actual())=='VALID'
 keys=[f['key']for f in registry.parameter_fields('opc_ua_pubsub')];assert len(keys)==len(set(keys));assert not set(keys)&set(P.REMOVED)
 for bad in({'bitrate_bps':10000000},{'mtu_bytes':1500},{'local_timing_evidence':{}},{'ua_hello_rx':8192}):assert status({**actual(),**bad})=='INVALID'
 assert status({**actual('MQTT'),'payload_bytes':70000})=='VALID'

@pytest.mark.parametrize('field',registry.parameter_fields('opc_ua_pubsub'),ids=lambda f:f['key'])
def test_pubsub_every_declared_field_type_unit_and_bounds(field):
 bad='not-number'if field['type']=='number' else 1
 assert status({**actual(),field['key']:bad})=='INVALID'
 for edge,offset in(('min',-1),('max',1)):
  if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

def test_pubsub_standard_proposals_are_conditional_no_invented_actual_identity_schedule():
 f={v['key']:v for v in registry.parameter_fields('opc_ua_pubsub')}
 assert f['ps_edition']['default']==P.EDITION
 assert {(d['when']['ps_binding'],d['value'])for d in f['ps_port']['conditional_defaults']}=={('UDP',4840),('DTLS',4843)}
 assert f['ps_discovery_max_bytes']['conditional_defaults'][0]['value']==4096
 assert f['ps_mqtt_version']['conditional_defaults'][0]['value']=='BestAvailable'
 assert f['ps_topic_prefix']['conditional_defaults'][0]['value']=='opcua'
 for k in('ps_address','ps_publisher_id','ps_publish_ms','ps_receive_timeout_ms','ps_path_mtu','ps_max_network_bytes','payload_bytes'):
  assert 'default'not in f[k];assert not f[k].get('conditional_defaults')

def test_pubsub_uint64_publisher_identity_is_exact_text_not_js_float():
 assert status(actual())=='VALID'
 for value in('18446744073709551616','00018446744073709551616','0','-1','1e3',float(2**64-1)):
  assert status({**actual(),'ps_publisher_id':value})=='INVALID'
 assert status({**actual(),'ps_publisher_id':'00018446744073709551615'})=='VALID'
 assert status({**actual('MQTT','JSON'),'ps_publisher_type':'STRING','ps_publisher_id':'device-one'})=='VALID'

@pytest.mark.parametrize('kind,width',[('UINT8',8),('UINT16',16),('UINT32',32),('UINT64',64)])
def test_pubsub_each_unsigned_publisher_identity_width_is_source_qualified(kind,width):
 x={**actual(),'ps_publisher_type':kind,'ps_publisher_id':str(2**width-1)};assert status(x)=='VALID'
 assert status({**x,'ps_publisher_id':str(2**width)})=='INVALID'
 assert status({**x,'ps_publisher_id':'0'})=='INVALID'

def test_pubsub_cyclic_event_heartbeat_keyframe_and_keepalive_are_not_cs_subscription():
 x={**actual(),'ps_dataset_kind':'CYCLIC','ps_keyframe_count':1,'ps_publish_ms':10,'ps_keepalive_ms':10};assert status(x)=='VALID'
 for bad in({'ps_keyframe_count':0},{'ps_publish_ms':0},{'ps_keepalive_ms':9.999}):assert status({**x,**bad})=='INVALID'
 x.update(ps_dataset_kind='ACYCLIC',ps_keyframe_count=0,ps_publish_ms=0);assert status(x)=='VALID'
 assert status({**x,'ps_keepalive_ms':0})=='INVALID'
 x.update(ps_dataset_kind='HEARTBEAT',ps_keyframe_count=1,ps_publish_ms=10,ps_version_major=0,ps_version_minor=0);assert status(x)=='VALID'
 assert status({**x,'ps_version_major':1})=='INVALID'

def test_pubsub_writer_group_assignment_ranges_are_not_arbitrary_can_identifiers():
 x={**actual(),'ps_assignment':'EXTERNAL','ps_writer_group_id':32767};assert status(x)=='VALID'
 assert status({**x,'ps_writer_group_id':32768})=='INVALID'
 assert status({**x,'ps_assignment':'INTERNAL','ps_writer_group_id':32768})=='VALID'
 assert status({**x,'ps_writer_group_id':0})=='INVALID'
 assert status({**x,'ps_dataset_assignment':'INTERNAL','ps_dataset_writer_id':32768})=='VALID'
 assert status({**x,'ps_dataset_assignment':'EXTERNAL','ps_dataset_writer_id':32768})=='INVALID'

def test_pubsub_offsets_are_ordered_duration_arrays_and_repeats_are_datagram_specific():
 x={**actual(),'ps_uadp_version':1,'ps_sampling_offset_ms':-1,'ps_receive_offset_ms':2.5,'ps_processing_offset_ms':3,
  'ps_publish_offsets_ms_json':'[1.5, 2.75]','ps_publish_offsets_count':2,'ps_repeat_count':0,'ps_discovery_announce_s':0};assert status(x)=='VALID'
 for value in('[true]','["1.5"]','{"0":1.5}','[NaN]','[Infinity]','[1e400]','[1e-1000]','[1,]'):
  assert status({**x,'ps_publish_offsets_ms_json':value})=='INVALID'
 assert status({**x,'ps_publish_offsets_count':1})=='INVALID';assert status({**x,'ps_uadp_version':2})=='INVALID'
 assert status({**x,'ps_publish_offsets_ms_json':'[-1]','ps_publish_offsets_count':1})=='VALID'
 assert status({**x,'ps_publish_offsets_ms_json':'[]','ps_publish_offsets_count':0})=='VALID'
 assert status({**actual('MQTT','JSON'),'ps_uadp_version':1})=='INVALID'

def test_pubsub_udp_ip_budget_excludes_mac_while_direct_eth_includes_it():
 assert status({**actual(),'ps_network_bytes':70000,'ps_max_network_bytes':70000})=='INVALID'
 x={**actual(),'ps_no_ip_fragmentation':True,'ps_budget_layer':'IP_PACKET','ps_path_mtu':1500,
  'ps_network_bytes':1472,'ps_max_network_bytes':1472,'ps_ip_header_bytes':20,'ps_transport_overhead_bytes':0,
  'ps_ip_packet_bytes':1500,'ps_headers_bytes':50,'ps_wire_bytes':1522};assert status(x)=='VALID'
 assert status({**x,'ps_ip_packet_bytes':1522})=='INVALID'
 assert status({**x,'ps_budget_layer':'COMPLETE_LINK_FRAME'})=='INVALID'
 assert status({**x,'ps_ip_version':'IPv6','ps_ip_header_bytes':40})=='INVALID'
 x.update(ps_ip_version='IPv6',ps_ip_header_bytes=40,ps_network_bytes=1452,ps_max_network_bytes=1452,ps_headers_bytes=70);assert status(x)=='VALID'
 x=actual('ETHERNET');x.update(ps_network_bytes=1500,ps_max_network_bytes=1500,ps_headers_bytes=22,ps_wire_bytes=1522,ps_budget_layer='COMPLETE_LINK_FRAME');assert status(x)=='VALID'
 assert status({**x,'ps_wire_bytes':1523})=='INVALID';assert status({**x,'ps_port':4840})=='INVALID'
 assert status({**x,'ps_ether_type':0x0800})=='INVALID'

def test_pubsub_dtls_is_unicast13_and_actual_record_overhead_not_plain_udp():
 x=actual('DTLS');x.update(ps_network_bytes=100,ps_max_network_bytes=100,ps_ip_header_bytes=20,ps_transport_overhead_bytes=30,ps_ip_packet_bytes=158)
 assert status(x)=='VALID';assert status({**x,'ps_ip_packet_bytes':128})=='INVALID'
 assert status({**x,'ps_dtls_version':1.2})=='INVALID';assert status({**x,'ps_network_mode':'MULTICAST'})=='INVALID'
 x.pop('ps_transport_overhead_bytes');assert status(x)=='UNVERIFIED'

def test_pubsub_multicast_interface_membership_and_unicast_send_address_are_role_specific():
 x=actual(role='SUBSCRIBER');assert status(x)=='VALID'
 assert status({**x,'ps_publisher_filter':'another'})=='INVALID';assert status({**x,'ps_membership_reported':False})=='INVALID'
 x['ps_interface_count']=2;assert status(x)=='UNVERIFIED';x['ps_interface']='actual-interface';assert status(x)=='VALID'
 assert status({**x,'ps_writer_address':'opc.udp://239.0.0.1'})=='INVALID'
 x=actual();x['ps_network_mode']='UNICAST';assert status(x)=='UNVERIFIED'
 x['ps_writer_address']='opc.udp://subscriber.invalid:4840';assert status(x)=='VALID'

def test_pubsub_mqtt_delivery_content_retain_and_keepalive_are_actual_mapping():
 x={**actual('MQTT','JSON'),'ps_mqtt_version':'BestAvailable','ps_delivery':'ExactlyOnce','ps_mqtt_qos':2,
  'ps_topic':'opcua/json/data/device/group','ps_topic_kind':'data','ps_retain':False,'ps_content_type':'application/json',
  'ps_network_bytes':70000,'ps_max_network_bytes':70000,'ps_mqtt_packet_bytes':70100,'ps_broker_packet_limit':70100,
  'ps_max_group_keepalive_ms':10000,'ps_mqtt_keepalive_s':11};assert status(x)=='VALID'
 for bad in({'ps_mqtt_qos':1},{'ps_content_type':'application/opcua+uadp'},{'ps_broker_packet_limit':70099},
  {'ps_topic':'opcua/json/data/+/group'},{'ps_mqtt_keepalive_s':10},{'ps_mqtt_version':'3.1.1'}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ps_retain':True})=='UNVERIFIED';assert status({**x,'ps_retain':True,'ps_data_retain_override':True})=='VALID'
 assert status({**x,'ps_topic_kind':'metadata','ps_retain':False})=='INVALID'
 assert status({**x,'ps_topic_kind':'metadata','ps_retain':True})=='VALID'

@pytest.mark.parametrize('width,encoding',[(16,'UADP'),(32,'JSON')])
def test_pubsub_sender_sequence_wrap_and_receiver_modular_thresholds(width,encoding):
 x={**actual('MQTT',encoding),'ps_sequence_width':width,'ps_sequence_phase':'NEXT','ps_previous_sequence':2**width-1,'ps_sequence':0}
 assert status(x)=='VALID';assert status({**x,'ps_sequence':1})=='INVALID'
 x.update(ps_sequence_phase='RECEIVE',ps_previous_sequence=0,ps_sequence=1,ps_sequence_distance=0,ps_sequence_result='NEW');assert status(x)=='VALID'
 lo=2**(width-2);hi=2**width-lo
 for distance,result in[(lo-1,'NEW'),(lo,'INVALID'),(hi,'INVALID'),(hi+1,'OLD'),(2**width-1,'OLD')]:
  a={**x,'ps_sequence':(distance+1)%(2**width),'ps_sequence_distance':distance,'ps_sequence_result':result};assert status(a)=='VALID'
  assert status({**a,'ps_sequence_result':'OLD'if result!='OLD'else'NEW'})=='INVALID'
 assert status({**x,'ps_sequence':2**width})=='INVALID'
 x.pop('ps_previous_sequence');assert status(x)=='UNVERIFIED'

def test_pubsub_actual_flags_padding_metadata_and_functional_acceptance():
 x={**actual(),'ps_flags1_hex':'0B','ps_dataset_valid':True,'ps_field_encoding':1,'ps_sequence_present':True,
  'ps_configured_dataset_bytes':32,'ps_dataset_bytes':24,'ps_dataset_padded_bytes':32};assert status(x)=='VALID'
 for bad in({'ps_flags1_hex':'0F'},{'ps_field_encoding':2},{'ps_dataset_padded_bytes':24},{'ps_dataset_bytes':33}):assert status({**x,**bad})=='INVALID'
 x.update(ps_flags1_hex='0A',ps_dataset_valid=False,ps_dataset_bytes=33);assert status(x)=='VALID'
 assert status({**x,'ps_data_accepted':True,'ps_metadata_matches':True,'ps_outcome':'ACCEPTED'})=='INVALID'
 x={**actual(),'ps_data_accepted':True,'ps_metadata_matches':True,'ps_dataset_valid':True,'ps_outcome':'ACCEPTED','ps_age_ms':10,'ps_freshness_limit_ms':10};assert status(x)=='VALID'
 assert status({**x,'ps_metadata_matches':False})=='INVALID';assert status({**x,'ps_age_ms':10.001})=='INVALID'

def test_pubsub_foreign_can_rate_does_not_reset_confirmed_native_parameters():
 x={**actual(),'ps_publish_ms':42,'ps_keyframe_count':3,'ps_receive_timeout_ms':150,'payload_bytes':300};before=deepcopy(x)
 assert status({**x,'bitrate_bps':500000})=='INVALID';assert x==before;assert status(x)=='VALID'
