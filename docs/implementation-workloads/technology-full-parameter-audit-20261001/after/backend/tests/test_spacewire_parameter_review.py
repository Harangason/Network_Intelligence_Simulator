"""Independent SpaceWire physical/symbol/credit/route boundaries."""
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import spacewire as R

def actual():
 x={'spw_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(spw_edition='ECSS_2019',spw_proposal_mode='ACTUAL_CONFIG',spw_minimum_capability='FULL_2M',spw_phy='SPW_LVDS',spw_state='RUN',spw_traffic='PACKET')
 return x
def status(x):return registry.validate_parameters('spacewire',x)['status']

def test_spacewire_own_symbols_without_foreign_rate_payload_or_default():
 p=registry.profile('spacewire');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING' and p['default_stack']==['spacewire']
 assert status(actual())=='VALID' and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('spacewire')};assert not set(R.REMOVED)&set(f)
 for k in('payload_bytes','spw_device_max_bps','spw_peer_receive_max_bps','spw_logical_address','spw_tx_credit'):
  assert 'default'not in f[k] and 'conditional_defaults'not in f[k]
 assert status({**actual(),'nominal_bitrate_bps':500000})=='INVALID'
 assert status({**actual(),'local_timing_evidence':{'confirmed':True}})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('spacewire'),ids=lambda f:f['key'])
def test_each_spacewire_field_type_and_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('state',['ERROR_RESET','ERROR_WAIT','READY','STARTED','CONNECTING'])
def test_initial_rate_9_to_11_mbps_not_run_rate(state):
 x={**actual(),'spw_state':state,'spw_tx_bps':10000000};assert status(x)=='VALID'
 assert status({**x,'spw_tx_bps':2000000})=='INVALID'
 assert status({**x,'spw_tx_bps':11000001})=='INVALID'

