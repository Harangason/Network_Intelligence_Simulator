"""SunSpec information model and actual serial/TCP/security are different scopes."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.sunspec_modbus import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame

def actual():
 x={'ss_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(ss_edition='MODEL_1_1_2022',ss_transport='TCP')
 return x
def status(x):return registry.validate_parameters('sunspec_modbus',x)['status']
def secure():
 x=actual();x.update(ss_transport='SECURE_TCP',ss_secure_edition='SECURE_1_0_2025',ss_secure_source='synthetic TLS device',ss_rights_source='synthetic vendor+SunSpec pinned rights map',ss_cipher='TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256',ss_tls_version='1.2',ss_role='ReadOnlySunSpec',ss_role_oid='1.3.6.1.4.1.50316.802.1',ss_role_encoding='ASN1_UTF8STRING',ss_role_extension_count=1,ss_root_certificates=10,ss_fragment_capability_bytes=512,ss_weak_crypto=False)
 for k in('tls12_supported','mutual_tls','x509v3','certificate_request','client_certificate','tls12_gcm','tls12_chacha','tls12_ccm8','cipher_order_verified','iana_allowed','certificate_compatible','disable_discouraged','mandatory_roles','rights_configurable','role_map_verified','trust_verified','p256_supported','secure_renegotiation','compression_null','sha256_supported'):x['ss_'+k]=True
 return x

def test_sunspec_model_has_no_ethernet_rate_or_general253byte_model_cap():
 p=registry.profile('sunspec_modbus');assert p['max_payload_bytes']is None
 assert p['default_stack']==['sunspec_modbus']and p['capacity_evidence']['status']=='MODEL_MISSING'
 assert status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':500000},{'mtu_bytes':1500},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('SUNSPEC_MODBUS',8,actual()).to_dict()['transmission_time_s']is None
 assert not set(R.REMOVED)&{v['key']for v in registry.parameter_fields('sunspec_modbus')}

@pytest.mark.parametrize('f',registry.parameter_fields('sunspec_modbus'),ids=lambda f:f['key'])
def test_every_sunspec_field_type_and_individual_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'

@pytest.mark.parametrize('base',[0,40000,50000])
def test_discovery_is_zero_based_not40001(base):
 x={**actual(),'ss_map_base':base,'ss_marker_hi':0x5375,'ss_marker_lo':0x6E53};assert status(x)=='VALID'
 for bad in({'ss_map_base':40001},{'ss_marker_hi':0x5376},{'ss_marker_lo':0x6E54}):assert status({**x,**bad})=='INVALID'

def test_variable_instance_lengths_end_marker_and_next_scan():
 x={**actual(),'ss_context':'MODBUS_INSTANCE','ss_model_id':701,'ss_model_address':40002,'ss_model_length':200,'ss_next_model_address':40204};assert status(x)=='VALID'
 assert status({**x,'ss_next_model_address':40202})=='INVALID'
 assert status({**x,'ss_context':'DEFINITION'})=='INVALID'
 assert status({**x,'ss_model_id':65535})=='INVALID'
 assert status({**x,'ss_context':'DEFINITION','ss_model_length':0,'ss_next_model_address':40004})=='VALID'

@pytest.mark.parametrize('kind,registers',[('int16',1),('sunssf',1),('int32',2),('float32',2),('int64',4),('float64',4),('ipv6addr',8),('eui48',3)])
def test_point_widths_are_registers_and_whole_big_endian(kind,registers):
 x={**actual(),'ss_point_type':kind,'ss_point_registers':registers,'ss_point_bytes':registers*2,'ss_word_order':'BIG_ENDIAN'};assert status(x)=='VALID'
 for bad in({'ss_point_registers':registers+1},{'ss_point_bytes':registers},{'ss_word_order':'LITTLE_ENDIAN'}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'ss_definition_size':registers})=='INVALID'

def test_string_size_static_count_scalefactor_and_atomic_group():
 x={**actual(),'ss_point_type':'string','ss_definition_size':8,'ss_point_registers':8,'ss_point_bytes':16};assert status(x)=='VALID'
 assert status({**x,'ss_point_registers':16})=='INVALID'
 del x['ss_definition_size'];assert status(x)=='UNVERIFIED'
 x={**actual(),'ss_point_count':4,'ss_count_static':True,'ss_count_defined_before':True,'ss_sf':-3,'ss_sf_static':True,'ss_sf_type_verified':True};assert status(x)=='VALID'
 for k in('ss_count_static','ss_count_defined_before','ss_sf_static','ss_sf_type_verified'):assert status({**x,k:False})=='INVALID'
 x={**actual(),'ss_group_type':'sync','ss_group_registers':100,'ss_atomic_registers':100,'ss_atomic':True};assert status(x)=='VALID'
 assert status({**x,'ss_atomic_registers':50})=='INVALID';assert status({**x,'ss_atomic':False})=='INVALID'

@pytest.mark.parametrize('t,raw',[('int16','8000'),('uint16','FFFF'),('int32','80000000'),('uint32','FFFFFFFF'),('uint64','FFFFFFFFFFFFFFFF'),('float32','7FC00000'),('float64','7FF8000000000000'),('sunssf','8000')])
def test_typed_unimplemented_sentinel_is_never_valid_or_mandatory(t,raw):
 x={**actual(),'ss_point_type':t,'ss_raw_hex':raw.lower(),'ss_availability':'NOT_IMPLEMENTED','ss_mandatory':'O'};assert status(x)=='VALID'
 assert status({**x,'ss_availability':'VALID'})=='INVALID';assert status({**x,'ss_mandatory':'M'})=='INVALID'
 assert status({**x,'ss_raw_hex':'0001'})=='INVALID'

@pytest.mark.parametrize('t,value',[('int16',-32768),('uint16',65535),('uint32',4294967295),('uint64',18446744073709551615),('acc64',9223372036854775808),('bitfield16',32768),('sunssf',11)])
def test_reserved_values_and_source_specific_numeric_ranges(t,value):
 assert status({**actual(),'ss_point_type':t,'ss_availability':'VALID','ss_value':value})=='INVALID'
 assert status({**actual(),'ss_point_type':t,'ss_availability':'VALID','ss_value':0})=='VALID'

def test_read125_write123_single6optional_and_address_space():
 x={**actual(),'ss_function':3,'ss_quantity':125,'ss_byte_count':250,'ss_register_address':65411};assert status(x)=='VALID'
 assert status({**x,'ss_register_address':65412})=='INVALID';assert status({**x,'ss_byte_count':125})=='INVALID'
 assert status({**x,'ss_function':16})=='INVALID'
 assert status({**x,'ss_function':16,'ss_quantity':123,'ss_byte_count':246})=='VALID'
 x={**actual(),'ss_function':6,'ss_quantity':1,'ss_support6':True};assert status(x)=='VALID'
 assert status({**x,'ss_support6':False})=='INVALID'
 del x['ss_support6'];assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('case',['UNIMPLEMENTED','INVALID_VALUE','READ_ONLY'])
def test_value_write_errors_differ_from_authorization(case):
 for code in(2,3,4):assert status({**actual(),'ss_write_case':case,'ss_exception_code':code})=='VALID'
 assert status({**actual(),'ss_write_case':case,'ss_exception_code':1})=='INVALID'
 assert status({**actual(),'ss_write_case':'AUTHORIZATION_DENIED','ss_exception_code':1})=='VALID'

@pytest.mark.parametrize('transport',['SERIAL_RTU','SERIAL_ASCII'])
def test_actual_serial_binding_has_no_tcp_port_or_guessed_unit(transport):
 x={**actual(),'ss_transport':transport,'ss_unit_id':247};assert status(x)=='VALID'
 for bad in({'ss_unit_id':0},{'ss_unit_id':248},{'ss_tcp_port':502}):assert status({**x,**bad})=='INVALID'

def test_literature_defaults_are_conditional_and_do_not_confirm_device():
 fields={f['key']:f for f in registry.parameter_fields('sunspec_modbus')}
 for k in('ss_map_base','ss_unit_id','ss_model_id','ss_sf','ss_value'):assert 'default'not in fields[k]and'conditional_defaults'not in fields[k]
 assert {p['value']for p in fields['ss_tcp_port']['conditional_defaults']}=={502,802}
 assert fields['ss_access']['conditional_defaults'][0]['value']=='R'
 assert fields['ss_mandatory']['conditional_defaults'][0]['value']=='O'

def test_secure2025_own_mandatory_tls_capabilities_and_three_suite_order():
 x=secure();assert status(x)=='VALID'
 for k in('ss_tls12_chacha','ss_mutual_tls','ss_role_map_verified','ss_trust_verified','ss_cipher_order_verified','ss_rights_configurable','ss_p256_supported','ss_certificate_compatible','ss_iana_allowed'):
  assert status({**x,k:False})=='INVALID'
  absent=dict(x);del absent[k];assert status(absent)=='UNVERIFIED'
 for bad in({'ss_root_certificates':9},{'ss_role_extension_count':2},{'ss_role_oid':'1.2.3'},{'ss_weak_crypto':True},{'ss_compression_null':False},{'ss_resume_after_fatal':True}):assert status({**x,**bad})=='INVALID'

def test_optional_tls13_requires_own_suites_while_tls12_still_supported():
 x=secure();x.update(ss_tls_version='1.3',ss_cipher='TLS_AES_128_GCM_SHA256',ss_tls13_supported=True,ss_tls13_gcm=True,ss_tls13_chacha=True,ss_tls13_ccm=True);assert status(x)=='VALID'
 for bad in({'ss_tls12_supported':False},{'ss_tls13_ccm':False},{'ss_cipher':'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256'}):assert status({**x,**bad})=='INVALID'

def test_public_root_trust_and_role_denial_are_not_success():
 x={**secure(),'ss_public_network':True,'ss_ca_signed':True};assert status(x)=='VALID'
 assert status({**x,'ss_ca_signed':False})=='INVALID'
 assert status({**x,'ss_authorized':False,'ss_exception_code':1})=='VALID'
 assert status({**x,'ss_authorized':False,'ss_exception_code':2})=='INVALID'

def test_read_after_write_is_information_exchange_not_operating_behavior():
 x={**actual(),'ss_write_success':True,'ss_readback_match':True};assert status(x)=='VALID'
 assert status({**x,'ss_readback_match':False})=='INVALID';assert status({**x,'ss_data_accepted':True})=='UNVERIFIED'
 x={**actual(),'ss_source_ms':1,'ss_transport_ms':2,'ss_consumer_ms':3,'ss_e2e_ms':6,'ss_deadline_ms':6,'ss_age_ms':5,'ss_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'ss_e2e_ms':2},{'ss_deadline_ms':5},{'ss_freshness_ms':4}):assert status({**x,**bad})=='INVALID'

def test_typed_integer_point_values_do_not_accept_fractional_registers():
 assert status({**actual(),'ss_point_type':'uint16','ss_availability':'VALID','ss_value':.5})=='INVALID'
 assert status({**actual(),'ss_point_type':'float32','ss_availability':'VALID','ss_value':.5})=='VALID'

@pytest.mark.parametrize('phase,function,quantity,pdu',[('REQUEST',3,125,5),('RESPONSE',3,125,252),('REQUEST',16,123,252),('RESPONSE',16,123,5),('REQUEST',6,1,5),('EXCEPTION',131,1,2)])
def test_pdu_sizes_include_function_and_control_not_model_size(phase,function,quantity,pdu):
 x={**actual(),'ss_phase':phase,'ss_function':function,'ss_quantity':quantity,'ss_pdu_bytes':pdu,'ss_support6':True};assert status(x)=='VALID'
 assert status({**x,'ss_pdu_bytes':pdu+1})=='INVALID'

def test_registered_edition_cannot_reuse_current_model_limits():
 x={**actual(),'ss_edition':'REGISTERED_ACTUAL','ss_registered_source':'synthetic registered definition','ss_map_base':40000};assert status(x)=='UNVERIFIED'

def test_readonly_certificate_cannot_authorize_write_by_role_flag():
 x={**secure(),'ss_operation':'WRITE','ss_authorized':False,'ss_exception_code':1};assert status(x)=='VALID'
 assert status({**x,'ss_authorized':True})=='INVALID'
