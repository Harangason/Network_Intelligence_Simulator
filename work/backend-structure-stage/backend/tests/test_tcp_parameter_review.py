"""TCP own negotiation/timing/algorithm scope, no automatic Ethernet capacity."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.tcp import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():
 x={'tcp_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(tcp_edition='RFC9293_2022',tcp_ip_version='IPV4')
 return x
def status(x):return registry.validate_parameters('tcp',x)['status']

def test_tcp_stream_has_no_foreign_clock_or65535byte_application_cap():
 p=registry.profile('tcp');assert p['max_payload_bytes']is None and p['default_stack']==['tcp']
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':100000000},{'mtu_bytes':1500},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('TCP',100000,actual()).to_dict()['transmission_time_s']is None

@pytest.mark.parametrize('f',registry.parameter_fields('tcp'),ids=lambda f:f['key'])
def test_every_tcp_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'

def test_header_options_and_pseudoheader_do_not_inflate_wire_tcp():
 x={**actual(),'tcp_header_bytes':32,'tcp_data_offset':8,'tcp_options_bytes':12,'tcp_data_bytes':100,'tcp_segment_bytes':132,'tcp_ip_protocol':6,'tcp_pseudoheader_bytes':12};assert status(x)=='VALID'
 for bad in({'tcp_data_offset':5},{'tcp_options_bytes':10},{'tcp_segment_bytes':144},{'tcp_ip_protocol':17},{'tcp_pseudoheader_bytes':40}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tcp_ip_version':'IPV6','tcp_pseudoheader_bytes':40})=='VALID'

def test_transmitted_reserved_zero_receiver_ignored_and_mandatory_checksum():
 x={**actual(),'tcp_phase':'SEND','tcp_reserved_bits':1};assert status(x)=='INVALID'
 assert status({**x,'tcp_phase':'RECEIVE'})=='VALID'
 assert status({**actual(),'tcp_checksum_verified':False})=='INVALID'
 assert status({**actual(),'tcp_padding_zero':False})=='INVALID'

def test_syn_fin_sequence_octets_wrap_and_byte_stream_not_socket_messages():
 x={**actual(),'tcp_sequence':4294967290,'tcp_syn':True,'tcp_fin':True,'tcp_syn_units':1,'tcp_fin_units':1,'tcp_data_bytes':8,'tcp_next_sequence':4};assert status(x)=='VALID'
 assert status({**x,'tcp_next_sequence':2})=='INVALID';assert status({**x,'tcp_syn_units':0})=='INVALID'

@pytest.mark.parametrize('version,mss',[('IPV4',536),('IPV6',1220)])
def test_mss_no_option_source_fallback_is_ip_specific(version,mss):
 x={**actual(),'tcp_ip_version':version,'tcp_mss_option_received':False,'tcp_mss_received':mss};assert status(x)=='VALID'
 assert status({**x,'tcp_mss_received':1460})=='INVALID'
 assert status({**x,'tcp_mss_option_received':True,'tcp_mss_received':1460})=='VALID'

def test_effective_mss_accounts_both_tcp_ip_options_and_peer_path_limit():
 x={**actual(),'tcp_mss_received':1460,'tcp_mms_s':1280,'tcp_mms_r':1480,'tcp_header_bytes':32,'tcp_ip_options_bytes':8,'tcp_effective_mss':1240,'tcp_mss_advertised':1460,'tcp_data_bytes':1240};assert status(x)=='VALID'
 for bad in({'tcp_effective_mss':1460},{'tcp_data_bytes':1241},{'tcp_mss_advertised':1461}):assert status({**x,**bad})=='INVALID'

@pytest.mark.parametrize('kind,length',[(2,4),(3,3),(8,10)])
def test_option_complete_lengths_not_fixed_frame_defaults(kind,length):
 x={**actual(),'tcp_option_kind':kind,'tcp_option_length':length};assert status(x)=='VALID'
 assert status({**x,'tcp_option_length':length-1})=='INVALID'
 assert status({**actual(),'tcp_option_kind':0,'tcp_option_length':1})=='INVALID'

def test_ws_both_offers_syn_unscaled_and_received_oversize_clamped():
 x={**actual(),'tcp_ws_negotiated':True,'tcp_ws_local_offer':True,'tcp_ws_peer_offer':True,'tcp_window_scale_received':255,'tcp_window_scale_effective':14,'tcp_window_wire':65535,'tcp_window_effective':1073725440,'tcp_syn':False};assert status(x)=='VALID'
 for bad in({'tcp_window_scale_effective':15},{'tcp_ws_peer_offer':False},{'tcp_window_effective':1073741824}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tcp_syn':True,'tcp_window_effective':65535})=='VALID'
 assert status({**x,'tcp_syn':True})=='INVALID'
 assert status({**actual(),'tcp_phase':'SEND','tcp_option_kind':3,'tcp_syn':False})=='INVALID'

def test_timestamp_negotiation_clock_recycle_and_stale_recent():
 x={**actual(),'tcp_ts_negotiated':True,'tcp_ts_local_offer':True,'tcp_ts_peer_offer':True,'tcp_rst':False,'tcp_timestamp_present':True,'tcp_timestamp_tick_s':.001,'tcp_timestamp_recycle_s':4294967.296,'tcp_msl_s':120};assert status(x)=='VALID'
 for bad in({'tcp_ts_peer_offer':False},{'tcp_timestamp_present':False},{'tcp_timestamp_recycle_s':120}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tcp_idle_s':2073601,'tcp_paws_recent_valid':True})=='INVALID'
 assert status({**x,'tcp_idle_s':2073601,'tcp_paws_recent_valid':False})=='VALID'

def test_time_wait_delayed_ack_and_one_lost_keepalive():
 x={**actual(),'tcp_state':'TIME_WAIT','tcp_msl_s':120,'tcp_time_wait_s':240,'tcp_delayed_ack_s':.499};assert status(x)=='VALID'
 assert status({**x,'tcp_time_wait_s':120})=='INVALID';assert status({**x,'tcp_delayed_ack_s':.5})=='INVALID'
 assert status({**actual(),'tcp_keepalive_enabled':True,'tcp_keepalive_failures':1,'tcp_connection_dead':True})=='INVALID'

def test_first_rtt_rto_and_source_recommended_floor_not_lan_clock_guess():
 x={**actual(),'tcp_rto_profile':'RFC6298_BASELINE','tcp_rto_phase':'FIRST_SAMPLE','tcp_rtt_sample_s':.1,'tcp_srtt_s':.1,'tcp_rttvar_s':.05,'tcp_clock_granularity_s':.01,'tcp_raw_rto_s':.3,'tcp_rto_s':1,'tcp_rto_cap_enabled':False};assert status(x)=='VALID'
 for bad in({'tcp_srtt_s':.05},{'tcp_rttvar_s':.1},{'tcp_raw_rto_s':.1},{'tcp_rto_s':.3},{'tcp_initial_rto_s':.5}):assert status({**x,**bad})=='INVALID'

def test_rttvar_uses_old_srtt_before_update():
 x={**actual(),'tcp_rto_phase':'SUBSEQUENT_SAMPLE','tcp_previous_srtt_s':.1,'tcp_previous_rttvar_s':.02,'tcp_rtt_sample_s':.2,'tcp_alpha':.125,'tcp_beta':.25,'tcp_srtt_s':.1125,'tcp_rttvar_s':.04};assert status(x)=='VALID'
 assert status({**x,'tcp_rttvar_s':.036875})=='INVALID';assert status({**x,'tcp_srtt_s':.2})=='INVALID'
 assert status({**x,'tcp_sample_retransmitted':True})=='UNVERIFIED'
 assert status({**x,'tcp_sample_retransmitted':True,'tcp_timestamp_unambiguous':False})=='INVALID'

def test_rto_backoff_honors_actual_optional_cap_without_inventing60seconds():
 x={**actual(),'tcp_rto_phase':'TIMEOUT','tcp_previous_rto_s':40,'tcp_rto_s':80,'tcp_rto_cap_enabled':False};assert status(x)=='VALID'
 assert status({**x,'tcp_rto_s':40})=='INVALID'
 assert status({**x,'tcp_rto_cap_enabled':True,'tcp_rto_max_s':60,'tcp_rto_s':60})=='VALID'
 assert status({**x,'tcp_rto_cap_enabled':True,'tcp_rto_max_s':59,'tcp_rto_s':59})=='INVALID'

def test_rwnd_is_not_cwnd_and_flight_size_not_window():
 x={**actual(),'tcp_cwnd_bytes':10000,'tcp_rwnd_bytes':4000,'tcp_flight_bytes':3000,'tcp_new_data_bytes':1000};assert status(x)=='VALID'
 assert status({**x,'tcp_new_data_bytes':1001})=='INVALID'
 assert status({**x,'tcp_flight_bytes':5000,'tcp_new_data_bytes':0})=='VALID'

@pytest.mark.parametrize('smss,segments',[(1095,4),(1096,3),(2190,3),(2191,2)])
def test_reno_initial_window_exact_boundaries_not_iw10(smss,segments):
 x={**actual(),'tcp_iw_profile':'RFC5681','tcp_smss':smss,'tcp_initial_window_bytes':smss*segments};assert status(x)=='VALID'
 assert status({**x,'tcp_initial_window_bytes':smss*segments+1})=='INVALID'

def test_optional_iw10_experiment_is_separately_selected():
 x={**actual(),'tcp_iw_profile':'RFC6928_EXPERIMENT','tcp_smss':1460,'tcp_initial_window_bytes':14600};assert status(x)=='VALID'
 assert status({**x,'tcp_iw_profile':'RFC5681'})=='INVALID';assert status({**x,'tcp_initial_window_bytes':14601})=='INVALID'

def test_reno_timeout_threshold_uses_actual_flight_and_one_loss_segment():
 x={**actual(),'tcp_congestion':'RENO_RFC5681','tcp_recovery_phase':'TIMEOUT','tcp_smss':1000,'tcp_flight_bytes':8000,'tcp_ssthresh_bytes':4000,'tcp_cwnd_bytes':1000};assert status(x)=='VALID'
 assert status({**x,'tcp_ssthresh_bytes':5000})=='INVALID';assert status({**x,'tcp_cwnd_bytes':2000})=='INVALID'

def test_cubic_own_window_units_and_cubic_shape_not_reno_increase_limit():
 x={**actual(),'tcp_congestion':'CUBIC_RFC9438','tcp_cubic_c':.4,'tcp_cubic_beta':.7,'tcp_cubic_t_s':3,'tcp_cubic_k_s':2,'tcp_cubic_wmax':100,'tcp_cubic_epoch_window':96.8,'tcp_cubic_window':100.4,'tcp_cubic_cwnd':100,'tcp_srtt_s':.5,'tcp_cubic_target':101.35,'tcp_recovery_phase':'CONGESTION_AVOIDANCE','tcp_smss':1000,'tcp_cwnd_increment_bytes':2000};assert status(x)=='VALID'
 for bad in({'tcp_cubic_window':101},{'tcp_cubic_target':151},{'tcp_cubic_beta':1},{'tcp_cubic_c':0}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'tcp_congestion':'RENO_RFC5681'})=='INVALID'

def test_cubic_signed_epoch_root_and_next_rtt_target_clamping():
 x={**actual(),'tcp_congestion':'CUBIC_RFC9438','tcp_cubic_c':.4,'tcp_cubic_beta':.7,'tcp_cubic_k_s':-2,'tcp_cubic_wmax':100,'tcp_cubic_epoch_window':103.2,'tcp_cubic_t_s':10,'tcp_cubic_cwnd':100,'tcp_srtt_s':1,'tcp_cubic_target':150}
 assert status(x)=='VALID'
 assert status({**x,'tcp_cubic_epoch_window':96.8})=='INVALID'
 assert status({**x,'tcp_cubic_target':149})=='INVALID'
 assert status({**x,'tcp_cubic_t_s':0,'tcp_cubic_k_s':2,'tcp_cubic_epoch_window':96.8,'tcp_cubic_target':100})=='VALID'

def test_retransmitted_rtt_requires_negotiated_unambiguous_timestamps():
 x={**actual(),'tcp_sample_retransmitted':True,'tcp_timestamp_unambiguous':True}
 assert status(x)=='UNVERIFIED'
 assert status({**x,'tcp_ts_negotiated':False})=='INVALID'
 assert status({**x,'tcp_ts_negotiated':True,'tcp_ts_local_offer':True,'tcp_ts_peer_offer':True})=='VALID'

def test_source_defaults_conditional_known_mss_does_not_confirm_actual_path():
 f={v['key']:v for v in registry.parameter_fields('tcp')}
 assert {p['value']for p in f['tcp_mss_received']['conditional_defaults']}=={536,1220}
 assert f['tcp_keepalive_enabled']['conditional_defaults'][0]['value']is False
 assert f['tcp_keepalive_idle_s']['conditional_defaults'][0]['value']==7200
 assert f['tcp_cubic_c']['conditional_defaults'][0]['value']==.4
 for k in('tcp_window_wire','tcp_dst_port','tcp_sequence','tcp_srtt_s','tcp_mms_s','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]

def test_ip_version_and_whole_application_framing_acceptance():
 x={**actual(),'tcp_source_address':'192.0.2.1','tcp_destination_address':'192.0.2.2'};assert status(x)=='VALID'
 assert status({**x,'tcp_source_address':'2001:db8::1'})=='INVALID'
 assert status({**x,'tcp_data_accepted':True})=='UNVERIFIED'
 x={**actual(),'tcp_source_ms':1,'tcp_transport_ms':2,'tcp_consumer_ms':3,'tcp_e2e_ms':6,'tcp_deadline_ms':6,'tcp_age_ms':5,'tcp_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'tcp_e2e_ms':2},{'tcp_deadline_ms':5},{'tcp_freshness_ms':4}):assert status({**x,**bad})=='INVALID'

def test_registered_variants_cannot_reuse_current_tcp_schema():
 x={**actual(),'tcp_edition':'REGISTERED_ACTUAL','tcp_registered_source':'synthetic','tcp_header_bytes':20};assert status(x)=='UNVERIFIED'
