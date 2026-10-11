"""USB endpoint, host and power rules are mode-qualified, not inherited CAN facts."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.usb import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual(speed='FULL'):
 x={'ub_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(ub_speed=speed,ub_review_profile='USB2_2025_BUNDLE'if speed in R.USB2_SPEEDS else'USB3_2_REV1_1'if speed in R.USB3_SPEEDS else'USB4_PUBLIC_ARCHITECTURE')
 if speed in R.USB4_SPEEDS:x.update(ub_tunnel_source='synthetic',ub_registered_source='synthetic')
 return x
def status(x):return registry.validate_parameters('usb',x)['status']
def test_usb_own_industry_neutral_phy_no_universal480m_or1024_transfer():
 p=registry.profile('usb');assert p['domain']=='generic_networking'and p['default_stack']==['usb']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 assert status({**actual(),'bitrate':480000000})=='INVALID'
 assert estimate_frame('usb',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('usb'),ids=lambda f:f['key'])
def test_each_usb_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('speed,rate',[('LOW',1500000),('FULL',12000000),('HIGH',480000000),('GEN1_X1',5000000000),('GEN1_X2',10000000000),('GEN2_X1',10000000000),('GEN2_X2',20000000000)])
def test_actual_selected_link_rate_not_highspeed_everywhere(speed,rate):
 assert status({**actual(speed),'ub_link_bps':rate})=='VALID'
 assert status({**actual(speed),'ub_link_bps':rate+1})=='INVALID'
@pytest.mark.parametrize('speed',['LOW','FULL','HIGH'])
def test_usb2_cannot_silently_be_a_usb3_or_usb4_endpoint(speed):assert status({**actual(speed),'ub_speed':'GEN2_X2'})=='INVALID'
@pytest.mark.parametrize('speed',['GEN1_X1','GEN1_X2','GEN2_X1','GEN2_X2'])
def test_usb3_lanes_and_coding_match_actual_mode(speed):
 lanes=2 if speed.endswith('X2')else 1;encoding='8B10B'if speed.startswith('GEN1')else'128B132B';x={**actual(speed),'ub_lanes':lanes,'ub_encoding':encoding,'ub_frame_us':125}
 assert status(x)=='VALID';assert status({**x,'ub_lanes':3})=='INVALID';assert status({**x,'ub_encoding':'NRZI_STUFF6'})=='INVALID'
def test_usb4_aggregate_needs_registered_tunnel_not_usb3_descriptor_assumptions():
 x={**actual('USB4_ASYM_120_40'),'ub_link_bps':120000000000,'ub_reverse_bps':40000000000,'ub_tunnel_allocation_bps':20000000000};assert status(x)=='VALID'
 for bad in({'ub_reverse_bps':120000000000},{'ub_tunnel_allocation_bps':121000000000},{'ub_bmaxburst':0}):assert status({**x,**bad})=='INVALID'
 x.pop('ub_tunnel_source');assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('transfer',['BULK','ISOCHRONOUS'])
def test_low_speed_forbids_bulk_and_iso(transfer):assert status({**actual('LOW'),'ub_transfer':transfer})=='INVALID'
@pytest.mark.parametrize('speed,transfer,packet',[('LOW','CONTROL',8),('FULL','CONTROL',16),('FULL','BULK',64),('HIGH','CONTROL',64),('HIGH','BULK',512),('GEN1_X1','CONTROL',512),('GEN2_X2','BULK',1024)])
def test_endpoint_maxpacket_not_application_buffer(speed,transfer,packet):
 x={**actual(speed),'ub_transfer':transfer,'ub_max_packet_bytes':packet,'ub_packet_bytes':packet,'ub_transfer_bytes':100000,'ub_host_buffer_bytes':100000,'ub_peer_buffer_bytes':100000};assert status(x)=='VALID'
 assert status({**x,'ub_packet_bytes':packet+1})=='INVALID'
 assert status({**x,'ub_host_buffer_bytes':99999})=='INVALID'
@pytest.mark.parametrize('speed,transfer,limit',[('LOW','INTERRUPT',8),('FULL','INTERRUPT',64),('FULL','ISOCHRONOUS',1023),('HIGH','INTERRUPT',1024),('HIGH','ISOCHRONOUS',1024)])
def test_each_periodic_maximum(speed,transfer,limit):
 x={**actual(speed),'ub_transfer':transfer,'ub_max_packet_bytes':limit};assert status(x)=='VALID';assert status({**x,'ub_max_packet_bytes':limit+1})=='INVALID'
def test_zero_address_default_and_ep0_control_only():
 x={**actual(),'ub_device_state':'DEFAULT','ub_device_address':0,'ub_endpoint':0,'ub_transfer':'CONTROL','ub_direction':'BIDIRECTIONAL'};assert status(x)=='VALID'
 for bad in({'ub_device_state':'CONFIGURED'},{'ub_transfer':'BULK'},{'ub_direction':'IN'}):assert status({**x,**bad})=='INVALID'
def test_endpoint_address_reserved_bits_and_host_direction():
 x={**actual(),'ub_endpoint':3,'ub_direction':'IN','ub_endpoint_address_raw':131};assert status(x)=='VALID'
 for bad in({'ub_endpoint_address_raw':147},{'ub_endpoint_address_raw':3},{'ub_direction':'OUT'}):assert status({**x,**bad})=='INVALID'
def highband():return {**actual('HIGH'),'ub_transfer':'ISOCHRONOUS','ub_max_packet_bytes':1024,'ub_extra_transactions':2,'ub_max_packet_raw':5120,'ub_transactions':3,'ub_double_eusb2':False,'ub_binterval':1,'ub_interval_us':125,'ub_periodic_allocation_percent':80}
def test_highbandwidth_wmaxpacket_has_additional_transaction_bits():
 x=highband();assert status(x)=='VALID'
 for bad in({'ub_max_packet_raw':1024},{'ub_extra_transactions':3},{'ub_transactions':6},{'ub_binterval':2},{'ub_periodic_allocation_percent':81}):assert status({**x,**bad})=='INVALID'
def test_eusb2_double_iso_in_requires_direct_inbox_and_ecn_companion():
 x={**actual('HIGH'),'ub_double_eusb2':True,'ub_direct_inbox':True,'ub_transfer':'ISOCHRONOUS','ub_direction':'IN','ub_bcdusb':544,'ub_max_packet_raw':0,'ub_max_packet_bytes':1024,'ub_binterval':1,'ub_dwbytes_per_interval':6144,'ub_bytes_per_interval':6144,'ub_transactions':6,'ub_periodic_allocation_percent':95};assert status(x)=='VALID'
 for bad in({'ub_direct_inbox':False},{'ub_direction':'OUT'},{'ub_dwbytes_per_interval':6145},{'ub_dwbytes_per_interval':3072},{'ub_max_packet_raw':1024},{'ub_periodic_allocation_percent':96}):assert status({**x,**bad})=='INVALID'
def test_ls_fs_integer_frames_and_hs_exponential_microframes():
 x={**actual('LOW'),'ub_transfer':'INTERRUPT','ub_binterval':10,'ub_interval_us':10000};assert status(x)=='VALID';assert status({**x,'ub_binterval':1})=='INVALID'
 x={**actual('FULL'),'ub_transfer':'ISOCHRONOUS','ub_binterval':4,'ub_interval_us':8000};assert status(x)=='VALID';assert status({**x,'ub_interval_us':500})=='INVALID'
 x.update(actual('HIGH'),ub_interval_us=1000);assert status(x)=='VALID'
def test_usb3_control_and_bulk_interval_is_reserved_not_generic100ms_period():
 for transfer in('CONTROL','BULK'):assert status({**actual('GEN1_X1'),'ub_transfer':transfer,'ub_binterval':1})=='INVALID'
def test_usb_generations_forbid_foreign_companion_facts():
 assert status({**actual('FULL'),'ub_bmaxburst':0})=='INVALID'
 assert status({**actual('GEN2_X1'),'ub_extra_transactions':0})=='INVALID'
 assert status({**actual('HIGH'),'ub_periodic_allocation_percent':95})=='UNVERIFIED'
def test_usb3_notification_minimum8_and_interrupt_burst_max3packets():
 x={**actual('GEN1_X1'),'ub_transfer':'INTERRUPT','ub_interrupt_usage':'NOTIFICATION','ub_binterval':8,'ub_interval_us':16000,'ub_bmaxburst':2,'ub_burst_packets':3,'ub_max_packet_bytes':1024,'ub_wbytes_per_interval':3072};assert status(x)=='VALID'
 for bad in({'ub_binterval':7},{'ub_bmaxburst':3},{'ub_wbytes_per_interval':3073},{'ub_max_packet_bytes':64}):assert status({**x,**bad})=='INVALID'
def test_usb3_bulk_streams_zero_is_none_and_count_is_power_of2():
 x={**actual('GEN1_X1'),'ub_transfer':'BULK','ub_maxstreams':16,'ub_stream_count':65536};assert status(x)=='VALID';assert status({**x,'ub_stream_count':16})=='INVALID'
 x.update(ub_maxstreams=0,ub_stream_count=0);assert status(x)=='VALID';assert status({**x,'ub_stream_count':1})=='INVALID'
def test_usb3_iso_reservation_uses_actual_packet_burst_and_mult():
 x={**actual('GEN1_X1'),'ub_transfer':'ISOCHRONOUS','ub_ssp_iso_companion':False,'ub_bmaxburst':15,'ub_mult':2,'ub_max_packet_bytes':1024,'ub_wbytes_per_interval':49152};assert status(x)=='VALID';assert status({**x,'ub_wbytes_per_interval':49153})=='INVALID'
 assert status({**x,'ub_bmaxburst':0,'ub_mult':1,'ub_wbytes_per_interval':1024})=='INVALID'
def test_ssp_iso_above48k_requires_companion_and_mode_capacity():
 x={**actual('GEN2_X2'),'ub_transfer':'ISOCHRONOUS','ub_ssp_iso_companion':True,'ub_wbytes_per_interval':1,'ub_dwbytes_per_interval':150000,'ub_ssp_iso_max_bytes':196608,'ub_ssp_source':'synthetic'};assert status(x)=='VALID'
 for bad in({'ub_speed':'GEN1_X1'},{'ub_wbytes_per_interval':150000},{'ub_dwbytes_per_interval':49152},{'ub_dwbytes_per_interval':196608}):assert status({**x,**bad})=='INVALID'
def test_iso_has_no_data_retry_or_handshake_function_guarantee():assert status({**actual(),'ub_transfer':'ISOCHRONOUS','ub_retry_enabled':True})=='INVALID'
@pytest.mark.parametrize('profile,unit',[('USB2_LEGACY',100),('USB3_LEGACY_SINGLE_LANE',150),('USB3_LEGACY_DUAL_LANE',250)])
def test_legacy_power_unit_is_mode_specific_actual_peak(profile,unit):
 x={**actual(),'ub_power_profile':profile,'ub_unit_load_ma':unit,'ub_device_state':'DEFAULT','ub_current_ma':unit};assert status(x)=='VALID';assert status({**x,'ub_current_ma':unit+1})=='INVALID';assert status({**x,'ub_unit_load_ma':unit+1})=='INVALID'
def test_vbus_ecn_55_not_old525_or_pd_voltage_assumption():
 x={**actual(),'ub_power_profile':'USB2_LEGACY','ub_vbus_revision':'VBUS_MAX_ECN','ub_vbus_v':5.5};assert status(x)=='VALID';assert status({**x,'ub_vbus_revision':'BASE_2000'})=='INVALID'
 assert status({**actual(),'ub_power_profile':'PD_ACTUAL','ub_vbus_v':20})=='UNVERIFIED'
def test_actual_source_to_function_bound_not_periodic_descriptor_only():
 x={**actual(),'ub_source_ms':1,'ub_transport_ms':2,'ub_use_ms':3,'ub_e2e_ms':6,'ub_deadline_ms':6,'ub_age_ms':4,'ub_freshness_ms':4};assert status(x)=='VALID'
 for bad in({'ub_e2e_ms':2},{'ub_deadline_ms':5},{'ub_freshness_ms':3}):assert status({**x,**bad})=='INVALID'
 x.update(ub_data_accepted=True,ub_observation_source='synthetic',ub_schedule_verified=True,ub_path_verified=True,ub_outcome='ACCEPTED');assert status(x)=='VALID';assert status({**x,'ub_outcome':'NAK'})=='INVALID'
def test_only_qualified_source_baselines_no_fake_endpoint_or_bandwidth_allocation():
 f={v['key']:v for v in registry.parameter_fields('usb')};assert f['ub_link_bps']['conditional_defaults'][0]['when']['ub_speed']=='LOW'
 for k in('ub_speed','ub_max_packet_bytes','ub_binterval','ub_current_ma','ub_tunnel_allocation_bps','payload_bytes'):assert'default'not in f[k]and'conditional_defaults'not in f[k]
