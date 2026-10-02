"""OCPP edition/binding isolation, wire integrity and confirmed-value preservation."""
from copy import deepcopy
import json
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import ocpp as O
def actual(version='V2_1_ED2',binding='JSON_WEBSOCKET'):
 x={'oc_'+k:'synthetic-actual-'+k for k in O.REQUIRED}
 x.update(oc_version=version,oc_binding=binding,oc_role='STATION',oc_transport='WSS',oc_subprotocol=O.SUBPROTOCOLS[version])
 if binding=='SOAP_HTTP':
  x.pop('oc_subprotocol');x.update(oc_transport='HTTPS',oc_soap_version='1.2',oc_soap_action='/Heartbeat',oc_soap_phase='REQUEST',
   oc_soap_message_id='urn:uuid:some-actual-request-identifier-longer-than-36-characters',oc_soap_from='https://station.example.test/inbound',oc_soap_reply_to='http://www.w3.org/2005/08/addressing/anonymous')
 return x
def status(x):return registry.validate_parameters('ocpp',x)['status']
def frame(kind=2,version='V2_1_ED2'):
 x=actual(version);x.update(oc_message_type=kind,oc_message_id='m42',oc_message_id_chars=3,oc_max_message_bytes=100000,
  oc_limit_source='synthetic-reported-limit',oc_expects_response=kind==2)
 if kind in(2,6):
  action='Heartbeat'if kind==2 else'NotifyPeriodicEventStream';wire=[kind,'m42',action,{}];x.update(oc_action=action,oc_message_id_unused=True,oc_phase='NEW')
 elif kind==3:wire=[kind,'m42',{}]
 else:
  code='FormationViolation'if version==O.VERSIONS[0]else'FormatViolation';wire=[kind,'m42',code,'',{}];x.update(oc_error_code=code,oc_error_description='')
 if kind in(3,4,5):x.update(oc_pending_message_id='m42',oc_pending_connection_id=x['oc_connection_id'],oc_pending_match=True)
 x.update(oc_wire_text=json.dumps(wire,separators=(',',':')),oc_envelope_elements=len(wire));x['oc_wire_bytes']=len(x['oc_wire_text'].encode())
 return x
def test_ocpp_application_has_no_ethernet_clock_mtu_or_payload8_65535_fallback():
 p=registry.profile('ocpp');assert p['domain']=='generic_networking';assert p['default_stack']==['ocpp']
 assert p['capacity_evidence']['status']=='MODEL_MISSING';assert p['max_payload_bytes']is None
 assert registry.parameter_defaults_review('ocpp')['values']=={};assert status(actual())=='VALID'
 keys=[f['key']for f in registry.parameter_fields('ocpp')];assert len(keys)==len(set(keys));assert not set(keys)&set(O.REMOVED)
 for patch in({'bitrate_bps':10000000},{'mtu_bytes':1500},{'mq_qos':1},{'o_transport':'CAN_11_250'},{'local_timing_evidence':{}}):assert status({**actual(),**patch})=='INVALID'
 assert status({**actual(),'payload_bytes':70000})=='VALID'
 for key in('payload_bytes','oc_heartbeat_s','oc_ping_s','oc_message_timeout_s','oc_station_id','oc_password_chars','oc_max_message_bytes'):
  f=next(f for f in registry.parameter_fields('ocpp')if f['key']==key);assert 'default'not in f;assert not f.get('conditional_defaults')
@pytest.mark.parametrize('field',registry.parameter_fields('ocpp'),ids=lambda f:f['key'])
def test_ocpp_every_declared_parameter_type_unit_and_applicable_bound(field):
 bad='not-number'if field['type']=='number'else 1
 assert status({**actual(),field['key']:bad})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('version',O.VERSIONS)
def test_ocpp_actual_negotiated_subprotocol_is_edition_specific(version):
 x=actual(version);assert status(x)=='VALID';assert status({**x,'oc_subprotocol':'ocpp1.6,ocpp2.1'})=='INVALID'
 x.pop('oc_subprotocol');assert status(x)=='UNVERIFIED'
 f=next(f for f in registry.parameter_fields('ocpp')if f['key']=='oc_subprotocol')
 assert any(d['when']=={'oc_version':version,'oc_binding':'JSON_WEBSOCKET'}and d['value']==O.SUBPROTOCOLS[version]for d in f['conditional_defaults'])
