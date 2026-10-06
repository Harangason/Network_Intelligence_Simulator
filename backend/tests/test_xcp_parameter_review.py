import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as R
from backend.nis.communication.technologies.xcp import rules as N
def base():return {'xc_'+k:'synthetic-'+k for k in N.REQUIRED}
def status(x):return R.validate_parameters('xcp',x)['status']
@pytest.mark.parametrize('f',R.parameter_fields('xcp'),ids=lambda f:f['key'])
def test_every_field_type_and_outer_bound(f):
 assert status({**base(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,off in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**base(),f['key']:f[side]+off})=='INVALID'
@pytest.mark.parametrize('unit,factor',N.UNITS.items())
def test_every_sampling_unit_and_noncyclic_zero(unit,factor):
 x={**base(),'xc_event_unit':unit,'xc_event_cycle':2,'xc_event_ms':2*factor};assert status(x)=='VALID';assert status({**x,'xc_event_ms':100})=='INVALID'
 assert status({**x,'xc_event_cycle':0,'xc_event_ms':0})=='VALID';assert status({**x,'xc_event_cycle':0,'xc_event_ms':1})=='INVALID'
@pytest.mark.parametrize('kind,maximum',[('CTO',8),('DTO',16)])
def test_negotiated_packet_and_transport_budget_not_application_limit(kind,maximum):
 x={**base(),'xc_packet_kind':kind,'xc_max_cto':8,'xc_max_dto':16,'payload_bytes':maximum-2,'xc_protocol_overhead_bytes':2,'xc_packet_bytes':maximum,'xc_lower_packet_max':maximum};assert status(x)=='VALID'
 for bad in [{'xc_packet_bytes':maximum+1},{'xc_lower_packet_max':maximum-1},{'payload_bytes':maximum}]:assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('transport',['UDP_IP','TCP_IP'])
def test_autosar_slave_single_connection(transport):
 x={**base(),'xc_edition':'AUTOSAR_R25_11','xc_transport':transport,'xc_connections':1};assert status(x)=='VALID';assert status({**x,'xc_connections':2})=='INVALID'
def test_can_receive_and_transmit_ids_are_distinct():
 x={**base(),'xc_transport':'CAN','xc_can_tx_id':257,'xc_can_rx_id':256};assert status(x)=='VALID';assert status({**x,'xc_can_rx_id':257})=='INVALID'
@pytest.mark.parametrize('k',['xc_odt_count','xc_odt_entries'])
def test_dynamic_daq_fields_not_static(k):
 assert status({**base(),'xc_daq_config':'DYNAMIC',k:1})=='VALID';assert status({**base(),'xc_daq_config':'STATIC',k:1})=='INVALID'
def test_source_to_use_not_cto_response():
 x={**base(),'xc_source_ms':1,'xc_transport_ms':2,'xc_use_ms':3,'xc_e2e_ms':6,'xc_deadline_ms':6,'xc_age_ms':4,'xc_freshness_ms':4,'xc_data_accepted':True,'xc_path_verified':True,'xc_observation_source':'synthetic','xc_outcome':'ACCEPTED'};assert status(x)=='VALID'
 for bad in [{'xc_e2e_ms':2},{'xc_deadline_ms':5},{'xc_age_ms':5},{'xc_outcome':'PACKET_ONLY'}]:assert status({**x,**bad})=='INVALID'
def test_bus_independent_no_implicit_can_rate_or_device_sizes():
 p=R.profile('xcp');assert p['default_stack']==['xcp']and p['capacity_evidence']['status']=='MODEL_MISSING'and p['domain']=='generic_networking';assert status({})=='UNVERIFIED';assert status({**base(),'bitrate':500000})=='INVALID'
 f={v['key']:v for v in R.parameter_fields('xcp')};assert 'default'not in f['xc_max_cto']and'conditional_defaults'not in f['xc_max_dto']
