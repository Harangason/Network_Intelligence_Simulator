"""SV parameter units/edition/LE versus other profiles and complete observed chain."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.sampled_values import rules as R
def actual():
 x={'sv_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(sv_profile='ACTUAL_DEVICE',sv_edition='ED2_1',sv_implementation='ACTUAL_DEVICE',sv_proposal_mode='ACTUAL_CONFIG',sv_mapping='RAW_L2_9_2')
 return x
def status(x):return registry.validate_parameters('sampled_values',x)['status']
def le(block='MSVCB01',line=50):
 return {**actual(),'sv_profile':'UCA_9_2LE_2004','sv_edition':'ED1','sv_le_block':block,'sv_line_hz':line}
def test_native_sample_rate_distinct_physical_rate_and_ethernet_mtu():
 p=registry.profile('sampled_values');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('sampled_values')};assert not set(R.REMOVED)&set(f)
 for k in('sv_line_hz','sv_age_us','sv_smp_synch','sv_multicast_mac','sv_raw_value'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
@pytest.mark.parametrize('field',registry.parameter_fields('sampled_values'),ids=lambda f:f['key'])
def test_every_field_type_and_declared_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('block,line,rate,n,hz,frames',[('MSVCB01',50,80,1,4000,4000),('MSVCB01',60,80,1,4800,4800),('MSVCB02',50,256,8,12800,1600),('MSVCB02',60,256,8,15360,1920)])
def test_le80_256_perperiod_and_asdu_batching_not_ethernet_packet_rate(block,line,rate,n,hz,frames):
 x={**le(block,line),'sv_smp_mode':'PER_NOMINAL_PERIOD','sv_smp_rate':rate,'sv_no_asdu':n,'sv_sample_hz':hz,'sv_frame_hz':frames,'sv_wrap_count':hz,'sv_smp_cnt':hz-1,'sv_sample_interval_us':1000000/hz};assert status(x)=='VALID'
 for bad in({'sv_smp_rate':rate+1},{'sv_no_asdu':n+1},{'sv_sample_hz':hz+1},{'sv_frame_hz':frames+1},{'sv_smp_cnt':hz},{'sv_wrap_count':65536}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('k,valid,bad',[('link_bps',100000000,1000000000),('appid',0x4000,0x4001),('channel_count',8,7),('data_bytes',64,8),('current_scale',.001,.01),('voltage_scale',.01,.001),('offset',0,1),('conf_rev',1,2)])
def test_le_fixed_subset_not_universal_newer_edition_defaults(k,valid,bad):
 assert status({**le(),'sv_'+k:valid})=='VALID'
 assert status({**le(),'sv_'+k:bad})=='INVALID'
 assert status({**actual(),'sv_'+k:bad})=='VALID'
@pytest.mark.parametrize('bad',[{'sv_duplex':'HALF'},{'sv_phy':'REGISTERED_ACTUAL','sv_registered_source':'synthetic'}, {'sv_has_smp_mode':True},{'sv_has_smp_rate':True},{'sv_has_dataset':True},{'sv_edition':'ED2_1'},{'sv_priority':3},{'sv_vlan_id':2}])
def test_le_link_and_optional_field_subset(bad):assert status({**le(),**bad})=='INVALID'
@pytest.mark.parametrize('mode,rate,hz',[('PER_NOMINAL_PERIOD',80,4000),('SAMPLES_PER_SECOND',4800,4800),('SECONDS_PER_SAMPLE',2,.5)])
def test_selected_sample_rate_units(mode,rate,hz):
 x={**actual(),'sv_smp_mode':mode,'sv_smp_rate':rate,'sv_sample_hz':hz,'sv_line_hz':50};assert status(x)=='VALID'
 assert status({**x,'sv_sample_hz':hz+1})=='INVALID'
def test_absent_smpmode_means_perperiod_not_zero_api_readback_proof():
 assert status({**actual(),'sv_has_smp_mode':False,'sv_smp_mode':'PER_NOMINAL_PERIOD'})=='VALID'
 assert status({**actual(),'sv_has_smp_mode':False,'sv_smp_mode':'SAMPLES_PER_SECOND'})=='INVALID'
def test_pinned_library_optional_smpmod_encoding_mismatch_not_falsely_compatible():
 x={**actual(),'sv_implementation':'LIBIEC61850_1_6','sv_library_pair':'PINNED_PUBLISHER_AND_SUBSCRIBER','sv_has_smp_mode':True};assert status(x)=='INVALID'
 assert status({**x,'sv_has_smp_mode':False})=='VALID'
 assert status({**x,'sv_library_pair':'VERIFIED_OTHER_PEER'})=='VALID'
@pytest.mark.parametrize('edition,state,n',[('ED1','NONE',0),('ED1','LOCAL',1),('ED1','GLOBAL',1),('ED2_1','NONE',0),('ED2_1','LOCAL',1),('ED2_1','GLOBAL',2)])
def test_sync_wire_interpretation_depends_on_edition(edition,state,n):
 x={**actual(),'sv_edition':edition,'sv_sync_state':state,'sv_smp_synch':n};assert status(x)=='VALID'
 assert status({**x,'sv_smp_synch':3})=='INVALID'
 assert status({**x,'sv_smp_synch':2 if n==1 else 1})=='INVALID'
def test_other_named_local_sync_needs_registered_actual_edition():
 x={**actual(),'sv_smp_synch':5};assert status(x)=='INVALID'
 x.update(sv_edition='REGISTERED_OTHER',sv_registered_source='synthetic-newer-qualified-edition');assert status(x)=='VALID'
 for n in(3,4,255):assert status({**x,'sv_smp_synch':n})=='INVALID'
@pytest.mark.parametrize('k,limit',[('master_error_us',1),('mu_jitter_us',2),('sample_error_us',4)])
def test_le_clock_accuracy_not_uniform_generic_100us(k,limit):
 assert status({**le(),'sv_'+k:limit})=='VALID'
 assert status({**le(),'sv_'+k:limit+.01})=='INVALID'
def test_pps_delay_requires_compensation_and_holdover_actual_bound():
 x={**le(),'sv_pps_delay_us':2.1};assert status(x)=='UNVERIFIED'
 assert status({**x,'sv_pps_compensated':False})=='INVALID'
 assert status({**x,'sv_pps_compensated':True})=='VALID'
 x={**actual(),'sv_holdover':True,'sv_synchronized':True,'sv_holdover_elapsed_s':3,'sv_holdover_limit_s':3};assert status(x)=='VALID'
 assert status({**x,'sv_holdover_elapsed_s':3.01})=='INVALID'
 x.pop('sv_holdover_limit_s');assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('mac',['01-0C-CD-04-00-00','01:0c:cd:04:01:ff'])
def test_configured_sv_mac_range_not_goose_constructor_alias(mac):
 assert status({**actual(),'sv_multicast_mac':mac})=='VALID'
 for v in('01-0C-CD-01-00-01','01-0C-CD-04-02-00','00-00-00-00-00-00'):assert status({**actual(),'sv_multicast_mac':v})=='INVALID'
def frame():
 return {**actual(),'sv_tagged':True,'sv_mac_header_bytes':18,'sv_sv_header_bytes':8,'sv_no_asdu':1,'sv_data_bytes':64,'sv_apdu_bytes':110,'sv_software_frame_bytes':136,'sv_frame_bytes':140,'sv_occupancy_bytes':160,'sv_link_bps':100000000,'sv_wire_time_us':12.8}
@pytest.mark.parametrize('bad',[{'sv_mac_header_bytes':14},{'sv_sv_header_bytes':4},{'sv_apdu_bytes':63},{'sv_software_frame_bytes':110},{'sv_frame_bytes':136},{'sv_occupancy_bytes':140},{'sv_wire_time_us':11.2}])
def test_sample_bytes_not_apdu_or_complete_ethernet_occupation(bad):
 assert status(frame())=='VALID';assert status({**frame(),**bad})=='INVALID'
def test_pinned_buffer_limit_not_universal1500byte_application_limit():
 x={**actual(),'sv_implementation':'LIBIEC61850_1_6','sv_tagged':True,'sv_mac_header_bytes':18,'sv_sv_header_bytes':8,'sv_apdu_bytes':1492,'sv_software_frame_bytes':1518};assert status(x)=='VALID'
 assert status({**x,'sv_apdu_bytes':1493,'sv_software_frame_bytes':1519})=='INVALID'
 assert status({**x,'sv_implementation':'ACTUAL_DEVICE','sv_apdu_bytes':2000,'sv_software_frame_bytes':2026})=='VALID'
def accepted():
 return {**frame(),'sv_sample_accepted':True,'sv_smp_rate':4800,'sv_smp_mode':'SAMPLES_PER_SECOND','sv_sample_hz':4800,'sv_frame_hz':4800,'sv_conf_rev':2,'sv_peer_conf_rev':2,'sv_sv_id':'syntheticMU01','sv_channel_count':8,'sv_smp_cnt':5,'sv_wrap_count':4800,'sv_smp_synch':2,'sv_sync_state':'GLOBAL','sv_synchronized':True,'sv_purpose':'OPERATIONAL','sv_validity':'GOOD','sv_test':False,'sv_operator_blocked':False,'sv_simulation':False,'sv_outcome':'ACCEPTED','sv_mapping_valid':True,'sv_frame_verified':True,'sv_clock_verified':True,'sv_observation_source':'synthetic-full-channels-clock','sv_capture_bound_us':200,'sv_network_bound_us':100,'sv_decode_bound_us':200,'sv_e2e_bound_us':500,'sv_e2e_limit_us':500,'sv_age_us':500,'sv_freshness_us':1000,'sv_phy':'REGISTERED_ACTUAL','sv_registered_source':'syntheticPHY','sv_duplex':'FULL','sv_appid':0x4001,'sv_multicast_mac':'01-0C-CD-04-00-01','sv_priority':4,'sv_vlan_id':2}
@pytest.mark.parametrize('bad',[{'sv_validity':'INVALID'},{'sv_validity':'QUESTIONABLE'},{'sv_test':True},{'sv_operator_blocked':True},{'sv_simulation':True},{'sv_synchronized':False},{'sv_peer_conf_rev':1},{'sv_age_us':1001},{'sv_e2e_bound_us':12.8},{'sv_e2e_limit_us':499},{'sv_clock_verified':False}])
def test_bitrate_sync_bit_or_decoded_bad_quality_not_application_acceptance(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_confirmed_actual_settings_and_derived_neutral_measurement_retained():
 x={**accepted(),'sv_derived':True};before=deepcopy(x);assert status(x)=='VALID'and x==before
def test_routable_mapping_not_implicitly_ethernet_capacity_or_raw_sv_ethertype():
 x={**actual(),'sv_mapping':'REGISTERED_ROUTABLE'};assert status(x)=='UNVERIFIED'
 x.update(sv_registered_source='synthetic90-5-qualified-path');assert status(x)=='VALID'
 assert status({**le(),'sv_mapping':'REGISTERED_ROUTABLE','sv_registered_source':'synthetic'})=='INVALID'
