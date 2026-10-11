import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.wireless_m_bus import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():return{'wm_'+k:'synthetic-'+k for k in R.REQUIRED}
def status(x):return registry.validate_parameters('wireless_m_bus',x)['status']
def test_wireless_is_separate_wired_mbus_or_can():
 p=registry.profile('wireless_m_bus');assert p['domain']=='generic_networking'and p['max_payload_bytes']is None and p['default_stack']==['wireless_m_bus']
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'and p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status({**actual(),'bitrate':100000})=='INVALID';assert estimate_frame('wireless_m_bus',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('wireless_m_bus'),ids=lambda f:f['key'])
def test_every_field_type_and_outer_bound(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('mode,coding,rate,freq',[(k,*v)for k,v in R.MODES.items()])
def test_each_mode_source_baseline_not_can_defaults(mode,coding,rate,freq):
 x={**actual(),'wm_mode':mode,'wm_direction':'METER_TO_OTHER','wm_coding':coding,'wm_chip_rate_cps':rate,'wm_centre_mhz':freq};assert status(x)=='VALID';assert status({**x,'wm_coding':'REGISTERED_ACTUAL'})=='INVALID'
@pytest.mark.parametrize('mode,coding,rate,freq',[('T2','MANCHESTER',32768,868.3),('C2','NRZ',50000,869.525)])
def test_bidirectional_downlink_phy_is_not_uplink(mode,coding,rate,freq):
 x={**actual(),'wm_mode':mode,'wm_direction':'OTHER_TO_METER','wm_coding':coding,'wm_chip_rate_cps':rate,'wm_centre_mhz':freq};assert status(x)=='VALID';assert status({**x,'wm_centre_mhz':868.95})=='INVALID'
@pytest.mark.parametrize('mode',['S1','S1M','T1','C1','N1','F1'])
def test_unidirectional_cannot_reply(mode):assert status({**actual(),'wm_mode':mode,'wm_direction':'OTHER_TO_METER'})=='INVALID'
@pytest.mark.parametrize('coding,factor',[('MANCHESTER',.5),('THREE_OF_SIX',2/3)])
def test_chip_rate_not_application_information_rate(coding,factor):
 x={**actual(),'wm_coding':coding,'wm_chip_rate_cps':100000,'wm_data_bps':100000*factor};assert status(x)=='VALID';assert status({**x,'wm_data_bps':100000})=='INVALID'
@pytest.mark.parametrize('index',list(R.NINDEX))
def test_every_n_index_channel_spacing_frequency_and_rate(index):
 bps,freq,spacing,last=R.NINDEX[index];bits=2 if bps==19200 else 1
 x={**actual(),'wm_mode':'N2','wm_n_index':index,'wm_channel':last,'wm_centre_mhz':freq+last*spacing*.001,'wm_spacing_khz':spacing,'wm_data_bps':bps,'wm_chip_rate_cps':bps/bits,'wm_symbol_bits':bits,'wm_coding':'NRZ','wm_hardware':'EFR32_SERIES2'};assert status(x)=='VALID'
 for bad in({'wm_channel':last+1},{'wm_data_bps':bps+1},{'wm_centre_mhz':freq+1}):assert status({**x,**bad})=='INVALID'
def test_series1_t_needs_software_postamble_and_series2_not_fake_workaround():
 x={**actual(),'wm_hardware':'EFR32_SERIES1','wm_coding':'THREE_OF_SIX','wm_direction':'METER_TO_OTHER','wm_software_postamble':True};assert status(x)=='VALID';assert status({**x,'wm_software_postamble':False})=='INVALID'
@pytest.mark.parametrize('data,blocks',[(10,1),(11,2),(26,2),(27,3),(256,17)])
def test_frame_a_first10_then16_crc_length(data,blocks):
 x={**actual(),'wm_frame':'A','wm_datagram_bytes':data,'wm_l_field':data-1,'wm_crc_blocks':blocks,'wm_crc_bytes':2*blocks,'wm_radio_bytes':data+2*blocks};assert status(x)=='VALID'
 assert status({**x,'wm_l_field':data+2*blocks-1})=='INVALID';assert status({**x,'wm_crc_blocks':blocks+1})=='INVALID'
@pytest.mark.parametrize('data,blocks',[(10,1),(125,1),(126,2),(252,2)])
def test_frame_b_length_counts_crc_and_max_two_blocks(data,blocks):
 x={**actual(),'wm_frame':'B','wm_datagram_bytes':data,'wm_crc_blocks':blocks,'wm_crc_bytes':2*blocks,'wm_radio_bytes':data+2*blocks,'wm_l_field':data+2*blocks-1};assert status(x)=='VALID';assert status({**x,'wm_l_field':data-1})=='INVALID'
def test_encoded_chips_crc_sync_preamble_postamble_not_just_payload():
 x={**actual(),'wm_coding':'THREE_OF_SIX','wm_radio_bytes':28,'wm_preamble_chips':48,'wm_sync_chips':0,'wm_postamble_chips':8,'wm_encoded_chips':392,'wm_chip_rate_cps':100000,'wm_nominal_air_us':3920};assert status(x)=='VALID'
 for bad in({'wm_encoded_chips':224},{'wm_nominal_air_us':2240}):assert status({**x,**bad})=='INVALID'
def test_oms_cc_reserved_bits_and_dll_only():
 x={**actual(),'wm_edition':'OMS5_0_1','wm_frame':'A','wm_dll_bytes':10,'wm_cc_raw':128};assert status(x)=='VALID'
 assert status({**x,'wm_cc_raw':137})=='INVALID';assert status({**x,'wm_dll_bytes':3})=='INVALID'
def test_historical_response_window_edition_qualified_not_function_deadline():
 x={**actual(),'wm_edition':'TI_AN121_2012_DRAFT','wm_mode':'T2','wm_direction':'OTHER_TO_METER','wm_response_ms':2,'wm_fac_n':3,'wm_fac_ms':3000,'wm_fac_timeout_s':25};assert status(x)=='VALID'
 for bad in({'wm_response_ms':100},{'wm_fac_n':7},{'wm_fac_ms':100},{'wm_fac_timeout_s':24}):assert status({**x,**bad})=='INVALID'
def test_function_acceptance_requires_source_to_use_age_path_not_crc():
 x={**actual(),'wm_source_ms':1,'wm_transport_ms':2,'wm_use_ms':3,'wm_e2e_ms':6,'wm_deadline_ms':6,'wm_age_ms':4,'wm_freshness_ms':4,'wm_data_accepted':True,'wm_path_verified':True,'wm_observation_source':'synthetic','wm_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in({'wm_e2e_ms':2},{'wm_deadline_ms':5},{'wm_age_ms':5},{'wm_outcome':'CRC_ONLY'}):assert status({**x,**bad})=='INVALID'
def test_nominal_literature_only_mode_direction_no_radio_configuration_confirmation():
 f={v['key']:v for v in registry.parameter_fields('wireless_m_bus')};assert len(f['wm_chip_rate_cps']['conditional_defaults'])>10
 for k in('wm_mode','wm_regulatory_source','wm_l_field','wm_security_source','wm_transport_ms','payload_bytes'):assert'default'not in f[k]and'conditional_defaults'not in f[k]

@pytest.mark.parametrize('mode,pre,sync',[('S1',576,0),('S2',48,0),('R2',96,0),('C2',32,32),('N2',16,16)])
def test_selected_historical_preamble_is_not_payload(mode,pre,sync):
 x={**actual(),'wm_edition':'TI_AN121_2012_DRAFT','wm_mode':mode,'wm_preamble_chips':pre,'wm_sync_chips':sync};assert status(x)=='VALID';assert status({**x,'wm_preamble_chips':pre-1})=='INVALID'
def test_frame_b_datagram_upper_bound_even_without_lfield():assert status({**actual(),'wm_frame':'B','wm_datagram_bytes':253})=='INVALID'
@pytest.mark.parametrize('mode,lo',[('S2',3),('R2',3),('C2',999.5),('F2',999.5)])
def test_selected_historical_slow_window(mode,lo):
 x={**actual(),'wm_edition':'TI_AN121_2012_DRAFT','wm_mode':mode,'wm_direction':'OTHER_TO_METER','wm_response_mode':'SLOW','wm_response_ms':lo};assert status(x)=='VALID';assert status({**x,'wm_response_ms':lo-1})=='INVALID'


@pytest.mark.parametrize('bps,allowed,bad',[(2400,7,2),(4800,13,3),(19200,3,7)])
def test_historical_ng_frequent_access_is_not_na_to_nf(bps,allowed,bad):
 x={**actual(),'wm_edition':'TI_AN121_2012_DRAFT','wm_mode':'N2','wm_data_bps':bps,'wm_fac_n':allowed}
 assert status(x)=='VALID'
 assert status({**x,'wm_fac_n':bad})=='INVALID'
 assert status({k:v for k,v in x.items() if k!='wm_data_bps'})=='UNVERIFIED'

def test_r2_meter_frequency_is_channel_dependent_not_other_device_frequency():
 f={v['key']:v for v in registry.parameter_fields('wireless_m_bus')}
 assert not any(v['when'].get('wm_mode')=='R2' and v['when'].get('wm_direction')=='METER_TO_OTHER' for v in f['wm_centre_mhz']['conditional_defaults'])
