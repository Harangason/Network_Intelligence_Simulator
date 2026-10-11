"""SPI clock/mode/electrical/transaction evidence without fabricated hardware."""
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import spi as R
from backend.engineering.capacity.calculators import estimate_frame
def actual():
 x={'spi_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(spi_controller_profile='REGISTERED_DEVICE',spi_bus_variant='SPI_SINGLE',spi_role='CONTROLLER',bitrate_bps=1000000)
 return x
def status(x):return registry.validate_parameters('spi',x)['status']
def evidence():return dict(master_node_id='controller',chip_select='CS0',word_length_bits=8,duplex_mode='FULL_DUPLEX',cpol=0,cpha=0,cs_setup_bound_us=2,inter_transfer_gap_us=1,transfer_bits_bound=64,bitrate_bps=1000000,source='synthetic total device transaction envelope',confirmed=True)

def test_spi_device_clock_and_supported_conservative_executor():
 p=registry.profile('spi');assert p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_AVAILABLE' and p['capacity_evidence']['requires_confirmed_device_parameters']
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('spi')};assert not set(R.REMOVED)&set(f)
 for k in('bitrate','payload_bytes','spi_mode','spi_word_bits','spi_controller_max_bps'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 assert status({**actual(),'nominal_bitrate_bps':500000})=='INVALID'
 assert estimate_frame('SPI',8,{'local_timing_evidence':evidence()}).transmission_time_s==pytest.approx(.000067)

@pytest.mark.parametrize('field',registry.parameter_fields('spi'),ids=lambda f:f['key'])
def test_every_spi_field_type_and_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('mode,pol,pha,edge',[(0,0,0,'RISING'),(1,0,1,'FALLING'),(2,1,0,'FALLING'),(3,1,1,'RISING')])
def test_all_four_clock_modes_not_universal_mode0(mode,pol,pha,edge):
 x={**actual(),'spi_mode':mode,'spi_cpol':pol,'spi_cpha':pha,'spi_sample_edge':edge,'spi_change_edge':'FALLING'if edge=='RISING'else'RISING'};assert status(x)=='VALID'
 for bad in({'spi_cpol':1-pol},{'spi_cpha':1-pha},{'spi_change_edge':edge}):assert status({**x,**bad})=='INVALID'

def test_three_distinct_clock_limits_not50mhz_universal():
 x={**actual(),'bitrate_bps':80000000,'spi_controller_max_bps':100000000,'spi_target_max_bps':80000000,'spi_physical_max_bps':90000000};assert status(x)=='VALID'
 assert status({**x,'bitrate_bps':80000001})=='INVALID'
 assert status({**x,'spi_controller_max_bps':70000000})=='INVALID'

def test_clock_edges_full_period_and_actual_setup_hold_windows():
 x={**actual(),'bitrate_bps':10000000,'spi_period_ns':100,'spi_high_ns':40,'spi_low_ns':40,'spi_rise_ns':10,'spi_fall_ns':10,'spi_minimum_high_ns':40,'spi_minimum_low_ns':40,'spi_data_setup_ns':5,'spi_minimum_setup_ns':5,'spi_data_hold_ns':5,'spi_minimum_hold_ns':5};assert status(x)=='VALID'
 for bad in({'spi_period_ns':90},{'spi_high_ns':39},{'spi_data_setup_ns':4},{'spi_data_hold_ns':4}):assert status({**x,**bad})=='INVALID'
 x.update(spi_sample_window_ns=50,spi_output_valid_ns=25,spi_path_delay_ns=15,spi_jitter_ns=5);assert status(x)=='VALID'
 assert status({**x,'spi_sample_window_ns':49})=='INVALID'

@pytest.mark.parametrize('kind',['setup','hold','inactive'])
def test_cs_guard_device_minimums_not_clock_serialization(kind):
 x={**actual(),'spi_cs_'+kind+'_ns':100,'spi_minimum_cs_'+kind+'_ns':100};assert status(x)=='VALID'
 assert status({**x,'spi_cs_'+kind+'_ns':99})=='INVALID'

def test_full_duplex_clock_pulses_not_tx_plus_rx():
 x={**actual(),'spi_duplex':'FULL_DUPLEX','spi_word_bits':8,'spi_words':2,'spi_data_bits':16,'spi_command_bits':8,'spi_address_bits':24,'spi_dummy_bits':8,'spi_transfer_clock_bits':56,'spi_tx_bits':16,'spi_rx_bits':16,'spi_serialized_us':56};assert status(x)=='VALID'
 assert status({**x,'spi_transfer_clock_bits':72})=='INVALID'
 assert status({**x,'spi_duplex':'HALF_DUPLEX'})=='INVALID'
 assert status({**x,'spi_rx_bits':17})=='INVALID'

def test_whole_transaction_guards_gaps_and_ready_wait():
 x={**actual(),'spi_transfer_clock_bits':64,'spi_serialized_us':64,'spi_setup_bound_us':2,'spi_hold_bound_us':3,'spi_gap_bound_us':10,'spi_transaction_bound_us':79,'spi_ready_enabled':True,'spi_ready_wait_us':10};assert status(x)=='VALID'
 assert status({**x,'spi_transaction_bound_us':78})=='INVALID';assert status({**x,'spi_ready_wait_us':11})=='INVALID'
 assert status({k:v for k,v in x.items()if k!='spi_hold_bound_us'})=='UNVERIFIED'

def test_pic32_actual_pbclk_divider_zero_and_511_no_cpu_or_table_guess():
 x={**actual(),'spi_controller_profile':'PIC32MX_DS61106E','spi_peripheral_clock_bps':40000000,'spi_brg':0,'bitrate_bps':20000000,'spi_word_bits':32,'spi_bit_order':'MSB_FIRST','spi_cpol':0,'spi_cpha':0,'spi_pic32_ckp':0,'spi_pic32_cke':1,'spi_framed':False};assert status(x)=='VALID'
 for bad in({'bitrate_bps':10000000},{'spi_word_bits':24},{'spi_bit_order':'LSB_FIRST'},{'spi_pic32_cke':0}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spi_brg':511,'bitrate_bps':39062.5})=='VALID'
 assert status({**x,'spi_role':'TARGET','spi_pic32_smp':1})=='INVALID'
 assert status({**x,'spi_changing_width':True,'spi_idle':False})=='INVALID'
 assert status({**x,'spi_framed':True,'spi_pic32_cke':0})=='VALID'

def test_imx_two_stage_clock_not_source_table_default():
 x={**actual(),'spi_controller_profile':'IMX1_AN3020','spi_imx_pll_bps':96000000,'spi_imx_pclk_div':4,'spi_imx_spi_div':16,'bitrate_bps':1500000};assert status(x)=='VALID'
 assert status({**x,'bitrate_bps':96000000})=='INVALID';assert status({**x,'spi_imx_spi_div':12})=='INVALID'

@pytest.mark.parametrize('k,bad',[('cpol',.5),('cpol',True),('cpha',False),('word_length_bits',8.5),('word_length_bits',True),('transfer_bits_bound',64.5),('bitrate_bps',True),('chip_select',1),('source',1),('confirmed','true')])
def test_invalid_local_device_types_never_coerce_to_timing(k,bad):
 e={**evidence(),k:bad};assert R.evidence_issues(e,8)
 assert estimate_frame('SPI',8,{'local_timing_evidence':e}).to_dict()['transmission_time_s'] is None

@pytest.mark.parametrize('key,local_key,value',[('bitrate_bps','bitrate_bps',2000000),('spi_cpol','cpol',1),('spi_cpha','cpha',1),('spi_word_bits','word_length_bits',16),('spi_duplex','duplex_mode','HALF_DUPLEX'),('spi_chip_select','chip_select','CS1')])
def test_conflicting_bound_device_transaction_cannot_be_reused(key,local_key,value):
 assert estimate_frame('SPI',8,{'local_timing_evidence':evidence(),key:value}).to_dict()['transmission_time_s'] is None

def test_quad_not_sized_with_single_line_clock_model():
 assert estimate_frame('SPI',8,{'local_timing_evidence':evidence(),'spi_bus_variant':'REGISTERED_DUAL_QUAD'}).to_dict()['transmission_time_s'] is None

def test_actual_local_schema_fields_each_have_source_and_no_defaults():
 for f in R.local_fields():assert f['source']in R.SOURCES and 'default'not in f and f['default_status']=='UNKNOWN'

def test_functional_acceptance_not_implied_by_busy_window():
 x={**actual(),'spi_source_bound_ms':1,'spi_busy_bound_ms':2,'spi_consumer_bound_ms':3,'spi_e2e_bound_ms':6,'spi_e2e_limit_ms':6,'spi_age_ms':5,'spi_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'spi_e2e_bound_ms':2},{'spi_e2e_limit_ms':5},{'spi_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spi_data_accepted':True})=='UNVERIFIED'
 assert status({**x,'spi_data_accepted':True,'spi_outcome':'OVERFLOW'})=='INVALID'
