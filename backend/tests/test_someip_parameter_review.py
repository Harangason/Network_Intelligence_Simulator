"""SOME/IP own serializer/transaction/UDP-TCP-TP regression boundaries."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.someip import rules as R

def actual():
 x={'someip_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(someip_edition='FO_R25_11',someip_proposal_mode='ACTUAL_CONFIG',someip_transport='UDP',someip_role='SENDER',someip_message='APPLICATION',someip_message_type='REQUEST',someip_session_active=True)
 return x

def status(x):return registry.validate_parameters('someip',x)['status']

def test_someip_own_transport_and_payload_not_can_or_forced_ethernet():
 p=registry.profile('someip');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert 'ethernet'not in p['default_stack']
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('someip')};assert not set(R.REMOVED)&set(f)
 for k in('payload_bytes','someip_session_id','someip_service_id','someip_tp_reassembly_timeout_s','someip_response_timeout_s','someip_udp_budget_bytes'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('someip'),ids=lambda f:f['key'])
def test_each_field_type_and_own_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('transport,flag',[('UDP',0),('TCP',0),('UDP_TP',32)])
@pytest.mark.parametrize('kind,code',list(R.BASE_TYPES.items()))
def test_message_wire_type_and_tp_flag(transport,flag,kind,code):
 x={**actual(),'someip_transport':transport,'someip_message_type':kind,'someip_wire_type':code+flag,'someip_tp_flag':bool(flag)}
 if kind=='REQUEST_NO_RETURN'and transport!='UDP_TP':x['someip_session_active']=False
 assert status(x)=='VALID'
 assert status({**x,'someip_wire_type':code+flag+1})=='INVALID'
 assert status({**x,'someip_tp_flag':not bool(flag)})=='INVALID'

def test_ids_length_and_request_session_binding():
 x={**actual(),'someip_service_id':3,'someip_method_id':9,'someip_message_id':3*65536+9,'someip_client_id':7,'someip_session_id':1,'someip_request_id':7*65536+1,'payload_bytes':12,'someip_length_bytes':20,'someip_message_bytes':28}
 assert status(x)=='VALID'
 for k,v in [('someip_message_id',9),('someip_request_id',7),('someip_length_bytes',28),('someip_message_bytes',20),('someip_session_id',0)]:assert status({**x,k:v})=='INVALID'
 assert status({**x,'someip_session_id':65535,'someip_request_id':7*65536+65535})=='VALID'

def test_recommended_id_split_is_not_mandatory_method_limit():
 assert status({**actual(),'someip_method_id':65534})=='VALID'

@pytest.mark.parametrize('key,values',[('service_id',[0,65534,65535]),('method_id',[0,32767,32768,65535])])
def test_reserved_ids_not_ordinary_application_identifiers(key,values):
 for v in values:assert status({**actual(),'someip_'+key:v})=='INVALID'

@pytest.mark.parametrize('kind',['REQUEST','REQUEST_NO_RETURN','NOTIFICATION'])
def test_only_zero_request_return_codes(kind):
 x={**actual(),'someip_message_type':kind,'someip_return_code':0}
 if kind=='REQUEST_NO_RETURN':x['someip_session_active']=False
 assert status(x)=='VALID';assert status({**x,'someip_return_code':1})=='INVALID'

def test_error_nonzero_and_interface_specific_allocation():
 x={**actual(),'someip_message_type':'ERROR','someip_return_code':1};assert status(x)=='VALID'
 assert status({**x,'someip_return_code':0})=='INVALID'
 assert status({**x,'someip_return_code':32})=='UNVERIFIED'
 assert status({**x,'someip_return_code':32,'someip_return_code_source':'synthetic-interface-error32'})=='VALID'

def test_notification_client_zero_and_fire_forget_inactive_session():
 x={**actual(),'someip_message_type':'NOTIFICATION','someip_client_id':0};assert status(x)=='VALID'
 assert status({**x,'someip_client_id':7})=='INVALID'
 x={**actual(),'someip_message_type':'REQUEST_NO_RETURN','someip_session_active':False,'someip_session_id':0};assert status(x)=='VALID'
 assert status({**x,'someip_session_active':True})=='INVALID'

def test_udp_recommendation1400_not_universal_payload65535_or_datagram_limit():
 x={**actual(),'payload_bytes':2000,'someip_length_bytes':2008,'someip_message_bytes':2016,'someip_udp_budget_bytes':3000,'someip_accumulation_bytes':100,'someip_datagram_bytes':2116}
 assert status(x)=='VALID'
 assert status({**x,'someip_udp_budget_bytes':2115})=='INVALID'
 assert status({**x,'someip_datagram_bytes':2016})=='INVALID'
 assert status({**actual(),'someip_transport':'TCP','payload_bytes':70000,'someip_length_bytes':70008,'someip_message_bytes':70016})=='VALID'

@pytest.mark.parametrize('order',['someip_header_order','someip_structural_order'])
def test_scalar_little_endian_not_length_tag_or_header(order):
 x={**actual(),'someip_payload_order':'LITTLE_ENDIAN',order:'BIG_ENDIAN'};assert status(x)=='VALID'
 assert status({**x,order:'LITTLE_ENDIAN'})=='INVALID'

@pytest.mark.parametrize('kind',['array','string'])
def test_dynamic_length_field_cannot_be_absent(kind):
 x={**actual(),'someip_'+kind+'_kind':'DYNAMIC','someip_'+kind+'_length_bytes':1};assert status(x)=='VALID'
 assert status({**x,'someip_'+kind+'_length_bytes':0})=='INVALID'
 assert status({**x,'someip_'+kind+'_kind':'FIXED','someip_'+kind+'_length_bytes':0})=='VALID'

def tlv():return {**actual(),'someip_serialization':'TLV','someip_alignment':1,'someip_top_length_bytes':4,**{'someip_'+k+'_length_bytes':4 for k in('array','string','struct','union')}}

@pytest.mark.parametrize('bad',[{'someip_alignment':2},{'someip_struct_length_bytes':0},{'someip_array_length_bytes':2},{'someip_union_length_bytes':3}])
def test_tlv_no_zero_length_no_override_and_byte_alignment(bad):
 assert status(tlv())=='VALID';assert status({**tlv(),**bad})=='INVALID'

def segment():
 return {**actual(),'someip_transport':'UDP_TP','someip_tp_flag':True,'someip_tp_more':True,'someip_tp_segment_bytes':1392,'someip_tp_offset_units':87,'someip_tp_offset_bytes':1392,'someip_tp_original_bytes':3000,'someip_tp_buffer_bytes':4000,'someip_tp_reserved':0,'someip_length_bytes':1404,'someip_message_bytes':1412}

@pytest.mark.parametrize('bad',[{'someip_tp_segment_bytes':1391},{'someip_tp_offset_bytes':87},{'someip_tp_original_bytes':2783},{'someip_tp_buffer_bytes':2999},{'someip_tp_reserved':1},{'someip_length_bytes':1400},{'someip_session_active':False}])
def test_tp_offset16_units_reserved_sender_alignment_and_buffer(bad):
 assert status(segment())=='VALID';assert status({**segment(),**bad})=='INVALID'

def test_tp_last_segment_need_not_align_and_recommended1392_is_not_absolute():
 x={**segment(),'someip_tp_more':False,'someip_tp_segment_bytes':3,'someip_length_bytes':15,'someip_message_bytes':23};assert status(x)=='VALID'
 x={**segment(),'someip_tp_segment_bytes':1408,'someip_length_bytes':1420,'someip_message_bytes':1428};assert status(x)=='VALID'
 assert status({**segment(),'someip_role':'RECEIVER','someip_tp_reserved':7})=='VALID'

def test_cp_timeout_uses_actual_separation_and_route_budget_not_default100ms():
 x={**segment(),'someip_edition':'CP_R25_11','someip_tp_separation_s':.001,'someip_tp_budget_s':.002,'someip_tp_reassembly_timeout_s':.003,'someip_tp_burst_size':1};assert status(x)=='VALID'
 assert status({**x,'someip_tp_reassembly_timeout_s':.001})=='INVALID'
 assert status({**x,'someip_tp_separation_s':0})=='INVALID'

@pytest.mark.parametrize('direction,method,kind',[('COOKIE_CLIENT_SERVER',0,'REQUEST_NO_RETURN'),('COOKIE_SERVER_CLIENT',32768,'NOTIFICATION')])
def test_directional_magic_cookie_not_ordinary_service_or_client_zero(direction,method,kind):
 x={**actual(),'someip_message':direction,'someip_transport':'TCP','someip_message_type':kind,'someip_service_id':65535,'someip_method_id':method,'someip_client_id':0xDEAD,'someip_session_id':0xBEEF,'someip_interface_version':1,'someip_length_bytes':8,'payload_bytes':0,'someip_return_code':0}
 assert status(x)=='VALID'
 assert status({**x,'someip_client_id':0})=='INVALID'
 assert status({**x,'someip_transport':'UDP'})=='INVALID'

def accepted():
 return {**actual(),'someip_data_accepted':True,'someip_outcome':'ACCEPTED','someip_binding_verified':True,'someip_codec_verified':True,'someip_protocol_version':1,'someip_interface_version':2,'someip_expected_interface_version':2,'someip_service_id':1,'someip_method_id':2,'someip_client_id':3,'someip_session_id':4,'someip_header_order':'BIG_ENDIAN','someip_structural_order':'BIG_ENDIAN','someip_wire_type':0,'someip_return_code':0,'payload_bytes':8,'someip_length_bytes':16,'someip_message_bytes':24,'someip_observation_source':'synthetic-correlated-consumer-trace','someip_source_bound_ms':1,'someip_network_bound_ms':2,'someip_consumer_bound_ms':3,'someip_e2e_bound_ms':6,'someip_e2e_limit_ms':6,'someip_age_ms':5,'someip_freshness_ms':5,'someip_udp_budget_bytes':1500,'someip_datagram_bytes':24,'someip_accumulation_bytes':0}

@pytest.mark.parametrize('bad',[{'someip_interface_version':1},{'someip_binding_verified':False},{'someip_codec_verified':False},{'someip_e2e_bound_ms':2},{'someip_e2e_limit_ms':5},{'someip_age_ms':6},{'someip_outcome':'TIMEOUT'}])
def test_wire_success_no_full_application_timing_or_freshness_acceptance(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'

def test_response_client_session_must_match_outstanding_request():
 x={**accepted(),'someip_message_type':'RESPONSE','someip_wire_type':128,'someip_expected_client_id':3,'someip_expected_session_id':4};assert status(x)=='VALID'
 assert status({**x,'someip_session_id':5})=='INVALID'
 x.pop('someip_expected_client_id');assert status(x)=='UNVERIFIED'

def test_e2e_header_not_safety_or_functional_timing_approval():
 x={**accepted(),'someip_e2e_protected':True,'someip_e2e_header_bytes':4,'someip_e2e_offset_bits':64};assert status(x)=='UNVERIFIED'
 x.update(someip_e2e_source='synthetic-independent-E2E-case',someip_e2e_verified=True);assert status(x)=='VALID'
 assert status({**x,'someip_e2e_verified':False})=='INVALID'

def test_source_proposals_do_not_overwrite_confirmed_serialization():
 x={**accepted(),'someip_proposal_mode':'SOURCE_PROPOSALS','someip_payload_order':'LITTLE_ENDIAN','someip_alignment':8};before=deepcopy(x)
 assert status(x)=='VALID'and x==before
