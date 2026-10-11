import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.websocket import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():return{'ws_'+k:'synthetic-'+k for k in R.REQUIRED}
def status(x):return registry.validate_parameters('websocket',x)['status']
def frame(n=124,client=True):
 extra=0 if n<=125 else 2 if n<=65535 else 8
 return{**actual(),'ws_direction':'CLIENT_TO_SERVER'if client else'SERVER_TO_CLIENT','ws_mask':client,'ws_mask_bytes':4 if client else 0,'ws_opcode':2,'ws_fin':True,'ws_rsv':0,'ws_extension':'NONE','ws_frame_payload_bytes':n,'ws_application_bytes':n,'ws_extension_bytes':0,'ws_length_code':n if n<=125 else 126 if n<=65535 else 127,'ws_extended_length_bytes':extra,'ws_header_bytes':2+extra+(4 if client else 0)}
def test_own_industry_neutral_transport_without_ethernet_or_65535():
 p=registry.profile('websocket');assert p['domain']=='generic_networking'and p['default_stack']==['websocket']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 assert status({**actual(),'mtu_bytes':1500})=='INVALID';assert estimate_frame('websocket',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('websocket'),ids=lambda f:f['key'])
def test_every_exported_field_type_and_outer_bound(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('n',[0,124,125,126,65535,65536,2**53+1,2**63-1])
def test_minimal_payload_length_boundaries(n):
 x=frame(n);assert status(x)=='VALID';assert status({**x,'ws_extended_length_bytes':1})=='INVALID'
@pytest.mark.parametrize('client',[True,False])
def test_direction_mask_and_header(client):
 x=frame(client=client);assert status(x)=='VALID';assert status({**x,'ws_mask':not client})=='INVALID';assert status({**x,'ws_header_bytes':2})==('INVALID'if client else'VALID')
@pytest.mark.parametrize('op',[8,9,10])
def test_control_frames_final_and125_limit(op):
 x={**frame(125),'ws_opcode':op};assert status(x)=='VALID'
 for bad in({'ws_fin':False},{'ws_frame_payload_bytes':126},{'ws_rsv':4},{'ws_compressed':True}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('op',[3,4,7,11,15])
def test_reserved_opcode_without_extension_rejected(op):assert status({**frame(),'ws_opcode':op})=='INVALID'
def test_extension_length_is_part_of_payload_not_header():
 x=frame(126);x.update(ws_extension='REGISTERED_ACTUAL',ws_extension_source='synthetic',ws_extension_bytes=8,ws_application_bytes=118,ws_wire_bytes=134);assert status(x)=='VALID';assert status({**x,'ws_wire_bytes':126})=='INVALID'
@pytest.mark.parametrize('frag,fin,op',[('SINGLE',True,1),('FIRST',False,2),('CONTINUATION',False,0),('LAST',True,0)])
def test_message_fragment_sequence_role_distinct_control(frag,fin,op):
 x={**frame(),'ws_fragment':frag,'ws_fin':fin,'ws_opcode':op};assert status(x)=='VALID';assert status({**x,'ws_fin':not fin})=='INVALID'
@pytest.mark.parametrize('code',[1004,1005,1006,1015])
def test_never_transmit_reserved_close_status(code):assert status({**frame(2),'ws_opcode':8,'ws_close_code':code,'ws_close_reason_bytes':0})=='INVALID'
def test_close_body_not_single_byte_or_over125():
 assert status({**frame(1),'ws_opcode':8})=='INVALID';x={**frame(125),'ws_opcode':8,'ws_close_code':1000,'ws_close_reason_bytes':123};assert status(x)=='VALID'
def test_compression_only_first_data_frame_and_negotiated():
 x={**frame(),'ws_extension':'PERMESSAGE_DEFLATE','ws_extension_source':'synthetic','ws_fragment':'FIRST','ws_fin':False,'ws_compressed':True,'ws_rsv':4};assert status(x)=='VALID';assert status({**x,'ws_extension':'NONE'})=='INVALID'
 x.update(ws_fragment='CONTINUATION',ws_opcode=0,ws_rsv=0);assert status(x)=='VALID';assert status({**x,'ws_rsv':4})=='INVALID'
def test_deflate_response_client_window_requires_offer_and_not_server_hint_bound():
 x={**actual(),'ws_extension':'PERMESSAGE_DEFLATE','ws_extension_source':'synthetic','ws_server_window_offer':10,'ws_server_window_bits':10,'ws_server_window_bytes':1024,'ws_client_window_offered':True,'ws_client_window_offer':9,'ws_client_window_bits':15,'ws_client_window_bytes':32768};assert status(x)=='VALID'
 for bad in({'ws_server_window_bits':11},{'ws_client_window_offered':False},{'ws_client_window_bytes':512}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('transport',['HTTP2_STREAM','HTTP3_QUIC_STREAM'])
def test_extended_connect_is_not_http1_upgrade_handshake(transport):
 x={**actual(),'ws_transport':transport,'ws_method':'CONNECT','ws_connect_enabled':True,'ws_protocol':'websocket','ws_path':'/','ws_authority':'host','ws_http_scheme':'https','ws_scheme':'wss','ws_http_status':200};assert status(x)=='VALID'
 for bad in({'ws_method':'GET'},{'ws_http_status':101},{'ws_upgrade_header':True},{'ws_key_header':True},{'ws_connect_enabled':False},{'ws_http_scheme':'http'}):assert status({**x,**bad})=='INVALID'
def test_http1_version13_and101_upgrade():
 x={**actual(),'ws_transport':'HTTP1_TCP','ws_method':'GET','ws_version':13,'ws_http_status':101};assert status(x)=='VALID';assert status({**x,'ws_version':12})=='INVALID'
def test_reassembled_buffer_and_consumer_bound_not_pong():
 x={**actual(),'ws_message_bytes':100000,'ws_max_message_bytes':100000,'ws_source_ms':1,'ws_transport_ms':2,'ws_use_ms':3,'ws_e2e_ms':6,'ws_deadline_ms':6,'ws_age_ms':4,'ws_freshness_ms':4,'ws_data_accepted':True,'ws_observation_source':'synthetic','ws_path_verified':True,'ws_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in({'ws_max_message_bytes':65535},{'ws_e2e_ms':2},{'ws_deadline_ms':5},{'ws_outcome':'PONG_ONLY'}):assert status({**x,**bad})=='INVALID'
def test_only_rfc_baselines_no_fabricated_runtime_limit():
 f={v['key']:v for v in registry.parameter_fields('websocket')};assert f['ws_version']['conditional_defaults'][0]['value']==13
 for k in('ws_max_message_bytes','ws_transport_ms','ws_mask_source','ws_transport_source','payload_bytes'):assert'default'not in f[k]and'conditional_defaults'not in f[k]
