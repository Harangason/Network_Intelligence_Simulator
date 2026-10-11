"""MMS negotiated caps, directionality, wire layers and confirmed SQL values."""
from copy import deepcopy
import math
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mms as MM

def actual(profile='LIBIEC61850_1_6',phase='DATA'):
    x={'mm_'+k:'synthetic-actual-'+k for k in MM.REQUIRED}
    x.update(mm_profile=profile,mm_role='CLIENT',mm_binding='RFC1006_TCP',mm_phase=phase,mm_encoding='ASN1_BER',
      mm_build='CUSTOM',mm_build_source='synthetic-actual-build',mm_version=1,mm_pdu_offer_bytes=64000,
      mm_peer_pdu_limit_bytes=60000,mm_negotiated_pdu_bytes=60000,mm_compiled_pdu_bytes=65000,
      mm_calling_offer=4,mm_called_offer=3,mm_calling_negotiated=4,mm_called_negotiated=3,
      mm_compiled_calling=5,mm_compiled_called=5,mm_nesting_negotiated=10,
      mm_negotiation_source='synthetic-handshake')
    if profile=='REGISTERED':x['mm_registered_source']='synthetic-registered-implementation'
    return x

def status(x):return registry.validate_parameters('mms',x)['status']

def test_mms_industry_neutral_and_no_can_or_ethernet_capacity_fallback():
    fields={f['key']:f for f in registry.parameter_fields('mms')}
    assert not set(MM.REMOVED)&set(fields)
    assert registry.profile('mms')['rate_model']['fields']==[]
    assert registry.parameter_defaults_review('mms')['values']=={}
    assert 'default'not in fields['payload_bytes']
    assert registry.profile('mms')['capacity_evidence']['status']=='MODEL_MISSING'
    assert status(actual())=='VALID'
    for patch in ({'bitrate':500000},{'bitrate_bps':100000000},{'queue_size':1024},{'retry_limit':3},
      {'local_timing_evidence':{'bitrate_bps':100000,'source':'I2C','confirmed':True}},
      {'iec61850_mapping':'IEC61850_8_1'}):assert status({**actual(),**patch})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('mms'),ids=lambda f:f['key'])
def test_mms_every_declared_type_and_own_bounds(field):
    wrong='not-number'if field['type']=='number'else 1
    assert status({**actual(),field['key']:wrong})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

def test_mms_factory_proposals_do_not_create_installed_identity_negotiation_or_tls_confirmation():
    fields={f['key']:f for f in registry.parameter_fields('mms')}
    for key,value in MM.FACTORY.items():
        assert fields['mm_'+key]['conditional_defaults'][0]['value']==value
    assert fields['mm_request_timeout_ms']['conditional_defaults'][0]['value']==5000
    assert fields['mm_connect_timeout_ms']['conditional_defaults'][0]['value']==10000
    assert fields['mm_services_bitmap']['conditional_defaults'][0]['value']=='EE1C00000408000079EF18'
    assert fields['mm_cbb_offer']['conditional_defaults'][0]['value']==0xF100
    for key in ('local_ap_title','remote_ap_title','local_ae_qualifier','remote_ae_qualifier',
      'negotiated_pdu_bytes','nesting_negotiated','tls_compiled','tls_authenticated','credential_ref'):
        assert 'conditional_defaults'not in fields['mm_'+key]
    x={**actual(),'mm_build':'FACTORY','mm_compiled_pdu_bytes':65000}
    assert status(x)=='VALID'
    assert status({**x,'mm_compiled_pdu_bytes':64000})=='INVALID'
    assert status({**actual(),'mm_compiled_pdu_bytes':64000})=='VALID'

@pytest.mark.parametrize('patch',[
 {'mm_pdu_offer_bytes':127},{'mm_peer_pdu_limit_bytes':127},
 {'mm_negotiated_pdu_bytes':60001},{'mm_compiled_pdu_bytes':59999},
 {'mm_calling_negotiated':5},{'mm_called_negotiated':4},
 {'mm_compiled_calling':3},{'mm_compiled_called':2},
 {'mm_nesting_negotiated':128},{'mm_version':2}])
def test_mms_local_peer_pdu_and_two_direction_windows_are_independent(patch):
    assert status({**actual(),**patch})=='INVALID'