def test_run_min_device_max_and_different_opposite_direction():
 x={**actual(),'spw_device_min_bps':2000000,'spw_device_max_bps':500000000,'spw_peer_receive_max_bps':400000000,'spw_tx_bps':300000000,'spw_rx_bps':2000000,'spw_local_receive_max_bps':100000000};assert status(x)=='VALID'
 for bad in({'spw_tx_bps':400000001},{'spw_rx_bps':100000001},{'spw_tx_bps':1999999}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spw_minimum_capability':'LIMITED_ACTUAL','spw_device_min_bps':8000000})=='VALID'
 assert status({**x,'spw_minimum_capability':'LIMITED_ACTUAL','spw_device_min_bps':12000000})=='INVALID'

@pytest.mark.parametrize('bad',[{'spw_encoding':'UART'},{'spw_parity':'EVEN'},{'spw_bit_order':'MSB_FIRST'},{'spw_arbitration':'UNFAIR'}])
def test_encoding_and_router_fairness(bad):assert status({**actual(),**bad})=='INVALID'

def test_lvttl_short_internal_not_lvds_connector():
 x={**actual(),'spw_phy':'SPW_LVTTL','spw_connector':'OTHER','spw_cable_m':.299};assert status(x)=='VALID'
 assert status({**x,'spw_cable_m':.3})=='INVALID';assert status({**x,'spw_connector':'TYPE_A'})=='INVALID'

@pytest.mark.parametrize('k,good,bad',[('termination_ohm',100,89),('tx_cm_v',1.2,1.5),('tx_diff_peak_v',.3,.455),('tx_single_peak_v',.15,.228),('tx_cm_imbalance_v',.049,.05),('tx_single_imbalance_v',.049,.05),('tx_dynamic_imbalance_v',.149,.15),('ground_diff_v',.999,1)])
def test_lvds_explicit_fixture_limits(k,good,bad):
 assert status({**actual(),'spw_'+k:good})=='VALID';assert status({**actual(),'spw_'+k:bad})=='INVALID'

def test_skew_margin_and_monotonic_edges_fraction_of_actual_interval():
 x={**actual(),'spw_tx_bps':100000000,'spw_bit_ui_ps':10000,'spw_tx_skew_ps':1000,'spw_cable_skew_ps':1000,'spw_cable_jitter_ps':500,'spw_receiver_min_sep_ps':500,'spw_minimum_ui_ps':3300,'spw_rise_ps':260,'spw_fall_ps':2999,'spw_monotonic':True};assert status(x)=='VALID'
 for bad in({'spw_minimum_ui_ps':3000},{'spw_bit_ui_ps':3300},{'spw_rise_ps':259},{'spw_fall_ps':3000},{'spw_monotonic':False}):assert status({**x,**bad})=='INVALID'
 assert status({k:v for k,v in x.items()if k!='spw_cable_jitter_ps'})=='UNVERIFIED'

def test_signed_receiver_levels_and_coupled_pin_values():
 x={**actual(),'spw_logic':True,'spw_rx_diff_v':.3,'spw_rx_cm_v':1.2,'spw_rx_p_v':1.35,'spw_rx_n_v':1.05,'spw_tx_diff_peak_v':.3,'spw_ringing_abs_v':.12};assert status(x)=='VALID'
 for bad in({'spw_rx_diff_v':.1},{'spw_rx_p_v':1.2},{'spw_ringing_abs_v':.121},{'spw_rx_cm_v':2.4}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spw_logic':False,'spw_rx_diff_v':-.3,'spw_rx_p_v':1.05,'spw_rx_n_v':1.35})=='VALID'

@pytest.mark.parametrize('k,good,bad',[('disconnect_ns',850,727),('disconnect_ns',1000,1001),('error_reset_us',6.4,5.81),('error_reset_us',7.22,7.23),('error_wait_us',12.8,11.63),('error_wait_us',14.33,14.34)])
def test_link_detection_and_state_timing(k,good,bad):
 assert status({**actual(),'spw_'+k:good})=='VALID';assert status({**actual(),'spw_'+k:bad})=='INVALID'

@pytest.mark.parametrize('symbol,bits',[('DATA',10),('FCT',4),('EOP',4),('EEP',4),('NULL',8),('BROADCAST',14)])
def test_symbol_encoding_counts_and_serialization(symbol,bits):
 x={**actual(),'spw_symbol':symbol,'spw_symbol_bits':bits,'spw_tx_bps':10000000,'spw_symbol_wire_ns':bits*100};assert status(x)=='VALID'
 assert status({**x,'spw_symbol_bits':bits+1})=='INVALID';assert status({**x,'spw_symbol_wire_ns':bits*100+1})=='INVALID'

def test_packet_address_headers_and_eop_are_not_generic_65535_limit():
 x={**actual(),'payload_bytes':100000,'spw_address_bytes':2,'spw_higher_header_bytes':3,'spw_packet_data_chars':100005,'spw_packet_bits':1000054};assert status(x)=='VALID'
 assert status({**x,'spw_packet_bits':1000050})=='INVALID'
 assert status({**x,'payload_bytes':8})=='INVALID'
 assert status({k:v for k,v in x.items()if k!='payload_bytes'})=='UNVERIFIED'

def test_trace_compound_codes_not_double_counted_or_latency():
 x={**actual(),'spw_trace_data_chars':2,'spw_trace_controls':3,'spw_trace_nulls':4,'spw_trace_broadcasts':5,'spw_trace_bits':134,'spw_trace_wire_ns':13400,'spw_tx_bps':10000000};assert status(x)=='VALID'
 assert status({**x,'spw_trace_bits':146})=='INVALID';assert status({**x,'spw_trace_wire_ns':1})=='INVALID'
 x.update(spw_trace_data_chars=0,spw_trace_controls=0,spw_trace_nulls=0,spw_trace_broadcasts=0,spw_trace_bits=0,spw_trace_wire_ns=0);assert status(x)=='VALID'
 assert status({**x,'spw_trace_wire_ns':1})=='INVALID'

def test_credit_fct_grants_streaming_packet_and_intermediate_counters():
 x={**actual(),'spw_credit_before':16,'spw_fcts_received':10,'spw_nchars_sent':80,'spw_credit_after':16,'spw_tx_credit':16,'spw_next_nchars':16,'spw_rx_credit':24,'spw_rx_credit_max':32,'spw_rx_fifo_free':24,'spw_outstanding_fcts':7};assert status(x)=='VALID'
 for bad in({'spw_credit_after':15},{'spw_next_nchars':17},{'spw_rx_fifo_free':23},{'spw_outstanding_fcts':8}):assert status({**x,**bad})=='INVALID'
 assert status({**actual(),'spw_state':'ERROR_RESET','spw_tx_credit':1})=='INVALID'

def test_path_configuration_zero_valid_logical255_reserved():
 assert status({**actual(),'spw_addressing':'PATH','spw_path_port':0,'spw_router_ports':4})=='VALID'
 assert status({**actual(),'spw_addressing':'PATH','spw_path_port':5,'spw_router_ports':4})=='INVALID'
 assert status({**actual(),'spw_addressing':'LOGICAL','spw_logical_address':32})=='VALID'
 assert status({**actual(),'spw_addressing':'LOGICAL','spw_logical_address':255})=='INVALID'

def test_timecode_wrap_one_master_and_interrupt_ack_bit():
 x={**actual(),'spw_broadcast_kind':'TIME_CODE','spw_broadcast_type':0,'spw_broadcast_value':0,'spw_time_value':0,'spw_previous_time':63,'spw_time_valid':True,'spw_time_masters':1};assert status(x)=='VALID'
 for bad in({'spw_time_value':1},{'spw_time_masters':2},{'spw_broadcast_type':1}):assert status({**x,**bad})=='INVALID'
 x={**actual(),'spw_broadcast_kind':'INTERRUPT_ACK','spw_broadcast_type':2,'spw_interrupt_id':5,'spw_relay_register_bits':8,'spw_broadcast_value':37};assert status(x)=='VALID'
 assert status({**x,'spw_broadcast_value':5})=='INVALID';assert status({**x,'spw_relay_register_bits':5})=='INVALID'

def test_interrupt_ack_timeout_entire_network_handler_ack_chain():
 x={**actual(),'spw_interrupt_mode':'WITH_ACK','spw_interrupt_sources':1,'spw_interrupt_acknowledgers':1,'spw_interrupt_propagation_ns':100,'spw_ack_propagation_ns':200,'spw_ack_handler_max_ns':1000,'spw_ack_handler_actual_ns':500,'spw_interrupt_repeat_ns':1301,'spw_interrupt_timeout_ns':1301};assert status(x)=='VALID'
 for bad in({'spw_interrupt_repeat_ns':1300},{'spw_ack_handler_actual_ns':100},{'spw_ack_handler_actual_ns':1000},{'spw_interrupt_sources':2},{'spw_interrupt_acknowledgers':2}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spw_interrupt_mode':'INTERRUPT_ONLY','spw_interrupt_repeat_ns':101,'spw_interrupt_timeout_ns':101})=='VALID'

def test_functional_timing_source_route_consumer_and_freshness():
 x={**actual(),'spw_source_bound_ms':1,'spw_network_bound_ms':2,'spw_consumer_bound_ms':3,'spw_e2e_bound_ms':6,'spw_e2e_limit_ms':6,'spw_age_ms':5,'spw_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'spw_e2e_bound_ms':2},{'spw_e2e_limit_ms':5},{'spw_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spw_data_accepted':True})=='UNVERIFIED'
 assert status({**x,'spw_data_accepted':True,'spw_outcome':'EEP'})=='INVALID'

def test_literal_baseline_default_proposals_not_actual_evidence():
 f={v['key']:v for v in registry.parameter_fields('spacewire')}
 assert {v['value']for v in f['spw_tx_bps']['conditional_defaults']}=={2000000,10000000}
 assert f['spw_disconnect_ns']['conditional_defaults'][0]['value']==850
 for key in('spw_tx_bps','spw_disconnect_ns','spw_termination_ohm'):
  assert all(v['when']['spw_proposal_mode']=='SOURCE_BASELINE'for v in f[key]['conditional_defaults'])

@pytest.mark.parametrize('denominator',[0,-1,float('inf'),True])
def test_invalid_symbol_denominator_cannot_crash_or_pass(denominator):
 assert status({**actual(),'spw_symbol_bits':10,'spw_tx_bps':denominator,'spw_symbol_wire_ns':1000})=='INVALID'
