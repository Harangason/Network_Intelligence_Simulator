"""Individually reviewed RS422 electrical/termination/codec conditions."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.rs422 import rules as R

def actual():
 x={'rs422_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(rs422_profile='TIA_422_TI2010',rs422_signal_kind='DATA_STREAM',rs422_topology='POINT_TO_POINT',rs422_direction='SIMPLEX',rs422_encoding='RAW_BITS',rs422_drivers=1,rs422_receivers=1)
 return x
def status(x):return registry.validate_parameters('rs422',x)['status']
def test_balanced_electrical_profile_not_rs485_or_uart_default():
 p=registry.profile('rs422');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('rs422')};assert not set(R.REMOVED)&set(f)
 for k in('rs422_bitrate_bps','rs422_cable_m','rs422_termination_ohm','rs422_receivers','rs422_encoding'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('rs422'),ids=lambda f:f['key'])
def test_each_field_type_and_declared_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('receivers',[1,2,10])
def test_single_driver_multidrop_receivers_not_multiple_drivers(receivers):
 x={**actual(),'rs422_topology':'MULTIDROP','rs422_receivers':receivers};assert status(x)=='VALID'
 assert status({**x,'rs422_drivers':2})=='INVALID'
 assert status({**x,'rs422_receivers':11})=='INVALID'
 assert status({**actual(),'rs422_receivers':2})=='INVALID'
def test_rate_not_10m_default_and_qualified_devices_keep_higher_rate():
 assert status({**actual(),'rs422_bitrate_bps':10000000})=='VALID'
 assert status({**actual(),'rs422_bitrate_bps':10000001})=='INVALID'
 x={**actual(),'rs422_profile':'DEVICE_QUALIFIED','rs422_bitrate_bps':20000000,'rs422_registered_source':'synthetic-qualified'}
 assert status(x)=='UNVERIFIED';x.update(rs422_device_max_bps=25000000,rs422_peer_max_bps=22000000)
 before=deepcopy(x);assert status(x)=='VALID'and x==before
 assert status({**x,'rs422_peer_max_bps':10000000})=='INVALID'
@pytest.mark.parametrize('k,valid,bad',[
 ('receiver_input_ohm',4000,3999),('driver_diff_abs_v',10,10.01),('driver_offset_abs_v',3,3.01),
 ('driver_diff_delta_abs_v',.4,.41),('driver_offset_delta_abs_v',.4,.41),('driver_short_abs_ma',150,151)])
def test_fixture_electrical_limits_not_normal_drive_defaults(k,valid,bad):
 assert status({**actual(),'rs422_'+k:valid})=='VALID'
 assert status({**actual(),'rs422_'+k:bad})=='INVALID'
def test_loaded_100ohm_minimum_and_unloaded_signed_voltage():
 x={**actual(),'rs422_load_scope':'STANDARD_100_OHM','rs422_driver_diff_abs_v':2,'rs422_fixture_load_ohm':100};assert status(x)=='VALID'
 assert status({**x,'rs422_driver_diff_abs_v':1.99})=='INVALID'
 assert status({**x,'rs422_fixture_load_ohm':120})=='INVALID'
 for v in(-6,6):assert status({**actual(),'rs422_load_scope':'OPEN_CIRCUIT','rs422_driver_a_v':v})=='VALID'
 assert status({**actual(),'rs422_load_scope':'OPEN_CIRCUIT','rs422_driver_a_v':6.01})=='INVALID'
@pytest.mark.parametrize('v',[-.25,6])
def test_poweroff_leakage_fixture_range(v):
 x={**actual(),'rs422_off_test_v':v,'rs422_off_leak_abs_ua':100};assert status(x)=='VALID'
 assert status({**x,'rs422_off_leak_abs_ua':101})=='INVALID'
 x.pop('rs422_off_test_v');assert status(x)=='UNVERIFIED'
def measured():
 return {**actual(),'rs422_receiver_a_v':1,'rs422_receiver_b_v':0,'rs422_receiver_common_v':.5,'rs422_receiver_diff_v':1,'rs422_receiver_diff_abs_v':1,'rs422_logic_mapping':'POSITIVE_IS_1','rs422_decoded_logic':'ONE','rs422_polarity_source':'synthetic-truth-table'}
@pytest.mark.parametrize('bad',[{'rs422_receiver_common_v':1},{'rs422_receiver_diff_v':.5},{'rs422_receiver_diff_abs_v':.5},{'rs422_decoded_logic':'ZERO'}])
def test_signed_pair_commonmode_and_actual_logic_not_ab_label(bad):
 assert status(measured())=='VALID';assert status({**measured(),**bad})=='INVALID'
@pytest.mark.parametrize('common',[-7,7])
def test_commonmode_rs422_not_rs485_plus12(common):
 x={**actual(),'rs422_receiver_a_v':common+.1,'rs422_receiver_b_v':common-.1,'rs422_receiver_common_v':common};assert status(x)=='VALID'
 assert status({**x,'rs422_receiver_a_v':common+.2})=='INVALID'
 assert status({**actual(),'rs422_receiver_a_v':12,'rs422_receiver_b_v':12,'rs422_receiver_common_v':12})=='INVALID'
def terminated():
 return {**actual(),'rs422_termination':'PARALLEL','rs422_termination_count':1,'rs422_termination_position':'FAR_RECEIVER','rs422_cable_impedance_ohm':120,'rs422_termination_ohm':120}
@pytest.mark.parametrize('v',[96,120,144])
def test_one_far_end_termination_matches_actual_line_with20percent(v):
 x={**terminated(),'rs422_termination_ohm':v};assert status(x)=='VALID'
 assert status({**x,'rs422_termination_count':2})=='INVALID'
 for v in(95,145):assert status({**x,'rs422_termination_ohm':v})=='INVALID'
def test_ac_capacitor_is_actual_qualified_not_1000pf_default():
 x={**terminated(),'rs422_termination':'AC','rs422_termination_pf':2200,'rs422_termination_source':'synthetic-reflection-test'};assert status(x)=='VALID'
 x.pop('rs422_termination_source');assert status(x)=='UNVERIFIED'
def test_none_termination_needs_actual_delay_or_lowrate_shortline_proof():
 x={**actual(),'rs422_termination':'NONE','rs422_termination_count':0,'rs422_termination_position':'NONE','rs422_unterminated_basis':'LOW_RATE_SHORT_LINE','rs422_bitrate_bps':200000,'rs422_termination_source':'synthetic-short-line'};assert status(x)=='VALID'
 assert status({**x,'rs422_bitrate_bps':200001})=='INVALID'
 x.update(rs422_unterminated_basis='RISE_GT_FOUR_DELAYS',rs422_bitrate_bps=1000000,rs422_rise_ns=41,rs422_delay_ns=10);assert status(x)=='VALID'
 assert status({**x,'rs422_rise_ns':40})=='INVALID'
@pytest.mark.parametrize('rate,ui,bound',[(10000000,100,20),(1000000,1000,100)])
def test_waveform_max20ns_or10percent_ui_under_100ohm(rate,ui,bound):
 x={**actual(),'rs422_load_scope':'STANDARD_100_OHM','rs422_bitrate_bps':rate,'rs422_unit_interval_ns':ui,'rs422_rise_ns':bound,'rs422_fall_ns':bound,'rs422_overshoot_percent':10};assert status(x)=='VALID'
 for k in('rs422_rise_ns','rs422_fall_ns','rs422_overshoot_percent'):assert status({**x,k:x[k]+.01})=='INVALID'
def transaction():
 return {**actual(),'rs422_bitrate_bps':1000000,'rs422_words':10,'rs422_word_data_bits':8,'rs422_word_wire_bits':10,'rs422_wire_bits':100,'rs422_wire_time_ms':.1,'rs422_process_bound_ms':.9,'rs422_transaction_bound_ms':1,'rs422_transaction_limit_ms':1}
@pytest.mark.parametrize('bad',[{'rs422_wire_bits':80},{'rs422_wire_time_ms':.08},{'rs422_transaction_bound_ms':.1},{'rs422_transaction_limit_ms':.99},{'rs422_word_wire_bits':7}])
def test_independently_declared_codec_and_complete_wire_processing_chain(bad):
 assert status(transaction())=='VALID';assert status({**transaction(),**bad})=='INVALID'
def test_empty_wire_transmission_does_not_gain_positive_time():
 x={**transaction(),'rs422_words':0,'rs422_wire_bits':0,'rs422_wire_time_ms':0,'rs422_process_bound_ms':0,'rs422_transaction_bound_ms':0};assert status(x)=='VALID'
 assert status({**x,'rs422_wire_time_ms':1})=='INVALID'
def accepted():
 return {**transaction(),**measured(),**terminated(),'rs422_signal_accepted':True,'rs422_outcome':'ACCEPTED','rs422_electrical_valid':True,'rs422_mapping_valid':True,'rs422_termination_verified':True,'rs422_codec_verified':True,'rs422_fault':'NORMAL','rs422_power_state':'ACTIVE','rs422_wave_source':'synthetic-wave','rs422_clock_source':'synthetic-clock','rs422_termination_source':'synthetic-test','rs422_age_ms':1,'rs422_freshness_ms':2,'rs422_noise_abs_mv':100,'rs422_noise_margin_mv':700}
@pytest.mark.parametrize('bad',[{'rs422_outcome':'ELECTRICAL_FAULT'},{'rs422_fault':'IDLE'},{'rs422_fault':'OPEN'},{'rs422_fault':'SHORT'},{'rs422_power_state':'HIGH_Z'},{'rs422_age_ms':3},{'rs422_codec_verified':False},{'rs422_electrical_valid':False},{'rs422_noise_margin_mv':701}])
def test_failsafe_idle_or_electrical_rate_do_not_prove_functional_acceptance(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_clock_pair_has_own_frequency_and_verification():
 x={**accepted(),'rs422_signal_kind':'CLOCK_PAIR','rs422_encoding':'CLOCK_ONLY','rs422_clock_hz':1000000,'rs422_clock_verified':True};assert status(x)=='VALID'
 assert status({**x,'rs422_clock_verified':False})=='INVALID'