@pytest.mark.parametrize('key',['negotiation_source','compiled_pdu_bytes','compiled_calling','compiled_called',
 'pdu_offer_bytes','peer_pdu_limit_bytes','calling_offer','called_offer','nesting_negotiated'])
def test_mms_data_requires_actual_handshake_and_local_build_caps(key):
    x=actual();x.pop('mm_'+key)
    assert status(x)=='UNVERIFIED'

def test_mms_native_asn_integer_widths_are_not_can_uint16_or_negative_sentinels():
    x=actual('REGISTERED');x.update(mm_pdu_offer_bytes=2147483647,mm_peer_pdu_limit_bytes=2147483647,
      mm_negotiated_pdu_bytes=2147483647,mm_calling_offer=32767,mm_called_offer=32767,
      mm_calling_negotiated=32767,mm_called_negotiated=32767,mm_nesting_negotiated=127,mm_version=32767)
    assert status(x)=='VALID'
    for key in ('pdu_offer_bytes','calling_offer','called_offer','nesting_negotiated'):
        assert status({**x,'mm_'+key:-1})=='INVALID'
    x.update(mm_invoke_id=4294967295,mm_invoke_source='synthetic-unique-outstanding-calls')
    assert status(x)=='VALID'
    assert status({**x,'mm_invoke_id':4294967296})=='INVALID'
    assert status({**x,'mm_invoke_id':True})=='INVALID'

@pytest.mark.parametrize('tpdu,tsdu',[(128,124),(128,125),(128,126),(1024,1021),(8192,65020)])
def test_mms_cotp_tpdu_fragmentation_counts_full_tsdu_and_not_tcp_segments(tpdu,tsdu):
    pdu=tsdu-20;fragments=math.ceil(tsdu/(tpdu-3))
    x={**actual(),'mm_tpdu_exponent':int(math.log2(tpdu)),'mm_tpdu_bytes':tpdu,'mm_compiled_tpdu_bytes':8192,
      'mm_dt_header_bytes':3,'mm_tpkt_header_bytes':4,'mm_tpkt_version':3,'mm_fragment_payload_bytes':tpdu-3,
      'mm_tsdu_bytes':tsdu,'mm_pdu_bytes':pdu,'mm_session_bytes':4,'mm_presentation_bytes':16,
      'mm_acse_bytes':0,'mm_fragments':fragments,'mm_tpkt_stream_bytes':tsdu+7*fragments,
      'mm_fragment_source':'synthetic-normal-DT-reassembly','mm_negotiated_pdu_bytes':65000,'mm_peer_pdu_limit_bytes':65000,
      'mm_pdu_offer_bytes':65000}
    assert status(x)=='VALID'
    for patch in ({'mm_fragments':fragments+1},{'mm_tpkt_stream_bytes':tsdu+4*fragments},
      {'mm_fragment_payload_bytes':tpdu-4},{'mm_tsdu_bytes':tsdu-1},{'mm_dt_header_bytes':7},
      {'mm_session_bytes':8},{'mm_acse_bytes':4},{'mm_tpkt_version':1},{'mm_tpkt_header_bytes':0}):
        assert status({**x,**patch})=='INVALID'
    assert status({**x,'mm_tpdu_bytes':tpdu+1})=='INVALID'
    assert status({**x,'mm_compiled_tpdu_bytes':128})=='INVALID'
    y=deepcopy(x);y.pop('mm_tpdu_exponent');assert status(y)=='UNVERIFIED'

def test_mms_variable_ber_overhead_and_application_bytes_need_complete_pdu():
    x={**actual(),'payload_bytes':58000,'mm_mms_overhead_bytes':100,'mm_pdu_bytes':58100}
    assert status(x)=='VALID'
    for patch in ({'payload_bytes':58101},{'mm_pdu_bytes':58000},{'mm_pdu_bytes':60001}):assert status({**x,**patch})=='INVALID'

