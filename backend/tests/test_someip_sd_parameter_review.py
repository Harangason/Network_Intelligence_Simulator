"""Independent SD lifetime/option/reboot/state boundaries for every exported field."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.someip_sd import rules as R

def actual():
 x={'sd_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(sd_edition='FO_R25_11',sd_proposal_mode='ACTUAL_CONFIG',sd_transport='UDP',sd_ip_version='IPV4',sd_role='SENDER',sd_relation='UNICAST',sd_entry='OFFER')
 return x

def status(x):return registry.validate_parameters('someip_sd',x)['status']

def test_sd_own_discovery_not_ethernet_rate_or_advertised_service_tcp():
 p=registry.profile('someip_sd');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert 'ethernet'not in p['default_stack']
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('someip_sd')};assert not set(R.REMOVED)&set(f)
 for k in('payload_bytes','sd_ttl_s','sd_multicast_address','sd_initial_min_ms','sd_repetitions_base_ms','sd_session_id','sd_endpoint_port'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('someip_sd'),ids=lambda f:f['key'])
def test_every_sd_field_type_and_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('k,v',[('transport','TCP'),('header_service_id',1),('header_method_id',2),('protocol_version',2),('interface_version',2),('message_type',32),('return_code',1),('client_id',7),('byte_order','LITTLE_ENDIAN'),('unicast_flag',False)])
def test_mandatory_sd_header_rules_not_application_interface_version(k,v):
 assert status({**actual(),'sd_'+k:v})=='INVALID'

def test_sender_wrap_and_initial_session_nonzero_per_relation():
 x={**actual(),'sd_wrapped_since_boot':False,'sd_reboot':True,'sd_relation_initial':True,'sd_session_id':1};assert status(x)=='VALID'
 assert status({**x,'sd_reboot':False})=='INVALID';assert status({**x,'sd_session_id':2})=='INVALID'
 x.update(sd_wrapped_since_boot=True,sd_relation_initial=False,sd_reboot=False,sd_session_id=65535);assert status(x)=='VALID'
 assert status({**x,'sd_reboot':True})=='INVALID'

@pytest.mark.parametrize('bad',[{'sd_reboot_detected':False},{'sd_session_id':11}])
def test_receiver_reboot_comparison_same_relation(bad):
 x={**actual(),'sd_role':'RECEIVER','sd_relation_initial':False,'sd_old_reboot':True,'sd_reboot':True,'sd_old_session_id':10,'sd_session_id':10,'sd_reboot_detected':True};assert status(x)=='VALID'
 assert status({**x,**bad})=='INVALID'
 assert status({**x,'sd_session_id':11,'sd_reboot_detected':False})=='VALID'
 assert status({**x,'sd_reboot':False,'sd_reboot_detected':False})=='VALID'
 assert status({**x,'sd_old_reboot':False,'sd_reboot_detected':False})=='INVALID'

def test_undefined_flags_sender_zero_receiver_ignored():
 assert status({**actual(),'sd_undefined_flags':1})=='INVALID'
 assert status({**actual(),'sd_role':'RECEIVER','sd_undefined_flags':63})=='VALID'

@pytest.mark.parametrize('entry,code',list(R.ENTRIES.items()))
def test_wire_entry_types_and_ttl_actions(entry,code):
 x={**actual(),'sd_entry':entry,'sd_entry_type':code,'sd_ttl_s':0 if entry in('STOP_OFFER','STOP_SUBSCRIBE','NACK','FIND') else 1};assert status(x)=='VALID'
 assert status({**x,'sd_entry_type':5})=='INVALID'
 if entry!='FIND':assert status({**x,'sd_ttl_s':1 if x['sd_ttl_s']==0 else 0})=='INVALID'

def test_find_ttl_ignored_wildcards_not_offer_or_subscribe():
 x={**actual(),'sd_entry':'FIND','sd_ttl_s':0,'sd_instance_id':65535,'sd_major':255,'sd_minor':4294967295};assert status(x)=='VALID'
 assert status({**x,'sd_ttl_s':16777215})=='VALID'
 assert status({**x,'sd_entry':'OFFER','sd_ttl_s':1})=='INVALID'
 assert status({**x,'sd_instance_id':0})=='INVALID'

@pytest.mark.parametrize('entry',['SUBSCRIBE','STOP_SUBSCRIBE','ACK','NACK'])
def test_subscription_entries_unicast_only_not_multicast_sd(entry):
 assert status({**actual(),'sd_entry':entry,'sd_relation':'MULTICAST'})=='INVALID'

def test_offer_lifetime_vs_cycle_and_expiry_except_until_reboot():
 x={**actual(),'sd_ttl_s':3,'sd_cyclic_offer_ms':3000,'sd_elapsed_lifetime_s':2.9};assert status(x)=='VALID'
 assert status({**x,'sd_cyclic_offer_ms':3001})=='INVALID'
 assert status({**x,'sd_elapsed_lifetime_s':3})=='INVALID'
 assert status({**x,'sd_ttl_s':16777215,'sd_elapsed_lifetime_s':20000000})=='VALID'

def body():return {**actual(),'sd_entries_count':1,'sd_entries_bytes':16,'sd_options_bytes':12,'sd_options_count':1,'sd_payload_bytes':40,'payload_bytes':40,'sd_length_bytes':48,'sd_message_bytes':56,'sd_udp_budget_bytes':56}

@pytest.mark.parametrize('bad',[{'sd_entries_bytes':15},{'sd_payload_bytes':28},{'payload_bytes':8},{'sd_length_bytes':56},{'sd_message_bytes':48},{'sd_udp_budget_bytes':55}])
def test_distinct_16byte_entries_12body_16header_lengths_and_udp_budget(bad):
 assert status(body())=='VALID';assert status({**body(),**bad})=='INVALID'

def test_no_fixed1400_discovery_payload_cap():
 x={**body(),'sd_options_bytes':2000,'sd_payload_bytes':2028,'payload_bytes':2028,'sd_length_bytes':2036,'sd_message_bytes':2044,'sd_udp_budget_bytes':3000};assert status(x)=='VALID'

@pytest.mark.parametrize('run',[1,2])
def test_empty_run_sender_index_zero_receiver_ignored_and_nonempty_bound(run):
 x={**actual(),'sd_count'+str(run):0,'sd_index'+str(run):0};assert status(x)=='VALID'
 assert status({**x,'sd_index'+str(run):255})=='INVALID'
 assert status({**x,'sd_role':'RECEIVER','sd_index'+str(run):255})=='VALID'
 x.update({'sd_options_count':5,'sd_count'+str(run):2,'sd_index'+str(run):3});assert status(x)=='VALID'
 assert status({**x,'sd_index'+str(run):4})=='INVALID'

@pytest.mark.parametrize('kind,code',list(R.OPTIONS.items()))
def test_each_known_option_code_length_and_discardability(kind,code):
 x={**actual(),'sd_option':kind,'sd_option_type':code}
 if kind=='IPV6_SD_ENDPOINT':x['sd_ip_version']='IPV6'
 if kind.startswith('IPV'):
  n=9 if kind.startswith('IPV4') else 21;x.update(sd_option_length=n,sd_option_bytes=n+3,sd_option_discardable=False)
  assert status({**x,'sd_option_discardable':True})=='INVALID'
 elif kind=='LOAD_BALANCING':x.update(sd_option_length=5,sd_option_bytes=8)
 assert status(x)=='VALID';assert status({**x,'sd_option_type':0})=='INVALID'
 if 'sd_option_length'in x:assert status({**x,'sd_option_length':x['sd_option_length']+1})=='INVALID'

@pytest.mark.parametrize('kind',['IPV4_SD_ENDPOINT','IPV6_SD_ENDPOINT'])
def test_sd_endpoint_first_unreferenced_family_match_sender(kind):
 x={**actual(),'sd_option':kind,'sd_option_index':0,'sd_option_referenced':False,'sd_ip_version':'IPV4'if kind.startswith('IPV4')else'IPV6','sd_endpoint_protocol':17,'sd_endpoint_transport':'UDP'};assert status(x)=='VALID'
 for bad in({'sd_option_index':1},{'sd_option_referenced':True},{'sd_ip_version':'IPV6'if kind.startswith('IPV4')else'IPV4'},{'sd_endpoint_transport':'TCP'},{'sd_endpoint_protocol':6}):assert status({**x,**bad})=='INVALID'

def test_advertised_service_tcp_option_not_discovery_tcp():
 x={**actual(),'sd_option':'IPV4_ENDPOINT','sd_endpoint_transport':'TCP','sd_endpoint_protocol':6,'sd_endpoint_port':1234};assert status(x)=='VALID'
 assert status({**x,'sd_transport':'TCP'})=='INVALID'
 assert status({**x,'sd_endpoint_protocol':17})=='INVALID'

def test_endpoint_addresses_use_ip_parser_instead_of_arbitrary_text():
 x={**actual(),'sd_endpoint_address':'192.0.2.2','sd_multicast_address':'239.1.2.3'};assert status(x)=='VALID'
 assert status({**x,'sd_endpoint_address':'synthetic-host'})=='INVALID'
 assert status({**x,'sd_multicast_address':'999.1.2.3'})=='INVALID'

@pytest.mark.parametrize('bad',[{'sd_endpoint_references':0},{'sd_endpoint_references':3},{'sd_multicast_references':1},{'sd_load_references':2}])
def test_offer_endpoint_and_option_reference_rules(bad):
 x={**actual(),'sd_endpoint_references':1,'sd_multicast_references':0,'sd_load_references':1};assert status(x)=='VALID'
 assert status({**x,**bad})=='INVALID'
 assert status({**x,'sd_entry':'FIND'})=='INVALID'

def test_delay_ranges_source_example100ms_not_universal_default():
 x={**actual(),'sd_initial_min_ms':5,'sd_initial_max_ms':20,'sd_initial_actual_ms':15,'sd_repetitions_max':3,'sd_phase':'REPETITION','sd_repetition_index':2,'sd_repetitions_base_ms':7,'sd_repetition_delay_ms':28};assert status(x)=='VALID'
 for bad in({'sd_initial_max_ms':4},{'sd_initial_actual_ms':21},{'sd_repetition_delay_ms':21},{'sd_repetition_index':3},{'sd_repetitions_max':0}):assert status({**x,**bad})=='INVALID'
 assert status({**actual(),'sd_phase':'MAIN','sd_entry':'FIND','sd_trigger':'CYCLIC'})=='INVALID'

def test_multicast_response_random_delay_not_unicast_answer_delay():
 x={**actual(),'sd_trigger':'MULTICAST_RESPONSE','sd_response_min_ms':10,'sd_response_max_ms':20,'sd_response_actual_ms':15};assert status(x)=='VALID'
 assert status({**x,'sd_response_actual_ms':9})=='INVALID'
 assert status({**x,'sd_trigger':'UNICAST_RESPONSE'})=='INVALID'
 assert status({**x,'sd_trigger':'UNICAST_RESPONSE','sd_response_actual_ms':0})=='VALID'

@pytest.mark.parametrize('threshold,n,delivery',[(0,10,'CLIENT_ENDPOINT'),(1,1,'SERVER_MULTICAST'),(3,2,'CLIENT_ENDPOINT'),(3,3,'SERVER_MULTICAST')])
def test_multicast_threshold_distinct_endpoint_count_not_raw_subscriptions(threshold,n,delivery):
 x={**actual(),'sd_multicast_threshold':threshold,'sd_subscribed_endpoints':n,'sd_event_delivery':delivery};assert status(x)=='VALID'
 assert status({**x,'sd_event_delivery':'CLIENT_ENDPOINT'if delivery=='SERVER_MULTICAST'else'SERVER_MULTICAST'})=='INVALID'

def test_finite_retry_cap_and_infinite_only_forever_offer():
 x={**actual(),'sd_retry_kind':'FINITE','sd_retry_max':2,'sd_retry_count':2,'sd_ttl_s':3};assert status(x)=='VALID'
 assert status({**x,'sd_retry_count':3})=='INVALID'
 assert status({**x,'sd_retry_kind':'INFINITE'})=='INVALID'
 assert status({**x,'sd_retry_kind':'INFINITE','sd_ttl_s':16777215})=='VALID'

def accepted():
 return {**body(),'sd_data_accepted':True,'sd_outcome':'ACCEPTED','sd_service_matches':True,'sd_options_verified':True,'sd_state_verified':True,'sd_resources_ready':True,'sd_header_service_id':65535,'sd_header_method_id':33024,'sd_protocol_version':1,'sd_interface_version':1,'sd_message_type':2,'sd_return_code':0,'sd_client_id':0,'sd_session_id':1,'sd_byte_order':'BIG_ENDIAN','sd_unicast_flag':True,'sd_entry_type':1,'sd_service_id':1,'sd_instance_id':2,'sd_major':3,'sd_ttl_s':5,'sd_elapsed_lifetime_s':1,'sd_relation_initial':True,'sd_reboot':True,'sd_observation_source':'synthetic-correlated-SD-state','sd_source_bound_ms':1,'sd_network_bound_ms':2,'sd_consumer_bound_ms':3,'sd_e2e_bound_ms':6,'sd_e2e_limit_ms':6,'sd_age_ms':1,'sd_freshness_ms':1}

@pytest.mark.parametrize('bad',[{'sd_resources_ready':False},{'sd_service_matches':False},{'sd_options_verified':False},{'sd_state_verified':False},{'sd_e2e_bound_ms':2},{'sd_e2e_limit_ms':5},{'sd_age_ms':2},{'sd_security_required':True,'sd_security_ready':False},{'sd_tcp_required':True,'sd_tcp_ready':False}])
def test_header_success_not_subscription_resource_security_or_full_timing_success(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'

def test_ack_tuple_counter_lifetime_must_match_subscription():
 x={**accepted(),'sd_entry':'ACK','sd_entry_type':7,'sd_eventgroup_id':4,'sd_counter':1,'sd_event_reserved12':0,'sd_expected_service_id':1,'sd_expected_instance_id':2,'sd_expected_major':3,'sd_expected_eventgroup_id':4,'sd_expected_counter':1,'sd_expected_ttl_s':5};assert status(x)=='VALID'
 for key,value in [('sd_counter',2),('sd_eventgroup_id',5),('sd_major',4),('sd_ttl_s',4)]:assert status({**x,key:value})=='INVALID'
 x.pop('sd_expected_counter');assert status(x)=='UNVERIFIED'

def test_confirmed_alternative_port_is_not_overwritten_by_source_proposal():
 x={**accepted(),'sd_proposal_mode':'SOURCE_PROPOSALS','sd_port':40000};before=deepcopy(x)
 assert status(x)=='VALID'and x==before
