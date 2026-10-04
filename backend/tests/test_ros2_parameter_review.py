"""Endpoint policy, transport isolation and real processing acceptance boundaries."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.ros2 import rules as R
def actual():
 x={'ros_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(ros_profile='RMW_ROLLING_20261002',ros_middleware='DDS',ros_rmw='rmw_cyclonedds_cpp',ros_transport='DDS_UDP',ros_interface='TOPIC',ros_role='PUBLISHER')
 return x
def status(x):return registry.validate_parameters('ros2',x)['status']
def test_ros_native_not_always_dds_udp_ethernet_or_robotics():
 p=registry.profile('ros2');assert p['default_stack']==['ros2']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and p['rate_model']['fields']==[]
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 assert not set(R.REMOVED)&{v['key']for v in registry.parameter_fields('ros2')}
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'bitrate_bps':100000000},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('ros2'),ids=lambda f:f['key'])
def test_ros_every_field_type_and_outer_bound(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
def proposals(preset):
 fields=registry.parameter_fields('ros2');x={'ros_profile':'RMW_ROLLING_20261002','ros_middleware':'DDS','ros_preset':preset}
 for f in fields:
  for item in f.get('conditional_defaults',[]):
   if all(x.get(k)==v for k,v in item['when'].items()):x[f['key']]=item['value']
 return x
@pytest.mark.parametrize('preset,depth,rel,dur',[('DEFAULT',10,'RELIABLE','VOLATILE'),('SENSOR_DATA',5,'BEST_EFFORT','VOLATILE'),('PARAMETERS',1000,'RELIABLE','VOLATILE'),('PARAMETER_EVENTS',1000,'RELIABLE','VOLATILE'),('SERVICES_DEFAULT',10,'RELIABLE','VOLATILE'),('ROSOUT',1000,'RELIABLE','TRANSIENT_LOCAL')])
def test_ros_pinned_presets_are_not_full_dds_defaults(preset,depth,rel,dur):
 x=proposals(preset)
 assert x['ros_offered_depth']==depth and x['ros_requested_reliability']==rel and x['ros_offered_durability']==dur
 assert x['ros_offered_liveliness']=='SYSTEM_DEFAULT'and x['ros_domain_id']==0 and not x['ros_avoid_namespace']
 assert x['ros_offered_lifespan_ns']==(10000000000 if preset=='ROSOUT'else 0)
 assert status({**actual(),**x})=='VALID'
 assert 'ros_actual_qos_resolved'not in x and 'bitrate'not in x
@pytest.mark.parametrize('preset,depth,deadline',[('SYSTEM_DEFAULT',0,0),('BEST_AVAILABLE',10,R.S64-1)])
def test_ros_system_or_discovery_race_profile_remains_unresolved(preset,depth,deadline):
 x=proposals(preset);assert x['ros_offered_depth']==depth and x['ros_offered_deadline_ns']==deadline
 assert status({**actual(),**x})=='VALID'
 assert status({**actual(),**x,'ros_qos_compatibility':'OK','ros_compatibility_source':'synthetic-result'})=='UNVERIFIED'
@pytest.mark.parametrize('key,pub,sub',[('reliability','BEST_EFFORT','RELIABLE'),('durability','VOLATILE','TRANSIENT_LOCAL'),('liveliness','AUTOMATIC','MANUAL_BY_TOPIC')])
def test_ros_dds_requested_policy_cannot_exceed_offered(key,pub,sub):
 x={**actual(),'ros_offered_'+key:pub,'ros_requested_'+key:sub,'ros_compatibility_source':'synthetic-result','ros_qos_compatibility':'OK'}
 assert status(x)=='INVALID';assert status({**x,'ros_qos_compatibility':'ERROR'})=='VALID'
@pytest.mark.parametrize('key',['deadline','lease'])
def test_ros_finite_deadline_and_lease_request_vs_offer(key):
 x={**actual(),'ros_duration_encoding':'NORMALIZED_NS','ros_offered_'+key+'_mode':'FINITE','ros_offered_'+key+'_ns':20,
  'ros_requested_'+key+'_mode':'FINITE','ros_requested_'+key+'_ns':30,'ros_qos_compatibility':'OK','ros_compatibility_source':'synthetic-result'}
 assert status(x)=='VALID';assert status({**x,'ros_requested_'+key+'_ns':19})=='INVALID'
 assert status({**x,'ros_offered_'+key+'_mode':'UNSPECIFIED','ros_offered_'+key+'_ns':0})=='INVALID'
@pytest.mark.parametrize('key',['deadline','lease','lifespan'])
def test_ros_duration_zero_is_unspecified_not_zero_latency(key):
 x={**actual(),'ros_duration_encoding':'NORMALIZED_NS','ros_offered_'+key+'_mode':'UNSPECIFIED','ros_offered_'+key+'_ns':0}
 assert status(x)=='VALID';assert status({**x,'ros_offered_'+key+'_ns':1})=='INVALID'
 assert status({**x,'ros_offered_'+key+'_mode':'FINITE'})=='INVALID'
 assert status({**x,'ros_offered_'+key+'_mode':'INFINITE','ros_offered_'+key+'_ns':R.S64})=='VALID'
 x.pop('ros_duration_encoding');assert status(x)=='UNVERIFIED'
def zenoh():
 return {**actual(),'ros_middleware':'ZENOH','ros_rmw':'rmw_zenoh_cpp','ros_transport':'ZENOH_TCP','ros_zenoh_config_source':'synthetic-session-config'}
def test_ros_zenoh_has_own_matching_and_discovery_not_dds_rxo():
 x={**zenoh(),'ros_offered_reliability':'BEST_EFFORT','ros_requested_reliability':'RELIABLE','ros_qos_compatibility':'ZENOH_ACTUAL','ros_compatibility_source':'synthetic-zenoh-check'}
 assert status(x)=='VALID'
 for bad in({'ros_transport':'DDS_UDP'},{'ros_qos_compatibility':'OK'},{'ros_discovery_range':'SUBNET'},{'ros_static_peers':'localhost'}, {'ros_port_mapping':'DDS_UDP_STANDARD'}):assert status({**x,**bad})=='INVALID'
 assert status({**actual(),'ros_rmw':'rmw_zenoh_cpp'})=='INVALID'
def test_ros_zenoh_default_connect_is_local_and_not_guaranteed_reachable():
 f={v['key']:v for v in registry.parameter_fields('ros2')}
 for key,value in [('zenoh_mode','peer'),('zenoh_connect','tcp/localhost:7447'),('zenoh_listen','tcp/localhost:0'),('zenoh_multicast',False),('zenoh_gossip',True),('zenoh_shm',False),('zenoh_shm_pool_bytes',50331648),('zenoh_buffer_pool_bytes',8388608),('zenoh_shm_threshold_bytes',512)]:
  p=f['ros_'+key]['conditional_defaults'][0];assert p['value']==value and p['when']['ros_middleware']=='ZENOH'
 for k in('discovered','actual_qos_resolved','type_hash','wave_source','clock_source'):
  assert 'conditional_defaults'not in f['ros_'+k]and'default'not in f['ros_'+k]
def test_ros_zenoh_shm_flag_does_not_prove_observed_path():
 x={**zenoh(),'ros_transport':'ZENOH_SHM','ros_zenoh_shm':True,'ros_zenoh_shm_capable':True,'ros_zenoh_peer_shm':True}
 assert status(x)=='UNVERIFIED';x['ros_zenoh_shm_observed']=True;assert status(x)=='VALID'
 assert status({**x,'ros_zenoh_peer_shm':False})=='INVALID'
 assert status({**x,'ros_zenoh_shm_threshold_bytes':512,'ros_zenoh_shm_threshold_bits':9})=='VALID'
 assert status({**x,'ros_zenoh_shm_threshold_bytes':513,'ros_zenoh_shm_threshold_bits':9})=='INVALID'
 assert status({**actual(),'ros_zenoh_shm':False})=='INVALID'
@pytest.mark.parametrize('domain,participant,port',[(0,0,7411),(1,119,7899),(101,53,32767),(232,62,65535)])
def test_ros_dds_default_port_mapping(domain,participant,port):
 x={**actual(),'ros_port_mapping':'DDS_UDP_STANDARD','ros_domain_id':domain,'ros_participant_id':participant,'ros_user_unicast_port':port}
 assert status(x)=='VALID';assert status({**x,'ros_user_unicast_port':port-1})=='INVALID'
def test_ros_default_dds_port_overflow_checked_without_explicit_port_and_custom_domain_separate():
 x={**actual(),'ros_port_mapping':'DDS_UDP_STANDARD','ros_domain_id':232,'ros_participant_id':63};assert status(x)=='INVALID'
 assert status({**actual(),'ros_port_mapping':'DDS_UDP_STANDARD','ros_domain_id':233})=='INVALID'
 assert status({**actual(),'ros_port_mapping':'REGISTERED_ACTUAL','ros_domain_id':1000,'ros_registered_source':'synthetic-custom-mapping'})=='VALID'
 assert status({**actual(),'ros_domain_id':1,'ros_peer_domain_id':2})=='INVALID'
@pytest.mark.parametrize('name',['topic','/a/','/a//b','/1thing','/a/3b','/{thing}','/a-b','/a.b','/'+'a'*247])
def test_ros_actual_topic_name_constraints(name):assert status({**actual(),'ros_topic':name})=='INVALID'
def test_ros_valid_names_and_large_serialized_image_not_forced_udp_limit():
 assert status({**actual(),'ros_topic':'/_ns/topic_1','ros_serialized_bytes':24000000,'ros_serialized_bound_bytes':24000000,'payload_bytes':24000000})=='VALID'
 assert status({**actual(),'ros_serialized_bytes':10,'ros_serialized_bound_bytes':9})=='INVALID'
 assert status({**actual(),'ros_offered_durability':'PERSISTENT'})=='INVALID'
 assert status({**actual(),'ros_offered_liveliness':'MANUAL_BY_PARTICIPANT'})=='INVALID'
def accepted():
 x=actual();x.update(ros_value_accepted=True,ros_outcome='ACCEPTED',ros_type_match=True,ros_discovered=True,ros_mapping_valid=True,ros_actual_qos_resolved=True,
  ros_actual_qos_source='synthetic-readback',ros_interoperability_verified=True,ros_interoperability_source='synthetic-pairwise',ros_wave_source='synthetic-trace',ros_clock_source='synthetic-clock',ros_type_name='test/msg/Value',
  ros_qos_compatibility='OK',ros_compatibility_source='synthetic-check',ros_age_ms=3,ros_freshness_ms=10,ros_serialize_bound_ms=1,ros_transport_bound_ms=2,ros_executor_wait_bound_ms=3,ros_callback_bound_ms=4,ros_e2e_bound_ms=10,ros_e2e_limit_ms=10)
 return x
@pytest.mark.parametrize('bad',[{'ros_discovered':False},{'ros_outcome':'EXPIRED'},{'ros_actual_qos_resolved':False},{'ros_mapping_valid':False},{'ros_type_match':False},{'ros_interoperability_verified':False},{'ros_age_ms':11},{'ros_e2e_bound_ms':4},{'ros_e2e_limit_ms':9},{'ros_qos_compatibility':'WARNING'},{'ros_executor':'SINGLE_THREADED','ros_threads':2}])
def test_ros_message_acceptance_requires_take_and_callback_not_only_reliable_qos(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_ros_zenoh_type_hash_and_actual_interoperability_required():
 x={**accepted(),**zenoh(),'ros_qos_compatibility':'ZENOH_ACTUAL'};assert status(x)=='UNVERIFIED'
 x['ros_type_hash']='synthetic-actual-hash';assert status(x)=='VALID'
def test_ros_zero_copy_and_actions_not_inferred_from_topic_selection():
 for interface in('SERVICE_REQUEST','SERVICE_RESPONSE','ACTION_GOAL','ACTION_RESULT','ACTION_CANCEL','ACTION_FEEDBACK','ACTION_STATUS'):
  assert status({**actual(),'ros_interface':interface,'ros_transport':'INTRA_PROCESS'})=='VALID'
def test_ros_confirmed_custom_endpoint_qos_retained():
 x={**actual(),'ros_preset':'SENSOR_DATA','ros_offered_depth':20,'ros_offered_history':'KEEP_LAST','ros_offered_reliability':'RELIABLE'};before=deepcopy(x)
 assert status(x)=='VALID';assert x==before