@pytest.mark.parametrize('level,maximum',[('t',4),('s',16),('p',16)])
def test_mms_local_remote_selectors_use_octet_lengths_not_identical_device_defaults(level,maximum):
    x={**actual(),'mm_local_'+level+'selector':'AB'*maximum,'mm_remote_'+level+'selector':'CD',
      'mm_identity_source':'synthetic-installed-selectors'}
    assert status(x)=='VALID'
    for value in ('A','GG','AB'*(maximum+1)):
        assert status({**x,'mm_local_'+level+'selector':value})=='INVALID'
    x.pop('mm_identity_source');assert status(x)=='UNVERIFIED'

def test_mms_cbb_and_service_bitmap_have_different_width_and_padding():
    x={**actual(),'mm_cbb_offer':0xF100,'mm_cbb_negotiated':0x0100,'mm_services_bitmap':'EE1C00000408000079EF18'}
    assert status(x)=='VALID'
    for patch in ({'mm_cbb_offer':0xF101},{'mm_cbb_negotiated':0x0101},
      {'mm_services_bitmap':'EE1C00000408000079EF19'},{'mm_services_bitmap':'EE1C00000408000079EF1'},
      {'mm_services_bitmap':'EE1C00000408000079EF1800'}):assert status({**x,**patch})=='INVALID'
    assert status({**actual(),'mm_acse_context_id':1,'mm_mms_context_id':3})=='VALID'
    assert status({**actual(),'mm_acse_context_id':3,'mm_mms_context_id':3})=='INVALID'

@pytest.mark.parametrize('side',['local','remote'])
def test_mms_ap_title_oid_grammar_and_actual_ber_limit_do_not_use_text_length(side):
    x={**actual(),'mm_'+side+'_ap_title':'1.1.1.999','mm_'+side+'_ap_encoded_bytes':5,
      'mm_identity_source':'synthetic-actual-OID-and-BER'}
    assert status(x)=='VALID'
    for oid in ('3.1.2','1.40.1','-1.1.1','1.01.2','1..2','1.1.x'):
        assert status({**x,'mm_'+side+'_ap_title':oid})=='INVALID'
    assert status({**x,'mm_'+side+'_ap_encoded_bytes':11})=='INVALID'
    x.pop('mm_'+side+'_ap_encoded_bytes');assert status(x)=='UNVERIFIED'

def test_mms_tls_port_is_not_build_credentials_trust_or_authenticator_evidence():
    x={**actual(),'mm_binding':'RFC1006_TLS','mm_peer_port':3782}
    assert status(x)=='UNVERIFIED'
    x.update(mm_tls_compiled=True,mm_tls_authenticated=True,mm_credential_ref='synthetic-reference-only',
      mm_security_source='synthetic-trust-and-TLS-build')
    assert status(x)=='VALID'
    for patch in ({'mm_tls_compiled':False},{'mm_tls_authenticated':False}):assert status({**x,**patch})=='INVALID'
    x.update(mm_auth='TLS_CERTIFICATE',mm_authenticator=True)
    assert status(x)=='VALID'
    assert status({**x,'mm_authenticator':False})=='INVALID'
    assert status({**x,'mm_auth':'ACSE_CERTIFICATE_REGISTERED'})=='INVALID'
    assert status({**x,'mm_binding':'RFC1006_TCP'})=='INVALID'

def test_mms_factory_compilation_does_not_grant_rename_service_or_actual_dataset_resources():
    x={**actual(),'mm_service':'RENAME_FILE','mm_service_source':'synthetic-runtime','mm_service_supported':True,
      'mm_registered_source':'synthetic-modified-rename-codec'}
    assert status(x)=='VALID'
    assert status({**x,'mm_build':'FACTORY'})=='INVALID'
    x.update(mm_service='FILE',mm_open_files=7)
    assert status(x)=='UNVERIFIED'
    x['mm_resource_source']='synthetic-modified-resource-limit';assert status(x)=='VALID'

def test_mms_confirmed_nondefault_negotiation_and_pdu_survive_rejected_isolated_sql_edit():
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.project_context import current_project_id
    x={**actual(),'mm_peer_port':1102,'payload_bytes':58000,'mm_mms_overhead_bytes':100,'mm_pdu_bytes':58100,
      'mm_calling_negotiated':2,'mm_request_timeout_ms':7200}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'mms','technology_parameters':{'mms':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['mms']['values']['mm_pdu_bytes']=58000
    bad['technology_parameters']['mms']['provenance']['mm_pdu_bytes']['value']=58000
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
