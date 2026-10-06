"""UWB packet, device family, ranging and application acceptance stay distinct."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.uwb import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame

def actual(profile='DW1000_DS2_23_API2_4'):
 x={'uw_'+k:'synthetic-'+k for k in R.REQUIRED};x['uw_review_profile']=profile
 return x
def status(x):return registry.validate_parameters('uwb',x)['status']
def test_industry_neutral_no_advertised_rate_or_capacity_as_evidence():
 p=registry.profile('uwb');assert p['domain']=='generic_networking'and p['max_payload_bytes']is None and p['default_stack']==['uwb']
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 assert status({**actual(),'bitrate':27000000})=='INVALID'
 assert estimate_frame('uwb',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('uwb'),ids=lambda f:f['key'])
def test_every_exported_type_and_outer_bound(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('mode,rate',[('RATE_110K',110000),('RATE_850K',850000),('RATE_6M8',6810000)])
def test_nominal_user_rate_distinct_from_symbol_rate(mode,rate):
 x={**actual(),'uw_data_mode':mode,'uw_data_bps':rate};assert status(x)=='VALID';assert status({**x,'uw_data_bps':rate+1})=='INVALID'
def test_device_family_rejects_foreign_channel_and110k_mode():
 x=actual('DW3000_UM1_1');assert status({**x,'uw_channel':9})=='VALID'
 assert status({**x,'uw_channel':1})=='INVALID';assert status({**x,'uw_data_mode':'RATE_110K'})=='INVALID'
 assert status({**actual(),'uw_channel':9})=='INVALID'
@pytest.mark.parametrize('ch',list(R.CHANNELS))
def test_complex_channel_frequency_bandwidth_code_match(ch):
 profile='DW3000_UM1_1'if ch==9 else'DW1000_DS2_23_API2_4';cf,bw,c16,c64=R.CHANNELS[ch]
 x={**actual(profile),'uw_channel':ch,'uw_centre_mhz':cf,'uw_bandwidth_mhz':bw,'uw_prf_mhz':64,'uw_dps':False,'uw_tx_code':c64[0]};assert status(x)=='VALID'
 for bad in({'uw_centre_mhz':cf+1},{'uw_bandwidth_mhz':bw+1},{'uw_tx_code':1}):assert status({**x,**bad})=='INVALID'
def test_code_requires_prf_channel_and_explicit_static_or_dynamic_selection():
 assert status({**actual(),'uw_tx_code':9})=='UNVERIFIED'
 x={**actual(),'uw_channel':5,'uw_prf_mhz':64,'uw_dps':True,'uw_dps_source':'synthetic','uw_tx_code':13};assert status(x)=='VALID'
 assert status({**x,'uw_prf_mhz':16})=='INVALID';assert status({**x,'uw_peer_code':14})=='INVALID'
@pytest.mark.parametrize('symbols,pac',[(64,8),(128,8),(256,16),(512,16),(1024,32),(1536,64),(2048,64),(4096,64)])
def test_recommendation_pac_and_timeout_are_conditional(symbols,pac):
 x={**actual(),'uw_proposal_mode':'SOURCE_RECOMMENDED','uw_preamble_mode':'LEGACY_PSR','uw_preamble_symbols':symbols,'uw_pac_symbols':pac,'uw_sfd_symbols':8,'uw_sfd_timeout_symbols':symbols+9-pac};assert status(x)=='VALID'
 assert status({**x,'uw_sfd_timeout_symbols':0})=='INVALID';assert status({**x,'uw_pac_symbols':symbols})=='INVALID'
def test_fine_preamble_is_dw3000_groups8_not_any_arbitrary_length():
 x={**actual('DW3000_UM1_1'),'uw_preamble_mode':'FINE_MULTIPLE8','uw_fine_preamble_groups':4,'uw_preamble_symbols':32};assert status(x)=='VALID'
 assert status({**x,'uw_preamble_symbols':33})=='INVALID';assert status({**x,'uw_review_profile':'DW1000_DS2_23_API2_4'})=='INVALID'
def test_phr_fast_mode_device_specific():
 x={**actual('DW3000_UM1_1'),'uw_data_mode':'RATE_6M8','uw_phr_rate':'MATCH_DATA','uw_phr_symbol_ns':128.21};assert status(x)=='VALID'
 assert status({**x,'uw_phr_rate':'STANDARD'})=='INVALID';assert status({**x,'uw_review_profile':'DW1000_DS2_23_API2_4'})=='INVALID'
def test_full_psdu_includes_headers_fcs_and_rs_coding():
 x={**actual(),'uw_packet_config':'SP0','uw_phr_mode':'STANDARD_127','uw_mac_header_bytes':9,'uw_security_header_bytes':0,'uw_data_bytes':116,'payload_bytes':116,'uw_fcs_bytes':2,'uw_psdu_bytes':127,'uw_rs_blocks':4,'uw_rs_parity_bits':192,'uw_data_coded_bits':1208};assert status(x)=='VALID'
 for bad in({'uw_psdu_bytes':128},{'uw_fcs_bytes':0},{'uw_data_bytes':127},{'uw_rs_blocks':3},{'uw_data_coded_bits':1016}):assert status({**x,**bad})=='INVALID'
def test_extended1023_is_matched_nonstandard_phy_not_application_max():
 x={**actual(),'uw_phr_mode':'EXTENDED_1023','uw_extended_peer':True,'uw_registered_source':'synthetic','uw_psdu_bytes':1023};assert status(x)=='VALID'
 assert status({**x,'uw_extended_peer':False})=='INVALID';assert status({**x,'uw_psdu_bytes':1024})=='INVALID'
def sts():return{**actual('DW3000_UM1_1'),'uw_packet_config':'SP1','uw_sts_profile':'DEVICE_PROGRAMMABLE','uw_sts_length_units':128,'uw_cps_len_raw':15,'uw_sts_source':'synthetic','uw_sts_counter_increment':64,'uw_secure_ranging':True,'uw_sts_seed_aligned':True,'uw_sts_nonce_fresh':True,'uw_cp_toast_ok':True,'uw_cia_done':True,'uw_acc_qual':77}
@pytest.mark.parametrize('bad',[{'uw_acc_qual':76},{'uw_sts_nonce_fresh':False},{'uw_cp_toast_ok':False},{'uw_cia_done':False},{'uw_sts_profile':'NONSECURE_SDC'},{'uw_cps_len_raw':14},{'uw_sts_counter_increment':128}])
def test_sts_timestamp_quality_nonce_alignment_and_nonsecure_sdc(bad):
 assert status(sts())=='VALID';assert status({**sts(),**bad})=='INVALID'
def test_sp3_has_sts_but_no_phr_or_mac_data():
 x={**sts(),'uw_packet_config':'SP3','uw_psdu_bytes':0,'uw_phr_bits':0,'uw_fcs_bytes':0,'uw_data_bytes':0,'uw_rs_blocks':0,'uw_rs_parity_bits':0,'uw_data_coded_bits':0};assert status(x)=='VALID';assert status({**x,'uw_psdu_bytes':10})=='INVALID'
def test_host_single_sided_clock_correction_and_units():
 x={**actual(),'uw_ranging_model':'SS_UNCOMPENSATED','uw_round1_ns':220,'uw_reply1_ns':200,'uw_tof_ns':10};assert status(x)=='VALID';assert status({**x,'uw_tof_ns':110})=='INVALID'
 x.update(uw_ranging_model='SS_CLOCK_COMPENSATED',uw_clock_offset_ratio=.01,uw_tof_ns=11);assert status(x)=='VALID'
def test_asymmetric_double_sided_formula_not_ignored_or_single_sided():
 x={**actual(),'uw_ranging_model':'DS_ASYMMETRIC','uw_round1_ns':220,'uw_round2_ns':420,'uw_reply1_ns':400,'uw_reply2_ns':200,'uw_ds_numerator_ns2':12400,'uw_ds_denominator_ns':1240,'uw_tof_ns':10};assert status(x)=='VALID'
 for bad in({'uw_ds_numerator_ns2':12000},{'uw_ds_denominator_ns':1239},{'uw_tof_ns':11}):assert status({**x,**bad})=='INVALID'
 x.pop('uw_reply2_ns');assert status(x)=='UNVERIFIED'
def test_range_accuracy_is_not_automatic10cm_or_application_acceptance():
 x={**actual(),'uw_range_verified':True,'uw_calibration_source':'synthetic','uw_ranging_source':'synthetic','uw_range_error_m':.15,'uw_range_tolerance_m':.2};assert status(x)=='VALID';assert status({**x,'uw_range_tolerance_m':.1})=='INVALID'
def test_application_acceptance_requires_full_bound_age_observation():
 x={**actual(),'uw_source_ms':1,'uw_transport_ms':2,'uw_use_ms':3,'uw_e2e_ms':6,'uw_deadline_ms':6,'uw_age_ms':4,'uw_freshness_ms':4,'uw_data_accepted':True,'uw_observation_source':'synthetic','uw_path_verified':True,'uw_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in({'uw_e2e_ms':2},{'uw_deadline_ms':5},{'uw_outcome':'RANGE_ONLY'},{'uw_age_ms':5}):assert status({**x,**bad})=='INVALID'
def test_only_edition_qualified_baselines_no_fake_airtime_or_location():
 f={v['key']:v for v in registry.parameter_fields('uwb')};assert len(f['uw_data_mode']['conditional_defaults'])>=3
 for k in('uw_regulatory_source','uw_antenna_tx_delay_ticks','uw_tof_ns','uw_air_us','uw_range_error_m','payload_bytes'):assert'default'not in f[k]and'conditional_defaults'not in f[k]