@pytest.mark.parametrize('kind',[2,3,4,5,6])
def test_ocpp21_five_envelope_types_have_distinct_shape_and_response_semantics(kind):
 x=frame(kind);assert status(x)=='VALID'
 for patch in({'oc_envelope_elements':x['oc_envelope_elements']+1},{'oc_wire_bytes':x['oc_wire_bytes']+1},
  {'oc_message_id':'other'},{'oc_expects_response':not x['oc_expects_response']}):assert status({**x,**patch})=='INVALID'
 wire=json.loads(x['oc_wire_text']);wire[-1]=None;bad=json.dumps(wire)
 assert status({**x,'oc_wire_text':bad,'oc_wire_bytes':len(bad)})=='INVALID'
 if kind in(3,4,5):
  assert status({**x,'oc_pending_match':False})=='INVALID';assert status({**x,'oc_pending_connection_id':'another-station'})=='INVALID'
  x.pop('oc_pending_message_id');assert status(x)=='UNVERIFIED'
 if kind==2:assert status({**x,'oc_pending_calls':1})=='INVALID'
 if kind==6:assert status({**x,'oc_pending_calls':1})=='VALID'
@pytest.mark.parametrize('version',O.VERSIONS[:2])
@pytest.mark.parametrize('kind',[5,6])
def test_ocpp_pre21_has_no_send_or_result_error(version,kind):assert status(frame(kind,version))=='INVALID'
@pytest.mark.parametrize('wire',[
 '{}','[true,"m42","Heartbeat",{}]','[2.0,"m42","Heartbeat",{}]','[2,"m42","Heartbeat",null]',
 '[2,"m42","Heartbeat",{"v":NaN}]','[2,"m42","Heartbeat",{"v":Infinity}]',
 '[2,"m42","Heartbeat",{"v":1,"v":2}]','[2,"m42","Heartbeat",{"v":"\\ud800"}]',
 '[2,"m42","Heartbeat",{},0]','[2,"m42","Other",{}]','[2,"m43","Heartbeat",{}]'])
def test_ocpp_json_wire_integrity_not_proved_by_declared_scalar_fields(wire):
 x=frame();x.update(oc_wire_text=wire,oc_wire_bytes=len(wire.encode()));assert status(x)=='INVALID'
def test_ocpp_utf8_escaping_and_whitespace_count_wire_bytes_not_unicode_or_compact_object():
 x=frame();x['oc_wire_text']='[2, "m42", "Heartbeat", {"text":"ä 😀"}]';x['oc_wire_bytes']=len(x['oc_wire_text'].encode())
 assert status(x)=='VALID';assert status({**x,'oc_wire_bytes':len(x['oc_wire_text'])})=='INVALID'
 x.update(oc_message_id='a'*36,oc_message_id_chars=36);x['oc_wire_text']=json.dumps([2,x['oc_message_id'],'Heartbeat',{}]);x['oc_wire_bytes']=len(x['oc_wire_text']);assert status(x)=='VALID'
 assert status({**x,'oc_message_id_chars':37})=='INVALID'
def test_ocpp_identity_old_space_example_differs_new_identifier_and_basic_colon_rule():
 x={**actual(O.VERSIONS[0]),'oc_station_id':'RDAM 123','oc_station_id_chars':8};assert status(x)=='VALID'
 x.update(oc_version=O.VERSIONS[2],oc_subprotocol='ocpp2.1');assert status(x)=='INVALID'
 x.update(oc_station_id='RDAM|123');assert status(x)=='VALID'
 for value in('a'*49,'ID:123','ID/123','ID😀'):assert status({**x,'oc_station_id':value,'oc_station_id_chars':len(value)})=='INVALID'
def test_ocpp_security_and_compression_are_selected_profile_role_and_negotiation_not_defaults():
 x={**actual(),'oc_security_profile':'PROFILE2_TLS_BASIC','oc_tls':True,'oc_tls_version':'V1_2','oc_basic_auth':True,
  'oc_peer_verified':True,'oc_certificate_source':'synthetic-chain-hostname-time','oc_password_source':'synthetic-provisioning',
  'oc_password_chars':16,'oc_password_max_chars':40};assert status(x)=='VALID'
 for patch in({'oc_tls':False},{'oc_tls_version':'V1_1'},{'oc_peer_verified':False},{'oc_password_chars':15},{'oc_password_max_chars':65}):assert status({**x,**patch})=='INVALID'
 x.update(oc_role='CSMS',oc_compression_supported=False);assert status(x)=='INVALID'
 x.update(oc_role='STATION');assert status(x)=='VALID'
 x.update(oc_compression_negotiated=True);assert status(x)=='INVALID'
 x.update(oc_compression_supported=True,oc_compressed_bytes=19);assert status(x)=='VALID'
 assert status({**actual(),'oc_endpoint':'ws://server.example.test/x'})=='INVALID'
 assert status({**actual(),'oc_endpoint':'wss://server.example.test/x'})=='VALID'
