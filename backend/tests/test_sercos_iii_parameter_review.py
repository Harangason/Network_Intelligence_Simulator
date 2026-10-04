"""Individual SercosIII cycle/phase/RTC-UCC/device conditions."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.sercos_iii import rules as R
def actual():
 x={'sercos_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(sercos_profile='PUBLIC_SERIII_REFERENCE',sercos_proposal_mode='ACTUAL_CONFIG',sercos_phase='CP4',sercos_topology='LINE',sercos_role='MASTER',sercos_channel='REAL_TIME',sercos_mechanism='M_S',sercos_telegram='MDT')
 return x
def status(x):return registry.validate_parameters('sercos_iii',x)['status']
def test_seriii_own_cycle_not_seri_ii_or_generic_ethernet_queue():
 p=registry.profile('sercos_iii');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('sercos_iii')};assert not set(R.REMOVED)&set(f)
 for k in('sercos_ring_delay_ns','sercos_phase','sercos_ucc_mtu_bytes','sercos_allowed_mst_losses','sercos_age_ns'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('sercos_iii'),ids=lambda f:f['key'])
def test_every_field_type_and_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('ns',[31250,62500,125000,250000,750000,1250000,65000000])
def test_exact_public_cycle_series(ns):
 assert status({**actual(),'sercos_cycle_ns':ns})=='VALID'
 assert status({**actual(),'sercos_cycle_ns':ns+1})=='INVALID'
def test_hilscher_master_minimum250us_not_all_protocol31_25us():
 x={**actual(),'sercos_profile':'HILSCHER_V2_1','sercos_cycle_ns':250000};assert status(x)=='VALID'
 assert status({**x,'sercos_cycle_ns':125000})=='INVALID'
 assert status({**actual(),'sercos_cycle_ns':125000,'sercos_slave_min_ns':250000})=='INVALID'
 assert status({**actual(),'sercos_cycle_ns':125000,'sercos_master_min_ns':250000})=='INVALID'
def test_seriii100mfull_not_other_ethernet_or_serii16m():
 x={**actual(),'sercos_link_bps':100000000,'sercos_duplex':'FULL'};assert status(x)=='VALID'
 for rate in(16000000,1000000000):assert status({**x,'sercos_link_bps':rate})=='INVALID'
 assert status({**x,'sercos_duplex':'HALF'})=='INVALID'
def telegram(data=40):
 return {**actual(),'sercos_data_bytes':data,'sercos_hotplug_bytes':0,'sercos_svc_bytes':6,'sercos_rtd_bytes':30,'sercos_padding_bytes':data-36,'sercos_occupancy_bytes':data+44,'sercos_link_bps':100000000,'sercos_wire_ns':(data+44)*80,'sercos_ethertype':0x88CD,'sercos_mdt_count':1,'sercos_at_count':1,'sercos_telegram_index':0,'sercos_connection_offset_bytes':2,'sercos_connection_bytes':28}
@pytest.mark.parametrize('data',[40,1494])
def test_full_aggregate_telegram_and_44byte_wire_management(data):
 x=telegram(data);assert status(x)=='VALID'
 for bad in({'sercos_data_bytes':data+1},{'sercos_occupancy_bytes':data+40},{'sercos_wire_ns':(data+40)*80},{'sercos_connection_bytes':29},{'sercos_ethertype':0x88BA}):assert status({**x,**bad})=='INVALID'
def test_one_telegram_index_not_device_or_channel_address():
 x=telegram();assert status(x)=='VALID';assert status({**x,'sercos_telegram_index':1})=='INVALID'
 x.update(sercos_mdt_count=4,sercos_telegram_index=3);assert status(x)=='VALID'
 assert status({**x,'sercos_mdt_count':5})=='INVALID'
def schedule():
 return {**telegram(),'sercos_cycle_ns':250000,'sercos_mdt_occupancy_sum':84,'sercos_at_occupancy_sum':84,'sercos_cycle_wire_ns':13440,'sercos_ring_delay_ns':1000,'sercos_guard_ns':560,'sercos_rt_end_ns':15000}
@pytest.mark.parametrize('bad',[{'sercos_mdt_occupancy_sum':83},{'sercos_at_occupancy_sum':1539},{'sercos_cycle_wire_ns':6720},{'sercos_rt_end_ns':14999},{'sercos_rt_end_ns':250001}])
def test_all_mdt_at_wire_path_guard_schedule_not_one_message_load(bad):
 assert status(schedule())=='VALID';assert status({**schedule(),**bad})=='INVALID'
def ucc():
 return {**schedule(),'sercos_profile':'HILSCHER_V2_1','sercos_ucc_enabled':True,'sercos_t6_ns':15000,'sercos_t7_ns':21720,'sercos_ucc_window_ns':6720,'sercos_ucc_mtu_bytes':46}
@pytest.mark.parametrize('bad',[{'sercos_t6_ns':0},{'sercos_t6_ns':14999},{'sercos_t7_ns':21719,'sercos_ucc_window_ns':6719},{'sercos_ucc_mtu_bytes':47},{'sercos_t7_ns':250001},{'sercos_ucc_mtu_bytes':1501}])
def test_hilscher_minimum6720ns_ucc_and_mtu_must_fit_actual_window(bad):
 assert status(ucc())=='VALID';assert status({**ucc(),**bad})=='INVALID'
def test_ucc_ethernet_separate_from_rtc_no88cd_or_mdt_assumption():
 x={**actual(),'sercos_channel':'UCC','sercos_mechanism':'OTHER_ETHERNET','sercos_telegram':'UCC_FRAME','sercos_ethertype':0x0800};assert status(x)=='UNVERIFIED'
 x.update(sercos_ucc_protocol_source='synthetic-ipv4-path');assert status(x)=='VALID'
 assert status({**x,'sercos_ethertype':0x88CD})=='INVALID'
 assert status({**x,'sercos_telegram':'MDT'})=='INVALID'
@pytest.mark.parametrize('key',['t1_ns','t3_ns','t6_ns','t7_ns'])
def test_selected_hilscher_timing_offsets_bound_by_cycle(key):
 x={**actual(),'sercos_profile':'HILSCHER_V2_1','sercos_cycle_ns':250000,'sercos_'+key:250000};assert status(x)=='VALID'
 assert status({**x,'sercos_'+key:250001})=='INVALID'
def test_feedback_capture_uses_processing_period_and_sync_jitter_own_bound():
 x={**actual(),'sercos_profile':'HILSCHER_V2_1','sercos_cycle_ns':250000,'sercos_process_cycle_ns':1000000,'sercos_sync_time_ns':1000000,'sercos_sync_jitter_ns':125000};assert status(x)=='VALID'
 assert status({**x,'sercos_sync_time_ns':1000001})=='INVALID'
 assert status({**x,'sercos_sync_jitter_ns':125001})=='INVALID'
@pytest.mark.parametrize('key',['process_input_bytes','process_output_bytes'])
def test_hilscher_process_image_even_5760_not_generic_app_packet_limit(key):
 x={**actual(),'sercos_profile':'HILSCHER_V2_1','sercos_'+key:5760};assert status(x)=='VALID'
 for v in(5761,5759):assert status({**x,'sercos_'+key:v})=='INVALID'
 assert status({**x,'sercos_profile':'PUBLIC_SERIII_REFERENCE','sercos_'+key:6000})=='VALID'
def test_hilscher_slave_and_cp0_stability_values_vendor_scoped():
 x={**actual(),'sercos_profile':'HILSCHER_V2_1','sercos_slave_count':511,'sercos_cp0_wait_cycles':100};assert status(x)=='VALID'
 assert status({**x,'sercos_slave_count':512})=='INVALID';assert status({**x,'sercos_cp0_wait_cycles':99})=='INVALID'
def accepted():
 return {**schedule(),'sercos_data_accepted':True,'sercos_outcome':'ACCEPTED','sercos_phase_ready':True,'sercos_producer_ready':True,'sercos_mapping_valid':True,'sercos_schedule_verified':True,'sercos_clock_verified':True,'sercos_duplex':'FULL','sercos_master_min_ns':250000,'sercos_slave_min_ns':250000,'sercos_purpose':'OPERATIONAL','sercos_observation_source':'synthetic-allport-trace','sercos_allowed_mst_losses':2,'sercos_connection_loss_limit':1,'sercos_observed_mst_losses':0,'sercos_source_bound_ns':100000,'sercos_network_bound_ns':15000,'sercos_consumer_bound_ns':100000,'sercos_e2e_bound_ns':215000,'sercos_e2e_limit_ns':215000,'sercos_age_ns':200000,'sercos_freshness_ns':250000}
@pytest.mark.parametrize('bad',[{'sercos_phase':'CP3'},{'sercos_phase':'CP0'},{'sercos_phase':'NRT'},{'sercos_phase_ready':False},{'sercos_producer_ready':False},{'sercos_observed_mst_losses':3},{'sercos_allowed_mst_losses':1},{'sercos_e2e_bound_ns':6720},{'sercos_e2e_limit_ns':214999},{'sercos_age_ns':250001}])
def test_cp3_zero_data_rate_or_partial_wiretime_not_operational_acceptance(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_safety_container_requires_independent_safety_assurance():
 x={**accepted(),'sercos_mechanism':'SAFETY'};assert status(x)=='UNVERIFIED'
 x.update(sercos_safety_source='synthetic-independent-safety-case',sercos_safety_verified=True);assert status(x)=='VALID'
 assert status({**x,'sercos_safety_verified':False})=='INVALID'
def test_source_minimum_proposals_preserve_confirmed_supported_slower_cycle():
 x={**accepted(),'sercos_cycle_ns':1000000,'sercos_proposal_mode':'SOURCE_MINIMUM_PROPOSALS'};before=deepcopy(x)
 assert status(x)=='VALID'and x==before
