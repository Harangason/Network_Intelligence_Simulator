import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.wifi import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():return{'wf_'+k:'synthetic-'+k for k in R.REQUIRED}
def status(x):return registry.validate_parameters('wifi',x)['status']
def test_wifi_no_universal_one_gigabit_frame_or_capacity():
 p=registry.profile('wifi');assert p['domain']=='generic_networking'and p['max_payload_bytes']is None and p['default_stack']==['wifi']
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'and p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status({**actual(),'bitrate':1000000000})=='INVALID';assert estimate_frame('wifi',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('wifi'),ids=lambda f:f['key'])
def test_each_wifi_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('phy,band,width',[('DSSS_HR','2_4_GHZ',22),('LEGACY_OFDM','5_GHZ',20),('HT','2_4_GHZ',40),('VHT','5_GHZ',160),('HE','6_GHZ',160),('EHT','6_GHZ',320)])
def test_generation_band_width_not_foreign_ethernet(phy,band,width):
 x={**actual(),'wf_phy':phy,'wf_band':band,'wf_width_mhz':width};assert status(x)=='VALID';assert status({**x,'wf_width_mhz':1000})=='INVALID'
def test_320mhz_not24_or5ghz():assert status({**actual(),'wf_phy':'EHT','wf_band':'5_GHZ','wf_width_mhz':320})=='INVALID'
@pytest.mark.parametrize('phy,gi,mcs',[('HT',.4,7),('VHT',.8,9),('HE',1.6,11),('EHT',3.2,13)])
def test_mcs_known_guard_and_generation(phy,gi,mcs):
 x={**actual(),'wf_phy':phy,'wf_mcs_known':True,'wf_mcs':mcs,'wf_gi_us':gi};assert status(x)=='VALID'
 assert status({**x,'wf_mcs_known':False})=='INVALID';assert status({**x,'wf_gi_us':4})=='INVALID'
def test_vht_group_streams_and_stbc():
 x={**actual(),'wf_phy':'VHT','wf_ppdu':'SU','wf_group_id':63,'wf_nss':4,'wf_stbc':True,'wf_nsts':8};assert status(x)=='VALID'
 for bad in({'wf_group_id':1},{'wf_nss':9},{'wf_nsts':4}):assert status({**x,**bad})=='INVALID'
def test_ht_index_is_not_vht_four_bit_index_limit():
 x={**actual(),'wf_phy':'HT','wf_mcs_known':True,'wf_mcs':32};assert status(x)=='VALID'
 assert status({**x,'wf_mcs':77})=='INVALID';assert status({**x,'wf_phy':'VHT'})=='INVALID'
def test_he_ru_not_whole_channel_or_unknown_capture():
 x={**actual(),'wf_phy':'HE','wf_ru_tones':26};assert status(x)=='VALID';assert status({**x,'wf_ru_tones':20})=='INVALID'
@pytest.mark.parametrize('ac,up',[('BK',1),('BE',0),('VI',5),('VO',7)])
def test_wmm_priority_mapping_not_wired_pcp_automatic(ac,up):
 x={**actual(),'wf_ac':ac,'wf_user_priority':up};assert status(x)=='VALID';assert status({**x,'wf_user_priority':8})=='INVALID'
def test_ecw_exponent_txop32_and_aifs():
 x={**actual(),'wf_ecwmin':4,'wf_ecwmax':10,'wf_cwmin':15,'wf_cwmax':1023,'wf_aifsn':3,'wf_slot_us':9,'wf_sifs_us':16,'wf_aifs_us':43,'wf_txop_units':47,'wf_txop_us':1504};assert status(x)=='VALID'
 for bad in({'wf_cwmin':4},{'wf_ecwmax':3},{'wf_aifs_us':34},{'wf_txop_us':47}):assert status({**x,**bad})=='INVALID'
def test_beacon_and_fragment_source_units():
 x={**actual(),'wf_beacon_tu':100,'wf_beacon_ms':102.4,'wf_fragment_threshold':-1};assert status(x)=='VALID'
 for bad in({'wf_beacon_ms':100},{'wf_fragment_threshold':0},{'wf_fragment_threshold':255}):assert status({**x,**bad})=='INVALID'
def test_msdu_mpdu_cipher_fcs_separated():
 x={**actual(),'wf_phy':'VHT','wf_aggregation':'NONE','wf_msdu_bytes':2304,'wf_mac_header_bytes':26,'wf_crypto_bytes':16,'wf_fcs_bytes':4,'wf_mpdu_bytes':2350,'wf_max_mpdu_bytes':3895};assert status(x)=='VALID'
 for bad in({'wf_msdu_bytes':2305},{'wf_fcs_bytes':0},{'wf_mpdu_bytes':2304},{'wf_max_mpdu_bytes':1500}):assert status({**x,**bad})=='INVALID'
def test_dmg_not2304_limit_and_requires_own_path():
 x={**actual(),'wf_phy':'DMG','wf_registered_source':'synthetic','wf_msdu_bytes':7920};assert status(x)=='VALID';assert status({**x,'wf_msdu_bytes':7921})=='INVALID'
@pytest.mark.parametrize('phy,exp,buf',[('HT',3,64),('VHT',7,64),('HE',7,256),('EHT',7,1024)])
def test_ampdu_bytes_and_reordering_buffer_generation(phy,exp,buf):
 x={**actual(),'wf_phy':phy,'wf_ampdu_limit_base':True,'wf_ampdu_exp':exp,'wf_max_ampdu_bytes':2**(13+exp)-1,'wf_ampdu_bytes':8000,'wf_ba_buffer_frames':buf};assert status(x)=='VALID'
 assert status({**x,'wf_ba_buffer_frames':buf+1})=='INVALID';assert status({**x,'wf_max_ampdu_bytes':8000})=='INVALID'
def test_actual_function_deadline_not_association_or_mac_ack():
 x={**actual(),'wf_source_ms':1,'wf_transport_ms':2,'wf_use_ms':3,'wf_e2e_ms':6,'wf_deadline_ms':6,'wf_age_ms':4,'wf_freshness_ms':4,'wf_path_verified':True,'wf_observation_source':'synthetic','wf_data_accepted':True,'wf_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in({'wf_e2e_ms':2},{'wf_deadline_ms':5},{'wf_outcome':'MAC_ACK_ONLY'},{'wf_age_ms':5}):assert status({**x,**bad})=='INVALID'
def test_known_source_baselines_qualified_role_and_edition():
 f={v['key']:v for v in registry.parameter_fields('wifi')};assert f['wf_txop_units']['conditional_defaults'][0]['when']['wf_role']=='STA';assert f['wf_beacon_tu']['conditional_defaults'][0]['value']==100
 for k in('wf_phy','wf_mcs','wf_air_us','wf_regulatory_source','wf_channel','payload_bytes'):assert'default'not in f[k]and'conditional_defaults'not in f[k]
