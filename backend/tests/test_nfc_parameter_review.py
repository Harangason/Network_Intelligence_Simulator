"""NFC role/firmware/RF/host isolation and transaction-boundary regressions."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.nfc import rules as NF

def actual(protocol='NFC_A',operation='READER_WRITER',patch=0x11):
    x={'nf_'+k:'synthetic-actual-'+k for k in NF.REQUIRED}
    divisor={'NFC_A':128,'NFC_B':128,'NFC_F':64,'NFC_V':512,'NFCIP1_ECMA340_2024':128}[protocol]
    rate={128:106000,64:212000,512:26480}[divisor]
    peer=protocol=='NFCIP1_ECMA340_2024'
    x.update(bitrate_bps=rate,nf_implementation='PN7160',nf_protocol=protocol,nf_operation='PEER' if peer else operation,
      nf_mode='PASSIVE',nf_role='INITIATOR' if peer else('READER' if operation=='READER_WRITER'else'CARD'),
      nf_direction='INITIATOR_TO_TARGET' if peer else'READER_TO_CARD',nf_rate_basis='NOMINAL_LABEL',nf_carrier_hz=13560000,
      nf_divisor=divisor,nf_rate_profile='SPECIFIED',nf_fw_rom=0x12,nf_fw_major=0x50,nf_fw_patch=patch,
      nf_model_id=0x61,nf_firmware_hex=f'1250{patch:02x}')
    return x
def status(x):return registry.validate_parameters('nfc',x)['status']
def dep():
    return {**actual('NFCIP1_ECMA340_2024',patch=0x0a),
      'nf_dep_pdu':'INFORMATION','nf_dep_len':5,'nf_dep_body_bytes':2,'nf_dep_lr':0,'nf_dep_body_limit':64,
      'nf_dep_header_bytes':1,'nf_dep_data_bytes':1,'nf_dep_did_present':False,'nf_dep_nad_present':False,
      'nf_dep_more':False,'nf_dep_pni':0,'nf_dep_pfb':0,'nf_dep_cmd1':0xd4,'nf_dep_cmd2':6,
      'nf_transaction_source':'synthetic-current-transaction'}
def nci():
    return {**actual(),'nf_host':'SPI','nf_host_source':'synthetic-ordered-SPI',
      'nf_host_direction':'DH_TO_NFCC','nf_host_clock_bps':7000000,'nf_host_half_duplex':True,
      'nf_host_follower_only':True,'nf_host_extra_octets':1,'nf_host_bytes':7,'nf_spi_direction_octet':0,
      'nf_nci_kind':'DATA','nf_nci_mt':0,'nf_nci_header0':0,'nf_nci_conn_id':0,'nf_nci_pbf':0,'nf_nci_last':True,
      'nf_nci_length':3,'nf_nci_packet_bytes':6,'nf_nci_hex':'000003aabbcc','nf_max_data_payload':255,
      'nf_connection_source':'synthetic-CORE-init-activation','nf_credits':1,'nf_nci_send':True}

def test_nfc_no_foreign_can_ethernet_catalog_rate_or_application_packet_default():
    keys=[v['key']for v in registry.parameter_fields('nfc')]
    assert len(keys)==len(set(keys));assert not set(NF.REMOVED)&set(keys)
    assert registry.profile('nfc')['domain']=='generic_networking'
    assert registry.profile('nfc')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('nfc')['values']=={}
    assert status(actual())=='VALID'
    for patch in({'bitrate_bps':500000},{'bitrate_bps':0},{'mtu_bytes':1500},{'vlan_id':0},{'queue_size':256},
      {'retry_limit':3},{'mq_qos':1},{'local_timing_evidence':{'technology':'I2C'}}):
        assert status({**actual(),**patch})=='INVALID'
    for k in('payload_bytes','nf_host_address','nf_fw_patch','nf_operating_distance_mm','nf_credits','nf_vbatt_v'):
        f=next(v for v in registry.parameter_fields('nfc')if v['key']==k)
        assert 'default'not in f;assert not f.get('conditional_defaults')

@pytest.mark.parametrize('field',registry.parameter_fields('nfc'),ids=lambda f:f['key'])
def test_nfc_every_declared_type_unit_and_own_bound(field):
    bad='not-number'if field['type']=='number'else 1
    assert status({**actual(),field['key']:bad})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('protocol,rate,divisor',[
 ('NFC_A',106000,128),('NFC_B',106000,128),('NFC_F',212000,64),('NFC_V',26480,512)])
def test_nfc_distinct_baselines_and_exact_carrier_divisor_not_hostclock(protocol,rate,divisor):
    x=actual(protocol,patch=0x0a);assert status(x)=='VALID'
    assert status({**x,'bitrate_bps':424000})=='INVALID'
    assert status({**x,'nf_rate_basis':'CARRIER_DIVISOR','bitrate_bps':13560000/divisor})=='VALID'
    assert status({**x,'nf_rate_basis':'CARRIER_DIVISOR'})=='INVALID'
    assert status({**x,'nf_bit_duration_us':divisor/13.56})=='VALID'
    assert status({**x,'nf_bit_duration_us':8/divisor})=='INVALID'
    field=next(v for v in registry.parameter_fields('nfc')if v['key']=='bitrate')
    assert any(v['when']['nf_protocol']==protocol and v['value']==rate for v in field['conditional_defaults'])

@pytest.mark.parametrize('protocol',['NFC_F','NFCIP1_ECMA340_2024'])
def test_nfc_current_2026_firmware_removes_old_um_feature_claims(protocol):
    x=actual(protocol,patch=0x0a);assert status(x)=='VALID'
    for patch in(0x0b,0x0c,0x0d,0x0e,0x10,0x11):assert status({**x,'nf_fw_patch':patch,'nf_firmware_hex':f'1250{patch:02x}'})=='INVALID'
    for patch in({'nf_fw_patch':5,'nf_firmware_hex':'12500a'}, {'nf_fw_major':50}, {'nf_fw_rom':12}, {'nf_model_id':0x71}):
        assert status({**x,**patch})=='INVALID'
    y=actual();y.update(nf_implementation='PN7161',nf_model_id=0x71,nf_reset_ntf_hex='600009020020040471125011')
    assert status(y)=='VALID';assert status({**y,'nf_reset_ntf_hex':'600009020020040461125011'})=='INVALID'
    y.pop('nf_fw_patch');assert status(y)=='UNVERIFIED'

def test_nfc_ecp_requires_actual_pn7161_authorization_and_no_inferred_certificate():
    assert status({**actual(),'nf_ecp':True,'nf_ecp_authorization_source':'synthetic'})=='INVALID'
    x={**actual(),'nf_implementation':'PN7161','nf_model_id':0x71,'nf_ecp':True}
    assert status(x)=='UNVERIFIED';x['nf_ecp_authorization_source']='synthetic-existing-authorization';assert status(x)=='VALID'

def test_nfc_reader_848_does_not_become_card_or_peer_848_and_extended_ecma_needs_own_phy():
    x={**actual(),'nf_divisor':16,'bitrate_bps':848000};assert status(x)=='VALID'
    x.update(nf_operation='CARD_EMULATION',nf_role='CARD');assert status(x)=='INVALID'
    x={**dep(),'nf_divisor':16,'bitrate_bps':848000};assert status(x)=='INVALID'
    x.update(nf_implementation='REGISTERED',nf_registered_source='synthetic-qualified-active-extendedPHY',nf_rate_profile='EXTENDED_REGISTERED',nf_mode='ACTIVE')
    assert status(x)=='VALID';x.pop('nf_registered_source');assert status(x)=='UNVERIFIED'

def test_nfc_direction_specific_modulation_coding_and_separate_nfc_v():
    for protocol,tx,rx in [('NFC_A','MODIFIED_MILLER','MANCHESTER'),('NFC_B','NRZ','BPSK'),('NFC_F','MANCHESTER','MANCHESTER'),('NFC_V','PPM_1_OF_4','MANCHESTER')]:
        x={**actual(protocol,patch=0x0a),'nf_coding':tx};assert status(x)=='VALID'
        x.update(nf_direction='CARD_TO_READER',nf_coding=rx);assert status(x)=='VALID'
        assert status({**x,'nf_coding':'REGISTERED'})=='INVALID'
    x={**actual('NFC_V'),'nf_operation':'CARD_EMULATION','nf_role':'CARD'};assert status(x)=='INVALID'
    assert status({**actual(),'nf_role':'INITIATOR'})=='INVALID'

def test_nfc_host_spi_packet_mapping_and_clock_not_rf_capacity():
    x=nci();assert status(x)=='VALID'
    for patch in({'nf_host_clock_bps':7000001},{'bitrate_bps':7000000},{'nf_host_half_duplex':False},
      {'nf_host_follower_only':False},{'nf_spi_direction_octet':128},{'nf_host_extra_octets':0},{'nf_host_bytes':6}):
        assert status({**x,**patch})=='INVALID'
    x.update(nf_host_direction='NFCC_TO_DH',nf_spi_direction_octet=255);assert status(x)=='VALID'
    assert status({**x,'nf_spi_direction_octet':0})=='INVALID'

@pytest.mark.parametrize('mode,limit',[('STANDARD',100000),('FAST',400000),('HIGH_SPEED',3400000)])
def test_nfc_i2c_sevenbit_actual_address_straps_not_rf_rate(mode,limit):
    x={**actual(),'nf_host':'I2C','nf_host_source':'synthetic-ordered-I2C',
      'nf_host_i2c_mode':mode,'nf_host_clock_bps':limit,'nf_host_address_bits':7,
      'nf_host_address':0x2b,'nf_host_write_address':0x56,'nf_host_read_address':0x57}
    assert status(x)=='VALID'
    for patch in({'nf_host_clock_bps':limit+1},{'nf_host_address_bits':10},{'nf_host_address':0x2c},
      {'nf_host_address':0x28},{'nf_host_write_address':0x2b},{'nf_host_read_address':0x56},{'nf_host_i2c_mode':'FAST_PLUS'}):
        assert status({**x,**patch})=='INVALID'

def test_nfc_nci_packet_length_empty_packet_segmentation_and_zero_credit_wait():
    x=nci();assert status(x)=='VALID'
    for patch in({'nf_nci_packet_bytes':5},{'nf_nci_mt':7},{'nf_nci_length':256},{'nf_nci_hex':'000002aabbcc'},
      {'nf_nci_pbf':1},{'nf_max_data_payload':2},{'nf_mapping_mtu':5},{'nf_credits':2},{'nf_credits':0}):
        assert status({**x,**patch})=='INVALID'
    x.update(nf_credits=0,nf_nci_send=False);assert status(x)=='VALID'
    x.update(nf_nci_length=0,nf_nci_packet_bytes=3,nf_host_bytes=4,nf_nci_hex='000000');assert status(x)=='VALID'
    x.update(nf_nci_pbf=1,nf_nci_header0=16,nf_nci_hex='100000',nf_nci_last=False);assert status(x)=='VALID'
    x.update(nf_nci_length=255,nf_nci_packet_bytes=258,nf_host_bytes=259,nf_nci_hex='1000ff'+'00'*255);assert status(x)=='VALID'
    x['nf_dynamic_connections']=2;assert status(x)=='INVALID'

def test_nfc_controller_rf_states_do_not_sum_simultaneous_static_and_dynamic_paths():
    for logical,state in [('STATIC_RF','NON_IDLE'),('DYNAMIC_NDEF','IDLE'),('DYNAMIC_LOOPBACK','IDLE')]:
        x={**actual(),'nf_logical_kind':logical,'nf_rf_state':state};assert status(x)=='VALID'
        assert status({**x,'nf_rf_state':'NON_IDLE'if state=='IDLE'else'IDLE'})=='INVALID'

@pytest.mark.parametrize('kind,mt,direction',[('COMMAND',1,'DH_TO_NFCC'),('RESPONSE',2,'NFCC_TO_DH'),('NOTIFICATION',3,'NFCC_TO_DH')])
def test_nfc_control_packet_header_opcode_and_direction_are_not_data_fields(kind,mt,direction):
    x={**actual(),'nf_nci_kind':kind,'nf_nci_mt':mt,'nf_nci_pbf':0,'nf_nci_header0':32*mt,
      'nf_nci_gid':0,'nf_nci_oid':1,'nf_nci_length':0,'nf_nci_packet_bytes':3,
      'nf_nci_hex':f'{32*mt:02x}0100','nf_host_direction':direction,'nf_max_control_payload':32}
    assert status(x)=='VALID'
    for patch in({'nf_nci_header0':0},{'nf_nci_hex':f'{32*mt:02x}c100'},
      {'nf_host_direction':'NFCC_TO_DH'if direction=='DH_TO_NFCC'else'DH_TO_NFCC'}):assert status({**x,**patch})=='INVALID'

def test_nfc_missing_actual_required_inputs_cannot_turn_proposal_into_valid_capacity():
    for k in NF.REQUIRED:
        x=actual();x.pop('nf_'+k);assert status(x)!='VALID'
    assert status({'bitrate':106000})=='UNVERIFIED'
    x=actual();x['bitrate']=500000;assert status(x)=='INVALID'

@pytest.mark.parametrize('lr,limit',list(enumerate((64,128,192,252))))
def test_nfc_dep_len_body_and_negotiated_lr_distinct_application_and_nci(lr,limit):
    x={**dep(),'nf_dep_lr':lr,'nf_dep_body_limit':limit,'nf_dep_body_bytes':limit,'nf_dep_data_bytes':limit-1,'nf_dep_len':limit+3}
    assert status(x)=='VALID'
    for patch in({'nf_dep_len':limit+2},{'nf_dep_body_limit':255},{'nf_dep_body_bytes':limit+1},
      {'nf_dep_data_bytes':limit},{'nf_dep_header_bytes':2}):assert status({**x,**patch})=='INVALID'
    assert status({**x,'payload_bytes':6000})=='VALID'

def test_nfc_dep_optional_addresses_pfb_ack_and_supervisory_header():
    x={**dep(),'nf_dep_did_present':True,'nf_dep_nad_present':True,'nf_dep_did':14,'nf_dep_nad':255,
      'nf_dep_header_bytes':3,'nf_dep_body_bytes':4,'nf_dep_len':7,'nf_dep_more':True,'nf_dep_pni':3,'nf_dep_pfb':31}
    assert status(x)=='VALID'
    for patch in({'nf_dep_pfb':30},{'nf_dep_did':15},{'nf_dep_pni':4},{'nf_dep_cmd1':0xd5},{'nf_dep_cmd2':7}):
        assert status({**x,**patch})=='INVALID'
    for pdu,pfb,data in [('ACK',64,0),('NACK',80,0),('ATTENTION',128,0),('TIMEOUT_EXTENSION',144,1)]:
        x={**dep(),'nf_dep_pdu':pdu,'nf_dep_pfb':pfb,'nf_dep_data_bytes':data,'nf_dep_body_bytes':1+data,'nf_dep_len':4+data}
        if pdu=='TIMEOUT_EXTENSION':x['nf_rtox']=59
        assert status(x)=='VALID';assert status({**x,'nf_dep_data_bytes':data+1})=='INVALID'

@pytest.mark.parametrize('wt',[0,1,7,14])
def test_nfc_wait_exponent_exact_edges_extension_saturation_and_reserved(wt):
    wait=4096/13.56*2**wt;maximum=4096/13.56*16384
    x={**dep(),'nf_wt':wt,'nf_response_wait_us':wait,'nf_rtox':59,'nf_extended_wait_us':min(wait*59,maximum)}
    assert status(x)=='VALID'
    for patch in({'nf_wt':15},{'nf_rtox':0},{'nf_rtox':60},{'nf_extended_wait_us':wait*60},
      {'nf_response_wait_us':round(wait)}):assert status({**x,**patch})=='INVALID'

def test_nfc_initial_rfca_has_strict_guard_not_zero_default_and_later_random_is_zero():
    x={**dep(),'nf_mode':'ACTIVE','nf_initial_delay_us':4096/13.56+1,'nf_rf_wait_us':512/13.56,
      'nf_initial_guard_us':5001,'nf_active_delay_us':768/13.56,'nf_active_guard_us':1024/13.56+1,'nf_rf_random_n':3}
    assert status(x)=='VALID'
    for patch in({'nf_initial_delay_us':4096/13.56},{'nf_initial_guard_us':5000},
      {'nf_active_delay_us':767/13.56},{'nf_active_guard_us':1024/13.56},{'nf_later_exchange':True},
      {'nf_transaction_uninterrupted':False},{'nf_psl_during_data':True},{'nf_mode_changed':True}):assert status({**x,**patch})=='INVALID'

def test_nfc_role_supply_disjoint_io_rail_and_actual_field_qualification():
    x={**actual(operation='CARD_EMULATION'),'nf_vbatt_v':2.5,'nf_vddpad_v':1.8,'nf_tx_supply_v':2.7,'nf_temperature_c':-30}
    assert status(x)=='VALID';assert status({**x,'nf_vddpad_v':3.3})=='VALID'
    for patch in({'nf_vddpad_v':2.4},{'nf_vbatt_v':2.49},{'nf_temperature_c':-40},{'nf_tx_supply_v':5.26}):assert status({**x,**patch})=='INVALID'
    assert status({**actual(),'nf_vbatt_v':2.5})=='INVALID'
    x={**dep(),'nf_field_a_m':3};assert status(x)=='UNVERIFIED'
    x['nf_field_qualification_source']='synthetic-qualified-operating-volume';assert status(x)=='VALID'
    x['nf_mode']='ACTIVE';x['nf_field_a_m']=8;assert status(x)=='INVALID'

def test_nfc_confirmed_custom_application_distance_host_and_firmware_survive_rejected_foreign_rate():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x={**nci(),'payload_bytes':6000,'nf_operating_distance_mm':12.5}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'nfc','technology_parameters':{'nfc':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['nfc']['values']['bitrate_bps']=500000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
