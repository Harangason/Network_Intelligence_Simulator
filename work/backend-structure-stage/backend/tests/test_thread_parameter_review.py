"""Thread own radio, roles, dataset and uncompressed fragmentation scope."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.thread import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual():
 x={'th_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(th_review_profile='PUBLIC_BASELINE_2026',th_phy='IEEE_802154_24GHZ_OQPSK',bitrate=250000)
 return x
def status(x):return registry.validate_parameters('thread',x)['status']
def test_thread_own_profile_no127byte_application_cap_or_ethernet_clock():
 p=registry.profile('thread');assert p['default_stack']==['thread']and p['max_payload_bytes']is None
 assert p['domain']=='generic_networking'and p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':100000000},{'mtu_bytes':1500},{'nominal_bitrate_bps':500000},{'retry_limit':3}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('thread',1280,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('thread'),ids=lambda f:f['key'])
def test_every_thread_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
def test_radio_symbol_psdu_and_whole_airtime_not_functional_timing():
 x={**actual(),'th_symbol_rate':62500,'th_symbol_us':16,'th_symbols_per_octet':2,'th_psdu_bytes':100,'th_mac_header_bytes':15,'th_security_overhead_bytes':9,'th_fcs_bytes':2,'th_adaptation_bytes':4,'th_frame_data_bytes':70,'th_phy_overhead_bytes':6,'th_wire_bytes':106,'th_airtime_us':3392}
 assert status(x)=='VALID'
 for bad in({'th_airtime_us':3200},{'th_psdu_bytes':128},{'th_wire_bytes':100},{'th_fcs_bytes':0},{'th_symbol_us':32},{'th_frame_data_bytes':71}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('channel',[11,15,26])
def test_selected_channel_bit_in_dataset_mask_not_just_numeric_range(channel):
 x={**actual(),'th_channel':channel,'th_channel_mask':(1<<channel)|(1<<12)}
 assert status(x)=='VALID'
 assert status({**x,'th_channel_mask':1<<13})=='INVALID'
 assert status({**x,'th_channel_mask':(1<<channel)|1})=='INVALID'
def dataset(kind='ACTIVE'):
 return {**actual(),'th_dataset_kind':kind,'th_active_seconds':1,'th_active_ticks':0,'th_active_authoritative':False,'th_channel':15,'th_channel_mask':1<<15,'th_extended_pan_hex':'0102030405060708','th_mesh_prefix':'fd12:3456:789a:bcde::/64','th_network_name':'NIS','th_network_name_bytes':3,'th_pan_id':42,'th_network_key_ref':'synthetic-key-reference','th_network_key_bytes':16,'th_pskc_ref':'synthetic-pskc-reference','th_pskc_bytes':16}
def test_complete_dataset_nonsecret_refs_and_pending_extra_tlvs():
 x=dataset();assert status(x)=='VALID'
 for k in ('th_channel_mask','th_pskc_ref','th_active_authoritative','th_extended_pan_hex'):
  y=dict(x);y.pop(k);assert status(y)=='UNVERIFIED'
 assert status(dataset('PENDING'))=='UNVERIFIED'
 assert status({**dataset('PENDING'),'th_pending_seconds':2,'th_pending_ticks':0,'th_pending_authoritative':False,'th_pending_delay_ms':1000})=='VALID'
 assert status({**x,'th_network_key_bytes':8})=='INVALID'
@pytest.mark.parametrize('prefix',['fe80::/64','fd12::1/64','fd12::/48','fd12::::/64','192.0.2.0/24','fd12::%eth0/64'])
def test_mesh_prefix_is_actual_strict_ipv6_ula_network_not_regex_only(prefix):
 assert status({**dataset(),'th_mesh_prefix':prefix})=='INVALID'
def test_utf8_network_name_byte_limit_broadcast_pan_and_extended_pan():
 x=dataset();assert status({**x,'th_network_name':'ä'*8,'th_network_name_bytes':16})=='VALID'
 for bad in({'th_network_name':'ä'*9,'th_network_name_bytes':18},{'th_network_name':'NIS\n','th_network_name_bytes':4},{'th_network_name_bytes':2},{'th_pan_id':65535},{'th_extended_pan_hex':'0000000000000000'},{'th_extended_pan_hex':'ffffffffffffffff'}):assert status({**x,**bad})=='INVALID'
def test_parent_child_and_active_forwarding_role_are_not_interchangeable():
 x={**actual(),'th_role':'LEADER','th_device_type':'ECD','th_rx_on_idle':True,'th_forwards':True,'th_child_id':0,'th_leaders_per_partition':1,'th_mesh_extenders':32};assert status(x)=='VALID'
 for bad in({'th_device_type':'MED'},{'th_rx_on_idle':False},{'th_child_id':1},{'th_leaders_per_partition':2},{'th_mesh_extenders':33}):assert status({**x,**bad})=='INVALID'
 x={**actual(),'th_device_type':'SED','th_role':'END_DEVICE','th_rx_on_idle':False,'th_forwards':False,'th_parent_id':'synthetic','th_poll_wait_ms':100};assert status(x)=='VALID'
 assert status({**x,'th_forwards':True})=='INVALID'
 y=dict(x);y.pop('th_parent_id');assert status(y)=='UNVERIFIED'
def test_real_parent_table_and_configured_router_range_limit_actual_counts():
 x={**actual(),'th_children':20,'th_allowed_children':20,'th_router_id_min':2,'th_router_id_max':20,'th_router_id':15};assert status(x)=='VALID'
 for bad in({'th_children':21},{'th_router_id':21},{'th_router_id_min':21},{'th_children':512,'th_allowed_children':600}):assert status({**x,**bad})=='INVALID'
def test_zero_poll_override_does_not_infer_zero_delivery_wait():
 assert status({**actual(),'th_poll_ms':0})=='VALID'
 for p in (1,9,67108864):assert status({**actual(),'th_poll_ms':p})=='INVALID'
 for p in (10,1000,67108863):assert status({**actual(),'th_poll_ms':p})=='VALID'
 assert status({**actual(),'th_poll_ms':0,'th_device_type':'SED','th_role':'END_DEVICE','th_rx_on_idle':False,'th_parent_id':'synthetic'})=='UNVERIFIED'
def test_csl_period_has160us_units_and_own_version_clock_source():
 x={**actual(),'th_csl_period_units':100,'th_csl_period_us':16000};assert status(x)=='VALID'
 assert status({**x,'th_csl_period_us':100})=='INVALID'
 x.update(th_device_type='SSED',th_role='END_DEVICE',th_rx_on_idle=False,th_parent_id='synthetic',th_poll_wait_ms=16)
 assert status(x)=='UNVERIFIED';assert status({**x,'th_csl_source':'synthetic-version-and-platform'})=='VALID'
def test_local_thread_does_not_require_border_router_external_path_does():
 assert status({**actual(),'th_border_router':False,'th_external_delivery':False})=='VALID'
 assert status({**actual(),'th_external_delivery':True})=='UNVERIFIED'
 assert status({**actual(),'th_external_delivery':True,'th_external_binding_source':'synthetic-path'})=='VALID'
def fragments():
 return {**actual(),'th_ipv6_mtu':1280,'th_ipv6_payload_bytes':240,'th_datagram_bytes':280,'th_fragment_kind':'SUBSEQUENT','th_fragment_header_bytes':5,'th_fragment_size':280,'th_fragment_offset_units':10,'th_fragment_offset_bytes':80,'th_fragment_coverage_bytes':80,'th_last_fragment':False,'th_fragment_tag':65535,'th_next_fragment_tag':0,'th_reassembly_buffer_bytes':280,'th_reassembly_timeout_s':60}
def test_fragment_size_offsets_are_uncompressed_and_tag_wraps():
 x=fragments();assert status(x)=='VALID'
 for bad in({'th_fragment_size':200},{'th_fragment_offset_bytes':10},{'th_fragment_header_bytes':4},{'th_fragment_coverage_bytes':79},{'th_fragment_coverage_bytes':208},{'th_reassembly_buffer_bytes':279},{'th_next_fragment_tag':65536},{'th_reassembly_timeout_s':61}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'th_fragment_coverage_bytes':79,'th_last_fragment':True})=='VALID'
 assert status({**x,'th_fragment_kind':'FIRST','th_fragment_header_bytes':4,'th_fragment_offset_units':0,'th_fragment_offset_bytes':0})=='VALID'
def test_overlap_must_discard_and_deep_hopfield_not_silently_absent():
 assert status({**fragments(),'th_reassembly_overlap':True,'th_partial_discarded':False})=='INVALID'
 assert status({**fragments(),'th_reassembly_overlap':True,'th_partial_discarded':True})=='VALID'
 assert status({**actual(),'th_hops_left':15})=='UNVERIFIED'
 assert status({**actual(),'th_hops_left':15,'th_deep_hops_left':32})=='VALID'
def test_iphc_two_byte_base_not_whole_header_and_context_byte():
 x={**actual(),'th_compression':'IPHC','th_context_extension':True,'th_iphc_base_bytes':3,'th_compressed_header_bytes':7};assert status(x)=='VALID'
 assert status({**x,'th_iphc_base_bytes':2})=='INVALID'
 assert status({**x,'th_compressed_header_bytes':2})=='INVALID'
 assert status({**x,'th_context_extension':False,'th_iphc_base_bytes':2})=='VALID'
def test_udp_port_compression_and_integrity_authorization_not_blanket_elision():
 x={**actual(),'th_udp_ports_mode':'LOW4_LOW4','th_udp_source_port':0xf0b0,'th_udp_destination_port':0xf0bf};assert status(x)=='VALID'
 assert status({**x,'th_udp_destination_port':5683})=='INVALID'
 assert status({**x,'th_udp_ports_mode':'FULL_FULL','th_udp_destination_port':5683})=='VALID'
 x.update(th_checksum_elided=True);assert status(x)=='UNVERIFIED'
 x.update({f'th_{k}':True for k in('checksum_authorized','checksum_verified','integrity_verified','checksum_restored')});assert status(x)=='VALID'
 for k in('checksum_authorized','checksum_verified','integrity_verified','checksum_restored'):assert status({**x,f'th_{k}':False})=='INVALID'
def test_functional_whole_path_bound_includes_poll_and_hops():
 x={**actual(),'th_source_ms':1,'th_transport_ms':30,'th_poll_wait_ms':20,'th_hop_bound_ms':10,'th_consumer_ms':2,'th_e2e_ms':33,'th_deadline_ms':33,'th_age_ms':32,'th_freshness_ms':32};assert status(x)=='VALID'
 for bad in({'th_transport_ms':10},{'th_e2e_ms':10},{'th_deadline_ms':32},{'th_freshness_ms':31}):assert status({**x,**bad})=='INVALID'
 assert status({**actual(),'th_data_accepted':True})=='UNVERIFIED'
def test_source_defaults_are_conditional_not_actual_identity_or_secret():
 f={v['key']:v for v in registry.parameter_fields('thread')}
 assert f['bitrate']['conditional_defaults'][0]['value']==250000
 assert f['th_ipv6_mtu']['conditional_defaults'][0]['value']==1280
 for k in('th_poll_ms','th_channel','th_network_name','th_extended_pan_hex','th_network_key_ref','th_router_id','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
def test_registered_edition_requires_own_source_not_public_baseline_bounds():
 x={**actual(),'th_review_profile':'REGISTERED_ACTUAL','th_registered_source':'synthetic'}
 assert status({**x,'th_channel':15})=='UNVERIFIED'
