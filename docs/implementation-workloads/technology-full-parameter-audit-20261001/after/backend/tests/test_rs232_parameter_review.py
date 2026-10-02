"""RS232 physical conditions, codec independence and retained actual settings."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import rs232 as R
def actual():
 x={'rs232_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(rs232_profile='TIA_232_F_TI2002',rs232_role='DTE',rs232_peer_role='DCE',rs232_wiring='STRAIGHT',rs232_connector='DE9_EIA574',rs232_direction='FULL_DUPLEX',rs232_clocking='ASYNCHRONOUS',rs232_encoding='START_STOP')
 return x
def status(x):return registry.validate_parameters('rs232',x)['status']
def test_232_is_electrical_not_uart_8n1_or_fixed115200():
 p=registry.profile('rs232');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('rs232')};assert not set(R.REMOVED)&set(f)
 for k in('rs232_bitrate_bps','rs232_start_bits','rs232_data_bits','rs232_parity','rs232_stop_bits','rs232_connector','rs232_total_load_pf'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'bitrate_bps':115200},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('rs232'),ids=lambda f:f['key'])
def test_232_every_field_type_and_outer_bound(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('key,low,high',[('driver_mark_v',-15,-5),('driver_space_v',5,15),('receiver_mark_v',-15,-3),('receiver_space_v',3,15),('receiver_load_ohm',3000,7000)])
def test_232_loaded_voltage_and_receiver_fixture(key,low,high):
 for v in(low,high):assert status({**actual(),'rs232_'+key:v})=='VALID'
 for v in(low-.01,high+.01):assert status({**actual(),'rs232_'+key:v})=='INVALID'
@pytest.mark.parametrize('logic,v',[('MARK_1',-3),('SPACE_0',3)])
def test_232_ttl_0_and3v3_do_not_represent_all_rs232_data(logic,v):
 x={**actual(),'rs232_data_logic':logic,'rs232_receiver_data_v':v};assert status(x)=='VALID'
 assert status({**x,'rs232_receiver_data_v':0})=='INVALID'
 assert status({**x,'rs232_receiver_data_v':-v})=='INVALID'
@pytest.mark.parametrize('state,v',[('ON',3),('OFF',-3)])
def test_232_control_assertion_not_data_mark_polarity(state,v):
 x={**actual(),'rs232_control_state':state,'rs232_control_v':v};assert status(x)=='VALID'
 assert status({**x,'rs232_control_v':-v})=='INVALID'
@pytest.mark.parametrize('role,peer,wiring',[('DTE','DCE','STRAIGHT'),('DCE','DTE','STRAIGHT'),('DTE','DTE','NULL_MODEM'),('DCE','DCE','NULL_MODEM')])
def test_232_dte_dce_wiring_roles(role,peer,wiring):
 x={**actual(),'rs232_role':role,'rs232_peer_role':peer,'rs232_wiring':wiring};assert status(x)=='VALID'
 assert status({**x,'rs232_wiring':'STRAIGHT'if wiring=='NULL_MODEM'else'NULL_MODEM'})=='INVALID'
def test_232_higher_rate_needs_both_devices_qualified_not_same_connector():
 assert status({**actual(),'rs232_bitrate_bps':20000})=='VALID'
 assert status({**actual(),'rs232_bitrate_bps':115200})=='INVALID'
 x={**actual(),'rs232_profile':'DEVICE_QUALIFIED','rs232_bitrate_bps':115200,'rs232_registered_source':'synthetic-selected-higher-rate'}
 assert status(x)=='UNVERIFIED';x.update(rs232_device_max_bps=250000,rs232_peer_max_bps=120000);assert status(x)=='VALID'
 assert status({**x,'rs232_peer_max_bps':20000})=='INVALID'
 for v in(0,-1):assert status({**x,'rs232_bitrate_bps':v})=='INVALID'
def test_232_capacitance_not_fixed_15m_or_receiver20pf_assumption():
 x={**actual(),'rs232_total_load_pf':2500,'rs232_receiver_cap_pf':50,'rs232_other_cap_pf':50,'rs232_cable_pf_m':60,'rs232_cable_m':40}
 assert status(x)=='VALID';assert status({**x,'rs232_cable_m':41})=='INVALID'
 assert status({**x,'rs232_total_load_pf':2501})=='INVALID'
 x.pop('rs232_receiver_cap_pf');assert status(x)=='UNVERIFIED'
def test_232_driver_poweroff_impedance_and_slew_are_fixture_limits():
 assert status({**actual(),'rs232_driver_off_impedance_ohm':301,'rs232_slew_v_us':30})=='VALID'
 assert status({**actual(),'rs232_driver_off_impedance_ohm':300})=='INVALID'
 assert status({**actual(),'rs232_slew_v_us':30.01})=='INVALID'
@pytest.mark.parametrize('rate,max_us',[(10,1000),(40,1000),(9600,4.166666666666667),(20000,2)])
def test_232_transition_region_rate_dependent_4percent_not_universal5us(rate,max_us):
 x={**actual(),'rs232_bitrate_bps':rate,'rs232_transition_us':max_us};assert status(x)=='VALID'
 assert status({**x,'rs232_transition_us':max_us+.01})=='INVALID'
def frame():
 return {**actual(),'rs232_bitrate_bps':9600,'rs232_data_bits':8,'rs232_start_bits':1,'rs232_parity':'NONE','rs232_parity_bits':0,'rs232_stop_bits':1.5,'rs232_character_bits':10.5,'rs232_characters':16,'rs232_wire_bits':168,'rs232_wire_time_ms':17.5}
def test_232_startstop_codec_actual_fractional_stop_and_wiretime():
 x=frame();assert status(x)=='VALID'
 for bad in({'rs232_character_bits':10},{'rs232_wire_bits':160},{'rs232_wire_time_ms':16.6667},{'rs232_stop_bits':1.25},{'rs232_parity':'ODD'}):assert status({**x,**bad})=='INVALID'
 x.pop('rs232_parity_bits');assert status(x)=='UNVERIFIED'
def test_232_synchronous_not_forced_uart_character_framing():
 x={**actual(),'rs232_clocking':'SYNCHRONOUS','rs232_encoding':'SYNCHRONOUS_RAW','rs232_wire_bits':8,'rs232_bitrate_bps':8000,'rs232_wire_time_ms':1};assert status(x)=='VALID'
 assert status({**x,'rs232_encoding':'START_STOP'})=='INVALID'
def test_232_empty_transaction_can_have_zero_wiretime_but_not_zero_rate():
 x={**frame(),'rs232_characters':0,'rs232_wire_bits':0,'rs232_wire_time_ms':0,'rs232_bitrate_bps':9600};assert status(x)=='VALID'
 assert status({**x,'rs232_wire_time_ms':1})=='INVALID'
def test_232_flow_wait_and_processing_separate_from_wiretime():
 x={**frame(),'rs232_flow_control':'RTS_CTS','rs232_flow_wait_bound_ms':50,'rs232_decode_bound_ms':2.5,'rs232_transaction_bound_ms':70,'rs232_transaction_limit_ms':70}
 assert status(x)=='VALID';assert status({**x,'rs232_transaction_bound_ms':17.5})=='INVALID'
 assert status({**x,'rs232_transaction_limit_ms':69})=='INVALID'
 assert status({**x,'rs232_flow_control':'NONE'})=='INVALID'
def accepted():
 return {**frame(),'rs232_value_accepted':True,'rs232_outcome':'ACCEPTED','rs232_electrical_valid':True,'rs232_mapping_valid':True,'rs232_codec_verified':True,
  'rs232_power_sequence_verified':True,'rs232_power_state':'ACTIVE','rs232_ttl_bias':'INTERNAL','rs232_wave_source':'synthetic-wave','rs232_clock_source':'synthetic-clock','rs232_power_source':'synthetic-power',
  'rs232_age_ms':3,'rs232_freshness_ms':10,'rs232_flow_wait_bound_ms':0,'rs232_decode_bound_ms':2.5,'rs232_transaction_bound_ms':20,'rs232_transaction_limit_ms':20}
@pytest.mark.parametrize('bad',[{'rs232_outcome':'PARITY_ERROR'},{'rs232_outcome':'BREAK'},{'rs232_power_state':'STARTUP'},{'rs232_ttl_bias':'FLOATING'},{'rs232_age_ms':11}, {'rs232_electrical_valid':False},{'rs232_codec_verified':False},{'rs232_power_sequence_verified':False},{'rs232_flow_control':'RTS_CTS','rs232_cts_asserted':False}])
def test_232_electrical_rate_does_not_prove_accepted_value(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_232_bias_power_sequence_and_bidirectional_tvs():
 x={**actual(),'rs232_ttl_bias':'EXTERNAL_PULL_UP','rs232_ttl_bias_ohm':47000,'rs232_power_source':'synthetic-backbias-check','rs232_tvs':'BIDIRECTIONAL'};assert status(x)=='VALID'
 assert status({**x,'rs232_tvs':'UNIDIRECTIONAL'})=='INVALID'
 x.pop('rs232_power_source');assert status(x)=='UNVERIFIED'
def test_232_chargepump_cap_rating_uses_actual_selected_part_typical_output():
 x={**actual(),'rs232_chargepump_cap_voltage_v':25,'rs232_output_typ_abs_v':12};assert status(x)=='VALID'
 assert status({**x,'rs232_chargepump_cap_voltage_v':23})=='INVALID'
def test_232_confirmed_device_rate_and_codec_retained():
 x={**frame(),'rs232_profile':'DEVICE_QUALIFIED','rs232_registered_source':'synthetic-selected-driver','rs232_bitrate_bps':115200,'rs232_device_max_bps':250000,'rs232_peer_max_bps':250000};x.pop('rs232_wire_time_ms');before=deepcopy(x)
 assert status(x)=='VALID';assert x==before
