"""MOST native clocks, actual INIC resources and host versus carrier separation."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.most import rules as MO

def actual(device='OS81050'):
    x={'mo_'+k:'synthetic-actual-'+k for k in MO.REQUIRED}
    generation,size,fs,phy={'OS81050':('MOST25',64,44100,'OPTICAL_POF'),
        'OS81092':('MOST50',128,48000,'UTP_EPHY'),
        'OS81118':('MOST150',384,48000,'OPTICAL_POF')}[device]
    x.update(mo_device=device,mo_generation=generation,mo_frame_bytes=size,mo_frame_bits=size*8,
       mo_target_fs_hz=fs,bitrate=size*8*fs,mo_phy=phy,mo_topology='RING',mo_clock_role='TIMING_MASTER',
       mo_channel='CONTROL',mo_variant='BF' if device=='OS81118' else 'REGISTERED',
       mo_registered_source='synthetic-actual-registration')
    return x

def status(x):return registry.validate_parameters('most',x)['status']

def test_most_has_no_foreign_defaults_or_universal_150m_payload_limit():
    fields=registry.parameter_fields('most');keys=[f['key'] for f in fields]
    assert len(keys)==len(set(keys))
    assert not set(MO.REMOVED)&set(keys)
    assert registry.parameter_defaults_review('most')['values']=={}
    assert registry.profile('most')['domain']=='generic_networking'
    assert registry.profile('most')['capacity_evidence']['status']=='MODEL_MISSING'
    assert status(actual())=='VALID'
    for patch in ({'bitrate':150000000},{'payload_bytes':1500,'mo_application_bytes':1501},
        {'queue_size':1024},{'mtu_bytes':1500},{'mr_crc_bits':16},{'local_timing_evidence':{'technology':'CAN'}}):
        assert status({**actual(),**patch})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('most'),ids=lambda f:f['key'])
def test_most_every_declared_type_and_own_bounds(field):
    wrong='not-number' if field['type']=='number' else 1
    assert status({**actual(),field['key']:wrong})=='INVALID'
    for bound,offset in [('min',-1),('max',1)]:
        if field.get(bound) is not None:
            assert status({**actual(),field['key']:field[bound]+offset})=='INVALID'

@pytest.mark.parametrize('device,fs,rate',[('OS81050',44100,22579200),('OS81050',48000,24576000),
    ('OS81092',48000,49152000),('OS81118',48000,147456000)])
def test_most_exact_generation_clock_is_not_rounded_speed_grade_or_host_clock(device,fs,rate):
    x=actual(device);x.update(mo_target_fs_hz=fs,bitrate=rate,mo_frame_period_us=1000000/fs)
    assert status(x)=='VALID'
    for patch in ({'bitrate':rate+1},{'mo_frame_bits':x['mo_frame_bits']+1},{'mo_target_fs_hz':47999},
        {'mo_generation':'MOST150' if device!='OS81118' else 'MOST25'}):
        assert status({**x,**patch})=='INVALID'

@pytest.mark.parametrize('device,lo,hi,voltage',[('OS81050',44000,48100,2.5),('OS81092',47900,48100,1.8)])
def test_most_device_operating_limits_not_absolute_maximum_or_other_generation(device,lo,hi,voltage):
    for fs in (lo,hi):
        x={**actual(device),'mo_observed_fs_hz':fs,'mo_core_v':voltage,'mo_peripheral_v':3.3,'mo_temperature_c':125}
        assert status(x)=='VALID'
        for patch in ({'mo_observed_fs_hz':lo-1},{'mo_observed_fs_hz':hi+1},
            {'mo_core_v':1.8 if voltage==2.5 else 2.5},{'mo_temperature_c':150}):
            assert status({**x,**patch})=='INVALID'

def test_most_frame_allocation_and_multiframe_message_are_distinct():
    x={**actual('OS81092'),'mo_channel':'ASYNC_PACKET','mo_frame_overhead_bytes':8,
       'mo_control_allocation_bytes':8,'mo_stream_allocation_bytes':64,'mo_packet_allocation_bytes':48,
       'mo_application_bytes':1014,'payload_bytes':1014,'mo_encoded_message_bytes':1020,'mo_fragments':22,
       'mo_allocation_bps':48*8*48000,'mo_host_port':'MEDIALB3','mo_host_source':'synthetic-MediaLB',
       'mo_message_kind':'MDP'}
    assert status(x)=='VALID'
    for patch in ({'mo_frame_overhead_bytes':9},{'mo_fragments':21},{'mo_allocation_bps':49152000},
        {'mo_application_bytes':1015,'payload_bytes':1015},{'mo_host_port':'I2C'}):
        assert status({**x,**patch})=='INVALID'
    x.pop('mo_packet_allocation_bytes');assert status(x)=='UNVERIFIED'

def test_most_streaming_needs_clock_lock_actual_mapping_and_three_frame_settle():
    x={**actual('OS81092'),'mo_channel':'SYNC_STREAM','mo_mapping_source':'synthetic-source-sink-map',
       'mo_stream_sources':1,'mo_stream_sinks':8,'mo_network_locked':True,'mo_stream_ready':True,
       'mo_lock_sync_frames':3,'mo_stream_start_delay_us':62.5,'mo_oscillator_hz':18432000}
    assert status(x)=='VALID'
    for patch in ({'mo_network_locked':False},{'mo_lock_sync_frames':2},{'mo_stream_start_delay_us':62},
        {'mo_stream_sources':2},{'mo_oscillator_hz':12288000}):assert status({**x,**patch})=='INVALID'
    x.pop('mo_mapping_source');assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('device',['OS81050','OS81092'])
def test_most25_and_50_exclude_150_only_channels_and_host_ports(device):
    for patch in ({'mo_channel':'ISOCHRONOUS'},{'mo_channel':'EMBEDDED_ETHERNET'},
        {'mo_host_port':'USB','mo_host_source':'synthetic-usb'},{'mo_phy':'COAX_CPHY'}):
        assert status({**actual(device),**patch})=='INVALID'

def test_most_host_clock_is_separately_qualified_and_port_message_has_own_length():
    x={**actual('OS81092'),'mo_host_port':'MEDIALB3','mo_host_source':'synthetic-host',
       'mo_host_clock_multiplier':1024,'mo_host_clock_hz':49152000,
       'mo_pml':1100,'mo_pmhl':5,'mo_port_body_bytes':1094,'mo_host_message_bytes':1102}
    assert status(x)=='VALID'
    for patch in ({'mo_host_clock_hz':49152001},{'mo_host_port':'MEDIALB5'},
        {'mo_host_message_bytes':1100},{'mo_port_body_bytes':1095}):assert status({**x,**patch})=='INVALID'
    x.pop('mo_host_source');assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('device',['OS81050','OS81092'])
def test_most_stream_format_sample_packing_and_socket_clock_depend_actual_port(device):
    x={**actual(device),'mo_host_port':'STREAMING','mo_host_source':'synthetic-port',
       'mo_host_clock_multiplier':128,'mo_host_clock_hz':128*actual(device)['mo_target_fs_hz'],
       'mo_stream_format':'LEFT_JUSTIFIED','mo_sample_bits':24,'mo_stream_channels':2,'mo_stream_socket_bytes':6}
    assert status(x)=='VALID'
    for patch in ({'mo_sample_bits':32},{'mo_stream_channels':1},{'mo_stream_socket_bytes':8},
        {'mo_host_clock_multiplier':256}):assert status({**x,**patch})=='INVALID'

def test_most_selected_phy_variant_and_device_revision_have_no_ethernet_or_can_fallback():
    x={**actual('OS81092'),'mo_cable_impedance_ohm':130,'mo_host_i2c_master':True,'mo_revision_c1d_or_later':True}
    assert status(x)=='VALID'
    for patch in ({'mo_cable_impedance_ohm':99},{'mo_cable_impedance_ohm':141},{'mo_revision_c1d_or_later':False}):
        assert status({**x,**patch})=='INVALID'
    assert status({**actual(),'mo_host_i2c_master':True})=='INVALID'
    x={**actual('OS81118'),'mo_variant':'AF','mo_phy':'COAX_CPHY','mo_topology':'DAISY_CHAIN',
        'mo_phy_mode':'FULL_DUPLEX','mo_companion_source':'synthetic-OS81119-companion'}
    assert status(x)=='VALID'
    for patch in ({'mo_variant':'BF'},{'mo_phy':'OPTICAL_POF'},{'mo_phy_mode':'DUAL_SIMPLEX'}):
        assert status({**x,**patch})=='INVALID'
    x.pop('mo_companion_source');assert status(x)=='UNVERIFIED'

def test_most_confirmed_clock_and_device_values_survive_invalid_foreign_edits():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x={**actual('OS81092'),'mo_node_address':0x1234,'mo_cable_impedance_ohm':120}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'most','technology_parameters':{'most':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['most']['values']['bitrate']=150000000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
