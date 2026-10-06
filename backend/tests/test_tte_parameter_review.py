"""TTE traffic/role and source-identified device limits remain independent."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.tte import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():
 x={'tt_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(tt_review_profile='PUBLIC_REFERENCE',tt_traffic_class='BE');return x
def status(x):return registry.validate_parameters('tte',x)['status']
def test_tte_own_industry_neutral_profile_not_generic_safety_or_tsn():
 p=registry.profile('tte');assert p['domain']=='generic_networking'and p['default_stack']==['tte']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':1000000000},{'mtu_bytes':1500},{'retry_limit':3},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('tte',1500,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('tte'),ids=lambda f:f['key'])
def test_every_tte_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('profile,rate',[('TTTECH_CONTROLLER_SPACE_2016',10000000),('TTTECH_CONTROLLER_SPACE_2016',1000000000),('TTTECH_PMC_2026',100000000)])
def test_literature_product_rates_only_identified_device(profile,rate):
 x={**actual(),'tt_device_profile':profile,'tt_device_source':'synthetic','tt_link_bps':rate,'tt_channels':3,'tt_full_duplex':True};assert status(x)=='VALID'
 for bad in({'tt_link_bps':115200},{'tt_channels':4},{'tt_full_duplex':False}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tt_device_profile':'REGISTERED_ACTUAL','tt_link_bps':10000000000})=='VALID'
def test_pmc_no_10m_and_old_rmii_no_1g():
 assert status({**actual(),'tt_device_profile':'TTTECH_PMC_2026','tt_device_source':'synthetic','tt_link_bps':10000000})=='INVALID'
 assert status({**actual(),'tt_device_profile':'TTTECH_CONTROLLER_SPACE_2016','tt_device_source':'synthetic','tt_phy_interface':'RMII','tt_link_bps':1000000000})=='INVALID'
@pytest.mark.parametrize('field,maximum',[('send_vls',128),('receive_vls',256),('partitions',8),('send_com_ports',1024),('receive_com_ports',2048)])
def test_2016_controller_limits_not_every_new_device(field,maximum):
 x={**actual(),'tt_device_profile':'TTTECH_CONTROLLER_SPACE_2016','tt_device_source':'synthetic','tt_'+field:maximum};assert status(x)=='VALID'
 assert status({**x,'tt_'+field:maximum+1})=='INVALID'
 assert status({**x,'tt_device_profile':'REGISTERED_ACTUAL','tt_'+field:maximum+1})=='VALID'
def timed():return {**actual(),'tt_traffic_class':'TT','tt_integration_us':1000,'tt_integration_cycles':10,'tt_cluster_us':10000,'tt_period_us':2000,'tt_phase_us':100,'tt_offset_us':100,'tt_slot_end_us':110,'tt_serialization_us':8,'tt_guard_us':2,'tt_clock_error_us':1,'tt_precision_us':1,'tt_clock_source':'synthetic','tt_membership_source':'synthetic','tt_vl_id':'synthetic','tt_path_id':'synthetic','tt_schedule_revision':'synthetic','tt_sync_role':'SC'}
def test_tt_cluster_equal_integration_cycles_and_dispatch_phase():
 x=timed();assert status(x)=='VALID'
 for bad in({'tt_cluster_us':1000},{'tt_integration_us':0},{'tt_period_us':0},{'tt_phase_us':2000}):assert status({**x,**bad})=='INVALID'
def test_every_link_interval_fits_serialization_guard_and_cluster():
 x=timed();assert status(x)=='VALID'
 for bad in({'tt_slot_end_us':109},{'tt_slot_end_us':10001},{'tt_guard_us':.5},{'tt_clock_error_us':2}):assert status({**x,**bad})=='INVALID'
def test_tt_needs_clock_membership_and_schedule_not_progresscard():
 for k in ('tt_membership_source','tt_clock_source','tt_slot_end_us','tt_schedule_revision'):
  x=timed();x.pop(k);assert status(x)=='UNVERIFIED'
 assert status({**timed(),'tt_sync_role':'NONE'})=='INVALID'
def test_sm_cm_role_not_forced_to_specific_physical_device_class():
 for role in('SM','CM','SC'):
  assert status({**timed(),'tt_sync_role':role})=='VALID'
def test_permanence_wait_reception_actual_transit_and_maximum():
 x={**actual(),'tt_actual_delay_us':30,'tt_maximum_delay_us':100,'tt_added_delay_us':70,'tt_rx_time_us':-5,'tt_permanence_us':65};assert status(x)=='VALID'
 for bad in({'tt_actual_delay_us':101},{'tt_added_delay_us':100},{'tt_permanence_us':100}):assert status({**x,**bad})=='INVALID'
 x.pop('tt_actual_delay_us');assert status(x)=='UNVERIFIED'
def test_pcf_and_fault_claim_need_independent_sources_not_fixed_sm_counts():
 assert status({**actual(),'tt_pcf_type':'IN'})=='UNVERIFIED'
 assert status({**actual(),'tt_pcf_type':'IN','tt_pcf_source':'synthetic'})=='VALID'
 assert status({**actual(),'tt_fault_tolerance_claimed':True})=='UNVERIFIED'
 assert status({**actual(),'tt_fault_tolerance_claimed':True,'tt_fault_profile':'DUAL_OMISSION','tt_fault_source':'synthetic','tt_sync_masters':6,'tt_compression_masters':6})=='VALID'
def test_rc_not_tt_period_and_requires_own_bag_jitter_queue_codec():
 x={**actual(),'tt_traffic_class':'RC'};assert status(x)=='UNVERIFIED'
 x.update(tt_rc_profile='ARINC664P7_BOUND_ACTUAL',tt_rc_source='synthetic',tt_rc_bag_us=1000,tt_rc_jitter_us=20,tt_rc_queue_us=300);assert status(x)=='VALID'
 assert status({**x,'tt_rc_bag_us':0})=='INVALID'
def test_be_default_has_no_guaranteed_bound_without_extra_source():
 assert status({**actual(),'tt_transport_ms':1})=='UNVERIFIED'
 assert status({**actual(),'tt_transport_ms':1,'tt_be_bound_source':'synthetic'})=='VALID'
def test_whole_wire_serialization_and_peer_cap_distinct_payload():
 x={**actual(),'tt_frame_bytes':64,'tt_wire_bytes':84,'tt_link_bps':100000000,'tt_serialization_us':6.72,'tt_peer_frame_max':1500};assert status(x)=='VALID'
 for bad in({'tt_serialization_us':5.12},{'tt_wire_bytes':63},{'tt_peer_frame_max':63}):assert status({**x,**bad})=='INVALID'
def test_full_network_plus_node_acceptance_not_sae_scope_only():
 x={**timed(),'tt_source_ms':1,'tt_transport_ms':2,'tt_consumer_ms':3,'tt_e2e_ms':6,'tt_deadline_ms':6,'tt_age_ms':5,'tt_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'tt_e2e_ms':2},{'tt_deadline_ms':5},{'tt_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 x.update(tt_data_accepted=True);assert status(x)=='UNVERIFIED'
 x.update(tt_observation_source='synthetic',tt_host_source='synthetic',tt_path_verified=True,tt_host_verified=True,tt_clock_verified=True,tt_schedule_verified=True,tt_tt_nonoverlap_verified=True,tt_sync_state='SYNCHRONIZED',tt_outcome='ACCEPTED');assert status(x)=='VALID'
 for bad in({'tt_host_verified':False},{'tt_sync_state':'INTEGRATING'},{'tt_tt_nonoverlap_verified':False}):assert status({**x,**bad})=='INVALID'
def test_minimum_product_mode_proposals_not_fixed_protocol_cycles():
 f={v['key']:v for v in registry.parameter_fields('tte')}
 assert [p['value']for p in f['tt_link_bps']['conditional_defaults']]==[10000000,100000000]
 for k in('tt_integration_us','tt_integration_cycles','tt_precision_us','tt_sync_masters','tt_compression_masters','tt_startup_us','tt_vl_id','tt_period_us','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
def test_registered_standard_requires_own_source_not_old_research_proof():
 assert status({**actual(),'tt_review_profile':'REGISTERED_ACTUAL','tt_registered_source':'synthetic','tt_channels':10})=='UNVERIFIED'
