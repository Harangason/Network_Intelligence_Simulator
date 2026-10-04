"""MBAP framing/correlation/resources and separately scoped Security requirements."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.modbus_tcp import rules as MT
from backend.nis.communication.core.physical import physical_profile

def actual():
    x={'mt_'+k:'synthetic-actual-'+k for k in MT.REQUIRED}
    x.update(mt_profile='GUIDE_1_0B',mt_mode='PLAIN',mt_role='CLIENT',mt_destination='DIRECT_TCP',
       mt_transaction_id=9,mt_request_transaction_id=9,mt_unit_id=255,mt_request_unit_id=255,
       mt_connection_id='synthetic-conn',mt_request_connection_id='synthetic-conn',mt_pending_match=True)
    return x
def status(x):return registry.validate_parameters('modbus_tcp',x)['status']
def secure():
    x={**actual(),'mt_mode':'SECURITY_V36','mt_port':802,'mt_tls_version':'TLS1_2','mt_credential_kind':'X509V3',
       'mt_key_kind':'RSA','mt_encryption_required':True,'mt_authorization_enabled':False,
       'mt_tls_source':'synthetic-actual-TLS','mt_certificate_ref':'synthetic-cert-reference','mt_trust_ref':'synthetic-PKI',
       'mt_cipher':'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256','mt_cipher_registry_source':'synthetic-IANA-and-policy-review',
       'mt_mutual_auth':True,'mt_certificate_validated':True,'mt_mfl_extension':True,'mt_mfl_512_supported':True,
       'mt_secure_renegotiation':True,'mt_rsa_required_suite_supported':True}
    return x

def test_tcp_application_has_no_own_rate_or_serial_ethernet_defaults():
    fields={f['key']:f for f in registry.parameter_fields('modbus_tcp')}
    assert not set(MT.REMOVED)&set(fields)
    assert registry.parameter_defaults_review('modbus_tcp')['values']=={}
    assert physical_profile('modbus_tcp')is None
    assert fields['mt_port']['conditional_defaults'][0]['value']==502
    assert fields['mt_port']['conditional_defaults'][1]['value']==802
    assert fields['mt_unit_id']['conditional_defaults'][0]['value']==255
    for key in ('mt_client_transaction_cap','mt_server_transaction_cap','mt_transaction_id','mt_response_timeout_ms',
                'mt_certificate_ref','mt_certificate_role','mt_driver_receive_bytes'):
        assert 'conditional_defaults'not in fields[key]
    assert 'default'not in fields['payload_bytes']
    assert status(actual())=='VALID';assert status(secure())=='VALID'
    for patch in ({'bitrate':100000000},{'duplex':'FULL'},{'mtu_bytes':1500},{'vlan_id':0},
      {'ma_lrc':0},{'mr_crc_bits':16},{'queue_size':1024},{'retry_limit':3},
      {'local_timing_evidence':{'technology':'I2C'}}):assert status({**actual(),**patch})=='INVALID'
    assert registry.profile('modbus_tcp')['capacity_evidence']['status']=='MODEL_MISSING'

@pytest.mark.parametrize('field',registry.parameter_fields('modbus_tcp'),ids=lambda f:f['key'])
def test_tcp_every_declared_type_and_own_bounds(field):
    base=secure() if field.get('source')==MT.SECURITY else actual()
    wrong='not-number'if field['type']=='number'else 1
    assert status({**base,field['key']:wrong})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**base,field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('pdu,adu',[(1,8),(5,12),(253,260)])
def test_tcp_mbap_length_is_unit_plus_pdu_and_adu_is_seven_plus_pdu(pdu,adu):
    x={**actual(),'mt_pdu_bytes':pdu,'mt_data_bytes':pdu-1,'payload_bytes':pdu-1,
       'mt_mbap_bytes':7,'mt_length_field':pdu+1,'mt_adu_bytes':adu,'mt_protocol_id':0}
    assert status(x)=='VALID'
    for patch in ({'mt_length_field':pdu},{'mt_adu_bytes':adu+1},{'mt_mbap_bytes':6},{'mt_protocol_id':1},
      {'mt_pdu_bytes':254},{'payload_bytes':pdu}):assert status({**x,**patch})=='INVALID'

def test_tcp_actual_adu_header_octets_match_scalars_and_no_crc():
    # Guide section4.4.1.2 read register5 example: TID1501/protocol0/len6/unitFF/FC3/offset4/qty1.
    x={**actual(),'mt_adu_hex':'150100000006FF0300040001','mt_transaction_id':0x1501,'mt_protocol_id':0,
       'mt_length_field':6,'mt_unit_id':255,'mt_function':3,'mt_request_function':3,'mt_phase':'REQUEST',
       'mt_function_kind':'PUBLIC','mt_quantity':1,'mt_start_address':4,'mt_pdu_bytes':5,'mt_adu_bytes':12}
    assert status(x)=='VALID'
    for patch in ({'mt_transaction_id':0x1502},{'mt_length_field':5},{'mt_unit_id':0},{'mt_function':4},
      {'mt_adu_bytes':14},{'mt_adu_hex':x['mt_adu_hex']+'FFFF'}):assert status({**x,**patch})=='INVALID'

def test_tcp_response_correlates_pending_request_on_same_connection():
    x={**actual(),'mt_phase':'RESPONSE','mt_function_kind':'PUBLIC','mt_request_function':3,'mt_function':3,
       'mt_transaction_id':65535,'mt_request_transaction_id':65535,'mt_unit_id':255,'mt_request_unit_id':255,
       'mt_connection_id':'synthetic-connection1','mt_request_connection_id':'synthetic-connection1','mt_pending_match':True}
    assert status(x)=='VALID'
    for patch in ({'mt_transaction_id':0},{'mt_unit_id':0},{'mt_connection_id':'connection2'},{'mt_pending_match':False}):
        assert status({**x,**patch})=='INVALID'
    x.pop('mt_request_connection_id');assert status(x)=='UNVERIFIED'
    x={**actual(),'mt_destination':'SERIAL_GATEWAY','mt_unit_id':247,'mt_gateway_network_id':'serial-network',
       'mt_gateway_source':'synthetic-qualified-gateway'}
    assert status(x)=='VALID';assert status({**x,'mt_unit_id':255})=='INVALID'
    x.pop('mt_gateway_source');assert status(x)=='UNVERIFIED'

def test_tcp_concurrency_and_socket_resources_depend_actual_implementation():
    x={**actual(),'mt_implementation':'GUIDE_EXAMPLE','mt_client_transaction_cap':16,'mt_outstanding':16,
       'mt_pending_id_unique':True,'mt_connections':3,'mt_connection_cap':4,
       'mt_receive_buffer_bytes':900,'mt_driver_receive_bytes':901,'mt_send_buffer_bytes':900,'mt_driver_send_bytes':901}
    assert status(x)=='VALID'
    for patch in ({'mt_outstanding':17},{'mt_pending_id_unique':False},{'mt_connections':5},
      {'mt_client_transaction_cap':17},{'mt_receive_buffer_bytes':901},{'mt_driver_send_bytes':899}):
        assert status({**x,**patch})=='INVALID'
    x.update(mt_implementation='REGISTERED',mt_client_transaction_cap=128,mt_outstanding=128,
             mt_registered_source='synthetic-device-128-transactions')
    assert status(x)=='VALID'
    x.pop('mt_pending_id_unique');assert status(x)=='UNVERIFIED'

def test_tcp_deliberately_no_response_timeout_or_universal_legacy_stack_defaults():
    x={**actual(),'mt_response_timeout_ms':4200,'mt_response_bound_ms':4199,'mt_timer_source':'synthetic-timer'}
    assert status(x)=='VALID'
    for bound in (4200,4200.001):assert status({**x,'mt_response_bound_ms':bound})=='INVALID'
    x.pop('mt_response_bound_ms');assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('fc',[7,8,11,12,17])
def test_tcp_native_public_functions_exclude_serial_only_functions(fc):
    assert status({**actual(),'mt_function_kind':'PUBLIC','mt_request_function':fc})=='INVALID'

def test_tcp_security_tls_capabilities_are_conditional_and_do_not_change_mbap():
    x=secure()
    for patch in ({'mt_port':502},{'mt_mutual_auth':False},{'mt_certificate_validated':False},
      {'mt_tls_version':'TLS1_1'},{'mt_credential_kind':'PSK'},{'mt_mfl_extension':False},
      {'mt_mfl_512_supported':False},{'mt_secure_renegotiation':False},{'mt_tls_record_bytes':18433},
      {'mt_tls_fragment_bytes':513},{'mt_rsa_required_suite_supported':False},
      {'mt_cipher':'TLS_RSA_WITH_NULL_SHA256'},{'mt_cipher':'TLS_NULL_WITH_NULL_NULL'}):
        assert status({**x,**patch})=='INVALID'
    x.update(mt_key_kind='ECC',mt_ecc_required_suite_supported=True,mt_ecc_curve_bits=256,
       mt_cipher='TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256')
    assert status(x)=='VALID';assert status({**x,'mt_ecc_curve_bits':255})=='INVALID'
    x=secure();x['mt_encryption_required']=False;x['mt_cipher']='TLS_RSA_WITH_NULL_SHA256';assert status(x)=='VALID'
    x=secure();x.update(mt_tls_version='TLS1_3',mt_cipher='TLS_AES_128_GCM_SHA256')
    for k in ('mt_mfl_extension','mt_mfl_512_supported','mt_secure_renegotiation'):x.pop(k)
    assert status(x)=='VALID'
    x=secure();x.pop('mt_trust_ref');assert status(x)=='UNVERIFIED'
    assert status({**actual(),'mt_mutual_auth':True})=='INVALID'

def test_tcp_security_roles_are_one_utf8_extension_and_vendor_configurable_rules():
    x={**secure(),'mt_authorization_enabled':True,'mt_roles_configurable':True,
       'mt_authorization_source':'synthetic-vendor-role-db','mt_role_oid':'1.3.6.1.4.1.50316.802.1',
       'mt_role_encoding':'ASN1_UTF8STRING','mt_certificate_role':'Prüfer','mt_role_utf8_bytes':7,'mt_role_count':1}
    assert status(x)=='VALID'
    for patch in ({'mt_roles_configurable':False},{'mt_role_count':2},{'mt_role_oid':'1.3.6.1.4.1.50316.802.2'},
                 {'mt_role_utf8_bytes':6},{'mt_role_encoding':'ASCII'}):assert status({**x,**patch})=='INVALID'
    x.update(mt_authorization_denied=True,mt_phase='EXCEPTION',mt_exception_code=1,
       mt_request_transaction_id=7,mt_transaction_id=7,mt_request_unit_id=255,mt_unit_id=255,
       mt_connection_id='conn',mt_request_connection_id='conn',mt_pending_match=True)
    assert status(x)=='VALID';assert status({**x,'mt_exception_code':2})=='INVALID'
    x=secure();x['mt_role_count']=0;assert status(x)=='VALID'
    assert status({**x,'mt_certificate_role':'Operator'})=='INVALID'

def test_tcp_confirmed_sql_values_survive_rejected_serial_and_mbap_edits():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x={**actual(),'mt_port':502,'mt_unit_id':0,'mt_transaction_id':65535,
       'mt_response_timeout_ms':4200,'mt_response_bound_ms':4100,'mt_timer_source':'synthetic-actual-timer'}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'modbus_tcp','technology_parameters':{'modbus_tcp':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['modbus_tcp']['values']['bitrate']=100000000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters


# Shared PDU rules independently exercised through the explicit TCP binding.
@pytest.mark.parametrize('fc,maximum,bytecount',[(1,2000,250),(2,2000,250),(3,125,250),(4,125,250),
 (15,1968,246),(16,123,246)])
def test_tcp_shared_quantity_and_binary_pdu_depend_selected_public_function(fc,maximum,bytecount):
    phase='RESPONSE'if fc<=4 else'REQUEST'
    pdu=bytecount+(2 if fc<=4 else 6)
    x={**actual(),'mt_phase':phase,'mt_function_kind':'PUBLIC','mt_request_function':fc,'mt_function':fc,
      'mt_quantity':maximum,'mt_start_address':65536-maximum,'mt_byte_count':bytecount,'mt_pdu_bytes':pdu}
    assert status(x)=='VALID'
    for patch in ({'mt_quantity':maximum+1},{'mt_start_address':65537-maximum},{'mt_byte_count':bytecount+1},
      {'mt_pdu_bytes':pdu+1}):assert status({**x,**patch})=='INVALID'
    if fc<=2:
        x.update(mt_quantity=9,mt_byte_count=2,mt_pdu_bytes=4,mt_start_address=0)
        assert status(x)=='VALID'


@pytest.mark.parametrize('fc',[1,2,3,4,15,16])
def test_tcp_shared_encoded_pdu_cannot_confirm_missing_function_specific_quantity(fc):
    x={**actual(),'mt_phase':'REQUEST','mt_function_kind':'PUBLIC','mt_request_function':fc,'mt_function':fc,
      'mt_pdu_bytes':5 if fc<=4 else 8,'mt_byte_count':2}
    assert status(x)=='UNVERIFIED'
    x.pop('mt_byte_count');assert status(x)=='UNVERIFIED'


def test_tcp_shared_exception_function_and_user_defined_namespaces_are_not_industry_templates():
    x={**actual(),'mt_phase':'EXCEPTION','mt_function_kind':'PUBLIC','mt_request_function':3,
      'mt_function':131,'mt_exception_code':2,'mt_pdu_bytes':2}
    assert status(x)=='VALID'
    for patch in ({'mt_function':3},{'mt_exception_code':7},{'mt_pdu_bytes':3}):assert status({**x,**patch})=='INVALID'
    x.update(mt_phase='REQUEST',mt_function_kind='USER_DEFINED',mt_request_function=65,mt_function=65,mt_pdu_bytes=2)
    assert status(x)=='UNVERIFIED'
    x['mt_function_source']='synthetic-vendor-FC65';assert status(x)=='VALID'
    assert status({**x,'mt_request_function':73})=='INVALID'


def test_tcp_shared_single_coil_literal_and_readwrite_quantities_use_own_function():
    x={**actual(),'mt_phase':'REQUEST','mt_function_kind':'PUBLIC','mt_request_function':5,'mt_function':5,
      'mt_pdu_bytes':5,'mt_coil_value':65280}
    assert status(x)=='VALID';assert status({**x,'mt_coil_value':1})=='INVALID'
    x.update(mt_request_function=23,mt_function=23,mt_read_quantity=125,mt_write_quantity=121,
      mt_write_byte_count=242,mt_pdu_bytes=252,mt_start_address=65411,mt_write_start_address=65415)
    x.pop('mt_coil_value')
    assert status(x)=='VALID'
    for patch in ({'mt_write_quantity':123},{'mt_write_byte_count':240},{'mt_pdu_bytes':253},
      {'mt_write_start_address':65416}):assert status({**x,**patch})=='INVALID'


@pytest.mark.parametrize('field,value,wrong_fc',[('mt_coil_value',65280,6),('mt_register_value',65535,5),
 ('mt_read_quantity',125,16),('mt_write_quantity',121,3),('mt_write_byte_count',242,15),
 ('mt_write_start_address',0,3),('mt_quantity',125,23),('mt_diagnostic',3,43),('mt_mei_type',14,8)])
def test_tcp_shared_function_specific_fields_cannot_be_reused_by_another_public_function(field,value,wrong_fc):
    x={**actual(),'mt_function_kind':'PUBLIC','mt_request_function':wrong_fc,field:value}
    assert status(x)=='INVALID'

