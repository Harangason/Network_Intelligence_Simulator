"""RS485 actual unit loads, driver control and distinct electrical fixtures."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import rs485 as R
def actual():
 x={'rs485_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(rs485_profile='TIA_485_TI2010',rs485_topology='BUS_DAISY_CHAIN',rs485_direction='HALF_DUPLEX_ONE_PAIR',rs485_wire_protocol='REGISTERED_ACTUAL')
 return x
def status(x):return registry.validate_parameters('rs485',x)['status']
def test_electrical_rs485_not_can_or_modbus_or_default_10m():
 p=registry.profile('rs485');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('rs485')};assert not set(R.REMOVED)&set(f)
 for k in('rs485_bitrate_bps','rs485_unit_load','rs485_bias_selected_ohm','rs485_cable_m','rs485_word_data_bits'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('rs485'),ids=lambda f:f['key'])
def test_each_parameter_declared_type_and_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
def loads(nodes=256,bias=0):
 return {**actual(),'rs485_load_model':'HOMOGENEOUS_ACTUAL','rs485_nodes':nodes,'rs485_unit_load':.125,'rs485_receiver_load_ul':nodes*.125,'rs485_bias_load_ul':bias,'rs485_total_load_ul':nodes*.125+bias}
@pytest.mark.parametrize('nodes,bias',[(32,0),(64,0),(256,0),(96,20)])
def test_unit_load_not_device_count_and_bias_reduces_budget(nodes,bias):
 x=loads(nodes,bias);assert status(x)=='VALID'
 assert status(loads(nodes+1,32-nodes*.125))=='INVALID'
 assert status({**x,'rs485_total_load_ul':1})=='INVALID'
def test_no_default_one_eighth_ul_or_twenty_ul_bias():
 x=loads(32);x.update(rs485_unit_load=1,rs485_receiver_load_ul=32,rs485_total_load_ul=32);assert status(x)=='VALID'
 assert status({**x,'rs485_bias_load_ul':1,'rs485_total_load_ul':33})=='INVALID'
 x.pop('rs485_unit_load');assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('direction',['HALF_DUPLEX_ONE_PAIR','FULL_DUPLEX_TWO_PAIRS'])
def test_only_one_active_driver_per_pair_even_full_duplex(direction):
 x={**actual(),'rs485_direction':direction,'rs485_drivers':20,'rs485_active_drivers':1,'rs485_activity':'FRAME'};assert status(x)=='VALID'
 assert status({**x,'rs485_active_drivers':2})=='INVALID'
 assert status({**x,'rs485_active_drivers':0})=='INVALID'
 assert status({**x,'rs485_activity':'IDLE','rs485_active_drivers':0})=='VALID'
def test_reference_upper_rate_and_preserved_separate_higher_device_qualification():
 assert status({**actual(),'rs485_bitrate_bps':10000000})=='VALID'
 assert status({**actual(),'rs485_bitrate_bps':40000000})=='INVALID'
 x={**actual(),'rs485_profile':'DEVICE_QUALIFIED','rs485_bitrate_bps':40000000};assert status(x)=='UNVERIFIED'
 x.update(rs485_device_max_bps=40000000,rs485_peer_max_bps=45000000);before=deepcopy(x)
 assert status(x)=='VALID'and x==before
 assert status({**x,'rs485_peer_max_bps':10000000})=='INVALID'
@pytest.mark.parametrize('scope,high',[('OPEN_CIRCUIT',6),('STANDARD_54_OHM',5),('STANDARD_CM_60_375',5)])
def test_loaded_unloaded_fixture_voltage_limits_distinguished(scope,high):
 for v in(1.5,high):assert status({**actual(),'rs485_load_scope':scope,'rs485_driver_diff_abs_v':v})=='VALID'
 for v in(1.49,high+.01):assert status({**actual(),'rs485_load_scope':scope,'rs485_driver_diff_abs_v':v})=='INVALID'
@pytest.mark.parametrize('k,valid,bad',[('driver_offset_v',-1,-1.01),('driver_offset_v',3,3.01),('driver_diff_delta_abs_v',.2,.21),('driver_offset_delta_abs_v',.2,.21),('short_test_v',-7,-7.01),('short_test_v',12,12.01)])
def test_signed_offset_imbalance_and_short_test_extremes(k,valid,bad):
 assert status({**actual(),'rs485_'+k:valid})=='VALID'
 assert status({**actual(),'rs485_'+k:bad})=='INVALID'
def test_short_current_limit_not_indefinite_full_voltage_hardware_proof():
 x={**actual(),'rs485_short_current_abs_ma':250,'rs485_short_test_v':12};assert status(x)=='VALID'
 assert status({**x,'rs485_short_current_abs_ma':251})=='INVALID'
 assert status({**x,'rs485_short_indefinite_verified':True})=='UNVERIFIED'
@pytest.mark.parametrize('common',[-7,12])
def test_rs485_common_mode_not_rs422_plus7(common):
 x={**actual(),'rs485_receiver_a_v':common+.1,'rs485_receiver_b_v':common-.1,'rs485_receiver_common_v':common};assert status(x)=='VALID'
 assert status({**x,'rs485_receiver_common_v':common+.01})=='INVALID'
 assert status({**actual(),'rs485_receiver_a_v':12.11,'rs485_receiver_b_v':12.09,'rs485_receiver_common_v':12.1})=='INVALID'
def waveform():
 return {**actual(),'rs485_load_scope':'STANDARD_54_OHM','rs485_bitrate_bps':10000000,'rs485_unit_interval_ns':100,'rs485_rise_ns':30,'rs485_fall_ns':30,'rs485_fixture_ohm':54,'rs485_fixture_pf':50,'rs485_overshoot_percent':10}
@pytest.mark.parametrize('bad',[{'rs485_rise_ns':30.01},{'rs485_fall_ns':30.01},{'rs485_unit_interval_ns':101},{'rs485_fixture_ohm':100},{'rs485_fixture_pf':51},{'rs485_overshoot_percent':10.01}])
def test_54ohm_50pf_waveform30percent_ui_not_rs42220ns(bad):
 assert status(waveform())=='VALID';assert status({**waveform(),**bad})=='INVALID'
def physical():
 return {**actual(),'rs485_termination':'PARALLEL_TWO_ENDS','rs485_termination_count':2,'rs485_termination_ohm':120,'rs485_cable_impedance_ohm':120,'rs485_rise_ns':100,'rs485_velocity_fraction':.78,'rs485_stub_m':2,'rs485_stub_delay_ns':10,'rs485_media_pf_m':50,'rs485_node_cap_pf':10,'rs485_spacing_m':1.1,'rs485_loaded_impedance_ohm':49}
@pytest.mark.parametrize('bad',[{'rs485_termination_count':1},{'rs485_termination_ohm':100},{'rs485_stub_m':2.34},{'rs485_stub_delay_ns':10.01},{'rs485_spacing_m':1.05},{'rs485_loaded_impedance_ohm':48}])
def test_actual_line_end_termination_stub_and_node_spacing_guidelines(bad):
 assert status(physical())=='VALID';assert status({**physical(),**bad})=='INVALID'
def test_split_effective_termination_and_actual_capacitor_not220pf_default():
 x={**physical(),'rs485_termination':'SPLIT_TWO_ENDS','rs485_split_resistor_ohm':60,'rs485_split_filter_pf':470};assert status(x)=='VALID'
 assert status({**x,'rs485_split_resistor_ohm':55})=='INVALID'
 x.pop('rs485_split_filter_pf');assert status(x)=='UNVERIFIED'
def bias():
 return {**loads(96,20),'rs485_failsafe':'EXTERNAL_PROVEN','rs485_failsafe_source':'synthetic-noise-test','rs485_noise_abs_mv':50,'rs485_bias_diff_v':.25,'rs485_bias_supply_min_v':4.75,'rs485_cable_impedance_ohm':120,'rs485_bias_max_ohm':4.75*375*120/(.25*1620),'rs485_bias_selected_ohm':523}
def test_failsafe_equation_actual_supply_line_noise_and_ul_load():
 x=bias();assert status(x)=='VALID'
 for bad in({'rs485_bias_diff_v':.24},{'rs485_bias_max_ohm':523},{'rs485_bias_selected_ohm':529},{'rs485_nodes':256,'rs485_receiver_load_ul':32,'rs485_total_load_ul':52}):assert status({**x,**bad})=='INVALID'
def transaction():
 return {**actual(),'rs485_bitrate_bps':1000000,'rs485_words':10,'rs485_word_data_bits':8,'rs485_word_wire_bits':10,'rs485_wire_bits':100,'rs485_wire_time_ms':.1,'rs485_grant_wait_ms':2,'rs485_enable_delay_ms':.01,'rs485_turnaround_ms':.09,'rs485_process_ms':.8,'rs485_transaction_bound_ms':3,'rs485_transaction_limit_ms':3}
@pytest.mark.parametrize('bad',[{'rs485_wire_bits':80},{'rs485_wire_time_ms':.08},{'rs485_transaction_bound_ms':.1},{'rs485_transaction_limit_ms':2.99},{'rs485_word_wire_bits':7}])
def test_selected_codec_and_complete_grant_enable_wire_turnaround_processing_chain(bad):
 assert status(transaction())=='VALID';assert status({**transaction(),**bad})=='INVALID'
def test_empty_wire_time_is_not_positive_transaction_wire_time():
 x={**transaction(),'rs485_words':0,'rs485_wire_bits':0,'rs485_wire_time_ms':0,'rs485_transaction_bound_ms':2.9};assert status(x)=='VALID'
 assert status({**x,'rs485_wire_time_ms':1})=='INVALID'
def accepted():
 return {**transaction(),**loads(32),**physical(),'rs485_value_accepted':True,'rs485_outcome':'ACCEPTED','rs485_activity':'FRAME','rs485_active_drivers':1,'rs485_drivers':20,'rs485_de_control_verified':True,'rs485_electrical_valid':True,'rs485_mapping_valid':True,'rs485_codec_verified':True,'rs485_physical_verified':True,'rs485_ground_scheme':'SIGNAL_AND_SUPPLY_ISOLATED','rs485_ground_source':'synthetic-ground-test','rs485_ground_diff_v':0,'rs485_receiver_a_v':1,'rs485_receiver_b_v':0,'rs485_receiver_common_v':.5,'rs485_receiver_diff_v':1,'rs485_receiver_diff_abs_v':1,'rs485_logic_mapping':'POSITIVE_IS_1','rs485_decoded_logic':'ONE','rs485_polarity_source':'synthetic-truth-table','rs485_termination_source':'synthetic-reflections','rs485_wave_source':'synthetic-wave','rs485_clock_source':'synthetic-clock','rs485_age_ms':1,'rs485_freshness_ms':2}
@pytest.mark.parametrize('bad',[{'rs485_activity':'IDLE'},{'rs485_activity':'OPEN'},{'rs485_activity':'SHORT'},{'rs485_activity':'CONTENTION'},{'rs485_de_control_verified':False},{'rs485_physical_verified':False},{'rs485_age_ms':3},{'rs485_codec_verified':False}])
def test_idle_failsafe_or_bitrate_does_not_prove_accepted_decoded_value(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
