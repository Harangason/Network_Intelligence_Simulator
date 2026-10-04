"""F-parameters remain distinct from black-channel physical data and certification."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.profisafe import rules as P
def actual():
 x={'ps_'+k:'synthetic-'+k for k in P.REQUIRED}
 x.update(ps_profile='DRIVER_2_2_3',ps_mode='V2_XP',ps_bearer='PROFIBUS_DP',ps_role='F_DEVICE',ps_direction='F_OUTPUT')
 return x
def status(x):return registry.validate_parameters('profisafe',x)['status']
def test_ps_black_channel_has_no_own_rate_ethernet_application_limit_or_capacity_claim():
 p=registry.profile('profisafe');assert p['default_stack']==['profisafe']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and p['rate_model']['fields']==[]and status(actual())=='VALID'
 keys=[v['key']for v in registry.parameter_fields('profisafe')];assert len(keys)==len(set(keys))and not set(keys)&set(P.REMOVED)
 for bad in({'bitrate_bps':100000000},{'mtu_bytes':1500},{'nominal_bitrate_bps':500000},{'local_timing_evidence':{'confirmed':True}}):
  assert status({**actual(),**bad})=='INVALID'
 assert status({})=='UNVERIFIED'
@pytest.mark.parametrize('field',registry.parameter_fields('profisafe'),ids=lambda f:f['key'])
def test_ps_every_field_type_and_outer_bound(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
def test_ps_defaults_only_known_structure_or_selected_manufacturer_preset():
 f={v['key']:v for v in registry.parameter_fields('profisafe')};assert 'bitrate'not in f
 assert f['ps_control_status_bytes']['conditional_defaults'][0]['value']==1
 assert f['ps_monitor_wire_bytes']['conditional_defaults'][0]['value']==0
 for k,value in [('crc_seed',1),('passivation',0)]:
  v=f['ps_'+k]['conditional_defaults'][0];assert v['value']==value
  assert v['when']=={'ps_profile':'S7_F_SYSTEMS_6_4','ps_mode':'V2_XP','ps_configuration':'SELECTED_S7_XP_PRESET'}
 for k in('source_add','dest_add','watchdog_ms','device_sil','ipar_crc','parameters_verified','timer_independent'):
  assert 'default'not in f['ps_'+k]and 'conditional_defaults'not in f['ps_'+k]
@pytest.mark.parametrize('bearer',['PROFINET_IO','MIXED_DP_PN'])
def test_ps_pn_and_mixed_require_v2_capabilities_not_only_interface_selection(bearer):
 x={**actual(),'ps_bearer':bearer};assert status(x)=='UNVERIFIED'
 x.update(ps_host_v2_capable=True,ps_device_v2_capable=True);assert status(x)=='VALID'
 for bad in({'ps_mode':'V1'},{'ps_host_v2_capable':False},{'ps_device_v2_capable':False}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('mode,crc,seed,limit',[('V1',2,None,12),('V1',4,None,123),('V2_LP',3,0,12),('V2_XP',4,1,123)])
def test_ps_driver_directional_crc_and_compiled_buffers(mode,crc,seed,limit):
 x={**actual(),'ps_mode':mode,'ps_crc_bytes':crc,'ps_input_bytes':limit,'ps_output_bytes':0,
  'ps_compiled_input_max':limit,'ps_compiled_output_max':0}
 if mode=='V1':x['ps_v1_enabled']=True
 if seed is not None:x['ps_crc_seed']=seed
 assert status(x)=='VALID'
 assert status({**x,'ps_compiled_input_max':limit-1})=='INVALID'
 if limit==12:assert status({**x,'ps_input_bytes':13,'ps_compiled_input_max':13})=='INVALID'
 x.pop('ps_compiled_input_max');assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('mode,crc,limit',[('V1',2,12),('V2_LP',3,12),('V2_XP',4,40)])
def test_ps_s7_v64_host_limits_not_general_driver123byte_ceiling(mode,crc,limit):
 x={**actual(),'ps_profile':'S7_F_SYSTEMS_6_4','ps_mode':mode,'ps_crc_bytes':crc,'ps_input_bytes':limit,'ps_compiled_input_max':limit}
 assert status(x)=='VALID';assert status({**x,'ps_input_bytes':limit+1,'ps_compiled_input_max':limit+1})=='INVALID'
 assert status({**x,'ps_crc_bytes':4 if crc!=4 else 3})=='INVALID'
def test_ps_v1_requires_compiled_support_no_irrelevant_seed_or_v2_seq_check():
 x={**actual(),'ps_mode':'V1'};assert status(x)=='UNVERIFIED'
 x['ps_v1_enabled']=True;assert status(x)=='VALID';assert status({**x,'ps_crc_seed':0})=='INVALID'
 assert status({**actual(),'ps_check_seqnr':False})=='INVALID'
 assert status({**x,'ps_profile':'S7_F_SYSTEMS_6_4','ps_check_seqnr':True})=='INVALID'
def test_ps_v2_spdu_has_no_transmitted_monitoring_number_or_bearer_frame_overhead():
 x={**actual(),'ps_crc_bytes':4,'ps_output_bytes':123,'ps_compiled_output_max':123,'ps_control_status_bytes':1,'ps_trailer_bytes':5,
  'ps_monitor_wire_bytes':0,'ps_spdu_bytes':128,'payload_bytes':2000}
 assert status(x)=='VALID'
 for bad in({'ps_monitor_wire_bytes':4},{'ps_spdu_bytes':132},{'ps_trailer_bytes':9}):assert status({**x,**bad})=='INVALID'
def test_ps_v1_frame_layout_needs_actual_driver_trailer_source_not_v2_guess():
 x={**actual(),'ps_mode':'V1','ps_v1_enabled':True,'ps_output_bytes':12,'ps_compiled_output_max':12,'ps_spdu_bytes':16}
 assert status(x)=='UNVERIFIED'
 x.update(ps_trailer_bytes=4,ps_registered_source='synthetic-actual-legacy-codec');assert status(x)=='VALID'
 assert status({**x,'ps_trailer_bytes':3})=='INVALID'
def test_ps_seed_passivation_and_ipar_block_cannot_be_independently_mixed():
 x={**actual(),'ps_profile':'S7_F_SYSTEMS_6_4','ps_crc_seed':1,'ps_passivation':1,'ps_ipar_present':True,'ps_block_id':1,'ps_ipar_crc':1234}
 assert status(x)=='VALID'
 for bad in({'ps_crc_seed':0},{'ps_block_id':0},{'ps_block_id':3},{'ps_mode':'V2_LP'}):assert status({**x,**bad})=='INVALID'
 x.pop('ps_ipar_crc');assert status(x)=='UNVERIFIED'
def test_ps_legacy_ipar_crc16_is_not_crc2_or_32bit_ipar_signature():
 x={**actual(),'ps_check_ipar':True,'ps_ipar_present':False,'ps_legacy_ipar_crc16':1};assert status(x)=='VALID'
 assert status({**x,'ps_legacy_ipar_crc16':0})=='INVALID'
 x.pop('ps_legacy_ipar_crc16');assert status(x)=='UNVERIFIED'
def test_ps_addresses_match_actual_local_assignment_not_ip_or_dp_address():
 x={**actual(),'ps_source_add':4000,'ps_local_source_add':4000,'ps_dest_add':5000,'ps_local_dest_add':5000,
  'ps_compare_source':True,'ps_source_add_inv':61535,'ps_dest_add_inv':60535};assert status(x)=='VALID'
 for bad in({'ps_dest_add':127},{'ps_local_source_add':3999},{'ps_source_add_inv':61534},{'ps_dest_add':65535},{'ps_source_add':0}):assert status({**x,**bad})=='INVALID'
 x.pop('ps_local_dest_add');assert status(x)=='UNVERIFIED'
def test_ps_sil_requires_actual_device_limit_never_autocertifies_system():
 x={**actual(),'ps_sil':2,'ps_device_sil':2};assert status(x)=='VALID'
 assert status({**x,'ps_sil':3})=='INVALID';x.pop('ps_device_sil');assert status(x)=='UNVERIFIED'
def test_ps_gsd_watchdog_limits_and_complete_exchange_are_separate():
 x={**actual(),'ps_watchdog_ms':100,'ps_watchdog_min_ms':50,'ps_watchdog_max_ms':200,'ps_exchange_bound_ms':99.9}
 assert status(x)=='VALID'
 for bad in({'ps_watchdog_ms':0},{'ps_watchdog_min_ms':101},{'ps_watchdog_max_ms':99},{'ps_exchange_bound_ms':100}):assert status({**x,**bad})=='INVALID'
 x.pop('ps_watchdog_max_ms');assert status(x)=='UNVERIFIED'
def test_ps_native_timer_independence_and_inverse_values_not_two_copies():
 x={**actual(),'ps_timer1':65530,'ps_timer1_inv':5,'ps_timer2':3,'ps_timer2_inv':65532,'ps_timer_tick_ms':1};assert status(x)=='VALID'
 for bad in({'ps_timer1_inv':65530},{'ps_timer2_inv':3},{'ps_timer_tick_ms':100}):assert status({**x,**bad})=='INVALID'
def test_ps_instance_limits_and_eight_bit_controller_only_single_instance():
 x={**actual(),'ps_instances':32,'ps_instance':32,'ps_controller_bits':32};assert status(x)=='VALID'
 assert status({**x,'ps_controller_bits':8})=='INVALID';assert status({**x,'ps_instances':31})=='INVALID'
def test_ps_demand_must_span_two_subsequent_monitoring_numbers():
 x={**actual(),'ps_demand_active':True,'ps_consecutive_demand_count':2};assert status(x)=='VALID'
 assert status({**x,'ps_consecutive_demand_count':1})=='INVALID';x.pop('ps_consecutive_demand_count');assert status(x)=='UNVERIFIED'
def test_ps_sfrt_total_chain_plus_maximum_extra_failure_delay_not_sum_all_watchdogs():
 x=actual();values=[('sensor',2,10),('bus_in',3,20),('host',4,30),('bus_out',5,20),('actuator',6,12)]
 for part,wcdt,wd in values:x['ps_'+part+'_wcdt_ms']=wcdt;x['ps_'+part+'_watchdog_ms']=wd
 x.update(ps_total_wcdt_ms=20,ps_fault_delta_ms=26,ps_sfrt_ms=46,ps_sfrt_limit_ms=50);assert status(x)=='VALID'
 for bad in({'ps_fault_delta_ms':92},{'ps_sfrt_ms':112},{'ps_total_wcdt_ms':5},{'ps_sfrt_limit_ms':45}):assert status({**x,**bad})=='INVALID'
 x.pop('ps_actuator_watchdog_ms');assert status(x)=='UNVERIFIED'
def accepted():
 return {**actual(),'ps_data_accepted':True,'ps_state':'PSD_DATAEX','ps_outcome':'ACCEPTED','ps_output_result':'F_OUTPUT_OK',
  'ps_parameters_verified':True,'ps_crc2_verified':True,'ps_mapping_valid':True,'ps_passivated':False,'ps_timer_independent':True,'ps_age_ms':10,'ps_freshness_ms':20}
@pytest.mark.parametrize('bad',[{'ps_output_result':'F_OUTPUT_OLD_CONSNR'},{'ps_output_result':'F_OUTPUT_WD_TIMEOUT'},
 {'ps_output_result':'F_OUTPUT_COMM_ERR'},{'ps_output_result':'F_OUTPUT_PASSIVATED'},{'ps_state':'PSD_PARAM'},{'ps_passivated':True},
 {'ps_timer_independent':False},{'ps_parameters_verified':False},{'ps_crc2_verified':False},{'ps_device_fault':True},
 {'ps_activate_fv':True},{'ps_fv_activated':True},{'ps_ipar_enabled':True},{'ps_oa_req':True,'ps_oa_confirmed':False},{'ps_age_ms':21}])
def test_ps_old_bad_passivated_unacknowledged_data_not_functionally_accepted(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_ps_finput_acceptance_not_forced_to_driver_foutput_result():
 x=accepted();x['ps_direction']='F_INPUT';x.pop('ps_output_result');assert status(x)=='VALID'
 x.pop('ps_crc2_verified');assert status(x)=='UNVERIFIED'
def test_ps_requested_operator_acknowledgment_cannot_be_missing_or_implicit():
 x={**accepted(),'ps_oa_req':True};assert status(x)=='UNVERIFIED'
 assert status({**x,'ps_oa_confirmed':False})=='INVALID'
 assert status({**x,'ps_oa_confirmed':True})=='VALID'
def test_ps_confirmed_values_retained_without_foreign_can_defaults():
 x={**actual(),'ps_dest_add':2000,'ps_local_dest_add':2000,'ps_watchdog_ms':321,'ps_watchdog_min_ms':20,'ps_watchdog_max_ms':500,'ps_ipar_crc':0x1234};before=deepcopy(x)
 assert status(x)=='VALID';assert status({**x,'nominal_bitrate_bps':500000})=='INVALID';assert x==before
