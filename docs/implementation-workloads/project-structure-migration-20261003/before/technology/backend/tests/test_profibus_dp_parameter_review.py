"""DP source-qualified timing and device evidence remain separate from PA/CAN."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profibus_dp as P
def actual():
 x={'dp_'+k:'synthetic-'+k for k in P.REQUIRED}
 x.update(bitrate_bps=9600,dp_version='V0',dp_parameter_set='ABB_CM592_AB281',dp_phy='RS485_TYPE_A',dp_role='SLAVE',dp_rate_agreed=True)
 return x
def status(x):return registry.validate_parameters('profibus_dp',x)['status']
def test_dp_profile_own_fdl_path_and_no_foreign_defaults():
 p=registry.profile('profibus_dp');assert p['default_stack']==['profibus_dp']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'
 f=registry.parameter_fields('profibus_dp');keys=[v['key']for v in f];assert len(keys)==len(set(keys))and not set(keys)&set(P.REMOVED)
 for bad in({'mtu_bytes':1500},{'nominal_bitrate_bps':500000},{'bitrate_bps':100000000},{'dp_rate_agreed':False}):
  assert status({**actual(),**bad})=='INVALID'
 assert status({'bitrate_bps':9600})=='UNVERIFIED'
@pytest.mark.parametrize('field',registry.parameter_fields('profibus_dp'),ids=lambda f:f['key'])
def test_dp_every_declared_field_type_and_outer_bound(field):
 k='bitrate_bps'if field['key']=='bitrate'else field['key']
 assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
def test_dp_source_proposals_and_unknown_devices_are_distinct():
 f={v['key']:v for v in registry.parameter_fields('profibus_dp')};assert f['bitrate']['default']==9600
 for k,val in P.DEFAULTS.items():assert f['dp_'+k]['default']==val and f['dp_'+k]['default_status']=='PROPOSED'
 for k in('station','master_station','target_rotation_bits','input_bytes','output_bytes','watchdog_ms','scan_interval_us','poll_timeout_ms'):
  assert 'default'not in f['dp_'+k]
 for k,values in P.SAIA_DEFAULTS.items():
  variants=f['dp_'+k]['conditional_defaults'];assert [v['value']for v in variants]==values
  assert [v['when']['bitrate_bps']for v in variants]==P.SAIA_RATES
@pytest.mark.parametrize('rate',P.RATES)
def test_dp_actual_all_listed_rates(rate):assert status({**actual(),'bitrate_bps':rate})=='VALID'
def test_dp_hsa_only_active_not_passive_slave_ceiling():
 x={**actual(),'dp_station':120,'dp_hsa':10,'dp_active_max_station':10,'dp_master_station':5,'dp_active_masters':2,'dp_token_holders':1}
 assert status(x)=='VALID'
 assert status({**x,'dp_role':'DPM1'})=='INVALID'
 assert status({**x,'dp_active_max_station':11})=='INVALID'
 assert status({**x,'dp_token_holders':2})=='INVALID'
 assert status({**x,'dp_state':'DATA_EXCHANGE','dp_station':126})=='INVALID'
@pytest.mark.parametrize('rate,limit',[(9600,1200),(45450,1200),(187500,1000),(500000,400),(1500000,200),(12000000,100)])
def test_dp_type_a_rate_dependent_lengths_and_repeater_loads(rate,limit):
 x={**actual(),'bitrate_bps':rate,'dp_cable_m':limit,'dp_segment_stations':31,'dp_repeater_loads':1,'dp_segment_loads':32,
  'dp_terminations':2,'dp_termination_powered':True,'dp_capacitance_pf_m':29.9}
 assert status(x)=='VALID'
 for bad in({'dp_cable_m':limit+.1},{'dp_segment_stations':32},{'dp_segment_loads':33},{'dp_terminations':1},
  {'dp_termination_powered':False},{'dp_capacitance_pf_m':30},{'dp_phy':'OPTICAL_REGISTERED','dp_registered_source':'synthetic-optics'}):
  assert status({**x,**bad})=='INVALID'
def test_dp_cyclic_input_output_and_gsd_mapping_separate():
 x={**actual(),'dp_input_bytes':244,'dp_output_bytes':244,'dp_device_input_max':244,'dp_device_output_max':244,
  'dp_mapped_input_bytes':244,'dp_mapped_output_bytes':244,'dp_ident_number':123,'dp_expected_ident_number':123,'payload_bytes':488}
 assert status(x)=='VALID'
 for bad in({'dp_device_input_max':243},{'dp_output_bytes':245},{'dp_mapped_output_bytes':243},{'dp_expected_ident_number':124}):
  assert status({**x,**bad})=='INVALID'
def test_dp_fdl_length_extensions_not_can_or_ethernet():
 x={**actual(),'dp_frame':'SD2','dp_service':'ACYCLIC','dp_version':'V1','dp_supports_v1':True,'dp_user_bytes':244,
  'dp_address_extension_bytes':2,'dp_data_unit_bytes':246,'dp_le':249,'dp_le_repeat':249,'dp_frame_bytes':255,'dp_wire_bits':2805}
 assert status(x)=='VALID'
 for bad in({'dp_le_repeat':248},{'dp_data_unit_bytes':245},{'dp_frame_bytes':253},{'dp_wire_bits':2040},{'dp_service':'CYCLIC'}):
  assert status({**x,**bad})=='INVALID'
 x.update(dp_service='CYCLIC',dp_address_extension_bytes=0,dp_data_unit_bytes=244,dp_le=247,dp_le_repeat=247,dp_frame_bytes=253,dp_wire_bits=2783)
 assert status(x)=='VALID'
@pytest.mark.parametrize('frame,size',[('SD1',6),('SD3',14),('SD4',3),('SC',1)])
def test_dp_fixed_fdl_frame_geometry(frame,size):
 x={**actual(),'dp_frame':frame,'dp_frame_bytes':size,'dp_wire_bits':size*11}
 assert status(x)=='VALID';assert status({**x,'dp_frame_bytes':size+1})=='INVALID'
def test_dp_native_bit_times_to_microseconds_not_milliseconds():
 x={**actual(),'bitrate_bps':1500000,'dp_frame':'SD4','dp_frame_bytes':3,'dp_wire_bits':33,'dp_serialization_us':22,
  'dp_slot_bits':300,'dp_slot_us':200,'dp_bit_time_us':2/3,'dp_target_rotation_bits':15000,'dp_rotation_us':10000,
  'dp_sync_bits':33,'dp_intra_frame_idle_bits':0,'dp_observed_response_bits':300}
 assert status(x)=='VALID'
 for bad in({'dp_slot_us':.2},{'dp_serialization_us':16},{'dp_sync_bits':32},{'dp_intra_frame_idle_bits':1},{'dp_observed_response_bits':301}):
  assert status({**x,**bad})=='INVALID'
def test_dp_manufacturer_bounds_do_not_cross_apply():
 x={**actual(),'dp_slot_bits':40,'dp_gap_factor':0,'dp_min_tsdr_bits':1,'dp_retry':15,'dp_hsa':1}
 assert status(x)=='VALID'
 assert status({**x,'dp_parameter_set':'SAIA_ENG02'})=='INVALID'
 assert status({**actual(),'dp_parameter_set':'SAIA_ENG02','bitrate_bps':45450})=='INVALID'
 assert status({**actual(),'dp_parameter_set':'REGISTERED_ACTUAL'})=='UNVERIFIED'
def test_dp_step7_dependent_response_idle_limits():
 x={**actual(),'dp_parameter_set':'SIEMENS_STEP7_V13','dp_setup_bits':1,'dp_quiet_bits':0,'dp_min_tsdr_bits':11,
  'dp_max_tsdr_bits':60,'dp_slot_bits':100,'dp_target_rotation_bits':5000,'dp_idle1_bits':37,'dp_idle2_bits':60,'dp_ready_bits':11}
 assert status(x)=='VALID'
 for bad in({'dp_max_tsdr_bits':36},{'dp_min_tsdr_bits':37},{'dp_slot_bits':74},{'dp_quiet_bits':11},
  {'dp_idle1_bits':35},{'dp_ready_bits':12},{'dp_target_rotation_bits':255}):assert status({**x,**bad})=='INVALID'
def test_dp_version_capabilities_not_connector_inference():
 assert status({**actual(),'dp_service':'ACYCLIC'})=='INVALID'
 x={**actual(),'dp_version':'V1','dp_service':'ACYCLIC','dp_supports_v1':True};assert status(x)=='VALID'
 x.pop('dp_supports_v1');assert status(x)=='UNVERIFIED'
 x={**actual(),'dp_version':'V2','dp_service':'ISOCHRONOUS','dp_supports_v2':True};assert status(x)=='VALID'
 assert status({**x,'dp_version':'V1'})=='INVALID'
def test_dp_spc3_watchdog_base_factors_and_baud_state_separate():
 x={**actual(),'dp_watchdog_impl':'SPC3_1_6','dp_watchdog_enabled':True,'dp_watchdog_source':'synthetic-WD',
  'dp_watchdog_base_ms':10,'dp_watchdog_factor1':10,'dp_watchdog_factor2':10,'dp_watchdog_ms':1000,
  'dp_baud_watchdog_units':100,'dp_baud_watchdog_ms':1000}
 assert status(x)=='VALID'
 for bad in({'dp_watchdog_ms':100},{'dp_baud_watchdog_ms':100},{'dp_watchdog_base_ms':2},
  {'dp_watchdog_factor1':1,'dp_watchdog_factor2':1,'dp_watchdog_ms':10}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'dp_watchdog_base_ms':1,'dp_watchdog_ms':100})=='UNVERIFIED'
 assert status({**x,'dp_watchdog_base_ms':1,'dp_watchdog_ms':100,'dp_supports_1ms':True})=='VALID'
 assert status({**x,'dp_watchdog_state':'DP_CONTROL','dp_watchdog_expired':True,'dp_state':'DATA_EXCHANGE'})=='INVALID'
 assert status({**x,'dp_watchdog_state':'BAUD_CONTROL','dp_watchdog_expired':True,'dp_state':'DATA_EXCHANGE'})=='VALID'
def test_dp_functional_acceptance_not_sc_ack_or_link_success():
 x={**actual(),'dp_service':'CYCLIC','dp_fdl':'SRD','dp_frame':'SD2','dp_data_accepted':True,'dp_outcome':'ACCEPTED',
  'dp_frame_valid':True,'dp_module_config_valid':True,'dp_state':'DATA_EXCHANGE','dp_age_ms':5,'dp_freshness_ms':10}
 assert status(x)=='VALID'
 for bad in({'dp_frame':'SC'},{'dp_frame_valid':False},{'dp_module_config_valid':False},{'dp_state':'WAIT_CFG'},{'dp_age_ms':11}):
  assert status({**x,**bad})=='INVALID'
 x.pop('dp_module_config_valid');assert status(x)=='UNVERIFIED'
def test_dp_existing_settings_preserved():
 x={**actual(),'bitrate_bps':187500,'dp_slot_bits':200,'dp_station':17,'dp_input_bytes':22};before=deepcopy(x)
 assert status({**x,'nominal_bitrate_bps':500000})=='INVALID'
 assert x==before and status(x)=='VALID'
