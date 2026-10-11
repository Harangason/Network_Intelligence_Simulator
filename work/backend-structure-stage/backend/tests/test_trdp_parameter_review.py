"""TCNOpen edition-scoped PD/MD headers, codec and actual transport evidence."""
import struct,zlib
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.trdp import rules as R
from backend.nis.communication.core.components import TechnologyValidator
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual(mode='PD'):
 x={'tr_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(tr_review_profile='TCNOPEN_3_0_0',tr_mode=mode,tr_transport='UDP')
 return x
def status(x):return registry.validate_parameters('trdp',x)['status']
def test_trdp_own_stack_not_ethernet_or_udp_cap():
 p=registry.profile('trdp');assert p['domain']=='generic_networking'and p['default_stack']==['trdp']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':100000000},{'mtu_bytes':1500},{'retry_limit':2},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('trdp',1432,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('trdp'),ids=lambda f:f['key'])
def test_every_trdp_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('mode,header,maximum',[('PD',40,1432),('MD',116,65388)])
@pytest.mark.parametrize('length',[0,1,3,4,100])
def test_pd_md_dataset_packet_padding_and_own_limits(mode,header,maximum,length):
 pad=(-length)%4;x={**actual(mode),'tr_header_bytes':header,'tr_data_bytes':length,'tr_padding_bytes':pad,'tr_packet_bytes':header+length+pad}
 assert status(x)=='VALID'
 for bad in({'tr_header_bytes':116 if mode=='PD'else 40},{'tr_padding_bytes':(pad+1)%4},{'tr_packet_bytes':header+length+pad+1},{'tr_data_bytes':maximum+1}):assert status({**x,**bad})=='INVALID'
def test_md_tcp_separate_pd_udp_and_native_kinds():
 assert status({**actual('MD'),'tr_transport':'TCP','tr_message_type':'Mr'})=='VALID'
 for bad in({'tr_transport':'TCP'},{'tr_message_type':'Mr'}):assert status({**actual(),**bad})=='INVALID'
 assert status({**actual('MD'),'tr_message_type':'Pd'})=='INVALID'
def test_minor_version_receive_compatibility_and_soa_send():
 assert status({**actual(),'tr_phase':'RECEIVE','tr_protocol_version':0x101})=='VALID'
 assert status({**actual(),'tr_phase':'RECEIVE','tr_protocol_version':0x1ff})=='VALID'
 assert status({**actual(),'tr_phase':'RECEIVE','tr_protocol_version':0x200})=='INVALID'
 assert status({**actual(),'tr_phase':'SEND','tr_variant':'BASE','tr_protocol_version':0x101})=='INVALID'
 assert status({**actual(),'tr_phase':'SEND','tr_variant':'SOA','tr_protocol_version':0x101})=='VALID'
def header(mode='PD',length=3):
 kind='Pd'if mode=='PD'else'Mr';code=R.TYPE_CODES[kind]
 common=struct.pack('!IHHIIII',0xffffffff,0x100,code,1001,0,5,length)
 raw=common+(struct.pack('!III',0,1002,0xc0000201)if mode=='PD'else struct.pack('!i',-2)+bytes.fromhex('01'*16)+struct.pack('!I',0)+b'source'.ljust(32,b'\x00')+b'destination'.ljust(32,b'\x00'))
 crc=zlib.crc32(raw);raw+=struct.pack('<I',crc)
 x={**actual(mode),'tr_message_type':kind,'tr_message_code':code,'tr_header_hex':raw.hex(),'tr_header_bytes':len(raw),'tr_sequence':0xffffffff,'tr_protocol_version':0x100,'tr_com_id':1001,'tr_etb_topology':0,'tr_operational_topology':5,'tr_data_bytes':length,'tr_header_crc':crc}
 x.update({'tr_reserved':0,'tr_reply_com_id':1002,'tr_reply_ip_raw':0xc0000201}if mode=='PD'else{'tr_reply_status':-2,'tr_reply_timeout_us':0})
 return x,raw
@pytest.mark.parametrize('mode',['PD','MD'])
def test_real_header_big_endian_fields_but_little_endian_crc(mode):
 x,raw=header(mode);assert status(x)=='VALID'
 for bad in({'tr_header_hex':raw[:-1].hex()},{'tr_header_hex':(raw[:8]+b'\xff'+raw[9:]).hex()},{'tr_header_hex':(raw[:-4]+raw[-4:][::-1]).hex()},{'tr_header_crc':x['tr_header_crc']^1},{'tr_com_id':1002}):assert status({**x,**bad})=='INVALID'
 y=dict(x);y.pop('tr_header_crc');assert status(y)=='UNVERIFIED'
def test_md_status_signed_negative_not_unsigned_wire():
 x,_=header('MD');assert status(x)=='VALID'
 assert status({**x,'tr_reply_status':4294967294})=='INVALID'
 assert status({**x,'tr_reply_status':2})=='INVALID'
def test_ieee_crc_known_independent_check_vector_and_missing_prefix():
 v=TechnologyValidator('test',{'parameter_constraints':[dict(parameter='wire',when={},hex_crc32_ieee_parameter='fcs')]})
 assert not v.validate({'parameters':{'wire':b'123456789'.hex(),'fcs':0xcbf43926}})
 assert v.validate({'parameters':{'wire':b'123456789'.hex(),'fcs':0xcbf43927}})
 v=TechnologyValidator('test',{'parameter_constraints':[dict(parameter='wire',when={},hex_crc32_ieee_parameter='fcs',hex_crc32_prefix_bytes=36)]})
 assert v.validate({'parameters':{'wire':'00','fcs':0}})
def test_sequence_wrap_zero_not_universal_forbidden_reset():
 assert status({**actual(),'tr_sequence':4294967295,'tr_next_sequence':0})=='VALID'
 assert status({**actual(),'tr_sequence':4294967295,'tr_next_sequence':1})=='INVALID'
def test_qos_platform_mapping_and_inherit_ttl_are_not_fixed_defaults():
 x={**actual(),'tr_socket_profile':'POSIX_DSCP','tr_socket_source':'synthetic','tr_qos':5,'tr_ds_field':160,'tr_ttl':0};assert status(x)=='VALID'
 assert status({**x,'tr_qos':8})=='INVALID';assert status({**x,'tr_ds_field':5})=='INVALID'
 assert status({**x,'tr_socket_profile':'REGISTERED_ACTUAL','tr_qos':8})=='VALID'
def test_worker_cadence_not_dataset_cycle_minimum():
 assert status({**actual(),'tr_library_process_cycle_us':10000,'tr_publish_cycle_us':1000})=='VALID'
 assert status({**actual(),'tr_publish_cycle_us':0})=='VALID'
 assert status({**actual(),'tr_tsn_build':True,'tr_timer_granularity_us':5000})=='INVALID'
 assert status({**actual(),'tr_tsn_build':True,'tr_timer_granularity_us':500})=='VALID'
 assert status({**actual(),'tr_tsn_build':False,'tr_indexed_build':False,'tr_timer_granularity_us':500})=='INVALID'
def test_tsn_flag_not_schedule_or_different_invented_header():
 x={**actual(),'tr_message_type':'Pt','tr_header_bytes':40,'tr_tsn_build':True};assert status(x)=='UNVERIFIED'
 assert status({**x,'tr_tsn_source':'synthetic'})=='VALID'
 assert status({**x,'tr_tsn_source':'synthetic','tr_header_bytes':32})=='INVALID'
@pytest.mark.parametrize('transport,multicast,configured,effective',[('UDP',False,1,2),('UDP',False,0,0),('UDP',True,1,0),('TCP',False,1,0)])
def test_md_retries_only_scoped_udp_unicast_input_one(transport,multicast,configured,effective):
 x={**actual('MD'),'tr_transport':transport,'tr_multicast':multicast,'tr_configured_expected_replies':configured,'tr_retries':2,'tr_effective_retries':effective};assert status(x)=='VALID'
 assert status({**x,'tr_effective_retries':3})=='INVALID'
def test_md_unicast_one_and_unknown_multicast_count_not_zero_completion():
 assert status({**actual('MD'),'tr_message_type':'Mr','tr_multicast':False,'tr_expected_replies':0})=='INVALID'
 assert status({**actual('MD'),'tr_message_type':'Mr','tr_multicast':True,'tr_expected_replies':0})=='VALID'
 assert status({**actual('MD'),'tr_expected_replies':2,'tr_replies_received':1,'tr_replies_complete':True})=='INVALID'
def test_infinite_api_sentinel_and_wire_zero_are_separate():
 x={**actual('MD'),'tr_message_type':'Mr','tr_api_reply_timeout_us':0xffffffff,'tr_reply_timeout_us':0};assert status(x)=='VALID'
 assert status({**x,'tr_reply_timeout_us':0xffffffff})=='INVALID'
 assert status({**x,'tr_api_reply_timeout_us':5000000,'tr_reply_timeout_us':5000000})=='VALID'
def test_topology_filter_zero_not_every_actual_zero_wildcard():
 x={**actual(),'tr_etb_topology':0,'tr_etb_filter':0,'tr_topology_verified':True};assert status(x)=='VALID'
 assert status({**x,'tr_etb_filter':1})=='INVALID'
def test_dataset_definition_variable_and_custom_registry():
 x={**actual(),'tr_dataset_id':1001,'tr_custom_dataset':True,'tr_dataset_reserved':0,'tr_element_type':9,'tr_element_size':0,'tr_element_count':4,'tr_variable_count_source':'synthetic-count','tr_element_width_bytes':2,'tr_element_bytes':8};assert status(x)=='VALID'
 for bad in({'tr_dataset_id':1000},{'tr_dataset_reserved':1},{'tr_element_width_bytes':4},{'tr_element_bytes':4},{'tr_element_type':20}):assert status({**x,**bad})=='INVALID'
 y=dict(x);y.pop('tr_variable_count_source');assert status(y)=='UNVERIFIED'
 assert status({**actual(),'tr_element_type':31})=='UNVERIFIED'
@pytest.mark.parametrize('t,n',R.TYPE_WIDTHS.items())
def test_actual_scalar_width_not_c_alignment(t,n):
 x={**actual(),'tr_element_type':t,'tr_element_width_bytes':n,'tr_element_count':3,'tr_element_bytes':3*n};assert status(x)=='VALID'
 assert status({**x,'tr_element_width_bytes':n+1})=='INVALID'
def test_scaling_and_lossless64bit_encoding():
 x={**actual(),'tr_scale':.5,'tr_offset':-2,'tr_raw_value':10,'tr_display_value':3};assert status(x)=='VALID'
 assert status({**x,'tr_display_value':5})=='INVALID'
 assert status({**x,'tr_element_type':11})=='UNVERIFIED'
 assert status({**x,'tr_element_type':11,'tr_scalar_hex':'000000000000000a'})=='VALID'
def test_uri_bytes_and_uuid_not_generated_default():
 assert status({**actual('MD'),'tr_session_hex':'01'*16,'tr_source_uri':'ä'*16,'tr_source_uri_bytes':32})=='VALID'
 assert status({**actual('MD'),'tr_session_hex':'01'*15})=='INVALID'
 assert status({**actual('MD'),'tr_source_uri':'ä'*17,'tr_source_uri_bytes':34})=='INVALID'
def test_peer_cap_and_full_consumer_bound_not_pd_timeout():
 x={**actual(),'tr_source_ms':1,'tr_transport_ms':2,'tr_consumer_ms':3,'tr_e2e_ms':6,'tr_deadline_ms':6,'tr_age_ms':5,'tr_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'tr_e2e_ms':2},{'tr_deadline_ms':5},{'tr_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 assert status({**actual(),'tr_data_bytes':10,'tr_peer_max_data_bytes':9})=='INVALID'
 assert status({**actual(),'tr_data_accepted':True,'tr_pd_expired':True})=='INVALID'
 assert status({**actual(),'tr_data_accepted':True})=='UNVERIFIED'
def test_library_proposals_not_actual_mode_topology_identity():
 f={v['key']:v for v in registry.parameter_fields('trdp')}
 assert [v['value']for v in f['tr_port']['conditional_defaults']]==[17224,17225]
 assert [v['value']for v in f['tr_qos']['conditional_defaults']]==[5,3]
 for k in('tr_publish_cycle_us','tr_com_id','tr_session_hex','tr_dataset_id','tr_source_address','tr_tsn_build','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
def test_registered_edition_requires_own_rules_not_3_0_bounds():
 x={**actual(),'tr_review_profile':'REGISTERED_ACTUAL','tr_registered_source':'synthetic','tr_data_bytes':70000};assert status(x)=='UNVERIFIED'
