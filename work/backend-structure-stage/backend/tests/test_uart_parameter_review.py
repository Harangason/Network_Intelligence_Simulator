"""UART device dividers, framing and service bounds remain source qualified."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.uart import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual(profile='PIC24H_DS70232B'):
 x={'ua_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(ua_review_profile=profile,ua_mode='ASYNC_UART',ua_baud=9600,ua_data_bits=8,ua_start_bits=1,ua_stop_bits=1,ua_parity='NONE',ua_direction='FULL_DUPLEX',ua_flow='NONE');return x
def status(x):return registry.validate_parameters('uart',x)['status']
def test_uart_own_clock_not_rs232_voltage_or_fixed115200():
 p=registry.profile('uart');assert p['domain']=='generic_networking'and p['default_stack']==['uart']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':115200},{'retry_limit':3},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('uart',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('uart'),ids=lambda f:f['key'])
def test_every_uart_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('parity',['NONE','EVEN','ODD'])
@pytest.mark.parametrize('stop',[1,2])
def test_pic_8bit_parity_and_stop_modes(parity,stop):assert status({**actual(),'ua_parity':parity,'ua_stop_bits':stop})=='VALID'
@pytest.mark.parametrize('bad',[{'ua_data_bits':7},{'ua_data_bits':9,'ua_parity':'EVEN'},{'ua_stop_bits':1.5},{'ua_parity':'MARK'},{'ua_start_bits':2},{'ua_bit_order':'MSB_FIRST'}])
def test_pic_modes_not_lpc_modes(bad):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('brg,oversample',[(0,16),(65535,16),(0,4),(25,16)])
def test_pic_real_input_clock_and_16bit_divisor(brg,oversample):
 clock=4000000;baud=clock/(oversample*(brg+1));x={**actual(),'ua_clock_hz':clock,'ua_brg':brg,'ua_oversampling':oversample,'ua_baud':baud};assert status(x)=='VALID'
 assert status({**x,'ua_baud':baud+1})=='INVALID'
def test_pic_instruction_clock_not_fosc_and_majority_mode():
 x={**actual(),'ua_clock_hz':4000000,'ua_brg':25,'ua_oversampling':16,'ua_baud':4000000/(16*26)};assert status(x)=='VALID'
 assert status({**x,'ua_oversampling':8})=='INVALID'
 assert status({**x,'ua_clock_hz':8000000})=='INVALID'
@pytest.mark.parametrize('bits,stop',[(5,1),(5,1.5),(6,1),(6,2),(7,2),(8,2)])
@pytest.mark.parametrize('parity',['NONE','EVEN','ODD','MARK','SPACE'])
def test_lpc_explicit_modes(bits,stop,parity):assert status({**actual('LPC24XX_UM10237_4'),'ua_data_bits':bits,'ua_stop_bits':stop,'ua_parity':parity})=='VALID'
def test_lpc_stop_dependency_no_pic9_or_oversampling4():
 for bad in({'ua_data_bits':5,'ua_stop_bits':2},{'ua_data_bits':8,'ua_stop_bits':1.5},{'ua_data_bits':9},{'ua_oversampling':4}):assert status({**actual('LPC24XX_UM10237_4'),**bad})=='INVALID'
def fractional():return {**actual('LPC24XX_UM10237_4'),'ua_clock_hz':12000000,'ua_dlm':0,'ua_dll':4,'ua_divisor':4,'ua_divaddval':5,'ua_mulval':8,'ua_baud':12000000/(16*4*(1+5/8))}
def test_lpc_fractional_example_is_computed_not_nominal115200():
 x=fractional();assert status(x)=='VALID'
 for bad in({'ua_baud':115200},{'ua_divisor':5},{'ua_divaddval':8},{'ua_mulval':0},{'ua_dll':2,'ua_divisor':2,'ua_baud':12000000/(16*2*(1+5/8))}):assert status({**x,**bad})=='INVALID'
def test_lpc_integer_divider_disabled_fractional_small_divisor_legal():
 x={**fractional(),'ua_divaddval':0,'ua_mulval':1,'ua_dll':1,'ua_divisor':1,'ua_baud':750000};assert status(x)=='VALID'
 assert status({**x,'ua_dll':0,'ua_divisor':0})=='INVALID'
def test_lpc_hardware_flow_only_bound_uart1():
 x={**actual('LPC24XX_UM10237_4'),'ua_flow':'RTS_CTS'};assert status(x)=='UNVERIFIED'
 assert status({**x,'ua_port':1})=='VALID';assert status({**x,'ua_port':0})=='INVALID'
def test_start_parity_stop_occupied_periods_distinct_payload():
 x={**actual(),'ua_parity':'EVEN','ua_parity_bits':1,'ua_character_bits':11,'ua_characters':2,'ua_wire_bits':22,'ua_serialization_us':22/9600*1000000};assert status(x)=='VALID'
 for bad in({'ua_parity_bits':0},{'ua_character_bits':10},{'ua_wire_bits':16},{'ua_serialization_us':16/9600*1000000}):assert status({**x,**bad})=='INVALID'
def test_fractional_stop_occupied_time_counts_half_period():
 x={**actual('LPC24XX_UM10237_4'),'ua_data_bits':5,'ua_stop_bits':1.5,'ua_parity_bits':0,'ua_character_bits':7.5,'ua_characters':2,'ua_wire_bits':15};assert status(x)=='VALID'
 assert status({**x,'ua_wire_bits':16})=='INVALID'
def test_bounded_flow_not_wire_time_alone():
 x={**actual(),'ua_serialization_us':100,'ua_idle_us':10,'ua_flow_block_us':50,'ua_transfer_us':160};assert status(x)=='VALID'
 assert status({**x,'ua_transfer_us':159})=='INVALID'
 assert status({**x,'ua_flow':'XON_XOFF'})=='UNVERIFIED'
 assert status({**x,'ua_flow':'XON_XOFF','ua_flow_source':'synthetic'})=='VALID'
def test_signed_baud_error_is_not_universal_receiver_tolerance():
 x={**actual(),'ua_baud':9615,'ua_target_baud':9600,'ua_baud_error_percent':.15625};assert status(x)=='VALID'
 assert status({**x,'ua_baud_error_percent':.16})=='INVALID'
 assert status({**x,'ua_baud':9504,'ua_baud_error_percent':-1})=='VALID'
def test_peer_combined_clock_envelope_requires_own_tolerance():
 x={**actual(),'ua_local_error_percent':1,'ua_peer_error_percent':2,'ua_combined_error_percent':3,'ua_receiver_tolerance_percent':3};assert status(x)=='VALID'
 assert status({**x,'ua_receiver_tolerance_percent':2.99})=='INVALID'
 assert status({**x,'ua_combined_error_percent':2})=='INVALID'
def test_peer_verified_needs_actual_peer_framing_and_error_source():
 x={**actual(),'ua_peer_verified':True};assert status(x)=='UNVERIFIED'
 x.update(ua_peer_data_bits=8,ua_peer_parity='NONE',ua_peer_stop_bits=1,ua_error_source='synthetic',ua_combined_error_percent=1,ua_receiver_tolerance_percent=2);assert status(x)=='VALID'
 for bad in({'ua_peer_data_bits':9},{'ua_peer_parity':'EVEN'},{'ua_peer_stop_bits':2}):assert status({**x,**bad})=='INVALID'
def test_actual_fifo_and_service_distinct_software_octets():
 x={**actual(),'ua_rx_fifo':4,'ua_tx_fifo':4,'ua_rx_occupancy':3,'ua_arrival_characters':3,'ua_service_capacity':2,'ua_post_occupancy':4};assert status(x)=='VALID'
 for bad in({'ua_rx_fifo':5},{'ua_rx_occupancy':5},{'ua_post_occupancy':5},{'ua_service_capacity':1,'ua_post_occupancy':5}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ua_review_profile':'LPC24XX_UM10237_4','ua_rx_fifo':16,'ua_tx_fifo':16})=='VALID'
def test_autobaud_measurement_sync_not_fixed_nominal_baud():
 x={**actual(),'ua_autobaud':'COMPLETE','ua_autobaud_sync':85,'ua_autobaud_source':'synthetic'};assert status(x)=='VALID'
 assert status({**x,'ua_autobaud_sync':65})=='INVALID'
 assert status({**x,'ua_review_profile':'LPC24XX_UM10237_4','ua_autobaud_sync':65})=='VALID'
def test_entire_host_path_and_consumption_not_legal_uart_bits_only():
 x={**actual(),'ua_source_ms':1,'ua_path_ms':2,'ua_consumer_ms':3,'ua_e2e_ms':6,'ua_deadline_ms':6,'ua_age_ms':5,'ua_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'ua_e2e_ms':2},{'ua_deadline_ms':5},{'ua_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 x.update(ua_data_accepted=True);assert status(x)=='UNVERIFIED'
def test_source_reset_proposals_are_not115200_or_confirmed8n1_every_device():
 f={v['key']:v for v in registry.parameter_fields('uart')};assert [p['value']for p in f['ua_data_bits']['conditional_defaults']]==[8,5]
 for k in('ua_baud','ua_clock_hz','ua_brg','ua_receiver_tolerance_percent','ua_transfer_us','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
def test_sync_usart_requires_independent_path_not_pic_asynchronous():
 assert status({**actual(),'ua_mode':'SYNC_USART','ua_registered_source':'synthetic'})=='INVALID'
 assert status({**actual(),'ua_review_profile':'REGISTERED_ACTUAL','ua_mode':'SYNC_USART','ua_registered_source':'synthetic','ua_data_bits':32})=='VALID'