def test_ocpp_heartbeat_ping_timeout_boot_status_and_meter_zero_have_distinct_meaning():
 x={**actual(),'oc_message_timeout_s':42,'oc_ping_s':0,'oc_boot_status':'Accepted','oc_boot_interval_s':600,'oc_heartbeat_s':600};assert status(x)=='VALID'
 for patch in({'oc_message_timeout_s':0},{'oc_ping_s':-1},{'oc_heartbeat_s':300}):assert status({**x,**patch})=='INVALID'
 x.update(oc_boot_status='Pending',oc_boot_interval_s=0,oc_boot_wait_s=30);assert status(x)=='VALID'
 assert status({**x,'oc_boot_wait_s':0})=='INVALID'
 x.update(oc_boot_interval_s=60);assert status(x)=='INVALID'
 x.update(oc_boot_wait_s=60);assert status(x)=='VALID'
 assert status({**actual(O.VERSIONS[0]),'oc_meter_sample_s':0,'oc_clock_aligned_s':0,'oc_connection_timeout_s':42})=='VALID'
def test_ocpp_reconnect_doubling_is_separate_transaction_resubmit_and_current_device_limits():
 x={**actual(),'oc_backoff_repeat':3,'oc_backoff_step':2,'oc_backoff_min_s':5,'oc_backoff_random_s':10,'oc_backoff_jitter_s':3,'oc_backoff_wait_s':23,
  'oc_attempt_interval_s':7,'oc_preceding_transmissions':2,'oc_resubmit_wait_s':14,'oc_message_items':8,'oc_max_message_items':8}
 assert status(x)=='VALID'
 for patch in({'oc_backoff_step':4},{'oc_backoff_jitter_s':11},{'oc_backoff_wait_s':20},{'oc_resubmit_wait_s':7},{'oc_message_items':9}):assert status({**x,**patch})=='INVALID'
def test_ocpp16_soap_is_12_synchronous_wsa_not_json36_or_another_edition():
 x=actual(O.VERSIONS[0],'SOAP_HTTP');assert status(x)=='VALID'
 for patch in({'oc_soap_version':'1.1'},{'oc_version':O.VERSIONS[1]},{'oc_soap_action':'Heartbeat'},
  {'oc_soap_reply_to':'https://callback.example.test'},{'oc_subprotocol':'ocpp1.6'},{'oc_message_type':2}):assert status({**x,**patch})=='INVALID'
 x.update(oc_soap_phase='RESPONSE',oc_soap_action='/HeartbeatResponse',oc_soap_request_id='urn:request42',oc_soap_relates_to='urn:request42');assert status(x)=='VALID'
 assert status({**x,'oc_soap_relates_to':'urn:other'})=='INVALID'
def test_ocpp_legacy_error_spelling_is_not_silently_rewritten_to_new_enum():
 assert status(frame(4,O.VERSIONS[0]))=='VALID'
 x=frame(4,O.VERSIONS[0]);x['oc_error_code']='FormatViolation';assert status(x)=='INVALID'
 x=frame(4);x['oc_error_code']='FormationViolation';assert status(x)=='INVALID'
 for v in O.NEW:assert status({**actual(v),'oc_error_code':'MessageTypeNotSupported'})=='INVALID'
def test_ocpp_action_names_are_versioned_and_send_is_only_registered_periodic_stream():
 for v,action in[(O.VERSIONS[0],'RemoteStartTransaction'),(O.VERSIONS[1],'RequestStartTransaction'),(O.VERSIONS[2],'SetDERControl')]:
  x=frame(2,v);x['oc_action']=action;x['oc_wire_text']=json.dumps([2,'m42',action,{}]);x['oc_wire_bytes']=len(x['oc_wire_text']);assert status(x)=='VALID'
 for v,action in[(O.VERSIONS[0],'RequestStartTransaction'),(O.VERSIONS[1],'SetDERControl'),(O.VERSIONS[2],'RemoteStartTransaction')]:
  assert status({**actual(v),'oc_message_type':2,'oc_message_id':'id','oc_message_id_chars':2,'oc_action':action})=='INVALID'
 x=frame(6);assert status({**x,'oc_action':'NotifyEventStream'})=='INVALID'
 # The publisher errata itself uses '=' in its example. Actual JSON uses ':'.
 wire='[6,"m42","NotifyPeriodicEventStream",{"basetime"="2024-08-27T12:30:40Z"}]'
 assert status({**x,'oc_wire_text':wire,'oc_wire_bytes':len(wire)})=='INVALID'
def test_ocpp_confirmed_actual_heartbeat_timeout_large_message_and_identifier_persist_after_rejection():
 from backend.engineering.workflow.service import WorkflowStatusService
 from backend.engineering.project_context import current_project_id
 x={**actual(),'oc_heartbeat_s':42,'oc_message_timeout_s':17,'oc_station_id':'MY|STATION','oc_station_id_chars':10,'payload_bytes':70000}
 g={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
 p={'technology':'ocpp','technology_parameters':{'ocpp':g}};service=WorkflowStatusService(current_project_id());service.save_parameters(p);assert service.get()['parameters']==p
 bad=deepcopy(p);bad['technology_parameters']['ocpp']['values']['bitrate_bps']=10000000
 with pytest.raises(ValueError):service.save_parameters(bad)
 assert service.get()['parameters']==p
