"""TSN selected toolsets and independently commissioned perhop configuration."""
import json
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.tsn import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():
 x={'tn_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(tn_review_profile='IEEE_PUBLIC_MODELS',tn_mapping='IEEE_YANG');return x
def status(x):return registry.validate_parameters('tsn',x)['status']
def test_tsn_own_tools_not_automatic_1g_1500_or_safety():
 p=registry.profile('tsn');assert p['domain']=='generic_networking'and p['default_stack']==['tsn']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':1000000000},{'mtu_bytes':1500},{'retry_limit':3},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('tsn',1500,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('tsn'),ids=lambda f:f['key'])
def test_every_tsn_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
def schedule(mapping='LINUX_IPROUTE2_6_17'):
 return {**actual(),'tn_mapping':mapping,'tn_gate_enabled':True,'tn_gcl_json':json.dumps([dict(index=2,operation='S',mask=1,interval_ns=10000),dict(index=9,operation='S',mask=2,interval_ns=10000)]),'tn_gcl_sum_ns':20000,'tn_cycle_numerator':1,'tn_cycle_denominator':50000,'tn_cycle_ns':20000,'tn_supported_cycle_ns':30000,'tn_supported_list_max':2,'tn_supported_interval_max_ns':15000,'tn_base_seconds':1,'tn_base_nanoseconds':0}
def test_nonconsecutive_gate_indexes_allowed_but_duplicate_no():
 x=schedule();assert status(x)=='VALID'
 entries=json.loads(x['tn_gcl_json']);entries[1]['index']=2
 assert status({**x,'tn_gcl_json':json.dumps(entries)})=='INVALID'
def test_full_gate_table_typed_mask_intervals_hardware_limits_and_sum():
 x=schedule();assert status(x)=='VALID'
 for bad in({'tn_supported_list_max':1},{'tn_supported_interval_max_ns':9999},{'tn_gcl_sum_ns':19999},{'tn_cycle_ns':30000},{'tn_supported_cycle_ns':19999}):assert status({**x,**bad})=='INVALID'
 for field,value in [('mask',65536),('mask',True),('interval_ns',-1),('interval_ns',True),('operation','Z'),('index',-1)]:
  entries=json.loads(x['tn_gcl_json']);entries[0][field]=value
  assert status({**x,'tn_gcl_json':json.dumps(entries)})=='INVALID'
 for text in('[]','{}','[{"index":0,"operation":"S","mask":1,"mask":2,"interval_ns":20}]','[{"index":0,"operation":"S","mask":1,"interval_ns":20,"invented":1}]'):
  assert status({**x,'tn_gcl_json':text})=='INVALID'
def test_cycle_rational_and_tenth_ns_tick_units_not_millisecond_defaults():
 x={**actual(),'tn_cycle_numerator':1,'tn_cycle_denominator':100000,'tn_cycle_ns':10000,'tn_tick_tenths_ns':25,'tn_tick_ns':2.5};assert status(x)=='VALID'
 for bad in({'tn_cycle_denominator':0},{'tn_cycle_ns':1},{'tn_tick_ns':25}):assert status({**x,**bad})=='INVALID'
def test_known_scheduling_needs_hardware_and_source_not_only_flag():
 x={**actual(),'tn_gate_enabled':True};assert status(x)=='UNVERIFIED'
 x=schedule();x.pop('tn_supported_list_max');assert status(x)=='UNVERIFIED'
def test_zero_queue_max_sdu_inherits_actual_mac_not_zero_capacity():
 x={**actual(),'tn_queue_max_sdu':0,'tn_mac_max_sdu':1500};assert status(x)=='VALID'
 assert status({**x,'tn_queue_max_sdu':1501})=='INVALID'
 assert status({**x,'tn_queue_max_sdu':1000})=='VALID'
def test_linux_full_offload_requires_phc_and_no_clockid_flags_three_invalid():
 x={**actual(),'tn_mapping':'LINUX_IPROUTE2_6_17','tn_taprio_flags':2};assert status(x)=='UNVERIFIED'
 x['tn_phc_source']='synthetic';assert status(x)=='VALID'
 assert status({**x,'tn_clockid':'CLOCK_TAI'})=='INVALID'
 assert status({**x,'tn_taprio_flags':3})=='INVALID'
def test_txtime_delay_strictly_exceeds_etf_delta():
 x={**actual(),'tn_mapping':'LINUX_IPROUTE2_6_17','tn_taprio_flags':1,'tn_txtime_delay_ns':1001,'tn_etf_delta_ns':1000};assert status(x)=='VALID'
 assert status({**x,'tn_txtime_delay_ns':1000})=='INVALID'
def cbs():return {**actual(),'tn_cbs_enabled':True,'tn_cbs_model':'SIMPLE_ANNEX_L','tn_cbs_source':'synthetic','tn_srp_active':False,'tn_link_bps':1000000000,'tn_admin_idle_bps':20000000,'tn_idle_bps':20000000,'tn_send_bps':-980000000,'tn_max_interference_bytes':1500,'tn_max_frame_bytes':1500,'tn_hi_credit_bytes':30,'tn_lo_credit_bytes':-1470}
def test_linux16class_mapping_not_ieee8bit_table_or_complex_cbs():
 x=schedule();entries=json.loads(x['tn_gcl_json']);entries[0]['mask']=256;x['tn_gcl_json']=json.dumps(entries);x['tn_traffic_class']=8
 assert status(x)=='VALID'
 assert status({**x,'tn_mapping':'IEEE_YANG'})=='INVALID'
 assert status({**cbs(),'tn_cbs_model':'REGISTERED_ACTUAL','tn_hi_credit_bytes':31})=='VALID'
def test_cbs_signed_credit_equations_whole_wire_scope_and_srp():
 x=cbs();assert status(x)=='VALID'
 for bad in({'tn_send_bps':980000000},{'tn_hi_credit_bytes':0},{'tn_lo_credit_bytes':0},{'tn_admin_idle_bps':10}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tn_srp_active':True,'tn_admin_idle_bps':10})=='VALID'
 x['tn_idle_bps']=0;x['tn_admin_idle_bps']=0;x['tn_send_bps']=-1000000000;x['tn_hi_credit_bytes']=0;x['tn_lo_credit_bytes']=-1500;assert status(x)=='VALID'
def test_psfp_meter_presence_color_coupling_burst_octets_not_ats_bits():
 x={**actual(),'tn_psfp_enabled':True,'tn_psfp_source':'synthetic','tn_stream_sdu_max':1500,'tn_meter_enabled':True};assert status(x)=='UNVERIFIED'
 x.update(tn_cir_bps=1000000,tn_eir_bps=0,tn_cbs_octets=1000,tn_ebs_octets=0,tn_color_mode='COLOR_AWARE',tn_coupling='ZERO',tn_drop_on_yellow=True);assert status(x)=='VALID'
 assert status({**x,'tn_color_mode':'CAN_PRIORITY'})=='INVALID'
 assert status({**x,'tn_coupling':'TWO'})=='INVALID'
 assert status({**x,'tn_cbs_octets':1000.5})=='INVALID'
def test_preemption_guard_actual_mac_and_relative_clock_evidence():
 x={**actual(),'tn_preemption_enabled':True,'tn_preemption_source':'synthetic','tn_hold_advance_ns':100,'tn_release_advance_ns':120,'tn_fragment_block_ns':700,'tn_preemption_active':True,'tn_clock_error_ns':50,'tn_guard_ns':750};assert status(x)=='VALID'
 assert status({**x,'tn_guard_ns':749})=='INVALID'
 x.update(tn_preemption_enabled=False,tn_serialization_ns=12304,tn_guard_ns=12354);assert status(x)=='VALID'
 assert status({**x,'tn_guard_ns':750})=='INVALID'
def test_scheduling_window_must_fit_whole_serialization_and_guard():
 x={**schedule(),'tn_serialization_ns':1000,'tn_guard_ns':100,'tn_gate_open_ns':1100};assert status(x)=='VALID'
 assert status({**x,'tn_gate_open_ns':1099})=='INVALID'
def test_ats_asynchronous_does_not_require_ptp_but_own_group_and_timing():
 x={**actual(),'tn_ats_enabled':True,'tn_sync_required':False};assert status(x)=='UNVERIFIED'
 x.update(tn_ats_source='synthetic',tn_ats_cir_bps=1000000,tn_ats_burst_bits=8000,tn_ats_group_id=1,tn_ats_residence_ns=100000,tn_ats_processing_min_ns=1,tn_ats_processing_max_ns=2,tn_ats_clock_variation_ns=100,tn_ats_rate_deviation_ppm=10,tn_ats_recognition_ns=100);assert status(x)=='VALID'
 assert status({**x,'tn_ats_processing_min_ns':3})=='INVALID'
def test_nxp_cqf_multiple_only_for_selected_implementation():
 x={**actual(),'tn_cqf_enabled':True,'tn_cqf_profile':'NXP_RTE_2_3','tn_cqf_source':'synthetic','tn_cqf_cycle_ns':10000,'tn_cqf_gate_ns':2000};assert status(x)=='VALID'
 assert status({**x,'tn_cqf_cycle_ns':10001})=='INVALID'
 assert status({**x,'tn_cqf_profile':'REGISTERED_ACTUAL','tn_cqf_cycle_ns':10001})=='VALID'
def test_frer_vector_history_match_scope_latent_and_invalid_sequence():
 x={**actual(),'tn_recovery_algorithm':'VECTOR','tn_frer_history':2,'tn_frer_history_max':4,'tn_sequence_space':65536,'tn_invalid_sequence':65536};assert status(x)=='VALID'
 for bad in({'tn_frer_history':1},{'tn_frer_history':5},{'tn_invalid_sequence':65535}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tn_recovery_algorithm':'MATCH','tn_frer_history':1})=='VALID'
 assert status({**actual(),'tn_frer_individual':True,'tn_frer_latent':True})=='INVALID'
def test_frer_latent_sources_and_independent_configured_paths():
 x={**actual(),'tn_frer_enabled':True,'tn_frer_source':'synthetic','tn_recovery_algorithm':'VECTOR','tn_frer_reset_ms':100,'tn_sequence_space':65536,'tn_frer_latent':True};assert status(x)=='UNVERIFIED'
 x.update(tn_frer_paths=3,tn_frer_difference=1,tn_frer_period_ms=2000,tn_frer_reset_period_ms=30000);assert status(x)=='VALID'
def test_gptp_management_current_log_and_scaled_ratio():
 x={**actual(),'tn_use_mgt_sync':True,'tn_mgt_log_sync':-3,'tn_current_log_sync':-3,'tn_sync_interval_s':.125,'tn_neighbor_ratio_scaled':0,'tn_neighbor_ratio':1};assert status(x)=='VALID'
 for bad in({'tn_current_log_sync':-2},{'tn_sync_interval_s':3},{'tn_neighbor_ratio':0}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tn_use_mgt_sync':False,'tn_mgt_log_sync':-2})=='VALID'
def test_started_cnc_or_pending_admin_never_functional_acceptance():
 x={**actual(),'tn_source_ms':1,'tn_transport_ms':2,'tn_consumer_ms':3,'tn_e2e_ms':6,'tn_deadline_ms':6,'tn_age_ms':5,'tn_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'tn_e2e_ms':3},{'tn_deadline_ms':5},{'tn_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 x.update(tn_data_accepted=True,tn_observation_source='synthetic',tn_stream_id='synthetic',tn_reservation_source='synthetic',tn_path_verified=True,tn_stream_status='READY',tn_config_pending=False,tn_outcome='ACCEPTED');assert status(x)=='VALID'
 assert status({**x,'tn_stream_status':'STARTED'})=='INVALID'
 assert status({**x,'tn_config_pending':True})=='INVALID'
 assert status({**x,'tn_sync_required':True})=='UNVERIFIED'
def test_source_defaults_only_declared_management_values():
 f={v['key']:v for v in registry.parameter_fields('tsn')}
 assert f['tn_gate_enabled']['conditional_defaults'][0]['value']is False
 assert f['tn_admin_gate_states']['conditional_defaults'][0]['value']==255
 assert f['tn_queue_max_sdu']['conditional_defaults'][0]['value']==0
 assert f['tn_preemption_status']['conditional_defaults'][0]['value']=='EXPRESS'
 for k in('tn_cycle_ns','tn_guard_ns','tn_clock_error_ns','tn_link_bps','tn_gcl_json','tn_base_seconds','tn_hold_advance_ns','tn_frer_reset_ms','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
def test_registered_toolset_not_false_ieee_cap():
 assert status({**actual(),'tn_review_profile':'REGISTERED_ACTUAL','tn_registered_source':'synthetic','tn_admin_gate_states':65535})=='UNVERIFIED'
