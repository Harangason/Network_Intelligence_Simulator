import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as R
from backend.nis.communication.technologies.zigbee import rules as N
def base():return {'zb_'+k:'synthetic-'+k for k in N.REQUIRED}
def status(x):return R.validate_parameters('zigbee',x)['status']
@pytest.mark.parametrize('f',R.parameter_fields('zigbee'),ids=lambda f:f['key'])
def test_every_field_type_and_bounds(f):
 assert status({**base(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**base(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('bytes_',range(2,128,5))
def test_full_psdu_and_phy_airtime_not_only_application(bytes_):
 x={**base(),'zb_phy':'IEEE_2G4_2006','zb_psdu_bytes':bytes_,'zb_phy_bytes':6,'zb_fcs_bytes':2,'zb_rate_bps':250000,'zb_air_us':32*(bytes_+6)};assert status(x)=='VALID'
 for bad in [{'zb_psdu_bytes':128},{'zb_phy_bytes':5},{'zb_rate_bps':2000000},{'zb_air_us':32*bytes_}]:assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('hops',range(1,12))
def test_aps_sdk_default_uses_actual_hops_not_fixed_can_deadline(hops):
 x={**base(),'zb_stack':'EMBERZNET_8_2_1','zb_ack_default':True,'zb_max_hops':hops,'zb_aps_ack_ms':50*hops+100};assert status(x)=='VALID';assert status({**x,'zb_aps_ack_ms':50*hops})=='INVALID'
def test_payload_fragment_and_security_actual_limits():
 x={**base(),'payload_bytes':82,'zb_fragmented':False,'zb_frame_application_bytes':82,'zb_peer_aps_max':82,'zb_mac_bytes':9,'zb_nwk_bytes':8,'zb_aps_bytes':8,'zb_security_bytes':18,'zb_fcs_bytes':2,'zb_psdu_bytes':127};assert status(x)=='VALID';assert status({**x,'zb_peer_aps_max':68})=='INVALID';assert status({**x,'zb_psdu_bytes':82})=='INVALID'
 assert status({**x,'zb_fragmented':True,'payload_bytes':300})=='VALID'
def test_retry_discovery_and_fragment_identity_not_queued_success():
 x={**base(),'zb_stack':'EMBERZNET_8_2_1','zb_aps_retry':True,'zb_attempts':3,'zb_forced_discovery':True};assert status(x)=='VALID';assert status({**x,'zb_attempts':2})=='VALID';assert status({**x,'zb_attempts':4})=='INVALID';assert status({**x,'zb_aps_retry':False})=='INVALID'
 x={**base(),'zb_fragmented':True,'zb_fragment_index':1,'zb_sequence':255,'zb_first_sequence':255};assert status(x)=='VALID';assert status({**x,'zb_sequence':0})=='INVALID'
def test_eui64_stays_exact_hex_text():
 assert status({**base(),'zb_destination_eui64':'FFFFFFFFFFFFFFFF'})=='VALID';assert status({**base(),'zb_destination_eui64':'FFFFFFFFFFFFFFF'})=='INVALID'
def test_function_deadline_and_freshness_independent_ack():
 x={**base(),'zb_source_ms':1,'zb_mesh_ms':2,'zb_use_ms':3,'zb_e2e_ms':6,'zb_deadline_ms':6,'zb_age_ms':4,'zb_freshness_ms':4,'zb_data_accepted':True,'zb_path_verified':True,'zb_observation_source':'synthetic','zb_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in [{'zb_deadline_ms':5},{'zb_age_ms':5},{'zb_e2e_ms':2},{'zb_outcome':'APS_ACK_ONLY'},{'zb_outcome':'QUEUED'}]:assert status({**x,**bad})=='INVALID'
def test_explicit_phy_no_inherited_can_or_127_application():
 assert status({})=='UNVERIFIED';assert status({**base(),'bitrate':250000})=='INVALID';p=R.profile('zigbee');assert p['max_payload_bytes']is None and p['capacity_evidence']['status']=='MODEL_MISSING'and p['default_stack']==['zigbee']
