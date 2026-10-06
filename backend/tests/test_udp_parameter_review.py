"""UDP IP-version, checksum and actual datagram/path sizes are independent."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.udp import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual(ip='IPV4'):
 x={'ud_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(ud_review_profile='RFC_BASE',ud_ip_version=ip,ud_src_port=0,ud_dst_port=1234,ud_checksum_mode='FULL',ud_size_mode='NORMAL');return x
def status(x):return registry.validate_parameters('udp',x)['status']
def test_udp_own_datagram_path_not_generic_ethernet_frame():
 p=registry.profile('udp');assert p['domain']=='generic_networking'and p['default_stack']==['udp']and p['max_payload_bytes']is None
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':100000000},{'mtu_bytes':1500},{'retry_limit':3},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('udp',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('udp'),ids=lambda f:f['key'])
def test_every_udp_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('src,dst',[(0,1234),(65535,65535),(1000,1)])
def test_ports_16bit_source0_unused_no_default_canid(src,dst):assert status({**actual(),'ud_src_port':src,'ud_dst_port':dst})=='VALID'
def test_actual_address_version_and_application_payload_binding():
 assert status({**actual(),'ud_source_ip':'192.0.2.1','ud_destination_ip':'198.51.100.1','payload_bytes':10,'ud_payload':10})=='VALID'
 assert status({**actual(),'ud_source_ip':'2001:db8::1'})=='INVALID'
 assert status({**actual('IPV6'),'ud_destination_ip':'198.51.100.1'})=='INVALID'
 assert status({**actual(),'payload_bytes':10,'ud_payload':11})=='INVALID'
def test_udp_whole_datagram_min8_and_wire_length():
 x={**actual(),'ud_header_bytes':8,'ud_payload':0,'ud_datagram_bytes':8,'ud_length_field':8};assert status(x)=='VALID'
 for bad in({'ud_header_bytes':7},{'ud_datagram_bytes':0},{'ud_length_field':0},{'ud_length_field':9}):assert status({**x,**bad})=='INVALID'
def test_ipv4_vs_ipv6_maximum_not_global65507():
 x={**actual(),'ud_payload':65507,'ud_datagram_bytes':65515,'ud_length_field':65515,'ud_ip_header_bytes':20,'ud_ip_packet_bytes':65535};assert status(x)=='VALID'
 assert status({**x,'ud_ip_header_bytes':24,'ud_ip_packet_bytes':65539})=='INVALID'
 y={**actual('IPV6'),'ud_payload':65527,'ud_datagram_bytes':65535,'ud_length_field':65535,'ud_ip_header_bytes':40,'ud_extension_bytes':0,'ud_ip_packet_bytes':65575,'ud_ip_payload_length':65535};assert status(y)=='VALID'
 assert status({**y,'ud_payload':65528,'ud_datagram_bytes':65536,'ud_length_field':0})=='INVALID'
def test_ipv4_options_and_ipv6_extensions_not_udp_header_or_pseudo_length():
 x={**actual('IPV6'),'ud_payload':100,'ud_datagram_bytes':108,'ud_ip_header_bytes':48,'ud_extension_bytes':8,'ud_ip_packet_bytes':156,'ud_ip_payload_length':116,'ud_pseudo_length':108};assert status(x)=='VALID'
 for bad in({'ud_ip_header_bytes':40},{'ud_ip_payload_length':108},{'ud_pseudo_length':116}):assert status({**x,**bad})=='INVALID'
 for n in(19,21,64):assert status({**actual(),'ud_ip_header_bytes':n})=='INVALID'
def jumbo():return {**actual('IPV6'),'ud_size_mode':'IPV6_JUMBO','ud_payload':70000,'ud_datagram_bytes':70008,'ud_length_field':0,'ud_ip_payload_length':0,'ud_extension_bytes':8,'ud_jumbo_payload_length':70016,'ud_pseudo_length':70008,'ud_fragment_header':False,'ud_jumbo_path_verified':True}
def test_jumbo_length0_actual_pseudo_length_and_wholepath():
 x=jumbo();assert status(x)=='VALID'
 for bad in({'ud_length_field':8},{'ud_ip_version':'IPV4'},{'ud_ip_payload_length':100},{'ud_fragment_header':True},{'ud_jumbo_path_verified':False},{'ud_jumbo_payload_length':70008},{'ud_pseudo_length':0}):assert status({**x,**bad})=='INVALID'
def test_small_udp_in_large_ipv6_packet_keeps_nonzero_udp_length():
 x={**jumbo(),'ud_payload':100,'ud_datagram_bytes':108,'ud_length_field':108,'ud_extension_bytes':70000,'ud_jumbo_payload_length':70108,'ud_pseudo_length':108};assert status(x)=='VALID'
 assert status({**x,'ud_length_field':0})=='INVALID'
def test_ipv4_omission_and_ipv6_nonzero_not_same():
 assert status({**actual(),'ud_checksum_mode':'IPV4_OMITTED','ud_checksum':0})=='VALID'
 assert status({**actual('IPV6'),'ud_checksum_mode':'IPV4_OMITTED','ud_checksum':0})=='INVALID'
 assert status({**actual('IPV6'),'ud_checksum':0})=='INVALID'
def test_calculated_checksum0_wireffff_not_disabled_zero():
 x={**actual(),'ud_computed_checksum':0,'ud_checksum':65535};assert status(x)=='VALID'
 assert status({**x,'ud_checksum':0})=='INVALID'
 assert status({**x,'ud_computed_checksum':1})=='INVALID'
def tunnel():return {**actual('IPV6'),'ud_checksum_mode':'IPV6_TUNNEL_ZERO','ud_checksum':0,'ud_tunnel_port_enabled':True,'ud_address_checks':True,'ud_inner_integrity':True,'ud_middleboxes_verified':True,'ud_tunnel_source':'synthetic'}
def test_ipv6_tunnel_zero_requires_all_assessed_conditions():
 x=tunnel();assert status(x)=='VALID'
 for k in('ud_tunnel_source','ud_tunnel_port_enabled','ud_address_checks','ud_inner_integrity','ud_middleboxes_verified'):
  y=dict(x);y.pop(k);assert status(y)=='UNVERIFIED'
 for bad in({'ud_address_checks':False},{'ud_checksum':1},{'ud_ip_version':'IPV4'}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ud_environment':'INTERNET','ud_congestion_source':'synthetic'})=='UNVERIFIED'
 assert status({**x,'ud_environment':'INTERNET','ud_congestion_source':'synthetic','ud_fallback_full_checksum':True})=='VALID'
@pytest.mark.parametrize('ip,hop,emtu,header,maxpayload',[('IPV4',1500,576,20,548),('IPV4',500,500,20,472),('IPV4',1500,576,60,508),('IPV6',1500,1280,40,1232),('IPV6',1500,1280,48,1224)])
def test_fallback_emtu_subtracts_all_headers_not_ethernet1500(ip,hop,emtu,header,maxpayload):
 x={**actual(ip),'ud_pmtu_mode':'FALLBACK_EMTU','ud_first_hop_mtu':hop,'ud_emtu_s':emtu,'ud_ip_header_bytes':header,'ud_max_payload':maxpayload,'ud_payload':maxpayload};assert status(x)=='VALID'
 assert status({**x,'ud_max_payload':maxpayload+1})=='INVALID'
 assert status({**x,'ud_payload':maxpayload+1})=='INVALID'
def test_known_path_mtu_and_fragmentation_not_udp_segmentation():
 x={**actual(),'ud_pmtu_mode':'DISCOVERED','ud_path_mtu':1500,'ud_ip_header_bytes':20,'ud_max_payload':1472,'ud_payload':1472,'ud_datagram_bytes':1480,'ud_ip_packet_bytes':1500};assert status(x)=='VALID'
 assert status({**x,'ud_payload':1473,'ud_datagram_bytes':1481,'ud_ip_packet_bytes':1501})=='INVALID'
 assert status({**x,'ud_payload':1473,'ud_datagram_bytes':1481,'ud_ip_packet_bytes':1501,'ud_fragmentation_allowed':True})=='VALID'
def probes():return {**actual(),'ud_pmtu_mode':'DPLPMTUD','ud_probe_layer':'UDP_PACKET','ud_pmtu_source':'synthetic','ud_probe_source':'synthetic','ud_min_plpmtu':40,'ud_base_plpmtu':1200,'ud_max_plpmtu':1472,'ud_max_probes':3,'ud_probe_timer_s':16,'ud_raise_timer_s':600}
def test_actual_dplpmtud_own_sizes_and_timers_not_udp_native_ack():
 x=probes();assert status(x)=='VALID'
 for bad in({'ud_probe_timer_s':.99},{'ud_probe_timer_s':2,'ud_probe_ack_bound_s':2},{'ud_base_plpmtu':1472},{'ud_plpmtu':1473},{'ud_probe_count':4}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ud_probe_timer_s':1})=='VALID'
def test_acknowledgment_resets_probe_count_and_confirmation_timer_scope():
 x=probes();assert status({**x,'ud_probe_acked':True,'ud_probe_count':0})=='VALID'
 assert status({**x,'ud_probe_acked':True,'ud_probe_count':1})=='INVALID'
 assert status({**x,'ud_acknowledged_pl':True,'ud_confirmation_timer_s':30})=='INVALID'
 assert status({**x,'ud_acknowledged_pl':False,'ud_confirmation_timer_s':30})=='VALID'
 assert status({**x,'ud_acknowledged_pl':False,'ud_confirmation_timer_s':600})=='INVALID'
def test_packetization_layer_sizes_account_separate_header_units():
 x={**probes(),'ud_first_hop_mtu':1500,'ud_peer_emtu_r':1500,'ud_ip_header_bytes':20,'ud_min_plpmtu':48,'ud_max_plpmtu':1480};assert status(x)=='VALID'
 assert status({**x,'ud_max_plpmtu':1481})=='INVALID'
 assert status({**x,'ud_probe_layer':'APPLICATION_PAYLOAD','ud_max_plpmtu':1480})=='INVALID'
 assert status({**x,'ud_probe_layer':'APPLICATION_PAYLOAD','ud_min_plpmtu':40,'ud_max_plpmtu':1472})=='VALID'
 assert status({**x,'ud_min_plpmtu':47})=='INVALID'
def test_congestion_and_reliability_are_explicit_application_proofs():
 assert status({**actual(),'ud_environment':'INTERNET'})=='UNVERIFIED'
 assert status({**actual(),'ud_environment':'INTERNET','ud_congestion_source':'synthetic'})=='VALID'
 assert status({**actual(),'ud_environment':'CONTROLLED'})=='UNVERIFIED'
 assert status({**actual(),'ud_reliable_claimed':True})=='UNVERIFIED'
 assert status({**actual(),'ud_reliable_claimed':True,'ud_reliability_source':'synthetic'})=='VALID'
def test_native_header_big_endian_complete_fields():
 x={**actual(),'ud_length_field':8,'ud_checksum':65535,'ud_header_hex':'000004d20008ffff'};assert status(x)=='VALID'
 for bad in({'ud_header_hex':'0000d2040008ffff'},{'ud_header_hex':'000004d20000ffff'},{'ud_header_hex':'000004d20008ffff00'}):assert status({**x,**bad})=='INVALID'
def test_ipv6_has_no_broadcast_and_multicast_needs_whole_receiver_evidence():
 assert status({**actual('IPV6'),'ud_delivery':'BROADCAST'})=='INVALID'
 assert status({**actual('IPV6'),'ud_delivery':'MULTICAST','ud_receiver_count':2})=='VALID'
def test_complete_data_age_and_function_not_datagram_send_response():
 x={**actual(),'ud_source_ms':1,'ud_path_ms':2,'ud_consumer_ms':3,'ud_e2e_ms':6,'ud_deadline_ms':6,'ud_age_ms':5,'ud_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'ud_e2e_ms':2},{'ud_deadline_ms':5},{'ud_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 x.update(ud_data_accepted=True,ud_observation_source='synthetic',ud_path_verified=True,ud_outcome='ACCEPTED');assert status(x)=='VALID'
 assert status({**x,'ud_outcome':'DUPLICATE'})=='INVALID'
def test_standard_proposals_do_not_invent_pmtu_ip_ports_rate_or_timer1():
 f={v['key']:v for v in registry.parameter_fields('udp')}
 assert f['ud_max_probes']['conditional_defaults'][0]['value']==3 and f['ud_raise_timer_s']['conditional_defaults'][0]['value']==600
 for k in('ud_path_mtu','ud_ip_version','ud_src_port','ud_dst_port','ud_probe_timer_s','ud_wire_bytes','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
