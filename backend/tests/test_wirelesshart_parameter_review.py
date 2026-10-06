import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as R
from backend.nis.communication.technologies.wirelesshart import rules as N
def base():return {'wh_'+k:'synthetic-'+k for k in N.REQUIRED}
def status(x):return R.validate_parameters('wirelesshart',x)['status']
@pytest.mark.parametrize('f',R.parameter_fields('wirelesshart'),ids=lambda f:f['key'])
def test_every_exported_field_type_and_bounds(f):
 assert status({**base(),f['key']:'wrong' if f['type']=='number' else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**base(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('channel',range(11,26))
def test_qualified_radio_channel_frequency_not_host_baud(channel):
 x={**base(),'wh_radio':'LTC5800_WHM','wh_channel':channel,'wh_centre_mhz':2405+5*(channel-11),'wh_rate_bps':250000,'wh_slot_us':10000};assert status(x)=='VALID'
 for bad in [{'wh_channel':26},{'wh_rate_bps':115200},{'wh_centre_mhz':2440.1},{'wh_slot_us':5000}]:assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('slots',range(1,12))
def test_manager_superframe_explicit_schedule_bound(slots):
 x={**base(),'wh_superframe_slots':slots,'wh_slot_us':10000,'wh_superframe_us':10000*slots,'wh_slot_index':slots-1,'wh_allocated_slots':slots};assert status(x)=='VALID'
 for bad in [{'wh_slot_index':slots},{'wh_allocated_slots':slots+1},{'wh_superframe_us':10000*slots+1}]:assert status({**x,**bad})=='INVALID'
def test_full_frame_and_nominal_airtime_do_not_prove_mesh_schedule():
 x={**base(),'payload_bytes':8,'wh_header_bytes':10,'wh_security_bytes':4,'wh_fcs_bytes':2,'wh_psdu_bytes':24,'wh_peer_psdu_max':24,'wh_phy_bytes':6,'wh_rate_bps':250000,'wh_air_us':960};assert status(x)=='VALID'
 assert status({**x,'wh_psdu_bytes':8})=='INVALID';assert status({**x,'wh_air_us':256})=='INVALID';assert status({**x,'wh_peer_psdu_max':23})=='INVALID'
@pytest.mark.parametrize('bad',[{'wh_deadline_ms':5},{'wh_age_ms':5},{'wh_e2e_ms':1},{'wh_schedule_verified':False},{'wh_security_verified':False},{'wh_outcome':'RADIO_ACK_ONLY'}])
def test_function_acceptance_independent_from_radio_ack(bad):
 x={**base(),'wh_source_ms':1,'wh_mesh_ms':2,'wh_use_ms':3,'wh_e2e_ms':6,'wh_deadline_ms':6,'wh_age_ms':4,'wh_freshness_ms':4,'wh_data_accepted':True,'wh_schedule_verified':True,'wh_security_verified':True,'wh_observation_source':'synthetic','wh_outcome':'ACCEPTED'};assert status(x)=='VALID';assert status({**x,**bad})=='INVALID'
def test_unknown_hardware_and_schedule_not_nominal_confirmation():
 assert status({})=='UNVERIFIED';assert status(base())=='VALID';assert status({**base(),'bitrate':250000})=='INVALID'
 p=R.profile('wirelesshart');assert p['capacity_evidence']['status']=='MODEL_MISSING'and p['max_payload_bytes']is None and p['domain']=='generic_networking'
