"""Negotiated PCIe values, source-qualified packet/credits and application isolation."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.pcie import rules as P

def actual():
 x={'pcie_'+k:'synthetic-'+k for k in P.REQUIRED}
 x.update(pcie_implementation='REGISTERED_ACTUAL',pcie_mode='NON_FLIT',pcie_encoding='8B10B',
  pcie_role='ENDPOINT',pcie_generation=1,pcie_lanes=1)
 return x

def status(x):return registry.validate_parameters('pcie',x)['status']

def test_pcie_own_profile_has_no_can_or_ethernet_payload_clock_assumption():
 p=registry.profile('pcie');assert p['default_stack']==['pcie'] and p['max_payload_bytes']is None
 assert p['domain']=='generic_networking' and p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'
 fields=registry.parameter_fields('pcie');keys=[v['key']for v in fields]
 assert len(keys)==len(set(keys))and not set(keys)&set(P.REMOVED)
 for bad in ({'bitrate_bps':8000000000},{'mtu_bytes':1500},{'local_timing_evidence':{}},{'os_service':'SPDO'}):
  assert status({**actual(),**bad})=='INVALID'
 assert status({**actual(),'payload_bytes':100000})=='VALID'

@pytest.mark.parametrize('field',registry.parameter_fields('pcie'),ids=lambda f:f['key'])
def test_pcie_each_declared_type_unit_and_outer_bound(field):
 bad='not-number' if field['type']=='number' else 1
 assert status({**actual(),field['key']:bad})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('gen,rate,encoding',[(1,2.5,'8B10B'),(2,5,'8B10B'),(3,8,'128B130B'),(4,16,'128B130B'),(5,32,'128B130B'),(6,64,'FLIT_PAM4'),(7,128,'FLIT_PAM4')])
def test_pcie_generation_lane_rate_and_encoding_are_separate(gen,rate,encoding):
 x={**actual(),'pcie_generation':gen,'pcie_rate_gts':rate,'pcie_lanes':16,'pcie_max_lanes':16,
  'pcie_encoding':encoding,'pcie_mode':'FLIT'if gen>=6 else'NON_FLIT','pcie_flit_supported':True,
  'pcie_raw_direction_bps':rate*1e9*16,'pcie_max_generation':gen}
 assert status(x)=='VALID'
 for bad in ({'pcie_rate_gts':rate+0.1},{'pcie_raw_direction_bps':rate*1e9*32},{'pcie_max_lanes':8},{'pcie_lanes':3}):
  assert status({**x,**bad})=='INVALID'
 if gen>=6:
  assert status({**x,'pcie_mode':'NON_FLIT'})=='INVALID'
  assert status({**x,'pcie_flit_supported':False})=='INVALID'
 else:assert status({**x,'pcie_encoding':'FLIT_PAM4'})=='INVALID'

def test_pcie_baseline_proposals_not_actual_link_or_hardware_defaults():
 f={v['key']:v for v in registry.parameter_fields('pcie')}
 assert f['pcie_generation']['default']==f['pcie_lanes']['default']==1
 assert f['pcie_mps']['default']==f['pcie_mrrs']['default']==128
 assert f['pcie_rate_gts']['conditional_defaults'][0]['value']==2.5
 for k in ('pcie_mps_supported','pcie_header_credits','pcie_completion_timeout_us','pcie_link_active','payload_bytes'):
  assert 'default'not in f[k]and not f[k].get('conditional_defaults')

def test_pcie_decoded_ceiling_not_bidirectional_or_measured_goodput():
 x={**actual(),'pcie_rate_gts':2.5,'pcie_raw_direction_bps':2.5e9,'pcie_decoded_ceiling_bps':2e9}
 assert status(x)=='VALID'
 assert status({**x,'pcie_decoded_ceiling_bps':4e9})=='INVALID'
 x.update(pcie_generation=3,pcie_encoding='128B130B',pcie_rate_gts=8,pcie_raw_direction_bps=8e9,pcie_decoded_ceiling_bps=8e9*128/130)
 assert status(x)=='VALID'

def test_pcie_mps_and_mrrs_are_independent_device_and_path_limits():
 x={**actual(),'pcie_mps':128,'pcie_mps_supported':512,'pcie_path_mps':256,'pcie_mrrs':4096,
  'pcie_mps_code':0,'pcie_mrrs_code':5,'pcie_tlp_payload_bytes':128,'pcie_request_bytes':4096,'pcie_remaining_bytes':4000}
 assert status(x)=='VALID'
 for bad in ({'pcie_tlp_payload_bytes':129},{'pcie_mps':1024},{'pcie_mps':192},{'pcie_mps_code':6},
             {'pcie_mrrs_code':0},{'pcie_remaining_bytes':4097}):
  assert status({**x,**bad})=='INVALID'

def test_pcie_nonflit_and_flit_geometry_are_not_combined_or_truncated():
 x={**actual(),'pcie_header_bytes':12,'pcie_prefix_bytes':0,'pcie_tlp_payload_bytes':128,
  'pcie_digest_bytes':4,'pcie_ecrc_enabled':True,'pcie_ecrc_supported':True,
  'pcie_lcrc_bytes':4,'pcie_framing_bytes':4,'pcie_packet_bytes':152}
 assert status(x)=='VALID'
 assert status({**x,'pcie_packet_bytes':150})=='INVALID'
 assert status({**x,'pcie_ecrc_supported':False})=='INVALID'
 x={**actual(),'pcie_mode':'FLIT','pcie_generation':6,'pcie_encoding':'FLIT_PAM4','pcie_flit_supported':True,
  'pcie_tlp_payload_bytes':4096,'pcie_flit_bytes':256,'pcie_flit_tlp_bytes':236,
  'pcie_flit_dlp_bytes':6,'pcie_flit_crc_bytes':8,'pcie_flit_fec_bytes':6}
 assert status(x)=='VALID'
 for bad in ({'pcie_lcrc_bytes':4},{'pcie_flit_tlp_bytes':242},{'pcie_decoded_ceiling_bps':64e9*128/130}):
  assert status({**x,**bad})=='INVALID'
 x.update(pcie_generation=3,pcie_encoding='REGISTERED_LOWER_RATE_FLIT')
 assert status(x)=='VALID'
 assert status({**x,'pcie_encoding':'128B130B'})=='INVALID'

def test_pcie_implementation_capabilities_are_not_universal_defaults():
 x={**actual(),'pcie_implementation':'AGILEX5_GTS_25_3','pcie_generation':4,'pcie_encoding':'128B130B',
  'pcie_lanes':8,'pcie_mps':256,'pcie_mps_supported':512,'pcie_mrrs':4096,
  'pcie_vc_count':1,'pcie_virtual_channel':0,'pcie_tag_bits':10,'pcie_tag_capacity':512,'pcie_clock':'SRIS'}
 assert status(x)=='VALID'
 for bad in ({'pcie_mps_supported':4096},{'pcie_virtual_channel':1},{'pcie_generation':5},
             {'pcie_implementation':'AGILEX3_GTS_25_3'},{'pcie_lanes':4}):
  assert status({**x,**bad})=='INVALID'

def test_pcie_available_credits_not_raw_advertised_counter_control_emission():
 x={**actual(),'pcie_implementation':'AGILEX3_GTS_25_3','pcie_tlp_payload_bytes':20,
  'pcie_needed_data_credits':2,'pcie_data_credits':2,'pcie_header_credits':1,
  'pcie_transmission_started':True,'pcie_link_active':True,'pcie_training':False}
 assert status(x)=='VALID'
 for bad in ({'pcie_needed_data_credits':1},{'pcie_data_credits':1},{'pcie_header_credits':0},{'pcie_tlp_payload_bytes':17},
             {'pcie_training':True},{'pcie_link_active':False}):
  assert status({**x,**bad})=='INVALID'
 x.pop('pcie_data_credits');assert status(x)=='UNVERIFIED'

def test_pcie_tags_address_and_ordering_are_lossless_and_correlated():
 x={**actual(),'pcie_tag_bits':10,'pcie_tag':1023,'pcie_address_hex':'FFFFFFFFFFFFFFFF',
  'pcie_outstanding_requests':512,'pcie_tag_capacity':512,'pcie_relaxed_ordering':True,'pcie_ordering_source':'actual-coherency'}
 assert status(x)=='VALID'
 for bad in ({'pcie_tag_bits':8},{'pcie_outstanding_requests':513},{'pcie_address_hex':18446744073709551615}):
  assert status({**x,**bad})=='INVALID'
 x.pop('pcie_ordering_source');assert status(x)=='UNVERIFIED'

def test_pcie_link_ack_does_not_prove_nonposted_completion_or_application_acceptance():
 x={**actual(),'pcie_traffic':'NON_POSTED','pcie_data_accepted':True,'pcie_outcome':'ACCEPTED',
  'pcie_poisoned':False,'pcie_completion_received':True,'pcie_completion_success':True,'pcie_tag_unique':True,
  'pcie_completion_timeout_disabled':False,'pcie_completion_timeout_us':10000,'pcie_completion_elapsed_us':500,
  'pcie_age_us':500,'pcie_freshness_limit_us':1000}
 assert status(x)=='VALID'
 for bad in ({'pcie_completion_success':False},{'pcie_tag_unique':False},{'pcie_poisoned':True},
             {'pcie_completion_elapsed_us':10001},{'pcie_age_us':1001}):
  assert status({**x,**bad})=='INVALID'
 x.pop('pcie_completion_received');assert status(x)=='UNVERIFIED'
 assert registry.profile('pcie')['capacity_evidence']['status']=='MODEL_MISSING'

def test_pcie_conventional_reset_wait_not_link_training_or_can_recovery():
 x={**actual(),'pcie_conventional_reset':True,'pcie_readiness_notification':False,'pcie_reset_wait_us':1000000}
 assert status(x)=='VALID'
 assert status({**x,'pcie_reset_wait_us':999999})=='INVALID'
 assert status({**x,'pcie_readiness_notification':True,'pcie_reset_wait_us':1})=='VALID'
 assert status({**actual(),'pcie_completion_timeout_disabled':True,'pcie_completion_timeout_disable_supported':False})=='INVALID'

def test_pcie_foreign_rate_rejection_preserves_confirmed_negotiated_values():
 x={**actual(),'pcie_generation':4,'pcie_encoding':'128B130B','pcie_lanes':4,'pcie_rate_gts':16,'pcie_mps':256,'pcie_mrrs':1024}
 before=deepcopy(x);assert status({**x,'bitrate_bps':500000})=='INVALID'
 assert x==before and status(x)=='VALID'

def test_pcie_invalid_large_tag_width_cannot_allocate_unbounded_exact_power():
 assert status({**actual(),'pcie_tag_bits':1000000000,'pcie_tag':1})=='INVALID'
 from backend.nis.communication.core.components import _parameter_expression
 import math
 assert math.isnan(_parameter_expression({'ceiling':{'product':[17,1/16]}},{},exact=True))
 assert math.isnan(_parameter_expression({'power':[2,'width']},{'width':1000000000},exact=True))
 assert math.isnan(_parameter_expression('width',{'width':{'power':[2,32]}},exact=True))
 assert _parameter_expression({'ceiling':[{'product':[20,1/16]}]},{},exact=True)==2
 assert math.isnan(_parameter_expression({'product':[1e300,1e300]},{},exact=True))
 assert math.isnan(_parameter_expression({'power':[2,32,1]},{},exact=True))
 assert status({**actual(),'pcie_tag_bits':10**400,'pcie_tag':1})=='INVALID'

def test_pcie_link_status_and_memory_page_span_decode_actual_registers():
 x={**actual(),'pcie_generation':4,'pcie_encoding':'128B130B','pcie_lanes':4,
  'pcie_link_status_hex':'2044','pcie_link_status':0x2044,'pcie_training':False,'pcie_link_active':True,
  'pcie_address_space':'MEMORY','pcie_address_hex':'FFFFFFFFFFFFF000','pcie_page_offset':0,'pcie_request_bytes':4096}
 assert status(x)=='VALID'
 for bad in ({'pcie_training':True},{'pcie_generation':3},{'pcie_lanes':1},{'pcie_link_status':0x2043},
             {'pcie_page_offset':1},{'pcie_address_hex':'FFFFFFFFFFFFF001'}):
  assert status({**x,**bad})=='INVALID'
 x.update(pcie_address_hex='FFFFFFFFFFFFF001',pcie_page_offset=1,pcie_request_bytes=4095)
 assert status(x)=='VALID'
