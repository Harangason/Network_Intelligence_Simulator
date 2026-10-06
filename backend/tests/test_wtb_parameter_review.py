import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as R
from backend.nis.communication.technologies.wtb import rules as N
def base():return {'wt_'+k:'synthetic-'+k for k in N.REQUIRED}
def status(x):return R.validate_parameters('wtb',x)['status']
@pytest.mark.parametrize('f',R.parameter_fields('wtb'),ids=lambda f:f['key'])
def test_every_field_type_and_bounds(f):
 assert status({**base(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**base(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('exponent',range(8))
def test_inaugurated_process_period_not_can_cycle(exponent):
 x={**base(),'wt_period_exponent':exponent,'wt_process_ms':25*2**exponent};assert status(x)=='VALID';assert status({**x,'wt_process_ms':25*2**exponent+1})=='INVALID'
@pytest.mark.parametrize('bytes_',range(0,129,8))
def test_full_frame_not_payload_only(bytes_):
 x={**base(),'payload_bytes':bytes_,'wt_frame_data_bytes':bytes_,'wt_preamble_bits':16,'wt_stuffed_bits':0,'wt_frame_bits':82+8*bytes_,'wt_rate_bps':1000000,'wt_air_us':82+8*bytes_};assert status(x)=='VALID'
 for bad in [{'wt_frame_bits':8*bytes_},{'wt_stuffed_bits':(48+8*bytes_)//5+1},{'wt_air_us':1}]:assert status({**x,**bad})=='INVALID'
def test_periodic_phase_cannot_consume_supervisory_phase():
 x={**base(),'wt_basic_ms':25,'wt_periodic_ms':15,'wt_sporadic_ms':10};assert status(x)=='VALID';assert status({**x,'wt_periodic_ms':16,'wt_sporadic_ms':9})=='INVALID';assert status({**x,'wt_sporadic_ms':15})=='INVALID'
@pytest.mark.parametrize('profile,rate',[('STANDARD_1M',1000000),('EKE_ORDERED_HALF',500000)])
def test_half_speed_is_qualified_order_not_standard_default(profile,rate):
 x={**base(),'wt_profile':profile,'wt_rate_bps':rate};assert status(x)=='VALID';assert status({**x,'wt_rate_bps':rate/2})=='INVALID'
def test_topology_master_address_and_independent_function_acceptance():
 assert status({**base(),'wt_role':'MASTER','wt_address':1})=='VALID';assert status({**base(),'wt_role':'MASTER','wt_address':2})=='INVALID';assert status({**base(),'wt_role':'SLAVE','wt_address':1})=='INVALID'
 x={**base(),'wt_source_ms':1,'wt_transport_ms':2,'wt_use_ms':3,'wt_e2e_ms':6,'wt_deadline_ms':6,'wt_age_ms':4,'wt_freshness_ms':4,'wt_data_accepted':True,'wt_inaugurated':True,'wt_schedule_verified':True,'wt_observation_source':'synthetic','wt_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in [{'wt_deadline_ms':5},{'wt_inaugurated':False},{'wt_schedule_verified':False},{'wt_outcome':'FRAME_ONLY'}]:assert status({**x,**bad})=='INVALID'
def test_own_profile_no_gateway_bitrate_or_capacity_fallback():
 assert status({})=='UNVERIFIED';assert status(base())=='VALID';assert status({**base(),'bitrate':1000000})=='INVALID';assert R.profile('wtb')['capacity_evidence']['status']=='MODEL_MISSING'
