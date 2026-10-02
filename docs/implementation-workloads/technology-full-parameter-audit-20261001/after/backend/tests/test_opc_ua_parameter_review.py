"""Source-qualified OPC UA semantics; no PHY/capacity certification claim."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import opc_ua as U

def actual(binding='UA_TCP',family='RSA'):
 x={'ua_'+k:'synthetic-'+k for k in U.REQUIRED}
 scheme='opc.tcp'if binding=='UA_TCP'else 'opc.https'if binding.startswith('HTTPS')else 'opc.wss'
 x.update(ua_edition=U.EDITION,ua_binding=binding,ua_direction='REQUEST',ua_endpoint=scheme+'://server.invalid/ua')
 if binding in U.UACP:
  n=1024 if family=='ECC' else 8192
  uri=next(u for u,(f,_)in U.POLICIES.items()if f==family)
  x.update(ua_security_family=family,ua_security_policy_uri=uri,ua_security_mode='None'if family=='NONE'else'SignAndEncrypt',
   ua_protocol_requested=0,ua_protocol_revised=0,ua_hello_rx=n,ua_hello_tx=n,ua_ack_rx=n,ua_ack_tx=n,
   ua_endpoint_utf8_bytes=len(x['ua_endpoint'].encode()),ua_endpoint_encoded_bytes=len(x['ua_endpoint'].encode())+4)
 if binding in U.WS:x['ua_subprotocol']=dict(zip(U.WS,('opcua+uacp','opcua+uajson','opcua+openapi')))[binding]
 return x
def check(x):return registry.validate_parameters('opc_ua',x)
def status(x):return check(x)['status']
def message(x=None):
 a=actual()if x is None else deepcopy(x)
 a.update(ua_message_type='MSG',ua_chunk_type='F',ua_channel_id=19,ua_sequence=42,ua_previous_sequence=41,
  ua_request_id=300,ua_legacy_sequence=True,ua_sequence_phase='NEXT',ua_sequence_unused_for_token=True)
 raw=b'MSGF'+(24).to_bytes(4,'little')+(19).to_bytes(4,'little')+(2).to_bytes(4,'little')+(42).to_bytes(4,'little')+(300).to_bytes(4,'little')
 a.update(ua_chunk_hex=raw.hex().upper(),ua_chunk_bytes=len(raw));return a

def test_opc_ua_is_application_not_can_or_ethernet_phy():
 p=registry.profile('opc_ua');assert p['default_stack']==['opc_ua'];assert p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING';assert status(actual())=='VALID'
 keys=[f['key']for f in registry.parameter_fields('opc_ua')];assert len(keys)==len(set(keys));assert not set(keys)&set(U.REMOVED)
 for bad in({'bitrate_bps':10000000},{'mtu_bytes':1500},{'local_timing_evidence':{}},{'can_identifier':1},{'ow_mode':'STANDARD'}):assert status({**actual(),**bad})=='INVALID'
 assert status({**actual(),'payload_bytes':70000})=='VALID'

@pytest.mark.parametrize('field',registry.parameter_fields('opc_ua'),ids=lambda f:f['key'])
def test_opc_ua_every_declared_field_has_matching_type_and_bounds(field):
 bad='not-number'if field['type']=='number'else 1
 assert status({**actual(),field['key']:bad})=='INVALID'
 for edge,offset in(('min',-1),('max',1)):
  if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

def test_opc_ua_proposals_are_source_qualified_not_negotiated_or_confirmed():
 f={v['key']:v for v in registry.parameter_fields('opc_ua')}
 assert f['ua_edition']['default']==U.EDITION;assert f['ua_subscription_priority']['default']==0
 assert {(d['when']['ua_security_family'],d['value'])for d in f['ua_hello_rx']['conditional_defaults']}=={('RSA',8192),('NONE',8192),('ECC',1024)}
 assert f['ua_sampling_requested_ms']['conditional_defaults'][0]['value']==-1
 assert f['ua_queue_requested']['conditional_defaults'][0]['value']==1
 for k in('ua_ack_rx','ua_security_policy_uri','ua_security_mode','ua_endpoint','ua_publish_revised_ms','ua_item_status','payload_bytes'):
  assert 'default'not in f[k];assert not f[k].get('conditional_defaults')

@pytest.mark.parametrize('family',['RSA','ECC','NONE'])
def test_opc_ua_hello_ack_security_minima_and_cross_direction_buffers(family):
 x=actual(family=family);assert status(x)=='VALID'
 n=x['ua_hello_rx'];assert status({**x,'ua_hello_rx':n-1})=='INVALID'
 assert status({**x,'ua_ack_rx':x['ua_hello_tx']+1})=='INVALID'
 x.update(ua_hello_rx=10000,ua_hello_tx=20000,ua_ack_rx=15000,ua_ack_tx=9000,ua_chunk_bytes=12000)
 assert status(x)=='VALID';assert status({**x,'ua_direction':'RESPONSE'})=='INVALID'
 assert status({**x,'ua_ack_tx':8191})=='INVALID'
 x=actual(family='ECC');assert status({**x,'ua_ack_rx':1023})=='INVALID'

def test_opc_ua_body_and_chunk_limits_zero_means_no_limit_direction_matters():
 x={**actual(),'ua_client_max_message':10,'ua_server_max_message':0,'ua_message_body_bytes':70000,
  'ua_client_max_chunks':1,'ua_server_max_chunks':0,'ua_message_chunks':2};assert status(x)=='VALID'
 assert status({**x,'ua_direction':'RESPONSE'})=='INVALID'
 assert status({**x,'ua_server_max_message':70000,'ua_server_max_chunks':2})=='VALID'
 assert status({**x,'ua_server_max_message':69999})=='INVALID'

def test_opc_ua_endpoint_binary_string_length_is_not_character_count_or_ethernet_mtu():
 x=actual();x['ua_endpoint']='opc.tcp://server.invalid/ä';x['ua_endpoint_utf8_bytes']=len(x['ua_endpoint'].encode());x['ua_endpoint_encoded_bytes']=x['ua_endpoint_utf8_bytes']+4
 assert status(x)=='VALID';assert status({**x,'ua_endpoint_utf8_bytes':len(x['ua_endpoint'])})=='INVALID'
 prefix='opc.tcp://server.invalid/';x['ua_endpoint']=prefix+'a'*(4091-len(prefix));x.update(ua_endpoint_utf8_bytes=4091,ua_endpoint_encoded_bytes=4095)
 assert status(x)=='VALID';x['ua_endpoint']+='a';x.update(ua_endpoint_utf8_bytes=4092,ua_endpoint_encoded_bytes=4096);assert status(x)=='INVALID'

def test_opc_ua_exact_little_endian_wire_header_and_size_include_header():
 x=message();assert status(x)=='VALID'
 for bad in({'ua_chunk_bytes':16},{'ua_channel_id':20},{'ua_chunk_hex':x['ua_chunk_hex'][:8]+'00000018'+x['ua_chunk_hex'][16:]},
  {'ua_message_type':'OPN'},{'ua_chunk_type':'C'},{'ua_chunk_hex':' '.join([x['ua_chunk_hex'][:8],x['ua_chunk_hex'][8:]])}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ua_chunk_hex':x['ua_chunk_hex'].lower()})=='VALID'
 x.update(ua_message_type='OPN',ua_chunk_type='C',ua_chunk_hex=None);assert status(x)=='INVALID'

def test_opc_ua_sequence_renew_wrap_and_response_correlation():
 x=message();assert status({**x,'ua_token_id':99})=='VALID'
 assert status({**x,'ua_sequence':0})=='INVALID';assert status({**x,'ua_sequence_unused_for_token':False})=='INVALID'
 x.pop('ua_chunk_hex');x.update(ua_legacy_sequence=False,ua_security_family='ECC',ua_security_policy_uri='http://opcfoundation.org/UA/SecurityPolicy#ECC_curve25519_ChaCha20Poly1305',
  ua_sequence_phase='WRAP',ua_previous_sequence=U.UINT32,ua_sequence=0);assert status(x)=='VALID'
 assert status({**x,'ua_previous_sequence':U.UINT32-1})=='INVALID'
 x.update(ua_direction='RESPONSE',ua_pending_request_id=300,ua_pending_connection_id=x['ua_connection_id']);assert status(x)=='VALID'
 assert status({**x,'ua_pending_request_id':301})=='INVALID';assert status({**x,'ua_pending_connection_id':'another'})=='INVALID'
 x.update(ua_legacy_sequence=True,ua_security_policy_uri='http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256',ua_security_family='RSA',ua_previous_sequence=U.UINT32-1023,ua_sequence=1023);assert status(x)=='VALID'
 assert status({**x,'ua_previous_sequence':U.UINT32-1024})=='INVALID';assert status({**x,'ua_sequence':1024})=='INVALID'

def test_opc_ua_current_policy_is_not_an_archived_forbidden_uri_or_insecure_default():
 assert status({**actual(),'ua_security_policy_uri':U.FORBIDDEN_POLICY,'ua_security_family':'ECC'})=='INVALID'
 assert status({**actual(),'ua_security_family':'NONE','ua_security_mode':'Sign'})=='INVALID'
 x=actual(family='ECC');x.update(ua_legacy_sequence=True);assert status(x)=='INVALID'

@pytest.mark.parametrize('binding',U.BINDINGS[:-1])
def test_opc_ua_transport_encoding_scope_never_reuses_uacp_for_json(binding):
 x=actual(binding);assert status(x)=='VALID'
 if binding in('WS_JSON','WS_OPENAPI'):
  assert status({**x,'ua_hello_rx':8192})=='INVALID'
  assert status({**x,'ua_ws_frame_bytes':1025,'ua_ws_receiver_limit':1024})=='INVALID'
  assert status({**x,'ua_ws_frame_bytes':1024,'ua_ws_receiver_limit':1024})=='VALID'
 if binding in U.WS:assert status({**x,'ua_subprotocol':'opcua+json'})=='INVALID'
 if binding=='WS_OPENAPI':
  assert status({**x,'ua_gzip':False,'ua_ws_opcode':1})=='VALID';assert status({**x,'ua_gzip':True,'ua_ws_opcode':1})=='INVALID'

def test_opc_ua_requested_and_revised_service_values_are_independent():
 x={**actual(),'ua_session_requested_ms':60000,'ua_session_revised_ms':120000,'ua_publish_requested_ms':-1,'ua_publish_revised_ms':250,
  'ua_keepalive_requested':0,'ua_keepalive_revised':10,'ua_lifetime_requested':1,'ua_lifetime_revised':30};assert status(x)=='VALID'
 assert status({**x,'ua_lifetime_revised':29})=='INVALID';assert status({**x,'ua_session_revised_ms':0})=='INVALID'
 x.update(ua_session_service=True,ua_session_id='actual-session',ua_session_activated=False);assert status(x)=='INVALID'
 x['ua_session_activated']=True;assert status(x)=='VALID'
 assert status({**x,'ua_token_revised_ms':10000,'ua_renew_proposal_ms':7500})=='VALID'
 assert status({**x,'ua_token_revised_ms':10000,'ua_renew_proposal_ms':10000})=='INVALID'

def test_opc_ua_sampling_revision_maximum_exception_and_negative_sentinel():
 x={**actual(),'ua_sampling_requested_ms':1000,'ua_sampling_revised_ms':500,'ua_sampling_server_max_ms':500};assert status(x)=='VALID'
 assert status({**x,'ua_sampling_revised_ms':499})=='INVALID'
 x.update(ua_sampling_requested_ms=100,ua_sampling_server_max_ms=500);assert status({**x,'ua_sampling_revised_ms':99})=='INVALID'
 assert status({**x,'ua_sampling_requested_ms':-20,'ua_sampling_revised_ms':250})=='VALID'
 assert status({**x,'ua_sampling_revised_ms':501})=='INVALID'

def test_opc_ua_queue_sentinel_and_discard_last_are_item_specific():
 x={**actual(),'ua_item_kind':'DATA','ua_queue_requested':0,'ua_queue_revised':1,'ua_discard_oldest':False,'ua_discard_effect':'IGNORED'};assert status(x)=='VALID'
 assert status({**x,'ua_queue_revised':2})=='INVALID'
 x.update(ua_queue_requested=10,ua_queue_revised=5,ua_discard_effect='LAST');assert status(x)=='VALID'
 assert status({**x,'ua_discard_effect':'OLDEST'})=='INVALID'
 x.update(ua_item_kind='EVENT',ua_queue_requested=1,ua_queue_revised=4,ua_event_queue_min=4,ua_event_queue_max=100);assert status(x)=='VALID'
 assert status({**x,'ua_queue_revised':1})=='INVALID'
 assert status({**x,'ua_queue_requested':U.UINT32,'ua_queue_revised':100})=='VALID'

def test_opc_ua_percent_deadband_needs_actual_analog_eu_range():
 x={**actual(),'ua_deadband':'PERCENT','ua_deadband_value':5,'ua_eu_low':-20,'ua_eu_high':180,
  'ua_deadband_threshold':10,'ua_analog_item':True,'ua_numeric_item':True};assert status(x)=='VALID'
 for bad in({'ua_deadband_value':101},{'ua_deadband_threshold':5},{'ua_analog_item':False},{'ua_eu_high':-20}):assert status({**x,**bad})=='INVALID'
 x.pop('ua_eu_low');assert status(x)=='UNVERIFIED'

def test_opc_ua_overall_good_does_not_accept_bad_item_or_stale_value():
 x={**actual(),'ua_service_status':0,'ua_item_status':0,'ua_item_severity':0,'ua_data_accepted':True,'ua_outcome':'ACCEPTED',
  'ua_age_ms':60,'ua_freshness_limit_ms':60,'ua_timeout_hint_ms':0,'ua_max_age_ms':0};assert status(x)=='VALID'
 assert status({**x,'ua_item_status':0x80000000,'ua_item_severity':2})=='INVALID'
 assert status({**x,'ua_item_status':0xC0000000,'ua_item_severity':3})=='INVALID'
 assert status({**x,'ua_service_status':0x80000000})=='INVALID'
 assert status({**x,'ua_age_ms':60.001})=='INVALID'
 x.update(ua_item_status=0x40000000,ua_item_severity=1);assert status(x)=='UNVERIFIED'
 assert status({**x,'ua_uncertain_accepted':True})=='VALID';assert status({**x,'ua_uncertain_accepted':False})=='INVALID'

def test_opc_ua_rejected_foreign_rate_does_not_overwrite_confirmed_native_values():
 x={**actual(),'ua_session_revised_ms':42000,'ua_publish_revised_ms':75,'ua_queue_requested':42,'payload_bytes':70000}
 confirmed=deepcopy(x);assert status({**x,'bitrate_bps':500000})=='INVALID';assert x==confirmed;assert status(x)=='VALID'
