"""Independent per-technology checks for the approved complete parameter audit."""
from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies.catalog import PARAMETER_UI_ALIASES, DDS_POLICY_ENTITIES
from backend.engineering.agent_tools.wizard_generation import _parameter_defaults
from backend.engineering.capacity.service import parameters_for_protocol
from backend.engineering.workflow.service import WorkflowStatusService
from backend.communication.technologies.core.registry import TechnologyRegistry
import pytest

from backend.communication.technologies import mipi_csi2 as CS


def csi_actual(device='TI960',direction='TX'):
    x={'cs_'+k:'synthetic-actual-'+k for k in CS.REQUIRED}
    x.update(cs_version='2.0',cs_phy='DPHY_FCM',cs_phy_revision='1.2',cs_device=device,cs_direction=direction,
        cs_clock_mode='CONTINUOUS',cs_lanes=4,cs_lane_bitrate_bps=800000000,cs_cci_mode='I2C_FAST',
        cs_cci_rate_bps=400000,cs_header='BASE_DPHY',cs_buffer_source='synthetic-buffer')
    return x


def csi_long(wc=2400):
    return {**csi_actual(),'cs_packet':'LONG','cs_word_count':wc,'payload_bytes':wc,'cs_header_bytes':4,
        'cs_footer_bytes':2,'cs_packet_bytes':wc+6,'cs_vc':3,'cs_data_type':43,'cs_data_id':235}


def test_csi_has_native_lane_and_control_rates_without_global_two_point_five_g_or_can_defaults():
    f={v['key']:v for v in registry.parameter_fields('mipi_csi2')}
    assert not set(CS.REMOVED)&set(f)
    assert registry.profile('mipi_csi2')['rate_model']['fields']==[]
    assert registry.parameter_defaults_review('mipi_csi2')['values']=={}
    assert 'default' not in f['payload_bytes'] and 'default'not in f['cs_lane_bitrate_bps']
    assert {v['value']for v in f['cs_lane_bitrate_bps']['conditional_defaults']}=={80000000,160000000,320000000,400000000}
    assert all(v['source']and v['source_revision']for v in f['cs_cci_rate_bps']['conditional_defaults'])
    assert registry.validate_parameters('mipi_csi2',csi_actual())['status']=='VALID'
    for patch in ({'bitrate':2500000000},{'bitrate_bps':2500000000},{'retry_limit':3},{'queue_size':1024},
                  {'local_timing_evidence':{'source':'i2c','confirmed':True}},{'arbitration_bitrate_bps':500000}):
        assert registry.validate_parameters('mipi_csi2',{**csi_actual(),**patch})['status']=='INVALID'
    assert registry.profile('mipi_csi2')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('mipi_csi2'),ids=lambda field:'csi2/'+field['key'])
def test_csi_every_declared_field_rejects_foreign_types_and_its_declared_bounds(field):
    wrong='bad-number'if field['type']=='number'else 1
    assert registry.validate_parameters('mipi_csi2',{**csi_actual(),field['key']:wrong})['status']=='INVALID'
    for limit,offset in [('min',-1),('max',1)]:
        if field.get(limit)is not None:
            assert registry.validate_parameters('mipi_csi2',{**csi_actual(),field['key']:field[limit]+offset})['status']=='INVALID'


@pytest.mark.parametrize('wc',[0,1,6,32,2400,65535])
def test_csi_classic_long_wordcount_excludes_header_crc_and_phy_framing(wc):
    x=csi_long(wc)
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_packet_bytes':wc+8},{'cs_header_bytes':6},{'cs_footer_bytes':4},
                  {'payload_bytes':wc+1},{'cs_word_count':65536},{'cs_data_type':15},{'cs_data_id':234},{'cs_vc':4}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    for key in ('cs_word_count','cs_packet','cs_header'):
        assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'


def test_csi_short_has_16bit_information_field_and_no_long_payload_footer():
    x={**csi_actual(),'cs_packet':'SHORT','cs_data_type':0,'cs_vc':2,'cs_data_id':128,
       'cs_short_data':65535,'cs_packet_bytes':4,'cs_header_bytes':4,'cs_footer_bytes':0,'payload_bytes':0}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_word_count':2},{'payload_bytes':2},{'cs_footer_bytes':2},{'cs_packet_bytes':6},
                  {'cs_short_data':65536},{'cs_data_type':16}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'


@pytest.mark.parametrize('packing,fmt,pixels,wc',[('PACKED_RAW10','RAW10',1920,2400),('PACKED_RAW12','RAW12',1080,1620)])
def test_csi_raw_wire_group_packing_is_distinct_from_host16bit_samples(packing,fmt,pixels,wc):
    x={**csi_long(wc),'cs_packing':packing,'cs_format':fmt,'cs_line_pixels':pixels,'cs_packing_remainder':0}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_word_count':pixels*2},{'cs_line_pixels':pixels+1},{'cs_packing_remainder':1},
                  {'cs_dpcm':True},{'cs_mpc':True},{'cs_format':'RAW8'}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!='cs_packing_remainder'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('phy,version,revision,rate,bits,symbols,information',[('CPHY_6WS','2.0','1.2',7000000,16,7,16000000),
    ('CPHY_18WS','4.1','3.0',9000000,32,9,32000000)])
def test_csi_cphy_symbol_coding_is_not_dphy_ddr_or_rounded_two_point_two_eight(phy,version,revision,rate,bits,symbols,information):
    x=csi_actual('REGISTERED');x.pop('cs_lane_bitrate_bps')
    x.update(cs_registered_source='synthetic-registered-cphy',cs_header='REGISTERED',cs_phy=phy,cs_version=version,
        cs_phy_revision=revision,cs_clock_mode='EMBEDDED',cs_clock_lanes=0,cs_symbol_rate_sps=rate,
        cs_coding_bits=bits,cs_coding_symbols=symbols,cs_information_rate_bps=information,
        cs_aggregate_information_bps=information*4,cs_vc=31)
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_clock_hz':rate/2},{'cs_lane_bitrate_bps':information},{'cs_clock_lanes':1},
                  {'cs_information_rate_bps':rate*2.28},{'cs_coding_symbols':symbols+1},{'cs_coding_bits':bits+1}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_version':'1.2'})['status']=='INVALID'
    if phy=='CPHY_18WS':
        assert registry.validate_parameters('mipi_csi2',{**x,'cs_usl':True,'cs_feature_source':'synthetic-usl'})['status']=='INVALID'


def test_csi_dphy_ecm_has_coding_overhead_no_forwarded_clock_and_requires_csi42():
    x=csi_actual('REGISTERED');x.update(cs_registered_source='synthetic-ecm',cs_version='4.2',cs_phy='DPHY_ECM',
        cs_phy_revision='3.6',cs_header='EXTENDED_DPHY',cs_clock_mode='EMBEDDED',cs_clock_lanes=0,cs_lanes=5,
        cs_lane_bitrate_bps=132000000,cs_coding_bits=128,cs_coded_block_bits=132,cs_information_rate_bps=128000000,
        cs_aggregate_information_bps=640000000,cs_vc=15)
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_version':'4.1'},{'cs_phy_revision':'2.1'},{'cs_clock_hz':66000000},
                  {'cs_information_rate_bps':132000000},{'cs_coded_block_bits':128},{'cs_data_id':255},{'cs_vc':16}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    # Later CSI revisions do not share the CSI1.1 four-data-lane limit.
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_lanes':7,'cs_aggregate_information_bps':896000000})['status']=='VALID'


@pytest.mark.parametrize('mode,rate',[('I2C_STANDARD',100000),('I2C_FAST',400000),('I2C_FAST_PLUS',1000000),('I3C_SDR',12500000),('I3C_HDR_DDR',25000000)])
def test_csi_control_clock_has_own_mode_bounds_and_canonical_network(mode,rate):
    x={**csi_actual(),'cs_version':'4.2','cs_cci_mode':mode,'cs_cci_rate_bps':rate}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_cci_rate_bps':rate+1})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!='cs_cci_network_id'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_version':'1.3'})['status']==('VALID'if mode in ('I2C_STANDARD','I2C_FAST')else'INVALID')


@pytest.mark.parametrize('code,reference,rate',[(0,23000000,1472000000),(0,25000000,1600000000),
    (0,26000000,1664000000),(1,25000000,1200000000),(2,25000000,800000000),(3,25000000,400000000)])
def test_csi_ti_selected_pll_reference_and400m_override_are_real_dependencies(code,reference,rate):
    x={**csi_actual(),'cs_pll_code':code,'cs_reference_clock_hz':reference,'cs_lane_bitrate_bps':rate,
       'cs_clock_hz':rate/2,'cs_initial_skew':True,'cs_timing_override':True,
       'cs_timing_override_source':'synthetic-nine-register-writes-selected-port','cs_pll_source':'synthetic-reference-register'}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_lane_bitrate_bps':rate+1},{'cs_clock_hz':rate},{'cs_reference_clock_hz':27000000},{'cs_lanes':5},{'cs_vc':4}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    if code==3:
        assert registry.validate_parameters('mipi_csi2',{**x,'cs_timing_override':False})['status']=='INVALID'
        assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!='cs_timing_override_source'})['status']=='UNVERIFIED'
    if code==0:assert registry.validate_parameters('mipi_csi2',{**x,'cs_initial_skew':False})['status']=='INVALID'


@pytest.mark.parametrize('device,direction,lo,hi,width',[('LATTICE_SOFT','TX',160000000,1500000000,8),
    ('LATTICE_SOFT','RX',80000000,1500000000,8),('LATTICE_HARD','TX',320000000,2500000000,16),
    ('LATTICE_HARD','RX',160000000,2500000000,16),('LATTICE_HARD','RX',160000000,2500000000,8)])
def test_csi_lattice_direction_phy_ppi_clock_and_capabilities_use_current_ip42(device,direction,lo,hi,width):
    x={**csi_actual(device,direction),'cs_lane_bitrate_bps':lo,'cs_phy_width_bits':width,'cs_byte_clock_hz':lo/width,
       'cs_reference_clock_hz':60000000,'cs_controller_bits':64 if width==16 else 32,
       'cs_ppi_source':'synthetic-generated-configuration','cs_ppc':4,'cs_interface':'UVSI',
       'cs_format':'RAW10','cs_host_pixel_bits':16,'cs_pixel_bits':10,'cs_axis_width_bits':64,
       'cs_escape':False,'cs_ulps':False,'cs_bta':False,'cs_interlaced':False}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_lane_bitrate_bps':lo-1},{'cs_lane_bitrate_bps':hi+1},{'cs_lanes':3},
                  {'cs_phy_width_bits':24},{'cs_axis_width_bits':40},{'cs_host_pixel_bits':10},
                  {'cs_interlaced':True},{'cs_escape':True},{'cs_ulps':True},{'cs_bta':True},{'cs_ppc':8}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    y={**x,'cs_lane_bitrate_bps':hi,'cs_byte_clock_hz':hi/width}
    if device=='LATTICE_HARD':y['cs_initial_skew']=True
    assert registry.validate_parameters('mipi_csi2',y)['status']=='VALID'
    assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!='cs_ppi_source'})['status']=='UNVERIFIED'
    if direction=='RX':assert registry.validate_parameters('mipi_csi2',{**x,'cs_controller_bits':32 if width==16 else 64})['status']=='INVALID'
    if device=='LATTICE_HARD':assert registry.validate_parameters('mipi_csi2',{**y,'cs_initial_skew':False})['status']=='INVALID'


@pytest.mark.parametrize('direction,width,wc',[('TX',32,32),('RX',32,6),('RX',64,10)])
def test_csi_vendor_minimum_wordcount_and_mbsibuffer8byte_allowance_do_not_change_wire6(direction,width,wc):
    x={**csi_long(wc),**csi_actual('LATTICE_HARD',direction),'cs_word_count':wc,'cs_controller_bits':width,
       'cs_interface':'MBSI','cs_buffer_bytes':1024,'cs_buffer_payload_bytes':1016,
       'cs_phy_width_bits':16 if width==64 else 8,'cs_ppi_source':'synthetic-generated-configuration'}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_word_count':wc-1,'payload_bytes':wc-1,'cs_packet_bytes':wc+5})['status']=='INVALID'
    if direction=='TX':
        assert registry.validate_parameters('mipi_csi2',{**x,'cs_buffer_payload_bytes':1018})['status']=='INVALID'
        y={**x,'cs_word_count':1017,'payload_bytes':1017,'cs_packet_bytes':1023}
        assert registry.validate_parameters('mipi_csi2',y)['status']=='INVALID'
    if width==64:assert registry.validate_parameters('mipi_csi2',{**x,'cs_lanes':2})['status']=='INVALID'


def test_csi_ti_instantaneous_ui_eot_prepare_zero_and_electrical_limits_are_not_ethernet():
    x={**csi_actual(),'cs_measurement_source':'synthetic-fixture','cs_ui_ns':1.25,'cs_ui_variation_percent':10,
       'cs_clk_post_ns':125,'cs_clk_pre_ns':10,'cs_hs_prepare_ns':45,'cs_hs_zero_ns':112.5,
       'cs_hs_settle_ns':92.5,'cs_eot_ns':120,'cs_hs_trail_ns':65,'cs_data_term_ns':40,
       'cs_hs_common_mv':250,'cs_hs_diff_mv':140,'cs_single_output_ohm':62.5,'cs_lp_high_v':1.1,
       'cs_sdd_h_db':-9,'cs_max_capability_bps':1500000000,'cs_tx_rise_ps':375}
    assert registry.validate_parameters('mipi_csi2',x)['status']=='VALID'
    for patch in ({'cs_clk_post_ns':124.999},{'cs_hs_prepare_ns':44.999},{'cs_hs_zero_ns':112.4999},
                  {'cs_eot_ns':120.001},{'cs_data_term_ns':40.001},{'cs_hs_common_mv':250.1},
                  {'cs_hs_diff_mv':139.99},{'cs_lp_high_v':.95},{'cs_sdd_h_db':-8.99},{'cs_tx_rise_ps':375.01}):
        assert registry.validate_parameters('mipi_csi2',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{k:v for k,v in x.items()if k!='cs_ui_ns'})['status']=='UNVERIFIED'
    y={**x,'cs_lane_bitrate_bps':1600000000,'cs_ui_ns':.625,'cs_max_capability_bps':1664000000,
       'cs_ui_variation_percent':5,'cs_clk_post_ns':92.5,'cs_clk_pre_ns':5,'cs_hs_prepare_ns':42.5,
       'cs_hs_zero_ns':108.75,'cs_hs_settle_ns':88.75,'cs_eot_ns':112.5,'cs_hs_trail_ns':62.5,
       'cs_data_term_ns':37.5,'cs_sdd_h_db':-4.5,'cs_tx_rise_ps':250,'cs_lp_high_v':.95}
    assert registry.validate_parameters('mipi_csi2',y)['status']=='VALID'
    for patch in ({'cs_ui_variation_percent':5.001},{'cs_tx_rise_ps':250.001},{'cs_tx_rise_ps':49.999}):
        assert registry.validate_parameters('mipi_csi2',{**y,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{**y,'cs_tx_skew_ui':.2})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{**x,'cs_tx_static_skew_ui':.2})['status']=='INVALID'
    assert registry.validate_parameters('mipi_csi2',{**y,'cs_tx_static_skew_ui':.2,'cs_tx_dynamic_skew_ui':.15})['status']=='VALID'


def test_csi_confirmed_native_nondefault_rate_and_vc_survive_rejected_packet_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x=csi_long(1620);x.update(cs_lane_bitrate_bps=1200000000,cs_vc=2,cs_data_id=171,
        cs_cci_rate_bps=330000,cs_format='RAW12',cs_packing='PACKED_RAW12',cs_line_pixels=1080,cs_packing_remainder=0)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'mipi_csi2','technology_parameters':{'mipi_csi2':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['mipi_csi2']['values']['cs_packet_bytes']=1628
    bad['technology_parameters']['mipi_csi2']['provenance']['cs_packet_bytes']['value']=1628
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
    assert registry.profile('mipi_csi2')['capacity_evidence']['status']=='MODEL_MISSING'

from backend.communication.technologies import mil_std_1553 as MS

MIL1553_ACTUAL={'ms_'+k:'synthetic-actual-'+k for k in MS.REQUIRED}
MIL1553_ACTUAL.update(ms_edition=MS.EDITION,ms_application='BASE_C',ms_role='BC',ms_message='BC_RT',
                     ms_condition='NORMAL',bitrate=1000000)


def mil1553_packet(message='BC_RT',words=32):
    commands,status,responses,tr={'BC_RT':(1,1,1,0),'RT_BC':(1,1,1,1),'RT_RT':(2,2,2,0),
        'BC_BROADCAST':(1,0,0,0),'RT_BROADCAST':(2,1,1,0)}[message]
    x={**MIL1553_ACTUAL,'ms_message':message,'ms_command_address':31 if 'BROADCAST'in message else 2,
       'ms_source_rt_address':2 if message=='RT_BC' else 3,'ms_subaddress':7,'ms_tr_bit':tr,
       'ms_requested_data_words':words,'ms_count_code':words%32,'ms_data_words':words,'ms_data_octets':2*words,
       'payload_bytes':2*words,'ms_command_words':commands,'ms_status_words':status,'ms_response_count':responses,
       'ms_total_words':commands+status+words,'ms_wire_bit_times':20*(commands+status+words)}
    if 'BROADCAST'in message:x['ms_broadcast_supported']=True
    return x


def test_mil1553_revision_specific_standard_proposal_has_no_can_queue_or_payload_default():
    p=registry.profile('mil_std_1553');f={v['key']:v for v in registry.parameter_fields('mil_std_1553')}
    assert p['rate_model']['fixed_bps']==1000000
    assert registry.parameter_defaults_review('mil_std_1553')['values']=={}
    assert f['bitrate']['conditional_defaults']==[dict(when={'ms_edition':MS.EDITION},value=1000000,
        source=MS.CORE,source_revision=MS.SOURCES[MS.CORE])]
    assert 'default'not in f['payload_bytes'] and f['payload_bytes']['max']==64
    assert not set(MS.REMOVED)&set(f)
    assert registry.validate_parameters('mil_std_1553',MIL1553_ACTUAL)['status']=='UNVERIFIED'
    assert p['capacity_evidence']['status']=='MODEL_MISSING'
    x=mil1553_packet()
    for patch in ({'bitrate':500000},{'nominal_bitrate_bps':500000},{'retry_limit':3},
                  {'i2c_mode':'STANDARD'},{'local_timing_evidence':{'confirmed':True,'source':'not1553'}},
                  {'qos_priority':3}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'


@pytest.mark.parametrize('message',['BC_RT','RT_BC','RT_RT','BC_BROADCAST','RT_BROADCAST'])
@pytest.mark.parametrize('words',[1,2,31,32])
def test_mil1553_command_status_response_and_word_count_follow_each_actual_transfer(message,words):
    x=mil1553_packet(message,words)
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    for patch in ({'ms_count_code':(words+1)%32},{'ms_total_words':x['ms_total_words']+1},
                  {'ms_wire_bit_times':x['ms_wire_bit_times']*2},{'ms_command_words':3-x['ms_command_words']},
                  {'ms_status_words':(x['ms_status_words']+1)%3},{'ms_response_count':(x['ms_response_count']+1)%3},
                  {'ms_tr_bit':1-x['ms_tr_bit']},{'payload_bytes':2*words+1},{'ms_data_octets':2*words+1},
                  {'ms_subaddress':0}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'
    for key in ('ms_requested_data_words','ms_count_code','ms_subaddress','ms_command_address','ms_data_words','ms_data_octets'):
        assert registry.validate_parameters('mil_std_1553',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'
    if 'BROADCAST'in message:
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_command_address':30})['status']=='INVALID'
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_broadcast_supported':False})['status']=='INVALID'
    else:
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_command_address':31})['status']=='INVALID'
    if message=='RT_RT':
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_source_rt_address':2})['status']=='INVALID'
    assert registry.profile('mil_std_1553')['capacity_evidence']['status']=='MODEL_MISSING'


def mil1553_mode(code,broadcast=False):
    # Independent normative table, not a snapshot of registry constraints.
    table={0:(1,0,False),1:(1,0,True),2:(1,0,False),3:(1,0,True),4:(1,0,True),5:(1,0,True),
           6:(1,0,True),7:(1,0,True),8:(1,0,True),16:(1,1,False),17:(0,1,True),
           18:(1,1,False),19:(1,1,False),20:(0,1,True),21:(0,1,True)}
    tr,data,allowed=table[code]
    x={**MIL1553_ACTUAL,'ms_message':'MODE_BROADCAST'if broadcast else'MODE','ms_mode_code':code,
       'ms_mode_source':'synthetic-mode','ms_command_address':31 if broadcast else 2,'ms_subaddress':31,
       'ms_tr_bit':tr,'ms_data_words':data,'ms_data_octets':2*data,'payload_bytes':0,'ms_command_words':1,
       'ms_status_words':0 if broadcast else 1,'ms_response_count':0 if broadcast else 1}
    if broadcast:x['ms_broadcast_supported']=True
    if code in (4,5):x.update(ms_redundancy='DUAL_STANDBY',ms_bus_count=2,ms_redundancy_source='synthetic-redundancy')
    if code in (20,21):x.update(ms_redundancy='MULTIPLE_REGISTERED',ms_bus_count=3,ms_registered_source='synthetic-three-bus')
    if code in (4,5,20,21):x.update(ms_command_bus_id='command-bus',ms_target_bus_id='alternate-bus')
    if code==0:x['ms_dynamic_control_supported']=True
    return x,allowed


@pytest.mark.parametrize('code',[0,1,2,3,4,5,6,7,8,16,17,18,19,20,21])
@pytest.mark.parametrize('broadcast',[False,True])
def test_mil1553_mode_table_direction_one_or_no_data_and_broadcast_permission(code,broadcast):
    x,allowed=mil1553_mode(code,broadcast)
    if broadcast and not allowed:
        assert registry.validate_parameters('mil_std_1553',x)['status']=='INVALID';return
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    for patch in ({'ms_tr_bit':1-x['ms_tr_bit']},{'ms_data_words':2},{'ms_subaddress':1},
                  {'ms_count_code':1},{'ms_requested_data_words':1},{'payload_bytes':1},
                  {'ms_status_words':1 if broadcast else 0}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'
    if code in (4,5,20,21):
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_target_bus_id':'command-bus'})['status']=='INVALID'
        assert registry.validate_parameters('mil_std_1553',{k:v for k,v in x.items()if k!='ms_command_bus_id'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('code',list(range(9,16))+list(range(22,32)))
def test_mil1553_reserved_modes_cannot_be_assigned_custom_functions(code):
    x,_=mil1553_mode(1);x['ms_mode_code']=code
    assert registry.validate_parameters('mil_std_1553',x)['status']=='INVALID'


def test_mil1553_busy_transmitter_returns_status_without_requested_data_and_keeps_count():
    x=mil1553_packet('RT_BC',32)
    x.update(ms_condition='BUSY_TRANSMITTER',ms_busy_bit=True,ms_data_words=0,ms_data_octets=0,
             payload_bytes=0,ms_total_words=2,ms_wire_bit_times=40)
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    assert registry.validate_parameters('mil_std_1553',{**x,'payload_bytes':64})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{**x,'ms_busy_bit':False})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{**x,'ms_count_code':32})['status']=='INVALID'


@pytest.mark.parametrize('key,lo,hi',[('ms_response1_us',4,12),('ms_response2_us',4,12),
    ('ms_observed_bitrate_bps',999000,1001000),('ms_short_stability_hz',0,100),
    ('ms_intermessage_gap_us',4,None),('ms_no_response_timeout_us',14,None),('ms_hardware_failsafe_us',.01,800)])
def test_mil1553_timing_uses_actual_reference_points_and_clock_limits(key,lo,hi):
    x=mil1553_packet('RT_RT')
    x.update(ms_measurement_source='synthetic-pointA',ms_failsafe_hardware=True)
    assert registry.validate_parameters('mil_std_1553',{**x,key:lo})['status']=='VALID'
    if hi is not None:
        assert registry.validate_parameters('mil_std_1553',{**x,key:hi})['status']=='VALID'
        assert registry.validate_parameters('mil_std_1553',{**x,key:hi+1})['status']=='INVALID'
    if key!='ms_hardware_failsafe_us':
        assert registry.validate_parameters('mil_std_1553',{**x,key:lo-1})['status']=='INVALID'
    else:
        assert registry.validate_parameters('mil_std_1553',{**x,key:0})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{k:v for k,v in {**x,key:lo}.items()if k!='ms_measurement_source'})['status']=='UNVERIFIED'
    x=mil1553_packet('BC_BROADCAST');x.update(ms_measurement_source='synthetic-pointA',ms_response1_us=4)
    assert registry.validate_parameters('mil_std_1553',x)['status']=='INVALID'


@pytest.mark.parametrize('scope',['A2_ARMY','A2_NAVY','A2_AIR_FORCE'])
def test_mil1553_appendix_scope_changes_broadcast_redundancy_coupling_shield_and_address(scope):
    x=mil1553_packet();x.update(ms_application=scope,ms_role='RT',ms_redundancy='DUAL_STANDBY',ms_bus_count=2,
        ms_active_bus_count=1,ms_redundancy_source='synthetic-dual',ms_coupling='TRANSFORMER',ms_address_valid=True,
        ms_address_wiring_source='synthetic-external-validated',ms_cable_shield_percent=90,ms_reset_bound_ms=5,
        ms_self_test_bound_ms=100,ms_rt_rt_validation_us=57,ms_both_mode_subaddresses=True,
        ms_required_modes_supported=True,ms_minimum_formats_supported=True,ms_positive_center_pin=True,
        ms_dual_terminal_connectors=True)
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    for patch in ({'ms_cable_shield_percent':89.99},{'ms_reset_bound_ms':5.01},{'ms_self_test_bound_ms':100.01},
                  {'ms_rt_rt_validation_us':60.01},{'ms_address_valid':False},{'ms_bus_count':1},
                  {'ms_active_bus_count':2},{'ms_both_mode_subaddresses':False},{'ms_redundancy':'SINGLE'}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{**x,'ms_coupling':'DIRECT'})['status']==('VALID'if scope=='A2_NAVY'else'INVALID')
    if scope=='A2_NAVY':
        assert registry.validate_parameters('mil_std_1553',{**x,'ms_dual_terminal_connectors':False})['status']=='INVALID'
    y,_=mil1553_mode(0);y.update(ms_application=scope,ms_redundancy='DUAL_STANDBY',ms_redundancy_source='synthetic-dual')
    assert registry.validate_parameters('mil_std_1553',y)['status']==('INVALID'if scope=='A2_AIR_FORCE'else'VALID')
    b=mil1553_packet('BC_BROADCAST');b.update(ms_application=scope,ms_redundancy='DUAL_STANDBY',ms_redundancy_source='synthetic-dual')
    assert registry.validate_parameters('mil_std_1553',b)['status']=='INVALID'


@pytest.mark.parametrize('coupling,stub,tx,fixture,rxlo,rxhi,nothi,impedance,awgn,testinput',[
    ('TRANSFORMER',20,27,70,.86,14,.2,1000,140,2.1),('DIRECT',1,9,35,1.2,20,.28,2000,200,3)])
def test_mil1553_stub_fixture_receiver_and_noise_envelopes_are_never_interchanged(coupling,stub,tx,fixture,rxlo,rxhi,nothi,impedance,awgn,testinput):
    x={**mil1553_packet(),'ms_coupling':coupling,'ms_stub_policy':'RECOMMENDED_SHORT','ms_stub_ft':stub,
       'ms_measurement_source':'synthetic-qualified-fixture','ms_measurement_point':'TERMINAL_FIXTURE_A',
       'ms_tx_vpp':tx,'ms_fixture_ohm':fixture,'ms_tx_rise_ns':100,'ms_tx_fall_ns':300,'ms_tx_crossing_ns':25}
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    for patch in ({'ms_stub_ft':stub+.01},{'ms_tx_vpp':tx+.01},{'ms_fixture_ohm':fixture*1.021},
                  {'ms_tx_rise_ns':99.99},{'ms_tx_fall_ns':300.01},{'ms_tx_crossing_ns':25.01},
                  {'ms_measurement_point':'STUB_A'}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'
    y={**x,'ms_stub_ft':stub+1,'ms_stub_policy':'QUALIFIED_EXCEPTION','ms_stub_exception_source':'synthetic-installed-waveform'}
    assert registry.validate_parameters('mil_std_1553',y)['status']=='VALID'
    assert registry.validate_parameters('mil_std_1553',{k:v for k,v in y.items()if k!='ms_stub_exception_source'})['status']=='UNVERIFIED'
    for value in (rxlo,rxhi):
        y={**mil1553_packet(),'ms_coupling':coupling,'ms_measurement_source':'synthetic-stubA',
           'ms_measurement_point':'STUB_A','ms_receiver_region':'RESPOND','ms_rx_vpp':value,'ms_rx_input_ohm':impedance}
        assert registry.validate_parameters('mil_std_1553',y)['status']=='VALID'
        assert registry.validate_parameters('mil_std_1553',{**y,'ms_rx_vpp':rxlo-.01})['status']=='INVALID'
        assert registry.validate_parameters('mil_std_1553',{**y,'ms_rx_input_ohm':impedance-1})['status']=='INVALID'
    y.update(ms_receiver_region='NO_RESPONSE',ms_rx_vpp=nothi)
    assert registry.validate_parameters('mil_std_1553',y)['status']=='VALID'
    assert registry.validate_parameters('mil_std_1553',{**y,'ms_rx_vpp':nothi+.01})['status']=='INVALID'
    y.update(ms_noise_awgn_mvrms=awgn,ms_noise_input_vpp=testinput,ms_noise_word_error_rate=1e-7,ms_noise_test_source='synthetic-TableII')
    assert registry.validate_parameters('mil_std_1553',y)['status']=='VALID'
    assert registry.validate_parameters('mil_std_1553',{**y,'ms_noise_awgn_mvrms':awgn+1})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{**y,'ms_noise_word_error_rate':1.01e-7})['status']=='INVALID'


def test_mil1553_cable_termination_fault_load_and_strict_transformer_bounds():
    x={**mil1553_packet(),'ms_coupling':'TRANSFORMER','ms_cable_nominal_ohm':78,'ms_termination_ohm':79.56,
       'ms_isolation_resistor_ohm':58.5,'ms_fault_impedance_ohm':117,'ms_turns_ratio':1.4523,
       'ms_measurement_source':'synthetic-transformer','ms_measurement_point':'TRANSFORMER_B',
       'ms_transformer_open_ohm':3000.01,'ms_transformer_ringing_v':.999,'ms_transformer_cmrr_db':45.01,
       'ms_transformer_droop_percent':20}
    assert registry.validate_parameters('mil_std_1553',x)['status']=='VALID'
    for patch in ({'ms_termination_ohm':79.56000000001},{'ms_fault_impedance_ohm':116.9999},
                  {'ms_turns_ratio':1.452300000001},{'ms_transformer_open_ohm':3000},
                  {'ms_transformer_ringing_v':1},{'ms_transformer_cmrr_db':45},
                  {'ms_transformer_droop_percent':20.01}):
        assert registry.validate_parameters('mil_std_1553',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('mil_std_1553',{k:v for k,v in x.items()if k!='ms_cable_nominal_ohm'})['status']=='UNVERIFIED'
    y={**mil1553_packet(),'ms_coupling':'DIRECT','ms_isolation_resistor_ohm':53.9,'ms_fault_impedance_ohm':110}
    assert registry.validate_parameters('mil_std_1553',y)['status']=='VALID'
    assert registry.validate_parameters('mil_std_1553',{**y,'ms_turns_ratio':1.41})['status']=='INVALID'


def test_mil1553_confirmed_nondefault_addresses_and_observed_clock_survive_rejected_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x=mil1553_packet('RT_RT',11)
    x.update(ms_command_address=27,ms_source_rt_address=13,ms_observed_bitrate_bps=999750,
             ms_measurement_source='synthetic-qualified-clock',ms_response1_us=11.5,ms_response2_us=8.75)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'mil_std_1553','technology_parameters':{'mil_std_1553':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['mil_std_1553']['values']['ms_command_address']=31
    bad['technology_parameters']['mil_std_1553']['provenance']['ms_command_address']['value']=31
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==parameters


@pytest.mark.parametrize('key,kind',[(v['key'],v['type'])for v in MS.DECLARATIONS if v['type']in('number','boolean')])
def test_mil1553_every_native_scalar_rejects_coerced_text(key,kind):
    assert registry.validate_parameters('mil_std_1553',{**mil1553_packet(),key:'1'})['status']=='INVALID'


from backend.communication.technologies import matter as MT

MATTER_ACTUAL={'mt_'+k:'synthetic-actual-'+k for k in MT.REQUIRED}
MATTER_ACTUAL.update(mt_edition=MT.EDITION,mt_implementation=MT.SDK,mt_phase='OPERATIONAL',
    mt_transport='UDP',mt_lower_path_kind='THREAD',mt_session_kind='SECURE_UNICAST',mt_direction='OUTGOING',
    mt_session_establishment='CASE')


def matter_packet(payload=1198):
    return {**MATTER_ACTUAL,'payload_bytes':payload,'mt_source_id_present':False,'mt_destination_encoding':'ELIDED',
      'mt_message_extension_present':False,'mt_vendor_present':False,'mt_ack_present':False,'mt_secured_extension_present':False,
      'mt_message_header_octets':8,'mt_protocol_header_octets':6,'mt_mic_octets':16,'mt_message_octets':payload+30,
      'mt_ip_extension_octets':0,'mt_udp_ip_octets':48,'mt_ip_packet_octets':payload+78,'mt_framing_octets':0,
      'mt_stream_octets':payload+30}


def test_matter_has_explicit_lower_link_and_no_can_frame_queue_or_foreign_defaults():
    p=registry.profile('matter');fields={v['key']:v for v in registry.parameter_fields('matter')}
    assert p['domain']=='generic_networking' and p['max_payload_bytes']is None
    assert p['rate_model']['fields']==[] and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('matter')['values']=={}
    assert registry.validate_parameters('matter',MATTER_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('matter',{})['status']=='UNVERIFIED'
    assert not set(MT.REMOVED)&fields.keys()
    assert fields['payload_bytes']['min']==0 and 'max'not in fields['payload_bytes'] and 'default'not in fields['payload_bytes']
    for key in ('mt_fabric_id','mt_source_node_id','mt_session_id','mt_message_counter','mt_key_ref',
                'mt_supported_fabrics','mt_capacity_confirmed','mt_tcp_local_max_message_octets','mt_source_port'):
        assert 'default'not in fields[key] and 'conditional_defaults'not in fields[key]
    for patch in ({'bitrate':500000},{'retry_limit':0},{'qos_priority':3},{'local_timing_evidence':{'slave_address':32}}):
        assert registry.validate_parameters('matter',{**MATTER_ACTUAL,**patch})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('matter'),ids=lambda f:'matter/'+f['key'])
def test_each_matter_parameter_validates_its_own_type_integer_and_scalar_bounds(field):
    key=field['key'];bad={'number':True,'boolean':'false','select':'invalid-option','text':42}.get(field['type'])
    if bad is not None:assert registry.validate_parameters('matter',{**MATTER_ACTUAL,key:bad})['status']=='INVALID'
    for boundary,offset in [('min',-1),('max',1)]:
        if boundary in field:assert registry.validate_parameters('matter',{**MATTER_ACTUAL,key:field[boundary]+offset})['status']=='INVALID'
    if field.get('integer') and field['type']=='number':
        assert registry.validate_parameters('matter',{**MATTER_ACTUAL,key:field.get('min',0)+.5})['status']=='INVALID'


@pytest.mark.parametrize('link',['ETHERNET','WIFI','THREAD'])
def test_matter_operational_udp_uses_selected_link_without_changing_native_limits(link):
    x={**matter_packet(1202),'mt_lower_path_kind':link}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert x['mt_ip_packet_octets']==1280
    assert registry.validate_parameters('matter',{**matter_packet(1203),'mt_lower_path_kind':link})['status']=='INVALID'
    assert registry.validate_parameters('matter',{**x,'mt_ip_extension_octets':8,'mt_udp_ip_octets':56,'mt_ip_packet_octets':1288})['status']=='INVALID'
    assert registry.validate_parameters('matter',{**x,'mt_ip_packet_octets':1279})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_udp_ip_octets'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('transport,link,framing',[('BTP','BLUETOOTH_LE',2),('PAFTP','WIFI_PAF',2),('NTL','NFC',0)])
def test_matter_commissioning_channels_cannot_become_operational_ip_or_mrp(transport,link,framing):
    x={**MATTER_ACTUAL,'mt_phase':'COMMISSIONING','mt_session_establishment':'PASE','mt_transport':transport,
       'mt_lower_path_kind':link,'mt_commissioning_source':'synthetic-qualified-channel','mt_framing_octets':framing}
    if transport=='NTL':x['mt_nt_l_alternate_channel']=True
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for patch in ({'mt_phase':'OPERATIONAL'},{'mt_lower_path_kind':'ETHERNET'},
                  {'mt_max_transmissions':5},{'mt_framing_octets':4}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'
    if transport=='NTL':assert registry.validate_parameters('matter',{**x,'mt_nt_l_alternate_channel':False})['status']=='INVALID'


def matter_tcp():
    x=matter_packet(63970)
    for k in ('mt_ip_extension_octets','mt_udp_ip_octets','mt_ip_packet_octets'):x.pop(k)
    x.update(mt_transport='TCP',mt_lower_path_kind='ETHERNET',mt_framing_octets=4,mt_stream_octets=64004,
             mt_peer_tcp_supported=True,mt_local_tcp_supported=True,mt_tcp_source='synthetic-authenticated-peers',
             mt_tcp_peer_max_message_octets=64000,mt_tcp_local_max_message_octets=64000,mt_needs_ack=False)
    return x


def test_matter_tcp_negotiated_message_bound_excludes_length_prefix_and_has_its_own_reliability():
    x=matter_tcp();assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert x['mt_message_octets']==64000 and x['mt_stream_octets']==64004
    for patch in ({'mt_needs_ack':True},{'mt_max_transmissions':5},{'mt_ip_packet_octets':64048},
                  {'mt_tcp_peer_max_message_octets':63999},{'mt_tcp_local_max_message_octets':63999},
                  {'mt_peer_tcp_supported':False},{'mt_framing_octets':2},{'mt_stream_octets':64000}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'
    for key in ('mt_tcp_peer_max_message_octets','mt_tcp_local_max_message_octets','mt_tcp_source','mt_peer_tcp_supported'):
        assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'
    x.update(mt_tcp_keepalive_enabled=True,mt_tcp_keepalive_time_ms=1000,mt_tcp_keepalive_interval_ms=100,
             mt_tcp_keepalive_probes=3,mt_tcp_keepalive_timeout_ms=1300)
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,'mt_tcp_keepalive_timeout_ms':1200})['status']=='INVALID'
    assert registry.validate_parameters('matter',{**MATTER_ACTUAL,'mt_tcp_user_timeout_ms':1000})['status']=='INVALID'


@pytest.mark.parametrize('key,default',[('mt_peer_idle_ms',500),('mt_peer_active_ms',300),('mt_peer_threshold_ms',4000)])
def test_matter_peer_fallback_is_distinct_from_discovery_session_and_local_values(key,default):
    fields={v['key']:v for v in registry.parameter_fields('matter')}
    proposal=fields[key]['conditional_defaults'][0]
    assert proposal['value']==default and proposal['when']=={'mt_edition':MT.EDITION,'mt_peer_parameter_origin':'STANDARD_FALLBACK'}
    x={**MATTER_ACTUAL,key:3600000 if key!='mt_peer_threshold_ms' else 65535,
       'mt_parameter_source':'synthetic-peer','mt_peer_parameter_origin':'DNS_SD'}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,key:x[key]+1})['status']=='INVALID'
    if key!='mt_peer_threshold_ms':
        x.update(mt_peer_parameter_origin='SESSION_ESTABLISHMENT');x[key]=4294967295
        assert registry.validate_parameters('matter',x)['status']=='VALID'
        assert registry.validate_parameters('matter',{**x,key:4294967296})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_parameter_source'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('matter',{**x,'mt_local_idle_ms':2000,'mt_local_active_ms':2000})['status']=='VALID'


@pytest.mark.parametrize('ot,linux,expected',[(False,False,(500,300,0)),(False,True,(500,300,0)),
                                           (True,False,(2000,2000,1500)),(True,True,(500,300,0))])
def test_matter_pinned_sdk_proposals_are_conditioned_on_actual_platform_and_non_icd(ot,linux,expected):
    fields={v['key']:v for v in registry.parameter_fields('matter')}
    for key,value in zip(('mt_local_idle_ms','mt_local_active_ms','mt_sdk_sender_boost_ms'),expected):
        candidates=[v for v in fields[key]['conditional_defaults']if v['when']['mt_sdk_openthread']==ot and v['when']['mt_sdk_linux']==linux]
        assert len(candidates)==1 and candidates[0]['value']==value
        assert candidates[0]['when']['mt_implementation']==MT.SDK and candidates[0]['when']['mt_sdk_icd_enabled']is False
        assert candidates[0]['source']==MT.MRPH


@pytest.mark.parametrize('attempt,jitter',[(0,0),(0,255),(1,0),(2,128),(4,255),(5,255),(9,0)])
def test_matter_pinned_sdk_rounding_and_exponent_clamp_are_not_replaced_by_real_equation(attempt,jitter):
    # Independently evaluate the three integer divisions and SDK exponent clamp.
    base=301;exponent=min(4,max(0,attempt-1))
    expected=(((base*1127//1024)*16**exponent//10**exponent)*(1024+jitter)//1024)+1500+200
    x={**MATTER_ACTUAL,'mt_timer_arithmetic':'CHIP_FIXED_POINT','mt_base_interval_ms':base,'mt_backoff_attempt':attempt,
       'mt_sdk_jitter_u8':jitter,'mt_sdk_sender_boost_ms':1500,'mt_sdk_icd_fast_poll_ms':200,'mt_backoff_ms':expected}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,'mt_backoff_ms':expected+1})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_sdk_sender_boost_ms'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('matter',{**x,'mt_implementation':'REGISTERED_IMPLEMENTATION','mt_registered_source':'synthetic-other'})['status']=='INVALID'


@pytest.mark.parametrize('attempt,jitter',[(0,0),(1,1),(2,.5),(4,1)])
def test_matter_standard_real_equation_uses_selected_peer_base_and_jitter(attempt,jitter):
    expected=500*1.1*1.6**max(0,attempt-1)*(1+jitter*.25)
    x={**MATTER_ACTUAL,'mt_timer_arithmetic':'SPEC_REAL','mt_base_interval_ms':500,'mt_backoff_attempt':attempt,
       'mt_backoff_margin':1.1,'mt_backoff_base':1.6,'mt_backoff_threshold':1,'mt_jitter_unit':jitter,
       'mt_backoff_jitter':.25,'mt_backoff_ms':expected}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,'mt_backoff_ms':expected+1})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_base_interval_ms'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('source,encoding,extra',[(False,'ELIDED',0),(True,'ELIDED',8),(False,'NODE',8),(True,'NODE',16),(True,'GROUP',10)])
def test_matter_optional_header_bytes_are_counted_without_inventing_a_payload_maximum(source,encoding,extra):
    x={**matter_packet(8),'mt_source_id_present':source,'mt_destination_encoding':encoding,
       'mt_message_header_octets':8+extra,'mt_message_octets':38+extra,'mt_ip_packet_octets':86+extra,'mt_stream_octets':38+extra}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,'mt_message_header_octets':9+extra})['status']=='INVALID'
    x.update(mt_direction='INCOMING',mt_message_extension_present=True,mt_message_extension_octets=3,
             mt_message_header_octets=13+extra,mt_message_octets=43+extra,mt_ip_packet_octets=91+extra,mt_stream_octets=43+extra)
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,'mt_direction':'OUTGOING'})['status']=='INVALID'


@pytest.mark.parametrize('node_id',['0000000000000001','0020000000000001','ffffffefffffffff','FFFFFFEFFFFFFFFF'])
def test_matter_operational_uint64_identity_is_lossless_and_excludes_reserved_ranges(node_id):
    x={**MATTER_ACTUAL,'mt_source_node_id':node_id,'mt_fabric_id':'0000000000000001'}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for bad in (0,9007199254740993,'0000000000000000','fffffff000000000','ffffffffffffffff','1','10000000000000000'):
        assert registry.validate_parameters('matter',{**x,'mt_source_node_id':bad})['status']=='INVALID'


def test_matter_group_data_and_standalone_ack_have_different_reliability_and_payload_rules():
    x={**MATTER_ACTUAL,'mt_session_kind':'GROUP','mt_session_establishment':'GROUP_KEYS','mt_group_source':'synthetic-group',
       'mt_source_id_present':True,'mt_destination_encoding':'GROUP','mt_control_message':False,'mt_needs_ack':False,'mt_ack_present':False,
       'mt_privacy':True}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for patch in ({'mt_needs_ack':True},{'mt_ack_present':True,'mt_ack_counter':7},{'mt_transport':'TCP'},
                  {'mt_source_id_present':False},{'mt_group_id':0xFFFD},{'mt_destination_port':5550},{'mt_privacy':False}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_control_message'})['status']=='UNVERIFIED'
    ack={**MATTER_ACTUAL,'mt_message_kind':'STANDALONE_ACK','mt_protocol_id':0,'mt_opcode':0x10,
         'mt_ack_present':True,'mt_ack_counter':99,'payload_bytes':0}
    assert registry.validate_parameters('matter',ack)['status']=='VALID'
    for patch in ({'payload_bytes':1},{'mt_opcode':0x50},{'mt_protocol_id':1},{'mt_needs_ack':True}):
        assert registry.validate_parameters('matter',{**ack,**patch})['status']=='INVALID'


@pytest.mark.parametrize('opcode',range(1,11))
def test_matter_each_im_opcode_uses_its_protocol_namespace_without_assuming_cluster_revision(opcode):
    x={**MATTER_ACTUAL,'mt_protocol_id':1,'mt_protocol_vendor_id':0,'mt_opcode':opcode,'mt_im_revision':13}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for bad in (0,11,16,255):assert registry.validate_parameters('matter',{**x,'mt_opcode':bad})['status']=='INVALID'
    x.update(mt_protocol_vendor_id=0x1234,mt_message_kind='REGISTERED_VENDOR',mt_opcode=255,mt_registered_source='synthetic-vendor-schema')
    assert registry.validate_parameters('matter',x)['status']=='VALID'


@pytest.mark.parametrize('field,minimum', [('mt_acl_entries_per_fabric',4),('mt_case_sessions_per_fabric',3),
    ('mt_read_paths_per_interaction',9),('mt_subscriptions_per_fabric',3),('mt_subscription_paths',3)])
def test_matter_guaranteed_resources_use_standard_per_fabric_minima_not_sdk_global_pool(field,minimum):
    x={**MATTER_ACTUAL,field:minimum,'mt_supported_fabrics':5}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    assert registry.validate_parameters('matter',{**x,field:minimum-1})['status']=='INVALID'
    for kind,n in [('NONE',1),('GROUPS',3),('GROUPCAST',4)]:
        assert registry.validate_parameters('matter',{**x,'mt_group_cluster':kind,'mt_group_keys_per_fabric':n})['status']=='VALID'
        assert registry.validate_parameters('matter',{**x,'mt_group_cluster':kind,'mt_group_keys_per_fabric':n-1})['status']=='INVALID'


def test_matter_icd_seconds_ms_runtime_lit_registration_and_normative18hour_limit_are_distinct():
    x={**MATTER_ACTUAL,'mt_icd_mode':'LIT','mt_icd_source':'synthetic-icd','mt_icd_sai_advertised':True,
       'mt_icd_lit_feature':True,'mt_icd_user_trigger':True,'mt_icd_checkin_supported':True,'mt_icd_registered_clients':1,
       'mt_icd_threshold_ms':5000,'mt_icd_idle_s':64800,'mt_icd_active_ms':1000,'mt_icd_fast_poll_ms':999,
       'mt_icd_checkin_backoff_s':64800,'mt_icd_clients_per_fabric':1}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for patch in ({'mt_icd_idle_s':68400},{'mt_icd_checkin_backoff_s':68400},{'mt_icd_threshold_ms':4999},
                  {'mt_icd_registered_clients':0},{'mt_icd_fast_poll_ms':1000},{'mt_icd_clients_per_fabric':0},
                  {'mt_icd_checkin_supported':False},{'mt_icd_user_trigger':False},{'mt_icd_lit_feature':False}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'
    x.update(mt_icd_mode='SIT',mt_icd_sii_advertised=True,mt_icd_slow_poll_ms=15000,mt_icd_idle_s=1,
             mt_icd_checkin_backoff_s=1,mt_icd_active_ms=1000)
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for patch in ({'mt_icd_slow_poll_ms':15001},{'mt_icd_sii_advertised':False},{'mt_icd_active_ms':1001}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'


def test_matter_invoke_multiple_paths_match_peer_capacity_and_exclude_group_or_wildcard_targets():
    x={**MATTER_ACTUAL,'mt_invoke_paths':2,'mt_max_paths_per_invoke':2,'mt_invoke_group_target':False,'mt_invoke_wildcard_target':False}
    assert registry.validate_parameters('matter',x)['status']=='VALID'
    for patch in ({'mt_invoke_paths':3},{'mt_invoke_group_target':True},{'mt_invoke_wildcard_target':True}):
        assert registry.validate_parameters('matter',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('matter',{k:v for k,v in x.items()if k!='mt_max_paths_per_invoke'})['status']=='UNVERIFIED'


def test_matter_confirmed_peer_interval_and_uint64_identity_survive_rejected_foreign_transport_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x={**MATTER_ACTUAL,'mt_peer_parameter_origin':'SESSION_ESTABLISHMENT','mt_parameter_source':'synthetic-peer-session',
       'mt_peer_idle_ms':5300,'mt_peer_active_ms':1250,'mt_peer_threshold_ms':5000,
       'mt_source_node_id':'0020000000000001','mt_fabric_id':'0000000000000001'}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'matter','technology_parameters':{'matter':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['matter']['values']['mt_transport']='BTP'
    bad['technology_parameters']['matter']['provenance']['mt_transport']['value']='BTP'
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
    assert registry.profile('matter')['capacity_evidence']['status']=='MODEL_MISSING'

from backend.communication.technologies import m_bus as MB

MBUS_ACTUAL={**{'mb_'+k:'synthetic-actual-'+k for k in MB.REQUIRED if k not in ('edition','role','direction','hardware')},
    'mb_edition':MB.EDITION,'mb_role':'MASTER','mb_direction':'DOWN','mb_hardware':'REGISTERED_HARDWARE',
    'mb_registered_source':'synthetic-qualified-other-hardware'}
MBUS_SOURCE_ONLY=dict(MBUS_ACTUAL)
# Actual synthetic endpoint capabilities are explicit test inputs, never defaults.
MBUS_ACTUAL.update(bitrate=300,mb_rate_set='OMS_STANDARD_SET',mb_rx_baud=300,mb_tx_baud=300,
                   mb_master_max_baud=38400,mb_slave_max_baud=38400)
for endpoint in ('master','slave'):
    MBUS_ACTUAL.update({'mb_'+endpoint+'_support_'+str(b):True for b in MB.BAUDS})


def m_bus_rate(rate=300,master=38400,slave=38400):
    x={**MBUS_ACTUAL,'bitrate':rate,'mb_rate_set':'OMS_STANDARD_SET','mb_rx_baud':rate,'mb_tx_baud':rate,
      'mb_master_max_baud':master,'mb_slave_max_baud':slave}
    for endpoint,maximum in [('master',master),('slave',slave)]:
        x.update({'mb_'+endpoint+'_support_'+str(b):b<=maximum for b in MB.BAUDS})
    return x


def m_bus_physical():
    return {**MBUS_ACTUAL,'mb_topology':'TREE','mb_termination_present':False,'mb_bus_ground_coupled':False,
      'mb_measurement_source':'synthetic-installation-measurement','mb_slave_units':2,'mb_slave_mark_ma':2,
      'mb_slave_space_increment_ma':15,'mb_slave_space_total_ma':17,'mb_total_units':20,'mb_master_capacity_units':30,
      'mb_master_idle_ma':20,'mb_current_budget_ma':40,'mb_line_loop_ohm':75,'mb_master_source_ohm':25,'mb_drop_v':4,
      'mb_master_mark_v':36,'mb_master_space_v':24,'mb_slave_mark_v':32,'mb_slave_space_v':20,'mb_voltage_delta_v':12,
      'mb_series_protection_ohm':430,'mb_inrush_ma':99,'mb_charge_v_s':100,'mb_discharge_v_s':2,
      'mb_startup_delay_s':2.999,'mb_switchon_slew_v_s':168}


def test_m_bus_wired_defaults_and_capability_do_not_inherit_can_or_wireless_values():
    p=registry.profile('m_bus');f={v['key']:v for v in registry.parameter_fields('m_bus')}
    assert p['domain']=='generic_networking'and p['default_stack']==['m_bus']
    assert p['max_payload_bytes']is None and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('m_bus')['values']=={}
    assert registry.validate_parameters('m_bus',MBUS_ACTUAL)['status']=='VALID'
    source_only=registry.validate_parameters('m_bus',MBUS_SOURCE_ONLY)
    assert source_only['status']=='UNVERIFIED'
    assert any(v.get('parameter')=='bitrate_bps'for v in source_only['findings'])
    assert registry.validate_parameters('m_bus',{})['status']=='UNVERIFIED'
    assert not set(MB.REMOVED)&f.keys()
    assert 'default'not in f['bitrate']
    assert f['bitrate']['conditional_defaults'][0]['value']==300
    assert f['bitrate']['conditional_defaults'][0]['when']=={'mb_edition':MB.EDITION,'mb_rate_set':'OMS_STANDARD_SET'}
    for key in ('payload_bytes','mb_primary_address','mb_secondary_id','mb_master_mark_v','mb_slave_units',
                'mb_master_capacity_units','mb_key_ref','mb_capacity_confirmed','mb_response_wait_ms','mb_master_max_baud'):
        assert 'default'not in f[key]and'conditional_defaults'not in f[key]
    for patch in ({'bitrate':500000,'mb_rate_set':'OMS_STANDARD_SET'}, {'qos_priority':7},
                  {'local_timing_evidence':{'slave_address':32}}):
        assert registry.validate_parameters('m_bus',{**MBUS_ACTUAL,**patch})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('m_bus'),ids=lambda f:'m_bus/'+f['key'])
def test_each_m_bus_field_has_its_own_source_type_and_qualified_scalar_limits(field):
    x={**MBUS_ACTUAL};key=field['key']
    bad={'number':True,'boolean':'false','select':'not-an-option','text':42}.get(field['type'])
    if bad is not None:assert registry.validate_parameters('m_bus',{**x,key:bad})['status']=='INVALID'
    for bound,offset in [('min',-1),('max',1)]:
        if bound in field:assert registry.validate_parameters('m_bus',{**x,key:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):assert registry.validate_parameters('m_bus',{**x,key:field.get('min',0)+.5})['status']=='INVALID'


@pytest.mark.parametrize('rate',MB.BAUDS)
def test_m_bus_each_baud_is_matched_to_independent_master_and_slave_capabilities(rate):
    x=m_bus_rate(rate);assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_rx_baud':rate+1})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_tx_baud':rate+1})['status']=='INVALID'
    for endpoint in ('master','slave'):
        assert registry.validate_parameters('m_bus',{**x,'mb_'+endpoint+'_support_300':False})['status']=='INVALID'
        assert registry.validate_parameters('m_bus',{**x,'mb_'+endpoint+'_support_2400':False})['status']=='INVALID'
    x=m_bus_rate(rate,38400,2400)
    assert registry.validate_parameters('m_bus',x)['status']==('VALID'if rate<=2400 else'INVALID')


@pytest.mark.parametrize('maximum',MB.BAUDS[1:])
def test_m_bus_optional_baud_capabilities_require_each_endpoint_lower_rates(maximum):
    x=m_bus_rate(300,maximum,maximum)
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    for endpoint in ('master','slave'):
        for rate in MB.BAUDS:
            if rate>maximum:continue
            key='mb_'+endpoint+'_support_'+str(rate)
            assert registry.validate_parameters('m_bus',{**x,key:False})['status']=='INVALID'
            assert registry.validate_parameters('m_bus',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'
    x=m_bus_rate(600);x.update(mb_rate_set='REGISTERED_ADDITIONAL')
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{k:v for k,v in x.items()if k!='mb_registered_source'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('units,low,high',[(1,0,1.5),(2,1.5001,3),(3,3.0001,4.5),(4,4.5001,6)])
def test_m_bus_unit_load_identity_is_not_primary_address_space_or_fixed_current(units,low,high):
    for current in (low,high):
        x={**MBUS_ACTUAL,'mb_slave_units':units,'mb_slave_mark_ma':current,'mb_measurement_source':'synthetic-current'}
        assert registry.validate_parameters('m_bus',x)['status']=='VALID'
        assert registry.validate_parameters('m_bus',{**x,'mb_slave_mark_ma':high+.0001})['status']=='INVALID'
        if units>1:assert registry.validate_parameters('m_bus',{**x,'mb_slave_mark_ma':1.5*(units-1)})['status']=='INVALID'
    x={**MBUS_ACTUAL,'mb_slave_count':250,'mb_total_units':1000,'mb_master_capacity_units':250}
    assert registry.validate_parameters('m_bus',x)['status']=='INVALID'
    x['mb_master_capacity_units']=1000
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'


@pytest.mark.parametrize('key,value',[
 ('mb_topology','RING'),('mb_termination_present',True),('mb_bus_ground_coupled',True),
 ('mb_shield_at_master_only',False),('mb_half_duplex',False),('mb_break_detection',False),
 ('mb_secondary_supported',False),('mb_master_count',2),('mb_slave_space_increment_ma',10.999),
 ('mb_slave_space_increment_ma',20.001),('mb_slave_space_total_ma',15),('mb_drop_v',3.999),
 ('mb_master_mark_v',27.999),('mb_master_space_v',15.999),('mb_master_space_v',24.001),
 ('mb_slave_mark_v',31.999),('mb_slave_mark_v',36.001),('mb_slave_space_v',19.999),
 ('mb_slave_space_v',24.001),('mb_voltage_delta_v',11.999),('mb_voltage_delta_v',15.001),
 ('mb_series_protection_ohm',419.999),('mb_series_protection_ohm',440.001),('mb_inrush_ma',100),
 ('mb_startup_delay_s',3),('mb_switchon_slew_v_s',167.999),('mb_charge_v_s',60)])
def test_m_bus_voltage_current_topology_and_recovery_have_their_own_closed_or_strict_limits(key,value):
    x=m_bus_physical();assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,key:value})['status']=='INVALID'


@pytest.mark.parametrize('rate',MB.BAUDS)
def test_m_bus_clean_reply_and_loaded_edges_use_actual_baud_and_do_not_become_functional_deadline(rate):
    x={**m_bus_rate(rate),'mb_measurement_source':'synthetic-clocked-load-fixture','mb_load_scope':'EN2018_LOAD_FIXTURE',
      'mb_response_wait_ms':50,'mb_rise_us':500000/rate-.001,'mb_fall_us':500000/rate-.001}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID',registry.validate_parameters('m_bus',x)
    assert registry.validate_parameters('m_bus',{**x,'mb_rise_us':500000/rate})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_fall_us':500000/rate+.001})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_response_wait_ms':11000/rate-.001})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_response_wait_ms':50+330000/rate+.001})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_response_wait_ms':50,'deadline_ms':1000})['status']=='VALID'
    for key in ('response_min_bits','response_max_bits','response_max_add_ms','disturbed_idle_bits'):
        assert registry.validate_parameters('m_bus',{**x,'mb_'+key:0})['status']=='INVALID'


@pytest.mark.parametrize('state,valid,invalid',[
 ('MARK',6,6.0001),('SPACE',9,8.9999),('SPACE',50,50.0001),
 ('MANDATORY_COLLISION',50.0001,50),('EARLY_COLLISION',25.0001,25)])
def test_m_bus_master_detects_incremental_current_with_its_own_thresholds(state,valid,invalid):
    x={**MBUS_ACTUAL,'mb_receive_state':state,'mb_master_idle_ma':100,'mb_master_delta_ma':valid,
       'mb_receive_pulse_ms':49.999,'mb_receive_duty_ratio':.9199,
       'mb_measurement_source':'synthetic-current-pulses'}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_master_delta_ma':invalid})['status']=='INVALID'
    if state in ('MARK','SPACE'):
        for key,limit in [('mb_receive_pulse_ms',50),('mb_receive_duty_ratio',.92)]:
            assert registry.validate_parameters('m_bus',{**x,key:limit})['status']=='INVALID'
            assert registry.validate_parameters('m_bus',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'


@pytest.mark.parametrize('ci',list(MB.CI))
def test_m_bus_every_oms_ci_has_its_own_direction_header_and_wired_applicability(ci):
    direction,header=MB.CI[ci]
    x={**MBUS_ACTUAL,'mb_ci':ci,'mb_ci_direction':direction,'mb_tpl_header':header,
      'mb_direction':'DOWN'if direction=='LOWER'else direction,'mb_inner_ci_source':'synthetic-actual-inner-layers'}
    if ci in (0xB8,0xBB,0xBD,0xBE,0xBF):
        x.update(mb_frame='CONTROL',mb_requested_baud=dict(zip((0xB8,0xBB,0xBD,0xBE,0xBF),MB.BAUDS))[ci])
    assert registry.validate_parameters('m_bus',x)['status']=='VALID',registry.validate_parameters('m_bus',x)
    assert registry.validate_parameters('m_bus',{**x,'mb_ci_direction':'UP'if direction!='UP'else'DOWN'})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_tpl_header':'LONG'if header!='LONG'else'NONE'})['status']=='INVALID'
    if direction!='LOWER':assert registry.validate_parameters('m_bus',{**x,'mb_direction':'UP'if direction=='DOWN'else'DOWN'})['status']=='INVALID'


@pytest.mark.parametrize('ci',MB.FORBIDDEN_CI)
def test_m_bus_does_not_import_wireless_ell_or_mbal_ci_from_a_shared_table(ci):
    assert registry.validate_parameters('m_bus',{**MBUS_ACTUAL,'mb_ci':ci})['status']=='INVALID'


def test_m_bus_primary_secondary_reply_and_broadcast_addresses_do_not_copy_request_or_example_ids():
    x={**MBUS_ACTUAL,'mb_addressing':'PRIMARY','mb_primary_address':17,'mb_request_address':17,'mb_reply_address':17,
      'mb_reply_address_source':'synthetic-commissioned-peer'}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_request_address':18})['status']=='INVALID'
    for reply in (0,253,254,255):assert registry.validate_parameters('m_bus',{**x,'mb_reply_address':reply})['status']=='INVALID'
    x.update(mb_addressing='SECONDARY',mb_request_address=253,mb_secondary_id='00012345',mb_manufacturer_id='ABC',mb_version=3,mb_device_type=7)
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_reply_address':253})['status']=='INVALID'
    for value in ('12345','123456789','abcdefgh','00012F45'):
        assert registry.validate_parameters('m_bus',{**x,'mb_secondary_id':value})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_manufacturer_id':'abc'})['status']=='INVALID'
    x.update(mb_addressing='BROADCAST_NO_REPLY',mb_request_address=255,mb_reply_expected=False)
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_reply_expected':True})['status']=='INVALID'
    x.update(mb_addressing='TEST_FE',mb_request_address=254,mb_phase='DATA',mb_slave_count=2)
    assert registry.validate_parameters('m_bus',x)['status']=='INVALID'
    x['mb_phase']='SEARCH';assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    for value in (251,252):assert registry.validate_parameters('m_bus',{**MBUS_ACTUAL,'mb_request_address':value})['status']=='INVALID'
    x={**MBUS_ACTUAL,'mb_is_adapter':False,'mb_secondary_change':'NO_CHANGE'}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_secondary_change':'ADAPTER_IDENT'})['status']=='INVALID'
    x.update(mb_is_adapter=True,mb_secondary_change='ADAPTER_IDENT')
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    for part in ('MANUFACTURER','VERSION'):
        assert registry.validate_parameters('m_bus',{**x,'mb_secondary_change':part})['status']=='INVALID'


@pytest.mark.parametrize('user', [0,1,29,252])
def test_m_bus_long_frame_wire_length_parity_and_serialization_are_not_application_payload(user):
    x={**m_bus_rate(2400),'mb_frame':'LONG','mb_user_area_octets':user,'mb_length_field':user+3,
      'mb_wire_octets':user+9,'mb_wire_bits':11*(user+9),'mb_serialization_ms':11*(user+9)*1000/2400}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    for patch in ({'mb_length_field':user+4},{'mb_wire_octets':user+8},{'mb_wire_bits':8*(user+9)},
                  {'mb_serialization_ms':8*(user+9)*1000/2400},{'payload_bytes':user+1}):
        assert registry.validate_parameters('m_bus',{**x,**patch})['status']=='INVALID'
    x={**m_bus_rate(300),'mb_ci':0xBD,'mb_ci_direction':'DOWN','mb_tpl_header':'NONE',
      'mb_frame':'CONTROL','mb_length_field':3,'mb_user_area_octets':0,'mb_wire_octets':9,'mb_requested_baud':9600}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_requested_baud':300})['status']=='INVALID'
    assert registry.validate_parameters('m_bus',{**x,'mb_wire_octets':5})['status']=='INVALID'


@pytest.mark.parametrize('key,value',[
 ('mb_chip_bus_v',42.001),('mb_chip_bus_v',10.799),('mb_chip_bat_v',2.499),('mb_chip_bat_v',3.801),
 ('mb_chip_stc_v',3.499),('mb_chip_ridd_kohm',12.999),('mb_chip_ridd_kohm',80.001),
 ('mb_chip_ris_ohm',99.999),('mb_chip_temperature_c',-25.001),('mb_chip_temperature_c',85.001),
 ('mb_chip_modulation_ma',11.499),('mb_chip_modulation_ma',19.501),('mb_role','MASTER')])
def test_m_bus_slave_chip_has_its_own_operating_envelope_not_absmax_or_other_bus_voltage(key,value):
    x={**m_bus_rate(9600,38400,9600),'mb_hardware':MB.CHIP,'mb_role':'SLAVE','mb_chip_direction':'RECEIVE_BUS',
      'mb_measurement_source':'synthetic-chip-fixture','mb_chip_bus_v':10.8,'mb_chip_bat_v':2.5,'mb_chip_stc_v':4,
      'mb_chip_ridd_kohm':30,'mb_chip_ris_ohm':100,'mb_chip_modulation_ma':15,'mb_chip_temperature_c':25}
    assert registry.validate_parameters('m_bus',x)['status']=='VALID'
    assert registry.validate_parameters('m_bus',{**x,key:value})['status']=='INVALID'


@pytest.mark.parametrize('key,value',[
 ('mb_char_parity','ODD'),('mb_char_data_bits',7),('mb_char_parity_bits',0),('mb_char_stop_bits',2),
 ('mb_char_bits',10),('mb_bit_order','MSB_FIRST'),('mb_master_repetitions',1),('mb_no_load_slew_v_us',75)])
def test_m_bus_character_repetitions_and_unloaded_slope_are_independently_qualified(key,value):
    x={**MBUS_ACTUAL,'mb_load_scope':'NO_LOAD','mb_measurement_source':'synthetic-empty-line',key:value}
    assert registry.validate_parameters('m_bus',x)['status']=='INVALID'


@pytest.mark.parametrize('key', ['mb_master_max_baud','mb_slave_max_baud','mb_rx_baud','mb_tx_baud','mb_rate_set'])
def test_m_bus_actual_baud_requires_both_endpoint_capabilities_and_transaction_context(key):
    x=m_bus_rate(2400)
    assert registry.validate_parameters('m_bus',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'


def test_m_bus_confirmed_native_addresses_and_rate_survive_rejected_wireless_ci_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x={**m_bus_rate(2400),'mb_ci':0x72,'mb_ci_direction':'UP','mb_direction':'UP','mb_tpl_header':'LONG',
      'mb_primary_address':17,'mb_reply_address':17,'mb_reply_address_source':'synthetic-actual-peer'}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    p={'technology':'m_bus','technology_parameters':{'m_bus':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(p)
    assert service.get()['parameters']==p
    bad=deepcopy(p);bad['technology_parameters']['m_bus']['values']['mb_ci']=0x7A
    bad['technology_parameters']['m_bus']['provenance']['mb_ci']['value']=0x7A
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==p
    assert registry.profile('m_bus')['capacity_evidence']['status']=='MODEL_MISSING'


from backend.communication.technologies import lvds as LV

LVDS_ACTUAL={**{'lv_'+key:'synthetic-actual-'+key for key in LV.REQUIRED
    if key not in ('edition','electrical','hardware','topology','purpose')},
    'lv_edition':LV.EDITION,'lv_electrical':LV.REV_A,'lv_hardware':'REGISTERED_HARDWARE',
    'lv_registered_source':'synthetic-qualified-other-hardware','lv_topology':'POINT_TO_POINT',
    'lv_purpose':'LEVEL_OR_INTERRUPT'}


def lvds_standard(electrical=LV.REV_A):
    ml=electrical==LV.MLVDS
    return {**LVDS_ACTUAL,'lv_electrical':electrical,'lv_load_scope':'STANDARD_FIXTURE',
      'lv_power_state':'ACTIVE','lv_receiver_type':'MLVDS_TYPE1'if ml else'LVDS',
      'lv_topology':'MULTIPOINT'if ml else'POINT_TO_POINT','lv_arbitration_source':'synthetic-arbiter',
      'lv_measurement_source':'synthetic-fixture','lv_transmitters':2 if ml else 1,'lv_receivers':2 if ml else 1,
      'lv_fixture_load_ohm':50 if ml else 100,'lv_effective_load_ohm':50 if ml else 100,
      'lv_tx_diff_abs_mv':550 if ml else 350,'lv_tx_loop_ma':11 if ml else 3.5,
      'lv_tx_common_v':1.2,'lv_tx_common_pp_mv':100,'lv_tx_diff_change_mv':20,'lv_tx_common_change_mv':20,
      'lv_transition_ns':1 if ml else .5,'lv_ground_shift_v':0,'lv_rx_threshold_abs_mv':50,
      'lv_rx_input_plus_v':1.375,'lv_rx_input_minus_v':1.025,'lv_input_leakage_abs_ua':10,
      **({'lv_diff_input_leakage_abs_ua':4 if ml else 6}if electrical!=LV.LVDS else{})}


def lvds_chip():
    return {**LVDS_ACTUAL,'lv_hardware':LV.CHIP,'lv_load_scope':'DATASHEET_AC','lv_power_state':'ACTIVE',
      'lv_input_fault':'DATA','lv_coupling':'DC','lv_measurement_source':'synthetic-ac-fixture',
      'lv_receiver_type':'LVDS','lv_rate_assurance':'DATASHEET_REFERENCE','lv_lane_bps':400_000_000,
      'lv_purpose':'DATA_STREAM','lv_encoding':'RAW_BITS','lv_clocking':'DIRECT','lv_data_lanes':4,
      'lv_clock_lanes':0,'lv_clock_same_chip':True,'lv_serializer_source':'synthetic-bitstream-interface',
      'lv_aggregate_bps':1_600_000_000,'lv_ui_ns':2.5,'lv_effective_load_ohm':100,'lv_ac_load_pf':15,
      'lv_tx_loop_ma':3.1,'lv_tx_diff_abs_mv':310,'lv_tx_common_v':1.17,'lv_tx_diff_change_mv':35,
      'lv_tx_common_change_mv':25,'lv_tx_supply_v':3.3,'lv_rx_supply_v':3.3,'lv_ground_shift_v':0,
      'lv_rx_diff_abs_mv':310,'lv_rx_common_v':1.17,'lv_rx_common_noise_v':0,'lv_rx_input_plus_v':1.325,'lv_rx_input_minus_v':1.015,
      'lv_tx_tphld_ns':1.7,'lv_tx_tplhd_ns':1.7,'lv_rx_tphld_ns':2.7,'lv_rx_tplhd_ns':2.7,
      'lv_tx_pulse_skew_ns':.4,'lv_rx_pulse_skew_ns':.4,'lv_reference_switch_mhz':200}


def test_lvds_has_no_universal_can_clock_payload_framing_or_capacity_default():
    p=registry.profile('lvds');f={v['key']:v for v in registry.parameter_fields('lvds')}
    assert p['domain']=='generic_networking'and p['default_stack']==['lvds']
    assert p['max_payload_bytes']is None and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('lvds')['values']=={}
    assert registry.validate_parameters('lvds',LVDS_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('lvds',{})['status']=='UNVERIFIED'
    assert not set(LV.REMOVED)&f.keys()
    for key in ('payload_bytes','lv_lane_bps','lv_aggregate_bps','lv_data_lanes','lv_tx_diff_abs_mv',
                'lv_rx_diff_abs_mv','lv_topology','lv_electrical','lv_input_fault','lv_capacity_confirmed'):
        assert 'default'not in f[key]and'conditional_defaults'not in f[key]
    for patch in ({'bitrate':3_000_000_000},{'bitrate_bps':3_000_000_000},{'qos_priority':7},
                  {'local_timing_evidence':{'slave_address':32}}):
        assert registry.validate_parameters('lvds',{**LVDS_ACTUAL,**patch})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('lvds'),ids=lambda f:'lvds/'+f['key'])
def test_each_lvds_field_has_independent_type_source_and_qualified_bounds(field):
    key=field['key'];kind=field['type'];x={**LVDS_ACTUAL}
    bad={'number':True,'boolean':'false','text':42,'select':'not-an-option'}.get(kind)
    if bad is not None:assert registry.validate_parameters('lvds',{**x,key:bad})['status']=='INVALID'
    for bound,offset in [('min',-1),('max',1)]:
        if bound in field:assert registry.validate_parameters('lvds',{**x,key:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):assert registry.validate_parameters('lvds',{**x,key:field.get('min',0)+.5})['status']=='INVALID'


@pytest.mark.parametrize('electrical',[LV.LVDS,LV.REV_A,LV.MLVDS])
def test_lvds_each_reference_fixture_has_independent_output_load_and_receiver_limits(electrical):
    x=lvds_standard(electrical);ml=electrical==LV.MLVDS
    assert registry.validate_parameters('lvds',x)['status']=='VALID',registry.validate_parameters('lvds',x)
    patches=[{'lv_fixture_load_ohm':100 if ml else 50},{'lv_effective_load_ohm':100 if ml else 50},
      {'lv_transition_ns':.999 if ml else .259},{'lv_tx_common_pp_mv':151},
      {'lv_tx_diff_change_mv':51},{'lv_tx_common_change_mv':51},{'lv_ground_shift_v':1.001},
      {'lv_input_leakage_abs_ua':20.001},{'lv_receiver_type':'LVDS'if ml else'MLVDS_TYPE1'},
      {'lv_rx_threshold_abs_mv':50.001 if ml else 100.001}]
    for pin in ('lv_rx_input_plus_v','lv_rx_input_minus_v'):
        patches.extend([{pin:-1.401 if ml else-.001},{pin:3.801 if ml else 2.401}])
    for vod in ([479.999,650.001]if ml else[246.999,454.001]):
        patches.append({'lv_tx_diff_abs_mv':vod,'lv_tx_loop_ma':vod/x['lv_effective_load_ohm']})
    for vos in ([.2999,2.1001]if ml else[1.1249,1.3751]):patches.append({'lv_tx_common_v':vos})
    if electrical!=LV.LVDS:patches.append({'lv_diff_input_leakage_abs_ua':4.001 if ml else 6.001})
    for patch in patches:assert registry.validate_parameters('lvds',{**x,**patch})['status']=='INVALID',patch


@pytest.mark.parametrize('key,value',[
 ('lv_tx_diff_change_mv',35.001),('lv_tx_common_change_mv',25.001),('lv_effective_load_ohm',90),
 ('lv_ac_load_pf',15.001),('lv_tx_tphld_ns',.499),('lv_tx_tplhd_ns',1.701),
 ('lv_rx_tphld_ns',1.199),('lv_rx_tplhd_ns',2.701),('lv_tx_pulse_skew_ns',.401),
 ('lv_rx_pulse_skew_ns',.401),('lv_tx_supply_v',2.999),('lv_rx_supply_v',3.601),
 ('lv_tx_temperature_c',-40.001),('lv_rx_temperature_c',85.001),('lv_reference_switch_mhz',250),
 ('lv_coupling','AC'),('lv_electrical',LV.MLVDS),('lv_data_lanes',5),('lv_lane_bps',400_000_001),
 ('lv_rx_diff_abs_mv',199.999),('lv_rx_diff_abs_mv',800.001),('lv_rx_input_plus_v',2.401)])
def test_lvds_exact_device_guarantees_are_not_typical_absolute_maxima_or_mlvds(key,value):
    x=lvds_chip();assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,key:value})['status']=='INVALID'


@pytest.mark.parametrize('amplitude,low,high',[(200,.1,2.3),(400,.2,2.2),(800,.4,2.0)])
def test_lvds_receiver_common_mode_shrinks_with_actual_differential_amplitude(amplitude,low,high):
    x=lvds_chip();x.update(lv_rx_diff_abs_mv=amplitude)
    for v in (low,high):
        p={**x,'lv_rx_common_v':v,'lv_rx_common_noise_v':v-x['lv_tx_common_v'],
          'lv_rx_input_plus_v':round(v+amplitude/2000,9),'lv_rx_input_minus_v':round(v-amplitude/2000,9)}
        assert registry.validate_parameters('lvds',p)['status']=='VALID',registry.validate_parameters('lvds',p)
    for v in (low-.0001,high+.0001):
        p={**x,'lv_rx_common_v':v,'lv_rx_common_noise_v':v-x['lv_tx_common_v']}
        assert registry.validate_parameters('lvds',p)['status']=='INVALID'


def test_lvds_midline_parallel_terminations_and_multipoint_do_not_use_single_driver_defaults():
    x={**LVDS_ACTUAL,'lv_terminations':2,'lv_end1_ohm':100,'lv_end2_ohm':100,'lv_effective_load_ohm':50,
      'lv_driver_position':'MID','lv_alternate_loading_source':'synthetic-double-load-design'}
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_effective_load_ohm':200})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_end2_ohm'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_alternate_loading_source'})['status']=='UNVERIFIED'
    x={**LVDS_ACTUAL,'lv_topology':'MULTIDROP','lv_transmitters':1,'lv_receivers':32,'lv_full_load_source':'synthetic-full-load'}
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_electrical':LV.LVDS})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{**x,'lv_transmitters':2})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_full_load_source'})['status']=='UNVERIFIED'
    x={**LVDS_ACTUAL,'lv_electrical':LV.MLVDS,'lv_topology':'MULTIPOINT','lv_receiver_type':'MLVDS_TYPE2',
      'lv_wired_or':True,'lv_asserted_logic':'HIGH','lv_failsafe':'TYPE2_LOW','lv_arbitration_source':'synthetic-owner'}
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    for patch in ({'lv_receiver_type':'MLVDS_TYPE1'},{'lv_asserted_logic':'LOW'},{'lv_electrical':LV.REV_A}):
        assert registry.validate_parameters('lvds',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_arbitration_source'})['status']=='UNVERIFIED'
    x={**LVDS_ACTUAL,'lv_electrical':LV.LVDS,'lv_diff_input_leakage_abs_ua':0}
    assert registry.validate_parameters('lvds',x)['status']=='UNVERIFIED'


def test_lvds_serialized_word_clock_bit_clock_ui_and_aggregate_are_independent():
    x={**LVDS_ACTUAL,'lv_purpose':'DATA_STREAM','lv_encoding':'START_STOP_2','lv_clocking':'FORWARDED_WORD',
      'lv_serializer_source':'synthetic-18bit-serializer','lv_word_clock_hz':10_000_000,'lv_word_data_bits':16,
      'lv_word_wire_bits':18,'lv_lane_bps':180_000_000,'lv_data_lanes':3,'lv_clock_lanes':1,
      'lv_ui_ns':1_000_000_000/180_000_000,'lv_aggregate_bps':540_000_000}
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    for patch in ({'lv_lane_bps':10_000_000},{'lv_aggregate_bps':720_000_000},{'lv_ui_ns':0},
                  {'lv_word_wire_bits':16},{'lv_encoding':'8B10B'}):
        assert registry.validate_parameters('lvds',{**x,**patch})['status']=='INVALID'
    x.update(lv_encoding='8B10B',lv_word_data_bits=8,lv_word_wire_bits=10,lv_lane_bps=100_000_000,
      lv_ui_ns=10,lv_aggregate_bps=300_000_000)
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_word_data_bits':10})['status']=='INVALID'
    x.update(lv_coupling='AC',lv_dc_balanced=True,lv_ac_balance_source='synthetic-startup-idle-RC-proof')
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_dc_balanced':False})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_ac_balance_source'})['status']=='UNVERIFIED'


def test_lvds_chip_channels_reference_rate_and_failsafe_require_their_own_real_conditions():
    x=lvds_chip();x.update(lv_data_lanes=3,lv_clock_lanes=1,lv_aggregate_bps=1_200_000_000)
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_data_lanes':4,'lv_aggregate_bps':1_600_000_000})['status']=='INVALID'
    x.update(lv_clock_same_chip=False)
    assert registry.validate_parameters('lvds',x)['status']=='UNVERIFIED'
    x['lv_external_clock_source']='synthetic-independent-clock-chip'
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    x=lvds_chip();x.update(lv_lane_bps=450_000_000,lv_aggregate_bps=1_800_000_000,lv_ui_ns=1e9/450_000_000)
    assert registry.validate_parameters('lvds',x)['status']=='INVALID'
    x.update(lv_rate_assurance='MEASURED_REGISTERED');x.pop('lv_registered_source')
    assert registry.validate_parameters('lvds',x)['status']=='UNVERIFIED'
    x['lv_registered_source']='synthetic-loaded-higher-rate-test'
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    x=lvds_chip();x.update(lv_input_fault='SHORT',lv_failsafe='DEVICE_PROVEN',
      lv_external_fault_common_v=0,lv_failsafe_source='synthetic-fault-test')
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_external_fault_common_v':1.2})['status']=='INVALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!='lv_external_fault_common_v'})['status']=='UNVERIFIED'
    x.update(lv_input_fault='TERMINATED_FLOATING',lv_rx_noise_abs_mv=10)
    assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{**x,'lv_rx_noise_abs_mv':10.001})['status']=='INVALID'


@pytest.mark.parametrize('derived,value,missing',[
 ('lv_ui_ns',2.5,'lv_lane_bps'),('lv_aggregate_bps',1_600_000_000,'lv_data_lanes'),
 ('lv_tx_diff_abs_mv',310,'lv_effective_load_ohm'),('lv_rx_common_v',1.17,'lv_rx_diff_abs_mv'),
 ('lv_tx_diff_abs_mv',310,'lv_measurement_source'),('lv_tx_diff_abs_mv',310,'lv_load_scope'),
 ('lv_tx_common_v',1.17,'lv_power_state'),('lv_lane_bps',400_000_000,'lv_rate_assurance'),
 ('lv_rx_common_v',1.17,'lv_rx_common_noise_v')])
def test_lvds_derived_or_measured_values_require_actual_inputs_and_test_scope(derived,value,missing):
    x={**lvds_chip(),derived:value};assert registry.validate_parameters('lvds',x)['status']=='VALID'
    assert registry.validate_parameters('lvds',{k:v for k,v in x.items()if k!=missing})['status']=='UNVERIFIED'


def test_lvds_conditional_proposals_are_design_references_not_operating_clock_measurements():
    f={v['key']:v for v in registry.parameter_fields('lvds')}
    assert {p['value']for p in f['lv_design_term_ohm']['conditional_defaults']}=={100}
    fixtures={p['when']['lv_electrical']:p['value']for p in f['lv_fixture_load_ohm']['conditional_defaults']}
    assert fixtures=={LV.LVDS:100,LV.REV_A:100,LV.MLVDS:50}
    assert f['lv_design_supply_v']['conditional_defaults'][0]['value']==3.3
    assert f['lv_reference_switch_mhz']['conditional_defaults'][0]['value']==200
    assert f['lv_word_data_bits']['conditional_defaults'][0]['value']==8
    assert f['lv_word_wire_bits']['conditional_defaults'][0]['value']==10
    for field in f.values():
        for proposal in field.get('conditional_defaults',[]):
            assert proposal['when']['lv_edition']==LV.EDITION and proposal['source']in LV.SOURCES
            assert proposal['source_revision']==LV.SOURCES[proposal['source']]
    x={**LVDS_ACTUAL,'lv_edition':'REGISTERED_EDITION','lv_lane_bps':450_000_000}
    assert registry.validate_parameters('lvds',x)['status']=='UNVERIFIED'


def test_lvds_confirmed_storage_survives_rejected_foreign_clock_or_wrong_ui():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x=lvds_chip();group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    p={'technology':'lvds','technology_parameters':{'lvds':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(p)
    assert service.get()['parameters']==p
    bad=deepcopy(p);bad['technology_parameters']['lvds']['values']['lv_ui_ns']=0
    bad['technology_parameters']['lvds']['provenance']['lv_ui_ns']['value']=0
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==p
    assert registry.profile('lvds')['capacity_evidence']['status']=='MODEL_MISSING'


from backend.communication.technologies.knx_rf import LEGACY as KNX_RF_EDITION
from backend.communication.technologies.lin import OLD as LIN_EDITION, protected_id
from backend.communication.technologies.lonworks import OLD as LON_EDITION, G as LON_GUIDE, X as LON_XCVR, R as LON_ROUTER

from backend.communication.technologies.lorawan import OLD as LORA_L2, REGIONAL as LORA_RP
from backend.communication.technologies.lte_m import EDITION as LTE_M_EDITION, BANDS as LTE_M_BANDS, TDD as LTE_M_TDD, CARRIER_PRBS as LTE_M_PRBS

LTE_M_ACTUAL={**{'ltm_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','binding_source','network_source','regulatory_source','physical_source','scheduler_source',
     'mac_rlc_source','rrc_nas_source','application_source','security_source','capacity_source','acceptance_source')},
    'ltm_edition':LTE_M_EDITION,'ltm_category':'M1','ltm_role':'UE','ltm_direction':'UPLINK',
    'ltm_duplex':'FDD','ltm_ue_duplex':'HD_FDD_TYPE_B','ltm_ce_mode':'A'}


def lte_m_actual(band=3,category='M1',direction='UPLINK',bw=20):
    duplex,ul,dl,_=LTE_M_BANDS[band]
    return {**LTE_M_ACTUAL,'ltm_band':band,'ltm_category':category,'ltm_direction':direction,'ltm_duplex':duplex,
      'ltm_ue_duplex':'TDD'if duplex=='TDD'else'HD_FDD_TYPE_B','ltm_carrier_bandwidth_mhz':bw,
      'ltm_carrier_prbs':LTE_M_PRBS[bw],'ltm_carrier_mhz':sum(ul if direction=='UPLINK'else dl)/2,
      **({'ltm_carrier20_block':'LOW','ltm_carrier_mhz':720 if band==28 else 675}if band in(28,71)and bw==20 and direction=='UPLINK'else{}),
      **({'ltm_power_profile_source':'synthetic-band66-profile'}if band==66 else{}),
      **({'ltm_band74_capability_source':'synthetic-band11-and21-compliance'}if band==74 else{}),
      **({'ltm_tdd_assignment':0,'ltm_tdd_special_source':'synthetic-actual-special-subframe'}if duplex=='TDD'else{})}


def test_lte_m_category_peaks_are_not_a_can_clock_or_payload_default_or_capacity_proof():
    p=registry.profile('lte_m');f={v['key']:v for v in registry.parameter_fields('lte_m')}
    assert p['domain']=='generic_networking'and p['default_stack']==['lte_m']
    assert p['max_payload_bytes']is None and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('lte_m')['values']=={}
    assert registry.validate_parameters('lte_m',LTE_M_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{})['status']=='UNVERIFIED'
    for key in ('bitrate','queue_size','queue_policy','qos_priority','sync_method','gateway_maximum_throughput'):
        assert key not in f
    for key in ('payload_bytes','ltm_band','ltm_category','ltm_allocated_prbs','ltm_output_power_dbm',
                'ltm_frequency_error_abs_ppm','ltm_ue_id','ltm_cell_id','ltm_subscription_key_ref','ltm_capacity_confirmed'):
        assert 'default'not in f[key]and'conditional_defaults'not in f[key]
    assert registry.validate_parameters('lte_m',{**LTE_M_ACTUAL,'local_timing_evidence':{'slave_address':32}})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('lte_m'),ids=lambda f:'lte_m/'+f['key'])
def test_each_lte_m_field_has_its_own_scalar_type_and_source_qualified_bounds(field):
    x={**LTE_M_ACTUAL};key=field['key'];kind=field['type']
    bad={'number':'not-a-number','boolean':'false','text':42,'select':'not-an-option'}.get(kind)
    if bad is not None:assert registry.validate_parameters('lte_m',{**x,key:bad})['status']=='INVALID'
    for bound,offset in [('min',-1),('max',1)]:
        if bound in field:assert registry.validate_parameters('lte_m',{**x,key:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):assert registry.validate_parameters('lte_m',{**x,key:field.get('min',0)+.5})['status']=='INVALID'


@pytest.mark.parametrize('band',list(LTE_M_BANDS))
@pytest.mark.parametrize('category',['M1','M2'])
def test_lte_m_each_band_has_independent_duplex_carrier_and_category_limits(band,category):
    duplex,ul,dl,widths=LTE_M_BANDS[band]
    for width in widths:
        x=lte_m_actual(band,category,bw=width)
        if band==74:x['ltm_band74_capability_source']='synthetic-band11-and21-compliance'
        maximum=1.4 if category=='M1'else min(5,max(widths))
        x.update(ltm_ue_max_bandwidth_mhz=maximum,ltm_allocated_bandwidth_mhz=min(maximum,width))
        assert registry.validate_parameters('lte_m',x)['status']=='VALID',registry.validate_parameters('lte_m',x)
        for patch in ({'ltm_duplex':'TDD'if duplex=='FDD'else'FDD'},
                      {'ltm_ue_max_bandwidth_mhz':maximum+.1},{'ltm_allocated_bandwidth_mhz':maximum+.1},
                      {'ltm_carrier_prbs':LTE_M_PRBS[width]+1}):
            assert registry.validate_parameters('lte_m',{**x,**patch})['status']=='INVALID'
        for direction,bounds in [('UPLINK',ul),('DOWNLINK',dl)]:
            assert registry.validate_parameters('lte_m',{**x,'ltm_direction':direction,'ltm_carrier_mhz':bounds[0]-.1})['status']=='INVALID'
        for wrong in set(LTE_M_PRBS)-set(widths):
            assert registry.validate_parameters('lte_m',{**x,'ltm_carrier_bandwidth_mhz':wrong})['status']=='INVALID'


@pytest.mark.parametrize('category',['M1','M2'])
@pytest.mark.parametrize('direction',['UPLINK','DOWNLINK'])
def test_lte_m_tbs_optional_features_are_not_constant_application_rates(category,direction):
    for flag in (False,True):
        dl,soft,ul,l2=(1000,25344,1000,20000)if category=='M1'and not flag else(1736,43008,2984,40000)if category=='M1'else(4008,73152,6968,100000)
        x={**lte_m_actual(category=category,direction=direction),'ltm_dl_max_tbs_r17':flag,'ltm_ul_max_tbs_r14':flag,
           'ltm_dl_tb_limit_bits':dl,'ltm_dl_soft_buffer_bits':soft,'ltm_ul_tb_limit_bits':ul,'ltm_layer2_capability_bytes':l2}
        x['ltm_actual_tb_bits']=dl if direction=='DOWNLINK'else ul
        assert registry.validate_parameters('lte_m',x)['status']=='VALID'
        for key in ('ltm_dl_tb_limit_bits','ltm_dl_soft_buffer_bits','ltm_ul_tb_limit_bits','ltm_layer2_capability_bytes','ltm_actual_tb_bits'):
            assert registry.validate_parameters('lte_m',{**x,key:x[key]+1})['status']=='INVALID'
        if category=='M1'and flag:
            assert registry.validate_parameters('lte_m',{**x,'ltm_ce_mode':'B','ltm_ce_b_supported':True})['status']=='INVALID'
            # Device optional capabilities can still exist while ModeB uses a basic TB.
            assert registry.validate_parameters('lte_m',{**x,'ltm_actual_tb_bits':1000,'ltm_ce_mode':'B','ltm_ce_b_supported':True})['status']=='VALID'


def test_lte_m_mode_b_ul_narrowband_is_not_m2_mode_a_or_full_cell_bandwidth():
    x={**lte_m_actual(category='M2'),'ltm_ce_mode':'B','ltm_ce_b_supported':True,'ltm_allocated_bandwidth_mhz':1.4,'ltm_allocated_prbs':6}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_allocated_bandwidth_mhz':5,'ltm_allocated_prbs':25})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_ce_b_supported':False})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_ce_a_supported':False})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_ce_mode':'A','ltm_allocated_bandwidth_mhz':5,'ltm_allocated_prbs':24,
      'ltm_grant_profile':'WIDE_PUSCH_5_C_RNTI','ltm_rrc_state':'CONNECTED','ltm_service':'UNICAST','ltm_wideband_r14':True})['status']=='VALID'


def test_lte_m_64qam_is_optional_unicast_nonrepeated_connected_downlink_only():
    x={**lte_m_actual(direction='DOWNLINK'),'ltm_modulation':'64QAM','ltm_dl_64qam_r15':True,
       'ltm_rrc_state':'CONNECTED','ltm_service':'UNICAST','ltm_repetitions':1}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    for patch in ({'ltm_direction':'UPLINK'},{'ltm_dl_64qam_r15':False},{'ltm_rrc_state':'IDLE'},
                  {'ltm_service':'REGISTERED_SERVICE','ltm_registered_source':'synthetic-profile'},
                  {'ltm_ce_mode':'B','ltm_ce_b_supported':True},{'ltm_repetitions':2},{'ltm_modulation':'256QAM'}):
        assert registry.validate_parameters('lte_m',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{k:v for k,v in x.items()if k!='ltm_repetitions'})['status']=='UNVERIFIED'


@pytest.mark.parametrize('assignment',list(LTE_M_TDD))
def test_lte_m_tdd_assignment_uses_own_ten_subframe_pattern_and_switch_period(assignment):
    pattern,period=LTE_M_TDD[assignment]
    x={**lte_m_actual(band=40,bw=5),'ltm_tdd_assignment':assignment,'ltm_tdd_pattern':pattern,'ltm_tdd_switch_ms':period}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_tdd_pattern':'DDDDDDDDDD'})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_tdd_switch_ms':10 if period==5 else 5})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{k:v for k,v in x.items()if k!='ltm_tdd_special_source'})['status']=='UNVERIFIED'


def test_lte_m_rf_footnotes_are_not_optional_without_actual_qualified_evidence():
    x=lte_m_actual(band=28,bw=20);x.pop('ltm_carrier20_block')
    assert registry.validate_parameters('lte_m',x)['status']=='UNVERIFIED'
    assert registry.validate_parameters('lte_m',{**x,'ltm_carrier20_block':'LOW','ltm_carrier_mhz':720})['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_carrier20_block':'LOW','ltm_carrier_mhz':730})['status']=='INVALID'
    x=lte_m_actual(band=71,bw=20)
    assert registry.validate_parameters('lte_m',{**x,'ltm_carrier20_block':'HIGH','ltm_carrier_mhz':685})['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_carrier20_block':'HIGH','ltm_carrier_mhz':680})['status']=='INVALID'
    x={**lte_m_actual(band=66,direction='DOWNLINK'),'ltm_carrier_mhz':2185,'ltm_power_profile_source':'synthetic-band66-profile'}
    assert registry.validate_parameters('lte_m',x)['status']=='UNVERIFIED'
    assert registry.validate_parameters('lte_m',{**x,'ltm_carrier_aggregation_source':'synthetic-actual-CA-proof'})['status']=='VALID'
    x=lte_m_actual(band=74);x.pop('ltm_band74_capability_source')
    assert registry.validate_parameters('lte_m',x)['status']=='UNVERIFIED'


@pytest.mark.parametrize('duplex,frequency,duration,limit',[
 ('HD_FDD_TYPE_B',900,64,.1),('HD_FDD_TYPE_B',900,64.001,.2),('HD_FDD_TYPE_B',1000,100,.2),
 ('HD_FDD_TYPE_B',1000.001,100,.1),('FD_FDD',900,100,.1),('TDD',2301,100,.1)])
def test_lte_m_measured_frequency_error_is_duration_frequency_and_duplex_qualified(duplex,frequency,duration,limit):
    x={**LTE_M_ACTUAL,'ltm_band':8 if frequency<=1000 else 40 if duplex=='TDD'else 3,
      'ltm_duplex':'TDD'if duplex=='TDD'else'FDD','ltm_ue_duplex':duplex,'ltm_direction':'DOWNLINK'if frequency<=1000 else'UPLINK',
      'ltm_continuous_ul_ms':duration,'ltm_frequency_error_abs_ppm':limit,'ltm_frequency_error_source':'synthetic-measured-carrier-comparison',
      'ltm_carrier_bandwidth_mhz':5,'ltm_carrier_mhz':frequency,
      **({'ltm_tdd_assignment':0,'ltm_tdd_special_source':'synthetic-special-subframe'}if duplex=='TDD'else{})}
    # Synthetic boundary frequencies isolate the error rule; separate band
    # tests verify actual operating intervals. This is not a deployable RF setup.
    findings=registry.validate_parameters('lte_m',x)['findings']
    assert not any(v['code']=='TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH'and'ltm_frequency_error_abs_ppm'in v['message']for v in findings)
    result=registry.validate_parameters('lte_m',{**x,'ltm_frequency_error_abs_ppm':limit+.000001})
    assert any('ltm_frequency_error_abs_ppm'in v['message']for v in result['findings'])


def test_lte_m_standard_proposals_are_native_conditioned_and_preserve_unknown_actuals():
    f={v['key']:v for v in registry.parameter_fields('lte_m')}
    def proposals(key,**context):
        return [v['value']for v in f[key].get('conditional_defaults',[])if all(v['when'].get('ltm_'+k)==value for k,value in context.items())]
    assert proposals('ltm_carrier_bandwidth_mhz',band=1)==[5]
    assert proposals('ltm_carrier_bandwidth_mhz',band=3)==[1.4]
    assert proposals('ltm_carrier_bandwidth_mhz',band=106)==[1.4]
    assert proposals('ltm_ue_max_bandwidth_mhz',band=106,category='M2')==[3]
    assert proposals('ltm_ue_max_bandwidth_mhz',band=3,category='M2')==[5]
    assert proposals('ltm_dl_tb_limit_bits',category='M1',dl_max_tbs_r17=False)==[1000]
    assert proposals('ltm_dl_tb_limit_bits',category='M1',dl_max_tbs_r17=True)==[1736]
    assert proposals('ltm_layer2_capability_bytes',category='M1',ul_max_tbs_r14=True)==[40000]
    assert proposals('ltm_nominal_max_power_dbm',band=66)==[]
    for key in ('ltm_psm_timer_encoding','ltm_edrx_timer_encoding','ltm_ce_b_supported','ltm_dl_64qam_r15','ltm_output_power_dbm'):
        assert 'default'not in f[key]and'conditional_defaults'not in f[key]


@pytest.mark.parametrize('key,value,missing',[
 ('ltm_ue_max_bandwidth_mhz',1.4,'ltm_band'),('ltm_ul_tb_limit_bits',1000,'ltm_ul_max_tbs_r14'),
 ('ltm_dl_tb_limit_bits',1000,'ltm_dl_max_tbs_r17'),('ltm_layer2_capability_bytes',20000,'ltm_ul_max_tbs_r14'),
 ('ltm_dl_soft_buffer_bits',25344,'ltm_dl_max_tbs_r17'),('ltm_carrier_prbs',100,'ltm_carrier_bandwidth_mhz'),
 ('ltm_wideband_prbs',24,'ltm_carrier_prbs'),('ltm_ul_symbols_per_slot',7,'ltm_cyclic_prefix'),
 ('ltm_nominal_max_power_dbm',23,'ltm_power_class'),('ltm_frequency_error_abs_ppm',.1,'ltm_carrier_mhz'),
 ('ltm_psm_enabled',True,'ltm_psm_timer_encoding'),('ltm_edrx_enabled',True,'ltm_edrx_timer_encoding')])
def test_lte_m_dependent_limits_and_measurements_require_their_actual_selectors(key,value,missing):
    x={**lte_m_actual(),'ltm_cyclic_prefix':'NORMAL','ltm_power_class':'3','ltm_continuous_ul_ms':10,
       'ltm_frequency_error_source':'synthetic-frequency-comparison','ltm_ul_max_tbs_r14':False,'ltm_dl_max_tbs_r17':False,
       'ltm_psm_timer_encoding':'synthetic-negotiated-NAS-profile','ltm_edrx_timer_encoding':'synthetic-negotiated-NAS-profile',key:value}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{k:v for k,v in x.items()if k!=missing})['status']=='UNVERIFIED'


@pytest.mark.parametrize('band',[31,72])
def test_lte_m_class2_power_is_hd_fdd_only_and_distinct_from_actual_output(band):
    x={**lte_m_actual(band=band,bw=1.4),'ltm_power_class':'2','ltm_nominal_max_power_dbm':26}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_ue_duplex':'FD_FDD'})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_nominal_max_power_dbm':23})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_output_power_dbm':10})['status']=='UNVERIFIED'
    assert registry.validate_parameters('lte_m',{**x,'ltm_output_power_dbm':10,'ltm_power_profile_source':'synthetic-measured-P-MPR-profile'})['status']=='VALID'


@pytest.mark.parametrize('bw,wide',[(1.4,6),(3,12),(5,24),(10,24),(15,24),(20,24)])
def test_lte_m_wideband_uses_available_regular_narrowbands_not_always24_prbs(bw,wide):
    x={**lte_m_actual(bw=bw),'ltm_wideband_prbs':wide}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_wideband_prbs':wide-1})['status']=='INVALID'


def test_lte_m_confirmed_storage_survives_rejected_foreign_bandwidth_or_grant_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x={**lte_m_actual(band=106,category='M2',bw=3),'ltm_ue_max_bandwidth_mhz':3,'ltm_allocated_prbs':13,
      'ltm_grant_profile':'WIDE_PUSCH_5_C_RNTI','ltm_rrc_state':'CONNECTED','ltm_service':'UNICAST','ltm_wideband_r14':True}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    p={'technology':'lte_m','technology_parameters':{'lte_m':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(p)
    assert service.get()['parameters']==p
    bad=deepcopy(p);bad['technology_parameters']['lte_m']['values']['ltm_carrier_bandwidth_mhz']=5
    bad['technology_parameters']['lte_m']['provenance']['ltm_carrier_bandwidth_mhz']['value']=5
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==p
    assert registry.profile('lte_m')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('key,value',[
 ('ltm_tdd_assignment',0),('ltm_tdd_pattern','DSUUUDSUUU'),('ltm_tdd_switch_ms',5),('ltm_tdd_special_source','synthetic-special-subframe')])
def test_lte_m_tdd_configuration_cannot_be_confirmed_for_an_fdd_network(key,value):
    assert registry.validate_parameters('lte_m',{**lte_m_actual(),key:value})['status']=='INVALID'


@pytest.mark.parametrize('key,value',[
 ('ltm_hd_guard_before_ms',1),('ltm_hd_guard_after_ms',1),('ltm_ue_duplex','TDD')])
def test_lte_m_half_duplex_guards_and_tdd_mode_cannot_be_applied_to_full_fdd(key,value):
    x={**lte_m_actual(),'ltm_ue_duplex':'FD_FDD',key:value}
    assert registry.validate_parameters('lte_m',x)['status']=='INVALID'


@pytest.mark.parametrize('key,value',[
 ('ltm_power_class','3'),('ltm_nominal_max_power_dbm',23),('ltm_output_power_dbm',10),('ltm_frequency_error_abs_ppm',.1)])
def test_lte_m_ue_rf_requirements_do_not_certify_an_enodeb_transmitter(key,value):
    assert registry.validate_parameters('lte_m',{**lte_m_actual(),'ltm_role':'ENODEB',key:value})['status']=='INVALID'


def test_lte_m_band_registration_matches_independent_reviewed_source_sets():
    # Exact TS36.101 5.5E list, separately from a generic LTE/NB-IoT list.
    assert {b for b,v in LTE_M_BANDS.items()if v[0]=='FDD'}=={1,2,3,4,5,7,8,11,12,13,14,18,19,20,21,24,25,26,27,28,31,54,66,71,72,73,74,85,87,88,106}
    assert {b for b,v in LTE_M_BANDS.items()if v[0]=='TDD'}=={39,40,41,42,43,48}
    assert LTE_M_BANDS[21][3]==(5,10,15)
    assert LTE_M_BANDS[106][3]==(1.4,3)
    for band in (6,9,65,70,103):
        assert registry.validate_parameters('lte_m',{**LTE_M_ACTUAL,'ltm_band':band})['status']=='INVALID'


@pytest.mark.parametrize('direction,band,bw,prbs,limit',[
 ('UPLINK',3,5,24,24),('DOWNLINK',3,5,24,24),('UPLINK',106,3,13,13),('DOWNLINK',106,3,12,12)])
def test_lte_m_actual_grant_limits_are_not_total_carrier_prbs(direction,band,bw,prbs,limit):
    x={**lte_m_actual(band=band,category='M2',direction=direction,bw=bw),'ltm_allocated_prbs':prbs,
      'ltm_grant_profile':'WIDE_PUSCH_5_C_RNTI'if direction=='UPLINK'else'WIDE_PDSCH_5_C_RNTI',
      'ltm_rrc_state':'CONNECTED','ltm_service':'UNICAST','ltm_wideband_r14':True}
    assert registry.validate_parameters('lte_m',x)['status']=='VALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_allocated_prbs':limit+1})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_grant_profile':'NARROW_6'})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{k:v for k,v in x.items()if k!='ltm_grant_profile'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('lte_m',{**x,'ltm_rrc_state':'IDLE'})['status']=='INVALID'
    assert registry.validate_parameters('lte_m',{**x,'ltm_service':'REGISTERED_SERVICE','ltm_registered_source':'synthetic-group-profile'})['status']=='INVALID'

LORA_ACTUAL={**{'lr_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','binding_source','regional_source','regulatory_source','channel_source','physical_source',
     'encoding_source','security_source','schedule_source','capacity_source','acceptance_source','registered_source')},
    'lr_protocol':LORA_L2,'lr_regional_profile':LORA_RP,'lr_region':'EU868','lr_role':'END_DEVICE',
    'lr_direction':'UPLINK','lr_frame_kind':'REGISTERED_FRAME','lr_phase':'NETWORK_CONTROLLED','lr_device_class':'A','lr_access_profile':'LBT_AFA','lr_lbt_source':'synthetic-qualified-access'}


def lora_data(region='EU868',direction='UPLINK',dr=0,sf=12,bw=125,payload=1,fopts=0,repeater=False,dwell=False,mode='LORA'):
    x={**LORA_ACTUAL,'lr_region':region,'lr_direction':direction,'lr_frame_kind':'DATA','lr_dr':dr,'lr_modulation':mode,
       'lr_uplink_dwell':dwell if direction=='UPLINK'else False,'lr_downlink_dwell':dwell if direction=='DOWNLINK'else False,
       'lr_repeater':repeater,'lr_payload_limit_use':'TRANSMIT','lr_fopts_octets':fopts,'lr_fhdr_octets':7+fopts,
       'lr_frm_payload_octets':payload,'lr_fport_present':True,'lr_fport':1,'lr_port_kind':'APPLICATION',
       'lr_mac_payload_octets':8+fopts+payload,'lr_phy_payload_octets':13+fopts+payload,
       'lr_confirmed_frame':False,'lr_ftype':2 if direction=='UPLINK'else 3,'lr_major':0,'lr_mhdr_octets':1,'lr_mic_octets':4,
       'lr_airtime_bound_ms':20,'lr_airtime_source':'synthetic-measured-full-radio-frame-bound'}
    if mode=='LORA':x.update(lr_sf=sf,lr_bandwidth_khz=bw,lr_coding_rate='4/5',lr_lora_header='EXPLICIT',
       lr_lora_preamble_symbols=8,lr_lora_sync_word=0x12 if sf<7 else 0x34,lr_lora_crc=direction=='UPLINK',
       lr_lora_iq_inverted=direction=='DOWNLINK',lr_lora_ldro=bw==125 and sf>=11 or bw==250 and sf==12)
    if mode=='FSK':x.update(lr_fs_bitrate_bps=50000,lr_fs_preamble_octets=5,lr_fs_sync_word=0xC194C1,
       lr_fs_deviation_khz=25,lr_fs_rx_bandwidth_khz=50,lr_fs_afc_bandwidth_khz=80,lr_fs_gaussian_bt=1,
       lr_fs_whitening='WHITENING',lr_fs_crc=True)
    if mode=='LR_FHSS':x.update(lr_bandwidth_khz=bw,lr_coding_rate='1/3',lr_fhss_headers=1,lr_fhss_hop_hz=488,
       lr_fhss_grid_khz=25.4 if bw==1523 else 3.9,lr_fhss_channels={137:35,336:86,1523:60}[bw],
       lr_fhss_payload_hop_ms=102.4,lr_fhss_header_hop_ms=233.472)
    return x


def test_lorawan_has_no_universal_can_clock_payload_or_automatic_actual_identifiers():
    p=registry.profile('lorawan');f={v['key']:v for v in registry.parameter_fields('lorawan')}
    assert p['domain']=='generic_networking' and p['default_stack']==['lorawan']
    assert p['max_payload_bytes']is None and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('lorawan')['values']=={}
    assert registry.validate_parameters('lorawan',LORA_ACTUAL)['status']=='VALID'
    assert not {'bitrate','queue_size','queue_policy','qos_priority','sync_method','retry_limit'} & f.keys()
    assert 'default'not in f['payload_bytes'] and 'max'not in f['payload_bytes']
    for key in ('protocol','regional_profile','region','direction','dev_addr','dev_eui','join_eui','fcnt','dev_nonce',
                'join_nonce','fport','fhss_headers','airtime_bound_ms','capacity_confirmed','counter_persistent',
                'class_b_enabled','class_c_enabled','tx_eirp_dbm','conducted_power_dbm'):
        assert 'default'not in f['lr_'+key] and 'conditional_defaults'not in f['lr_'+key],key
    for patch in ({'bitrate':50000},{'bitrate_bps':50000},{'qos_priority':7},{'local_timing_evidence':{}}):
        assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,**patch})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{})['status']=='UNVERIFIED'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_role':'END_DEVICE','lr_direction':'DOWNLINK'})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('lorawan'),ids=lambda f:'lorawan/'+f['key'])
def test_each_lorawan_field_has_independent_native_type_and_scalar_bounds(field):
    scope={k:v[0]if isinstance(v,list)else v for k,v in field.get('schema_when',{}).items()}
    x={**LORA_ACTUAL,**scope};key=field['key']
    bad={'number':True,'text':42,'boolean':'false','select':'unregistered-option'}.get(field['type'])
    if bad is not None:assert registry.validate_parameters('lorawan',{**x,key:bad})['status']=='INVALID'
    for bound,offset in [('min',-1),('max',1)]:
        if bound in field:assert registry.validate_parameters('lorawan',{**x,key:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):assert registry.validate_parameters('lorawan',{**x,key:field.get('min',0)+.5})['status']=='INVALID'


@pytest.mark.parametrize('region,direction,dr,sf,bw,mode,rate',[
 ('EU868','UPLINK',0,12,125,'LORA',250),('EU868','UPLINK',8,None,137,'LR_FHSS',162),
 ('EU868','UPLINK',10,None,336,'LR_FHSS',162),('EU433','UPLINK',12,6,125,'LORA',9375),
 ('US915','UPLINK',0,10,125,'LORA',980),('US915','UPLINK',4,8,500,'LORA',12500),
 ('US915','UPLINK',5,None,1523,'LR_FHSS',162),('US915','DOWNLINK',0,5,500,'LORA',62500),
 ('US915','DOWNLINK',8,12,500,'LORA',980),('AU915','UPLINK',2,10,125,'LORA',980),
 ('AU915','UPLINK',6,8,500,'LORA',12500),('AU915','UPLINK',7,None,1523,'LR_FHSS',162),
 ('AU915','DOWNLINK',14,6,500,'LORA',37500),('CN470','UPLINK',1,11,125,'LORA',440),
 ('CN470','UPLINK',6,7,500,'LORA',21900),('AS923_1','UPLINK',2,10,125,'LORA',980),
 ('AS923_2','UPLINK',6,7,250,'LORA',11000),('AS923_3','UPLINK',13,5,125,'LORA',15625),
 ('AS923_4','DOWNLINK',5,7,125,'LORA',5470),('KR920','UPLINK',12,6,125,'LORA',9375),
 ('IN865','UPLINK',7,None,None,'FSK',50000),('RU864','UPLINK',0,12,125,'LORA',250)])
def test_lorawan_regional_and_directional_dr_tables_are_not_one_scalar_clock(region,direction,dr,sf,bw,mode,rate):
    x=lora_data(region,direction,dr,sf,bw,mode=mode);x['lr_indicative_phy_bps']=rate
    assert registry.validate_parameters('lorawan',x)['status']=='VALID',registry.validate_parameters('lorawan',x)
    assert registry.validate_parameters('lorawan',{**x,'lr_indicative_phy_bps':rate+1})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_modulation':'FSK'if mode!='FSK'else'LORA'})['status']=='INVALID'
    if sf is not None:assert registry.validate_parameters('lorawan',{**x,'lr_sf':sf+1})['status']=='INVALID'
    if bw is not None:assert registry.validate_parameters('lorawan',{**x,'lr_bandwidth_khz':bw+1})['status']=='INVALID'


@pytest.mark.parametrize('region,dr,sf,bound,repeater,dwell',[
 ('EU868',0,12,59,False,False),('EU868',3,9,123,False,False),('EU868',5,7,230,True,False),
 ('EU868',5,7,250,False,False),('US915',0,10,19,False,False),('US915',1,9,61,False,False),
 ('US915',2,8,133,False,False),('AU915',2,10,19,False,True),('AU915',3,9,61,False,True),
 ('CN470',1,11,31,False,False),('CN470',2,10,94,False,False),('CN470',3,9,192,False,False),
 ('AS923_1',2,10,19,False,True),('AS923_1',2,10,123,False,False),('KR920',5,7,230,True,False),
 ('IN865',0,12,59,False,False),('RU864',5,7,250,False,False)])
def test_lorawan_maximum_mac_payload_includes_fopts_fport_and_not_only_application_bytes(region,dr,sf,bound,repeater,dwell):
    x=lora_data(region,dr=dr,sf=sf,payload=bound-8-5,fopts=5,repeater=repeater,dwell=dwell)
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    changed={**x,'lr_frm_payload_octets':x['lr_frm_payload_octets']+1,
       'lr_mac_payload_octets':bound+1,'lr_phy_payload_octets':bound+6}
    assert registry.validate_parameters('lorawan',changed)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{k:v for k,v in x.items()if k!='lr_uplink_dwell'})['status']=='UNVERIFIED'


def test_lorawan_as923_downlink_receive_limit_does_not_grant_sender_permission():
    x=lora_data('AS923_1','DOWNLINK',2,10,payload=115,dwell=True)
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_payload_limit_use':'END_DEVICE_RECEIVE'})['status']=='VALID'
    x=lora_data('AS923_1','UPLINK',0,12,dwell=True)
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',lora_data('CN470',dr=0,sf=12))['status']=='INVALID'
    assert registry.validate_parameters('lorawan',lora_data('KR920',dr=6,sf=7,bw=250))['status']=='INVALID'
    assert registry.validate_parameters('lorawan',lora_data('IN865',dr=6,sf=7,bw=250))['status']=='INVALID'


@pytest.mark.parametrize('region,ul,offset,dwell,down',[
 ('EU868',8,0,False,1),('EU868',12,1,False,5),('EU433',13,1,False,12),
 ('US915',0,0,False,10),('US915',8,0,False,0),('US915',4,1,False,13),
 ('AU915',0,0,False,8),('AU915',10,0,False,0),('AU915',7,0,False,9),
 ('CN470',7,5,False,2),('AS923_1',0,0,False,0),('AS923_1',0,0,True,2),
 ('AS923_2',4,6,False,5),('AS923_3',4,7,False,6),('AS923_4',12,5,True,2),
 ('KR920',12,1,False,5),('IN865',4,7,False,5),('IN865',5,7,False,7),('RU864',6,5,False,1)])
def test_lorawan_rx1_mapping_uses_its_own_region_preceding_uplink_and_dwell(region,ul,offset,dwell,down):
    x={**LORA_ACTUAL,'lr_region':region,'lr_uplink_dr':ul,'lr_rx1_dr_offset':offset,'lr_downlink_dwell':dwell,'lr_rx1_dr':down}
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_rx1_dr':down+1})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{k:v for k,v in x.items()if k!='lr_uplink_dr'})['status']=='UNVERIFIED'


def test_lorawan_class_c_window_is_distinct_from_class_c_device_and_mac_data_rules():
    x={**lora_data(direction='DOWNLINK',payload=1),'lr_device_class':'C','lr_receive_window':'RX1',
       'lr_port_kind':'MAC_COMMANDS','lr_fport':0}
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_receive_window':'CLASS_C_RXC'})['status']=='INVALID'
    x={**lora_data(),'lr_fopts_octets':1,'lr_fhdr_octets':8,'lr_mac_payload_octets':10,'lr_phy_payload_octets':15,'lr_fport':0}
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**lora_data(),'lr_fport_present':False})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_class_b_enabled':True,'lr_class_c_enabled':True})['status']=='INVALID'


def test_lorawan_counter_nonce_port_and_class_b_slots_do_not_get_guessed_defaults():
    x={**LORA_ACTUAL,'lr_fcnt':4294967295,'lr_fcnt_wire':65535,'lr_dev_eui':'0123456789abcdef',
       'lr_dev_addr':'ffffffff','lr_net_id':'ffffff','lr_device_class':'B','lr_ping_periodicity':7,
       'lr_ping_count':1,'lr_ping_period_slots':4096,'lr_ping_offset':4095}
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    for patch in ({'lr_fcnt_wire':65534},{'lr_fcnt':4294967296},{'lr_dev_eui':'ffffffff'},
                  {'lr_dev_addr':'0123456789abcdef'},{'lr_ping_count':2},{'lr_ping_offset':4096}):
        assert registry.validate_parameters('lorawan',{**x,**patch})['status']=='INVALID'
    for counter in (0,65535,65536,65537,4294967295):
        assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_fcnt':counter,'lr_fcnt_wire':counter%65536})['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_activation':'ABP','lr_counter_persistent':False})['status']=='INVALID'


def test_lorawan_response_and_airtime_limits_are_separate_from_clock_or_ack():
    x={**LORA_ACTUAL,'lr_device_class':'C','lr_retransmit_min_s':1,'lr_retransmit_max_s':3,
       'lr_ul_airtime_bound_ms':5000,'lr_class_response_timeout_s':8}
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_class_response_timeout_s':8.000000000000002})['status']=='VALID'
    for region,dr,sf,bw,allowed,blocked in [('US915',0,10,125,400,400.001),('CN470',1,11,125,1000,1000.001),
                                        ('KR920',0,12,125,3999.999,4000)]:
        x=lora_data(region,dr=dr,sf=sf,bw=bw)
        assert registry.validate_parameters('lorawan',{**x,'lr_airtime_bound_ms':allowed})['status']=='VALID'
        assert registry.validate_parameters('lorawan',{**x,'lr_airtime_bound_ms':blocked})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_region':'EU433','lr_tx_eirp_dbm':12})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_region':'EU433','lr_frequency_hz':434665000})['status']=='VALID'


@pytest.mark.parametrize('plan,ctrl,frequency,index,direction',[
 ('20_A',6,470300000,0,'UPLINK'),('20_A',7,503500000,32,'UPLINK'),('20_A',3,496500000,63,'DOWNLINK'),
 ('20_B',7,496900000,32,'UPLINK'),('26_A',3,479700000,47,'UPLINK'),('26_B',4,504700000,23,'DOWNLINK')])
def test_lorawan_cn_plan_masks_and_channel_frequencies_are_not_legacy96_channels(plan,ctrl,frequency,index,direction):
    x=lora_data('CN470',direction,1,11);x.update(lr_cn_plan=plan,lr_chmask_ctrl=ctrl,lr_frequency_hz=frequency,lr_channel_index=index)
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_frequency_hz':frequency+100})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_chmask_ctrl':5})['status']=='INVALID'
    if plan.startswith('20'):assert registry.validate_parameters('lorawan',{**x,'lr_chmask_ctrl':4})['status']=='INVALID'
    else:assert registry.validate_parameters('lorawan',{**x,'lr_chmask_ctrl':6})['status']=='INVALID'


def test_lorawan_standard_proposals_are_conditioned_and_never_assign_region_address_or_phy_proof():
    f={v['key']:v for v in registry.parameter_fields('lorawan')}
    def proposal(key,**context):
        ctx={**LORA_ACTUAL,**{'lr_'+k:v for k,v in context.items()}}
        values={p['value']for p in f['lr_'+key].get('conditional_defaults',[])if all(ctx.get(k)==v for k,v in p['when'].items())}
        assert len(values)==1,(key,context,values)
        return values.pop()
    assert proposal('receive_delay1_s',phase='BOOT')==1
    assert proposal('receive_delay2_s',phase='BOOT')==2
    assert proposal('rx2_dr',phase='BOOT',region='US915')==8
    assert proposal('rx2_frequency_hz',phase='BOOT',region='EU868')==869525000
    assert proposal('rx2_frequency_hz',phase='BOOT',region='AS923_3')==916600000
    assert proposal('rx2_frequency_hz',phase='BOOT',region='CN470',cn_plan='20_A',activation='ABP')==486900000
    assert proposal('rx2_frequency_hz',phase='BOOT',region='CN470',cn_plan='20_A',activation='OTAA',cn_join_index=7)==496500000
    assert proposal('rx2_dr',phase='BOOT',region='CN470')==1
    assert proposal('indicative_phy_bps',region='US915',direction='DOWNLINK',dr=0)==62500
    assert proposal('dr',phase='BOOT',region='AS923_1',frame_kind='JOIN_REQUEST')==2
    assert proposal('lora_sync_word',modulation='LORA',sf=5)==0x12
    assert proposal('lora_crc',modulation='LORA',direction='DOWNLINK')is False
    assert proposal('max_eirp_dbm',phase='BOOT',region='EU433')==12
    assert proposal('max_conducted_power_dbm',phase='BOOT',region='US915')==30
    assert proposal('max_eirp_dbm',phase='BOOT',region='KR920',frequency_hz=921900000)==10
    assert proposal('max_eirp_dbm',phase='BOOT',region='KR920',frequency_hz=922100000)==14
    assert proposal('fs_bitrate_bps',modulation='FSK')==50000
    assert proposal('fhss_channels',modulation='LR_FHSS',bandwidth_khz=336)==86


@pytest.mark.parametrize('adr,transmissions,expected',[(False,1,8),(False,3,8),(True,1,8),(True,3,28)])
def test_lorawan_class_c_confirmed_response_repetition_arithmetic_is_not_functional_deadline(adr,transmissions,expected):
    x={**lora_data(direction='DOWNLINK'),'lr_device_class':'C','lr_receive_window':'CLASS_C_RXC',
       'lr_confirmed_frame':True,'lr_ftype':5,'lr_adr':adr,'lr_nb_trans':transmissions,
       'lr_class_response_timeout_s':8,'lr_receive_delay1_s':1,'lr_receive_delay2_s':2,'lr_ack_response_bound_s':expected}
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_ack_response_bound_s':expected+1})['status']=='INVALID'
    assert registry.profile('lorawan')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('region,mask', [('US915',0x100),('US915',0x400),('AU915',0x8000),('EU868',0x400),('AS923_1',0x8000)])
def test_lorawan_channel_mask_rfu_bits_are_rejected_in_selected_command_context(region,mask):
    x={**LORA_ACTUAL,'lr_region':region,'lr_chmask_ctrl':5,'lr_channel_mask':mask}
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_channel_mask':0xff})['status']=='VALID'
    if region in ('US915','AU915'):
        assert registry.validate_parameters('lorawan',{**x,'lr_channel_mask':0x200})['status']=='VALID'
        assert registry.validate_parameters('lorawan',{**x,'lr_channel_mask':0x100,'lr_chmask_ctrl':0})['status']=='VALID'


@pytest.mark.parametrize('key',['lr_airtime_source','lr_airtime_bound_ms','lr_downlink_dwell','lr_confirmed_frame','lr_ftype',
                                'lr_sf','lr_bandwidth_khz','lr_lora_crc','lr_lora_header','lr_phy_payload_octets'])
def test_lorawan_incomplete_transaction_stays_unverified_instead_of_using_foreign_defaults(key):
    x=lora_data(direction='DOWNLINK')
    assert registry.validate_parameters('lorawan',{k:v for k,v in x.items()if k!=key})['status']=='UNVERIFIED'


def test_lorawan_regulatory_profile_actual_output_is_not_commissioned_max_or_conducted_power():
    x={**LORA_ACTUAL,'lr_region':'KR920','lr_frequency_hz':921900000,'lr_max_eirp_dbm':14,'lr_tx_eirp_dbm':11}
    assert registry.validate_parameters('lorawan',x)['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_tx_eirp_dbm':10})['status']=='VALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_frequency_hz':922000000,'lr_tx_eirp_dbm':10})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**x,'lr_access_profile':'DUTY_CYCLE'})['status']=='INVALID'
    assert registry.validate_parameters('lorawan',{**LORA_ACTUAL,'lr_region':'US915','lr_max_conducted_power_dbm':30,
                                                  'lr_tx_power_index':14,'lr_conducted_power_dbm':3})['status']=='INVALID'
    x={**LORA_ACTUAL,'lr_multicast':True,'lr_dev_addr':'aabbccdd','lr_multicast_source':'synthetic-assigned-group',
       'lr_nwk_skey_ref':'synthetic-group-session-key-ref','lr_app_skey_ref':'synthetic-group-app-key-ref'}
    assert registry.validate_parameters('lorawan',x)['status']=='VALID'
    assert registry.validate_parameters('lorawan',{k:v for k,v in x.items()if k!='lr_multicast_source'})['status']=='UNVERIFIED'


def test_lorawan_confirmed_storage_roundtrip_rejected_edit_does_not_overwrite_saved_radio_values():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    x=lora_data('US915',dr=0,sf=10);x.update(lr_fcnt=65536,lr_fcnt_wire=0)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    p={'technology':'lorawan','technology_parameters':{'lorawan':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(p)
    assert service.get()['parameters']==p
    bad=deepcopy(p);bad['technology_parameters']['lorawan']['values']['lr_dr']=4
    bad['technology_parameters']['lorawan']['provenance']['lr_dr']['value']=4
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==p
    assert registry.profile('lorawan')['capacity_evidence']['status']=='MODEL_MISSING'


LON_ACTUAL={**{'lw_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','transceiver_source','binding_source','physical_source','commissioning_source',
     'encoding_source','schedule_source','capacity_source','acceptance_source')},
    'lw_protocol':LON_EDITION,'lw_channel_profile':LON_GUIDE,'lw_channel':'TP_FT_10','lw_role':'APPLICATION'}


def test_lonworks_defaults_remain_source_qualified_channel_choices_not_foreign_78000():
    f={v['key']:v for v in registry.parameter_fields('lonworks')};p=registry.profile('lonworks')
    assert p['domain']=='generic_networking' and p['default_stack']==['lonworks']
    assert p['capacity_evidence']['status']=='MODEL_MISSING' and p['max_payload_bytes']is None
    assert registry.validate_parameters('lonworks',LON_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('lonworks')['values']=={}
    assert not {'bitrate','queue_policy','qos_priority','sync_method','retry_limit'} & f.keys()
    assert f['lw_network_bitrate_bps']['conditional_defaults']
    for key in ('source_node','source_subnet','destination_node','neuron_id','domain_id','group','device_priority_slot',
                'node_count','device_clock_mhz','oscillator_error_ppm','capacity_confirmed','wire_bit_order','carrier_khz'):
        assert 'default' not in f['lw_'+key] and 'conditional_defaults'not in f['lw_'+key]
    assert 'default'not in f['payload_bytes'] and 'max'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('lonworks'),ids=lambda f:'lonworks/'+f['key'])
def test_each_lonworks_field_has_independent_scalar_type_validation(field):
    bad={'number':True,'text':42,'boolean':'false','select':'unregistered-option'}.get(field['type'])
    scope={key:value[0]if isinstance(value,list)else value for key,value in field.get('schema_when',{}).items()}
    if bad is not None:assert registry.validate_parameters('lonworks',{**LON_ACTUAL,**scope,field['key']:bad})['status']=='INVALID'


@pytest.mark.parametrize('channel,rate,slots,clock,mode',[
    ('TP_XF_1250',1250000,16,10,'DIFFERENTIAL'),('TP_XF_78',78000,4,5,'DIFFERENTIAL'),
    ('TP_RS485_39',39000,4,5,'SINGLE_ENDED'),('TP_FT_10',78125,4,5,'SINGLE_ENDED'),
    ('PL_20_LN',5000,8,1.25,'SPECIAL_PURPOSE'),('PL_20_LE',5000,8,1.25,'SPECIAL_PURPOSE'),
    ('PL_20A_LN',3600,8,1.25,'SPECIAL_PURPOSE'),('FO_20S',1250000,16,10,'SINGLE_ENDED'),
    ('FO_20L',1250000,16,10,'SINGLE_ENDED')])
def test_lonworks_every_guideline_channel_has_its_own_nominal_proposal_and_clock_scope(channel,rate,slots,clock,mode):
    x={**LON_ACTUAL,'lw_channel':channel,'lw_medium_nominal_bps':rate,'lw_priority_slots':slots,
       'lw_channel_min_clock_mhz':clock,'lw_device_clock_mhz':clock,'lw_comm_port_mode':mode,'lw_oscillator_error_ppm':200}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_medium_nominal_bps':rate+1},{'lw_device_clock_mhz':clock-.1},{'lw_oscillator_error_ppm':200.1}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'


@pytest.mark.parametrize('channel,ident,rate,slots,clock,mode,first_code',[
    ('TP_XF_1250',1,1250000,16,5,1,140),('TP_XF_78',2,78125,4,4,1,29),('TP_RS485_39',3,39063,4,4,0,20),
    ('TP_FT_10',7,78125,4,4,0,90),('PL_20C',8,3987,8,3,2,73),('PL_20N',9,3987,8,3,2,73),
    ('FO_20S',24,1250000,4,5,0,1450),('FO_20L',152,1250000,4,5,0,12900)])
def test_lonworks_every_reviewed_xml_transceiver_preserves_exact_encoded_identity_and_rate(channel,ident,rate,slots,clock,mode,first_code):
    x={**LON_ACTUAL,'lw_channel_profile':LON_XCVR,'lw_channel':channel,'lw_standard_xcvr_id':ident,
       'lw_network_bitrate_bps':rate,'lw_priority_slots':slots,'lw_minimum_clock_id':clock,
       'lw_comm_mode_code':mode,'lw_raw_rcv_start_delay':first_code}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for key in ('standard_xcvr_id','network_bitrate_bps','priority_slots','comm_mode_code','raw_rcv_start_delay'):
        assert registry.validate_parameters('lonworks',{**x,'lw_'+key:x['lw_'+key]+1})['status']=='INVALID'
    assert registry.validate_parameters('lonworks',{**x,'lw_minimum_clock_id':clock-1})['status']=='INVALID'


def test_lonworks_conflicting_fo_priority_and_powerline_clock_sources_are_not_blended():
    guide={**LON_ACTUAL,'lw_channel':'FO_20S','lw_priority_slots':16}
    assert registry.validate_parameters('lonworks',guide)['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**guide,'lw_channel_profile':LON_XCVR})['status']=='INVALID'
    router={**LON_ACTUAL,'lw_channel_profile':LON_ROUTER,'lw_channel':'PL_20C','lw_router_source':'synthetic-router-fw5',
            'lw_network_bitrate_bps':3987,'lw_neuron_interface_bps':156250}
    assert registry.validate_parameters('lonworks',router)['status']=='VALID'
    for patch in [{'lw_network_bitrate_bps':5000},{'lw_network_bitrate_bps':156250},{'lw_neuron_interface_bps':3987}]:
        assert registry.validate_parameters('lonworks',{**router,**patch})['status']=='INVALID'


def test_lonworks_tpft_population_longest_path_and_power_are_distinct_from_logical_addresses():
    x={**LON_ACTUAL,'lw_local_powered_nodes':32,'lw_link_powered_nodes':64,'lw_node_count':96,
       'lw_link_power_present':True,'lw_power_source':'synthetic-loaded-PSU','lw_cable_profile':'CAT5_24AWG_568A',
       'lw_topology':'SINGLE_TERMINATED_FREE','lw_total_wire_m':450,'lw_device_distance_m':250}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_link_powered_nodes':65},{'lw_local_powered_nodes':33},{'lw_node_count':95},
                  {'lw_link_power_present':False},{'lw_total_wire_m':450.1},{'lw_device_distance_m':250.1}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'
    bus={**x,'lw_topology':'DOUBLE_TERMINATED_BUS','lw_total_wire_m':900,'lw_stub_m':3}
    assert registry.validate_parameters('lonworks',bus)['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**bus,'lw_stub_m':3.1})['status']=='INVALID'


@pytest.mark.parametrize('channel,count,beta',[('FO_20S',64,132),('FO_20L',512,1056)])
def test_lonworks_fiber_models_do_not_share_population_or_random_slot_width(channel,count,beta):
    x={**LON_ACTUAL,'lw_channel':channel,'lw_node_count':count,'lw_device_clock_mhz':10,
       'lw_cable_profile':'FIBER_62_5_125_492AAAA_A','lw_device_distance_m':25,'lw_stub_m':3,
       'lw_reference_beta2_us':beta,'lw_reference_packet_cycle_us':4020,'lw_reference_preamble_us':221.4}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_node_count':count+1},{'lw_device_distance_m':25.1},{'lw_reference_beta2_us':beta+1},
                  {'lw_reference_packet_cycle_us':4021},{'lw_reference_preamble_us':229.9}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('lonworks',{**x,'lw_device_clock_mhz':20})['status']=='UNVERIFIED'


def test_lonworks_transformer_cable_worst_case_and_temperature_limits_are_not_typical_maxima():
    x={**LON_ACTUAL,'lw_channel':'TP_XF_1250','lw_cable_profile':'UL_LEVEL_IV_22AWG','lw_wiring_case':'WORST_CASE',
       'lw_total_wire_m':130,'lw_stub_m':.3,'lw_nodes_per_16m':8,'lw_stub_capacitance_pf_m':56,
       'lw_temperature_profile':'XF1250_MINUS20_85','lw_temperature_min_c':-20,'lw_temperature_max_c':85,'lw_node_count':32}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_total_wire_m':130.1},{'lw_stub_m':.31},{'lw_nodes_per_16m':9},{'lw_node_count':33},
                  {'lw_temperature_min_c':-20.1},{'lw_stub_capacitance_pf_m':56.1}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'
    typical={**x,'lw_temperature_profile':'RANGE_0_70','lw_temperature_min_c':20,'lw_temperature_max_c':20,
             'lw_wiring_case':'TYPICAL_ROOM_5V_64_EVEN','lw_ambient_c':20,'lw_supply_v':5,'lw_node_count':64,
             'lw_even_distribution':True,'lw_total_wire_m':500}
    assert registry.validate_parameters('lonworks',typical)['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**typical,'lw_even_distribution':False})['status']=='INVALID'


def test_lonworks_predictive_csma_beta_and_transaction_timers_have_strict_native_dependencies():
    x={**LON_ACTUAL,'lw_comm_port_mode':'SINGLE_ENDED','lw_network_bitrate_bps':78125,'lw_propagation_us':1,
       'lw_mac_turnaround_us':2,'lw_beta1_us':16.81,'lw_beta2_us':4.01,'lw_device_priority_slot':2,'lw_priority_slots':4,
       'lw_timer_policy':'LONTALK3_SINGLE_CHANNEL_RECOMMENDATION','lw_timer_source':'synthetic-measured-transaction',
       'lw_packet_cycle_bound_us':1000,'lw_tx_completion_margin_us':500,'lw_retry_count':2,
       'lw_transmit_timer_ms':3.5,'lw_receive_timer_ms':14}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_beta1_us':16.8},{'lw_beta2_us':4},{'lw_device_priority_slot':1},
                  {'lw_device_priority_slot':5},{'lw_transmit_timer_ms':3.49},{'lw_receive_timer_ms':13.99},{'lw_retry_count':6}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID',patch
    # A genuinely greater decimal input must remain valid; do not widen the
    # forbidden boundary with an arbitrary epsilon to hide arithmetic errors.
    assert registry.validate_parameters('lonworks',{**x,'lw_beta1_us':16.800000000000004})['status']=='VALID'


@pytest.mark.parametrize('firmware,capacity,input_count,output_count,priority_count,total',[
    ('A',1500,2,15,2,1475),('B',1408,3,11,3,1343),('C',1500,2,15,2,1475)])
def test_lonworks_router_memory_checks_all_queues_and_other_records_by_actual_firmware(firmware,capacity,input_count,output_count,priority_count,total):
    x={**LON_ACTUAL,'lw_buffer_profile':'RTR10_01H','lw_router_firmware':firmware,'lw_router_source':'synthetic-actual-router-side',
       'lw_network_input_buffer_octets':66,'lw_network_output_buffer_octets':66,'lw_input_buffer_count':input_count,
       'lw_output_buffer_count':output_count,'lw_priority_buffer_count':priority_count,'lw_router_other_memory_octets':221,
       'lw_router_allocated_memory_octets':total,'lw_router_available_memory_octets':capacity}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_router_available_memory_octets':capacity+1},{'lw_router_allocated_memory_octets':total-1},
                  {'lw_input_buffer_count':4},{'lw_router_other_memory_octets':capacity,
                   'lw_router_allocated_memory_octets':total-221+capacity}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('lonworks',{k:v for k,v in x.items()if k!='lw_router_firmware'})['status']=='UNVERIFIED'


def test_lonworks_domain_group_neuron_and_lpdu_sizes_are_not_can_identifiers():
    x={**LON_ACTUAL,'lw_domain_octets':3,'lw_domain_id':'aabbcc','lw_address_format':'SUBNET_NODE',
       'lw_source_subnet':255,'lw_source_node':127,'lw_destination_subnet':1,'lw_destination_node':127,
       'lw_node_state':'ONLINE','lw_address_octets':4,'lw_enclosed_pdu_octets':9,'lw_lpdu_octets':20}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_domain_octets':2},{'lw_domain_id':'aabb'},{'lw_source_node':0},
                  {'lw_source_node':128},{'lw_lpdu_octets':21},{'lw_destination_subnet':0}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'
    group={**LON_ACTUAL,'lw_address_format':'GROUP','lw_service':'ACKD','lw_group_size':64,'lw_group_member':63}
    assert registry.validate_parameters('lonworks',group)['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**group,'lw_group_size':65})['status']=='INVALID'
    assert registry.validate_parameters('lonworks',{**group,'lw_service':'UNACKD','lw_group_size':100})['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**LON_ACTUAL,'lw_domain_octets':0,'lw_domain_id':''})['status']=='VALID'


def test_lonworks_ack_buffers_nv_and_explicit_application_messages_have_different_limits():
    x={**LON_ACTUAL,'lw_buffer_profile':'NEURON_C_2_2','lw_service':'ACKD','lw_network_input_buffer_octets':66,
       'lw_network_output_buffer_octets':66,'lw_required_output_buffer_octets':66,'lw_largest_encoded_message_octets':44,
       'lw_explicit_addressing':True,'lw_app_output_buffer_octets':66,'lw_app_data_octets':49,'lw_nv_octets':31}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    for patch in [{'lw_required_output_buffer_octets':67},{'lw_app_data_octets':50},{'lw_nv_octets':32},
                  {'lw_network_input_buffer_octets':65},{'lw_network_input_buffer_octets':67},
                  {'lw_largest_encoded_message_octets':45}]:
        assert registry.validate_parameters('lonworks',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('lonworks',{**x,'lw_service':'UNACKD','lw_network_output_buffer_octets':82,
                                                   'lw_required_output_buffer_octets':70})['status']=='VALID'
    for kind,code in [('APPLICATION_MESSAGE',62),('FOREIGN_FRAME',78),('RESPONDER_OFFLINE',63),
                      ('FOREIGN_RESPONDER_OFFLINE',79),('NETWORK_DIAGNOSTIC',95),('NETWORK_MANAGEMENT',127),('NETWORK_VARIABLE',255)]:
        assert registry.validate_parameters('lonworks',{**x,'lw_payload_kind':kind,'lw_message_code':code})['status']=='VALID'


@pytest.mark.parametrize('receives,nv,minimum',[(False,0,2),(True,0,8),(False,13,15),(True,14,16),(False,65536,16)])
def test_lonworks_receive_transactions_follow_actual_input_workload_not_generic_queue(receives,nv,minimum):
    x={**LON_ACTUAL,'lw_receives_application_frames':receives,'lw_nonconfig_input_nv_count':nv,'lw_receive_transaction_count':minimum}
    assert registry.validate_parameters('lonworks',x)['status']=='VALID'
    assert registry.validate_parameters('lonworks',{**x,'lw_receive_transaction_count':minimum-1})['status']=='INVALID'


def test_lonworks_ip852_authentication_and_registered_variants_cannot_borrow_foreign_defaults():
    ip={**LON_ACTUAL,'lw_channel':'IP_852','lw_ip_udp_supported':True,'lw_ip_normal_port':1628,'lw_ip_urgent_port':1629}
    assert registry.validate_parameters('lonworks',ip)['status']=='VALID'
    for patch in [{'lw_ip_udp_supported':False},{'lw_network_bitrate_bps':78125},{'bitrate':100000000},
                  {'can_fd_brs':True},{'local_timing_evidence':{'slave_address':1}}]:
        assert registry.validate_parameters('lonworks',{**ip,**patch})['status']=='INVALID'
    auth={**LON_ACTUAL,'lw_service':'ACKD','lw_authenticated':True,'lw_authentication_profile':'LEGACY_48_BIT',
          'lw_security_source':'synthetic-provisioning','lw_key_ref':'synthetic-secret-ref','lw_key_octets':6,'lw_challenge_octets':8}
    assert registry.validate_parameters('lonworks',auth)['status']=='VALID'
    for patch in [{'lw_service':'UNACKD'},{'lw_key_octets':16},{'lw_challenge_octets':6}]:
        assert registry.validate_parameters('lonworks',{**auth,**patch})['status']=='INVALID'
    registered={**LON_ACTUAL,'lw_protocol':'REGISTERED_PROTOCOL','lw_registered_source':'synthetic-current-edition'}
    assert registry.validate_parameters('lonworks',{**registered,'lw_source_node':1})['status']=='UNVERIFIED'


def test_lonworks_confirmed_values_survive_foreign_rate_edit_in_isolated_sql():
    from copy import deepcopy
    from backend.engineering.project_context import current_project_id
    service=WorkflowStatusService(current_project_id())
    saved={'technology':'lonworks','technology_parameters':{'lonworks':{'values':LON_ACTUAL,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in LON_ACTUAL.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);group=bad['technology_parameters']['lonworks'];group['values']['bitrate']=500000
    group['provenance']['bitrate']={'source':'USER_CONFIRMED','status':'CONFIRMED','value':500000}
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved

LIN_ACTUAL={**{'lin_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','binding_source','physical_source','ldf_source','encoding_source',
     'schedule_source','capacity_source','acceptance_source','commander_node_id')},
    'lin_edition':LIN_EDITION,'lin_physical_profile':'LIN_2_2A_SINGLE_WIRE','lin_node_role':'COMMANDER',
    'lin_frame_kind':'UNCONDITIONAL','lin_bitrate_bps':1000}


def test_lin_has_explicit_ldf_minimum_policy_proposal_not_example_19200_or_can_defaults():
    f={v['key']:v for v in registry.parameter_fields('lin')};p=registry.profile('lin')
    assert p['domain']=='generic_networking'and p['default_stack']==['lin']
    assert p['capacity_evidence']['frame_model']=='LIN_NOMINAL_WITH_CHECKSUM'
    assert p['verification_status']=='UNVERIFIED'
    assert registry.validate_parameters('lin',LIN_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('lin')['values']=={}
    assert f['lin_bitrate_bps']['conditional_defaults'][0]['value']==1000
    assert f['lin_bitrate_bps']['conditional_defaults'][0]['basis']=='USER_POLICY_LOWEST_SPECIFIED_RATE_NOT_UNIVERSAL_LIN_DEFAULT'
    assert 'bitrate'not in f and 'queue_policy'not in f and 'qos_priority'not in f
    for key in ('pid','commander_node_id','publisher_node_id','node_count','data_octets','slot_ticks','jitter_ms',
                'supply_v','bus_capacitance_nf','diag_nad','diode_present','capacity_confirmed'):
        item=f['lin_'+key]
        assert 'default'not in item
        if key=='data_octets':assert all(v['when']['lin_frame_kind'].startswith('DIAGNOSTIC')or v['when']['lin_frame_kind']=='GO_TO_SLEEP'for v in item['conditional_defaults'])
        else:assert 'conditional_defaults'not in item
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('lin'),ids=lambda f:'lin/'+f['key'])
def test_each_lin_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('lin',{**LIN_ACTUAL,field['key']:wrong})['status']=='INVALID'


def test_lin_nominal_adapter_preserves_math_but_cannot_select_foreign_phy_or_data_class():
    adapter=registry.resolve_stack('lin')['timing_model']
    assert adapter.transmission_time_us(8,1000,technology_parameters=LIN_ACTUAL)==pytest.approx(124000)
    for payload,patch in [(8,{'lin_bitrate_bps':19200}),(0,{}),(9,{}),
        (1,{'lin_frame_kind':'DIAGNOSTIC_REQUEST'}),(8,{'lin_frame_kind':'WAKE_UP'}),
        (8,{'lin_frame_kind':'REGISTERED_FRAME','lin_registered_source':'synthetic-custom-codec'}),
        (8,{'lin_physical_profile':'REGISTERED_PHY','lin_registered_source':'synthetic-24V-device'})]:
        with pytest.raises(ValueError):adapter.transmission_time_us(payload,1000,technology_parameters={**LIN_ACTUAL,**patch})


@pytest.mark.parametrize('identifier',range(62))
def test_lin_pid_parity_matches_independent_bit_count_for_every_non_reserved_id(identifier):
    p0=(identifier&0b010111).bit_count()%2
    p1=1-((identifier&0b111010).bit_count()%2)
    expected=identifier+64*p0+128*p1
    x={**LIN_ACTUAL,'lin_frame_kind':'DIAGNOSTIC_REQUEST'if identifier==60 else'DIAGNOSTIC_RESPONSE'if identifier==61 else'UNCONDITIONAL',
       'lin_frame_id':identifier,'lin_pid':expected,'lin_publisher_node_id':'synthetic-frame-owner'}
    assert protected_id(identifier)==expected
    assert registry.validate_parameters('lin',x)['status']=='VALID'
    assert registry.validate_parameters('lin',{**x,'lin_pid':expected^64})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':19200},{'can_fd_brs':True},{'ktp_bitrate_bps':9600},
    {'local_timing_evidence':{'slave_address':1}},{'lin_undocumented':1},{'lin_bitrate_bps':999},{'lin_bitrate_bps':20001},
    {'lin_commander_count':2},{'lin_node_count':17},{'lin_frame_id':60,'lin_publisher_node_id':'synthetic-owner'},
    {'lin_frame_id':62},{'lin_frame_id':63},{'lin_data_octets':9},{'lin_data_bits':9},{'lin_byte_bits':13},
    {'lin_uart_parity':'EVEN'},{'lin_break_bits':12.99},{'lin_delimiter_bits':.99},{'lin_sync_byte':84},
    {'lin_commander_clock_error_percent':.5},{'lin_peer_clock_difference_percent':2},
    {'lin_supply_v':7.99},{'lin_supply_v':18.01},{'lin_bus_capacitance_nf':10.01},{'lin_rc_time_us':5.01},
    {'lin_bus_length_m':40.01},{'lin_diode_present':False},{'lin_wake_pulse_us':249},{'lin_wake_pulse_us':5001},
    {'lin_wake_detect_us':150},{'lin_responder_ready_ms':100.01},{'lin_wake_retry_ms':251},
    {'lin_wake_block_attempts':4},{'lin_wake_block_pause_ms':1499},{'lin_sleep_idle_ms':3999},
    {'lin_sleep_idle_ms':10001},{'lin_flow_control':True},{'lin_n_as_timeout_ms':0},{'lin_n_cr_timeout_ms':1001}])
def test_lin_rejects_invalid_native_standard_boundaries_and_foreign_protocol_fields(patch):
    assert registry.validate_parameters('lin',{**LIN_ACTUAL,**patch})['status']=='INVALID'


def test_lin_nominal_padding_and_ldf_slot_jitter_are_not_zero_gap_capacity_assumptions():
    x={**LIN_ACTUAL,'lin_data_octets':8,'lin_header_nominal_bits':34,'lin_response_nominal_bits':90,
        'lin_frame_nominal_bits':124,'lin_frame_max_ms':173.6,'lin_header_actual_ms':47.6,'lin_response_actual_ms':126,
        'lin_time_base_ms':5,'lin_slot_ticks':35,'lin_slot_ms':175,'lin_jitter_ms':1.4}
    # Equality to jitter+maxframe is insufficient: the schedule requirement is strict.
    assert registry.validate_parameters('lin',x)['status']=='INVALID'
    x.update(lin_slot_ticks=36,lin_slot_ms=180)
    assert registry.validate_parameters('lin',x)['status']=='VALID'
    for patch in ({'lin_response_nominal_bits':80},{'lin_frame_nominal_bits':114},{'lin_frame_max_ms':124},
        {'lin_header_actual_ms':47.61},{'lin_response_actual_ms':126.01},{'lin_slot_ms':181},{'lin_time_base_ms':0}):
        assert registry.validate_parameters('lin',{**x,**patch})['status']=='INVALID'
    fast={**x,'lin_bitrate_bps':20000,'lin_frame_max_ms':8.68,'lin_header_actual_ms':2.38,'lin_response_actual_ms':6.3}
    assert registry.validate_parameters('lin',fast)['status']=='VALID'
    assert registry.validate_parameters('lin',{**fast,'lin_frame_max_ms':173.6})['status']=='INVALID'


def test_lin_frame_checksum_classes_collision_schedule_and_phy_clock_scope():
    diag={**LIN_ACTUAL,'lin_frame_kind':'DIAGNOSTIC_REQUEST','lin_frame_id':60,'lin_pid':0x3c,
        'lin_data_octets':8,'lin_checksum_model':'CLASSIC','lin_publisher_role':'COMMANDER',
        'lin_diag_class':'II','lin_ncf_source':'synthetic-node-capability','lin_diag_source':'synthetic-diag-schedule',
        'lin_p2_min_ms':50,'lin_st_min_ms':0,'lin_n_as_timeout_ms':1000,'lin_n_cr_timeout_ms':1000,
        'lin_n_cs_ms':399,'lin_n_as_actual_ms':500,'lin_flow_control':False}
    assert registry.validate_parameters('lin',diag)['status']=='VALID'
    for patch in ({'lin_checksum_model':'ENHANCED'},{'lin_data_octets':6},{'lin_frame_id':59},
        {'lin_publisher_role':'RESPONDER'},{'lin_diag_class':'I'},{'lin_n_cs_ms':400}):
        assert registry.validate_parameters('lin',{**diag,**patch})['status']=='INVALID'
    event={**LIN_ACTUAL,'lin_frame_kind':'EVENT_TRIGGERED'}
    assert registry.validate_parameters('lin',event)['status']=='UNVERIFIED'
    event['lin_collision_schedule_source']='synthetic-resolve-every-associated-unconditional'
    assert registry.validate_parameters('lin',event)['status']=='VALID'
    legacy={**LIN_ACTUAL,'lin_responder_version':'LIN_1_X','lin_checksum_model':'CLASSIC'}
    assert registry.validate_parameters('lin',legacy)['status']=='VALID'
    assert registry.validate_parameters('lin',{**legacy,'lin_checksum_model':'ENHANCED'})['status']=='INVALID'
    assert registry.validate_parameters('lin',{**legacy,'lin_responder_version':'LIN_2_X'})['status']=='INVALID'
    for sync,key,good,bad in [('SYNC_MEASURED','unsynced_clock_error_percent',13.99,14),
                            ('SYNC_MEASURED','synced_clock_error_percent',1.99,2),('NO_SYNC','no_sync_clock_error_percent',1.49,1.5)]:
        assert registry.validate_parameters('lin',{**LIN_ACTUAL,'lin_sync_mode':sync,'lin_'+key:good})['status']=='VALID'
        assert registry.validate_parameters('lin',{**LIN_ACTUAL,'lin_sync_mode':sync,'lin_'+key:bad})['status']=='INVALID'
    for role,value,bad in [('COMMANDER',1000,1101),('RESPONDER',30000,19999)]:
        assert registry.validate_parameters('lin',{**LIN_ACTUAL,'lin_supply_role':role,'lin_pullup_ohm':value})['status']=='VALID'
        assert registry.validate_parameters('lin',{**LIN_ACTUAL,'lin_supply_role':role,'lin_pullup_ohm':bad})['status']=='INVALID'


def test_lin_transport_nad_sf_ff_cf_and_current_registered_editions_are_separate():
    sf={**LIN_ACTUAL,'lin_frame_kind':'DIAGNOSTIC_RESPONSE','lin_frame_id':61,'lin_pid':0x7d,
        'lin_pdu_type':'SF','lin_message_octets':6,'lin_pdu_payload_octets':6,'lin_pci':6,
        'lin_nad_kind':'PHYSICAL','lin_diag_nad':125}
    assert registry.validate_parameters('lin',sf)['status']=='VALID'
    for patch in ({'lin_message_octets':7},{'lin_pci':7},{'lin_diag_nad':126},{'lin_flow_control':True}):
        assert registry.validate_parameters('lin',{**sf,**patch})['status']=='INVALID'
    ff={**sf,'lin_pdu_type':'FF','lin_message_octets':4095,'lin_pdu_payload_octets':5,'lin_pci':31}
    assert registry.validate_parameters('lin',ff)['status']=='VALID'
    assert registry.validate_parameters('lin',{**ff,'lin_message_octets':6})['status']=='INVALID'
    assert registry.validate_parameters('lin',{**ff,'lin_pci':16})['status']=='INVALID'
    for length,pci,low in [(7,16,7),(255,16,255),(256,17,0),(4095,31,255)]:
        frame={**ff,'lin_message_octets':length,'lin_pci':pci,'lin_ff_length_low':low}
        assert registry.validate_parameters('lin',frame)['status']=='VALID'
        assert registry.validate_parameters('lin',{**frame,'lin_ff_length_low':(low+1)%256})['status']=='INVALID'
    cf={**sf,'lin_pdu_type':'CF','lin_pdu_payload_octets':6,'lin_cf_sequence':0,'lin_pci':32}
    assert registry.validate_parameters('lin',cf)['status']=='VALID'
    assert registry.validate_parameters('lin',{**cf,'lin_pci':33})['status']=='INVALID'
    current={**LIN_ACTUAL,'lin_edition':'ISO_17987_REGISTERED','lin_physical_profile':'REGISTERED_PHY','lin_supply_v':24}
    assert registry.validate_parameters('lin',current)['status']=='UNVERIFIED'
    current['lin_registered_source']='synthetic-reviewed-current24V-physical-schema'
    assert registry.validate_parameters('lin',current)['status']=='VALID'
    assert registry.validate_parameters('lin',{**current,'lin_edition':LIN_EDITION,'lin_physical_profile':'LIN_2_2A_SINGLE_WIRE'})['status']=='INVALID'


def test_lin_isolated_sql_preserves_confirmed_ldf_and_rate_after_foreign_can_bitrate():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    saved={'technology':'lin','technology_parameters':{'lin':{'values':LIN_ACTUAL,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in LIN_ACTUAL.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['lin']['values']['lin_bitrate_bps']=500000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved

KNX_TP_ACTUAL={**{'ktp_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','physical_source','binding_source','commissioning_source',
     'application_source','encoding_source','schedule_source','capacity_source','acceptance_source')},
    'ktp_profile':'TP1_DEVICE_QUALIFIED','ktp_role':'END_DEVICE','ktp_frame_kind':'STANDARD_DATA','ktp_bitrate_bps':9600}


def test_knx_tp_native_wire_defaults_and_host_clocks_are_separate_from_can_or_ip():
    f={v['key']:v for v in registry.parameter_fields('knx_tp')};p=registry.profile('knx_tp')
    assert p['domain']=='generic_networking'and p['capacity_evidence']['status']=='MODEL_MISSING'
    assert p['max_payload_bytes']is None and p['default_stack']==['knx_tp']
    assert registry.validate_parameters('knx_tp',KNX_TP_ACTUAL)['status']=='VALID'
    assert f['ktp_bitrate_bps']['default']==9600
    assert f['ktp_character_bits']['default']==13
    assert 'bitrate'not in f and 'queue_policy'not in f and 'qos_priority'not in f
    assert registry.parameter_defaults_review('knx_tp')['values']=={}
    for key in ('source_address','destination_address','bus_voltage_v','segment_load_ma','tp64_count','tp256_count',
                'wire_checksum','auto_ack','capacity_confirmed','power_confirmed','data_secure'):
        assert 'default'not in f['ktp_'+key]and 'conditional_defaults'not in f['ktp_'+key]
    assert f['ktp_device_current_ma']['conditional_defaults'][0]['when']=={'ktp_power_basis':'ETS_ESTIMATE'}
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('knx_tp'),ids=lambda f:'knx_tp/'+f['key'])
def test_each_knx_tp_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('knx_tp',{**KNX_TP_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':9600},{'kip_port':3671},{'krf_bitrate_bps':16384},
    {'local_timing_evidence':{'slave_address':1}},{'can_fd_brs':True},{'ktp_undocumented':1},
    {'ktp_bitrate_bps':19200},{'ktp_data_bits':9},{'ktp_character_bits':11},{'ktp_pause_bits':0},
    {'ktp_source_address':65536},{'ktp_area':16},{'ktp_line':16},{'ktp_device_number':256},
    {'ktp_priority_code':4},{'ktp_hop_count':8},{'ktp_tpdu_octets':17},{'ktp_length_field':16},
    {'ktp_wire_checksum':256},{'ktp_idle_bits':49},{'ktp_segment_length_m':1000.01},{'ktp_psu_device_distance_m':350.01}] )
def test_knx_tp_no_foreign_defaults_or_invalid_tp_wire_fields(patch):
    assert registry.validate_parameters('knx_tp',{**KNX_TP_ACTUAL,**patch})['status']=='INVALID'


def test_knx_tp_wire_framing_addresses_group_editions_and_repetition_bit():
    x={**KNX_TP_ACTUAL,'ktp_tpdu_octets':16,'ktp_length_field':15,'ktp_frame_octets':23,
        'ktp_area':3,'ktp_line':10,'ktp_device_number':20,'ktp_source_address':0x3a14,
        'ktp_repeated':True,'ktp_repeat_bit':0,'ktp_idle_bits':50,'ktp_idle_ms':50*1000/9600,
        'ktp_ack_bound_ms':15*1000/9600,'ktp_address_kind':'GROUP','ktp_group_edition':'CALIMERO_V2_6_16BIT',
        'ktp_address_source':'synthetic-commissioned16bit-group','ktp_group_style':'THREE_LEVEL',
        'ktp_group_main':31,'ktp_group_middle':7,'ktp_group_sub':255,'ktp_destination_address':65535}
    assert registry.validate_parameters('knx_tp',x)['status']=='VALID'
    for patch in ({'ktp_source_address':0x3a15},{'ktp_repeat_bit':1},{'ktp_frame_octets':24},
                  {'ktp_length_field':16},{'ktp_idle_ms':5.2},{'ktp_ack_bound_ms':1.563},
                  {'ktp_group_edition':'TI2015_LEGACY_15BIT'},{'ktp_destination_address':65534},{'ktp_group_sub':256}):
        assert registry.validate_parameters('knx_tp',{**x,**patch})['status']=='INVALID'
    legacy={**x,'ktp_group_edition':'TI2015_LEGACY_15BIT','ktp_group_main':15,'ktp_destination_address':32767}
    assert registry.validate_parameters('knx_tp',legacy)['status']=='VALID'
    extended={**x,'ktp_frame_kind':'EXTENDED_DATA','ktp_tpdu_octets':255,'ktp_length_field':254,'ktp_frame_octets':263}
    assert registry.validate_parameters('knx_tp',extended)['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**extended,'ktp_frame_kind':'ACK'})['status']=='INVALID'


def test_knx_tp_electrical_fan_in_and_supply_current_and_voltage_are_independent():
    x={**KNX_TP_ACTUAL,'ktp_tp64_count':32,'ktp_tp256_count':128,'ktp_fan_in':256,
        'ktp_power_basis':'DATASHEET','ktp_power_source':'synthetic-all-installed-loads',
        'ktp_supply_current_ma':320,'ktp_segment_load_ma':320,'ktp_device_min_v':21,'ktp_device_max_v':30,
        'ktp_bus_voltage_v':29,'ktp_cable_profile':'KNX_APPROVED_0_8','ktp_cable_diameter_mm':.8}
    assert registry.validate_parameters('knx_tp',x)['status']=='VALID'
    for patch in ({'ktp_tp256_count':129},{'ktp_fan_in':255},{'ktp_segment_load_ma':320.01},
        {'ktp_bus_voltage_v':20.99},{'ktp_bus_voltage_v':30.01},{'ktp_device_min_v':31},{'ktp_cable_diameter_mm':.9}):
        assert registry.validate_parameters('knx_tp',{**x,**patch})['status']=='INVALID'
    estimated={**x,'ktp_power_basis':'ETS_ESTIMATE','ktp_power_confirmed':False}
    assert registry.validate_parameters('knx_tp',estimated)['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**estimated,'ktp_power_confirmed':True})['status']=='INVALID'
    assert registry.validate_parameters('knx_tp',{k:v for k,v in estimated.items()if k!='ktp_power_source'})['status']=='UNVERIFIED'


def test_knx_tp_ncn5120_qualified_uart_spi_crc_marker_and_retry_scopes():
    x={**KNX_TP_ACTUAL,'ktp_profile':'NCN5120_REV8','ktp_host_source':'synthetic-NCN-board',
        'ktp_host_kind':'UART9','ktp_host_bitrate_bps':19200,'ktp_host_data_bits':8,'ktp_host_stop_bits':1,
        'ktp_host_parity':'EVEN','ktp_host_order':'LSB_FIRST','ktp_device_state':'NORMAL','ktp_tx_enabled':True,
        'ktp_host_crc_enabled':True,'ktp_host_crc_octets':2,'ktp_host_crc_polynomial':0x1021,
        'ktp_host_crc_initial':65535,'ktp_host_crc_xorout':0,'ktp_host_frame_end':'MARKER','ktp_host_marker':203,
        'ktp_busy_retries':3,'ktp_nack_retries':3,'ktp_retries_enabled':True,'ktp_worst_attempts':7,
        'ktp_busy_idle_bits':150,'ktp_nack_idle_bits':50,'ktp_ack_timeout_bits':30,'ktp_sync_idle_bits':40}
    assert registry.validate_parameters('knx_tp',x)['status']=='VALID'
    for patch in ({'ktp_host_bitrate_bps':9600},{'ktp_host_data_bits':9},{'ktp_host_parity':'NONE'},
        {'ktp_device_state':'STOP'},{'ktp_host_crc_polynomial':0x3d65},{'ktp_host_crc_initial':0},
        {'ktp_host_marker':204},{'ktp_host_frame_end':'SILENCE'},{'ktp_host_crc_enabled':False},
        {'ktp_host_cpol':0},{'ktp_spi_master':'HOST'},{'ktp_worst_attempts':4},{'ktp_busy_idle_bits':149},
        {'ktp_nack_idle_bits':49},{'ktp_ack_timeout_bits':15},{'ktp_sync_idle_bits':50}):
        assert registry.validate_parameters('knx_tp',{**x,**patch})['status']=='INVALID'
    spi={k:v for k,v in x.items()if k not in ('ktp_host_data_bits','ktp_host_stop_bits','ktp_host_parity')}
    spi.update(ktp_host_kind='SPI',ktp_host_bitrate_bps=125000,ktp_host_cpol=0,ktp_host_cpha=0,ktp_spi_master='PHY')
    assert registry.validate_parameters('knx_tp',spi)['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**spi,'ktp_spi_master':'HOST'})['status']=='INVALID'
    assert registry.validate_parameters('knx_tp',{**spi,'ktp_host_kind':'ANALOG'})['status']=='INVALID'
    assert registry.validate_parameters('knx_tp',{**x,'ktp_retries_enabled':False,'ktp_worst_attempts':1})['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**x,'ktp_auto_ack':True})['status']=='UNVERIFIED'
    analog={**KNX_TP_ACTUAL,'ktp_profile':'NCN5120_REV8','ktp_host_kind':'ANALOG','ktp_host_source':'synthetic-host-bit-engine'}
    assert registry.validate_parameters('knx_tp',analog)['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**analog,'ktp_busy_retries':3})['status']=='INVALID'
    maximum={**x,'ktp_frame_kind':'EXTENDED_DATA','ktp_tpdu_octets':56,'ktp_length_field':55,
        'ktp_frame_octets':64,'ktp_host_buffer_source':'synthetic-command-index-limit63'}
    assert registry.validate_parameters('knx_tp',maximum)['status']=='VALID'
    assert registry.validate_parameters('knx_tp',{**maximum,'ktp_tpdu_octets':57,'ktp_length_field':56,'ktp_frame_octets':65})['status']=='INVALID'
    unknown_crc={k:v for k,v in x.items()if k!='ktp_host_crc_enabled'}
    assert registry.validate_parameters('knx_tp',unknown_crc)['status']=='UNVERIFIED'


def test_knx_tp_isolated_sql_preserves_confirmed_addresses_after_wrong_host_clock():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    saved={'technology':'knx_tp','technology_parameters':{'knx_tp':{'values':KNX_TP_ACTUAL,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in KNX_TP_ACTUAL.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['knx_tp']['values']['ktp_bitrate_bps']=19200
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved

KNX_RF_ACTUAL={**{'krf_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','regulatory_source','physical_source','binding_source','commissioning_source',
     'application_source','encoding_source','schedule_source','capacity_source','acceptance_source')},
    'krf_edition':KNX_RF_EDITION,'krf_variant':'RF1_READY','krf_channel':'SINGLE','krf_role':'END_DEVICE',
    'krf_direction':'TRANSMITTER','krf_device_direction':'BIDIRECTIONAL','krf_frame_kind':'READY_DATA','krf_bitrate_bps':16384}


def test_knx_rf_has_edition_and_channel_qualified_operating_proposals_not_generic_can_or_ip_phy():
    f={v['key']:v for v in registry.parameter_fields('knx_rf')};p=registry.profile('knx_rf')
    assert p['domain']=='generic_networking'and p['default_stack']==['knx_rf']
    assert p['capacity_evidence']['status']=='MODEL_MISSING'and p['max_payload_bytes']is None
    assert registry.validate_parameters('knx_rf',KNX_RF_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('knx_rf')['values']=={}
    assert 'bitrate'not in f and 'queue_policy'not in f and 'qos_priority'not in f
    proposals=f['krf_bitrate_bps']['conditional_defaults']
    assert {x['when']['krf_channel']:x['value']for x in proposals if x['when']['krf_variant']=='RF1_MULTI'}=={
        'F1':16384,'F2':16384,'F3':16384,'S1':8192,'S2':8192}
    assert not any(x['when'].get('krf_variant')=='MULTI_SLE_REGISTERED'for x in proposals)
    for key in ('serial_hex','domain_hex','battery_ok','duty_percent','duty_window_ms','tx_frequency_error_ppm',
                'rx_sensitivity_dbm','link_budget_db','random_ms','ack_expected','ack_slot','bib_repeater_number','bib_pause_ms','data_secure'):
        assert 'default'not in f['krf_'+key]and 'conditional_defaults'not in f['krf_'+key]
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('knx_rf'),ids=lambda f:'knx_rf/'+f['key'])
def test_each_knx_rf_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('knx_rf',{**KNX_RF_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':16384},{'kip_port':3671},{'i2c_mode':'STANDARD'},{'can_fd_brs':True},
    {'local_timing_evidence':{'slave_address':1}},{'krf_undocumented':1},{'krf_bitrate_bps':8192},
    {'krf_channel':'S1'},{'krf_frame_kind':'MULTI_DATA'},{'krf_carrier_hz':915000000},
    {'krf_tx_erp_dbm':15},{'krf_deviation_hz':47999},{'krf_bandwidth_hz':600001},{'krf_duty_percent':1.01},
    {'krf_tx_frequency_error_ppm':25.01},{'krf_rx_frequency_tolerance_ppm':24.99},
    {'krf_tx_chip_error_percent':1.51},{'krf_rx_chip_tolerance_percent':1.99},{'krf_tx_jitter_us':5.01},
    {'krf_operating_min_c':1},{'krf_operating_max_c':44},{'krf_rx_sensitivity_dbm':-79.99},
    {'krf_length_field':255},{'krf_crc_polynomial':0x1021},{'krf_crc_initial':65535},
    {'krf_c_field':69},{'krf_esc_field':0},{'krf_lfn':8},{'krf_repetition_counter':2},
    {'krf_bib_slot_ms':62.5},{'krf_ack_slot_ms':5},{'krf_domain_participants':256},
    {'krf_repeaters':4},{'krf_serial_hex':'01:23:45:67:89:ab'},{'krf_fast_ack':True}])
def test_knx_rf_rejects_foreign_buses_wrong_variant_radio_bounds_and_inapplicable_service_parameters(patch):
    assert registry.validate_parameters('knx_rf',{**KNX_RF_ACTUAL,**patch})['status']=='INVALID'


def test_knx_rf_ft3_lengths_per_block_crc_address_extension_and_access_timing_do_not_use_can_defaults():
    x={**KNX_RF_ACTUAL,'krf_encoding':'MANCHESTER','krf_chiprate_cps':32768,
       'krf_preamble_pairs':79,'krf_preamble_chips':158,'krf_user_octets':27,'krf_length_field':26,
       'krf_block_count':3,'krf_frame_octets':33,'krf_crc_octets':2,'krf_crc_polynomial':0x3d65,
       'krf_crc_initial':0,'krf_crc_xorout':65535,'krf_c_field':68,'krf_esc_field':255,
       'krf_communication':'MULTICAST','krf_serial_hex':'0123456789ab','krf_wire_address_hex':'0123456789ab',
       'krf_address_extension_type':0,'krf_address_type':1,'krf_access_kind':'ORIGINAL',
       'krf_interframe_ms':15,'krf_random_ms':14,'krf_medium_access_ms':29}
    assert registry.validate_parameters('knx_rf',x)['status']=='VALID'
    for patch in ({'krf_chiprate_cps':16384},{'krf_preamble_chips':79},{'krf_block_count':2},
                  {'krf_frame_octets':31},{'krf_length_field':27},{'krf_address_extension_type':1},
                  {'krf_wire_address_hex':'0123456789ac'},{'krf_address_type':0},
                  {'krf_interframe_ms':5},{'krf_random_ms':15,'krf_medium_access_ms':30},
                  {'krf_random_ms':.5},{'krf_medium_access_ms':30}):
        assert registry.validate_parameters('knx_rf',{**x,**patch})['status']=='INVALID'
    for user,blocks in [(26,2),(27,3),(42,3),(43,4),(255,17)]:
        assert registry.validate_parameters('knx_rf',{**x,'krf_user_octets':user,'krf_length_field':user-1,
            'krf_block_count':blocks,'krf_frame_octets':user+2*blocks})['status']=='VALID'
    broadcast={**x,'krf_communication':'SYSTEM_BROADCAST','krf_destination_address':0}
    assert registry.validate_parameters('knx_rf',broadcast)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**broadcast,'krf_destination_address':1})['status']=='INVALID'
    domain={**x,'krf_communication':'DOMAIN_BROADCAST','krf_domain_hex':'112233445566',
            'krf_domain_member_serial_hex':'112233445566','krf_wire_address_hex':'112233445566',
            'krf_address_extension_type':1,'krf_destination_address':0}
    assert registry.validate_parameters('knx_rf',domain)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**domain,'krf_domain_member_serial_hex':'112233445567'})['status']=='INVALID'


def test_knx_rf_multi_fast_slow_frequency_power_duty_and_ack_timings_are_checked_separately():
    x={**KNX_RF_ACTUAL,'krf_variant':'RF1_MULTI','krf_channel':'F2','krf_frame_kind':'MULTI_DATA',
       'krf_carrier_hz':868950000,'krf_encoding':'MANCHESTER','krf_chiprate_cps':32768,'krf_duty_percent':.1,
       'krf_preamble_pairs':247,'krf_repetition_counter':2,'krf_fast_ack':True,'krf_frame_control':144,
       'krf_ack_source':'synthetic-configured-ACK-table','krf_receiver_source':'synthetic-qualified-receivers',
       'krf_ack_expected':64,'krf_ack_slot':64,'krf_ack_slot_ms':5,'krf_ack_start_us':300,
       'krf_ack_clock_error_percent':.05,'krf_ack_postamble_ms':9,'krf_ack_retry_attempts':4,'krf_echo_timeout_ms':75,
       'krf_access_kind':'ORIGINAL','krf_interframe_ms':30,'krf_random_ms':19,'krf_medium_access_ms':49,'krf_channel_timeout_ms':500}
    assert registry.validate_parameters('knx_rf',x)['status']=='VALID'
    for patch in ({'krf_duty_percent':.101},{'krf_carrier_hz':868300000},{'krf_bitrate_bps':8192},
                  {'krf_ack_expected':65},{'krf_ack_slot':65},{'krf_ack_slot_ms':10},{'krf_ack_start_us':301},
                  {'krf_ack_clock_error_percent':.051},{'krf_ack_postamble_ms':18},{'krf_ack_retry_attempts':3},
                  {'krf_repetition_counter':6},{'krf_frame_control':128},{'krf_channel_timeout_ms':1500}):
        assert registry.validate_parameters('knx_rf',{**x,**patch})['status']=='INVALID'
    slow={k:v for k,v in x.items()if k!='krf_echo_timeout_ms'}
    slow.update(krf_channel='S2',krf_carrier_hz=869525000,krf_bitrate_bps=8192,krf_chiprate_cps=16384,
        krf_duty_percent=10,krf_preamble_pairs=4111,krf_ack_slot_ms=10,krf_ack_start_us=600,
        krf_ack_postamble_ms=18,krf_interframe_ms=60,krf_random_ms=39,krf_medium_access_ms=99,krf_channel_timeout_ms=1500)
    assert registry.validate_parameters('knx_rf',slow)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**slow,'krf_ack_slot_ms':5})['status']=='INVALID'
    power={k:v for k,v in slow.items()if k!='krf_duty_percent'}
    power.update(krf_channel='S1',krf_carrier_hz=869850000,krf_tx_erp_mw=5,krf_duty_percent=100)
    assert registry.validate_parameters('knx_rf',power)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**power,'krf_tx_erp_mw':5.000000000000001})['status']=='INVALID'
    assert registry.validate_parameters('knx_rf',{**power,'krf_tx_erp_mw':25,'krf_duty_percent':1})['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**power,'krf_tx_erp_dbm':0,'krf_tx_erp_mw':5})['status']=='INVALID'
    incomplete={k:v for k,v in power.items()if k!='krf_tx_erp_mw'}
    assert registry.validate_parameters('knx_rf',incomplete)['status']=='UNVERIFIED'


def test_knx_rf_bibat_sync_feedback_and_long_header_do_not_reuse_multi_ack_or_fast_phy_defaults():
    x={**KNX_RF_ACTUAL,'krf_variant':'RF1_BIBAT','krf_frame_kind':'BIBAT_DATA','krf_bib_master_role':'MASTER',
       'krf_bib_traffic_direction':'DOWN','krf_bib_schedule_source':'synthetic-commissioned-slot-pattern',
       'krf_bib_slot_ms':62.5,'krf_bib_pause_ms':250,'krf_bib_block_ms':4250,'krf_bib_section_blocks':128,
       'krf_preamble_pairs':16,'krf_preamble_chips':32,'krf_bib_airtime_ms':61,'krf_bib_concatenated_frames':3,
       'krf_bib_clock_error_ppm':99.99,'krf_bib_jitter_us':99.99,'krf_domain_hex':'112233445566','krf_bib_master_serial_hex':'112233445566'}
    assert registry.validate_parameters('knx_rf',x)['status']=='VALID'
    for patch in ({'krf_bib_slot_ms':5},{'krf_bib_block_ms':4000},{'krf_bib_section_blocks':127},
                  {'krf_bib_clock_error_ppm':100},{'krf_bib_jitter_us':100},{'krf_bib_airtime_ms':61.01},
                  {'krf_bib_concatenated_frames':4},{'krf_bib_master_role':'SLAVE'},
                  {'krf_domain_hex':'112233445567'},{'krf_preamble_pairs':15,'krf_preamble_chips':30}):
        assert registry.validate_parameters('knx_rf',{**x,**patch})['status']=='INVALID'
    repeated={**x,'krf_role':'REPEATER','krf_bib_master_role':'SYNCHRONOUS_REPEATER',
       'krf_bib_repeater_number':3,'krf_bib_repeater_delay_ms':250,'krf_received_repetition_counter':6,'krf_repetition_counter':5}
    assert registry.validate_parameters('knx_rf',repeated)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**repeated,'krf_bib_repeater_delay_ms':187.5})['status']=='INVALID'
    feedback={**KNX_RF_ACTUAL,'krf_variant':'RF1_BIBAT2','krf_frame_kind':'BIBAT_FAST_ACK','krf_channel':'F4',
       'krf_carrier_hz':869525000,'krf_deviation_hz':50000,'krf_bandwidth_hz':250000,'krf_duty_percent':10,
       'krf_bib_fastack_wait_ms':300,'krf_bib_fastack_attempts':3,'krf_bib_fastack_master_delay_ms':199.99,'krf_bib_fastack_retry_ms':10}
    assert registry.validate_parameters('knx_rf',feedback)['status']=='VALID'
    for patch in ({'krf_bib_fastack_wait_ms':5},{'krf_bib_fastack_attempts':4},
                  {'krf_bib_fastack_master_delay_ms':200},{'krf_bib_fastack_retry_ms':10.01},{'krf_deviation_hz':60001}):
        assert registry.validate_parameters('knx_rf',{**feedback,**patch})['status']=='INVALID'
    alarm={**KNX_RF_ACTUAL,'krf_variant':'RF1_BIBAT','krf_frame_kind':'LONG_HEADER','krf_long_header_ms':3500,'krf_long_header_wakeup_ms':3400}
    assert registry.validate_parameters('knx_rf',alarm)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**alarm,'krf_long_header_ms':500})['status']=='INVALID'


def test_knx_rf_current_registered_profile_and_secure_commissioning_need_separate_evidence():
    current={**KNX_RF_ACTUAL,'krf_edition':'REGISTERED_EDITION','krf_variant':'MULTI_SLE_REGISTERED',
       'krf_channel':'REGISTERED_CHANNEL','krf_frame_kind':'REGISTERED_SERVICE','krf_bitrate_bps':10000}
    assert registry.validate_parameters('knx_rf',current)['status']=='UNVERIFIED'
    current['krf_registered_profile_source']='synthetic-qualified-current-radio-schema'
    assert registry.validate_parameters('knx_rf',current)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**current,'krf_edition':KNX_RF_EDITION})['status']=='INVALID'
    secure={**KNX_RF_ACTUAL,'krf_data_secure':True,'krf_security_source':'synthetic-commissioned-endpoint-security',
        'krf_group_key_ref':'synthetic-protected-reference','krf_data_secure_key_octets':16}
    assert registry.validate_parameters('knx_rf',secure)['status']=='VALID'
    for key in ('krf_security_source','krf_group_key_ref','krf_data_secure_key_octets'):
        assert registry.validate_parameters('knx_rf',{k:v for k,v in secure.items()if k!=key})['status']=='UNVERIFIED'
    for patch in ({'krf_data_secure_key_octets':32},{'krf_data_secure':False},{'kip_security':'IP_SECURE'}):
        assert registry.validate_parameters('knx_rf',{**secure,**patch})['status']=='INVALID'


def test_knx_rf_confirmed_radio_domain_and_edition_survive_rejected_isolated_sql_wrong_channel_rate():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    saved={'technology':'knx_rf','technology_parameters':{'knx_rf':{'values':KNX_RF_ACTUAL,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in KNX_RF_ACTUAL.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['knx_rf']['values']['krf_bitrate_bps']=8192
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


def test_knx_rf_data_sync_trailer_individual_and_lte_frames_do_not_accept_reserved_formats():
    data={**KNX_RF_ACTUAL,'krf_violation_chips':6,'krf_sync_chips':12,'krf_postamble_chips':8}
    assert registry.validate_parameters('knx_rf',data)['status']=='VALID'
    for patch in ({'krf_violation_chips':5},{'krf_sync_chips':13},{'krf_postamble_chips':1},{'krf_postamble_chips':9}):
        assert registry.validate_parameters('knx_rf',{**data,**patch})['status']=='INVALID'
    individual={**data,'krf_communication':'INDIVIDUAL_CONNECTED','krf_telegram_format':'STANDARD',
        'krf_address_type':0,'krf_address_extension_type':1}
    assert registry.validate_parameters('knx_rf',individual)['status']=='VALID'
    assert registry.validate_parameters('knx_rf',{**individual,'krf_address_type':1})['status']=='INVALID'
    lte={**data,'krf_telegram_format':'LTE_EXTENDED','krf_eff':4,'krf_tpci':0,'krf_transport_sequence':1,
         'krf_lte_instance':255,'krf_address_extension_type':1}
    assert registry.validate_parameters('knx_rf',lte)['status']=='VALID'
    for patch in ({'krf_eff':3},{'krf_eff':8},{'krf_lte_instance':256},{'krf_address_extension_type':0}):
        assert registry.validate_parameters('knx_rf',{**lte,**patch})['status']=='INVALID'
    for kind,control in [('BIBAT_SYNC',80),('BIBAT_HELP',96),('BIBAT_HELP_RESPONSE',112)]:
        control_frame={**KNX_RF_ACTUAL,'krf_variant':'RF1_BIBAT','krf_frame_kind':kind,
            'krf_frame_control':control,'krf_repetition_counter':6}
        assert registry.validate_parameters('knx_rf',control_frame)['status']=='VALID'
        assert registry.validate_parameters('knx_rf',{**control_frame,'krf_frame_control':control+1})['status']=='INVALID'
        assert registry.validate_parameters('knx_rf',{**control_frame,'krf_repetition_counter':2})['status']=='INVALID'


KNX_IP_ACTUAL={**{'kip_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','binding_source','ip_source','application_source','encoding_source',
     'schedule_source','acceptance_source','capacity_source','endpoint_source')},
    'kip_mode':'TUNNELLING','kip_transport':'UDP','kip_security':'PLAIN','kip_profile':'QUALIFIED_DEVICE',
    'kip_direction':'TRANSMITTER','kip_message_kind':'CEMI_DATA'}


def test_knx_ip_has_distinct_transport_services_and_no_inherited_ethernet_phy_payload_or_identity():
    f={v['key']:v for v in registry.parameter_fields('knx_ip')}
    p=registry.profile('knx_ip')
    assert p['domain']=='generic_networking'and p['default_stack']==['knx_ip']
    assert p['capacity_evidence']['status']=='MODEL_MISSING'and p['max_payload_bytes']is None
    assert registry.validate_parameters('knx_ip',KNX_IP_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('knx_ip')['values']=={}
    assert f['kip_port']['default']==3671 and f['kip_header_octets']['default']==6
    assert 'bitrate'not in f and 'mtu_bytes'not in f and 'vlan_id'not in f
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']
    for key in ('channel_id','sequence','individual_address','group_address','serial_hex','local_address','remote_address',
                'user_key_ref','group_key_ref','data_secure','routing_latency_ms','functional_bound_ms'):
        assert 'default'not in f['kip_'+key]and 'conditional_defaults'not in f['kip_'+key]


@pytest.mark.parametrize('field',registry.parameter_fields('knx_ip'),ids=lambda f:'knx_ip/'+f['key'])
def test_each_knx_ip_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('knx_ip',{**KNX_IP_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':100000000},{'mtu_bytes':1500},{'vlan_id':1},{'can_fd_brs':True},
    {'local_timing_evidence':{'i2c_mode':'STANDARD'}},{'j39_priority':6},{'kip_undocumented':1},
    {'kip_transport':'ETHERNET'},{'kip_mode':'I2C'},{'kip_version':32},{'kip_port':0},
    {'kip_hpai_address':'::1'},{'kip_local_address':'2001:db8::1'},{'kip_remote_address':'192.168.1.999'},
    {'kip_tpdu_octets':256},{'kip_secure_sequence':281474976710656},{'kip_secure_key_octets':32},
    {'kip_routing_latency_ms':2000},{'kip_ip_multicast_ttl':64},{'kip_routing_datagrams_s':50},
    {'kip_security_source':'claimed-security'},{'kip_security_confirmed':True}])
def test_knx_ip_rejects_foreign_buses_malformed_addresses_and_inapplicable_wire_or_security_fields(patch):
    assert registry.validate_parameters('knx_ip',{**KNX_IP_ACTUAL,**patch})['status']=='INVALID'


def knx_ip_ldata_fixture():
    return {**KNX_IP_ACTUAL,'kip_version':16,'kip_cemi_format':'L_DATA_STANDARD','kip_tpdu_octets':16,
        'kip_npdu_length':15,'kip_additional_info_octets':0,'kip_cemi_octets':25,'kip_cemi_message_code':17,
        'kip_tunnel_layer':'LINK','kip_tunnel_layer_code':2,'kip_connection_header_octets':4,
        'kip_service_type':1056,'kip_outer_service_type':1056,'kip_service_body_octets':29,
        'kip_inner_packet_octets':35,'kip_packet_octets':35,'kip_header_octets':6}


def test_knx_ip_standard_extended_cemi_inner_service_and_secure_wire_lengths_remain_distinct():
    x=knx_ip_ldata_fixture()
    assert registry.validate_parameters('knx_ip',x)['status']=='VALID'
    for patch in ({'kip_service_type':1328},{'kip_tunnel_layer_code':4},{'kip_tpdu_octets':17},
                  {'kip_npdu_length':16},{'kip_additional_info_octets':1},{'kip_cemi_octets':24},
                  {'kip_service_body_octets':25},{'kip_inner_packet_octets':36},{'kip_packet_octets':73}):
        assert registry.validate_parameters('knx_ip',{**x,**patch})['status']=='INVALID'
    ext={**x,'kip_cemi_format':'L_DATA_EXTENDED','kip_tpdu_octets':255,'kip_npdu_length':254,
         'kip_additional_info_octets':6,'kip_additional_info_source':'synthetic-TLV-layout',
         'kip_cemi_octets':270,'kip_service_body_octets':274,'kip_inner_packet_octets':280,'kip_packet_octets':280}
    assert registry.validate_parameters('knx_ip',ext)['status']=='VALID'
    for patch in ({'kip_tpdu_octets':256},{'kip_npdu_length':255},{'kip_cemi_octets':264}):
        assert registry.validate_parameters('knx_ip',{**ext,**patch})['status']=='INVALID'
    assert registry.validate_parameters('knx_ip',{k:v for k,v in ext.items()if k!='kip_additional_info_source'})['status']=='UNVERIFIED'
    secure={**x,'kip_security':'IP_SECURE','kip_security_source':'synthetic-commissioned-IP-session',
        'kip_secure_key_octets':16,'kip_secure_mac_octets':16,'kip_exchange_key_octets':32,
        'kip_user_key_ref':'synthetic-protected-reference','kip_device_auth_ref':'synthetic-device-auth',
        'kip_user_id':2,'kip_secure_session_id':5,'kip_secure_sequence':281474976710655,
        'kip_serial_hex':'0123456789ab','kip_secure_tag':0,'kip_outer_service_type':2384,'kip_packet_octets':73}
    assert registry.validate_parameters('knx_ip',secure)['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**secure,'kip_data_secure':False})['status']=='VALID'
    for patch in ({'kip_secure_key_octets':32},{'kip_secure_mac_octets':32},{'kip_exchange_key_octets':16},
                  {'kip_outer_service_type':1056},{'kip_packet_octets':35},{'kip_secure_tag':1},
                  {'kip_serial_hex':'01234'},{'kip_user_id':128}):
        assert registry.validate_parameters('knx_ip',{**secure,**patch})['status']=='INVALID'
    for key in ('kip_security_source','kip_user_key_ref','kip_device_auth_ref','kip_user_id'):
        assert registry.validate_parameters('knx_ip',{k:v for k,v in secure.items()if k!=key})['status']=='UNVERIFIED'


def test_knx_ip_routing_uses_selected_ipv4_group_and_not_tunnel_ack_or_inherited_ip_ttl():
    x=knx_ip_ldata_fixture()
    for key in ('kip_tunnel_layer','kip_tunnel_layer_code','kip_connection_header_octets'):x.pop(key)
    x.update(kip_mode='ROUTING',kip_multicast_address='224.0.23.12',kip_port=3671,kip_service_type=1328,
        kip_outer_service_type=1328,kip_service_body_octets=25,kip_inner_packet_octets=31,kip_packet_octets=31,
        kip_knx_hop_count=6,kip_ip_multicast_ttl=64)
    assert registry.validate_parameters('knx_ip',x)['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**x,'kip_multicast_address':'239.255.255.255'})['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**x,'kip_ip_multicast_ttl':0,'kip_knx_hop_count':7})['status']=='VALID'
    for patch in ({'kip_multicast_address':'224.0.23.11'},{'kip_multicast_address':'223.255.255.255'},
                  {'kip_multicast_address':'240.0.0.0'},{'kip_multicast_address':'ff02::1'},
                  {'kip_multicast_address':'224.0.23.12.1'},{'kip_transport':'TCP'},{'kip_port':3672},
                  {'kip_ack_ms':1000},{'kip_message_kind':'IP_ACK'},{'kip_channel_id':1},
                  {'kip_knx_hop_count':8},{'kip_ip_multicast_ttl':256},{'kip_connect_ms':10000}):
        assert registry.validate_parameters('knx_ip',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('knx_ip',{k:v for k,v in x.items()if k!='kip_multicast_address'})['status']=='UNVERIFIED'
    secure={**x,'kip_security':'IP_SECURE','kip_security_source':'actual-domain-commissioning',
         'kip_secure_key_octets':16,'kip_group_key_ref':'synthetic-protected-group-reference',
         'kip_routing_latency_ms':1,'kip_secure_session_id':0,'kip_outer_service_type':2384,'kip_packet_octets':69}
    assert registry.validate_parameters('knx_ip',secure)['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**secure,'kip_routing_latency_ms':8000})['status']=='VALID'
    for patch in ({'kip_routing_latency_ms':0},{'kip_routing_latency_ms':8001},{'kip_secure_session_id':1},
                  {'kip_user_key_ref':'tunnel-reference'},{'kip_user_id':1}):
        assert registry.validate_parameters('knx_ip',{**secure,**patch})['status']=='INVALID'


def test_knx_ip_busy_flow_transmit_receive_ranges_and_address_encoding_are_independent():
    x={**KNX_IP_ACTUAL,'kip_mode':'ROUTING','kip_multicast_address':'224.0.23.12',
       'kip_message_kind':'ROUTING_BUSY','kip_routing_busy_wait_ms':20,'kip_routing_busy_counter':2,
       'kip_routing_random_ms':100,'kip_routing_pause_ms':120,'kip_routing_slow_ms':200,
       'kip_service_type':1330,'kip_service_body_octets':6,'kip_inner_packet_octets':12,
       'kip_outer_service_type':1330,'kip_packet_octets':12}
    assert registry.validate_parameters('knx_ip',x)['status']=='VALID'
    for patch in ({'kip_routing_busy_wait_ms':19},{'kip_routing_busy_wait_ms':101},
                  {'kip_routing_random_ms':101,'kip_routing_pause_ms':121},
                  {'kip_routing_pause_ms':121},{'kip_routing_slow_ms':201}):
        assert registry.validate_parameters('knx_ip',{**x,**patch})['status']=='INVALID'
    received={**x,'kip_direction':'RECEIVER','kip_routing_busy_wait_ms':65535,'kip_routing_pause_ms':65635}
    assert registry.validate_parameters('knx_ip',received)['status']=='VALID'
    addr={**KNX_IP_ACTUAL,'kip_area':15,'kip_line':15,'kip_device':255,'kip_individual_address':65535,
          'kip_group_style':'THREE_LEVEL','kip_main_group':31,'kip_middle_group':7,'kip_sub_group':255,'kip_group_address':65535}
    assert registry.validate_parameters('knx_ip',addr)['status']=='VALID'
    for patch in ({'kip_area':16},{'kip_individual_address':65534},{'kip_sub_group':256},
                  {'kip_middle_group':8},{'kip_group_address':65534}):
        assert registry.validate_parameters('knx_ip',{**addr,**patch})['status']=='INVALID'
    addr.pop('kip_middle_group')
    addr.update(kip_group_style='TWO_LEVEL',kip_sub_group=2047)
    assert registry.validate_parameters('knx_ip',addr)['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**addr,'kip_middle_group':0})['status']=='INVALID'


def test_knx_ip_actual_hpai_udp_tcp_and_qualified_factory_timers_do_not_cross_modes():
    from backend.communication.technologies.knx_ip import SHA
    f={v['key']:v for v in registry.parameter_fields('knx_ip')}
    assert f['kip_ack_ms']['conditional_defaults'][0]['value']==1000
    assert f['kip_ip_multicast_ttl']['conditional_defaults'][0]['value']==64
    x={**KNX_IP_ACTUAL,'kip_profile':'CALIMERO_V2_6_FACTORY','kip_build_commit':SHA,
       'kip_build_source':'synthetic-unchanged-build','kip_unmodified_build':True,
       'kip_hpai_kind':'UDP_NAT_ROUTE_BACK','kip_hpai_address':'0.0.0.0','kip_hpai_port':0,
       'kip_hpai_protocol':1,'kip_ack_ms':1000,'kip_tunnel_attempts':2,'kip_connect_ms':10000,
       'kip_confirmation_ms':3000,'kip_heartbeat_interval_ms':60000,'kip_heartbeat_response_ms':10000,
       'kip_heartbeat_attempts':4,'kip_heartbeat_repeat_ms':1000}
    assert registry.validate_parameters('knx_ip',x)['status']=='VALID'
    for patch in ({'kip_build_commit':'main'},{'kip_unmodified_build':False},{'kip_hpai_port':3671},
                  {'kip_hpai_protocol':2},{'kip_ack_ms':3000},{'kip_tunnel_attempts':1},
                  {'kip_heartbeat_response_ms':60000},{'kip_tcp_connect_ms':5000}):
        assert registry.validate_parameters('knx_ip',{**x,**patch})['status']=='INVALID'
    tcp={k:v for k,v in x.items()if k!='kip_ack_ms'}
    tcp.update(kip_transport='TCP',kip_hpai_kind='TCP_ROUTE_BACK',kip_hpai_protocol=2,kip_tunnel_attempts=1,kip_tcp_connect_ms=5000)
    assert registry.validate_parameters('knx_ip',tcp)['status']=='VALID'
    for patch in ({'kip_hpai_kind':'EXPLICIT_IPV4'},{'kip_hpai_address':'192.0.2.1'},
                  {'kip_tunnel_attempts':2},{'kip_ack_ms':1000},{'kip_message_kind':'IP_ACK'}):
        assert registry.validate_parameters('knx_ip',{**tcp,**patch})['status']=='INVALID'
    objectserver={**KNX_IP_ACTUAL,'kip_message_kind':'OBJECT_SERVER','kip_version':32}
    assert registry.validate_parameters('knx_ip',objectserver)['status']=='VALID'
    assert registry.validate_parameters('knx_ip',{**objectserver,'kip_version':16})['status']=='INVALID'


def test_knx_ip_confirmed_endpoint_and_commissioning_survive_rejected_isolated_sql_foreign_phy():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**KNX_IP_ACTUAL,'kip_hpai_address':'192.0.2.15','kip_hpai_kind':'EXPLICIT_IPV4','kip_hpai_port':51234}
    saved={'technology':'knx_ip','technology_parameters':{'knx_ip':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved)
    before=deepcopy(service.get()['parameters'])
    with pytest.raises(ValueError):service.save_parameters({'technology':'knx_ip','technology_parameters':{
        'knx_ip':{'values':{**values,'bitrate':100000000},'provenance':{}}}})
    assert service.get()['parameters']==before


J1939_ACTUAL={**{'j39_'+key:'synthetic-actual-'+key for key in
    ('data_link_revision','phy_revision','device_source','physical_source','binding_source','dictionary_source','name_source',
     'application_source','encoding_source','schedule_source','acceptance_source','capacity_source')},
    'j39_data_link':'J1939_21','j39_phy_profile':'J1939_11_250K_STP','j39_profile':'QUALIFIED_DEVICE',
    'j39_direction':'TRANSMITTER','j39_service':'APPLICATION','j39_transport':'SINGLE_FRAME',
    'j39_nominal_bitrate_bps':250000,'j39_frame_format':'CEFF_29','j39_frame_phase':'APPLICATION'}


def test_j1939_has_explicit_phy_rates_independent_classic_fd_and_industry_neutral_qualified_proposals():
    f={v['key']:v for v in registry.parameter_fields('j1939')}
    assert registry.profile('j1939')['domain']=='generic_networking'
    assert registry.profile('j1939')['default_stack']==['j1939']
    assert registry.profile('j1939')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.profile('j1939')['max_payload_bytes']is None
    assert registry.parameter_defaults_review('j1939')['values']=={}
    assert registry.validate_parameters('j1939',J1939_ACTUAL)['status']=='VALID'
    assert {p['when']['j39_phy_profile']:p['value']for p in f['j39_nominal_bitrate_bps']['conditional_defaults']}=={
        'J1939_11_250K_STP':250000,'J1939_15_250K_UTP':250000,'J1939_14_500K_CLASSIC':500000,'J1939_17_500K_2M_FD':500000}
    assert f['j39_data_bitrate_bps']['conditional_defaults'][0]['value']==2000000
    for key in ('identity_number','manufacturer_code','industry_group','source_address','preferred_address','claim_confirmed',
                'backbone_m','stub_m','termination_ohm','linux_retry_delay_ms'):
        assert 'default'not in f['j39_'+key]and 'conditional_defaults'not in f['j39_'+key]
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']
    assert 'bitrate'not in f and 'queue_policy'not in f


@pytest.mark.parametrize('field',registry.parameter_fields('j1939'),ids=lambda f:'j1939/'+f['key'])
def test_each_j1939_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('j1939',{**J1939_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':500000},{'can_fd_brs':True},{'nominal_bitrate_bps':250000},
    {'iso_bitrate_bps':250000},{'ip_hop_limit':64},{'j39_undocumented':1},{'j39_data_link':'ISOBUS'},
    {'j39_nominal_bitrate_bps':500000},{'j39_phy_profile':'J1939_14_500K_CLASSIC'},
    {'j39_data_bitrate_bps':2000000},{'j39_brs':True},{'j39_frame_format':'FEFF_29'},
    {'j39_transport':'FD_MULTI_PG'},{'j39_message_octets':9},{'j39_frame_octets':9},
    {'j39_source_address':255},{'j39_destination_address':254},{'j39_priority':8},
    {'j39_name_hex':'FFFFFFFFFFFFFFFF'},{'j39_name_hex':'0000000000000000'},
    {'j39_manufacturer_code':2048},{'j39_industry_group':6},{'j39_tos':2},
    {'j39_etp_offset_packets':0},{'j39_t5_ms':3000},{'j39_bam_interval_ms':50},
    {'j39_data_phase_bits':10}])
def test_j1939_rejects_foreign_buses_classic_fd_mix_bad_identity_and_inapplicable_native_parameters(patch):
    assert registry.validate_parameters('j1939',{**J1939_ACTUAL,**patch})['status']=='INVALID'


def test_j1939_exact_name_identifier_and_explicit_cannot_claim_broadcast_are_consistent():
    name=3+(2<<21)+(4<<32)+(5<<35)+(6<<40)+(7<<49)+(8<<56)+(5<<60)+(1<<63)
    x={**J1939_ACTUAL,'j39_name_hex':f'{name:016x}','j39_identity_number':3,'j39_manufacturer_code':2,
       'j39_ecu_instance':4,'j39_function_instance':5,'j39_function_code':6,'j39_name_reserved_bit':0,
       'j39_system_code':7,'j39_system_instance':8,'j39_industry_group':5,'j39_arbitrary_address_capable':True,
       'j39_pdu_kind':'PDU1','j39_reserved_data_page':0,'j39_data_page':0,'j39_pdu_format':239,
       'j39_pdu_specific':22,'j39_destination_address':22,'j39_source_address':1,'j39_priority':6,
       'j39_pgn':61184,'j39_message_pgn':61184,'j39_can_id':6*67108864+239*65536+22*256+1}
    assert registry.validate_parameters('j1939',x)['status']=='VALID'
    for patch in ({'j39_system_code':8},{'j39_arbitrary_address_capable':False},{'j39_industry_group':2},
                  {'j39_pgn':61185},{'j39_pdu_specific':23},{'j39_can_id':x['j39_can_id']+1}):
        assert registry.validate_parameters('j1939',{**x,**patch})['status']=='INVALID'
    pdu2={**x,'j39_pdu_kind':'PDU2','j39_pdu_format':240,'j39_pdu_specific':1,'j39_destination_address':255,
          'j39_pgn':61441,'j39_message_pgn':61441,'j39_can_id':6*67108864+240*65536+256+1}
    assert registry.validate_parameters('j1939',pdu2)['status']=='VALID'
    claim={**J1939_ACTUAL,'j39_service':'ADDRESS_CLAIM','j39_claim_state':'CANNOT_CLAIM',
        'j39_source_address':254,'j39_destination_address':255,'j39_pgn':60928,'j39_message_octets':8}
    assert registry.validate_parameters('j1939',claim)['status']=='VALID'
    for patch in ({'j39_destination_address':22},{'j39_source_address':255},{'j39_pgn':61184},{'j39_service':'APPLICATION'}):
        assert registry.validate_parameters('j1939',{**claim,**patch})['status']=='INVALID'


def test_j1939_classic_tp_and_optional_etp_do_not_inherit_fd_session_limits_or_assume_isobus_application():
    x={**J1939_ACTUAL,'j39_transport':'TP_BAM','j39_frame_phase':'TP_DT','j39_destination_address':255,
       'j39_message_octets':1785,'payload_bytes':1785,'j39_data_frames':255,'j39_frame_octets':8,
       'j39_transport_data_octets':7,'j39_pgn':60160,'j39_bam_interval_ms':50,'j39_active_sessions':1}
    assert registry.validate_parameters('j1939',x)['status']=='VALID'
    for patch in ({'j39_message_octets':1786,'payload_bytes':1786},{'j39_data_frames':254},
                  {'j39_destination_address':22},{'j39_transport_data_octets':8},{'j39_active_sessions':2},
                  {'j39_bam_interval_ms':10},{'j39_bam_interval_ms':201},{'j39_pgn':60416}):
        assert registry.validate_parameters('j1939',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('j1939',{**x,'j39_direction':'RECEIVER','j39_active_sessions':4})['status']=='VALID'
    connection={k:v for k,v in x.items()if k!='j39_bam_interval_ms'}
    connection.update(j39_transport='TP_CONNECTION',j39_destination_address=22,j39_active_sessions=2,j39_cts_packets=0)
    assert registry.validate_parameters('j1939',connection)['status']=='VALID'
    etp={**J1939_ACTUAL,'j39_transport':'ETP_EXTENSION','j39_frame_phase':'ETP_DT','j39_destination_address':22,
         'j39_message_octets':117440505,'payload_bytes':117440505,'j39_data_frames':16777215,
         'j39_etp_offset_packets':16777100,'j39_etp_sequence':115,'j39_segment_number':16777215,
         'j39_etp_enabled':True,'j39_etp_source':'actual-explicit-extension'}
    assert registry.validate_parameters('j1939',etp)['status']=='VALID'
    for patch in ({'j39_etp_enabled':False},{'j39_destination_address':255},{'j39_message_octets':1785,'payload_bytes':1785},
                  {'j39_message_octets':117440506,'payload_bytes':117440506},{'j39_segment_number':16777214}):
        assert registry.validate_parameters('j1939',{**etp,**patch})['status']=='INVALID'


def test_j1939_fd_uses_60byte_segments_24bit_length_and_distinct_bam_connection_session_limits():
    fd={**J1939_ACTUAL,'j39_data_link':'J1939_22','j39_phy_profile':'J1939_17_500K_2M_FD',
        'j39_nominal_bitrate_bps':500000,'j39_data_bitrate_bps':2000000,'j39_frame_format':'FEFF_29',
        'j39_fd_source':'actual-fd-hardware','j39_transport':'FD_TP_BAM','j39_frame_phase':'FD_DT',
        'j39_destination_address':255,'j39_message_octets':15300,'payload_bytes':15300,'j39_data_frames':255,
        'j39_segment_number':255,'j39_transport_data_octets':60,'j39_frame_octets':64,'j39_pgn':19968,
        'j39_fd_session_id':3,'j39_active_sessions':4,'j39_bam_interval_ms':10}
    assert registry.validate_parameters('j1939',fd)['status']=='VALID'
    for patch in ({'j39_message_octets':15301,'payload_bytes':15301},{'j39_fd_session_id':4},
                  {'j39_active_sessions':5},{'j39_destination_address':22},{'j39_bam_interval_ms':9},
                  {'j39_data_frames':254},{'j39_segment_number':256},{'j39_frame_octets':63},
                  {'j39_transport_data_octets':61},{'j39_data_bitrate_bps':1000000},{'j39_frame_phase':'TP_DT'}):
        assert registry.validate_parameters('j1939',{**fd,**patch})['status']=='INVALID'
    connection={k:v for k,v in fd.items()if k!='j39_bam_interval_ms'}
    connection.update(j39_transport='FD_TP_CONNECTION',j39_destination_address=22,j39_message_octets=16777215,
        payload_bytes=16777215,j39_data_frames=279621,j39_segment_number=279621,j39_fd_session_id=7,j39_active_sessions=8)
    assert registry.validate_parameters('j1939',connection)['status']=='VALID'
    for patch in ({'j39_message_octets':16777216,'payload_bytes':16777216},{'j39_data_frames':279620},
                  {'j39_fd_session_id':8},{'j39_active_sessions':9},{'j39_destination_address':255}):
        assert registry.validate_parameters('j1939',{**connection,**patch})['status']=='INVALID'


def test_j1939_multi_pg_counts_service_headers_and_minimal_representable_fd_dlc_padding():
    x={**J1939_ACTUAL,'j39_data_link':'J1939_22','j39_phy_profile':'J1939_17_500K_2M_FD',
        'j39_nominal_bitrate_bps':500000,'j39_data_bitrate_bps':2000000,'j39_frame_format':'FEFF_29',
        'j39_fd_source':'actual-fd-hardware','j39_transport':'FD_MULTI_PG','j39_frame_phase':'MULTI_PG',
        'j39_message_octets':60,'payload_bytes':60,'j39_cpg_octets':60,'j39_cpg_count':1,
        'j39_cpg_total_octets':60,'j39_container_octets':64,'j39_frame_octets':64,'j39_padding_octets':0,'j39_pgn':9472}
    assert registry.validate_parameters('j1939',x)['status']=='VALID'
    for patch in ({'j39_cpg_count':2},{'j39_message_octets':61,'payload_bytes':61},
                  {'j39_cpg_octets':59},{'j39_pgn':61184},{'j39_frame_octets':60},{'j39_padding_octets':1}):
        assert registry.validate_parameters('j1939',{**x,**patch})['status']=='INVALID'
    two={**x,'j39_message_octets':8,'payload_bytes':8,'j39_cpg_octets':8,'j39_cpg_count':2,
         'j39_cpg_total_octets':16,'j39_container_octets':24,'j39_frame_octets':24}
    assert registry.validate_parameters('j1939',two)['status']=='VALID'
    assert registry.validate_parameters('j1939',{**two,'j39_frame_octets':32,'j39_padding_octets':8})['status']=='INVALID'
    padded={**two,'j39_cpg_count':1,'j39_message_octets':5,'payload_bytes':5,'j39_cpg_octets':5,
            'j39_cpg_total_octets':5,'j39_container_octets':9,'j39_frame_octets':12,'j39_padding_octets':3}
    assert registry.validate_parameters('j1939',padded)['status']=='VALID'


def test_j1939_linux_and_python_defaults_are_version_qualified_and_privileges_assurance_not_inferred():
    from backend.communication.technologies.j1939 import SHA
    f={v['key']:v for v in registry.parameter_fields('j1939')}
    assert f['j39_cts_packets']['conditional_defaults'][0]['value']==1
    assert f['j39_linux_tx_queue_retries']['conditional_defaults'][0]['value']==100
    assert f['j39_bam_interval_ms']['conditional_defaults'][2]['value']==10
    linux={**J1939_ACTUAL,'j39_profile':'LINUX_V6_6_FACTORY','j39_build_commit':'v6.6',
           'j39_build_source':'actual-linux-build','j39_unmodified_build':True,'j39_priority':6,'j39_socket_priority':1}
    assert registry.validate_parameters('j1939',linux)['status']=='VALID'
    assert registry.validate_parameters('j1939',{**linux,'j39_socket_priority':6})['status']=='INVALID'
    assert registry.validate_parameters('j1939',{**linux,'j39_priority':1,'j39_socket_priority':6})['status']=='UNVERIFIED'
    assert registry.validate_parameters('j1939',{**linux,'j39_priority':1,'j39_socket_priority':6,'j39_cap_net_admin':True})['status']=='VALID'
    assert registry.validate_parameters('j1939',{**linux,'j39_destination_address':255,'j39_so_broadcast':False})['status']=='INVALID'
    assert registry.validate_parameters('j1939',{**linux,'j39_destination_address':255,'j39_so_broadcast':True})['status']=='VALID'
    py={**J1939_ACTUAL,'j39_profile':'PYTHON_CAN_01ABA95_FACTORY','j39_build_commit':SHA,
        'j39_build_source':'actual-python-build','j39_unmodified_build':True,'j39_t1_ms':750}
    assert registry.validate_parameters('j1939',py)['status']=='VALID'
    for patch in ({'j39_build_commit':'main'},{'j39_unmodified_build':False},{'j39_t1_ms':751},
                  {'j39_linux_tp_padding':True},{'j39_transport':'ETP_EXTENSION'},{'j39_name_reserved_bit':1}):
        assert registry.validate_parameters('j1939',{**py,**patch})['status']=='INVALID'
    fd={**py,'j39_data_link':'J1939_22','j39_phy_profile':'J1939_17_500K_2M_FD',
        'j39_nominal_bitrate_bps':500000,'j39_data_bitrate_bps':2000000,'j39_frame_format':'FEFF_29',
        'j39_fd_source':'actual-fd-hardware','j39_transport':'FD_MULTI_PG','j39_frame_phase':'MULTI_PG',
        'j39_tos':2,'j39_trailer_format':0,'j39_ad_type':0,'j39_assurance_mode':'NONE','j39_brs':True}
    assert registry.validate_parameters('j1939',fd)['status']=='VALID'
    for patch in ({'j39_frame_format':'FBFF_11'},{'j39_tos':3},{'j39_trailer_format':1},
                  {'j39_ad_type':1},{'j39_assurance_mode':'REGISTERED_SAE_FUSA','j39_assurance_source':'real-safety-source'},
                  {'j39_brs':False}):
        assert registry.validate_parameters('j1939',{**fd,**patch})['status']=='INVALID'


def test_j1939_confirmed_phy_address_and_dictionary_survive_rejected_isolated_sql_foreign_rate():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    saved={'technology':'j1939','technology_parameters':{'j1939':{'values':J1939_ACTUAL,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in J1939_ACTUAL.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['j1939']['values']['j39_nominal_bitrate_bps']=1000000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


ISOBUS_ACTUAL={**{'iso_'+key:'synthetic-actual-'+key for key in
    ('part3_revision','device_source','physical_source','binding_source','pgn_source','name_source','application_source','schedule_source','acceptance_source','capacity_source')},
    'iso_path':'CLASSIC_CAN','iso_profile':'QUALIFIED_DEVICE','iso_direction':'TRANSMITTER',
    'iso_service':'PROCESS_DATA','iso_transport':'SINGLE_FRAME','iso_bitrate_bps':250000,'iso_frame_phase':'APPLICATION'}


def test_isobus_is_industry_neutral_fixed_classic_can_without_a_universal_tp_payload_ceiling():
    f={v['key']:v for v in registry.parameter_fields('isobus')}
    assert registry.profile('isobus')['domain']=='generic_networking'
    assert registry.profile('isobus')['default_stack']==['isobus']
    assert registry.profile('isobus')['max_payload_bytes']is None
    assert registry.profile('isobus')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('isobus')['values']=={}
    assert registry.validate_parameters('isobus',ISOBUS_ACTUAL)['status']=='VALID'
    assert f['iso_bitrate_bps']['default']==250000
    assert f['iso_frame_format']['default']=='CLASSIC_EXTENDED_29'
    assert 'bitrate'not in f and 'queue_policy'not in f
    for key in ('identity_number','manufacturer_code','industry_group','preferred_address','claim_random_delay_ms','supply_v','termination_count','claim_confirmed'):
        assert 'default'not in f['iso_'+key]
    assert 'max'not in f['payload_bytes']and 'default'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('isobus'),ids=lambda f:'isobus/'+f['key'])
def test_each_isobus_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('isobus',{**ISOBUS_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':500000},{'can_fd_brs':True},{'nominal_bitrate_bps':250000},
    {'ip_hop_limit':64},{'iolw_bitrate_bps':1000000},{'iso_undocumented':1},{'iso_path':'HIGH_SPEED_ETHERNET'},
    {'iso_bitrate_bps':1000000},{'iso_frame_format':'FD_EXTENDED_29'},{'iso_fd_enabled':True},{'iso_brs':True},
    {'iso_source_address':255},{'iso_destination_address':254},{'iso_priority':8},{'iso_can_id':536870912},
    {'iso_pgn':262144},{'iso_manufacturer_code':2048},{'iso_identity_number':2097152},
    {'iso_function_instance':32},{'iso_ecu_instance':8},{'iso_industry_group':6},
    {'iso_message_octets':9},{'iso_frame_octets':9},{'iso_bam_interval_ms':50},
    {'iso_name_hex':'FFFFFFFFFFFFFFFF'},{'iso_name_hex':'1234'},{'iso_backbone_m':41}])
def test_isobus_rejects_foreign_industry_or_link_defaults_bad_identifiers_and_nonclassic_frames(patch):
    assert registry.validate_parameters('isobus',{**ISOBUS_ACTUAL,**patch})['status']=='INVALID'


def test_isobus_identifier_pdu1_destination_pdu2_group_extension_and_exact64bit_name_components():
    x={**ISOBUS_ACTUAL,'iso_pdu_kind':'PDU1','iso_extended_data_page':0,'iso_data_page':0,
       'iso_pdu_format':239,'iso_pdu_specific':22,'iso_destination_address':22,'iso_source_address':1,
       'iso_priority':6,'iso_pgn':61184,'iso_message_pgn':61184,'iso_can_id':6*67108864+239*65536+22*256+1,
       'iso_message_octets':8,'payload_bytes':8,'iso_frame_octets':8}
    name=3+(2<<21)+(4<<32)+(5<<35)+(6<<40)+(7<<49)+(8<<56)+(2<<60)+(1<<63)
    x.update(iso_name_hex=f'{name:016x}',iso_identity_number=3,iso_manufacturer_code=2,iso_ecu_instance=4,
       iso_function_instance=5,iso_function_code=6,iso_name_reserved_bit=0,iso_device_class=7,
       iso_device_class_instance=8,iso_industry_group=2,iso_arbitrary_address_capable=True)
    assert registry.validate_parameters('isobus',x)['status']=='VALID'
    for patch in ({'iso_pgn':61185},{'iso_pdu_specific':23},{'iso_can_id':x['iso_can_id']+1},
                  {'iso_manufacturer_code':3},{'iso_arbitrary_address_capable':False},
                  {'iso_industry_group':1},{'iso_frame_octets':7},{'iso_message_pgn':61185}):
        assert registry.validate_parameters('isobus',{**x,**patch})['status']=='INVALID'
    pdu2={**x,'iso_pdu_kind':'PDU2','iso_pdu_format':240,'iso_pdu_specific':1,'iso_destination_address':255,
          'iso_pgn':61441,'iso_message_pgn':61441,'iso_can_id':6*67108864+240*65536+256+1}
    assert registry.validate_parameters('isobus',pdu2)['status']=='VALID'
    assert registry.validate_parameters('isobus',{**pdu2,'iso_destination_address':22})['status']=='INVALID'


def test_isobus_tp_bam_and_connection_have_separate_admission_pacing_and_seven_byte_data():
    x={**ISOBUS_ACTUAL,'iso_transport':'TP_BAM','iso_frame_phase':'TP_DT','iso_destination_address':255,
       'iso_message_octets':1785,'payload_bytes':1785,'iso_data_frames':255,'iso_frame_octets':8,
       'iso_transport_data_octets':7,'iso_pgn':60160,'iso_bam_interval_ms':10,'iso_max_sessions':4,'iso_active_sessions':1}
    assert registry.validate_parameters('isobus',x)['status']=='VALID'
    for patch in ({'iso_message_octets':1786,'payload_bytes':1786},{'iso_data_frames':254},
                  {'iso_destination_address':22},{'iso_frame_octets':7},{'iso_pgn':60416},
                  {'iso_bam_interval_ms':9},{'iso_bam_interval_ms':201},{'iso_transport_data_octets':8},
                  {'iso_active_sessions':2},{'iso_max_sessions':0}):
        assert registry.validate_parameters('isobus',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('isobus',{**x,'iso_direction':'RECEIVER','iso_active_sessions':4})['status']=='VALID'
    connection={k:v for k,v in x.items()if k!='iso_bam_interval_ms'}
    connection.update(iso_transport='TP_CONNECTION',iso_destination_address=22,iso_active_sessions=2,iso_cts_packets=0)
    assert registry.validate_parameters('isobus',connection)['status']=='VALID'
    assert registry.validate_parameters('isobus',{**connection,'iso_destination_address':255})['status']=='INVALID'


def test_isobus_etp_large_payload_and_gnss_fastpacket32frames_do_not_inherit_tp1785_or_whole_nmea_profile():
    etp={**ISOBUS_ACTUAL,'iso_transport':'ETP','iso_frame_phase':'ETP_DT','iso_destination_address':22,
         'iso_message_octets':117440505,'payload_bytes':117440505,'iso_data_frames':16777215,
         'iso_etp_offset_packets':16777100,'iso_tp_sequence':115,'iso_absolute_packet':16777215}
    assert registry.validate_parameters('isobus',etp)['status']=='VALID'
    for patch in ({'iso_message_octets':1785,'payload_bytes':1785},{'iso_message_octets':117440506,'payload_bytes':117440506},
                  {'iso_destination_address':255},{'iso_absolute_packet':16777214},{'iso_data_frames':16777214}):
        assert registry.validate_parameters('isobus',{**etp,**patch})['status']=='INVALID'
    fp={**ISOBUS_ACTUAL,'iso_transport':'GNSS_FAST_PACKET','iso_service':'GNSS_FAST_PACKET',
        'iso_frame_phase':'FP_FIRST','iso_pgn':129029,'iso_message_octets':223,'payload_bytes':223,
        'iso_data_frames':32,'iso_fp_sequence':7,'iso_fp_frame_counter':0}
    assert registry.validate_parameters('isobus',fp)['status']=='VALID'
    for patch in ({'iso_message_octets':224,'payload_bytes':224},{'iso_data_frames':31},{'iso_fp_frame_counter':1},
                  {'iso_pgn':61184},{'iso_service':'FILE_SERVER'},{'iso_fp_sequence':8}):
        assert registry.validate_parameters('isobus',{**fp,**patch})['status']=='INVALID'


def test_isobus_library_defaults_and_address_arbitration_are_commit_and_name_group_qualified():
    from backend.communication.technologies.isobus import SHA
    f={v['key']:v for v in registry.parameter_fields('isobus')}
    for key,value in [('max_sessions',4),('frames_per_update',255),('cts_packets',16),('dpo_packets',16),('bam_interval_ms',50),('t1_ms',750)]:
        p=f['iso_'+key]['conditional_defaults'][0]
        assert p['value']==value and p['when']['iso_build_commit']==SHA and p['when']['iso_unmodified_build']is True
    assert {p['when']['iso_industry_group']:p['value']for p in f['iso_arbitration_end_address']['conditional_defaults']}=={0:247,1:158,2:235,3:207,4:207,5:207}
    factory={**ISOBUS_ACTUAL,'iso_profile':'AGISOSTACK_40EFE24_FACTORY','iso_build_commit':SHA,
             'iso_build_source':'actual-pinned-build','iso_unmodified_build':True,'iso_claim_contention_ms':250}
    assert registry.validate_parameters('isobus',factory)['status']=='VALID'
    for patch in ({'iso_build_commit':'main'},{'iso_unmodified_build':False},{'iso_claim_contention_ms':249},
                  {'iso_t1_ms':751},{'iso_preferred_address':254,'iso_arbitrary_address_capable':False}):
        assert registry.validate_parameters('isobus',{**factory,**patch})['status']=='INVALID'
    claim={**ISOBUS_ACTUAL,'iso_service':'ADDRESS_CLAIM','iso_claim_state':'CANNOT_CLAIM','iso_source_address':254,'iso_message_octets':8}
    assert registry.validate_parameters('isobus',claim)['status']=='VALID'
    assert registry.validate_parameters('isobus',{**claim,'iso_service':'PROCESS_DATA'})['status']=='INVALID'


def test_isobus_confirmed_address_and_transport_choices_survive_rejected_isolated_sql_clock_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id());values={**ISOBUS_ACTUAL,'iso_source_address':22,'iso_claim_state':'CLAIMED'}
    saved={'technology':'isobus','technology_parameters':{'isobus':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['isobus']['values']['iso_bitrate_bps']=500000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IP_ACTUAL={**{'ip_'+key:'synthetic-actual-'+key for key in
    ('interface_binding','lower_path_source','address_source','implementation_source','encoding_source','pmtu_source','schedule_source','acceptance_source')},
    'ip_version':'IPv4','ip_role':'SOURCE','ip_packet_kind':'WHOLE','ip_destination_kind':'UNICAST',
    'ip_lower_path_kind':'OTHER_REGISTERED_LINK','ip_source_address':'192.0.2.1','ip_destination_address':'198.51.100.2'}


def test_ip_has_no_phy_bitrate_ethernet_binding_or_universal65535_application_limit():
    f={v['key']:v for v in registry.parameter_fields('ip')}
    assert registry.profile('ip')['default_stack']==['ip']
    assert registry.profile('ip')['max_payload_bytes']is None
    assert registry.profile('ip')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('ip')['values']=={}
    assert registry.validate_parameters('ip',IP_ACTUAL)['status']=='VALID'
    assert f['ip_dscp']['default']==0
    assert f['ip_ttl']['conditional_defaults'][0]['value']==64
    assert 'historical'in f['ip_ttl']['source_revision']
    mtu=f['ip_link_mtu_octets']['conditional_defaults'][0]
    assert mtu['when']=={'ip_version':'IPv6','ip_lower_path_kind':'ETHERNET'}and mtu['value']==1500
    assert 'bitrate'not in f and 'queue_policy'not in f
    for key in ('path_mtu_octets','peer_reassembly_octets','source_address','next_hop_address','hop_limit','flow_label','capacity_confirmed'):
        assert 'default'not in f['ip_'+key]
    assert 'max'not in f['payload_bytes']and 'default'not in f['payload_bytes']


@pytest.mark.parametrize('field',registry.parameter_fields('ip'),ids=lambda f:'ip/'+f['key'])
def test_each_ip_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('ip',{**IP_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':100000000},{'can_fd_brs':True},{'iolw_bitrate_bps':1000000},
    {'ip_undocumented':1},{'ip_source_address':'999.1.2.3'},{'ip_destination_address':'2001:db8::1'},
    {'ip_prefix_bits':33},{'ip_ihl_words':4},{'ip_ihl_words':16},{'ip_options_octets':3},
    {'ip_ttl':0},{'ip_ttl':256},{'ip_protocol_number':256},{'ip_identification':65536},
    {'ip_header_checksum':65536},{'ip_ipv4_flags_reserved':1},{'ip_dscp':64},{'ip_ecn_bits':4},
    {'ip_flow_label':0},{'ip_hop_limit':64},{'ip_payload_mode':'NORMAL'},
    {'ip_dont_fragment':True,'ip_more_fragments':True}])
def test_ip_rejects_foreign_link_can_and_mixed_ipv4_ipv6_headers(patch):
    assert registry.validate_parameters('ip',{**IP_ACTUAL,**patch})['status']=='INVALID'


def test_ipv4_header_lengths_dscp_ecn_path_mtu_and_payload_lengths_use_their_own_units():
    x={**IP_ACTUAL,'ip_ihl_words':6,'ip_options_octets':4,'ip_options_source':'actual-options-padding',
       'ip_header_octets':24,'ip_payload_octets':1476,'ip_packet_octets':1500,'ip_link_mtu_octets':1500,
       'ip_path_mtu_octets':1500,'ip_ttl':64,'ip_forward_hops':3,'ip_dscp':46,'ip_ecn_mode':'ECT_0',
       'ip_ecn_bits':2,'ip_traffic_class':186,'ip_ecn_transport_capable':True,'ip_ecn_source':'actual-upper-ECN'}
    assert registry.validate_parameters('ip',x)['status']=='VALID'
    for patch in ({'ip_header_octets':20},{'ip_payload_octets':1477},{'ip_packet_octets':1501},
                  {'ip_path_mtu_octets':1600},{'ip_ttl':3},{'ip_ecn_bits':1},
                  {'ip_traffic_class':184},{'ip_ecn_transport_capable':False}):
        assert registry.validate_parameters('ip',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('ip',{**x,'ip_options_source':''})['status']=='UNVERIFIED'
    assert registry.validate_parameters('ip',{**x,'ip_ecn_source':''})['status']=='UNVERIFIED'


def ipv6_parameters():
    return {**IP_ACTUAL,'ip_version':'IPv6','ip_source_address':'2001:db8::1','ip_destination_address':'2001:db8::2',
       'ip_payload_mode':'NORMAL','ip_header_octets':40,'ip_payload_octets':1280,'ip_payload_length_field':1280,
       'ip_packet_octets':1320,'ip_link_mtu_octets':1500,'ip_path_mtu_octets':1500,'ip_extension_octets':8,
       'ip_extensions_source':'actual-ordered-extensions','ip_next_header':0,'ip_reassembly_timeout_s':60,
       'ip_hop_limit':64,'ip_forward_hops':3,'ip_flow_assignment_enabled':True,'ip_flow_label':1234,'ip_flow_source':'actual-flow-policy'}


def test_ipv6_base_header_extension_payload_and_source_only_fragment_fields_are_separate():
    x=ipv6_parameters();assert registry.validate_parameters('ip',x)['status']=='VALID'
    for patch in ({'ip_source_address':'192.0.2.1'},{'ip_destination_kind':'BROADCAST'},
                  {'ip_header_octets':20},{'ip_payload_length_field':1240},{'ip_extension_octets':1281},
                  {'ip_payload_octets':65536},{'ip_link_mtu_octets':1279},{'ip_path_mtu_octets':1279},
                  {'ip_reassembly_timeout_s':120},{'ip_header_checksum':0},{'ip_ttl':64},
                  {'ip_flow_label':1048576},{'ip_flow_assignment_enabled':False},
                  {'ip_hop_limit':3},{'ip_role':'FORWARDER','ip_hop_limit':0}):
        assert registry.validate_parameters('ip',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('ip',{**x,'ip_role':'DESTINATION','ip_hop_limit':0})['status']=='VALID'
    fragment={**x,'ip_packet_kind':'FRAGMENT','ip_fragment_header_present':True,'ip_fragment_header_octets':8,
       'ip_fragment_offset_units':0,'ip_fragment_offset_octets':0,'ip_fragment_data_octets':1200,
       'ip_more_fragments':True,'ip_identification':4294967295,'ip_fragment_source':'actual-disjoint-fragments',
       'ip_no_fragment_overlap':True,'ip_first_fragment_headers_complete':True}
    assert registry.validate_parameters('ip',fragment)['status']=='VALID'
    for patch in ({'ip_fragment_header_present':False},{'ip_fragment_data_octets':1201},
                  {'ip_fragment_offset_octets':8},{'ip_no_fragment_overlap':False},
                  {'ip_first_fragment_headers_complete':False},{'ip_ipv6_fragment_reserved':1}):
        assert registry.validate_parameters('ip',{**fragment,**patch})['status']=='INVALID'


def test_ipv6_jumbogram32bit_length_requires_actual_peer_link_support_and_excludes_fragments():
    x={**ipv6_parameters(),'ip_payload_mode':'JUMBO','ip_payload_octets':70000,'ip_packet_octets':70040,
       'ip_payload_length_field':0,'ip_jumbo_payload_octets':70000,'ip_jumbo_option_type':194,
       'ip_jumbo_option_length':4,'ip_jumbo_supported':True,'ip_jumbo_source':'actual-peer-link-codec-jumbo',
       'ip_link_mtu_octets':72000,'ip_path_mtu_octets':71000,'ip_fragment_header_present':False}
    assert registry.validate_parameters('ip',x)['status']=='VALID'
    for patch in ({'ip_payload_length_field':1},{'ip_jumbo_payload_octets':65535},
                  {'ip_payload_octets':69999},{'ip_next_header':6},{'ip_jumbo_supported':False},
                  {'ip_fragment_header_present':True},{'ip_packet_kind':'FRAGMENT'},
                  {'ip_jumbo_option_type':195},{'ip_extension_octets':0},{'ip_path_mtu_octets':70000}):
        assert registry.validate_parameters('ip',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('ip',{**x,'ip_jumbo_source':''})['status']=='UNVERIFIED'


def test_ipv4_confirmed_datagram_parameters_survive_rejected_isolated_sql_family_switch():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id());values={**IP_ACTUAL,'ip_ttl':128}
    saved={'technology':'ip','technology_parameters':{'ip':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['ip']['values']['ip_version']='IPv6'
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


def test_ip_layer_parameter_scope_does_not_claim_an_unconfigured_conventional_stack_is_verified():
    upper={'bitrate':100000000,'duplex':'FULL','payload_bytes':17,'afdx_lmax_frame_bytes':64}
    result=registry.validate_parameters('afdx',upper)
    assert result['status']=='VALID'and result['validation_scope']=='DECLARED_PROFILE_PARAMETERS'
    assert result['unverified_stack_layers']==['ip']
    assert result['stack_parameter_completeness']=='UNVERIFIED'
    configured={**upper,**IP_ACTUAL,'ip_ttl':64}
    result=registry.validate_parameters('afdx',configured)
    assert result['status']=='VALID'and result['unverified_stack_layers']==[]
    assert registry.validate_parameters('afdx',{**configured,'ip_hop_limit':64})['status']=='INVALID'
    assert registry.validate_parameters('afdx',{**upper,'ip_version':'IPv4'})['status']=='UNVERIFIED'


IOLW_ACTUAL={**{'iolw_'+key:'synthetic-actual-'+key for key in
    ('device_source','master_source','iodd_source','binding_source','radio_source','hopping_source','encoding_source',
     'schedule_source','acceptance_source','power_source','crc_source','capacity_source')},
    'iolw_specification':'V1_1_3_CORR1','iolw_role':'W_DEVICE','iolw_mode':'CYCLIC','iolw_direction':'UPLINK',
    'iolw_packet_kind':'UPLINK_SSLOT','iolw_device_mode':'NORMAL','iolw_bitrate_bps':1000000,
    'iolw_slot_type':'SSLOT','iolw_device_distinguisher':1234,'iolw_crc32_initial_rule':'XOR_DEVICE_DISTINGUISHER'}


def test_wireless_io_link_radio_defaults_are_distinct_from_wired_com_and_actual_capacity():
    f={v['key']:v for v in registry.parameter_fields('io_link_wireless')}
    assert registry.validate_parameters('io_link_wireless',IOLW_ACTUAL)['status']=='VALID'
    assert registry.profile('io_link_wireless')['domain']=='generic_networking'
    assert registry.profile('io_link_wireless')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.profile('io_link_wireless')['max_payload_bytes']is None
    assert registry.parameter_defaults_review('io_link_wireless')['values']=={}
    assert f['iolw_bitrate_bps']['default']==1000000
    assert f['iolw_max_retry']['default']==2
    assert f['iolw_data_syncword']['default']=='3E9459'
    assert f['iolw_modulation_index']['default']==.5
    assert 'bitrate'not in f and 'queue_policy'not in f
    for key in ('master_id','track_count','slot_index','ima_time_ms','tx_power_level','tx_eirp_dbm','paired','rf_confirmed','application_cycle_ms'):
        assert 'default'not in f['iolw_'+key]
    assert 'max'not in f['payload_bytes']and 'default'not in f['payload_bytes']
    for key in ('scan_timeout_ms','unique_pair_timeout_ms','button_pair_timeout_ms'):
        assert all(p['when']['iolw_mode'].startswith('SERVICE_')for p in f['iolw_'+key]['conditional_defaults'])


@pytest.mark.parametrize('field',registry.parameter_fields('io_link_wireless'),ids=lambda f:'io_link_wireless/'+f['key'])
def test_each_wireless_io_link_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'undocumented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('io_link_wireless',{**IOLW_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':500000},{'can_fd_brs':True},{'iol_com_mode':'COM1'},
    {'iolw_bitrate_bps':230400},{'iolw_bitrate_bps':2000000},{'iolw_undocumented':1},
    {'iolw_master_id':0},{'iolw_master_id':30},{'iolw_frequency_channel':2},{'iolw_frequency_channel':79},
    {'iolw_track_count':6},{'iolw_slot_index':8},{'iolw_max_retry':1},{'iolw_max_retry':32},
    {'iolw_subcycle_us':5000},{'iolw_modulation_index':.56},{'iolw_tx_eirp_dbm':11},
    {'iolw_carrier_error_ppm':21},{'iolw_receiver_sensitivity_dbm':-90},{'iolw_isdu_record_octets':233},
    {'iolw_isdu_total_octets':239},{'iolw_pd_input_octets':33},{'iolw_isdu_supported':False},
    {'iolw_specification':'D1_1_4'},{'iolw_direction':'DOWNLINK'},{'iolw_slot_type':'DSLOT'},
    {'iolw_packet_octets':25},{'iolw_packet_payload_octets':3},{'iolw_uplink_user_octets':2}])
def test_wireless_io_link_rejects_foreign_parameters_invalid_radio_or_wrong_single_slot_layout(patch):
    assert registry.validate_parameters('io_link_wireless',{**IOLW_ACTUAL,**patch})['status']=='INVALID'


def test_wireless_tracks_double_slots_and_whole_pd_are_independent():
    x={**IOLW_ACTUAL,'iolw_packet_kind':'UPLINK_DSLOT','iolw_slot_type':'DSLOT','iolw_slot_index':6,
       'iolw_slot_tx_us':200,'iolw_slot_with_guard_us':208,'iolw_packet_octets':25,'iolw_packet_payload_octets':15,
       'iolw_uplink_user_octets':14,'iolw_pd_input_octets':32,'iolw_track_count':2,'iolw_track_index':1,
       'iolw_single_slots':2,'iolw_double_slots':3,'iolw_track_devices':5,'iolw_total_devices':10,
       'iolw_frequency_channel':3,'iolw_carrier_mhz':2403,'iolw_blocklist':'01'+'0'*76+'10'}
    assert registry.validate_parameters('io_link_wireless',x)['status']=='VALID'
    for patch in ({'iolw_slot_index':5},{'iolw_slot_tx_us':208},{'iolw_slot_with_guard_us':200},
                  {'iolw_packet_octets':26},{'iolw_uplink_user_octets':15},{'iolw_track_index':2},
                  {'iolw_single_slots':3},{'iolw_track_devices':6},{'iolw_total_devices':17},
                  {'iolw_carrier_mhz':2404},{'iolw_blocklist':'0'*80}):
        assert registry.validate_parameters('io_link_wireless',{**x,**patch})['status']=='INVALID'


def test_wireless_retry_ima_nominal_application_cycles_and_free_running_have_distinct_units():
    x={**IOLW_ACTUAL,'iolw_max_retry':2,'iolw_minimum_retry_window_ms':4.992,'iolw_ima_time_base':2,
       'iolw_ima_multiplier':1,'iolw_ima_time_ms':5,'iolw_ima_subcycles':3,
       'iolw_device_ima_min_ms':5,'iolw_device_ima_max_ms':600000,
       'iolw_application_cycle_mode':'MULTIPLIER_5MS','iolw_application_multiplier':1,
       'iolw_application_cycle_ms':5,'iolw_application_subcycles':3,'iolw_device_min_input_cycle_ms':5}
    assert registry.validate_parameters('io_link_wireless',x)['status']=='VALID'
    for patch in ({'iolw_ima_time_ms':4.992},{'iolw_ima_subcycles':5},{'iolw_max_retry':3},
                  {'iolw_application_cycle_ms':4.992},{'iolw_application_subcycles':5},
                  {'iolw_device_min_input_cycle_ms':6},{'iolw_application_cycle_mode':'FREE_RUNNING'}):
        assert registry.validate_parameters('io_link_wireless',{**x,**patch})['status']=='INVALID'
    second={**x,'iolw_ima_time_base':3,'iolw_ima_time_ms':1000,'iolw_ima_subcycles':600}
    assert registry.validate_parameters('io_link_wireless',second)['status']=='VALID'


def test_wireless_service_radio_channels_crc_and_pairing_roles_do_not_inherit_cyclic_identity_salt():
    x={**IOLW_ACTUAL,'iolw_mode':'SERVICE_PAIRING','iolw_packet_kind':'CONFIG_UPLINK',
       'iolw_frequency_channel':80,'iolw_carrier_mhz':2480,'iolw_crc32_initial_rule':'COMMON_FFFFFFFF',
       'iolw_crc32_initial_value':4294967295,'iolw_unique_id':'0123456789abcdef'}
    assert registry.validate_parameters('io_link_wireless',x)['status']=='VALID'
    for patch in ({'iolw_frequency_channel':3},{'iolw_packet_kind':'UPLINK_SSLOT'},
                  {'iolw_crc32_initial_value':0},{'iolw_crc32_initial_rule':'XOR_DEVICE_DISTINGUISHER'},
                  {'iolw_unique_id':'1234'},{'iolw_role':'W_BRIDGE'}):
        assert registry.validate_parameters('io_link_wireless',{**x,**patch})['status']in ('INVALID','UNVERIFIED')
    assert registry.validate_parameters('io_link_wireless',{**x,'iolw_role':'W_BRIDGE','iolw_wired_binding':'actual-port'})['status']=='VALID'
    assert registry.validate_parameters('io_link_wireless',{**x,'iolw_role':'W_MASTER','iolw_button_pair_timeout_ms':4999})['status']=='INVALID'
    down={**IOLW_ACTUAL,'iolw_direction':'DOWNLINK','iolw_packet_kind':'FULL_DOWNLINK',
          'iolw_crc32_initial_rule':'COMMON_FFFFFFFF','iolw_crc32_initial_value':4294967295,
          'iolw_packet_octets':52,'iolw_packet_payload_octets':37}
    assert registry.validate_parameters('io_link_wireless',down)['status']=='VALID'
    assert registry.validate_parameters('io_link_wireless',{**down,'iolw_packet_payload_octets':38})['status']=='INVALID'


def test_wireless_confirmed_radio_values_survive_rejected_isolated_sql_clock_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id());values={**IOLW_ACTUAL,'iolw_max_retry':4}
    saved={'technology':'io_link_wireless','technology_parameters':{'io_link_wireless':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['io_link_wireless']['values']['iolw_bitrate_bps']=230400
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IOL_ACTUAL={**{'iol_'+key:'synthetic-actual-'+key for key in
    ('device_source','iodd_source','master_source','physical_source','binding_source','encoding_source','schedule_source','acceptance_source','port_binding','capability_source')},
    'iol_specification':'V1_1_5','iol_role':'MASTER_PORT','iol_port_mode':'IO_LINK','iol_port_class':'A','iol_connector':'M12',
    'iol_state':'OPERATE','iol_protocol_revision':'1_1','iol_com_mode':'COM1','iol_bitrate_bps':4800,'iol_msequence':'TYPE_2_1','iol_channel':'PROCESS_DATA'}


def test_io_link_com_baseline_is_not_a_peak_rate_or_a_confirmed_device_capability():
    f={v['key']:v for v in registry.parameter_fields('io_link')}
    assert registry.profile('io_link')['domain']=='generic_networking'
    assert registry.profile('io_link')['max_payload_bytes']is None
    assert registry.profile('io_link')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('io_link',IOL_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('io_link')['values']=={}
    assert f['iol_com_mode']['conditional_defaults'][0]['value']=='COM1'
    rates=f['iol_bitrate_bps']['conditional_defaults']
    assert {v['when']['iol_com_mode']:v['value']for v in rates}=={'COM1':4800,'COM2':38400,'COM3':230400}
    assert 'bitrate'not in f and 'queue_policy'not in f
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']
    for key in ('vendor_id','device_id','device_min_cycle_ms','min_cycle_code','isdu_supported','pd_valid','device_identity'):
        assert 'default'not in f['iol_'+key]


@pytest.mark.parametrize('field',registry.parameter_fields('io_link'),ids=lambda f:'io_link/'+f['key'])
def test_each_io_link_declared_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'not-a-documented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('io_link',{**IOL_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':500000},{'can_fd_brs':True},{'iol_undocumented':1},{'ib_role':'MASTER'},
    {'iol_bitrate_bps':500000},{'iol_bitrate_bps':230400},{'iol_parity':'NONE'},{'iol_data_bits':7},
    {'iol_stop_bits':2},{'iol_character_bits':10},{'iol_device_count':2},{'iol_cable_length_m':21},
    {'iol_msequence':'TYPE_2_6'},{'iol_pd_in_bits':9},{'iol_pd_out_bits':1},{'iol_od_octets':2},
    {'iol_min_cycle_code':1},{'iol_device_min_cycle_ms':0,'iol_min_cycle_code':0},{'iol_specification':'D1_1_6'},
    {'iol_retry_count':3},{'iol_wake_retry_count':3},{'iol_supply_v':19},{'iol_wake_retry_delay_ms':51}])
def test_io_link_rejects_foreign_clocks_unsupported_sequences_and_unavailable_device_timing(patch):
    assert registry.validate_parameters('io_link',{**IOL_ACTUAL,**patch})['status']=='INVALID'


def test_io_link_com_cycle_proposals_are_sequence_qualified_not_universal_device_minimums():
    f={v['key']:v for v in registry.parameter_fields('io_link')}
    assert {v['when']['iol_com_mode']:v['value']for v in f['iol_master_cycle_ms']['conditional_defaults']}=={'COM1':18,'COM2':2.3,'COM3':.4}
    assert all(v['when']['iol_msequence']=='TYPE_2_1'for v in f['iol_master_cycle_ms']['conditional_defaults'])
    x={**IOL_ACTUAL,'iol_com_mode':'COM3','iol_bitrate_bps':230400,'iol_cycle_time_base':0,'iol_cycle_multiplier':4,
       'iol_master_cycle_ms':.4,'iol_actual_cycle_ms':.44,'iol_min_cycle_code':4,'iol_device_min_cycle_ms':.4}
    assert registry.validate_parameters('io_link',x)['status']=='VALID'
    for patch in ({'iol_master_cycle_ms':.3},{'iol_actual_cycle_ms':.45},{'iol_device_min_cycle_ms':.5},
                  {'iol_cycle_time_base':3},{'iol_cycle_multiplier':3}):
        assert registry.validate_parameters('io_link',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('io_link',{**x,'iol_cycle_time_base':2,'iol_cycle_multiplier':63,
        'iol_master_cycle_ms':132.8,'iol_actual_cycle_ms':132.8,'iol_min_cycle_code':191,'iol_device_min_cycle_ms':132.8})['status']=='VALID'


def test_io_link_timing_estimate_accounts_for_11bit_uart_delay_and_idle_without_capacity_claim():
    bit=1000000/4800;mseq=bit*(5*11+10+1+3)
    x={**IOL_ACTUAL,'iol_timing_basis':'MSEQUENCE_ESTIMATE','iol_master_octets':2,'iol_device_octets':3,
       'iol_bit_time_us':bit,'iol_master_gap_bits':1,'iol_device_gap_bits':1.5,'iol_response_delay_bits':10,
       'iol_msequence_us':mseq,'iol_idle_us':18000-mseq,'iol_master_cycle_ms':18,'iol_actual_cycle_ms':18}
    assert registry.validate_parameters('io_link',x)['status']=='VALID'
    for patch in ({'iol_bit_time_us':bit/2},{'iol_device_octets':2},{'iol_master_gap_bits':2},
                  {'iol_response_delay_bits':0},{'iol_device_gap_bits':4},{'iol_actual_cycle_ms':17}):
        assert registry.validate_parameters('io_link',{**x,**patch})['status']=='INVALID'
    assert registry.profile('io_link')['capacity_evidence']['status']=='MODEL_MISSING'


def test_io_link_pd_octet_code_is_length_plus_one_and_not_full_telegram_size():
    x={**IOL_ACTUAL,'iol_msequence':'TYPE_2_V','iol_pd_in_unit':'OCTETS','iol_pd_in_length_code':31,
       'iol_pd_in_bits':256,'iol_pd_out_unit':'BITS','iol_pd_out_length_code':16,'iol_pd_out_bits':16,'iol_od_octets':32}
    assert registry.validate_parameters('io_link',x)['status']=='VALID'
    for patch in ({'iol_pd_in_bits':248},{'iol_pd_in_length_code':1},{'iol_pd_out_length_code':17},
                  {'iol_pd_out_bits':15},{'iol_pd_in_bits':257}):
        assert registry.validate_parameters('io_link',{**x,**patch})['status']=='INVALID'


def test_io_link_isdu_232_record238_total_and_short_extended_address_lengths_are_independent():
    x={**IOL_ACTUAL,'iol_channel':'ISDU','iol_isdu_supported':True,'iol_parameter_source':'actual-device-index-list',
       'iol_index':256,'iol_index_scope':'DEVICE','iol_subindex':0,'iol_isdu_operation':'WRITE_REQUEST',
       'iol_isdu_address_format':'INDEX16_SUB8','iol_isdu_length_format':'EXTENDED','iol_isdu_length_nibble':1,
       'iol_isdu_ext_length':238,'iol_isdu_header_bytes':6,'iol_record_bytes':232,'iol_isdu_bytes':238}
    assert registry.validate_parameters('io_link',x)['status']=='VALID'
    for patch in ({'iol_isdu_supported':False},{'iol_index':1},{'iol_index':255},{'iol_record_bytes':233},
                  {'iol_isdu_bytes':239},{'iol_isdu_ext_length':237},{'iol_isdu_header_bytes':5},
                  {'iol_isdu_address_format':'INDEX8_SUB8'},{'iol_index':65535}):
        assert registry.validate_parameters('io_link',{**x,**patch})['status']=='INVALID'
    short={k:v for k,v in x.items()if k!='iol_isdu_ext_length'}
    short.update(iol_index=64,iol_subindex=0,iol_isdu_address_format='INDEX8',iol_isdu_length_format='SHORT',
       iol_isdu_length_nibble=5,iol_isdu_header_bytes=3,iol_record_bytes=2,iol_isdu_bytes=5)
    assert registry.validate_parameters('io_link',short)['status']=='VALID'
    assert registry.validate_parameters('io_link',{**short,'iol_isdu_length_nibble':16,'iol_isdu_bytes':16})['status']=='INVALID'
    assert registry.validate_parameters('io_link',{**short,'iol_index':42})['status']=='INVALID'


def test_io_link_class_b_isolation_and_utf8_serial_octets_require_own_evidence():
    x={**IOL_ACTUAL,'iol_port_class':'B','iol_extra_power_isolated':True,'iol_extra_power_source':'actual-class-B-isolation',
       'iol_extra_supply_v':24,'iol_serial_number':'ä'*8,'iol_serial_number_bytes':16,'iol_string_encoding':'UTF8'}
    assert registry.validate_parameters('io_link',x)['status']=='VALID'
    for patch in ({'iol_connector':'M8'},{'iol_extra_power_isolated':False},{'iol_serial_number_bytes':8},
                  {'iol_serial_number':'ä'*9,'iol_serial_number_bytes':18},{'iol_string_encoding':'US_ASCII'},
                  {'iol_serial_number':'A\x00B','iol_serial_number_bytes':3}):
        assert registry.validate_parameters('io_link',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('io_link',{**x,'iol_extra_power_source':''})['status']=='UNVERIFIED'


def test_io_link_sio_mode_does_not_accept_serial_telegram_clock_and_confirmed_sql_values_survive_rejection():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**IOL_ACTUAL,'iol_com_mode':'COM3','iol_bitrate_bps':230400}
    saved={'technology':'io_link','technology_parameters':{'io_link':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['io_link']['values']['iol_port_mode']='DI'
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


INTERBUS_ACTUAL={**{'ib_'+key:'synthetic-actual-'+key for key in
    ('device_source','master_source','physical_source','encoding_source','schedule_source','acceptance_source','ring_binding')},
    'ib_device_profile':'ACTUAL_DEVICE','ib_configuration_phase':'CONFIGURED_DEVICE','ib_role':'MASTER',
    'ib_segment_kind':'REMOTE','ib_cycle_kind':'PROCESS_DATA','ib_bitrate_bps':500000,'ib_medium':'COPPER'}


def test_interbus_ring_register_and_pcp_scopes_have_no_foreign_defaults():
    f={v['key']:v for v in registry.parameter_fields('interbus')}
    assert registry.profile('interbus')['domain']=='generic_networking'
    assert registry.profile('interbus')['max_payload_bytes']is None
    assert registry.profile('interbus')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('interbus',INTERBUS_ACTUAL)['status']=='VALID'
    assert registry.parameter_defaults_review('interbus')['values']=={}
    assert f['ib_bitrate_bps']['conditional_defaults'][0]['value']==500000
    assert 'bitrate'not in f and 'queue_policy'not in f
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']
    for key in ('device_profile','role','station_order','ring_binding','node_identity','pcp_service_bytes','total_nodes'):
        assert 'default'not in f['ib_'+key]


@pytest.mark.parametrize('field',registry.parameter_fields('interbus'),ids=lambda f:'interbus/'+f['key'])
def test_each_interbus_field_rejects_wrong_scalar_type(field):
    wrong={'number':True,'text':42,'boolean':'false','select':'not-a-documented-option'}.get(field['type'])
    if wrong is not None:assert registry.validate_parameters('interbus',{**INTERBUS_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('patch',[{'bitrate':500000},{'can_fd_brs':True},{'ib_undocumented':1},
    {'ib_bitrate_bps':250000},{'ib_bitrate_bps':100000000},{'ib_bc_plc_cycle_ms':5},
    {'ib_pci_slave_words':16},{'ib_cycle_kind':'PCP','ib_pcp_service_bytes':247,'ib_peer_pcp_service_limit':246,'ib_pcp_source':'actual'},
    {'ib_master_input_bits':1024,'ib_master_output_bits':1024,'ib_master_io_bits':1024}])
def test_interbus_rejects_foreign_technology_and_unqualified_device_settings(patch):
    assert registry.validate_parameters('interbus',{**INTERBUS_ACTUAL,**patch})['status']=='INVALID'


def test_interbus_bc4000_fieldbus_words_do_not_add_local_plc_images_or_other_bc_defaults():
    f={v['key']:v for v in registry.parameter_fields('interbus')}
    for key,value in [('input_bytes',16),('output_bytes',16),('id_words',8),('id_code',51),('bc_plc_cycle_ms',5),
                      ('bc_background_ms',2),('bc_remanent_bytes',64),('bc_autorefresh_cycles',0)]:
        proposal=f['ib_'+key]['conditional_defaults'][0]
        assert proposal['value']==value
        assert proposal['when']=={'ib_device_profile':'BC4000_2_2','ib_configuration_phase':'FACTORY_PROFILE'}
    x={**INTERBUS_ACTUAL,'ib_device_profile':'BC4000_2_2','ib_role':'SLAVE','ib_input_bytes':16,'ib_output_bytes':16,
       'ib_effective_words':8,'ib_id_words':8,'ib_id_code':51,'ib_local_plc_input_bytes':512,
       'ib_local_plc_output_bytes':512,'ib_bc_remanent_bytes':64,'ib_bc_persistent_bytes':63}
    assert registry.validate_parameters('interbus',x)['status']=='VALID'
    for patch in ({'ib_bitrate_bps':2000000},{'ib_role':'MASTER'},{'ib_segment_kind':'LOCAL'},
                  {'ib_input_bytes':65},{'ib_local_plc_input_bytes':513},{'ib_id_words':16},
                  {'ib_bc_persistent_bytes':64},{'ib_hop_length_m':401},{'ib_bc_baud_bps':9600}):
        assert registry.validate_parameters('interbus',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('interbus',{**x,'ib_effective_words':11,'ib_id_words':12})['status']=='VALID'
    assert registry.validate_parameters('interbus',{**x,'ib_effective_words':11,'ib_id_words':11})['status']=='INVALID'


def test_interbus_axc_local_master_limits_are_separate_from_remote_and_power_evidence():
    x={**INTERBUS_ACTUAL,'ib_device_profile':'AXC_F_IL_ADAPT_202609','ib_segment_kind':'LOCAL','ib_bitrate_bps':2000000,
       'ib_total_nodes':63,'ib_local_nodes':63,'ib_pcp_nodes':24,'ib_remote_branches':0,
       'ib_master_input_bits':2048,'ib_master_output_bits':2048,'ib_master_io_bits':4096,'ib_master_register_bytes':512,'ib_power_source':'actual-derating'}
    assert registry.validate_parameters('interbus',x)['status']=='VALID'
    for patch in ({'ib_total_nodes':64},{'ib_pcp_nodes':25},{'ib_remote_branches':1},{'ib_segment_kind':'REMOTE'},
                  {'ib_medium':'GLASS'},{'ib_master_input_bits':2049},{'ib_master_register_bytes':513}):
        assert registry.validate_parameters('interbus',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('interbus',{**x,'ib_power_source':''})['status']=='UNVERIFIED'


def test_interbus_pci_coupler_clocks_and_parameter_channel_remain_independent():
    x={**INTERBUS_ACTUAL,'ib_device_profile':'PCI_SC_RI_I_T_6190_03','ib_role':'MASTER_SLAVE',
       'ib_coupled_ring_binding':'actual-upper-ring','ib_bitrate_bps':2000000,'ib_pci_slave_bitrate_bps':500000,
       'ib_pci_pcp_words':2,'ib_pci_slave_words':14,'ib_pci_slave_id_code':232}
    assert registry.validate_parameters('interbus',x)['status']=='VALID'
    for patch in ({'ib_pci_slave_words':15},{'ib_pci_slave_words':16},{'ib_pci_pcp_words':3},
                  {'ib_pci_slave_id_code':51},{'ib_pci_slave_bitrate_bps':100000000}):
        assert registry.validate_parameters('interbus',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('interbus',{**x,'ib_coupled_ring_binding':''})['status']=='UNVERIFIED'


def test_interbus_qualified_cycle_uses_bytes_and_is_not_a_full_functional_capacity_proof():
    cycle=.2+(13*(6+32)+1.5*2)*.002
    x={**INTERBUS_ACTUAL,'ib_timing_model':'BC4000_500K_MANUAL','ib_cycle_effective_bytes':32,'ib_cycle_couplers':2,
       'ib_model_cycle_ms':cycle,'ib_ring_reaction_ms':2*cycle,'ib_error_recovery_ms':5*cycle}
    assert registry.validate_parameters('interbus',x)['status']=='VALID'
    for patch in ({'ib_cycle_effective_bytes':16},{'ib_bitrate_bps':2000000},{'ib_ring_reaction_ms':cycle},
                  {'ib_error_recovery_ms':2*cycle}):
        assert registry.validate_parameters('interbus',{**x,**patch})['status']=='INVALID'
    assert registry.profile('interbus')['capacity_evidence']['status']=='MODEL_MISSING'


def test_interbus_confirmed_actual_clock_survives_rejected_isolated_sql_foreign_switch():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**INTERBUS_ACTUAL,'ib_bitrate_bps':2000000}
    saved={'technology':'interbus','technology_parameters':{'interbus':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['interbus']['values']['ib_bitrate_bps']=100000000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IEC61850_ACTUAL={**{'iec61850_'+key:'synthetic-actual-'+key for key in
    ('device_source','edition_source','scl_source','binding_source','physical_source','encoding_source','schedule_source',
     'acceptance_source','model_source','peer_endpoint','report_source')},
    'iec61850_service':'MMS_REPORT','iec61850_mapping':'MMS_8_1','iec61850_edition':'ED2_1',
    'iec61850_implementation':'ACTUAL_DEVICE','iec61850_profile_kind':'CONFIGURED_DEVICE',
    'iec61850_role':'CLIENT','iec61850_transport':'ISO_TCP'}


def test_iec61850_has_no_industry_selected_service_or_universal_ethernet_defaults():
    from backend.communication.technologies.core.models import TransportUnitType
    for family in ('iec61850','iec61162'):
        assert TransportUnitType(registry.profile(family)['transport_unit'])==TransportUnitType.MESSAGE
    f={v['key']:v for v in registry.parameter_fields('iec61850')}
    assert registry.profile('iec61850')['domain']=='generic_networking'
    assert registry.profile('iec61850')['default_stack']==['iec61850']
    assert registry.profile('iec61850')['max_payload_bytes']is None
    assert registry.parameter_defaults_review('iec61850')['values']=={}
    assert not {'bitrate','vlan_id','mtu_bytes','duplex','queue_size'}&f.keys()
    assert 'default'not in f['payload_bytes']and 'max'not in f['payload_bytes']
    for key in ('service','mapping','ied_name','object_reference','conf_rev','buf_tm_ms','intg_pd_ms','ctl_num',
                'origin_identity','peer_endpoint','report_enabled','security_source','lib_unmodified_build'):
        assert 'default'not in f['iec61850_'+key]
    assert registry.validate_parameters('iec61850',IEC61850_ACTUAL)['status']=='VALID'
    assert registry.profile('iec61850')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('iec61850'),ids=lambda f:'iec61850/'+f['key'])
def test_each_iec61850_declared_parameter_rejects_wrong_scalar_type(field):
    wrong=True if field['type']=='number'else 1 if field['type']in('boolean','text','select')else None
    if wrong is not None:assert registry.validate_parameters('iec61850',{**IEC61850_ACTUAL,field['key']:wrong})['status']=='INVALID'


@pytest.mark.parametrize('service,mapping,source',[
    ('GOOSE','GOOSE_8_1','goose'),('SV','SV_9_2','sv'),('RGOOSE','RGOOSE_90_5','rgoose'),
    ('RSV','RSV_90_5','rsv'),('XMPP','XMPP_8_2','xmpp')])
def test_iec61850_each_non_mms_service_has_its_own_mapping_role_evidence_and_no_mms_ports(service,mapping,source):
    x={k:v for k,v in IEC61850_ACTUAL.items()if k not in ('iec61850_peer_endpoint','iec61850_report_source','iec61850_transport')}
    x.update(iec61850_service=service,iec61850_mapping=mapping,iec61850_role='CLIENT'if service=='XMPP'else'PUBLISHER')
    x['iec61850_'+source+'_source']='synthetic-actual-selected-service-path'
    assert registry.validate_parameters('iec61850',x)['status']=='VALID'
    assert registry.validate_parameters('iec61850',{**x,'iec61850_mapping':'MMS_8_1'})['status']=='INVALID'
    assert registry.validate_parameters('iec61850',{**x,'iec61850_tcp_port':102})['status']=='INVALID'
    assert registry.validate_parameters('iec61850',{**x,'iec61850_buf_tm_ms':100})['status']=='INVALID'
    assert registry.validate_parameters('iec61850',{**x,'iec61850_'+source+'_source':''})['status']=='UNVERIFIED'


@pytest.mark.parametrize('patch',[
    {'bitrate':500000},{'can_fd_brs':True},{'iec104_t1_ms':15000},{'iec61850_undocumented':1},
    {'iec61850_mapping':'GOOSE_8_1'},{'iec61850_role':'PUBLISHER'},
    {'iec61850_lib_report_trg_mask':8},{'iec61850_conf_rev':4294967296},{'iec61850_buf_tm_ms':-1},
    {'iec61850_intg_pd_ms':1.5},{'iec61850_message_bytes':1501,'iec61850_peer_message_limit':1500},
    {'iec61850_mms_pdu_bytes':501,'iec61850_mms_peer_detail':500},
    {'iec61850_report_kind':'BRCB','iec61850_functional_constraint':'RP'},
    {'iec61850_report_kind':'URCB','iec61850_functional_constraint':'BR'}])
def test_iec61850_report_parameters_reject_foreign_protocols_and_mismatched_layout_or_service(patch):
    assert registry.validate_parameters('iec61850',{**IEC61850_ACTUAL,**patch})['status']=='INVALID'


def test_iec61850_factory_proposals_are_qualified_by_implementation_build_role_and_attribute_presence():
    f={v['key']:v for v in registry.parameter_fields('iec61850')}
    for key,value in [('buffer_brcb_bytes',65536),('max_connections',5),('report_settings_writable',63),
                      ('max_dynamic_dataset_entries',100),('mms_local_detail',65000)]:
        p=f['iec61850_'+key]['conditional_defaults'][0]
        assert p['value']==value
        assert p['when']['iec61850_implementation']=='LIBIEC61850_1_6'
        assert p['when']['iec61850_profile_kind']=='FACTORY_PROFILE'
        assert p['when']['iec61850_lib_unmodified_build']is True
    assert f['iec61850_connect_timeout_ms']['conditional_defaults'][0]['value']==10000
    assert f['iec61850_request_timeout_ms']['conditional_defaults'][0]['value']==5000
    assert {p['when']['iec61850_transport']:p['value']for p in f['iec61850_tcp_port']['conditional_defaults']}=={'ISO_TCP':102,'TLS_ISO_TCP':3782}
    for p in f['iec61850_sbo_timeout_ms']['conditional_defaults']:
        assert p['value']==15000 and p['when']['iec61850_sbo_timeout_attribute_present']is False
        assert p['when']['iec61850_control_model']in ('SBO_NORMAL','SBO_ENHANCED')
    lib={**IEC61850_ACTUAL,'iec61850_implementation':'LIBIEC61850_1_6','iec61850_profile_kind':'FACTORY_PROFILE',
         'iec61850_lib_unmodified_build':True,'iec61850_build_source':'synthetic-actual-unchanged-v1.6-build',
         'iec61850_lib_tcp_compile_limit':100,'iec61850_max_connections':99,'iec61850_lib_report_trg_mask':31,
         'iec61850_lib_report_opt_mask':255,'iec61850_mms_local_detail':65000}
    assert registry.validate_parameters('iec61850',lib)['status']=='VALID'
    for patch in ({'iec61850_max_connections':100},{'iec61850_lib_tcp_compile_limit':0},{'iec61850_edition':'ED1'},
                  {'iec61850_lib_report_trg_mask':128},{'iec61850_lib_report_opt_mask':256},
                  {'iec61850_mms_local_detail':127},{'iec61850_mms_local_detail':65001}):
        assert registry.validate_parameters('iec61850',{**lib,**patch})['status']=='INVALID'
    assert registry.validate_parameters('iec61850',{**lib,'iec61850_lib_tcp_compile_limit':-1,'iec61850_max_connections':100})['status']=='VALID'
    assert registry.validate_parameters('iec61850',{**IEC61850_ACTUAL,'iec61850_transport':'TLS_ISO_TCP'})['status']=='UNVERIFIED'


def test_iec61850_control_selection_and_termination_depend_on_actual_control_model_not_tls():
    x={k:v for k,v in IEC61850_ACTUAL.items()if k!='iec61850_report_source'}
    x.update(iec61850_service='MMS_CONTROL',iec61850_control_source='synthetic-actual-control-procedure',
             iec61850_control_model='SBO_ENHANCED',iec61850_command='SELECT_WITH_VALUE',iec61850_termination_required=True,
             iec61850_ctl_num=255,iec61850_origin_category=1)
    assert registry.validate_parameters('iec61850',x)['status']=='VALID'
    for patch in ({'iec61850_command':'SELECT'},{'iec61850_termination_required':False},{'iec61850_ctl_num':256},
                  {'iec61850_origin_category':0},{'iec61850_control_model':'DIRECT_NORMAL'},
                  {'iec61850_control_model':'STATUS_ONLY','iec61850_command':'OPERATE'}):
        assert registry.validate_parameters('iec61850',{**x,**patch})['status']=='INVALID'
    assert registry.validate_parameters('iec61850',{**x,'iec61850_control_model':'SBO_NORMAL','iec61850_command':'SELECT'})['status']=='VALID'


def test_iec61850_confirmed_report_buffer_and_mapping_survive_rejected_isolated_sql_service_switch():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**IEC61850_ACTUAL,'iec61850_buf_tm_ms':27,'iec61850_intg_pd_ms':2000,'iec61850_conf_rev':42,
            'iec61850_report_kind':'BRCB','iec61850_functional_constraint':'BR'}
    saved={'technology':'iec61850','technology_parameters':{'iec61850':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved);assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['iec61850']['values']['iec61850_mapping']='GOOSE_8_1'
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IEC61162_ACTUAL={**{'iec61162_'+key:'synthetic-actual-'+key for key in
    ('device_source','edition_source','binding_source','physical_source','schedule_source','encoding_source','serial_conformance_source')},
    'iec61162_part':'P1','iec61162_edition':'P1_2010','iec61162_device_profile':'FURUNO_FA150_2012',
    'iec61162_role':'TALKER','iec61162_transport':'ONE_WAY_SERIAL','iec61162_content':'SENTENCE','iec61162_baud_bps':4800}


def test_iec61162_family_has_no_silent_part_clock_or_can_ethernet_default():
    fields={v['key']:v for v in registry.parameter_fields('iec61162')}
    assert registry.profile('iec61162')['domain']=='generic_networking'
    assert registry.profile('iec61162')['default_stack']==['iec61162']
    assert registry.profile('iec61162')['max_payload_bytes']is None
    assert registry.parameter_defaults_review('iec61162')['values']=={}
    assert not {'bitrate','vlan_id','mtu_bytes','duplex','queue_size'}&fields.keys()
    assert 'default'not in fields['iec61162_part']and 'default'not in fields['payload_bytes']and 'max'not in fields['payload_bytes']
    for key in ('iec61162_sfi','iec61162_pgn_identity','iec61162_multicast_address','iec61162_group_index',
                'iec61162_isolated','iec61162_listener_count','iec61162_network_monitoring'):
        assert 'default'not in fields[key]
    assert registry.validate_parameters('iec61162',IEC61162_ACTUAL)['status']=='VALID'
    assert registry.profile('iec61162')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('iec61162'),ids=lambda f:'iec61162/'+f['key'])
def test_each_iec61162_declared_field_rejects_wrong_scalar_type(field):
    wrong=True if field['type']=='number'else 1 if field['type']in('boolean','text','select')else None
    if wrong is not None:
        assert registry.validate_parameters('iec61162',{**IEC61162_ACTUAL,field['key']:wrong})['status']=='INVALID'


def test_iec61162_proposals_follow_part_and_named_device_without_confirming_addresses():
    f={v['key']:v for v in registry.parameter_fields('iec61162')}
    assert {p['when']['iec61162_part']:p['value']for p in f['iec61162_baud_bps']['conditional_defaults']}=={'P1':4800,'P2':38400}
    assert f['iec61162_can_bitrate_bps']['conditional_defaults'][0]['when']=={'iec61162_part':'P3'}
    assert f['iec61162_can_bitrate_bps']['conditional_defaults'][0]['value']==250000
    assert f['iec61162_ethernet_bitrate_bps']['conditional_defaults'][0]['when']=={'iec61162_device_profile':'FURUNO_FAR2XX8_MK2'}
    assert {p['when']['iec61162_device_profile']:p['value']for p in f['iec61162_group_name']['conditional_defaults']}=={'FURUNO_FAR2XX8_MK2':'TGTD','FURUNO_VR7000':'MISC'}
    assert f['iec61162_igmp_version']['conditional_defaults'][0]['when']=={'iec61162_device_profile':'FURUNO_VR7000'}
    assert f['iec61162_sentence_inner_chars']['max']==79 and f['iec61162_sentence_wire_bytes']['max']==82


@pytest.mark.parametrize('patch',[
    {'bitrate':500000},{'iec104_t1_ms':15000},{'can_fd_brs':True},{'iec61162_undocumented':1},
    {'iec61162_can_bitrate_bps':250000},{'iec61162_ethernet_bitrate_bps':100000000},
    {'iec61162_multicast_address':'239.192.0.1'},{'iec61162_datagram_header':'UdPbC'},
    {'iec61162_baud_bps':38400},{'iec61162_parity':'EVEN'},{'iec61162_stop_bits':2},
    {'iec61162_data_bits':7},{'iec61162_character_bits':8},{'iec61162_talker_count':2},
    {'iec61162_edition':'P3_2008'},{'iec61162_edition':'P1_2010_COR2013'},
    {'iec61162_transport':'NMEA2000_CAN'},{'iec61162_content':'PGN'},{'iec61162_role':'CAN_NODE'},
    {'iec61162_sentence_inner_chars':80},{'iec61162_sentence_wire_bytes':83},
    {'iec61162_sentence_inner_chars':79,'iec61162_sentence_wire_bytes':79},
    {'iec61162_short_current_min_ma':150,'iec61162_short_current_max_ma':60}])
def test_iec61162_serial_parameters_never_accept_foreign_can_ip_or_later_device_editions(patch):
    assert registry.validate_parameters('iec61162',{**IEC61162_ACTUAL,**patch})['status']=='INVALID'


def test_iec61162_part2_and_part3_use_independently_qualified_clocks_roles_and_content():
    part2={**IEC61162_ACTUAL,'iec61162_part':'P2','iec61162_edition':'P2_1998','iec61162_baud_bps':38400}
    assert registry.validate_parameters('iec61162',part2)['status']=='VALID'
    assert registry.validate_parameters('iec61162',{**part2,'iec61162_baud_bps':4800})['status']=='INVALID'
    part3={k:v for k,v in IEC61162_ACTUAL.items()if k not in ('iec61162_baud_bps','iec61162_serial_conformance_source')}
    part3.update(iec61162_part='P3',iec61162_edition='P3_2008_AMD2010_AMD2014',iec61162_device_profile='ACTUAL_DEVICE',
                 iec61162_role='CAN_NODE',iec61162_transport='NMEA2000_CAN',iec61162_content='PGN',
                 iec61162_can_bitrate_bps=250000,iec61162_can_binding='actual-canonical-nmea-can-segment',iec61162_nmea_source='actual-NMEA-version-services')
    assert registry.validate_parameters('iec61162',part3)['status']=='VALID'
    for patch in ({'iec61162_can_bitrate_bps':100000000},{'iec61162_can_fd':True},{'iec61162_baud_bps':4800},
                  {'iec61162_ethernet_bitrate_bps':100000000},{'iec61162_physical_nodes':51},
                  {'iec61162_content':'SENTENCE'},{'iec61162_pgn_transport':'SINGLE_CAN','iec61162_pgn_payload_bytes':9},
                  {'iec61162_pgn_transport':'FAST_PACKET','iec61162_pgn_payload_bytes':224}):
        assert registry.validate_parameters('iec61162',{**part3,**patch})['status']=='INVALID'
    assert registry.validate_parameters('iec61162',{**part3,'iec61162_pgn_transport':'FAST_PACKET','iec61162_pgn_payload_bytes':223})['status']=='VALID'


IEC61162_IP={**{k:v for k,v in IEC61162_ACTUAL.items()if k not in ('iec61162_baud_bps','iec61162_serial_conformance_source')},
    'iec61162_part':'P450','iec61162_edition':'P450_2018','iec61162_device_profile':'FURUNO_FAR2XX8_MK2',
    'iec61162_role':'NETWORK_DEVICE','iec61162_transport':'UDP_IPV4_MULTICAST','iec61162_content':'SENTENCE',
    'iec61162_ethernet_binding':'actual-canonical-ethernet-ip-udp-path','iec61162_network_source':'actual-device-and-edition-IP-layout'}


def test_iec61162_ethernet_and_460_addon_never_validate_can_clocks_or_wrong_base_edition():
    assert registry.validate_parameters('iec61162',IEC61162_IP)['status']=='VALID'
    for patch in ({'iec61162_can_bitrate_bps':250000},{'iec61162_baud_bps':4800},
                  {'iec61162_ethernet_bitrate_bps':250000},{'iec61162_part':'P460'},
                  {'iec61162_edition':'P1_2024'}):
        assert registry.validate_parameters('iec61162',{**IEC61162_IP,**patch})['status']=='INVALID'
    modern={**IEC61162_IP,'iec61162_part':'P460','iec61162_edition':'P460_2024','iec61162_device_profile':'ACTUAL_DEVICE',
            'iec61162_base_450_edition':'P450_2024','iec61162_security_source':'actual-460-security-and-network-evidence'}
    assert registry.validate_parameters('iec61162',modern)['status']=='VALID'
    assert registry.validate_parameters('iec61162',{**modern,'iec61162_base_450_edition':'P450_2018'})['status']=='INVALID'
    assert registry.validate_parameters('iec61162',{**modern,'iec61162_security_source':''})['status']=='UNVERIFIED'


def test_iec61162_device_multicast_ranges_datagram_sizes_and_binary_paths_remain_separate():
    far={**IEC61162_IP,'iec61162_group_index':18,'iec61162_multicast_address':'239.192.0.18','iec61162_destination_port':60018,
         'iec61162_datagram_header':'UdPbC','iec61162_envelope_bytes':10,'iec61162_tag_block_bytes':6,
         'iec61162_sentence_bytes':82,'iec61162_datagram_bytes':98,'iec61162_peer_datagram_limit':100}
    assert registry.validate_parameters('iec61162',far)['status']=='VALID'
    for patch in ({'iec61162_group_index':20,'iec61162_multicast_address':'239.192.0.20','iec61162_destination_port':60020},
                  {'iec61162_destination_port':60001},{'iec61162_multicast_address':'127.0.0.1'},
                  {'iec61162_multicast_address':'239.192.0.1'},
                  {'iec61162_datagram_bytes':97},{'iec61162_peer_datagram_limit':97},{'iec61162_datagram_header':'RrUdP'}):
        assert registry.validate_parameters('iec61162',{**far,**patch})['status']=='INVALID'
    vr={**far,'iec61162_device_profile':'FURUNO_VR7000','iec61162_group_index':20,'iec61162_multicast_address':'239.192.0.20','iec61162_destination_port':60020}
    assert registry.validate_parameters('iec61162',vr)['status']=='VALID'
    binary={**IEC61162_IP,'iec61162_transport':'TCP_IP_BINARY','iec61162_content':'BINARY_BLOCK'}
    assert registry.validate_parameters('iec61162',binary)['status']=='VALID'
    assert registry.validate_parameters('iec61162',{**binary,'iec61162_multicast_address':'239.192.0.1'})['status']=='INVALID'
    assert registry.validate_parameters('iec61162',{**binary,'iec61162_edition':'P450_2011_AMD2016'})['status']=='INVALID'
    assert registry.validate_parameters('iec61162',{**IEC61162_IP,'iec61162_content':'PGN','iec61162_edition':'P450_2011'})['status']=='INVALID'


def test_iec61162_confirmed_serial_clock_and_part_survive_rejected_isolated_sql_switch():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**IEC61162_ACTUAL,'iec61162_data_bits':8,'iec61162_parity':'NONE','iec61162_stop_bits':1,
            'iec61162_character_bits':10,'iec61162_sentence_inner_chars':79,'iec61162_sentence_wire_bytes':82}
    saved={'technology':'iec61162','technology_parameters':{'iec61162':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['iec61162']['values']['iec61162_part']='P3'
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IEC104_ACTUAL={**{'iec104_'+key:'synthetic-actual-'+key for key in
    ('peer_endpoint','transport_binding','device_source','interoperability_source','physical_source','schedule_source')},
    'iec104_implementation':'ACTUAL_DEVICE','iec104_role':'CONTROLLING','iec104_transport':'TCP'}
IEC104_FRAME={**IEC104_ACTUAL,'iec104_format':'I','iec104_transfer_state':'STARTED','iec104_length_l':19,
    'iec104_apdu_bytes':21,'iec104_length_limit':253,'iec104_asdu_limit':249,'iec104_asdu_bytes':15,
    'iec104_type_id_bytes':1,'iec104_vsq_bytes':1,'iec104_cot_bytes':2,'iec104_ca_bytes':2,'iec104_ioa_bytes':3,
    'iec104_object_layout':'FIXED_OBJECT_SIZE','iec104_object_count':2,'iec104_object_bytes':3,
    'iec104_sequence':True,'iec104_objects_encoded_bytes':9,'iec104_first_ioa':42}


def test_iec104_has_explicit_tcp_binding_without_inherited_serial_or_ethernet_parameters():
    fields={f['key']:f for f in registry.parameter_fields('iec60870_5_104')}
    assert registry.profile('iec60870_5_104')['domain']=='generic_networking'
    assert registry.profile('iec60870_5_104')['default_stack']==['iec60870_5_104']
    assert registry.profile('iec60870_5_104')['max_payload_bytes']is None
    assert registry.parameter_defaults_review('iec60870_5_104')['values']=={}
    assert not {'bitrate','mtu_bytes','vlan_id','duplex','queue_size'}&fields.keys()
    assert 'default'not in fields['payload_bytes']and 'max'not in fields['payload_bytes']
    assert registry.validate_parameters('iec60870_5_104',IEC104_ACTUAL)['status']=='VALID'
    assert registry.profile('iec60870_5_104')['capacity_evidence']['status']=='MODEL_MISSING'
    for key in ('iec104_common_address','iec104_originator','iec104_first_ioa','iec104_peer_endpoint',
                'iec104_low_queue','iec104_max_connections','iec104_send_sequence','iec104_tcp_segment_bytes'):
        assert 'default'not in fields[key]


@pytest.mark.parametrize('field',registry.parameter_fields('iec60870_5_104'),ids=lambda f:'iec104/'+f['key'])
def test_each_iec104_field_rejects_wrong_scalar_type(field):
    wrong=True if field['type']=='number'else 1 if field['type']in('boolean','text','select')else None
    if wrong is not None:
        assert registry.validate_parameters('iec60870_5_104',{**IEC104_ACTUAL,field['key']:wrong})['status']=='INVALID'


def test_iec104_default_timer_profiles_and_secure_ports_do_not_hide_implementation_differences():
    from backend.communication.technologies import iec104
    f={v['key']:v for v in registry.parameter_fields('iec60870_5_104')}
    t0=f['iec104_t0_ms']['conditional_defaults']
    assert t0[0]['value']==30000 and t0[0]['when']=={'iec104_parameter_profile':'INTEROPERABILITY_BASELINE'}
    assert t0[0]['source']==iec104.ABB
    assert t0[1]['value']==10000 and t0[1]['when']=={'iec104_implementation':'LIB60870_C_2_3_2','iec104_parameter_profile':'FACTORY_PROFILE'}
    assert t0[1]['source']==iec104.CLIENT
    assert 'default'not in f['iec104_t0_ms']
    assert {p['when']['iec104_transport']:p['value']for p in f['iec104_port']['conditional_defaults']}=={'TCP':2404,'TLS_TCP':19998}
    assert f['iec104_server_mode']['conditional_defaults'][0]['when']['iec104_role']=='CONTROLLED'
    assert f['iec104_abb_message_limit_bytes']['conditional_defaults'][0]['value']==230
    assert 'default'not in f['iec104_abb_message_scope']


@pytest.mark.parametrize('patch',[
    {'bitrate':10000000},{'iec101_baud_bps':9600},{'can_fd_brs':True},{'iec104_undocumented':1},
    {'iec104_transport':'UDP'},{'iec104_asdu_bytes':250},{'iec104_apdu_bytes':19},{'iec104_length_l':21},
    {'iec104_length_limit':18},{'iec104_asdu_limit':14},{'iec104_objects_encoded_bytes':12},
    {'iec104_first_ioa':16777215},{'iec104_send_sequence':32768},{'iec104_receive_sequence':-1},
    {'iec104_k':0},{'iec104_k':32768},{'iec104_k':12,'iec104_outstanding_apdus':13},
    {'iec104_object_count':128},{'iec104_t1_ms':15000,'iec104_t2_ms':15000},
    {'iec104_format':'S'},{'iec104_transfer_state':'STOPPED'},
    {'iec104_u_function':'STARTDT_ACT'},{'iec104_tls_record_bytes':100},
    {'iec104_common_address':256,'iec104_ca_bytes':1},{'iec104_originator':0,'iec104_cot_bytes':1}])
def test_iec104_apci_asdu_windows_and_transport_values_reject_mismatched_conditions(patch):
    assert registry.validate_parameters('iec60870_5_104',IEC104_FRAME)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_104',{**IEC104_FRAME,**patch})['status']=='INVALID'


def test_iec104_s_and_u_formats_have_no_i_data_or_foreign_sequence_fields():
    s={**IEC104_ACTUAL,'iec104_format':'S','iec104_length_l':4,'iec104_apdu_bytes':6,'iec104_asdu_bytes':0,'iec104_receive_sequence':32767}
    u={**IEC104_ACTUAL,'iec104_format':'U','iec104_length_l':4,'iec104_apdu_bytes':6,'iec104_asdu_bytes':0,'iec104_u_function':'TESTFR_ACT'}
    for p in (s,u):assert registry.validate_parameters('iec60870_5_104',p)['status']=='VALID'
    for p in ({**s,'iec104_send_sequence':0},{**s,'iec104_asdu_bytes':1},
              {**u,'iec104_receive_sequence':0},{**u,'iec104_length_l':5},
              {**u,'iec104_send_sequence':0}):
        assert registry.validate_parameters('iec60870_5_104',p)['status']=='INVALID'


def test_iec104_baseline_seconds_library_abi_and_vendor_millisecond_limits_are_distinct():
    base={**IEC104_ACTUAL,'iec104_parameter_profile':'INTEROPERABILITY_BASELINE','iec104_k':12,'iec104_w':12,
          'iec104_t0_ms':30000,'iec104_t1_ms':15000,'iec104_t2_ms':10000,'iec104_t3_ms':20000}
    assert registry.validate_parameters('iec60870_5_104',base)['status']=='VALID' #2/3k recommendation is not a hard bound
    for patch in ({'iec104_t0_ms':30001},{'iec104_t0_ms':256000},{'iec104_t3_ms':0},{'iec104_t2_ms':15000}):
        assert registry.validate_parameters('iec60870_5_104',{**base,**patch})['status']=='INVALID'
    lib={**base,'iec104_implementation':'LIB60870_C_2_3_2','iec104_parameter_profile':'FACTORY_PROFILE',
         'iec104_lib_int_bits':16,'iec104_abi_source':'actual-16-bit-int-ABI','iec104_t0_ms':30000}
    assert registry.validate_parameters('iec60870_5_104',lib)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_104',{**lib,'iec104_t0_ms':33000})['status']=='INVALID'
    assert registry.validate_parameters('iec60870_5_104',{**lib,'iec104_lib_int_bits':24})['status']=='INVALID'
    abb={**base,'iec104_implementation':'ABB_COM600_3_5','iec104_parameter_profile':'CONFIGURED_DEVICE','iec104_t0_ms':1234}
    assert registry.validate_parameters('iec60870_5_104',abb)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_104',{**abb,'iec104_t0_ms':65536})['status']=='INVALID'
    assert registry.validate_parameters('iec60870_5_104',{**abb,'iec104_t1_ms':15001})['status']=='INVALID'


def test_iec104_redundancy_and_vendor_message_scope_require_actual_mapping():
    base={**IEC104_ACTUAL,'iec104_role':'CONTROLLED','iec104_server_mode':'MULTIPLE_REDUNDANCY_GROUPS',
          'iec104_group_count':2,'iec104_active_connections':2,'iec104_active_per_group':1,'iec104_max_connections':5,
          'iec104_redundancy_source':'actual-group-assignment'}
    assert registry.validate_parameters('iec60870_5_104',base)['status']=='VALID'
    for patch in ({'iec104_active_per_group':2},{'iec104_active_connections':3},{'iec104_server_mode':'SINGLE_REDUNDANCY_GROUP'}):
        assert registry.validate_parameters('iec60870_5_104',{**base,**patch})['status']=='INVALID'
    for scope,key,limit in [('LENGTH_L','iec104_length_l',19),('FULL_APDU','iec104_apdu_bytes',21),('ASDU','iec104_asdu_bytes',15)]:
        # Use one sufficiently large actual test frame so all vendor settings exceed documented minimum20.
        p={**IEC104_FRAME,'iec104_object_bytes':13,'iec104_objects_encoded_bytes':29,'iec104_asdu_bytes':35,
           'iec104_length_l':39,'iec104_apdu_bytes':41,'iec104_implementation':'ABB_COM600_3_5',
           'iec104_abb_message_scope':scope,'iec104_abb_message_scope_source':'actual-device-length-mapping',
           'iec104_abb_message_limit_bytes':limit+20}
        assert registry.validate_parameters('iec60870_5_104',p)['status']=='VALID'
        assert registry.validate_parameters('iec60870_5_104',{**p,'iec104_abb_message_limit_bytes':limit+19})['status']=='INVALID'
    tls={**IEC104_ACTUAL,'iec104_transport':'TLS_TCP','iec104_tls_source':'actual-TLS-policy'}
    assert registry.validate_parameters('iec60870_5_104',tls)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_104',{**tls,'iec104_tls_source':''})['status']=='UNVERIFIED'


def test_iec104_confirmed_actual_timers_addresses_and_transport_survive_bad_isolated_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**IEC104_ACTUAL,'iec104_t1_ms':30000,'iec104_t2_ms':10000,'iec104_common_address':1234,'iec104_ca_bytes':2,
            'iec104_first_ioa':456789,'iec104_port':42404}
    saved={'technology':'iec60870_5_104','technology_parameters':{'iec60870_5_104':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['iec60870_5_104']['values']['iec104_t2_ms']=30000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


IEC101_ACTUAL={**{'iec101_'+key:'synthetic-actual-'+key for key in
    ('serial_binding','device_source','interoperability_source','physical_source','schedule_source')},
    'iec101_implementation':'IEC_INTEROPERABILITY','iec101_role':'CONTROLLING','iec101_link_mode':'UNBALANCED',
    'iec101_physical':'RS485','iec101_baud_bps':9600,'iec101_data_bits':8,'iec101_parity':'EVEN',
    'iec101_stop_bits':1,'iec101_link_address_bytes':1,'iec101_cot_bytes':2,'iec101_ca_bytes':2,'iec101_ioa_bytes':3}
IEC101_FRAME={**IEC101_ACTUAL,'iec101_character_bits':11,'iec101_frame_kind':'VARIABLE','iec101_length_l':17,
    'iec101_wire_bytes':23,'iec101_peer_length_limit':230,'iec101_asdu_limit':249,'iec101_asdu_bytes':15,
    'iec101_object_layout':'FIXED_OBJECT_SIZE','iec101_object_count':2,'iec101_object_bytes':3,
    'iec101_sequence':True,'iec101_objects_encoded_bytes':9,'iec101_first_ioa':42}


def test_iec101_uses_its_actual_serial_profile_not_a_can_rate_or_ethernet_payload():
    fields={f['key']:f for f in registry.parameter_fields('iec60870_5_101')}
    assert registry.profile('iec60870_5_101')['default_stack']==['iec60870_5_101']
    assert registry.profile('iec60870_5_101')['domain']=='generic_networking'
    assert registry.parameter_defaults_review('iec60870_5_101')['values']=={}
    assert registry.profile('iec60870_5_101')['max_payload_bytes']is None
    assert 'bitrate'not in fields and 'default'not in fields['payload_bytes']
    assert 'max'not in fields['payload_bytes']
    assert registry.validate_parameters('iec60870_5_101',IEC101_ACTUAL)['status']=='VALID'
    for key in ('iec101_link_address','iec101_peer_link_address','iec101_common_address','iec101_first_ioa',
                'iec101_originator','iec101_physical','iec101_role','iec101_class1_queue'):
        assert 'default'not in fields[key]
    assert fields['iec101_byte_order']['default']=='LITTLE_ENDIAN_MODE1'
    assert registry.profile('iec60870_5_101')['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('iec60870_5_101'),ids=lambda f:'iec101/'+f['key'])
def test_each_iec101_field_rejects_wrong_scalar_type(field):
    wrong=True if field['type']=='number' else 1 if field['type']in('boolean','text','select') else None
    if wrong is not None:
        assert registry.validate_parameters('iec60870_5_101',{**IEC101_ACTUAL,field['key']:wrong})['status']=='INVALID'


def test_iec101_constructor_and_vendor_defaults_are_independently_qualified_and_sourced():
    from backend.communication.technologies import iec101
    f={v['key']:v for v in registry.parameter_fields('iec60870_5_101')}
    assert 'default'not in f['iec101_baud_bps']
    defaults=f['iec101_baud_bps']['conditional_defaults']
    assert defaults==[{'when':{'iec101_implementation':'ABB_COM600_5_1'},'value':19200,'source':iec101.ABB},
        {'when':{'iec101_implementation':'LIB60870_C_2_3_2','iec101_configuration_phase':'USER_GUIDE_EXAMPLE'},'value':9600,'source':iec101.GUIDE}]
    lib={p['when']['iec101_role']:p['value'] for p in f['iec101_link_state_timeout_ms']['conditional_defaults']}
    assert lib=={'CONTROLLING':5000}
    assert f['iec101_cot_bytes']['conditional_defaults'][0]['source']==iec101.MASTER
    assert {p['when']['iec101_link_mode']:p['value'] for p in f['iec101_cts_delay_ms']['conditional_defaults']}=={'BALANCED':50,'UNBALANCED':0}
    assert {p['when']['iec101_link_mode']:p['value'] for p in f['iec101_carrier_detect_required']['conditional_defaults']}=={'BALANCED':False,'UNBALANCED':True}
    assert f['iec101_ack_timeout_ms']['conditional_defaults'][0]['value']==200
    assert f['iec101_ack_timeout_ms']['conditional_defaults'][1]['value']==2000


@pytest.mark.parametrize('patch',[
    {'bitrate':500000},{'can_fd_brs':True},{'iec101_unknown':1},
    {'iec101_baud_bps':0},{'iec101_baud_bps':True},{'iec101_data_bits':8.5},
    {'iec101_character_bits':10},{'iec101_wire_bytes':17},{'iec101_length_l':23},
    {'iec101_peer_length_limit':16},{'iec101_asdu_limit':14},{'iec101_object_count':128},
    {'iec101_objects_encoded_bytes':12},{'iec101_ioa_bytes':4},{'iec101_cot_bytes':3},
    {'iec101_link_address_bytes':0},{'iec101_originator':256},{'iec101_cot':64},
    {'iec101_first_ioa':16777215},{'iec101_link_address':255,'iec101_address_purpose':'STATION'},
    {'iec101_link_address':254,'iec101_address_purpose':'BROADCAST'},
    {'iec101_balanced_dir':False},{'iec101_implementation':'ABB_COM600_5_1','iec101_baud_bps':500000},
    {'iec101_implementation':'ABB_COM600_5_1','iec101_retry_limit':256},
    {'iec101_implementation':'ABB_COM600_5_1','iec101_ack_timeout_ms':65536}])
def test_iec101_rejects_foreign_values_and_mismatched_serial_or_asdu_sizes(patch):
    assert registry.validate_parameters('iec60870_5_101',IEC101_FRAME)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_101',{**IEC101_FRAME,**patch})['status']=='INVALID'


def test_iec101_fixed_and_e5_ack_frames_have_their_own_wire_size_and_no_asdu():
    fixed={**IEC101_ACTUAL,'iec101_frame_kind':'FIXED','iec101_wire_bytes':5,'iec101_asdu_bytes':0}
    ack={**IEC101_ACTUAL,'iec101_frame_kind':'SINGLE_ACK','iec101_wire_bytes':1,'iec101_single_char_ack':True,'iec101_asdu_bytes':0}
    assert registry.validate_parameters('iec60870_5_101',fixed)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_101',ack)['status']=='VALID'
    for p in ({**fixed,'iec101_wire_bytes':6},{**fixed,'iec101_asdu_bytes':1},
              {**ack,'iec101_single_char_ack':False},{**ack,'iec101_wire_bytes':5},
              {**ack,'iec101_length_l':0}):
        assert registry.validate_parameters('iec60870_5_101',p)['status']=='INVALID'


def test_iec101_sequence_and_address_width_boundaries_are_not_shared():
    separate={**IEC101_FRAME,'iec101_sequence':False,'iec101_objects_encoded_bytes':12,
              'iec101_asdu_bytes':18,'iec101_length_l':20,'iec101_wire_bytes':26}
    assert registry.validate_parameters('iec60870_5_101',separate)['status']=='VALID'
    empty={**IEC101_FRAME,'iec101_object_count':0,'iec101_objects_encoded_bytes':0,
           'iec101_asdu_bytes':6,'iec101_length_l':8,'iec101_wire_bytes':14}
    assert registry.validate_parameters('iec60870_5_101',empty)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_101',{**empty,'iec101_objects_encoded_bytes':3})['status']=='INVALID'
    assert registry.validate_parameters('iec60870_5_101',{**IEC101_ACTUAL,'iec101_cot_bytes':1,'iec101_originator':0})['status']=='INVALID'
    for width in (1,2,3):
        assert registry.validate_parameters('iec60870_5_101',{**IEC101_ACTUAL,'iec101_ioa_bytes':width,'iec101_first_ioa':2**(8*width)-1})['status']=='VALID'
        assert registry.validate_parameters('iec60870_5_101',{**IEC101_ACTUAL,'iec101_ioa_bytes':width,'iec101_first_ioa':2**(8*width)})['status']=='INVALID'
    balanced={**IEC101_ACTUAL,'iec101_link_mode':'BALANCED','iec101_link_address_bytes':0,'iec101_balanced_dir':True,'iec101_peer_balanced_dir':False}
    assert registry.validate_parameters('iec60870_5_101',balanced)['status']=='VALID'
    assert registry.validate_parameters('iec60870_5_101',{**balanced,'iec101_peer_balanced_dir':True})['status']=='INVALID'
    assert registry.validate_parameters('iec60870_5_101',{**balanced,'iec101_link_address':1})['status']=='INVALID'


def test_iec101_confirmed_device_serial_and_address_values_survive_rejected_isolated_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**IEC101_ACTUAL,'iec101_link_address':42,'iec101_address_purpose':'STATION','iec101_common_address':1234,'iec101_first_ioa':456789}
    saved={'technology':'iec60870_5_101','technology_parameters':{'iec60870_5_101':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}for key,value in values.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['iec60870_5_101']['values']['iec101_link_address']=256
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


I2C_ACTUAL={'bitrate_bps':100000,'i2c_mode':'STANDARD','i2c_profile':'UM10204_STANDARD_LIMITS',
    'i2c_endpoint_role':'CONTROLLER','i2c_controller_id':'controller-A','i2c_device_source':'actual-device-rev',
    'i2c_binding_source':'actual-segment-A','i2c_physical_source':'actual-load-and-pins','i2c_schedule_source':'actual-transactions'}
I2C_TRANSFER={'technology':'i2c','confirmed':True,'source':'actual-datasheet-and-transaction-layout',
    'master_node_id':'controller-A','slave_address':'0x20','address_bits':7,'i2c_mode':'STANDARD',
    'transfer_direction':'READ','start_stop_bound_us':8,'clock_stretch_limit_us':5,'multi_master':False,
    'transfer_bits_bound':81,'bitrate_bps':100000}

I3C_ACTUAL={**{'i3c_'+key:'synthetic-actual-'+key for key in
    ('controller_id','device_source','capability_source','binding_source','physical_source','schedule_source','transaction_source','clock_source')},
    'i3c_version':'BASIC_1_2','i3c_mode':'SDR','i3c_implementation':'MIPI_DEVICE','i3c_role':'ACTIVE_CONTROLLER',
    'i3c_bus_kind':'PURE','i3c_pp_clock_hz':10000000,'i3c_od_clock_hz':2500000}


def test_i3c_is_not_a_generic_bitrate_or_fixed_packet_profile():
    fields={f['key']:f for f in registry.parameter_fields('i3c')}
    assert 'bitrate' not in fields and 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert fields['i3c_mode']['default']=='SDR'
    assert registry.parameter_defaults_review('i3c')['values']=={}
    assert registry.profile('i3c')['max_payload_bytes']is None
    assert registry.profile('i3c')['default_stack']==['i3c']
    assert registry.validate_parameters('i3c',I3C_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('i3c',{'bitrate_bps':12500000})['status']=='INVALID'
    for key in ('i3c_dynamic_address','i3c_bcr','i3c_dcr','i3c_tsco_ns','i3c_bus_cap_pf','i3c_static_address'):
        assert 'default' not in fields[key]
    from backend.engineering.capacity.calculators import estimate_frame
    assert not estimate_frame('I3C',8,I3C_ACTUAL).transmission_time_available


@pytest.mark.parametrize('field',registry.parameter_fields('i3c'),ids=lambda f:'i3c/'+f['key'])
def test_each_i3c_declared_field_rejects_wrong_scalar_type(field):
    wrong=True if field['type']=='number' else 1 if field['type']in('boolean','text','select') else None
    if wrong is not None:
        assert registry.validate_parameters('i3c',{**I3C_ACTUAL,field['key']:wrong})['status']=='INVALID'


def test_i3c_sdk_factory_defaults_are_qualified_proposals_not_global_or_address_defaults():
    fields={f['key']:f for f in registry.parameter_fields('i3c')}
    for key,value in [('i3c_pp_clock_hz',12500000),('i3c_od_clock_hz',2500000),('i3c_legacy_clock_hz',400000)]:
        assert 'default' not in fields[key]
        assert fields[key]['conditional_defaults']==[{'when':{'i3c_implementation':'MCUX_SDK_2_14','i3c_configuration_phase':'SDK_DEFAULT_CONFIG'},'value':value}]
        assert 'mcuxpresso.nxp.com' in fields[key]['source']
    assert registry.validate_parameters('i3c',{**I3C_ACTUAL,'payload_bytes':70000})['status']=='VALID'


@pytest.mark.parametrize('patch',[
    {'i3c_pp_clock_hz':12500001}, {'i3c_pp_clock_hz':True}, {'i3c_od_clock_hz':0},
    {'i3c_target_stretch':True},{'i3c_legacy_controller_present':True},
    {'i3c_bus_kind':'PURE','i3c_role':'LEGACY_TARGET'}, {'i3c_bus_kind':'PURE','i3c_mode':'LEGACY_I2C'},
    {'i3c_implementation':'STM32_AN5879','i3c_mode':'HDR_DDR','i3c_hdr_supported':True,'i3c_hdr_crc_policy':'DDR_CRC5_INCLUDES_PAD'},
    {'i3c_implementation':'PIC18_Q20','i3c_role':'ACTIVE_CONTROLLER'},
    {'i3c_version':'BASIC_1_0','i3c_mode':'HDR_DDR','i3c_hdr_supported':True,'i3c_hdr_crc_policy':'DDR_CRC5_INCLUDES_PAD'},
    {'i3c_version':'BASIC_1_2','i3c_mode':'HDR_TSP','i3c_hdr_supported':True,'i3c_hdr_crc_policy':'TERNARY_SPECIFIC'},
    {'i3c_version':'BASIC_1_2','i3c_lanes':2}, {'i3c_version':'BASIC_1_0','i3c_timing_control':'ASYNC_0','i3c_timing_control_source':'actual'},
    {'i3c_lanes':3},{'i3c_version':'FULL_1_0','i3c_lanes':2},
    {'i3c_implementation':'STM32_AN5879','i3c_od_clock_hz':4000001},
    {'i3c_timing_control':'ASYNC_1','i3c_timing_control_source':'actual'},
    {'i3c_hot_join':True,'i3c_address_method':'SETDASA','i3c_static_address':32},
    {'i3c_ibi_data_supported':True,'i3c_ibi_bytes':0,'i3c_ibi_source':'actual'},
    {'i3c_ibi_data_supported':False,'i3c_ibi_bytes':1,'i3c_ibi_source':'actual'},
    {'i3c_scl_drive':'MODE_SPECIFIC_HANDOFF'}, {'i3c_sda_phase':'LEGACY_OPEN_DRAIN'},
    {'i3c_ccc_scope':'BROADCAST','i3c_ccc_code':143,'i3c_ccc_source':'actual'},
    {'i3c_ccc_scope':'DIRECTED','i3c_ccc_code':7,'i3c_ccc_source':'actual'},
    {'i3c_version':'FULL_1_1','i3c_ccc_scope':'DIRECTED','i3c_ccc_code':134,'i3c_ccc_source':'actual'},
    {'i3c_bus_kind':'MIXED_FM','i3c_legacy_filter_50ns':False,'i3c_legacy_controller_present':False,
     'i3c_target_stretch':False,'i3c_legacy_mode':'FAST','i3c_legacy_clock_hz':400000},
    {'i3c_undocumented_native_field':1},{'can_fd_brs':True},{'bitrate':500000}])
def test_i3c_version_role_phase_and_capability_rules_reject_foreign_or_incompatible_choices(patch):
    assert registry.validate_parameters('i3c',{**I3C_ACTUAL,**patch})['status']=='INVALID'


@pytest.mark.parametrize('address',[0,1,2,5,6,7,62,94,110,118,122,124,126,127,128])
def test_i3c_reserved_and_broadcast_neighbour_addresses_are_not_assignable(address):
    p={**I3C_ACTUAL,'i3c_role':'TARGET','i3c_dynamic_address':address,
       'i3c_address_purpose':'ORDINARY','i3c_address_source':'synthetic-assignment'}
    assert registry.validate_parameters('i3c',p)['status']=='INVALID'


@pytest.mark.parametrize('address,key',[(3,'no_legacy_hs'),(4,'no_legacy_hs'),(120,'no_legacy_10bit'),
                                     (121,'no_legacy_10bit'),(123,'no_legacy_10bit'),(125,'no_legacy_device_id')])
def test_i3c_conditional_addresses_require_their_own_actual_legacy_conflict_evidence(address,key):
    p={**I3C_ACTUAL,'i3c_role':'TARGET','i3c_dynamic_address':address,'i3c_address_source':'actual-unique-assignment',
       'i3c_address_purpose':'LEGACY_EXCEPTION','i3c_'+key:True}
    assert registry.validate_parameters('i3c',p)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**p,'i3c_'+key:False})['status']=='INVALID'
    assert registry.validate_parameters('i3c',{**p,'i3c_address_purpose':'ORDINARY'})['status']=='INVALID'


@pytest.mark.parametrize('version,limit',[('FULL_1_1_1',12),('BASIC_1_1_1',12),('FULL_1_2',20),('BASIC_1_2',20)])
def test_i3c_turnaround_threshold_uses_actual_version_and_private_agreement(version,limit):
    p={**I3C_ACTUAL,'i3c_version':version,'i3c_tsco_ns':limit}
    assert registry.validate_parameters('i3c',p)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**p,'i3c_tsco_ns':limit+1})['status']=='UNVERIFIED'
    agreed={**p,'i3c_tsco_ns':limit+1,'i3c_bcr_speed_limited':True,'i3c_maxrd_tsco_code':7,'i3c_tsco_source':'actual-datasheet'}
    assert registry.validate_parameters('i3c',agreed)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**agreed,'i3c_bcr_speed_limited':False})['status']=='INVALID'


def test_i3c_read_budget_and_stm32_clock_divider_do_not_use_peak_rate_shortcuts():
    p={**I3C_ACTUAL,'i3c_tsco_ns':12,'i3c_read_sda_edge_ns':3,'i3c_read_setup_ns':3,
       'i3c_read_propagation_ns':2,'i3c_read_low_ns':21}
    assert registry.validate_parameters('i3c',p)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**p,'i3c_read_low_ns':20})['status']=='INVALID'
    stm={**I3C_ACTUAL,'i3c_implementation':'STM32_AN5879','i3c_kernel_clock_hz':96000000,
         'i3c_period_cycles':8,'i3c_pp_clock_hz':12000000}
    assert registry.validate_parameters('i3c',stm)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**stm,'i3c_pp_clock_hz':12500000})['status']=='INVALID'
    assert registry.validate_parameters('i3c',{**stm,'i3c_period_cycles':2,'i3c_kernel_clock_hz':24000000})['status']=='INVALID'


def test_i3c_pic_physical_limits_do_not_become_universal_bus_limits():
    p={**I3C_ACTUAL,'i3c_role':'TARGET','i3c_dynamic_address':32,'i3c_address_purpose':'ORDINARY','i3c_address_source':'actual-assigned',
       'i3c_bus_cap_pf':51,'i3c_pp_low_ns':23}
    assert registry.validate_parameters('i3c',p)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**p,'i3c_implementation':'PIC18_Q20'})['status']=='INVALID'
    pic={**p,'i3c_implementation':'PIC18_Q20','i3c_bus_cap_pf':50,'i3c_pp_low_ns':24}
    assert registry.validate_parameters('i3c',pic)['status']=='VALID'


def test_i3c_version_qualified_ccc_and_accepted_lengths_do_not_inherit_new_or_can_defaults():
    old={**I3C_ACTUAL,'i3c_version':'FULL_1_0','i3c_ccc_scope':'DIRECTED','i3c_ccc_code':134,'i3c_ccc_source':'actual-old-command'}
    assert registry.validate_parameters('i3c',old)['status']=='VALID'
    small={**I3C_ACTUAL,'i3c_max_read_bytes':3,'i3c_max_write_bytes':2,'i3c_length_source':'actual-accepted-content-limits'}
    assert registry.validate_parameters('i3c',small)['status']=='VALID'
    assert registry.validate_parameters('i3c',{**small,'i3c_max_read_bytes':65536})['status']=='INVALID'
    assert registry.validate_parameters('i3c',{**small,'i3c_direction':'READ','payload_bytes':3})['status']=='VALID'
    assert registry.validate_parameters('i3c',{**small,'i3c_direction':'READ','payload_bytes':4})['status']=='INVALID'
    assert registry.validate_parameters('i3c',{**small,'i3c_direction':'WRITE','payload_bytes':3})['status']=='INVALID'


def test_i3c_confirmed_actual_clocks_and_address_survive_rejected_isolated_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**I3C_ACTUAL,'i3c_role':'TARGET','i3c_dynamic_address':32,'i3c_address_purpose':'ORDINARY',
            'i3c_address_source':'actual-assignment','i3c_pp_clock_hz':8000000,'i3c_od_clock_hz':2000000}
    saved={'technology':'i3c','technology_parameters':{'i3c':{'values':values,'provenance':{
        key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(saved)
    assert service.get()['parameters']==saved
    bad=deepcopy(saved);bad['technology_parameters']['i3c']['values']['i3c_dynamic_address']=126
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==saved


def test_i2c_proposed_standard_is_not_a_device_address_or_electrical_measurement():
    fields={f['key']:f for f in registry.parameter_fields('i2c')}
    assert fields['bitrate']['default']==100000
    assert fields['i2c_mode']['default']=='STANDARD'
    assert registry.profile('i2c')['default_stack']==['i2c']
    assert registry.profile('i2c')['max_payload_bytes']is None
    assert not {'mtu_bytes','vlan_id','qos_priority','duplex','queue_policy','retry_limit'} & fields.keys()
    assert 'max' not in fields['payload_bytes'] and 'default' not in fields['payload_bytes']
    for key in ('i2c_target_address','i2c_address_bits','i2c_low_ns','i2c_bus_cap_pf','i2c_pullup_ohms','i2c_endpoint_role'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('i2c',I2C_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('i2c',{'bitrate_bps':100000})['status']=='UNVERIFIED'


@pytest.mark.parametrize('field',registry.parameter_fields('i2c'),ids=lambda f:'i2c/'+f['key'])
def test_every_i2c_form_field_has_its_own_type_and_rejects_foreign_scalar_types(field):
    wrong=(True if field['type']=='number' else 1 if field['type']in('boolean','text','select') else None)
    if wrong is None: return
    values={**I2C_ACTUAL,field['key']:wrong}
    # UI rate aliases must not be paired with a conflicting canonical value.
    if field['key']=='bitrate': values.pop('bitrate_bps')
    assert registry.validate_parameters('i2c',values)['status']=='INVALID',field['key']


@pytest.mark.parametrize('mode,rate,cap,low,high,rise,fall',[
    ('STANDARD',100000,400,4700,4000,1000,300),('FAST',400000,400,1300,600,300,300),
    ('FAST_PLUS',1000000,550,500,260,120,120),('ULTRA_FAST',5000000,900,50,50,50,50)])
def test_i2c_each_mode_uses_its_own_frequency_timing_and_capacitance(mode,rate,cap,low,high,rise,fall):
    p={**I2C_ACTUAL,'i2c_mode':mode,'bitrate_bps':rate,'i2c_bus_cap_pf':cap,
       'i2c_low_ns':low,'i2c_high_ns':high,'i2c_rise_ns':rise,'i2c_fall_ns':fall}
    assert registry.validate_parameters('i2c',p)['status']=='VALID'
    assert registry.validate_parameters('i2c',{**p,'bitrate_bps':rate+1})['status']=='INVALID'
    assert registry.validate_parameters('i2c',{**p,'i2c_low_ns':low-1})['status']=='INVALID'
    if mode!='ULTRA_FAST':
        assert registry.validate_parameters('i2c',{**p,'i2c_bus_cap_pf':cap+1})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'i2c_endpoint_role':'CONTROLLER','i2c_target_address':32},
    {'i2c_endpoint_role':'TARGET','i2c_address_bits':7,'i2c_target_address':128},
    {'i2c_endpoint_role':'TARGET','i2c_address_bits':7,'i2c_target_address':0,'i2c_address_purpose':'ORDINARY'},
    {'i2c_mode':'ULTRA_FAST','i2c_direction':'READ'},
    {'i2c_mode':'ULTRA_FAST','i2c_multi_controller':True},
    {'i2c_mode':'ULTRA_FAST','i2c_clock_stretch_supported':True},
    {'i2c_mode':'ULTRA_FAST','i2c_ack_policy':'ACK_NACK'},
    {'i2c_mode':'STANDARD','i2c_drive':'PUSH_PULL'},
    {'i2c_mode':'HIGH_SPEED','i2c_stretch_position':'ANY_LOW'},
    {'i2c_vol_max_v':0.6,'i2c_vil_max_v':0.5},
    {'i2c_vdd_v':3.3,'i2c_vih_min_v':3.4},
    {'i2c_special_pin':False,'i2c_pin_cap_pf':11},
    {'i2c_pullup_ohms':4700,'i2c_bus_cap_pf':400,'i2c_rise_ns':1000},
    {'i2c_pullup_ohms':100,'i2c_sink_bound_ma':3,'i2c_vol_max_v':0.4,'i2c_vdd_v':3.3},
    {'can_frame_format':'BASE_11'}, {'i2c_undocumented_fake_parameter':1}])
def test_i2c_role_electrical_and_mode_constraints_reject_wrong_assumptions(patch):
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,**patch})['status']=='INVALID'


def test_i2c_high_speed_interpolates_timing_and_includes_separate_entry_clock():
    from backend.engineering.capacity.calculators import confirmed_serial_evidence,estimate_frame
    p={**I2C_ACTUAL,'i2c_mode':'HIGH_SPEED','bitrate_bps':2000000,'i2c_bus_cap_pf':250,
       'i2c_hs_entry_rate_bps':400000,'i2c_hs_controller_code':9,'i2c_hs_diagnostic':False,
       'i2c_low_ns':240,'i2c_high_ns':90,'i2c_rise_ns':60,'i2c_fall_ns':60}
    assert registry.validate_parameters('i2c',p)['status']=='VALID'
    assert registry.validate_parameters('i2c',{**p,'i2c_low_ns':239})['status']=='INVALID'
    assert registry.validate_parameters('i2c',{**p,'i2c_rise_ns':14})['status']=='INVALID'
    assert registry.validate_parameters('i2c',{**p,'i2c_rise_ns':0,'i2c_fall_ns':0,'bitrate_bps':3400000})['status']=='INVALID'
    assert registry.validate_parameters('i2c',{**p,'i2c_bus_cap_pf':400})['status']=='INVALID'
    e={**I2C_TRANSFER,'i2c_mode':'HIGH_SPEED','bitrate_bps':2000000,'hs_entry_rate_bps':400000,
       'hs_entry_bound_us':25,'bus_cap_pf':250,'hs_clock_timing_source':'actual-interpolated-waveform'}
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':e},8)==e
    frame=estimate_frame('i2c',8,{'local_timing_evidence':e})
    assert frame.transmission_time_s==pytest.approx(81/2000000+38/1000000)
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':{**e,'hs_entry_bound_us':20}},8)is None


def test_i2c_controller_port_and_target_port_do_not_certify_a_transaction():
    from backend.engineering.capacity.calculators import confirmed_serial_evidence,serial_evidence_missing_fields
    controller={'evidence_scope':'CONTROLLER_PORT','confirmed':True,'source':'actual-controller-datasheet',
       'master_node_id':'controller-A','i2c_mode':'STANDARD','bitrate_bps':100000}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':controller})['status']=='VALID'
    missing=serial_evidence_missing_fields('i2c',{'local_timing_evidence':controller},8)
    assert 'local_timing_evidence.slave_address' not in missing
    assert missing==['local_timing_evidence.transaction_evidence']
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':controller},8)is None
    target={**controller,'evidence_scope':'TARGET_PORT','slave_address':'0x20','address_bits':7}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':target})['status']=='VALID'
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':target},8)is None
    from backend.engineering.capacity.dimensioning import local_evidence_proposal
    proposal=local_evidence_proposal('I2C',[{'stream_id':'controller-port','local_timing_evidence':controller}])
    assert not any(f['key'].endswith(':slave_address') or f['key'].endswith(':transfer_bits_bound') for f in proposal['fields'])
    assert proposal['release_gate']=='TIMING_BLOCKED_UNTIL_DEVICE_EVIDENCE_CONFIRMED'


@pytest.mark.parametrize('patch',[
    {'address_bits':True},{'address_bits':7.5},{'slave_address':False},
    {'transfer_bits_bound':80},{'transfer_bits_bound':81.5},{'transfer_bits_bound':True},
    {'source':123},{'source':'   '},{'master_node_id':123},
    {'start_stop_bound_us':2},{'multi_master':'false'},{'clock_stretch_limit_us':float('nan')},
    {'i2c_mode':'ULTRA_FAST','bitrate_bps':5000000},
    {'i2c_mode':'HIGH_SPEED','bitrate_bps':3400000},
    {'technology':'can'},{'address_bits':10,'slave_address':'0x300','transfer_bits_bound':90},
    {'transfer_direction':'BIDIRECTIONAL','transfer_bits_bound':81},
    {'multi_master':True,'arbitration_bound_us':None}])
def test_i2c_transaction_bounds_are_typed_and_include_address_ninth_pulses_and_competition(patch):
    from backend.engineering.capacity.calculators import confirmed_serial_evidence
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':{**I2C_TRANSFER,**patch}},8)is None


@pytest.mark.parametrize('field',registry.profile('i2c')['local_timing_schema'],ids=lambda f:'i2c/local/'+f['key'])
def test_every_i2c_local_device_field_has_typed_validation(field):
    e={**I2C_TRANSFER,field['key']:True if field['type']in('number','address') else 2}
    result=registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':e})
    assert result['status']=='INVALID'


@pytest.mark.parametrize('scope',[None,''])
def test_i2c_blank_optional_role_preserves_legacy_transaction_requirements(scope):
    from backend.engineering.capacity.calculators import confirmed_serial_evidence,serial_evidence_missing_fields
    from backend.engineering.capacity.dimensioning import local_evidence_proposal
    e={**I2C_TRANSFER,'evidence_scope':scope,'slave_address':32}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':e})['status']=='VALID'
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':e},8)==e
    incomplete={**e,'slave_address':None,'transfer_bits_bound':None}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':incomplete})['status']=='INVALID'
    missing=serial_evidence_missing_fields('i2c',{'local_timing_evidence':incomplete},8)
    assert 'local_timing_evidence.slave_address' in missing
    assert 'local_timing_evidence.transfer_bits_bound' in missing
    proposal=local_evidence_proposal('I2C',[{'stream_id':'legacy','local_timing_evidence':incomplete}])
    assert any(f['key'].endswith(':slave_address') for f in proposal['fields'])


@pytest.mark.parametrize('address',[32,32.0,'32','0x20','0X20'])
def test_i2c_existing_valid_integer_and_text_addresses_remain_accepted(address):
    from backend.engineering.capacity.calculators import confirmed_serial_evidence
    e={**I2C_TRANSFER,'slave_address':address}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':e})['status']=='VALID'
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':e},8)==e


@pytest.mark.parametrize('address',[True,False,-1,32.5,128,'nonsense','32.5','-1'])
def test_i2c_invalid_target_addresses_fail_both_form_and_capacity(address):
    from backend.engineering.capacity.calculators import confirmed_serial_evidence
    e={**I2C_TRANSFER,'slave_address':address}
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'local_timing_evidence':e})['status']=='INVALID'
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':e},8)is None


def test_i2c_explicit_ufm_and_unrestricted_data_count_are_separate_from_bidirectional_i2c():
    from backend.engineering.capacity.calculators import confirmed_serial_evidence
    e={**I2C_TRANSFER,'i2c_mode':'ULTRA_FAST','bitrate_bps':5000000,'transfer_direction':'WRITE',
       'clock_stretch_limit_us':0,'transfer_bits_bound':9*301}
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':e},300)==e
    assert registry.validate_parameters('i2c',{**I2C_ACTUAL,'payload_bytes':300})['status']=='VALID'
    read10={**I2C_TRANSFER,'address_bits':10,'slave_address':'0x300','transfer_bits_bound':99,'start_stop_bound_us':16.7}
    assert confirmed_serial_evidence('i2c',{'local_timing_evidence':read10},8)==read10


def test_i2c_confirmed_custom_target_and_rate_survive_rejected_isolated_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**I2C_ACTUAL,'bitrate_bps':50000,'i2c_endpoint_role':'TARGET','i2c_address_bits':10,
       'i2c_target_address':768,'i2c_address_purpose':'ORDINARY','i2c_address_source':'actual-straps',
       'payload_bytes':300}
    params={'technology':'i2c',**values,'local_timing_evidence':{**I2C_TRANSFER,'slave_address':'0x300',
       'address_bits':10,'bitrate_bps':50000,'transfer_bits_bound':2727,'start_stop_bound_us':16.7},
       'technology_parameters':{'i2c':{'values':values,'provenance':{
       key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(params)
    assert service.get()['parameters']==params
    bad=deepcopy(params);bad['technology_parameters']['i2c']['values']['i2c_address_bits']=7
    bad['technology_parameters']['i2c']['provenance']['i2c_address_bits']['value']=7
    with pytest.raises(ValueError): service.save_parameters(bad)
    assert service.get()['parameters']==params


CUSTOM_BINARY_ACTUAL = {'cb_specification_source': 'device-protocol.pdf', 'cb_specification_revision': '2.0',
                        'cb_transport_binding': 'device-serial-port-A', 'cb_framing': 'LENGTH_PREFIX'}
CUSTOM_PROTOCOL_ACTUAL = {'cp_specification_source': 'application-spec.pdf', 'cp_specification_revision': '1.4',
                          'cp_transport_binding': 'configured-port-P', 'cp_framing_source': 'spec-section3'}
CUSTOM_TCP_ACTUAL = {'ctcp_specification_source': 'stream-app.pdf', 'ctcp_specification_revision': '3.0',
                     'ctcp_transport_binding': 'actual-tcp-ip-wireless-link', 'ctcp_framing': 'LENGTH_PREFIX'}
CUSTOM_TEXT_ACTUAL = {'ctxt_specification_source': 'text-app.pdf', 'ctxt_specification_revision': '1.2',
                      'ctxt_transport_binding': 'actual-stream-port', 'ctxt_encoding': 'UTF8', 'ctxt_framing': 'DELIMITER'}
CUSTOM_UDP_ACTUAL = {'cudp_specification_source': 'datagram-app.pdf', 'cudp_specification_revision': '4.0',
                     'cudp_transport_binding': 'actual-udp-ip-radio-path', 'cudp_ip_version': 'IPV4', 'cudp_size_mode': 'NORMAL'}


DDS_ACTUAL = {'dds_entity': 'DATAWRITER', 'dds_transport_binding': 'selected-shared-memory-or-RTPS-transport',
              'dds_implementation_source': 'actual-vendor-implementation-and-version'}


DNP_ACTUAL = {'dnp_role': 'MASTER', 'dnp_transport': 'TCP', 'dnp_transport_binding': 'actual-tcp-ip-device-path',
              'dnp_configuration_source': 'actual-device-profile-and-IEEE1815-edition'}
DNP_OUTSTATION_FIELDS = {'dnp_app_confirm_timeout_ms','dnp_select_timeout_ms','dnp_unsolicited_enabled',
                        'dnp_unsolicited_retry_mode','dnp_max_unsolicited_retries','dnp_unsolicited_retry_delay_ms'}


DOIP_ACTUAL={'doip_transport':'TCP','doip_transport_binding':'actual-IP-path-and-transport',
             'doip_edition':'ISO_2019','doip_configuration_source':'actual-OEM-entity-and-implementation'}

EIP_ACTUAL={'eip_mode':'IMPLICIT_IO','eip_transport':'UDP','eip_transport_binding':'actual-UDP-IP-link',
            'eip_configuration_source':'actual-EDS-edition-and-firmware'}
EIP_PACKET={**EIP_ACTUAL,'eip_class':1,'eip_address_bytes':8,'eip_class_sequence_bytes':2,
            'eip_application_bytes':10,'eip_run_idle_present':True,'eip_run_idle_bytes':4,'payload_bytes':16,
            'eip_cpf_layout':'TWO_ITEM','eip_cpf_bytes':34,'eip_packet_bytes':34,'eip_forward_open':'STANDARD',
            'eip_o_to_t_size':16,'eip_size_direction':'O_TO_T','eip_size_mode':'FIXED','eip_size_definition':'OPENER_CPF_DATA'}

FR_ACTUAL={'bitrate_bps':2500000,'fr_profile':'PROTOCOL_3_0_1','fr_configuration_source':'actual-cluster-controller',
           'fr_physical_source':'actual-A-and-B-PHY-topology','fr_schedule_source':'actual-slot-channel-cycle-owner-table'}
FR_PACKET={**FR_ACTUAL,'fr_segment':'STATIC','fr_frame_id':1,'fr_payload_words':4,'fr_static_payload_words':4,
           'payload_bytes':8,'fr_frame_bytes':16,'fr_macro_per_cycle':1000,'fr_macrotick_us':1,
           'fr_microtick_ns':50,'fr_micro_per_cycle':20000,'fr_cycle_us':1000,'fr_cycle_mt':1000,
           'fr_static_slots':2,'fr_static_slot_mt':100,'fr_minislots':20,'fr_minislot_mt':20,
           'fr_symbol_window_mt':0,'fr_nit_mt':400,'fr_correction_start_mt':800,'fr_cycle_count_max':63,
           'fr_repetition':4,'fr_cycle_offset':2,'fr_channels':'AB','fr_tx_channels':'AB'}

FF_ACTUAL={'bitrate_bps':31250,'ff_profile':'H1_VOLTAGE_MODE','ff_configuration_source':'matched-H1-config',
           'ff_cff_source':'actual-device-version.cff','ff_physical_source':'actual-power-and-wiring',
           'ff_schedule_source':'actual-LAS-VCR-block-schedule'}
FF_PACKET={**FF_ACTUAL,'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':'DT','payload_bytes':59,
           'ff_fms_pci_bytes':4,'ff_fas_pci_bytes':1,'ff_dl_sdu_bytes':64,'ff_dl_pci_bytes':5,
           'ff_fcs_bytes':2,'ff_ph_sdu_bytes':71,'ff_preamble_bytes':1,'ff_start_bytes':1,'ff_end_bytes':1,
           'ff_wire_octets':74,'ff_priority':'URGENT','ff_vcr':'PUBLISHER_SUBSCRIBER',
           'ff_access':'SCHEDULED_CD','ff_buffering':'BUFFERED','ff_device_class':'BASIC','ff_las_active':False,
           'ff_address_state':'OPERATIONAL','ff_node_address':32,'ff_fun':20,'ff_nun':12,
           'ff_macrocycle_us':1000000,'ff_scheduled_us':400000,'ff_unscheduled_us':500000,
           'ff_maintenance_us':100000,'ff_publish_offset_us':10000,'ff_exchange_bound_us':30000,
           'ff_cable_type':'TYPE_A','ff_trunk_m':1500,'ff_spurs_total_m':400,'ff_segment_total_m':1900,
           'ff_terminators':2,'ff_terminal_v':24,'ff_supply_ma':100,'ff_devices_ma':90}

FS_ACTUAL={'fsoe_profile':'BASE_5100_1_2','fsoe_role':'MASTER','fsoe_transport_binding':'actual-mapped-black-channel',
           'fsoe_implementation_source':'matched-safety-device-fw','fsoe_connection_source':'actual-connection-config',
           'fsoe_timing_source':'actual-whole-exchange-and-watchdog-evidence'}
FS_PACKET={**FS_ACTUAL,'fsoe_state':'DATA','fsoe_direction':'MASTER_TO_SLAVE','payload_bytes':2,
           'fsoe_master_safe_bytes':2,'fsoe_slave_safe_bytes':4,'fsoe_crc_count':1,'fsoe_crc_word_bytes':2,
           'fsoe_command_bytes':1,'fsoe_connection_bytes':2,'fsoe_frame_bytes':7,'fsoe_pdo_capacity_bytes':7,
           'fsoe_data_command':'PROCESS_DATA','fsoe_command':54,'fsoe_conn_id':1,
           'fsoe_slave_address':42,'fsoe_peer_address':42,'fsoe_sequence':1,'fsoe_parameters_accepted':True,
           'fsoe_master_watchdog_ms':100,'fsoe_slave_watchdog_ms':100,'fsoe_exchange_bound_ms':99.999,
           'fsoe_mapping_source':'actual-PDO-mapping','fsoe_crc_source':'actual-chain-verification',
           'fsoe_safe_output_source':'actual-safety-application','fsoe_assurance_source':'actual-system-validation'}

GC_ACTUAL={'gcan_family':'CAN_CC','gcan_transport_binding':'actual-registered-can-port-A',
           'gcan_implementation_source':'actual-encoding-device-edition','gcan_schedule_source':'actual-ID-interference-and-error-bounds'}
GC_PACKET={**GC_ACTUAL,'gcan_frame_format':'STANDARD','gcan_frame_kind':'DATA','gcan_identifier':2047,'payload_bytes':8}

GS_ACTUAL={'gs_mode':'ASYNC_UART','gs_transport_binding':'actual-UART-port-and-PHY',
           'gs_implementation_source':'actual-UART-driver-clock-revision','gs_framing_source':'actual-message-encoding',
           'gs_uart_profile':'AVR_FRAME_FORMATS','gs_baud_rate':9600}
GS_PACKET={**GS_ACTUAL,'gs_peer_baud_rate':9600,'gs_data_bits':8,'gs_parity':'NONE',
           'gs_start_bits':1,'gs_stop_bits':1,'gs_char_bits':10,'gs_encoded_characters':10,
           'gs_wire_bits':100,'gs_serialization_us':100000000/9600,'gs_gap_bound_us':100,
           'gs_flow_control':'RTS_CTS','gs_flow_bound_us':200,'gs_wire_bound_us':100000000/9600+300,
           'gs_framing':'LENGTH_PREFIX','gs_message_bytes':8,'gs_max_message_bytes':1000,'payload_bytes':8}

GOOSE_ACTUAL={'bitrate_bps':10000000,'goose_profile':'LIBIEC61850_1_6_L2','goose_edition':'ED2',
              'goose_role':'PUBLISHER','goose_binding_source':'actual-L2-ports-and-multicast-path',
              'goose_scl_source':'actual-device.scd','goose_device_source':'actual-firmware-PIXIT',
              'goose_schedule_source':'actual-state-change-burst-and-LAN-schedule'}
GOOSE_PACKET={**GOOSE_ACTUAL,'eth_phy':'10BASE_T','duplex':'FULL','eth_frame_profile':'BASIC_MAC',
              'eth_frame_format':'ETHERTYPE','eth_type_length':35000,'eth_payload_layer':'MAC_CLIENT',
              'eth_tag_mode':'VLAN','eth_vlan_tags':1,'vlan_id':2,'qos_priority':4,
              'eth_client_bytes':108,'eth_pad_bytes':0,'eth_mac_frame_bytes':130,'eth_wire_slot_bytes':150,
              'goose_encoding':'ASN1_BER','goose_ethertype':35000,'goose_vlan_tag':True,
              'goose_header_bytes':8,'goose_apdu_bytes':100,'goose_length_bytes':108,'payload_bytes':108,'mtu_bytes':1500,
              'goose_all_data_bytes':10,'goose_num_entries':3,'goose_actual_entries':3,
              'goose_st_num':1,'goose_sq_num':0,'goose_phase':'STATE_CHANGE','goose_conf_rev':4,'goose_expected_conf_rev':4,
              'goose_test':False,'goose_nds_com':False,'goose_operating_mode':'OPERATIONAL',
              'goose_accept_operational':True,'goose_acceptance_source':'actual-subscriber-commissioning',
              'goose_min_ms':500,'goose_max_ms':5000,'goose_next_ms':500,'goose_tal_basis_ms':500,'goose_tal_ms':1500}

GPIO_ACTUAL={'gpio_profile':'STM8TL5_RM0312_3','gpio_pin':'PB3-on-actual-package',
             'gpio_device_source':'actual-datasheet-pin-and-clock-revision','gpio_wiring_source':'actual-peer-and-load',
             'gpio_direction':'DIGITAL_INPUT'}
GPIO_INPUT={**GPIO_ACTUAL,'gpio_phase':'OPERATING','gpio_pull':'UP','gpio_input_mode':'POLLED',
            'gpio_debounce_enabled':False,'gpio_vdd_v':3.3,'gpio_vil_max_v':0.8,'gpio_vih_min_v':2,
            'gpio_vol_max_v':0.4,'gpio_voh_min_v':2.9,
            'local_timing_evidence':{'sample_bound_ms':5,'source':'actual-polling-schedule-measurement','confirmed':True}}

HART_ACTUAL={'bitrate_bps':1200,'hart_profile':'PUBLIC_FSK_2023','hart_phy':'FSK',
             'hart_revision':'REV7','hart_role':'HOST','hart_binding_source':'actual-modem-loop',
             'hart_device_source':'actual-DD-command-and-preamble-revision','hart_physical_source':'actual-loop-power-and-loading',
             'hart_schedule_source':'actual-dual-host-burst-retry-schedule'}
HART_REQUEST={**HART_ACTUAL,'hart_host_role':'PRIMARY','hart_frame_kind':'REQUEST','hart_mode':'REQUEST_RESPONSE',
              'hart_address_format':'LONG','hart_address_bytes':5,'hart_poll_address':42,'hart_preamble_bytes':5,
              'hart_peer_preamble_bytes':5,'hart_expansion_bytes':0,'hart_delimiter':130,'hart_command':3,
              'hart_status_bytes':0,'hart_data_bytes':10,'payload_bytes':10,'hart_byte_count':10,
              'hart_checksum_bytes':1,'hart_wire_octets':24,'hart_char_bits':11,'hart_wire_bits':264,'hart_serialization_ms':220}

HTTP_ACTUAL={'http_version':'HTTP_1_1','http_transport':'TCP','http_binding_source':'actual-TCP-TLS-IP-device-path',
             'http_implementation_source':'actual-server-client-version-and-config',
             'http_schedule_source':'actual-handshake-request-response-recovery-schedule'}
HTTP_REQUEST={**HTTP_ACTUAL,'http_role':'CLIENT','http_message_kind':'REQUEST','http_method':'POST',
              'http_scheme':'http','http_port_explicit':True,'http_port':13500,'http_origin':'http://device.example:13500/config',
              'http_target_form':'ORIGIN','http_framing':'CONTENT_LENGTH','http_content_length_present':True,
              'http_content_length':'10','http_length_semantics':'MESSAGE_BODY','http_body_bytes':'10','http_transfer_encoding':'NONE'}
HTTP2_DATA={**HTTP_ACTUAL,'http_version':'HTTP_2','http2_frame_type':'DATA','http2_stream_id':1,
            'http2_frame_header_bytes':9,'http2_frame_payload_bytes':14,'http2_frame_bytes':23,
            'http2_max_frame_size':16384,'http2_current_stream_window':14,'http2_current_connection_window':14,
            'http2_pad_length_present':True,'http2_padding_bytes':3,'http2_data_bytes':10}
HTTP3_ACTUAL={**HTTP_ACTUAL,'http_version':'HTTP_3','http_transport':'QUIC_V1','http_tls_version':'TLS_1_3',
              'http_security_source':'actual-QUIC-TLS-origin-certificate-ALPN',
              'http3_quic_source':'actual-QUIC-v1-UDP-IP-radio-path-and-recovery'}


def test_http_versions_have_no_inherited_physical_rate_or_universal_message_size_and_keep_conditional_defaults():
    fields={f['key']:f for f in registry.parameter_fields('http')}
    assert registry.profile('http')['default_stack']==['http']
    assert registry.parameter_defaults_review('http')['values']=={}
    assert not {'bitrate','mtu_bytes','qos_priority','vlan_id','duplex','queue_size','retry_limit'} & fields.keys()
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert fields['http2_header_table_size']['conditional_defaults']==[
        {'when':{'http_version':'HTTP_2','http2_settings_phase':'INITIAL_DEFAULTS'},'value':4096}]
    assert fields['http3_qpack_max_table']['conditional_defaults']==[
        {'when':{'http_version':'HTTP_3','http3_settings_phase':'INITIAL_1RTT'},'value':'0'}]
    for key in ('http_port','http_version','http_body_bytes','http2_max_concurrent_streams',
                'http2_max_header_list_bytes','http3_max_field_section_bytes','http_request_timeout_ms'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('http',HTTP_REQUEST)['status']=='VALID'
    assert registry.validate_parameters('http',HTTP2_DATA)['status']=='VALID'
    assert registry.validate_parameters('http',HTTP3_ACTUAL)['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('http'),ids=lambda f:'http/'+f['key'])
def test_every_http_parameter_has_its_own_version_transport_role_and_scalar_type(field):
    key=field['key']
    value=(field['options'][0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    values={**(HTTP3_ACTUAL if key.startswith('http3_') else HTTP_ACTUAL),key:value}
    if key.startswith('http2_'): values['http_version']='HTTP_2'
    if key in {'http_content_length','http_body_bytes','http_wire_message_bytes'} or key.startswith('http3_') and field['type']=='text' and key!='http3_quic_source':
        value='0'; values[key]=value
    if key=='http_method': value='PATCH'; values[key]=value
    if key=='http_origin': value='http://actual.example/path'; values[key]=value
    if key=='http_message_kind': values['http_method']='GET'
    if key=='http_content_length': values.update(http_content_length_present=True,http_length_semantics='MESSAGE_BODY')
    if key=='http_transfer_encoding': value='NONE'; values[key]=value
    assert registry.validate_parameters('http',values)['status']=='VALID'
    assert registry.validate_parameters('http',{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('http',{**values,key:field[bound]+offset})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'http_content_length':'11'},{'http_body_bytes':'9'},{'http_content_length':'-10'},
    {'http_content_length':'10.0'},{'http_content_length':10},{'http_method':'GET\r\nX:y'},
    {'http_content_length_present':False},{'http_transfer_encoding':'CHUNKED','http_transfer_source':'actual-chunks'},
    {'http_origin':'http:///path'},{'http_origin':'http://device.example/#fragment'},
    {'http_status':200},{'http_target_form':'AUTHORITY'},{'http_target_form':'ASTERISK'},
    {'http_framing':'CLOSE_DELIMITED'},{'bitrate':500000},{'mtu_bytes':65535},
    {'http2_max_frame_size':16384},{'http3_frame_length':'10'},{'http_unknown_scalar':1},
])
def test_http1_checks_message_length_target_and_version_without_foreign_defaults(patch):
    assert registry.validate_parameters('http',{**HTTP_REQUEST,**patch})['status']=='INVALID'


def test_http_decimal_lengths_keep_exact_large_values_and_head_metadata_separate_from_empty_body():
    huge='1'+'0'*5000  # Beyond Python's decimal-to-int conversion limit; no float/int conversion is required.
    assert registry.validate_parameters('http',{**HTTP_REQUEST,'http_content_length':huge,'http_body_bytes':huge})['status']=='VALID'
    assert registry.validate_parameters('http',{**HTTP_REQUEST,'http_content_length':huge,'http_body_bytes':huge[:-1]+'1'})['status']=='INVALID'
    assert registry.validate_parameters('http',{**HTTP_REQUEST,'http_content_length':'00010'})['status']=='VALID'
    head={**HTTP_ACTUAL,'http_message_kind':'RESPONSE','http_method':'HEAD','http_status':200,
          'http_content_length_present':True,'http_content_length':'1000000','http_length_semantics':'SELECTED_REPRESENTATION','http_body_bytes':'0'}
    assert registry.validate_parameters('http',head)['status']=='VALID'
    assert registry.validate_parameters('http',{**head,'http_body_bytes':'1'})['status']=='INVALID'
    for status in (101,204,205,304):
        no_content={**HTTP_ACTUAL,'http_message_kind':'RESPONSE','http_status':status,'http_body_bytes':'0'}
        assert registry.validate_parameters('http',no_content)['status']=='VALID'
        assert registry.validate_parameters('http',{**no_content,'http_body_bytes':'1'})['status']=='INVALID'
    assert registry.validate_parameters('http',{**HTTP_ACTUAL,'http_message_kind':'RESPONSE','http_status':204,
        'http_content_length_present':True,'http_content_length':'0','http_length_semantics':'MESSAGE_BODY'})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'http_transport':'QUIC_V1'},{'http2_frame_header_bytes':8},{'http2_stream_id':0},
    {'http2_frame_payload_bytes':13},{'http2_frame_bytes':22},{'http2_padding_bytes':4},
    {'http2_current_stream_window':13},{'http2_current_stream_window':-1},{'http2_current_connection_window':13},
    {'http2_pad_length_present':False},{'http2_max_frame_size':16383},
    {'http_transfer_encoding':'CHUNKED'},{'http3_qpack_max_table':'0'},
])
def test_http2_data_accounts_for_pad_length_and_both_receiver_windows(patch):
    assert registry.validate_parameters('http',{**HTTP2_DATA,**patch})['status']=='INVALID'


def test_http2_control_frame_sizes_and_stream_ids_do_not_use_data_frame_rules():
    for kind,size,stream in [('PING',8,0),('PRIORITY',5,1),('RST_STREAM',4,1),('WINDOW_UPDATE',4,0),('SETTINGS',12,0)]:
        frame={**HTTP_ACTUAL,'http_version':'HTTP_2','http2_frame_type':kind,'http2_stream_id':stream,
               'http2_frame_payload_bytes':size}
        assert registry.validate_parameters('http',frame)['status']=='VALID'
        assert registry.validate_parameters('http',{**frame,'http2_frame_payload_bytes':size+1})['status']=='INVALID'
    server={**HTTP_ACTUAL,'http_version':'HTTP_2','http_role':'SERVER','http2_enable_push':0}
    assert registry.validate_parameters('http',server)['status']=='VALID'
    assert registry.validate_parameters('http',{**server,'http2_enable_push':1})['status']=='INVALID'
    # SETTINGS reductions can leave a negative stream window; this is state, not an unsigned limit.
    assert registry.validate_parameters('http',{**HTTP_ACTUAL,'http_version':'HTTP_2','http2_current_stream_window':-10})['status']=='VALID'


@pytest.mark.parametrize('key',['http3_frame_type','http3_frame_length','http3_qpack_max_table','http3_qpack_blocked_streams','http3_max_field_section_bytes'])
def test_every_http3_quic_integer_preserves_uint62_without_json_number_rounding(key):
    assert registry.validate_parameters('http',{**HTTP3_ACTUAL,key:'4611686018427387903'})['status']=='VALID'
    for value in ('4611686018427387904','-1','1.2','0001',4611686018427387903,True):
        assert registry.validate_parameters('http',{**HTTP3_ACTUAL,key:value})['status']=='INVALID'


def test_http3_stream_scope_security_and_initial_qpack_are_not_http2_or_tcp():
    for patch in ({'http_transport':'TCP'},{'http_tls_version':'TLS_1_2'},
                  {'http2_header_table_size':4096},{'http3_stream_kind':'CONTROL','http3_frame_type':'0'},
                  {'http3_stream_kind':'REQUEST','http3_frame_type':'4'},
                  {'http3_stream_kind':'QPACK_ENCODER','http3_frame_type':'0'}):
        assert registry.validate_parameters('http',{**HTTP3_ACTUAL,**patch})['status']=='INVALID'
    assert registry.validate_parameters('http',{**HTTP3_ACTUAL,'http3_stream_kind':'REQUEST','http3_frame_type':'33'})['status']=='VALID'
    optimistic={**HTTP_ACTUAL,'http_transition_optimistic':True}
    assert registry.validate_parameters('http',optimistic)['status']=='UNVERIFIED'
    assert registry.validate_parameters('http',{**optimistic,'http_transition_token':'TLS',
        'http_transition_source':'actual-confirmation-and-safe-byte-prefix-policy'})['status']=='VALID'


def test_http_semantics_do_not_accept_representation_lengths_for_normal_responses_or_forbidden_optimistic_upgrades():
    response={**HTTP_ACTUAL,'http_message_kind':'RESPONSE','http_method':'GET','http_status':200,
              'http_content_length_present':True,'http_content_length':'10','http_length_semantics':'SELECTED_REPRESENTATION','http_body_bytes':'5'}
    assert registry.validate_parameters('http',response)['status']=='INVALID'
    assert registry.validate_parameters('http',{**response,'http_status':304,'http_body_bytes':'000'})['status']=='VALID'
    for token in ('WEBSOCKET','CONNECT_UDP','CONNECT_IP'):
        assert registry.validate_parameters('http',{**HTTP_ACTUAL,'http_transition_token':token,
            'http_transition_optimistic':True,'http_transition_source':'a-source-does-not-overrule-this-rule'})['status']=='INVALID'
    connect={**HTTP_ACTUAL,'http_transition_token':'CONNECT_TCP','http_connect_untrusted':True}
    assert registry.validate_parameters('http',connect)['status']=='UNVERIFIED'
    assert registry.validate_parameters('http',{**connect,'http_wait_success':False})['status']=='INVALID'
    assert registry.validate_parameters('http',{**connect,'http_wait_success':True})['status']=='VALID'
    assert registry.validate_parameters('http',{**connect,'http_wait_success':False,'http_connection_close':True})['status']=='VALID'
    rejected={**connect,'http_transition_rejected':True,'http_role':'PROXY','http_wait_success':True}
    assert registry.validate_parameters('http',rejected)['status']=='UNVERIFIED'
    assert registry.validate_parameters('http',{**rejected,'http_connection_close':False})['status']=='INVALID'
    assert registry.validate_parameters('http',{**rejected,'http_connection_close':True})['status']=='VALID'


def test_http_confirmed_explicit_port_and_actual_peer_http2_settings_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**HTTP2_DATA,'http2_settings_phase':'PEER_ADVERTISED','http2_header_table_size':8192,
            'http2_initial_window_size':100000,'http_port':13500,'http_port_explicit':True}
    parameters={'technology':'http',**values,'technology_parameters':{'http':{'values':values.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['http']['values']['http2_frame_payload_bytes']=13
    bad['technology_parameters']['http']['provenance']['http2_frame_payload_bytes']['value']=13
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_hart_standard_fsk_rate_is_a_proposal_and_not_a_wireless_ip_or_c8psk_fallback():
    fields={f['key']:f for f in registry.parameter_fields('hart')}
    review=registry.parameter_defaults_review('hart')
    assert review['values']=={'bitrate_bps':1200} and review['basis']=='WIRED_FSK_BASELINE'
    assert not {'qos_priority','queue_size','queue_policy','reserved_bandwidth_percent','sync_method','retry_limit'} & fields.keys()
    for key in ('payload_bytes','hart_preamble_bytes','hart_peer_preamble_bytes','hart_poll_address',
                'hart_profile','hart_device_id','hart_burst_period_ms','hart_loop_load_ohms','hart_loop_supply_v'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('hart',HART_REQUEST)['status']=='VALID'
    assert registry.validate_parameters('hart',{**HART_ACTUAL,'hart_phy':'C8PSK'})['status']=='INVALID'
    c8={**HART_ACTUAL,'hart_phy':'C8PSK','hart_profile':'DEVICE_SPECIFIC','bitrate_bps':9600}
    assert registry.validate_parameters('hart',c8)['status']=='VALID'
    # FSK character bounds cannot certify a different modulation or device codec.
    assert registry.validate_parameters('hart',{**c8,'hart_char_bits':11})['status']=='UNVERIFIED'
    for rate in (500000,100000000,250000,True,'1200'):
        assert registry.validate_parameters('hart',{**HART_ACTUAL,'bitrate_bps':rate})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('hart'),ids=lambda f:'hart/'+f['key'])
def test_every_hart_parameter_has_typed_applicable_bounds_in_its_qualified_scope(field):
    key=field['key']
    value=(field['options'][0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    values={**HART_ACTUAL,key:value}
    if key=='bitrate': value=1200; values[key]=value
    if key in {'hart_burst_period_ms','hart_loop_supply_v','hart_signal_pp_ma'}: value=1; values[key]=value
    if key=='hart_extended_command': values.update(hart_command=31,hart_data_bytes=2)
    if key in {'hart_slave_timeout_chars','hart_hold_chars','hart_link_grant_chars','hart_quiet_chars'}:
        values.update(hart_profile='FCG_FSK_2016',hart_host_role='PRIMARY')
    if key=='hart_quiet_chars': value=33; values[key]=value
    assert registry.validate_parameters('hart',values)['status']=='VALID'
    assert registry.validate_parameters('hart',{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('hart',{**values,key:field[bound]+offset})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'hart_address_bytes':2},{'hart_preamble_bytes':4},{'hart_peer_preamble_bytes':6},
    {'hart_byte_count':12},{'hart_status_bytes':2},{'hart_wire_octets':22},{'hart_wire_bits':192},
    {'hart_char_bits':10},{'hart_serialization_ms':160},{'hart_delimiter':2},{'hart_delimiter':134},
    {'hart_revision':'REV5_OR_EARLIER'},{'hart_role':'FIELD_DEVICE'},
    {'hart_extended_command':512},{'hart_mode':'BURST','hart_burst_supported':False},
    {'hart_loop_supply_v':0},{'hart_signal_pp_ma':0},{'hart_burst_period_ms':0},
    {'qos_priority':3},{'mtu_bytes':1500},{'hart_unregistered_mode':1},
])
def test_hart_checks_whole_wire_frame_role_revision_and_device_dependencies(patch):
    assert registry.validate_parameters('hart',{**HART_REQUEST,**patch})['status']=='INVALID'


def test_hart_request_response_count_and_extended_command_are_separate_from_data_payload():
    response={**HART_REQUEST,'hart_role':'FIELD_DEVICE','hart_frame_kind':'RESPONSE',
              'hart_status_bytes':2,'hart_byte_count':12,'hart_delimiter':134,
              'hart_wire_octets':26,'hart_wire_bits':286,'hart_serialization_ms':286000/1200}
    assert registry.validate_parameters('hart',response)['status']=='VALID'
    maximum={**HART_ACTUAL,'hart_role':'FIELD_DEVICE','hart_frame_kind':'RESPONSE',
             'hart_status_bytes':2,'hart_data_bytes':253,'hart_byte_count':255}
    assert registry.validate_parameters('hart',maximum)['status']=='VALID'
    assert registry.validate_parameters('hart',{**maximum,'hart_data_bytes':254})['status']=='INVALID'
    extended={**HART_REQUEST,'hart_command':31,'hart_extended_command':512}
    assert registry.validate_parameters('hart',extended)['status']=='VALID'
    assert registry.validate_parameters('hart',{**HART_ACTUAL,'hart_command':31,'hart_extended_command':512,'hart_data_bytes':1})['status']=='INVALID'
    burst={**response,'hart_frame_kind':'BURST','hart_mode':'BURST','hart_burst_supported':True,'hart_delimiter':129}
    assert registry.validate_parameters('hart',burst)['status']=='VALID'


def test_hart_qualified_character_timers_distinguish_hosts_and_actual_response_start():
    timers={**HART_REQUEST,'hart_profile':'FCG_FSK_2016','hart_slave_timeout_chars':28,
            'hart_hold_chars':2,'hart_link_grant_chars':8,'hart_quiet_chars':33,
            'hart_gap_us':9000,'hart_response_start_ms':256}
    assert registry.validate_parameters('hart',timers)['status']=='VALID'
    for patch in ({'hart_gap_us':11000000/1200},{'hart_response_start_ms':257},
                  {'hart_slave_timeout_chars':29},{'hart_hold_chars':1},{'hart_link_grant_chars':7},
                  {'hart_host_role':'SECONDARY'}):
        assert registry.validate_parameters('hart',{**timers,**patch})['status']=='INVALID'
    assert registry.validate_parameters('hart',{**timers,'hart_host_role':'SECONDARY','hart_quiet_chars':41})['status']=='VALID'
    hazard={**HART_ACTUAL,'hart_is_required':True}
    assert registry.validate_parameters('hart',hazard)['status']=='UNVERIFIED'
    assert registry.validate_parameters('hart',{**hazard,'hart_is_source':'actual-certified-barrier-loop-entities'})['status']=='VALID'


def test_hart_confirmed_long_address_frame_and_peer_preamble_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'hart',**HART_REQUEST,'technology_parameters':{'hart':{'values':HART_REQUEST.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in HART_REQUEST.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['hart']['values']['hart_wire_bits']=192
    bad['technology_parameters']['hart']['provenance']['hart_wire_bits']['value']=192
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_gpio_has_no_bus_frame_and_no_universal_operating_voltage_or_reset_configuration():
    fields={f['key']:f for f in registry.parameter_fields('gpio')}
    assert not {'payload_bytes','bitrate','queue_policy','qos_priority','retry_limit','target_bus_load_percent'} & fields.keys()
    assert registry.parameter_defaults_review('gpio')['values']=={}
    assert registry.profile('gpio')['capacity_evidence']['status']=='NOT_APPLICABLE'
    assert fields['gpio_direction']['conditional_defaults']==[
        {'when':{'gpio_profile':'STM8TL5_RM0312_3','gpio_phase':'RESET','gpio_reset_exception':False},'value':'DIGITAL_INPUT'}]
    assert all('default' not in fields[key] for key in ('gpio_profile','gpio_direction','gpio_pull','gpio_vdd_v',
        'gpio_level','gpio_active_low','gpio_sink_bound_ma','gpio_rise_bound_ns'))
    assert registry.validate_parameters('gpio',GPIO_INPUT)['status']=='VALID'
    assert registry.validate_parameters('gpio',{**GPIO_ACTUAL,'bitrate':500000})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('gpio'),ids=lambda f:'gpio/'+f['key'])
def test_every_gpio_pin_and_application_parameter_uses_its_actual_role_and_type(field):
    key=field['key']
    value=(field['options'][0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    if key in {'gpio_vdd_v','gpio_pull_ohms'}: value=1
    values={**GPIO_ACTUAL,key:value}
    if key in {'gpio_drive','gpio_sink_load_ma','gpio_source_load_ma'}: values['gpio_direction']='DIGITAL_OUTPUT'
    assert registry.validate_parameters('gpio',values)['status']=='VALID'
    assert registry.validate_parameters('gpio',{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('gpio',{**values,key:field[bound]+offset})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'gpio_drive':'PUSH_PULL'},{'gpio_source_load_ma':1},{'gpio_event':'RISING'},
    {'gpio_pull':'DOWN'},{'gpio_vdd_v':0},{'gpio_vil_max_v':2.1},{'gpio_vol_max_v':0.9},
    {'gpio_voh_min_v':1.9},{'gpio_pull_ohms':0},{'gpio_port_typo':1},{'mtu_bytes':1500},
])
def test_gpio_checks_actual_voltage_compatibility_and_rejects_foreign_bus_or_output_fields(change):
    assert registry.validate_parameters('gpio',{**GPIO_INPUT,**change})['status']=='INVALID'


def test_gpio_reset_exceptions_and_output_load_are_distinct_from_operating_input():
    reset={**GPIO_ACTUAL,'gpio_phase':'RESET','gpio_reset_exception':False,'gpio_pull':'NONE'}
    assert registry.validate_parameters('gpio',reset)['status']=='VALID'
    assert registry.validate_parameters('gpio',{**reset,'gpio_pull':'UP'})['status']=='INVALID'
    assert registry.validate_parameters('gpio',{**reset,'gpio_reset_exception':True,'gpio_pull':'UP'})['status']=='VALID'
    output={**GPIO_ACTUAL,'gpio_direction':'DIGITAL_OUTPUT','gpio_pull':'NONE','gpio_drive':'PUSH_PULL',
            'gpio_sink_bound_ma':4,'gpio_sink_load_ma':4,'gpio_source_bound_ma':2,'gpio_source_load_ma':2}
    assert registry.validate_parameters('gpio',output)['status']=='VALID'
    for key,value in [('gpio_sink_load_ma',4.01),('gpio_source_load_ma',2.01),('gpio_input_mode','POLLED')]:
        assert registry.validate_parameters('gpio',{**output,key:value})['status']=='INVALID'
    open_drain={**output,'gpio_drive':'TRUE_OPEN_DRAIN'}
    assert registry.validate_parameters('gpio',open_drain)['status']=='UNVERIFIED'
    assert registry.validate_parameters('gpio',{**open_drain,'gpio_pull_source':'actual-pullup-wiring-and-rise'})['status']=='VALID'


@pytest.mark.parametrize('key',['sample_bound_ms','debounce_bound_ms','edge_detection_bound_ms','update_bound_ms'])
@pytest.mark.parametrize('value',[True,'5',-0.001,float('inf'),float('nan')])
def test_every_gpio_local_timing_bound_rejects_false_numeric_evidence(key,value):
    evidence={'sample_bound_ms':5,key:value,'source':'actual-device-timing','confirmed':True}
    assert registry.validate_parameters('gpio',{**GPIO_INPUT,'local_timing_evidence':evidence})['status']=='INVALID'


def test_gpio_timing_completeness_depends_on_input_poll_interrupt_debounce_or_output_role():
    confirmed={'source':'actual-device-and-task-timing','confirmed':True}
    polling={**GPIO_INPUT,'local_timing_evidence':{**confirmed,'sample_bound_ms':5}}
    assert registry.validate_parameters('gpio',polling)['status']=='VALID'
    assert registry.validate_parameters('gpio',{**polling,'local_timing_evidence':confirmed})['status']=='INVALID'
    interrupt={**GPIO_ACTUAL,'gpio_input_mode':'INTERRUPT','gpio_event':'BOTH_EDGES',
               'local_timing_evidence':{**confirmed,'edge_detection_bound_ms':0.1}}
    assert registry.validate_parameters('gpio',interrupt)['status']=='VALID'
    assert registry.validate_parameters('gpio',{**interrupt,'local_timing_evidence':confirmed})['status']=='INVALID'
    debounced={**polling,'gpio_debounce_enabled':True}
    assert registry.validate_parameters('gpio',debounced)['status']=='INVALID'
    assert registry.validate_parameters('gpio',{**debounced,'local_timing_evidence':{**confirmed,'sample_bound_ms':5,'debounce_bound_ms':10}})['status']=='VALID'
    output={**GPIO_ACTUAL,'gpio_direction':'DIGITAL_OUTPUT',
            'local_timing_evidence':{**confirmed,'update_bound_ms':0.2}}
    assert registry.validate_parameters('gpio',output)['status']=='VALID'
    # An output uses its update bound; input polling does not substitute for it.
    assert registry.validate_parameters('gpio',{**output,'local_timing_evidence':{**confirmed,'sample_bound_ms':5}})['status']=='INVALID'
    for patch in ({'confirmed':'true'},{'source':7},{'source':' '},{'technology':'i2c'}):
        assert registry.validate_parameters('gpio',{**polling,'local_timing_evidence':{**polling['local_timing_evidence'],**patch}})['status']=='INVALID'


def test_gpio_confirmed_operating_pin_and_input_evidence_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    pin_values={key:value for key,value in GPIO_INPUT.items() if key!='local_timing_evidence'}
    parameters={'technology':'gpio',**GPIO_INPUT,'technology_parameters':{'gpio':{'values':pin_values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in pin_values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['gpio']['values']['gpio_vol_max_v']=1
    bad['technology_parameters']['gpio']['provenance']['gpio_vol_max_v']['value']=1
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_goose_uses_explicit_ieee8023_transport_and_conditional_implementation_defaults():
    profile=registry.profile('goose')
    fields={f['key']:f for f in registry.parameter_fields('goose')}
    review=registry.parameter_defaults_review('goose')
    assert profile['domain']=='generic_networking' and profile['default_bitrate'] is None
    assert review['rate_profile']=='ethernet' and review['values']=={'bitrate_bps':10000000}
    assert review['source']==registry.parameter_defaults_review('ethernet')['source']
    assert fields['qos_priority']['conditional_defaults']==[
        {'when':{'goose_profile':'LIBIEC61850_1_6_L2','goose_vlan_tag':True},'value':4}]
    assert fields['goose_min_ms']['conditional_defaults']==[
        {'when':{'goose_profile':'LIBIEC61850_1_6_L2','goose_schedule_origin':'STACK_FALLBACK'},'value':500}]
    for name in ('payload_bytes','goose_profile','goose_edition','goose_st_num','goose_conf_rev','goose_test',
                 'goose_min_ms','goose_max_ms','goose_tal_ms','goose_accept_operational'):
        assert 'default' not in fields[name]
    assert not {'retry_limit','retransmission_enabled','sync_method','gateway_maximum_throughput'} & fields.keys()
    assert not profile['capabilities']['supports_safety_profile']
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('goose',GOOSE_PACKET)['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('goose'),ids=lambda f:'goose/'+f['key'])
def test_every_goose_native_and_shared_ethernet_parameter_has_individual_validation(field):
    if not field['key'].startswith('goose_'):
        _assert_ethernet_scalar_bounds('goose',field,GOOSE_ACTUAL,{'eth_type_length':35000})
        return
    key=field['key']
    value=(field['options'][0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    if key=='goose_ethertype': value=35000
    values={**GOOSE_ACTUAL,key:value}
    assert registry.validate_parameters('goose',values)['status']=='VALID'
    assert registry.validate_parameters('goose',{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('goose',{**values,key:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('goose',{**values,key:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'goose_ethertype':35002},{'eth_type_length':35002},{'goose_encoding':'FIXED_LENGTH'},
    {'goose_header_bytes':9},{'goose_length_bytes':109},{'payload_bytes':100},
    {'eth_client_bytes':100},{'eth_mac_frame_bytes':126},{'goose_all_data_bytes':101},
    {'goose_num_entries':2},{'goose_sq_num':1},{'goose_tal_ms':1000},{'goose_next_ms':1501},
    {'goose_max_ms':499},{'goose_expected_conf_rev':5},{'goose_nds_com':True},
    {'goose_test':True},{'goose_operating_mode':'TEST'},{'goose_reserved1':32768},
    {'eth_vlan_tags':0},{'goose_vlan_tag':False},{'mtu_bytes':107},{'doip_port':13400},
    {'goose_udp_port':102},{'bitrate_bps':250000},{'eth_peer_rate_bps':100000000},
])
def test_goose_mac_packet_lifecycle_and_operational_acceptance_use_actual_selected_profile(change):
    assert registry.validate_parameters('goose',{**GOOSE_PACKET,**change})['status']=='INVALID'


def test_goose_data_revision_test_and_device_variant_are_not_automatically_certified():
    state={**GOOSE_PACKET,'goose_phase':'STABLE','goose_next_ms':5000,'goose_tal_basis_ms':5000,'goose_tal_ms':15000,'goose_sq_num':4}
    assert registry.validate_parameters('goose',state)['status']=='VALID'
    assert registry.validate_parameters('goose',{**state,'goose_tal_ms':10000})['status']=='INVALID'
    monitor={**GOOSE_PACKET,'goose_test':True,'goose_operating_mode':'MONITOR','goose_accept_operational':False}
    assert registry.validate_parameters('goose',monitor)['status']=='VALID'
    missing={**GOOSE_PACKET,'goose_expected_conf_rev':None}
    assert registry.validate_parameters('goose',missing)['status']=='UNVERIFIED'
    other={**GOOSE_ACTUAL,'goose_profile':'DEVICE_SPECIFIC','goose_st_num':1}
    assert registry.validate_parameters('goose',other)['status']=='UNVERIFIED'
    assert registry.validate_parameters('goose',{**GOOSE_ACTUAL,'goose_min_ms':4,'goose_max_ms':1000})['status']=='VALID'
    # Explicit rate-source metadata must never route to a foreign or absent layer.
    for source in ('can','unknown_transport'):
        local=TechnologyRegistry()
        bad=registry.profile('goose')
        bad['rate_source_profile_id']=source
        local.register_defaults([registry.profile('ethernet'),bad])
        with pytest.raises(ValueError,match='explicitly registered stack layer'):
            local.parameter_defaults_review('goose')


def test_goose_confirmed_scl_and_vlan_parameters_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'goose',**GOOSE_PACKET,'technology_parameters':{'goose':{'values':GOOSE_PACKET.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in GOOSE_PACKET.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['goose']['values']['goose_test']=True
    bad['technology_parameters']['goose']['provenance']['goose_test']['value']=True
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_generic_serial_defaults_are_conditional_uart_tutorial_not_universal_serial_clock():
    profile=registry.profile('generic_serial')
    fields={f['key']:f for f in registry.parameter_fields('generic_serial')}
    assert profile['domain']=='generic_networking' and profile['default_stack']==['generic_serial']
    assert registry.parameter_defaults_review('generic_serial')['values']=={}
    assert profile['max_payload_bytes'] is None and 'max' not in fields['payload_bytes']
    assert not {'bitrate','retry_limit','queue_size','qos_priority','sync_method'} & fields.keys()
    assert fields['gs_baud_rate']['conditional_defaults']==[
        {'when':{'gs_mode':'ASYNC_UART','gs_uart_profile':'TB3216_8N1'},'value':9600}]
    assert all('default' not in fields[key] for key in ('payload_bytes','gs_mode','gs_uart_profile','gs_baud_rate',
        'gs_clock_hz','gs_peer_baud_rate','gs_flow_bound_us','gs_max_message_bytes'))
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('generic_serial',GS_PACKET)['status']=='VALID'
    assert registry.validate_parameters('generic_serial',{**GS_ACTUAL,'bitrate':500000})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('generic_serial'),ids=lambda field:'generic_serial/'+field['key'])
def test_every_generic_serial_parameter_is_individually_typed_and_scoped(field):
    value=(field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    value={'gs_data_bits':5,'gs_stop_bits':1,'gs_peer_baud_rate':9600}.get(field['key'],value)
    parameters={**GS_ACTUAL,field['key']:value}
    if field['key'] in {'gs_clock_hz','gs_cdc_line_coding_role'}:
        parameters={key:item for key,item in parameters.items() if key not in {'gs_uart_profile','gs_baud_rate'}}
        parameters['gs_mode']='SYNC_SERIAL' if field['key']=='gs_clock_hz' else 'USB_CDC'
    assert registry.validate_parameters('generic_serial',parameters)['status']=='VALID'
    wrong='wrong' if field['type']=='number' else 1
    assert registry.validate_parameters('generic_serial',{**parameters,field['key']:wrong})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('generic_serial',{**parameters,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('generic_serial',{**parameters,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'gs_peer_baud_rate':19200},{'gs_data_bits':4},{'gs_stop_bits':1.5},{'gs_start_bits':2},
    {'gs_parity':'MARK'},{'gs_char_bits':8},{'gs_wire_bits':80},{'gs_serialization_us':80000000/9600},
    {'gs_wire_bound_us':100000000/9600+299},{'gs_message_bytes':1001},
    {'gs_clock_hz':9600},{'gs_cdc_line_coding_role':'NATIVE_ADVISORY'},{'gs_typo_baud':9600},
])
def test_generic_serial_uart_validates_character_overhead_peer_and_actual_flow_bounds(change):
    assert registry.validate_parameters('generic_serial',{**GS_PACKET,**change})['status']=='INVALID'


def test_generic_serial_uart_frame_formats_and_non_uart_modes_remain_separate():
    parity={**GS_PACKET,'gs_data_bits':7,'gs_parity':'EVEN','gs_stop_bits':2,'gs_char_bits':11,
            'gs_wire_bits':110,'gs_serialization_us':110000000/9600,'gs_wire_bound_us':110000000/9600+300}
    assert registry.validate_parameters('generic_serial',parity)['status']=='VALID'
    tutorial={**GS_PACKET,'gs_uart_profile':'TB3216_8N1'}
    assert registry.validate_parameters('generic_serial',tutorial)['status']=='VALID'
    assert registry.validate_parameters('generic_serial',{**tutorial,'gs_parity':'EVEN'})['status']=='INVALID'
    # Tutorial proposal9600 is not a mandatory baud or a lowest physical rate.
    assert registry.validate_parameters('generic_serial',{**GS_ACTUAL,'gs_uart_profile':'TB3216_8N1',
        'gs_baud_rate':1200,'gs_peer_baud_rate':1200})['status']=='VALID'
    common={key:value for key,value in GS_ACTUAL.items() if key not in {'gs_uart_profile','gs_baud_rate'}}
    for mode,patch in [('SYNC_SERIAL',{'gs_clock_hz':1000000}),('USB_CDC',{'gs_cdc_line_coding_role':'NATIVE_ADVISORY'}),
                       ('CUSTOM_STREAM',{})]:
        assert registry.validate_parameters('generic_serial',{**common,'gs_mode':mode,**patch})['status']=='VALID'
        assert registry.validate_parameters('generic_serial',{**common,'gs_mode':mode,**patch,'gs_baud_rate':9600})['status']=='INVALID'
    assert registry.validate_parameters('generic_serial',{**common,'gs_mode':'SYNC_SERIAL'})['status']=='UNVERIFIED'
    assert registry.validate_parameters('generic_serial',{**common,'gs_mode':'USB_CDC'})['status']=='UNVERIFIED'
    # Actual API/message bounds are not a fabricated65535-octet transport ceiling.
    assert registry.validate_parameters('generic_serial',{**GS_ACTUAL,'payload_bytes':70000,
        'gs_message_bytes':80000,'gs_max_message_bytes':80000})['status']=='VALID'


def test_generic_serial_confirmed_peer_framing_and_clock_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'generic_serial',**GS_PACKET,'technology_parameters':{'generic_serial':{'values':GS_PACKET.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in GS_PACKET.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['generic_serial']['values']['gs_wire_bits']=80
    bad['technology_parameters']['generic_serial']['provenance']['gs_wire_bits']['value']=80
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_generic_can_is_explicit_family_wrapper_without_unsourced_half_megabit_default():
    profile=registry.profile('generic_can')
    fields={f['key']:f for f in registry.parameter_fields('generic_can')}
    assert profile['domain']=='generic_networking' and profile['default_stack']==['generic_can']
    assert registry.parameter_defaults_review('generic_can')['values']=={}
    assert not {'bitrate','qos_priority','queue_policy','queue_size','retry_limit','gateway_maximum_throughput'} & fields.keys()
    assert all('default' not in fields[key] for key in ('payload_bytes','gcan_family','gcan_identifier','gcan_priority_id'))
    assert registry.validate_parameters('generic_can',GC_PACKET)['status']=='VALID'
    for rate in (500000,10000000):
        assert registry.validate_parameters('generic_can',{**GC_ACTUAL,'bitrate_bps':rate})['status']=='INVALID'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('generic_can'),ids=lambda field:'generic_can/'+field['key'])
def test_every_generic_can_parameter_is_individually_typed_with_its_family_scope(field):
    value=(field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    family='CAN_XL' if field['key'] in {'gcan_priority_id','gcan_acceptance_field'} else 'CAN_CC'
    parameters={**GC_ACTUAL,'gcan_family':family,field['key']:value}
    assert registry.validate_parameters('generic_can',parameters)['status']=='VALID'
    assert registry.validate_parameters('generic_can',{**parameters,field['key']:'wrong' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('generic_can',{**parameters,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('generic_can',{**parameters,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'payload_bytes':9},{'gcan_identifier':2048},{'gcan_frame_format':'XL'},
    {'gcan_priority_id':0},{'gcan_acceptance_field':0},{'gcan_requested_bytes':8},
    {'gcan_frame_kind':'REMOTE'},
])
def test_generic_can_cc_rejects_fd_xl_fields_and_remote_payload(change):
    assert registry.validate_parameters('generic_can',{**GC_PACKET,**change})['status']=='INVALID'


def test_generic_can_cc_fd_xl_payload_and_remote_formats_are_independent():
    remote={**GC_PACKET,'gcan_frame_kind':'REMOTE','payload_bytes':0,'gcan_requested_bytes':8}
    assert registry.validate_parameters('generic_can',remote)['status']=='VALID'
    fd={**GC_PACKET,'gcan_family':'CAN_FD','payload_bytes':64,'gcan_frame_format':'EXTENDED','gcan_identifier':536870911}
    assert registry.validate_parameters('generic_can',fd)['status']=='VALID'
    assert registry.validate_parameters('generic_can',{**fd,'payload_bytes':10})['status']=='INVALID'
    assert registry.validate_parameters('generic_can',{**fd,'gcan_frame_kind':'REMOTE','payload_bytes':0})['status']=='INVALID'
    xl={**GC_ACTUAL,'gcan_family':'CAN_XL','gcan_frame_format':'XL','gcan_frame_kind':'DATA',
        'gcan_priority_id':2047,'gcan_acceptance_field':4294967295,'payload_bytes':2048}
    assert registry.validate_parameters('generic_can',xl)['status']=='VALID'
    assert registry.validate_parameters('generic_can',{**xl,'payload_bytes':0})['status']=='INVALID'
    assert registry.validate_parameters('generic_can',{**xl,'gcan_identifier':1})['status']=='INVALID'


def test_generic_can_confirmed_family_link_and_identifier_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'generic_can',**GC_PACKET,'technology_parameters':{'generic_can':{'values':GC_PACKET.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in GC_PACKET.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['generic_can']['values']['payload_bytes']=9
    bad['technology_parameters']['generic_can']['provenance']['payload_bytes']['value']=9
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_fsoe_requires_own_black_channel_and_does_not_inherit_ethercat_rate_or_payload_ceiling():
    fields={f['key']:f for f in registry.parameter_fields('fsoe')}
    profile=registry.profile('fsoe')
    assert profile['domain']=='generic_networking' and profile['default_stack']==['fsoe']
    assert registry.parameter_defaults_review('fsoe')['values']=={}
    assert profile['max_payload_bytes'] is None and 'max' not in fields['payload_bytes']
    assert not {'bitrate','mtu_bytes','duplex','vlan_id','queue_size','qos_priority','retry_limit'} & fields.keys()
    for key in ('payload_bytes','fsoe_conn_id','fsoe_slave_address','fsoe_sequence','fsoe_parameters_accepted',
                'fsoe_master_watchdog_ms','fsoe_slave_watchdog_ms','fsoe_safety_requirement'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('fsoe',FS_PACKET)['status']=='VALID'
    assert registry.validate_parameters('fsoe',{**FS_ACTUAL,'bitrate_bps':100000000})['status']=='INVALID'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    variant={**FS_ACTUAL,'fsoe_profile':'ENHANCEMENTS_5120','fsoe_frame_bytes':1}
    result=registry.validate_parameters('fsoe',variant)
    assert result['status']=='UNVERIFIED'
    assert any(f['code']=='TECHNOLOGY_PARAMETER_SCOPE_UNVERIFIED' for f in result['findings'])
    assert registry.validate_parameters('fsoe',{**variant,'fsoe_frame_bytes':'wrong'})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('fsoe'),ids=lambda field:'fsoe/'+field['key'])
def test_every_fsoe_parameter_is_typed_and_scoped_to_its_reviewed_base_format(field):
    value=(field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else
           'actual-reference' if field['type']=='text' else field.get('min',0))
    parameters={**FS_ACTUAL,field['key']:value}
    assert registry.validate_parameters('fsoe',parameters)['status']=='VALID'
    assert registry.validate_parameters('fsoe',{**parameters,field['key']:'wrong' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('fsoe',{**parameters,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('fsoe',{**parameters,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'payload_bytes':3},{'fsoe_master_safe_bytes':3},{'fsoe_slave_safe_bytes':3},
    {'fsoe_crc_count':2},{'fsoe_frame_bytes':9},{'fsoe_pdo_capacity_bytes':6},
    {'fsoe_direction':'SLAVE_TO_MASTER'},{'fsoe_conn_id':0},{'fsoe_peer_address':43},
    {'fsoe_sequence':0},{'fsoe_parameters_accepted':False},{'fsoe_command':8},
    {'fsoe_exchange_bound_ms':100},{'fsoe_exchange_bound_ms':101},{'fsoe_slave_watchdog_ms':101},
    {'fsoe_master_watchdog_ms':0},{'fsoe_master_watchdog_ms':100.5},{'fsoe_master_watchdog_ms':65536},
    {'fsoe_state':'RESET'},{'fsoe_state':'SESSION'},
    {'fsoe_parameter_bytes':100,'fsoe_parameter_remaining_bytes':101},
])
def test_fsoe_container_direction_connection_and_watchdog_checks_do_not_use_foreign_bus_rules(change):
    assert registry.validate_parameters('fsoe',{**FS_PACKET,**change})['status']=='INVALID'


def test_fsoe_one_byte_exception_is_six_wire_bytes_and_watchdog_is_unknown_until_declared():
    one={**FS_PACKET,'payload_bytes':1,'fsoe_master_safe_bytes':1,'fsoe_frame_bytes':6,'fsoe_pdo_capacity_bytes':6}
    assert registry.validate_parameters('fsoe',one)['status']=='VALID'
    assert registry.validate_parameters('fsoe',{**one,'fsoe_frame_bytes':7})['status']=='INVALID'
    slave={**FS_PACKET,'fsoe_direction':'SLAVE_TO_MASTER','payload_bytes':4,'fsoe_crc_count':2,
           'fsoe_frame_bytes':11,'fsoe_pdo_capacity_bytes':11}
    assert registry.validate_parameters('fsoe',slave)['status']=='VALID'
    assert registry.validate_parameters('fsoe',{**slave,'fsoe_data_command':'FAILSAFE_DATA','fsoe_command':8})['status']=='VALID'
    # Device mapping, not a universal Ethernet datagram ceiling, limits safe data.
    large={**FS_PACKET,'payload_bytes':2000,'fsoe_master_safe_bytes':2000,'fsoe_crc_count':1000,
           'fsoe_frame_bytes':4003,'fsoe_pdo_capacity_bytes':4003}
    assert registry.validate_parameters('fsoe',large)['status']=='VALID'
    # Scalar declaration does not prove this actual transport can map that container.
    assert registry.profile('fsoe')['capacity_evidence']['status']=='MODEL_MISSING'
    incomplete=FS_PACKET.copy()
    incomplete.pop('fsoe_slave_watchdog_ms')
    assert registry.validate_parameters('fsoe',incomplete)['status']=='UNVERIFIED'
    reset={**FS_ACTUAL,'fsoe_state':'RESET','fsoe_conn_id':0,'fsoe_crc0':0,'fsoe_command':42}
    assert registry.validate_parameters('fsoe',reset)['status']=='VALID'


def test_fsoe_confirmed_directional_mapping_and_watchdogs_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'fsoe',**FS_PACKET,'technology_parameters':{'fsoe':{'values':FS_PACKET.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in FS_PACKET.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['fsoe']['values']['fsoe_slave_watchdog_ms']=99
    bad['technology_parameters']['fsoe']['provenance']['fsoe_slave_watchdog_ms']['value']=99
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_foundation_h1_is_fixed_native_rate_and_separates_actual_telegram_from_baseline():
    profile=registry.profile('foundation_fieldbus_h1')
    fields={f['key']:f for f in registry.parameter_fields('foundation_fieldbus_h1')}
    assert profile['domain']=='generic_networking' and profile['default_stack']==['foundation_fieldbus_h1']
    assert registry.parameter_defaults_review('foundation_fieldbus_h1')['values']=={'bitrate_bps':31250}
    assert not {'qos_priority','sync_method','gateway_maximum_throughput','queue_size','retry_limit'} & fields.keys()
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    for key in ('payload_bytes','ff_node_address','ff_las_active','ff_macrocycle_us','ff_terminal_v','ff_is_required'):
        assert 'default' not in fields[key]
    assert fields['ff_fms_pci_bytes']['conditional_defaults']==[
        {'when':{'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':'DT'},'value':4}]
    assert registry.validate_parameters('foundation_fieldbus_h1',FF_PACKET)['status']=='VALID'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**FF_ACTUAL,'bitrate_bps':100000000})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('foundation_fieldbus_h1'),ids=lambda field:'foundation_h1/'+field['key'])
def test_every_foundation_h1_parameter_is_typed_and_uses_its_own_declared_bounds(field):
    preferred={'bitrate':31250,'ff_terminal_v':9,'ff_terminators':2}
    value=preferred.get(field['key'],field.get('options',[None])[0] if field.get('options') else
        False if field['type']=='boolean' else 'actual-reference' if field['type']=='text' else field.get('min',0))
    parameters={**FF_ACTUAL,field['key']:value}
    assert registry.validate_parameters('foundation_fieldbus_h1',parameters)['status']=='VALID'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**parameters,field['key']:'wrong' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('foundation_fieldbus_h1',{**parameters,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('foundation_fieldbus_h1',{**parameters,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'payload_bytes':60},{'ff_dl_pci_bytes':4},{'ff_fcs_bytes':4},{'ff_ph_sdu_bytes':72},
    {'ff_wire_octets':75},{'ff_buffering':'QUEUED'},{'ff_access':'UNSCHEDULED_PT'},
    {'ff_las_active':True},{'ff_node_address':31},{'ff_fun':246,'ff_nun':2},
    {'ff_node_address':248},{'ff_address_state':'CLEARED'},{'ff_address_state':'TEMPORARY'},
    {'ff_macrocycle_us':999999},{'ff_publish_offset_us':1000000},{'ff_exchange_bound_us':400001},
    {'ff_token_hold_us':1},{'ff_segment_total_m':1899},{'ff_cable_type':'TYPE_B'},
    {'ff_terminators':1},{'ff_terminal_v':8.99},{'ff_terminal_v':32.01},{'ff_devices_ma':101},
    {'ff_pdu':'CD'},
])
def test_foundation_h1_rejects_foreign_layout_role_address_schedule_or_power(change):
    assert registry.validate_parameters('foundation_fieldbus_h1',{**FF_PACKET,**change})['status']=='INVALID'


def test_foundation_h1_priority_uses_dl_sdu_not_encoded_data_and_pt_is_unscheduled():
    maximum={**FF_PACKET,'payload_bytes':251,'ff_dl_sdu_bytes':256,'ff_dl_pci_bytes':15,
             'ff_ph_sdu_bytes':273,'ff_wire_octets':276,'ff_priority':'TIME_AVAILABLE'}
    assert registry.validate_parameters('foundation_fieldbus_h1',maximum)['status']=='VALID'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**maximum,'ff_priority':'NORMAL'})['status']=='INVALID'
    queued={**FF_ACTUAL,'ff_vcr':'CLIENT_SERVER','ff_access':'UNSCHEDULED_PT','ff_buffering':'QUEUED',
            'ff_token_hold_us':100,'ff_unscheduled_us':100}
    assert registry.validate_parameters('foundation_fieldbus_h1',queued)['status']=='VALID'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**queued,'ff_token_hold_us':101})['status']=='INVALID'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**FF_ACTUAL,'ff_is_required':True})['status']=='UNVERIFIED'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**FF_ACTUAL,'ff_is_required':True,'ff_is_source':' '})['status']=='UNVERIFIED'
    assert registry.validate_parameters('foundation_fieldbus_h1',{**FF_ACTUAL,'ff_is_required':True,'ff_is_source':'matched-certificate'})['status']=='VALID'
    # Declared certificate reference is not itself an intrinsic-safety acceptance.
    assert registry.profile('foundation_fieldbus_h1')['capacity_evidence']['status']=='MODEL_MISSING'


def test_foundation_h1_confirmed_las_and_power_data_survive_rejected_sql_edits():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    parameters={'technology':'foundation_fieldbus_h1',**FF_PACKET,
        'technology_parameters':{'foundation_fieldbus_h1':{'values':FF_PACKET.copy(),
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in FF_PACKET.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['foundation_fieldbus_h1']['values']['ff_devices_ma']=101
    bad['technology_parameters']['foundation_fieldbus_h1']['provenance']['ff_devices_ma']['value']=101
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_flexray_baseline_is_standard_rate_not_peak_or_nxp_extension():
    fields={f['key']:f for f in registry.parameter_fields('flexray')}
    profile=registry.profile('flexray')
    assert profile['domain']=='generic_networking'
    assert registry.parameter_defaults_review('flexray')['values']=={'bitrate_bps':2500000}
    assert fields['payload_bytes']['multiple_of']==2 and 'default' not in fields['payload_bytes']
    assert not {'qos_priority','retry_limit','sync_method','gateway_maximum_throughput'} & fields.keys()
    for key in ('fr_frame_id','fr_cycle_us','fr_static_slots','fr_coldstart_node','fr_poc_state','fr_key_slot_id'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('flexray',FR_PACKET)['status']=='VALID'
    assert registry.validate_parameters('flexray',{**FR_ACTUAL,'bitrate_bps':8000000})['status']=='INVALID'
    nxp={**FR_ACTUAL,'fr_profile':'NXP_MFR4310_2_1','bitrate_bps':8000000,'fr_microtick_ns':25,'fr_samples_per_microtick':2}
    assert registry.validate_parameters('flexray',nxp)['status']=='VALID'
    assert registry.validate_parameters('flexray',{**nxp,'fr_microtick_ns':12.5})['status']=='INVALID'
    assert registry.validate_parameters('flexray',{**nxp,'fr_macro_per_cycle':8})['status']=='INVALID'
    for change in ({'fr_static_slot_mt':3},{'fr_static_slot_mt':700},{'fr_two_key_mode':True}):
        result=registry.validate_parameters('flexray',{**nxp,**change})
        assert result['status']=='UNVERIFIED'
        assert any(f['code']=='TECHNOLOGY_PARAMETER_SCOPE_UNVERIFIED' for f in result['findings'])
    assert registry.validate_parameters('flexray',{**nxp,'fr_static_slot_mt':'wrong-type'})['status']=='INVALID'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('flexray'),ids=lambda field:'flexray/'+field['key'])
def test_every_flexray_parameter_has_its_own_scalar_type_and_limits(field):
    preferred={'bitrate':2500000}
    value=preferred.get(field['key'],field.get('allowed_values',[None])[0] if field.get('allowed_values') else
        field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else
        'actual-controller-reference' if field['type']=='text' else field.get('min',0))
    values={**FR_ACTUAL,field['key']:value}
    assert registry.validate_parameters('flexray',values)['status']=='VALID'
    assert registry.validate_parameters('flexray',{**values,field['key']:'bad-number' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('flexray',{**values,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('flexray',{**values,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'bitrate_bps':500000},{'payload_bytes':7},{'fr_payload_words':3},{'fr_static_payload_words':5},
    {'fr_frame_bytes':24},{'fr_frame_id':3},{'fr_cycle_us':1001},{'fr_cycle_mt':999},
    {'fr_micro_per_cycle':19999},{'fr_action_point_mt':63,'fr_static_slot_mt':63},
    {'fr_minislot_action_point_mt':20},{'fr_symbol_action_point_mt':1},
    {'fr_correction_start_mt':599},{'fr_correction_start_mt':1000},
    {'fr_clock_fatal_pairs':3,'fr_clock_passive_pairs':4},{'fr_cycle_count_max':62},
    {'fr_cycle_counter':64},{'fr_cycle_offset':4},{'fr_repetition':3},
    {'fr_startup_frame':True,'fr_sync_frame':False},{'fr_startup_frame':True,'fr_coldstart_node':False},
    {'fr_payload_valid':False,'fr_preamble':True},{'fr_key_startup':True,'fr_key_sync':False},
    {'fr_key_startup':True,'fr_key_slot_id':0},{'fr_two_key_mode':True,'fr_second_key_id':1,'fr_key_slot_id':1},
    {'fr_channels':'A','fr_tx_channels':'AB'},{'fr_channels':'B','fr_wakeup_channel':'A'},
    {'fr_preamble':True,'fr_nmv_bytes':9},{'fr_message_id':22},{'fr_latest_tx':21},
])
def test_flexray_checks_matching_segment_clocks_channels_cycle_and_startup(change):
    assert registry.validate_parameters('flexray',{**FR_PACKET,**change})['status']=='INVALID'


def test_flexray_dynamic_payload_is_bounded_by_local_not_static_length():
    dynamic={**FR_PACKET,'fr_segment':'DYNAMIC','fr_frame_id':3,'fr_dynamic_payload_words_max':8,
             'fr_payload_words':8,'payload_bytes':16,'fr_frame_bytes':24,'fr_sync_frame':False,'fr_startup_frame':False}
    assert registry.validate_parameters('flexray',dynamic)['status']=='VALID'
    for change in ({'fr_dynamic_payload_words_max':7},{'fr_frame_id':2},{'fr_sync_frame':True},
                   {'fr_startup_frame':True},{'fr_preamble':True,'payload_bytes':0,'fr_payload_words':0,'fr_frame_bytes':8}):
        assert registry.validate_parameters('flexray',{**dynamic,**change})['status']=='INVALID'


def test_flexray_confirmed_slot_and_cluster_config_survive_invalid_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values=FR_PACKET.copy()
    parameters={'technology':'flexray',**values,'technology_parameters':{'flexray':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['flexray']['values']['fr_macro_per_cycle']=999
    bad['technology_parameters']['flexray']['provenance']['fr_macro_per_cycle']['value']=999
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_ethernet_ip_has_no_own_link_rate_or_forced_udp_for_explicit_messages():
    profile=registry.profile('ethernet_ip')
    fields={f['key']:f for f in registry.parameter_fields('ethernet_ip')}
    assert profile['domain']=='generic_networking' and profile['default_stack']==['ethernet_ip']
    assert profile['rate_model']['fields']==[] and not profile['deterministic']
    assert registry.parameter_defaults_review('ethernet_ip')['values']=={}
    assert not {'bitrate','vlan_id','mtu_bytes','duplex','retransmission_enabled','retry_limit'} & fields.keys()
    assert fields['payload_bytes']['max']==65535 and 'default' not in fields['payload_bytes']
    assert fields['eip_o_to_t_rpi_us']['conditional_defaults']==[
        {'when':{'eip_baseline_profile':'ODVA_INTEROP_V9','eip_class':1},'value':100000},
        {'when':{'eip_baseline_profile':'ODVA_INTEROP_V9','eip_class':3},'value':250000}]
    for key in ('eip_class','eip_run_idle_present','eip_established','eip_o_to_t_api_us','eip_session'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('ethernet_ip',EIP_ACTUAL)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**EIP_ACTUAL,'bitrate_bps':500000})['status']=='INVALID'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'


@pytest.mark.parametrize('field',registry.parameter_fields('ethernet_ip'),ids=lambda field:'ethernet_ip/'+field['key'])
def test_every_ethernet_ip_field_has_independent_type_bounds_and_applicability(field):
    preferred={'eip_transport':'UDP','eip_command':111,'eip_ip_address':'192.0.2.1','eip_address_bytes':8}
    value=preferred.get(field['key'],field.get('allowed_values',[None])[0] if field.get('allowed_values') else
        field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else
        'actual-device-reference' if field['type']=='text' else field.get('min',0))
    values={**EIP_ACTUAL,field['key']:value}
    if field['key'] in {'eip_encap_version','eip_encap_options','eip_encap_length','eip_encap_status','eip_session'}:
        values.update(eip_mode='CONNECTED_EXPLICIT',eip_transport='TCP')
    if field['key']=='eip_command': values.update(eip_mode='UNCONNECTED_EXPLICIT',eip_transport='TCP')
    assert registry.validate_parameters('ethernet_ip',values)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**values,field['key']:'bad-number' if field['type']=='number' else 1})['status']=='INVALID'
    for bound,offset in (('min',-1),('max',1)):
        if field.get(bound) is not None:
            assert registry.validate_parameters('ethernet_ip',{**values,field['key']:field[bound]+offset})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('ethernet_ip',{**values,field['key']:value+0.5})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'eip_transport':'TCP'},{'eip_class':3},{'eip_class':2},{'eip_command':112},
    {'eip_encap_length':34},{'eip_address_bytes':4},{'eip_class_sequence_bytes':0},
    {'eip_run_idle_bytes':0},{'eip_cpf_bytes':33},{'eip_packet_bytes':58},
    {'eip_o_to_t_size':17},{'eip_forward_open':'STANDARD','eip_t_to_o_size':512},
    {'eip_timeout_code':8},{'eip_class_sequence':65536},{'eip_io_sequence':4294967296},
    {'eip_delivery':'MULTICAST','eip_port':3333}, {'payload_bytes':True},
    {'eip_size_mode':'VARIABLE','eip_o_to_t_size':15},
])
def test_ethernet_ip_rejects_foreign_transport_packet_sizes_and_connections(change):
    assert registry.validate_parameters('ethernet_ip',EIP_PACKET)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**EIP_PACKET,**change})['status']=='INVALID'


def test_ethernet_ip_counts_encapsulation_only_for_explicit_tcp_and_preserves_large_io():
    explicit={**EIP_ACTUAL,'eip_mode':'CONNECTED_EXPLICIT','eip_transport':'TCP','eip_class':3,'eip_command':112,
              'eip_application_bytes':10,'eip_class_sequence_bytes':2,'payload_bytes':12,'eip_address_bytes':4,
              'eip_cpf_layout':'TWO_ITEM','eip_cpf_bytes':26,'eip_encap_length':32,'eip_packet_bytes':56}
    assert registry.validate_parameters('ethernet_ip',explicit)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**explicit,'eip_transport':'UDP'})['status']=='INVALID'
    assert registry.validate_parameters('ethernet_ip',{**explicit,'eip_packet_bytes':26})['status']=='INVALID'
    large={**EIP_PACKET,'eip_forward_open':'LARGE','eip_o_to_t_size':512,'eip_application_bytes':506,
           'payload_bytes':512,'eip_cpf_bytes':530,'eip_packet_bytes':530}
    assert registry.validate_parameters('ethernet_ip',large)['status']=='VALID'
    # Two independent sequence spaces; Class0 omits only the class sequence.
    zero={**EIP_PACKET,'eip_class':0,'eip_class_sequence_bytes':0,'eip_application_bytes':12,'eip_io_sequence':123}
    assert registry.validate_parameters('ethernet_ip',zero)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**zero,'eip_class_sequence':123})['status']=='INVALID'


def test_ethernet_ip_watchdog_uses_accepted_directional_interval_and_declared_resolution():
    actual={**EIP_ACTUAL,'eip_o_to_t_rpi_us':100000,'eip_o_to_t_api_us':125000,'eip_t_to_o_api_us':50000,
            'eip_timeout_code':0,'eip_watchdog_profile':'ACCEPTED_API','eip_watchdog_us':500000}
    assert registry.validate_parameters('ethernet_ip',actual)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**actual,'eip_watchdog_us':400000})['status']=='INVALID'
    opener={**actual,'eip_watchdog_profile':'OPENER_MILLISECOND','eip_o_to_t_rpi_us':1500,
            'eip_watchdog_us':4000,'eip_initial_watchdog_us':10000000}
    assert registry.validate_parameters('ethernet_ip',opener)['status']=='VALID'
    assert registry.validate_parameters('ethernet_ip',{**opener,'eip_watchdog_us':6000})['status']=='INVALID'
    assert registry.validate_parameters('ethernet_ip',{**opener,'eip_initial_watchdog_us':4000})['status']=='INVALID'
    assert registry.validate_parameters('ethernet_ip',{**actual,'eip_timeout_code':7,'eip_watchdog_us':64000000})['status']=='VALID'


def test_ethernet_ip_confirmed_connection_sizes_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**EIP_PACKET,'eip_established':True}
    parameters={'technology':'ethernet_ip',**values,'technology_parameters':{'ethernet_ip':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['ethernet_ip']['values']['eip_o_to_t_size']=10
    bad['technology_parameters']['ethernet_ip']['provenance']['eip_o_to_t_size']['value']=10
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters

ETB_ACTUAL={'bitrate_bps':100000000,'etb_phy':'100BASE_TX','etb_edition':'IEC_2014',
            'etb_node_role':'ETBN','etb_configuration_source':'actual-switch-config-and-edition',
            'etb_physical_binding':'actual-backbone-ports-cabling-and-bypass'}

ECAT_ACTUAL={'bitrate_bps':100000000,'ecat_transport':'NATIVE_ETHERNET','ecat_phy':'100BASE_TX',
             'ecat_esi_source':'actual-ESI-SII-ESC-and-device-config','ecat_topology_source':'actual-ordered-loop-ports-cables'}


ETH_ACTUAL={'bitrate_bps':10000000,'eth_phy':'10BASE_T','duplex':'FULL','mtu_bytes':1500,
            'eth_frame_profile':'BASIC_MAC','eth_payload_layer':'MAC_CLIENT','eth_upper_header_bytes':0,
            'eth_vlan_tags':0,'eth_ifg_bits':96,'eth_link_up':True,
            'eth_pause_rx':False,'eth_pause_tx':False,'eth_eee_enabled':False}


def test_ethernet_timing_and_load_adapters_require_explicit_frame_layout():
    from backend.engineering.capacity.calculators import estimate_frame
    adapter=registry.resolve_stack('ethernet')['timing_model']
    load=registry.resolve_stack('ethernet')['load_calculator']
    with pytest.raises(ValueError,match='Frame-Modell'):
        adapter.transmission_time_us(8,10000000)
    frame=estimate_frame('ETHERNET',8,{**ETH_ACTUAL,'bitrate':10000000})
    actual=adapter.transmission_time_us(8,10000000,technology_parameters=ETH_ACTUAL)
    assert actual==pytest.approx(frame.transmission_time_s*1000000)
    assert load.calculate(payload_bytes=8,cycle_ms=10,bitrate=10000000,technology_parameters=ETH_ACTUAL)['load_percent']==pytest.approx(actual/100)
    with pytest.raises(ValueError,match='another technology'):
        adapter.transmission_time_us(8,10000000,technology_parameters={**ETH_ACTUAL,'technology':'can'})
    with pytest.raises(ValueError,match='conflicts'):
        adapter.transmission_time_us(8,10000000,technology_parameters={**ETH_ACTUAL,'bitrate_bps':100000000})
    with pytest.raises(ValueError):
        adapter.transmission_time_us(8,10000000,technology_parameters={**ETH_ACTUAL,'eth_vlan_tags':True})


def test_generic_ethernet_uses_reviewed_ieee_schema_and_preserves_unknown_peer_state():
    fields={f['key']:f for f in registry.parameter_fields('generic_ethernet')}
    plain=lambda f:{k:v for k,v in f.items() if k!='default_review'}
    assert {k:plain(v) for k,v in fields.items()}=={f['key']:plain(f) for f in registry.parameter_fields('ethernet')}
    assert fields['bitrate']['default_review']['technology']=='generic_ethernet'
    profile=registry.profile('generic_ethernet')
    assert profile['domain']=='generic_networking' and profile['default_stack']==['generic_ethernet']
    assert registry.parameter_defaults_review('generic_ethernet')['values']=={'bitrate_bps':10000000}
    for key in ('duplex','payload_bytes','eth_link_up','eth_pause_rx','eth_pause_tx','eth_eee_enabled','eth_source_mac'):
        assert 'default' not in fields[key]
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('generic_ethernet',{**ETH_ACTUAL,'can_identifier':1})['status']=='INVALID'


@pytest.mark.parametrize('tags,data,pad,mac',[(0,0,46,64),(1,0,42,64),(2,0,38,64),(0,1500,0,1518),(2,1500,0,1526)])
def test_generic_ethernet_checks_its_mac_client_tags_and_padding_without_tcp_assumptions(tags,data,pad,mac):
    values={**ETH_ACTUAL,'eth_vlan_tags':tags,'eth_client_bytes':data,'payload_bytes':data,
            'eth_pad_bytes':pad,'eth_mac_frame_bytes':mac}
    assert registry.validate_parameters('generic_ethernet',values)['status']=='VALID'
    assert registry.validate_parameters('generic_ethernet',{**values,'eth_mac_frame_bytes':mac+1})['status']=='INVALID'
    assert registry.validate_parameters('generic_ethernet',{**values,'eth_pad_bytes':pad+1})['status']=='INVALID'


@pytest.mark.parametrize('change',[
    {'bitrate_bps':1000000000},{'eth_tag_mode':'UNTAGGED','vlan_id':1},{'eth_tag_mode':'UNTAGGED','qos_priority':3},
    {'mtu_bytes':9000},{'eth_peer_duplex':'HALF'},{'eth_peer_rate_bps':100000000},
    {'eth_pause_rx':True,'duplex':'HALF'},{'eth_eee_enabled':False,'eth_eee_wake_us':1},
    {'eth_plca_enabled':True},{'eth_payload_layer':'MAC_CLIENT','eth_upper_header_bytes':54},
])
def test_generic_ethernet_phy_scope_and_actual_features_are_not_foreign_defaults(change):
    assert registry.validate_parameters('generic_ethernet',{**ETH_ACTUAL,**change})['status']=='INVALID'


def test_generic_ethernet_confirmed_gigabit_and_jumbo_parameters_survive_rejected_sql_change():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**ETH_ACTUAL,'bitrate_bps':1000000000,'eth_phy':'1000BASE_T','eth_frame_profile':'JUMBO_DEVICE',
            'mtu_bytes':9000,'eth_device_source':'matched-jumbo-endpoints','eth_topology_source':'actual-jumbo-path','eth_peer_rate_bps':1000000000}
    assert registry.validate_parameters('generic_ethernet',values)['status']=='VALID'
    parameters={'technology':'generic_ethernet',**values,'technology_parameters':{'generic_ethernet':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['generic_ethernet']['values']['eth_peer_rate_bps']=100000000
    bad['technology_parameters']['generic_ethernet']['provenance']['eth_peer_rate_bps']['value']=100000000
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'): service.save_parameters(bad)
    assert service.get()['parameters']==parameters


@pytest.mark.parametrize('technology',['ethernet','generic_ethernet'])
@pytest.mark.parametrize('key',['eth_padding_bytes','eth_mtu_source','eth_phy_typo'])
def test_ethernet_native_typo_fields_are_rejected_instead_of_ignored(technology,key):
    result=registry.validate_parameters(technology,{**ETH_ACTUAL,key:1})
    assert result['status']=='INVALID'
    assert any(f['code']=='TECHNOLOGY_PARAMETER_NOT_APPLICABLE' and f['parameter']==key for f in result['findings'])


def test_ethernet_baseline_separates_mac_client_from_tcp_can_and_link_confirmation():
    fields={f['key']:f for f in registry.parameter_fields('ethernet')}
    assert registry.parameter_defaults_review('ethernet')['values']=={'bitrate_bps':10000000}
    assert fields['eth_phy']['default']=='10BASE_T'
    for key in ('duplex','payload_bytes','vlan_id','eth_pause_rx','eth_link_up','eth_eee_enabled','eth_source_mac'):
        assert 'default' not in fields[key]
    assert fields['mtu_bytes']['conditional_defaults']==[{'when':{'eth_frame_profile':'BASIC_MAC'},'value':1500}]
    assert fields['eth_plca_to_bits']['conditional_defaults']==[{'when':{'eth_phy':'10BASE_T1S','eth_plca_enabled':True},'value':32}]
    assert not {'retry_limit','sync_method','reserved_bandwidth_percent','gateway_maximum_routes'} & fields.keys()
    assert registry.profile('ethernet')['medium_access_model']=='VARIANT_DEPENDENT'
    assert 'ARP' not in registry.mechanisms('ethernet').get('address_resolution',[])
    assert registry.validate_parameters('ethernet',{**ETH_ACTUAL,'can_identifier':3})['status']=='INVALID'


@pytest.mark.parametrize('tags,data,pad,mac',[(0,0,46,64),(1,0,42,64),(2,0,38,64),
                                           (0,1500,0,1518),(1,1500,0,1522),(2,1500,0,1526)])
def test_ethernet_mac_boundaries_do_not_invent_tcp_headers(tags,data,pad,mac):
    from backend.engineering.capacity.calculators import estimate_frame
    values={**ETH_ACTUAL,'eth_vlan_tags':tags,'eth_client_bytes':data,'payload_bytes':data,
            'eth_pad_bytes':pad,'eth_mac_frame_bytes':mac,'eth_wire_slot_bytes':mac+20}
    assert registry.validate_parameters('ethernet',values)['status']=='VALID'
    frame=estimate_frame('ETHERNET',data,registry.normalize_parameters('ethernet',values)|{'bitrate':10000000})
    assert frame.frame_bits==(mac+20)*8 and frame.transmission_time_available
    assert frame.transmission_time_s==pytest.approx((mac+20)*8/10000000)
    assert registry.validate_parameters('ethernet',{**values,'eth_wire_slot_bytes':mac+21})['status']=='INVALID'


def test_ethernet_missing_layout_half_duplex_and_explicit_upper_headers_have_distinct_results():
    from backend.engineering.capacity.calculators import estimate_frame
    assert not estimate_frame('ETHERNET',100,{'bitrate':10000000}).transmission_time_available
    half=estimate_frame('ETHERNET',100,{**ETH_ACTUAL,'bitrate':10000000,'duplex':'HALF'})
    assert not half.transmission_time_available and half.calculation_model=='ETHERNET_ACCESS_UNVERIFIED'
    udp=estimate_frame('ETHERNET',1472,{**ETH_ACTUAL,'bitrate':10000000,'eth_payload_layer':'UPPER_LAYER','eth_upper_header_bytes':28})
    assert udp.frame_bits==1538*8
    with pytest.raises(ValueError,match='MTU'):
        estimate_frame('ETHERNET',1473,{**ETH_ACTUAL,'bitrate':10000000,'eth_payload_layer':'UPPER_LAYER','eth_upper_header_bytes':28})
    jumbo=estimate_frame('ETHERNET',9000,{**ETH_ACTUAL,'bitrate':10000000,'eth_frame_profile':'JUMBO_DEVICE','mtu_bytes':9000})
    assert jumbo.frame_bits==9038*8
    for key,value in (('eth_vlan_tags',True),('eth_vlan_tags',3),('eth_ifg_bits',95),('eth_upper_header_bytes',0.5),('eth_payload_layer','CAN')):
        assert not estimate_frame('ETHERNET',100,{**ETH_ACTUAL,'bitrate':10000000,key:value}).transmission_time_available


@pytest.mark.parametrize('patch',[
    {'eth_phy':'100BASE_TX','bitrate_bps':10000000}, {'eth_phy':'1000BASE_T','bitrate_bps':100000000},
    {'eth_phy':'5GBASE_T','bitrate_bps':5000000000,'duplex':'HALF'},
    {'eth_phy':'100BASE_T1','bitrate_bps':100000000,'duplex':'HALF'},
    {'eth_phy':'10BASE_T1S','duplex':'FULL'}, {'eth_peer_rate_bps':100000000}, {'eth_peer_duplex':'HALF'},
    {'eth_tag_mode':'UNTAGGED','vlan_id':0}, {'eth_tag_mode':'UNTAGGED','qos_priority':0},
    {'eth_tag_mode':'PRIORITY','vlan_id':1}, {'eth_tag_mode':'VLAN','vlan_id':0},
    {'vlan_id':4095},{'qos_priority':1.5},{'eth_frame_format':'ETHERTYPE','eth_type_length':1501},
    {'eth_frame_format':'LENGTH_LLC','eth_type_length':100,'eth_client_bytes':99},
    {'duplex':'HALF','eth_pause_rx':True}, {'duplex':'FULL','eth_backpressure':True},
    {'duplex':'HALF','eth_collision_slot_bits':4096}, {'duplex':'FULL','eth_attempt_limit':16},
    {'eth_pause_rx':True,'eth_pause_quanta':100,'eth_pause_time_us':1},
    {'eth_pause_rx':False,'eth_pause_tx':False,'eth_pause_quanta':0},
    {'eth_eee_enabled':False,'eth_eee_wake_us':0}, {'rate_limit_bit_s':10000001},
    {'eth_source_mac':'FF:FF:FF:FF:FF:FF'}, {'eth_source_mac':'00:00:00:00:00:00'},
    {'eth_destination_mac':'00:00:00:00:00:00'}, {'eth_source_mac':'02:gg:00:00:00:01'},
    {'payload_bytes':1501}, {'mtu_bytes':1501}, {'eth_phy':'10BASE_T','eth_plca_enabled':True},
    {'eth_phy':'10BASE_T1S','duplex':'HALF','eth_plca_id':255,'eth_plca_active':True},
    {'eth_phy':'10BASE_T1S','duplex':'HALF','eth_plca_enabled':False,'eth_plca_to_bits':32},
])
def test_ethernet_foreign_modes_and_inconsistent_actual_declarations_fail(patch):
    assert registry.validate_parameters('ethernet',{**ETH_ACTUAL,**patch})['status']=='INVALID'


def test_ethernet_pause_conversion_and_plca_disabled_identifier_are_not_guesses():
    pause={**ETH_ACTUAL,'eth_pause_rx':True,'eth_pause_quanta':100,'eth_pause_time_us':5120}
    assert registry.validate_parameters('ethernet',pause)['status']=='VALID'
    assert registry.validate_parameters('ethernet',{**pause,'bitrate_bps':100000000,'eth_phy':'100BASE_TX',
        'eth_pause_time_us':512})['status']=='VALID'
    assert registry.validate_parameters('ethernet',{**ETH_ACTUAL,'eth_phy':'10BASE_T1S','duplex':'HALF',
        'eth_plca_enabled':True,'eth_plca_id':255,'eth_plca_active':False})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('ethernet'),ids=lambda f:'ethernet/'+f['key'])
def test_every_ethernet_parameter_uses_own_types_ranges_and_quantum(field):
    _assert_ethernet_scalar_bounds('ethernet',field)


@pytest.mark.parametrize('field',registry.parameter_fields('generic_ethernet'),ids=lambda f:'generic_ethernet/'+f['key'])
def test_every_generic_ethernet_parameter_uses_its_actual_schema_types_ranges_and_quantum(field):
    _assert_ethernet_scalar_bounds('generic_ethernet',field)


def _assert_ethernet_scalar_bounds(technology,field,context=None,value_overrides=None):
    key=field['key']
    options=field.get('options',[])
    value=field.get('default',options[0] if options else False if field['type']=='boolean' else
                    'actual-ethernet-source' if field['type']=='text' else field.get('min',0))
    value=(value_overrides or {}).get(key,value)
    values={'bitrate_bps':10000000,**(context or {}),key:value}
    if key=='bitrate': values.pop('bitrate_bps')
    if key=='eth_source_mac': values[key]=value='02:00:00:00:00:01'
    if key=='eth_destination_mac': values[key]=value='FF:FF:FF:FF:FF:FF'
    if key=='eth_peer_rate_bps': values[key]=value=10000000
    assert registry.validate_parameters(technology,values)['status']=='VALID'
    assert registry.validate_parameters(technology,{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters(technology,{**values,key:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters(technology,{**values,key:value+0.5})['status']=='INVALID'


def test_ethernet_confirmed_tag_and_link_settings_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**ETH_ACTUAL,'eth_tag_mode':'VLAN','eth_vlan_tags':1,'vlan_id':19,'qos_priority':6,
            'eth_device_source':'actual-phy-mac-revision','eth_topology_source':'actual-port-cable-path'}
    parameters={'technology':'ethernet',**values,'technology_parameters':{'ethernet':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['ethernet']['values']['eth_peer_duplex']='HALF'
    bad['technology_parameters']['ethernet']['provenance']['eth_peer_duplex']={'source':'USER_CONFIRMED','status':'CONFIRMED','value':'HALF'}
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_ethercat_has_classic_source_qualified_baseline_not_can_queues_or_dc_defaults():
    fields={x['key']:x for x in registry.parameter_fields('ethercat')}
    assert registry.parameter_defaults_review('ethercat')['values']=={'bitrate_bps':100000000}
    assert fields['duplex']['options']==['FULL'] and fields['mtu_bytes']['default']==1500
    assert registry.profile('ethercat')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('ethercat',{})['status']=='UNVERIFIED'
    assert registry.validate_parameters('ethercat',ECAT_ACTUAL)['status']=='VALID'
    for key in ('ecat_expected_wkc','ecat_received_wkc','ecat_state','ecat_dc_supported','distributed_clock_cycle_ms','ecat_watchdog_divider','vlan_id'):
        assert 'default' not in fields[key]
    for key in ('qos_priority','sync_method','retry_limit','rate_limit_bit_s','gateway_maximum_routes'):
        assert key not in fields
    assert fields['ecat_watchdog_divider']['conditional_defaults']==[{'when':{'ecat_register_profile':'BECKHOFF_3_0'},'value':2498}]
    assert fields['ecat_pd_watchdog_ticks']['conditional_defaults']==[{'when':{'ecat_register_profile':'BECKHOFF_3_0'},'value':1000}]
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,'can_identifier':1})['status']=='INVALID'


@pytest.mark.parametrize('transport,tags,data,pad,mac',[
    ('NATIVE_ETHERNET',0,0,32,64),('NATIVE_ETHERNET',1,0,28,64),
    ('NATIVE_ETHERNET',0,1486,0,1518),('NATIVE_ETHERNET',1,1486,0,1522),
    ('UDP_IPV4',0,0,4,64),('UDP_IPV4',1,0,0,64),
    ('UDP_IPV4',0,1458,0,1518),('UDP_IPV4',1,1458,0,1522),
])
def test_ethercat_single_datagram_boundaries_include_headers_padding_fcs_and_ifg(transport,tags,data,pad,mac):
    values={**ECAT_ACTUAL,'ecat_transport':transport,'ecat_datagram_count':1,'payload_bytes':data,
            'ecat_sum_data_bytes':data,'ecat_datagram_length':data,'ecat_datagram_bytes':data+12,
            'ecat_header_length':data+12,'ecat_vlan_tags':tags,'ecat_padding_bytes':pad,
            'ecat_mac_frame_bytes':mac,'ecat_wire_slot_bytes':mac+20,'ecat_more':False}
    if transport=='UDP_IPV4':
        values.update(ecat_udp_port=34980,ecat_ipv4_header_bytes=20)
    assert registry.validate_parameters('ethercat',values)['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**values,'ecat_mac_frame_bytes':mac+1})['status']=='INVALID'
    assert registry.validate_parameters('ethercat',{**values,'ecat_padding_bytes':pad+1})['status']=='INVALID'


def test_ethercat_multi_datagram_example_uses_actual_sum_not_single_payload():
    values={**ECAT_ACTUAL,'payload_bytes':4,'ecat_datagram_count':4,'ecat_sum_data_bytes':10,
            'ecat_datagram_bytes':58,'ecat_header_length':58,'ecat_padding_bytes':0,
            'ecat_vlan_tags':0,'ecat_mac_frame_bytes':78,'ecat_wire_slot_bytes':98}
    assert registry.validate_parameters('ethercat',values)['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**values,'ecat_sum_data_bytes':4})['status']=='INVALID'
    assert registry.validate_parameters('ethercat',{**values,'ecat_device_datagram_limit':3})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'bitrate_bps':1000000000},{'duplex':'HALF'},{'mtu_bytes':1514},
    {'ecat_frame_type':2},{'ecat_header_reserved':1},{'ecat_datagram_reserved':1},
    {'ecat_datagram_length':10,'payload_bytes':9},
    {'ecat_datagram_count':1,'ecat_more':True},
    {'ecat_transport':'UDP_IPV4','payload_bytes':1459},
    {'ecat_transport':'UDP_IPV4','ecat_datagram_bytes':1471},
    {'ecat_transport':'UDP_IPV4','ecat_udp_port':88},
    {'ecat_udp_port':34980}, {'ecat_ipv4_header_bytes':20},
    {'ecat_sum_data_bytes':3,'payload_bytes':4},
    {'ecat_datagram_count':1,'ecat_sum_data_bytes':5,'payload_bytes':4},
    {'ecat_response_accepted':True,'ecat_expected_wkc':3,'ecat_received_wkc':2},
    {'ecat_sync_mode':'FREE_RUN','distributed_clock_cycle_ms':1},
    {'ecat_sync_mode':'SM_EVENT','distributed_clock_cycle_ms':1},
    {'ecat_sync_mode':'DC','ecat_dc_supported':False},
    {'ecat_dc_supported':False,'ecat_sync0_cycle_ns':1000000},
    {'ecat_sync_generation':'CYCLIC_PULSE','ecat_sync0_cycle_ns':0},
    {'ecat_sync_generation':'SINGLE_SHOT','ecat_sync0_cycle_ns':1},
    {'ecat_sync_generation':'SINGLE_SHOT','ecat_sync_pulse_ns':0},
    {'ecat_sync_generation':'CYCLIC_ACK','ecat_sync_pulse_ns':10},
    {'ecat_sync_generation':'CYCLIC_ACK','ecat_sync0_cycle_ns':0},
    {'ecat_sync_generation':'SINGLE_SHOT_ACK','ecat_sync0_cycle_ns':1},
    {'ecat_sync_mode':'DC','ecat_sync0_cycle_ns':1000000,'distributed_clock_cycle_ms':2},
    {'ecat_sync_pulse_ns':5},{'ecat_sync_pulse_ns':10,'ecat_sync_pulse_register':2},
    {'ecat_watchdog_divider':2498,'ecat_pd_watchdog_ticks':1000,'ecat_pd_watchdog_min_ns':99999999},
    {'ecat_watchdog_divider':2498,'ecat_pd_watchdog_ticks':1000,'ecat_pd_watchdog_max_ns':100000000},
    {'ecat_pd_watchdog_ticks':0,'ecat_pd_watchdog_max_ns':0},
    {'ecat_state':'SAFEOP','ecat_outputs_active':True},
    {'ecat_state':'INIT','ecat_outputs_active':True},
    {'ecat_command':'LRW','ecat_addressing':'CONFIGURED'},
    {'ecat_command':'FPRD','ecat_addressing':'LOGICAL'},
    {'ecat_addressing':'LOGICAL','ecat_register_offset':4096},
    {'ecat_addressing':'BROADCAST','ecat_logical_address':1},
    {'ecat_mailbox_bytes':64,'ecat_mailbox_data_bytes':59},
    {'ecat_link_detection':'STANDARD','ecat_link_loss_bound_us':15},
    {'ecat_phy':'EBUS','ecat_wire_slot_bytes':84},
])
def test_ethercat_parameter_dependencies_reject_wrong_sizes_states_addressing_and_timers(patch):
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,**patch})['status']=='INVALID'


def test_ethercat_working_counter_and_watchdog_do_not_certify_full_functional_timing():
    values={**ECAT_ACTUAL,'ecat_response_accepted':True,'ecat_expected_wkc':3,'ecat_received_wkc':3,
            'ecat_sync_mode':'DC','ecat_dc_supported':True,'ecat_sync0_cycle_ns':1000000,
            'distributed_clock_cycle_ms':1,'ecat_sync_generation':'CYCLIC_PULSE','ecat_sync_pulse_ns':100,
            'ecat_sync_pulse_register':10,'ecat_watchdog_divider':2498,'ecat_pd_watchdog_ticks':1000,
            'ecat_pd_watchdog_min_ns':100000000,'ecat_pd_watchdog_max_ns':100100000}
    result=registry.validate_parameters('ethercat',values)
    assert result['status']=='VALID' and result['required_parameter_completeness']=='UNVERIFIED'
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,'ecat_response_accepted':False,
        'ecat_received_wkc':2,'ecat_expected_wkc':3})['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,'ecat_sync_mode':'DC','ecat_dc_supported':True,
        'ecat_sync_generation':'SINGLE_SHOT_ACK','ecat_sync0_cycle_ns':0,'ecat_sync_pulse_ns':0,
        'distributed_clock_cycle_ms':0})['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,'ecat_link_detection':'STANDARD','ecat_link_loss_bound_us':14.5})['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**ECAT_ACTUAL,'ecat_phy':'EBUS','ecat_link_detection':'STANDARD','ecat_link_loss_bound_us':20})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('ethercat'),ids=lambda f:'ethercat/'+f['key'])
def test_every_ethercat_parameter_checks_own_types_bounds_and_encapsulation(field):
    key=field['key']
    options=field.get('options',[])
    value=field.get('default',options[0] if options else False if field['type']=='boolean' else
                    'actual-ethercat-evidence' if field['type']=='text' else field.get('min',0))
    values={**ECAT_ACTUAL,key:value}
    if key in {'ecat_udp_port','ecat_ipv4_header_bytes'}:
        values['ecat_transport']='UDP_IPV4'
        if key=='ecat_udp_port':
            values[key]=value=34980
    if key=='bitrate':
        values.pop('bitrate_bps')
    assert registry.validate_parameters('ethercat',values)['status']=='VALID'
    assert registry.validate_parameters('ethercat',{**values,key:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('ethercat',{**values,key:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('ethercat',{**values,key:value+0.5})['status']=='INVALID'


def test_ethercat_confirmed_dc_configuration_survives_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**ECAT_ACTUAL,'ecat_sync_mode':'DC','ecat_dc_supported':True,'distributed_clock_cycle_ms':1,
            'ecat_sync0_cycle_ns':1000000,'ecat_expected_wkc':3,'ecat_received_wkc':3,'ecat_response_accepted':True}
    parameters={'technology':'ethercat',**values,'technology_parameters':{'ethercat':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['ethercat']['values']['ecat_dc_supported']=False
    bad['technology_parameters']['ethercat']['provenance']['ecat_dc_supported']['value']=False
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_etb_baseline_has_own_phy_topology_and_no_automatic_capacity_certificate():
    fields={x['key']:x for x in registry.parameter_fields('etb')}
    assert registry.parameter_defaults_review('etb')['values']=={'bitrate_bps':100000000}
    assert registry.profile('etb')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('etb',{})['status']=='UNVERIFIED'
    assert registry.validate_parameters('etb',ETB_ACTUAL)['status']=='VALID'
    assert fields['etb_phy']['default']=='100BASE_TX'
    for key in ('etb_inauguration','etb_inhibition','etb_traffic_enabled','etb_local_id','etb_hello_timeout_ms','etb_consist_uuid','vlan_id'):
        assert 'default' not in fields[key]
    assert fields['mtu_bytes']['conditional_defaults']==[{'when':{'etb_frame_profile':'BASIC_MAC'},'value':1500}]
    assert all(key not in fields for key in ('qos_priority','sync_method','retry_limit','gateway_maximum_routes'))
    assert registry.validate_parameters('etb',{**ETB_ACTUAL,'can_identifier':1})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'bitrate_bps':10000000}, {'duplex':'HALF'},
    {'etb_phy':'1000BASE_T'},
    {'etb_frame_profile':'BASIC_MAC','payload_bytes':1501},
    {'etb_frame_profile':'BASIC_MAC','mtu_bytes':1501},
    {'mtu_bytes':1000,'payload_bytes':1001},
    {'rate_limit_bit_s':100000001},
    {'etb_implementation':'WEOS_5','etb_local_id':33},
    {'etb_implementation':'WEOS_5','etb_ecn_id':5},
    {'etb_implementation':'WEOS_5','etb_backbone_id':2},
    {'etb_implementation':'WEOS_5','etb_dir1_ports':3},
    {'etb_implementation':'WEOS_5','etb_dir2_ports':3},
    {'etb_implementation':'WEOS_5','etb_igmp_snooping':True},
    {'etb_implementation':'WEOS_5','etb_topology_vlan':493},
    {'etb_aggregation':'TTDP_ACTIVE_STANDBY','etb_active_links_per_direction':2},
    {'etb_dir1_ports':1,'etb_active_links_per_direction':2},
    {'etb_dir2_ports':0,'etb_active_links_per_direction':1},
    {'etb_inauguration':'PENDING','etb_traffic_enabled':True},
    {'etb_inauguration':'FAILED','etb_traffic_enabled':True},
    {'etb_traffic_scope':'INTER_CONSIST','etb_traffic_enabled':True,'etb_topology_counter':'0x12','etb_message_topology_counter':'0x13'},
    {'etb_hello_period_ms':100,'etb_hello_timeout_ms':99},
    {'etb_clock_role':'MASTER'}, {'etb_peer_clock_role':'MASTER'},
    {'etb_consist_uuid':'00000000-0000-0000-0000-000000000000'},
    {'etb_consist_uuid':'wrong'}, {'etb_etbn_mac':'00:11:22'}, {'etb_ip_address':'999.1.1.1'},
])
def test_etb_actual_phy_topology_payload_and_implementation_dependencies(patch):
    assert registry.validate_parameters('etb',{**ETB_ACTUAL,**patch})['status']=='INVALID'


def test_etb_gbit_clock_roles_redundancy_and_inhibition_are_distinct():
    values={**ETB_ACTUAL,'etb_phy':'1000BASE_T','bitrate_bps':1000000000,
            'etb_clock_role':'MASTER','etb_peer_clock_role':'FOLLOWER'}
    assert registry.validate_parameters('etb',values)['status']=='VALID'
    assert registry.validate_parameters('etb',{**values,'etb_peer_clock_role':'MASTER'})['status']=='INVALID'
    # Inhibition can keep an already inaugurated topology stable; it does not
    # mean all existing application traffic was stopped.
    operational={**ETB_ACTUAL,'etb_inauguration':'INAUGURATED','etb_inhibition':True,'etb_traffic_enabled':True,
                 'etb_traffic_scope':'INTER_CONSIST','etb_topology_counter':'0x12','etb_message_topology_counter':'0x12',
                 'etb_aggregation':'TTDP_ACTIVE_STANDBY','etb_dir1_ports':2,'etb_dir2_ports':2,'etb_active_links_per_direction':1}
    assert registry.validate_parameters('etb',operational)['status']=='VALID'
    assert registry.validate_parameters('etb',{**operational,'etb_inauguration':'PENDING','etb_traffic_enabled':False,
                                               'etb_active_links_per_direction':0})['status']=='VALID'
    assert registry.validate_parameters('etb',{**operational,'etb_traffic_scope':'INTRA_CONSIST','etb_message_topology_counter':'0'})['status']=='VALID'
    assert registry.validate_parameters('etb',{**ETB_ACTUAL,'etb_implementation':'DEVICE_SPECIFIC','etb_local_id':33})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('etb'),ids=lambda f:'etb/'+f['key'])
def test_every_etb_parameter_checks_own_type_bounds_and_phy_conditions(field):
    options=field.get('options',[])
    key=field['key']
    preferred={'bitrate':100000000,'etb_consist_uuid':'11111111-1111-1111-1111-111111111111',
               'etb_etbn_mac':'02:11:22:33:44:55','etb_ip_address':'192.0.2.10'}
    value=preferred.get(key,field.get('default',options[0] if options else False if field['type']=='boolean' else
                        'actual-etb-evidence' if field['type']=='text' else field.get('min',0)))
    values={**ETB_ACTUAL,key:value}
    if key in {'etb_clock_role','etb_peer_clock_role'}:
        values.update(etb_phy='1000BASE_T',bitrate_bps=1000000000)
    if key=='bitrate':
        values.pop('bitrate_bps')
    assert registry.validate_parameters('etb',values)['status']=='VALID'
    bad='invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('etb',{**values,key:bad})['status']=='INVALID'
    for bound in ('min','max'):
        if bound in field:
            assert registry.validate_parameters('etb',{**values,key:field[bound]+(-1 if bound=='min' else 1)})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('etb',{**values,key:value+0.5})['status']=='INVALID'


def test_etb_confirmed_gbit_topology_parameters_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**ETB_ACTUAL,'etb_phy':'1000BASE_T','bitrate_bps':1000000000,
            'etb_local_id':2,'etb_implementation':'WEOS_5','etb_topology_vlan':492}
    parameters={'technology':'etb',**values,'technology_parameters':{'etb':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['etb']['values']['bitrate_bps']=100000000
    bad['technology_parameters']['etb']['provenance']['bitrate_bps']['value']=100000000
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_doip_has_its_own_length_header_and_explicit_transport_not_ethernet_parameters():
    fields={item['key']:item for item in registry.parameter_fields('doip')}
    profile=registry.profile('doip')
    assert profile['default_stack']==['doip'] and profile['default_bitrate'] is None
    assert profile['max_payload_bytes']==4294967295
    assert registry.parameter_defaults_review('doip')['values']=={}
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('doip',{})['status']=='UNVERIFIED'
    assert 'default' not in fields['payload_bytes']
    assert 'default' not in fields['doip_routing_active']
    for patch in ({'bitrate':10000000},{'can_identifier':1},{'mtu_bytes':1500},
                  {'qos_priority':3},{'retry_limit':3},{'sync_method':'PTP'},{'queue_policy':'CBS'}):
        assert registry.validate_parameters('doip',{**DOIP_ACTUAL,**patch})['status']=='INVALID'
    result=registry.validate_parameters('doip',{**DOIP_ACTUAL,'doip_payload_type':32769,
        'payload_bytes':8196,'doip_user_data_bytes':8192,'doip_message_bytes':8204,'doip_routing_active':True})
    assert result['status']=='VALID' and result['required_parameter_completeness']=='UNVERIFIED'


@pytest.mark.parametrize('kind,size,transport',[(0,1,'TCP'),(1,0,'UDP'),(2,6,'UDP'),(3,17,'UDP'),
    (7,0,'TCP'),(8,2,'TCP'),(16385,0,'UDP'),(16387,0,'UDP'),(16388,1,'UDP')])
def test_doip_control_layout_lengths_and_transports_are_not_diagnostic_payload(kind,size,transport):
    values={**DOIP_ACTUAL,'doip_transport':transport,'doip_payload_type':kind,'payload_bytes':size,'doip_message_bytes':8+size}
    assert registry.validate_parameters('doip',values)['status']=='VALID'
    assert registry.validate_parameters('doip',{**values,'payload_bytes':size+1})['status']=='INVALID'
    if kind:
        assert registry.validate_parameters('doip',{**values,'doip_transport':'TCP' if transport=='UDP' else 'UDP'})['status']=='INVALID'


@pytest.mark.parametrize('kind,base,extra,transport',[(4,32,1,'UDP'),(5,7,4,'TCP'),(6,9,4,'TCP'),(16386,3,4,'UDP')])
@pytest.mark.parametrize('present',[False,True])
def test_doip_optional_layout_fields_have_message_specific_sizes(kind,base,extra,transport,present):
    size=base+extra if present else base
    values={**DOIP_ACTUAL,'doip_transport':transport,'doip_payload_type':kind,
            'doip_optional_field_present':present,'payload_bytes':size}
    assert registry.validate_parameters('doip',values)['status']=='VALID'
    assert registry.validate_parameters('doip',{**values,'payload_bytes':size+1})['status']=='INVALID'


@pytest.mark.parametrize('patch',[
    {'doip_protocol_version':3,'doip_inverse_version':253},
    {'doip_edition':'ISO_2012','doip_protocol_version':3},
    {'doip_protocol_version':255,'doip_payload_type':1},
    {'doip_protocol_version':255,'doip_transport':'UDP','doip_payload_type':4},
    {'doip_edition':'ISO_2012','doip_transport':'TLS'},
    {'doip_payload_type':32769,'doip_transport':'UDP'},
    {'doip_payload_type':32769,'payload_bytes':4},
    {'doip_payload_type':32769,'payload_bytes':6,'doip_user_data_bytes':1},
    {'doip_payload_type':32769,'doip_routing_active':False},
    {'doip_payload_type':32770,'doip_ack_code':1},
    {'doip_payload_type':32770,'payload_bytes':7,'doip_ack_copy_bytes':1},
    {'doip_message_bytes':16,'payload_bytes':7},
    {'doip_max_sockets':2,'doip_open_sockets':3},
    {'doip_peer_size_definition':'DOIP_PAYLOAD','doip_peer_size_limit_bytes':100,'payload_bytes':101},
    {'doip_peer_size_definition':'DIAGNOSTIC_USER_DATA','doip_peer_size_limit_bytes':100,'doip_user_data_bytes':101},
    {'doip_peer_size_definition':'COMPLETE_DOIP_MESSAGE','doip_peer_size_limit_bytes':108,'doip_message_bytes':109},
    {'doip_source_role':'CLIENT','doip_source_address':3583},
    {'doip_source_role':'CLIENT','doip_source_address':4096},
    {'doip_transport':'UDP','doip_initial_inactivity_ms':2000},
    {'doip_announce_interval_ms':500},
    {'doip_reserved':1},
    {'doip_payload_type':1,'doip_transport':'UDP','doip_user_data_bytes':1},
    {'doip_payload_type':5,'doip_optional_field_present':False,'doip_oem_data':0},
    {'doip_ip_address':'999.1.1.1'},{'doip_eid_hex':'123'},{'doip_vin_hex':'non-hex-string'},
])
def test_doip_known_version_connection_payload_peer_and_address_dependencies(patch):
    assert registry.validate_parameters('doip',{**DOIP_ACTUAL,**patch})['status']=='INVALID'


def test_doip_standard_proposals_depend_on_selected_edition_and_transport():
    fields={item['key']:item for item in registry.parameter_fields('doip')}
    assert fields['doip_port']['conditional_defaults']==[{'when':{'doip_transport':t},'value':p}
        for t,p in (('UDP',13400),('TCP',13400),('TLS',3496))]
    assert all(p['when']['doip_transport'] in {'TCP','TLS'} and p['value']==300000
               for p in fields['doip_general_inactivity_ms']['conditional_defaults'])
    assert fields['doip_announce_count']['conditional_defaults']==[
        {'when':{'doip_edition':'ISO_2019','doip_transport':'UDP'},'value':3}]
    for key in ('doip_general_inactivity_ms','doip_announce_count','doip_protocol_version','doip_inverse_version'):
        assert 'default' not in fields[key]
    assert registry.validate_parameters('doip',{**DOIP_ACTUAL,'doip_transport':'UDP',
        'doip_protocol_version':255,'doip_inverse_version':0,'doip_payload_type':1,'payload_bytes':0})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('doip'),ids=lambda field:'doip/'+field['key'])
def test_every_doip_field_has_separate_type_range_and_transport_applicability(field):
    options=field.get('options',[])
    preferred={'doip_protocol_version':3,'doip_ip_address':'2001:db8::1',
               'doip_vin_hex':'00'*17,'doip_eid_hex':'00'*6,'doip_gid_hex':'00'*6}
    value=preferred.get(field['key'],field.get('default',options[0] if options else False if field['type']=='boolean' else
                    'actual-doip-evidence' if field['type']=='text' else field.get('min',0)))
    values={**DOIP_ACTUAL,field['key']:value}
    if field['key'].startswith('doip_announce_'):
        values['doip_transport']='UDP'
    assert registry.validate_parameters('doip',values)['status']=='VALID'
    assert registry.validate_parameters('doip',{**values,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('doip',{**values,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('doip',{**values,field['key']:value+0.5})['status']=='INVALID'


def test_doip_confirmed_peer_limits_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**DOIP_ACTUAL,'doip_peer_size_definition':'DOIP_PAYLOAD','doip_peer_size_limit_bytes':8196,
            'doip_payload_type':32769,'doip_user_data_bytes':8192,'payload_bytes':8196,'doip_routing_active':True}
    parameters={'technology':'doip',**values,'technology_parameters':{'doip':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['doip']['values']['doip_peer_size_limit_bytes']=4096
    bad['technology_parameters']['doip']['provenance']['doip_peer_size_limit_bytes']['value']=4096
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_dnp3_has_no_can_rate_fixed_message_size_or_energy_industry_assumption():
    fields = {item['key']: item for item in registry.parameter_fields('dnp3')}
    profile = registry.profile('dnp3')
    assert profile['default_stack'] == ['dnp3'] and profile['domain'] == 'generic_networking'
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert registry.parameter_defaults_review('dnp3')['values'] == {}
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.validate_parameters('dnp3', {})['status'] == 'UNVERIFIED'
    assert fields['dnp_fragment_limit_bytes']['default'] == 2048
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert registry.validate_parameters('dnp3', {**DNP_ACTUAL, 'payload_bytes': 8192})['status'] == 'VALID'
    for patch in ({'bitrate': 500000}, {'can_identifier': 1}, {'mtu_bytes': 1500},
                  {'retry_limit': 3}, {'sync_method': 'PTP'}, {'qos_priority': 3}, {'queue_policy': 'CBS'}):
        assert registry.validate_parameters('dnp3', {**DNP_ACTUAL, **patch})['status'] == 'INVALID'


@pytest.mark.parametrize('user_bytes,length,wire,transport', [(0,5,10,None),(1,6,13,0),
    (16,21,28,15),(17,22,31,16),(249,254,291,248),(250,255,292,249)])
def test_dnp3_crc_block_and_transport_header_lengths_are_not_message_size(user_bytes,length,wire,transport):
    values = {**DNP_ACTUAL,'dnp_link_user_bytes': user_bytes, 'dnp_link_length_field': length,
              'dnp_link_frame_bytes': wire}
    if transport is not None:
        values['dnp_transport_data_bytes'] = transport
    assert registry.validate_parameters('dnp3', values)['status'] == 'VALID'
    for key in ('dnp_link_length_field','dnp_link_frame_bytes'):
        assert registry.validate_parameters('dnp3', {**values,key:values[key]+1})['status'] == 'INVALID'
    assert registry.validate_parameters('dnp3', {**values,'dnp_transport_data_bytes': 0 if transport is None else transport+1})['status'] == 'INVALID'


@pytest.mark.parametrize('mode,address', [('UNICAST',65519),('SELF',65532),('BROADCAST_NO_CONFIRM',65533),
    ('BROADCAST_CONFIRM',65534),('BROADCAST_OPTIONAL_CONFIRM',65535)])
def test_dnp3_address_modes_keep_reserved_and_individual_ranges_distinct(mode,address):
    values = {**DNP_ACTUAL,'dnp_destination_mode':mode,'dnp_destination_address':address}
    assert registry.validate_parameters('dnp3',values)['status'] == 'VALID'
    assert registry.validate_parameters('dnp3',{**values,'dnp_destination_address':65520 if mode=='UNICAST' else address-1})['status'] == 'INVALID'


@pytest.mark.parametrize('patch', [
    {'dnp_master_address':1,'dnp_outstation_address':1},
    {'dnp_destination_address':65520}, {'dnp_destination_address':65531},
    {'dnp_fragment_limit_bytes':2048,'dnp_peer_rx_buffer_bytes':1024},
    {'dnp_application_fragment_bytes':4096,'dnp_fragment_limit_bytes':2048},
    {'dnp_application_fragment_bytes':4096,'dnp_peer_rx_buffer_bytes':2048},
    {'dnp_application_fragment_bytes':2048,'payload_bytes':2047},
    {'dnp_application_kind':'RESPONSE','dnp_application_fragment_bytes':3},
    {'dnp_application_kind':'UNSOLICITED_RESPONSE','dnp_data_class':'CLASS0'},
    {'dnp_role':'OUTSTATION','dnp_unsolicited_enabled':False,'dnp_application_kind':'UNSOLICITED_RESPONSE'},
    {'dnp_link_confirm':False,'dnp_link_confirm_timeout_ms':1000},
    {'dnp_link_confirm':False,'dnp_link_retries':2},
    {'dnp_keepalive_enabled':False,'dnp_keepalive_ms':60000},
    {'dnp_role':'OUTSTATION','dnp_unsolicited_retry_mode':'UNLIMITED','dnp_max_unsolicited_retries':0},
    {'dnp_transport':'SERIAL','dnp_port':20000},
    {'dnp_transport':'TLS','dnp_security_mode':'NONE'},
    {'dnp_auto_retry_min_ms':1000,'dnp_auto_retry_max_ms':500},
    {'dnp_point_index_start':100,'dnp_point_index_end':99},
    {'dnp_app_confirm_timeout_ms':5000}, {'dnp_role':'OUTSTATION','dnp_response_timeout_ms':5000},
])
def test_dnp3_known_role_fragment_retry_and_security_dependencies(patch):
    assert registry.validate_parameters('dnp3',{**DNP_ACTUAL,**patch})['status']=='INVALID'


def test_dnp3_literature_and_library_defaults_remain_conditional_proposals():
    fields = {item['key']:item for item in registry.parameter_fields('dnp3')}
    assert fields['dnp_fragment_limit_bytes']['default_status']=='PROPOSED'
    assert fields['dnp_port']['conditional_defaults']==[
        {'when':{'dnp_transport':t},'value':20000} for t in ('TCP','UDP','SCTP')]
    for key in ('dnp_app_confirm_timeout_ms','dnp_select_timeout_ms','dnp_unsolicited_retry_delay_ms'):
        assert 'default' not in fields[key]
        assert fields[key]['conditional_defaults']==[
            {'when':{'dnp_implementation':'STEPFUNC_1_6','dnp_role':'OUTSTATION'},'value':5000}]
    assert 'default' not in fields['dnp_link_confirm']
    assert 'conditional_defaults' not in fields['dnp_response_timeout_ms']
    result = registry.validate_parameters('dnp3',{**DNP_ACTUAL,'payload_bytes':8192,
        'dnp_application_fragment_bytes':4096,'dnp_fragment_limit_bytes':4096,'dnp_peer_rx_buffer_bytes':4096})
    assert result['status']=='VALID' and result['required_parameter_completeness']=='UNVERIFIED'


@pytest.mark.parametrize('field',registry.parameter_fields('dnp3'),ids=lambda field:'dnp3/'+field['key'])
def test_every_dnp3_parameter_has_its_own_type_and_bounds(field):
    options=field.get('options',[])
    value=field.get('default',options[0] if options else False if field['type']=='boolean' else
                    'actual-dnp3-evidence' if field['type']=='text' else field.get('min',0))
    values={**DNP_ACTUAL,field['key']:value}
    if field['key'] in DNP_OUTSTATION_FIELDS:
        values['dnp_role']='OUTSTATION'
    if field['key']=='dnp_destination_address':
        values['dnp_destination_mode']='UNICAST'
    assert registry.validate_parameters('dnp3',values)['status']=='VALID'
    assert registry.validate_parameters('dnp3',{**values,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('dnp3',{**values,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('dnp3',{**values,field['key']:value+0.5})['status']=='INVALID'


def test_dnp3_saved_peer_buffer_and_addresses_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={**DNP_ACTUAL,'dnp_master_address':0,'dnp_outstation_address':65519,
            'dnp_peer_rx_buffer_bytes':4096,'dnp_fragment_limit_bytes':4096,'dnp_application_fragment_bytes':2048,'payload_bytes':8192}
    parameters={'technology':'dnp3',**values,'technology_parameters':{'dnp3':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['dnp3']['values']['dnp_peer_rx_buffer_bytes']=1024
    bad['technology_parameters']['dnp3']['provenance']['dnp_peer_rx_buffer_bytes']['value']=1024
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_devicenet_uses_its_can_adaptation_without_canopen_or_ethernet_defaults():
    fields = {item['key']: item for item in registry.parameter_fields('devicenet')}
    assert registry.parameter_defaults_review('devicenet')['values'] == {'bitrate_bps': 125000}
    assert fields['can_frame_format']['options'] == ['BASE_11']
    assert fields['can_frame_type']['options'] == ['DATA']
    assert fields['can_termination_ohms']['default'] == 121
    assert fields['can_stub_length_m']['max'] == 6
    assert registry.profile('devicenet')['max_payload_bytes'] == 8
    assert registry.profile('devicenet')['capacity_evidence']['status'] == 'MODEL_MISSING'
    for key in ('dn_mac_id', 'dn_cable_type', 'dn_supply_voltage_v', 'dn_expected_packet_rate_ms', 'dn_fragmented'):
        assert 'default' not in fields[key]
    for patch in ({'bitrate': 100000}, {'can_frame_format': 'EXTENDED_29'}, {'payload_bytes': 9},
                  {'can_frame_type': 'REMOTE'}, {'mtu_bytes': 1500}, {'co_node_id': 1},
                  {'sync_method': 'PTP'}, {'qos_priority': 3}, {'retry_limit': 3}):
        assert registry.validate_parameters('devicenet', {'bitrate': 125000, **patch})['status'] == 'INVALID', patch


@pytest.mark.parametrize('group,message,mac,identifier', [
    ('GROUP1',15,63,1023), ('GROUP2',7,63,1535), ('GROUP3',6,63,1983), ('GROUP4',47,None,2031)])
def test_devicenet_message_group_identifier_mapping_is_explicit(group,message,mac,identifier):
    values = {'bitrate': 125000, 'dn_identifier_layout': 'CLASSIC_GROUPS_1_4',
              'dn_message_group': group, 'dn_message_id': message, 'can_identifier': identifier}
    if mac is not None:
        values['dn_identifier_mac_id'] = mac
    assert registry.validate_parameters('devicenet', values)['status'] == 'VALID'
    assert registry.validate_parameters('devicenet', {**values, 'can_identifier': identifier - 1})['status'] == 'INVALID'
    assert registry.validate_parameters('devicenet', {**values, 'dn_message_id': message + 1})['status'] == 'INVALID'
    if group == 'GROUP4':
        assert registry.validate_parameters('devicenet', {**values, 'dn_identifier_mac_id': 0})['status'] == 'INVALID'
    assert registry.validate_parameters('devicenet', {'bitrate': 125000,
        'dn_identifier_layout': 'CLASSIC_GROUPS_1_4', 'can_identifier': 2032})['status'] == 'INVALID'


@pytest.mark.parametrize('cable,rate,limit', [(cable, rate, limit)
    for cable, limits in {'THICK': (500,250,100), 'MID': (300,250,100),
                          'THIN': (100,100,100), 'FLAT': (420,200,75)}.items()
    for rate, limit in zip((125000,250000,500000),limits)])
def test_devicenet_selected_cable_and_rate_limit_actual_farthest_path(cable,rate,limit):
    values = {'bitrate': rate, 'dn_cable_type': cable, 'can_bus_length_m': limit}
    assert registry.validate_parameters('devicenet', values)['status'] == 'VALID'
    assert registry.validate_parameters('devicenet', {**values, 'can_bus_length_m': limit + 1})['status'] == 'INVALID'


@pytest.mark.parametrize('rate,limit', [(125000,156),(250000,78),(500000,39)])
def test_devicenet_rate_limits_cumulative_drops_separately_from_single_drop(rate,limit):
    values = {'bitrate': rate, 'dn_cumulative_drop_m': limit, 'can_stub_length_m': 6}
    assert registry.validate_parameters('devicenet', values)['status'] == 'VALID'
    assert registry.validate_parameters('devicenet', {**values, 'dn_cumulative_drop_m': limit + 1})['status'] == 'INVALID'
    assert registry.validate_parameters('devicenet', {**values, 'can_stub_length_m': 7})['status'] == 'INVALID'


@pytest.mark.parametrize('patch', [
    {'dn_inhibit_ms': 101, 'dn_heartbeat_ms': 100},
    {'dn_worst_node_voltage_v': 25, 'dn_supply_voltage_v': 24},
    {'dn_worst_node_voltage_v': 19, 'dn_device_minimum_voltage_v': 20},
    {'dn_supply_voltage_v': 0}, {'dn_device_minimum_voltage_v': 0},
    {'payload_bytes': 8, 'dn_protocol_header_bytes': 2, 'dn_cip_data_bytes': 7},
    {'dn_fragmented': False, 'dn_cip_data_bytes': 7, 'dn_complete_message_bytes': 8},
    {'dn_fragmented': False, 'dn_complete_message_bytes': 9},
    {'dn_fragmented': True, 'dn_cip_data_bytes': 8, 'dn_complete_message_bytes': 7},
    {'dn_complete_message_bytes': 200, 'dn_peer_message_limit_bytes': 100},
    {'dn_duplicate_mac_passed': False, 'dn_connection_state': 'ESTABLISHED'},
    {'dn_cumulative_drop_m': 1, 'can_stub_length_m': 2},
])
def test_devicenet_known_power_connection_and_fragment_dependencies(patch):
    assert registry.validate_parameters('devicenet', {'bitrate': 125000, **patch})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('devicenet'), ids=lambda field: 'devicenet/' + field['key'])
def test_every_devicenet_field_has_its_own_type_and_boundaries(field):
    options = field.get('options', [])
    value = field.get('default', options[0] if options else False if field['type'] == 'boolean' else
                      'actual-devicenet-reference' if field['type'] == 'text' else field.get('min', 0))
    values = {'bitrate': 125000, field['key']: value}
    if field['key'] in {'dn_supply_voltage_v', 'dn_device_minimum_voltage_v'}:
        values[field['key']] = 24
    assert registry.validate_parameters('devicenet', values)['status'] == 'VALID'
    assert registry.validate_parameters('devicenet', {**values, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('devicenet', {**values, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('devicenet', {**values, field['key']: values[field['key']] + 0.5})['status'] == 'INVALID'


def test_devicenet_complete_message_can_exceed_frame_only_with_explicit_fragmentation():
    values = {'bitrate': 250000, 'payload_bytes': 8, 'dn_protocol_header_bytes': 2,
              'dn_cip_data_bytes': 6, 'dn_complete_message_bytes': 200, 'dn_peer_message_limit_bytes': 255,
              'dn_fragmented': True, 'dn_fragmentation_source': 'actual-edition-and-peer-fragment-contract'}
    result = registry.validate_parameters('devicenet', values)
    assert result['status'] == 'VALID' and result['required_parameter_completeness'] == 'UNVERIFIED'


def test_devicenet_saved_power_and_connection_settings_survive_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 125000, 'dn_supply_voltage_v': 24, 'dn_worst_node_voltage_v': 21,
              'dn_device_minimum_voltage_v': 20, 'dn_connection_type': 'CHANGE_OF_STATE',
              'dn_inhibit_ms': 50, 'dn_heartbeat_ms': 250, 'dn_mac_id': 63}
    parameters = {'technology': 'devicenet', **values, 'technology_parameters': {'devicenet': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['devicenet']['values']['dn_worst_node_voltage_v'] = 19
    bad['technology_parameters']['devicenet']['provenance']['dn_worst_node_voltage_v']['value'] = 19
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_dds_has_no_ethernet_rate_udp_size_or_robotics_industry_assumption():
    profile = registry.profile('dds')
    fields = {item['key']: item for item in registry.parameter_fields('dds')}
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['dds']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert registry.parameter_defaults_review('dds')['values'] == {}
    assert registry.validate_parameters('dds', {})['status'] == 'UNVERIFIED'
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    for patch in ({'bitrate': 10000000}, {'mtu_bytes': 1500}, {'can_identifier': 1}, {'qos_priority': 3},
                  {'queue_policy': 'CBS'}, {'retry_limit': 3}, {'sync_method': 'PTP'}):
        assert registry.validate_parameters('dds', {**DDS_ACTUAL, **patch})['status'] == 'INVALID'
    assert registry.validate_parameters('dds', {**DDS_ACTUAL, 'payload_bytes': 1_000_000})['status'] == 'VALID'
    before = profile['parameter_constraints']
    registry.parameter_fields('dds')
    SimulationService().catalog()
    assert registry.profile('dds')['parameter_constraints'] == before
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_dds_standard_defaults_depend_on_entity_and_do_not_map_infinite_to_zero():
    fields = {item['key']: item for item in registry.parameter_fields('dds')}
    assert 'default' not in fields['reliability_mode'] and 'default' not in fields['lifespan_ms']
    reliability = {p['when']['dds_entity']: p['value'] for p in fields['reliability_mode']['conditional_defaults']}
    assert reliability == {'TOPIC': 'BEST_EFFORT', 'DATAWRITER': 'RELIABLE', 'DATAREADER': 'BEST_EFFORT'}
    assert all(p['value'] == 1 and p['when']['history_kind'] == 'KEEP_LAST' for p in fields['history_depth']['conditional_defaults'])
    for key in ('dds_lifespan_kind', 'dds_deadline_kind', 'dds_lease_kind', 'dds_nowriter_purge_kind', 'dds_disposed_purge_kind'):
        assert all(p['value'] == 'INFINITE' for p in fields[key]['conditional_defaults'])
    assert all(p['value'] == -1 for p in fields['dds_max_samples']['conditional_defaults'])
    assert fields['dds_max_blocking_ms']['conditional_defaults'] == [{'when': {'dds_entity': 'DATAWRITER', 'reliability_mode': 'RELIABLE'}, 'value': 100}]


@pytest.mark.parametrize('patch', [
    {'dds_lifespan_kind': 'INFINITE', 'lifespan_ms': 0},
    {'dds_deadline_kind': 'INFINITE', 'dds_deadline_ms': 100},
    {'dds_lease_kind': 'INFINITE', 'dds_lease_ms': 100},
    {'dds_max_samples': 0}, {'dds_max_instances': -2}, {'dds_max_samples_per_instance': 1.5},
    {'dds_max_samples': 2, 'dds_max_samples_per_instance': 3},
    {'dds_max_samples': 2, 'dds_max_samples_per_instance': -1},
    {'history_kind': 'KEEP_LAST', 'history_depth': 3, 'dds_max_samples_per_instance': 2},
    {'dds_service_max_samples': 2, 'dds_service_max_samples_per_instance': 3},
    {'dds_service_history_kind': 'KEEP_LAST', 'dds_service_history_depth': 3, 'dds_service_max_samples_per_instance': 2},
    {'dds_entity': 'DATAREADER', 'dds_deadline_kind': 'FINITE', 'dds_deadline_ms': 10, 'dds_time_based_filter_ms': 11},
    {'dds_entity': 'DATAREADER', 'lifespan_ms': 10},
    {'dds_entity': 'DATAREADER', 'dds_ownership_strength': 1},
    {'dds_entity': 'DATAWRITER', 'dds_nowriter_purge_ms': 0},
    {'dds_entity': 'PUBLISHER', 'history_kind': 'KEEP_LAST'},
    {'dds_entity': 'TOPIC', 'dds_coherent_access': True},
    {'dds_transport_priority': 2147483648}, {'dds_lease_ms': float('inf')},
])
def test_dds_entity_duration_and_resource_limit_dependencies_are_explicit(patch):
    assert registry.validate_parameters('dds', {**DDS_ACTUAL, **patch})['status'] == 'INVALID'


def test_dds_finite_zero_and_unlimited_resource_limits_have_distinct_meanings():
    values = {**DDS_ACTUAL, 'dds_lifespan_kind': 'FINITE', 'lifespan_ms': 0,
              'history_kind': 'KEEP_LAST', 'history_depth': 1,
              'dds_max_samples': -1, 'dds_max_instances': -1, 'dds_max_samples_per_instance': -1,
              'dds_ownership': 'EXCLUSIVE', 'dds_ownership_strength': -1, 'dds_transport_priority': -1,
              'dds_service_cleanup_kind': 'FINITE', 'dds_service_cleanup_ms': 0}
    result = registry.validate_parameters('dds', values)
    assert result['status'] == 'VALID' and result['required_parameter_completeness'] == 'UNVERIFIED'
    assert registry.validate_parameters('dds', {**values, 'history_kind': 'KEEP_ALL', 'history_depth': 4})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('dds'), ids=lambda field: 'dds/' + field['key'])
def test_every_dds_field_checks_entity_type_and_range(field):
    base = dict(DDS_ACTUAL)
    if field['key'] in DDS_POLICY_ENTITIES:
        base['dds_entity'] = DDS_POLICY_ENTITIES[field['key']][0]
    options = field.get('options', [])
    value = field.get('default', options[0] if options else False if field['type'] == 'boolean' else
                      'actual-dds-type-transport-reference' if field['type'] == 'text' else field.get('min', 0))
    assert registry.validate_parameters('dds', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('dds', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('dds', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'
    if field.get('integer'):
        assert registry.validate_parameters('dds', {**base, field['key']: value + 0.5})['status'] == 'INVALID'
    for entity in DDS_POLICY_ENTITIES.get(field['key'], ()):
        assert registry.validate_parameters('dds', {**base, 'dds_entity': entity, field['key']: value})['status'] == 'VALID'


def test_dds_confirmed_reader_qos_survives_rejected_sql_edit():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**DDS_ACTUAL, 'dds_entity': 'DATAREADER', 'reliability_mode': 'BEST_EFFORT',
              'history_kind': 'KEEP_LAST', 'history_depth': 1, 'dds_deadline_kind': 'FINITE',
              'dds_deadline_ms': 100, 'dds_time_based_filter_ms': 50}
    parameters = {'technology': 'dds', **values, 'technology_parameters': {'dds': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['dds']['values']['dds_time_based_filter_ms'] = 101
    bad['technology_parameters']['dds']['provenance']['dds_time_based_filter_ms']['value'] = 101
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_dali_nominal_rate_is_not_tolerance_sampling_rate_or_can_default():
    profile = registry.profile('dali')
    fields = {item['key']: item for item in registry.parameter_fields('dali')}
    assert profile['default_stack'] == ['dali'] and profile['max_payload_bytes'] == 3
    assert registry.parameter_defaults_review('dali')['values'] == {'bitrate_bps': 1200}
    assert fields['bitrate']['min'] == fields['bitrate']['max'] == fields['bitrate']['default'] == 1200
    assert fields['dali_encoding']['default'] == 'MANCHESTER' and fields['dali_bit_order']['default'] == 'MSB_FIRST'
    assert fields['dali_supply_current_limit_ma']['default'] == 250
    assert 'default' not in fields['payload_bytes'] and 'default' not in fields['dali_bus_voltage_v']
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    for patch in ({'bitrate': 1080}, {'bitrate': 1320}, {'bitrate': 2400}, {'bitrate': 500000},
                  {'can_identifier': 3}, {'dali_encoding': 'NRZ'}, {'dali_bit_order': 'LSB_FIRST'},
                  {'sync_method': 'PTP'}, {'queue_policy': 'CBS'}, {'retry_limit': 3}):
        assert registry.validate_parameters('dali', {'bitrate': 1200, **patch})['status'] == 'INVALID', patch


@pytest.mark.parametrize('frame,length,space', [('FORWARD_16', 2, 'CONTROL_GEAR'),
    ('FORWARD_24', 3, 'CONTROL_DEVICE'), ('EVENT_24', 3, 'CONTROL_DEVICE'), ('BACKWARD_8', 1, 'CONTROL_GEAR')])
def test_dali_frame_length_and_address_space_are_separate(frame,length,space):
    base = {'bitrate': 1200, 'dali_revision': 'DALI_2', 'dali_frame': frame,
            'dali_address_space': space, 'payload_bytes': length}
    assert registry.validate_parameters('dali', base)['status'] == 'VALID'
    assert registry.validate_parameters('dali', {**base, 'payload_bytes': length + 1})['status'] == 'INVALID'
    if frame in {'FORWARD_24', 'EVENT_24'}:
        assert registry.validate_parameters('dali', {**base, 'dali_revision': 'VERSION_1'})['status'] == 'INVALID'
        assert registry.validate_parameters('dali', {**base, 'dali_address_space': 'CONTROL_GEAR'})['status'] == 'INVALID'


@pytest.mark.parametrize('patch', [
    {'dali_group_address': 16, 'dali_address_space': 'CONTROL_GEAR'},
    {'dali_scene': 1, 'dali_address_space': 'CONTROL_DEVICE'},
    {'dali_instance': 1, 'dali_address_space': 'CONTROL_GEAR'},
    {'dali_addressing': 'BROADCAST', 'dali_short_address': 1},
    {'dali_addressing': 'GROUP', 'dali_short_address': 1},
    {'dali_master_mode': 'SINGLE_MASTER', 'dali_controller_count': 2},
    {'dali_controller_count': 3, 'dali_control_device_count': 2},
    {'dali_maximum_supply_ma': 200, 'dali_guaranteed_supply_ma': 201},
    {'dali_guaranteed_supply_ma': 100, 'dali_bus_demand_ma': 101},
    {'dali_maximum_supply_ma': 251}, {'dali_gear_count': 65}, {'dali_control_device_count': 65},
    {'dali_reply_min_ms': 10, 'dali_reply_max_ms': 9},
    {'dali_cable_cross_section_mm2': 1.5, 'dali_farthest_distance_m': 301},
    {'dali_total_cable_m': 100, 'dali_farthest_distance_m': 101},
    {'dali_cable_cross_section_mm2': 0}, {'dali_bus_voltage_v': 0}, {'dali_topology': 'CLOSED_LOOP'},
    {'dali_forward_bound_ms': 0}, {'dali_repeat_required': False, 'dali_repeat_window_ms': 100},
])
def test_dali_actual_topology_address_and_current_constraints_reject_crossed_values(patch):
    assert registry.validate_parameters('dali', {'bitrate': 1200, **patch})['status'] == 'INVALID'


def test_dali_typical_voltage_cable_total_and_capacity_are_not_universal_actual_defaults():
    base = {'bitrate': 1200, 'dali_revision': 'DALI_2', 'dali_address_space': 'CONTROL_DEVICE',
            'dali_group_address': 31, 'dali_instance': 31, 'dali_gear_count': 64, 'dali_control_device_count': 64,
            'dali_master_mode': 'MULTI_MASTER', 'dali_controller_count': 2,
            'dali_maximum_supply_ma': 250, 'dali_guaranteed_supply_ma': 200, 'dali_bus_demand_ma': 150,
            'dali_bus_voltage_v': 15, 'dali_topology': 'STAR', 'dali_cable_cross_section_mm2': 1.5,
            'dali_farthest_distance_m': 200, 'dali_total_cable_m': 400}
    result = registry.validate_parameters('dali', base)
    assert result['status'] == 'VALID' and result['required_parameter_completeness'] == 'UNVERIFIED'
    assert registry.profile('dali')['capacity_evidence']['status'] == 'MODEL_MISSING'


@pytest.mark.parametrize('field', registry.parameter_fields('dali'), ids=lambda field: 'dali/' + field['key'])
def test_every_dali_parameter_has_type_and_boundary_checks(field):
    options = field.get('options', [])
    value = field.get('default', options[0] if options else False if field['type'] == 'boolean' else
                      'actual-IEC-edition-device-reference' if field['type'] == 'text' else max(0.1, field.get('min', 0)))
    if field.get('integer'):
        value = int(value)
    base = {'bitrate': 1200}
    assert registry.validate_parameters('dali', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('dali', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('dali', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_dali_confirmed_frame_and_power_survive_failed_sql_edits():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 1200, 'dali_revision': 'DALI_2', 'dali_frame': 'EVENT_24',
              'dali_address_space': 'CONTROL_DEVICE', 'payload_bytes': 3,
              'dali_maximum_supply_ma': 200, 'dali_guaranteed_supply_ma': 150, 'dali_bus_demand_ma': 100}
    parameters = {'technology': 'dali', **values, 'technology_parameters': {'dali': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['dali']['values']['payload_bytes'] = 2
    bad['technology_parameters']['dali']['provenance']['payload_bytes']['value'] = 2
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_dac_direct_analogue_output_has_no_can_frames_bus_load_or_network_queue():
    profile = registry.profile('dac')
    fields = registry.parameter_fields('dac')
    assert profile['default_stack'] == ['dac'] and profile['connection_type'] == 'DIRECT_IO'
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None and profile['overhead_bytes'] == 0
    assert profile['capacity_evidence']['status'] == 'NOT_APPLICABLE'
    assert registry.parameter_defaults_review('dac')['values'] == {}
    assert fields and all(field['parameter_origin'] == 'NIS_SCENARIO' and not field['required'] for field in fields)
    assert not {'bitrate', 'payload_bytes', 'queue_size', 'queue_policy', 'target_bus_load_percent', 'retry_limit', 'qos_priority'} & {field['key'] for field in fields}
    assert registry.validate_parameters('dac', {})['status'] == 'VALID'
    for foreign in ({'bitrate': 500000}, {'payload_bytes': 4}, {'queue_size': 256}, {'can_identifier': 1}):
        assert registry.validate_parameters('dac', foreign)['status'] == 'INVALID'
    local = profile['local_timing_schema']
    assert {item['key'] for item in local} == {'update_bound_ms', 'settling_bound_ms'}
    assert all(item['unit'] == 'ms' and item['default_status'] == 'UNKNOWN' and 'default' not in item and item['source'].startswith('https://') for item in local)


@pytest.mark.parametrize('field', registry.parameter_fields('dac'), ids=lambda field: 'dac/' + field['key'])
def test_every_dac_scenario_field_has_independent_type_and_boundary_checks(field):
    value = field['default']
    assert registry.validate_parameters('dac', {field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('dac', {field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('dac', {field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


@pytest.mark.parametrize('patch', [
    {'source': ''}, {'source': 1}, {'confirmed': 'true'}, {'confirmed': 1},
    {'update_bound_ms': True}, {'update_bound_ms': -1}, {'settling_bound_ms': float('inf')},
    {'settling_bound_ms': None}, {'settling_bound_ms': '0.004'}, {'technology': 'adc'},
])
def test_dac_confirmed_update_and_settling_bounds_require_actual_numeric_and_source_facts(patch):
    base = {'technology': 'dac', 'update_bound_ms': 0.002, 'settling_bound_ms': 0.004,
            'confirmed': True, 'source': 'Selected DAC datasheet; specified code step, tolerance and output load'}
    assert registry.validate_parameters('dac', {'local_timing_evidence': base})['status'] == 'VALID'
    assert registry.validate_parameters('dac', {'local_timing_evidence': {**base, **patch}})['status'] == 'INVALID'
    assert registry.validate_parameters('dac', {'local_timing_evidence': {'confirmed': False}})['status'] == 'VALID'


def test_dac_actual_device_timing_persists_and_failed_edits_leave_it_intact():
    from backend.engineering.repository import create_object, update_object, get_object
    node = create_object('HardwareNode', {'name': 'AnalogueOutputController', 'device_type': 'EmbeddedController'})
    local = {'technology': 'dac', 'update_bound_ms': 0.002, 'settling_bound_ms': 0.004,
             'confirmed': True, 'source': 'Actual DAC datasheet, load/step/tolerance timing table'}
    port = create_object('HardwareNetworkInterface', {'name': 'AnalogueOutput', 'technology': 'DAC',
        'hardware_node_id': str(node['id']), 'capabilities': {'local_timing_evidence': local}})
    assert port['capabilities']['local_timing_evidence'] == local
    for patch, code in (({'settling_bound_ms': -1}, 'LOCAL_TIMING_EVIDENCE_INVALID'),
                        ({'confirmed': 'true'}, 'LOCAL_TIMING_EVIDENCE_INVALID'),
                        ({'source': 1}, 'LOCAL_TIMING_SOURCE_MISSING'),
                        ({'technology': 'CAN'}, 'LOCAL_TIMING_TECHNOLOGY_MISMATCH')):
        with pytest.raises(ValueError, match=code):
            update_object('HardwareNetworkInterface', str(port['id']), {'expected_version': port['version'],
                'capabilities': {'local_timing_evidence': {**local, **patch}}})
        assert get_object('HardwareNetworkInterface', str(port['id']))['capabilities']['local_timing_evidence'] == local


def test_custom_udp_requires_actual_ip_family_and_application_spec_without_ethernet_rate():
    fields = {item['key']: item for item in registry.parameter_fields('custom_udp')}
    profile = registry.profile('custom_udp')
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['custom_udp']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.parameter_defaults_review('custom_udp')['values'] == {}
    assert registry.validate_parameters('custom_udp', {})['status'] == 'UNVERIFIED'
    assert not {'bitrate', 'mtu_bytes', 'vlan_id', 'duplex', 'retry_limit', 'sync_method'} & fields.keys()
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert fields['cudp_udp_header_bytes']['default'] == 8 and fields['cudp_checksum_policy']['default'] == 'ENABLED'
    assert fields['cudp_size_mode']['default'] == 'NORMAL'
    assert fields['cudp_fragmentation_policy']['default'] == 'NO_IP_FRAGMENTATION'
    for patch in ({'bitrate': 10000000}, {'ctcp_stream_service': 'ORDERED_BYTE_STREAM'}, {'cudp_ip_version': 'AUTOMOTIVE'}):
        assert registry.validate_parameters('custom_udp', {**CUSTOM_UDP_ACTUAL, **patch})['status'] == 'INVALID'


@pytest.mark.parametrize('ip_version,header,extension,payload,packet', [
    ('IPV4', 20, None, 65507, 65535), ('IPV4', 60, None, 65467, 65535),
    ('IPV6', None, 0, 65527, 65575), ('IPV6', None, 8, 65519, 65575),
])
def test_custom_udp_normal_limits_account_for_actual_ip_headers(ip_version,header,extension,payload,packet):
    base = {**CUSTOM_UDP_ACTUAL, 'cudp_ip_version': ip_version, 'payload_bytes': payload,
            'cudp_application_header_bytes': 0, 'cudp_application_trailer_bytes': 0, 'cudp_message_bytes': payload,
            'cudp_datagram_bytes': payload + 8, 'cudp_udp_length_field': payload + 8, 'cudp_ip_packet_bytes': packet}
    if header is not None:
        base['cudp_ipv4_header_bytes'] = header
    else:
        base['cudp_ipv6_extension_bytes'] = extension
        base['cudp_ipv6_payload_length'] = 65535
    assert registry.validate_parameters('custom_udp', base)['status'] == 'VALID'
    assert registry.validate_parameters('custom_udp', {**base, 'payload_bytes': payload + 1})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**base, 'cudp_message_bytes': payload + 1})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**base, 'cudp_udp_length_field': 0})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**base, 'cudp_fragmentation_policy': 'NO_IP_FRAGMENTATION', 'cudp_path_mtu_bytes': 1500})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**base, 'cudp_fragmentation_policy': 'EXPLICIT_IP_FRAGMENTATION', 'cudp_path_mtu_bytes': 1500})['status'] == 'VALID'


def test_custom_udp_jumbo_length_zero_is_conditional_on_actual_udp_datagram_length():
    base = {**CUSTOM_UDP_ACTUAL, 'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'JUMBO', 'payload_bytes': 70000,
            'cudp_application_header_bytes': 0, 'cudp_application_trailer_bytes': 0, 'cudp_message_bytes': 70000,
            'cudp_datagram_bytes': 70008, 'cudp_ipv6_extension_bytes': 8, 'cudp_jumbo_payload_length': 70016,
            'cudp_ipv6_payload_length': 0, 'cudp_udp_length_field': 0, 'cudp_ip_packet_bytes': 70056,
            'cudp_fragmentation_policy': 'NO_IP_FRAGMENTATION', 'cudp_path_mtu_bytes': 80000}
    assert registry.validate_parameters('custom_udp', base)['status'] == 'VALID'
    for patch in ({'cudp_ip_version': 'IPV4'}, {'cudp_size_mode': 'NORMAL'}, {'cudp_udp_length_field': 8},
                  {'cudp_ipv6_payload_length': 100}, {'cudp_jumbo_payload_length': 70015},
                  {'cudp_fragmentation_policy': 'EXPLICIT_IP_FRAGMENTATION'}, {'cudp_jumbo_supported': False},
                  {'cudp_path_mtu_bytes': 70055}, {'cudp_ipv6_extension_bytes': 0}):
        assert registry.validate_parameters('custom_udp', {**base, **patch})['status'] == 'INVALID', patch
    # IP Jumbo payload may exceed65535 due to extension headers while UDP itself
    # remains small. Only UDP datagrams >65535 use UDP Length0 (RFC2675 section4).
    small_udp = {**CUSTOM_UDP_ACTUAL, 'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'JUMBO', 'cudp_message_bytes': 0,
                 'cudp_datagram_bytes': 8, 'cudp_ipv6_extension_bytes': 65528, 'cudp_jumbo_payload_length': 65536,
                 'cudp_ipv6_payload_length': 0, 'cudp_udp_length_field': 8}
    assert registry.validate_parameters('custom_udp', small_udp)['status'] == 'VALID'
    assert registry.validate_parameters('custom_udp', {**small_udp, 'cudp_udp_length_field': 0})['status'] == 'INVALID'


def test_custom_udp_checksum_and_application_ack_are_not_tcp_or_can_retries():
    base = {**CUSTOM_UDP_ACTUAL, 'cudp_checksum_policy': 'ENABLED', 'cudp_udp_checksum_value': 65535,
            'cudp_application_ack': True, 'cudp_ack_timeout_ms': 10, 'cudp_ack_retry_limit': 2}
    assert registry.validate_parameters('custom_udp', base)['status'] == 'VALID'
    for patch in ({'cudp_udp_checksum_value': 0}, {'cudp_application_ack': False}, {'cudp_ack_timeout_ms': 0}):
        assert registry.validate_parameters('custom_udp', {**base, **patch})['status'] == 'INVALID'
    disabled = {**CUSTOM_UDP_ACTUAL, 'cudp_checksum_policy': 'IPV4_DISABLED', 'cudp_udp_checksum_value': 0}
    assert registry.validate_parameters('custom_udp', disabled)['status'] == 'VALID'
    assert registry.validate_parameters('custom_udp', {**disabled, 'cudp_ip_version': 'IPV6'})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**CUSTOM_UDP_ACTUAL, 'cudp_ipv4_header_bytes': 21})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**CUSTOM_UDP_ACTUAL, 'payload_bytes': 65508})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_udp', {**CUSTOM_UDP_ACTUAL, 'payload_bytes': 100, 'cudp_full_body_bytes': 1000000})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('custom_udp'), ids=lambda field: 'custom_udp/' + field['key'])
def test_every_custom_udp_parameter_has_independent_type_and_boundary_checks(field):
    base = dict(CUSTOM_UDP_ACTUAL)
    if field['key'] in {'cudp_ipv6_extension_bytes', 'cudp_ipv6_payload_length', 'cudp_jumbo_payload_length'}:
        base.update(cudp_ip_version='IPV6')
    if field['key'] in {'cudp_ipv6_payload_length', 'cudp_jumbo_payload_length'}:
        base.update(cudp_size_mode='JUMBO')
    options = field.get('options', [])
    preferred = {'cudp_udp_length_field': 8, 'cudp_ack_timeout_ms': 0.1}
    value = preferred.get(field['key'], field.get('default', options[0] if options else False if field['type'] == 'boolean' else 'actual-udp-reference' if field['type'] == 'text' else field.get('min', 0)))
    assert registry.validate_parameters('custom_udp', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('custom_udp', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('custom_udp', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_custom_udp_actual_ipv6_jumbo_fields_and_large_body_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**CUSTOM_UDP_ACTUAL, 'cudp_ip_version': 'IPV6', 'cudp_size_mode': 'JUMBO', 'payload_bytes': 70000,
              'cudp_message_bytes': 70000, 'cudp_datagram_bytes': 70008, 'cudp_ipv6_extension_bytes': 8,
              'cudp_jumbo_payload_length': 70016, 'cudp_ipv6_payload_length': 0, 'cudp_udp_length_field': 0,
              'cudp_full_body_bytes': 1000000}
    parameters = {'technology': 'custom_udp', **values, 'technology_parameters': {'custom_udp': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['custom_udp']['values']['cudp_size_mode'] = 'NORMAL'
    bad['technology_parameters']['custom_udp']['provenance']['cudp_size_mode']['value'] = 'NORMAL'
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_custom_text_requires_actual_charset_and_framing_without_false_length_default():
    fields = {item['key']: item for item in registry.parameter_fields('custom_text')}
    profile = registry.profile('custom_text')
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['custom_text']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert registry.parameter_defaults_review('custom_text')['values'] == {}
    assert registry.validate_parameters('custom_text', {})['status'] == 'UNVERIFIED'
    assert not {'bitrate', 'mtu_bytes', 'qos_priority', 'sync_method', 'retry_limit'} & fields.keys()
    for field in fields.values():
        if field['parameter_origin'] != 'NIS_SCENARIO':
            assert 'default' not in field and field['default_status'] == 'UNKNOWN'
    assert 'max' not in fields['payload_bytes']
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'payload_bytes': 1048576})['status'] == 'VALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctcp_stream_service': 'ORDERED_BYTE_STREAM'})['status'] == 'INVALID'


@pytest.mark.parametrize('encoding,text,octets,scalars,units', [
    ('UTF8', 'A\u00e4\U0001f600', 7, 3, None), ('ASCII', 'ABC', 3, 3, None),
    ('UTF16LE', 'A\U0001f600', 6, 2, 3), ('UTF16BE', 'A\U0001f600', 6, 2, 3),
    ('UTF8', '', 0, 0, None), ('UTF8', 'e\u0301', 3, 2, None),
])
def test_custom_text_counts_actual_encoded_octets_scalars_and_utf16_units(encoding,text,octets,scalars,units):
    base = {**CUSTOM_TEXT_ACTUAL, 'ctxt_encoding': encoding, 'ctxt_text_value': text,
            'ctxt_code_points': scalars, 'payload_bytes': octets}
    if units is not None:
        base['ctxt_utf16_code_units'] = units
    assert registry.validate_parameters('custom_text', base)['status'] == 'VALID'
    assert registry.validate_parameters('custom_text', {**base, 'payload_bytes': octets + 1})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**base, 'ctxt_code_points': scalars + 1})['status'] == 'INVALID'
    if units is not None:
        assert registry.validate_parameters('custom_text', {**base, 'ctxt_utf16_code_units': units + 1})['status'] == 'INVALID'


def test_custom_text_rejects_surrogates_wrong_ascii_and_impossible_payload_counts():
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_encoding': 'UTF16LE', 'payload_bytes': 3})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_encoding': 'UTF16BE', 'ctxt_code_points': 2, 'payload_bytes': 10})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_text_value': '\ud800'})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_encoding': 'ASCII', 'ctxt_text_value': '\u00e4'})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_code_points': 2, 'payload_bytes': 9})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_code_points': 2, 'payload_bytes': 1})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**CUSTOM_TEXT_ACTUAL, 'ctxt_delimiter_hex': '0A0'})['status'] == 'INVALID'
    framing = {**CUSTOM_TEXT_ACTUAL, 'payload_bytes': 7, 'ctxt_header_bytes': 0, 'ctxt_trailer_bytes': 2,
               'ctxt_escape_expansion_bytes': 0, 'ctxt_message_bytes': 9, 'ctxt_peer_message_limit_bytes': 9}
    assert registry.validate_parameters('custom_text', framing)['status'] == 'VALID'
    assert registry.validate_parameters('custom_text', {**framing, 'ctxt_peer_message_limit_bytes': 8})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_text', {**framing, 'ctxt_message_bytes': 8})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('custom_text'), ids=lambda field: 'custom_text/' + field['key'])
def test_every_custom_text_parameter_has_independent_type_and_boundary_checks(field):
    framing = 'FIXED_LENGTH' if field['key'] == 'ctxt_fixed_length_bytes' else 'DELIMITER'
    base = {**CUSTOM_TEXT_ACTUAL, 'ctxt_framing': framing, 'ctxt_encoding': 'UTF16LE' if field['key'] == 'ctxt_utf16_code_units' else 'UTF8'}
    options = field.get('options', [])
    value = '0D0A' if field['key'] == 'ctxt_delimiter_hex' else field.get('default', options[0] if options else False if field['type'] == 'boolean' else 'actual-text-reference' if field['type'] == 'text' else field.get('min', 0))
    assert registry.validate_parameters('custom_text', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('custom_text', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('custom_text', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_custom_text_actual_utf8_and_peer_limits_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**CUSTOM_TEXT_ACTUAL, 'ctxt_text_value': 'A\u00e4\U0001f600', 'ctxt_code_points': 3, 'payload_bytes': 7,
              'ctxt_header_bytes': 0, 'ctxt_trailer_bytes': 2, 'ctxt_escape_expansion_bytes': 0,
              'ctxt_message_bytes': 9, 'ctxt_peer_message_limit_bytes': 256, 'ctxt_delimiter_hex': '0D0A'}
    parameters = {'technology': 'custom_text', **values, 'technology_parameters': {'custom_text': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['custom_text']['values']['payload_bytes'] = 3
    bad['technology_parameters']['custom_text']['provenance']['payload_bytes']['value'] = 3
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_custom_tcp_application_has_no_ethernet_rate_or_tcp_segment_limit():
    fields = {item['key']: item for item in registry.parameter_fields('custom_tcp')}
    profile = registry.profile('custom_tcp')
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['custom_tcp']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.parameter_defaults_review('custom_tcp')['values'] == {}
    assert not {'bitrate', 'mtu_bytes', 'duplex', 'vlan_id', 'retry_limit', 'retransmission_delay_ms'} & fields.keys()
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert fields['ctcp_stream_service']['default'] == 'ORDERED_BYTE_STREAM'
    assert registry.validate_parameters('custom_tcp', {})['status'] == 'UNVERIFIED'
    assert registry.validate_parameters('custom_tcp', {**CUSTOM_TCP_ACTUAL, 'payload_bytes': 1048576})['status'] == 'VALID'
    assert registry.validate_parameters('custom_tcp', {**CUSTOM_TCP_ACTUAL, 'bitrate': 10000000})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_tcp', {**CUSTOM_TCP_ACTUAL, 'cp_acknowledgement': 'APPLICATION'})['status'] == 'INVALID'


def test_custom_tcp_actual_application_framing_and_ack_are_independent_from_tcp_delivery():
    base = {**CUSTOM_TCP_ACTUAL, 'payload_bytes': 100000, 'ctcp_header_bytes': 4, 'ctcp_trailer_bytes': 2,
            'ctcp_escape_expansion_bytes': 1, 'ctcp_message_bytes': 100007, 'ctcp_peer_message_limit_bytes': 200000,
            'ctcp_length_prefix_bytes': 4, 'ctcp_application_ack': True, 'ctcp_application_ack_timeout_ms': 20}
    assert registry.validate_parameters('custom_tcp', base)['status'] == 'VALID'
    for patch in ({'ctcp_message_bytes': 100006}, {'ctcp_peer_message_limit_bytes': 100000},
                  {'ctcp_framing': 'FIXED_LENGTH'}, {'ctcp_application_ack': False},
                  {'ctcp_application_ack_timeout_ms': 0}, {'ctcp_framing': 'TCP_PSH'}, {'ctcp_delimiter_hex': '0A'}):
        assert registry.validate_parameters('custom_tcp', {**base, **patch})['status'] == 'INVALID', patch
    for framing, key, value in [('FIXED_LENGTH', 'ctcp_fixed_length_bytes', 10), ('DELIMITER', 'ctcp_delimiter_hex', '0D0A'), ('CONNECTION_CLOSE', 'ctcp_message_bytes', 1000000)]:
        assert registry.validate_parameters('custom_tcp', {**CUSTOM_TCP_ACTUAL, 'ctcp_framing': framing, key: value})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('custom_tcp'), ids=lambda field: 'custom_tcp/' + field['key'])
def test_every_custom_tcp_parameter_has_independent_type_and_boundary_checks(field):
    framing = 'FIXED_LENGTH' if field['key'] == 'ctcp_fixed_length_bytes' else 'DELIMITER' if field['key'] == 'ctcp_delimiter_hex' else 'LENGTH_PREFIX'
    base = {**CUSTOM_TCP_ACTUAL, 'ctcp_framing': framing}
    options = field.get('options', [])
    preferred = {'ctcp_delimiter_hex': '0D0A', 'ctcp_application_ack_timeout_ms': 0.1}
    value = preferred.get(field['key'], field.get('default', options[0] if options else False if field['type'] == 'boolean' else 'actual-app-reference' if field['type'] == 'text' else field.get('min', 0)))
    assert registry.validate_parameters('custom_tcp', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('custom_tcp', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('custom_tcp', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_custom_tcp_large_application_messages_and_actual_transport_reference_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**CUSTOM_TCP_ACTUAL, 'payload_bytes': 100000, 'ctcp_header_bytes': 4, 'ctcp_trailer_bytes': 0,
              'ctcp_escape_expansion_bytes': 0, 'ctcp_message_bytes': 100004, 'ctcp_peer_message_limit_bytes': 200000}
    parameters = {'technology': 'custom_tcp', **values, 'technology_parameters': {'custom_tcp': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['custom_tcp']['values']['ctcp_peer_message_limit_bytes'] = 99999
    bad['technology_parameters']['custom_tcp']['provenance']['ctcp_peer_message_limit_bytes']['value'] = 99999
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_custom_protocol_requires_actual_spec_without_binary_can_or_transport_fallback():
    fields = {item['key']: item for item in registry.parameter_fields('custom_protocol')}
    profile = registry.profile('custom_protocol')
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['custom_protocol']
    assert profile['max_payload_bytes'] is None and profile['default_bitrate'] is None
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.parameter_defaults_review('custom_protocol')['values'] == {}
    assert registry.validate_parameters('custom_protocol', {})['status'] == 'UNVERIFIED'
    assert 'max' not in fields['payload_bytes'] and 'default' not in fields['payload_bytes']
    for field in fields.values():
        if field['parameter_origin'] != 'NIS_SCENARIO':
            assert field['default_status'] == 'UNKNOWN' and 'default' not in field
    base = {**CUSTOM_PROTOCOL_ACTUAL, 'payload_bytes': 1048576, 'cp_overhead_bytes': 12, 'cp_pdu_bytes': 1048588}
    assert registry.validate_parameters('custom_protocol', base)['status'] == 'VALID'
    for patch in ({'cb_byte_order': 'LITTLE_ENDIAN'}, {'can_identifier': 1}, {'coap_transport': 'UDP'},
                  {'bitrate': 10000000}, {'cp_peer_pdu_limit_bytes': 1048576}, {'cp_pdu_bytes': 1048587}):
        assert registry.validate_parameters('custom_protocol', {**base, **patch})['status'] == 'INVALID', patch


def test_custom_protocol_distinguishes_application_ack_from_lower_transport_reliability():
    base = {**CUSTOM_PROTOCOL_ACTUAL, 'cp_acknowledgement': 'APPLICATION', 'cp_ack_timeout_ms': 50,
            'cp_response_bound_ms': 40, 'cp_retry_limit': 2, 'cp_retry_delay_ms': 10}
    assert registry.validate_parameters('custom_protocol', base)['status'] == 'VALID'
    for patch in ({'cp_ack_timeout_ms': 0}, {'cp_response_bound_ms': 51},
                  {'cp_acknowledgement': 'NONE'}, {'cp_acknowledgement': 'LOWER_TRANSPORT_ONLY'}):
        assert registry.validate_parameters('custom_protocol', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('custom_protocol', {**CUSTOM_PROTOCOL_ACTUAL, 'cp_acknowledgement': 'LOWER_TRANSPORT_ONLY'})['status'] == 'VALID'
    assert registry.validate_parameters('custom_protocol', {**CUSTOM_PROTOCOL_ACTUAL, 'cp_ack_timeout_ms': 0.1})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('custom_protocol'), ids=lambda field: 'custom_protocol/' + field['key'])
def test_every_custom_protocol_parameter_has_independent_type_and_boundary_checks(field):
    options = field.get('options', [])
    value = 0.1 if field['key'] == 'cp_ack_timeout_ms' else field.get('default', options[0] if options else False if field['type'] == 'boolean' else 'actual-spec-reference' if field['type'] == 'text' else field.get('min', 0))
    assert registry.validate_parameters('custom_protocol', {**CUSTOM_PROTOCOL_ACTUAL, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('custom_protocol', {**CUSTOM_PROTOCOL_ACTUAL, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('custom_protocol', {**CUSTOM_PROTOCOL_ACTUAL, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_custom_protocol_independent_ack_and_large_pdu_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**CUSTOM_PROTOCOL_ACTUAL, 'payload_bytes': 100000, 'cp_overhead_bytes': 16, 'cp_pdu_bytes': 100016,
              'cp_acknowledgement': 'APPLICATION', 'cp_ack_timeout_ms': 25, 'cp_response_bound_ms': 20}
    parameters = {'technology': 'custom_protocol', **values, 'technology_parameters': {'custom_protocol': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    for section in ('values', 'provenance'):
        if section == 'values':
            bad['technology_parameters']['custom_protocol'][section]['cp_acknowledgement'] = 'NONE'
        else:
            bad['technology_parameters']['custom_protocol'][section]['cp_acknowledgement']['value'] = 'NONE'
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_custom_binary_requires_own_specification_without_can_or_ethernet_defaults():
    fields = {item['key']: item for item in registry.parameter_fields('custom_binary')}
    profile = registry.profile('custom_binary')
    assert profile['domain'] == 'generic_networking' and profile['default_stack'] == ['custom_binary']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.parameter_defaults_review('custom_binary')['values'] == {}
    assert 'max' not in fields['payload_bytes'] and 'default' not in fields['payload_bytes']
    assert not {'bitrate', 'mtu_bytes', 'duplex', 'qos_priority', 'sync_method', 'retry_limit'} & fields.keys()
    for field in fields.values():
        if field['parameter_origin'] != 'NIS_SCENARIO':
            assert field['default_status'] == 'UNKNOWN' and 'default' not in field
    assert registry.validate_parameters('custom_binary', {})['status'] == 'UNVERIFIED'
    assert registry.validate_parameters('custom_binary', {**CUSTOM_BINARY_ACTUAL, 'payload_bytes': 1000000})['status'] == 'VALID'
    assert registry.validate_parameters('custom_binary', {**CUSTOM_BINARY_ACTUAL, 'bitrate': 500000})['status'] == 'INVALID'
    assert registry.validate_parameters('custom_binary', {**CUSTOM_BINARY_ACTUAL, 'can_identifier': 1})['status'] == 'INVALID'


def test_custom_binary_framing_and_actual_peer_limit_do_not_borrow_transport_limits():
    base = {**CUSTOM_BINARY_ACTUAL, 'payload_bytes': 70000, 'cb_header_bytes': 4, 'cb_trailer_bytes': 2,
            'cb_padding_bytes': 2, 'cb_message_bytes': 70008, 'cb_peer_message_limit_bytes': 80000,
            'cb_length_prefix_bytes': 4, 'cb_byte_order': 'LITTLE_ENDIAN', 'cb_checksum': 'CRC', 'cb_checksum_bytes': 2}
    assert registry.validate_parameters('custom_binary', base)['status'] == 'VALID'
    for patch in ({'cb_message_bytes': 70007}, {'cb_peer_message_limit_bytes': 70007},
                  {'cb_framing': 'FIXED_LENGTH'}, {'cb_length_prefix_bytes': 0},
                  {'cb_checksum': 'NONE'}, {'cb_delimiter_hex': '0D0A'}, {'cb_byte_order': 'AUTOMOTIVE'}):
        assert registry.validate_parameters('custom_binary', {**base, **patch})['status'] == 'INVALID', patch
    fixed = {**CUSTOM_BINARY_ACTUAL, 'cb_framing': 'FIXED_LENGTH', 'cb_fixed_length_bytes': 72, 'cb_message_bytes': 72}
    assert registry.validate_parameters('custom_binary', fixed)['status'] == 'VALID'
    assert registry.validate_parameters('custom_binary', {**fixed, 'cb_fixed_length_bytes': 71})['status'] == 'INVALID'
    delimiter = {**CUSTOM_BINARY_ACTUAL, 'cb_framing': 'DELIMITER', 'cb_delimiter_hex': '0D0A'}
    assert registry.validate_parameters('custom_binary', delimiter)['status'] == 'VALID'
    assert registry.validate_parameters('custom_binary', {**delimiter, 'cb_delimiter_hex': '0D0'})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('custom_binary'), ids=lambda field: 'custom_binary/' + field['key'])
def test_every_custom_binary_parameter_has_independent_type_and_boundary_checks(field):
    framing = 'FIXED_LENGTH' if field['key'] == 'cb_fixed_length_bytes' else 'DELIMITER' if field['key'] == 'cb_delimiter_hex' else 'LENGTH_PREFIX'
    base = {**CUSTOM_BINARY_ACTUAL, 'cb_framing': framing}
    options = field.get('options', [])
    value = '0D0A' if field['key'] == 'cb_delimiter_hex' else field.get('default', options[0] if options else False if field['type'] == 'boolean' else 'actual-spec-reference' if field['type'] == 'text' else field.get('min', 0))
    assert registry.validate_parameters('custom_binary', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('custom_binary', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    for boundary in ('min', 'max'):
        if boundary in field:
            assert registry.validate_parameters('custom_binary', {**base, field['key']: field[boundary] + (-1 if boundary == 'min' else 1)})['status'] == 'INVALID'


def test_custom_binary_actual_large_messages_and_unknown_checksum_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {**CUSTOM_BINARY_ACTUAL, 'payload_bytes': 70000, 'cb_message_bytes': 70008,
              'cb_header_bytes': 4, 'cb_trailer_bytes': 2, 'cb_padding_bytes': 2, 'cb_peer_message_limit_bytes': 80000}
    parameters = {'technology': 'custom_binary', **values, 'technology_parameters': {'custom_binary': {'values': values,
                  'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    assert 'cb_checksum' not in service.get()['parameters']
    bad = deepcopy(parameters)
    bad['technology_parameters']['custom_binary']['values']['cb_peer_message_limit_bytes'] = 70000
    bad['technology_parameters']['custom_binary']['provenance']['cb_peer_message_limit_bytes']['value'] = 70000
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_coap_transport_selection_has_no_ethernet_rate_or_fixed_body_cap():
    fields={item['key']:item for item in registry.parameter_fields('coap')}
    profile=registry.profile('coap')
    assert profile['domain']=='generic_networking' and profile['default_stack']==['coap']
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('coap')['values']=={}
    assert fields['coap_transport']['required'] and 'default' not in fields['coap_transport']
    assert 'max' not in fields['payload_bytes'] and 'default' not in fields['payload_bytes']
    assert not {'bitrate','mtu_bytes','duplex','qos_priority','sync_method','retry_limit'} & fields.keys()
    assert fields['coap_max_age_s']['default']==60
    assert fields['coap_ack_timeout_s']['conditional_defaults']==[{'when':{'coap_transport':transport},'value':2} for transport in ('UDP','DTLS')]
    assert fields['coap_port']['conditional_defaults']==[{'when':{'coap_transport':transport},'value':port} for transport,port in (('UDP',5683),('DTLS',5684),('TCP',5683),('TLS',5684),('WS',80),('WSS',443))]
    assert registry.validate_parameters('coap',{})['status']=='UNVERIFIED'
    for transport in ('UDP','DTLS','TCP','TLS','WS','WSS'):
        assert registry.validate_parameters('coap',{'coap_transport':transport,'payload_bytes':16384})['status']=='VALID'
        assert registry.validate_parameters('coap',{'coap_transport':transport,'bitrate':10000000})['status']=='INVALID'


def test_coap_udp_retransmission_formulas_update_with_actual_timer_changes():
    base={'coap_transport':'UDP','coap_ack_timeout_s':2,'coap_ack_random_factor':1.5,'coap_max_retransmit':4,
          'coap_max_latency_s':100,'coap_processing_delay_s':2,'coap_max_transmit_span_s':45,'coap_max_transmit_wait_s':93,
          'coap_max_rtt_s':202,'coap_exchange_lifetime_s':247,'coap_non_repeat':True,'coap_non_lifetime_s':145}
    assert registry.validate_parameters('coap',base)['status']=='VALID'
    for patch in ({'coap_ack_timeout_s':1},{'coap_max_retransmit':5},{'coap_max_transmit_span_s':44},
                  {'coap_exchange_lifetime_s':246},{'coap_non_lifetime_s':144},{'coap_max_rtt_s':201},
                  {'coap_transport':'TCP'},{'coap_ack_random_factor':0.9}):
        assert registry.validate_parameters('coap',{**base,**patch})['status']=='INVALID',patch
    changed={**base,'coap_ack_timeout_s':1,'coap_congestion_control_verified':True,'coap_processing_delay_s':1,
             'coap_max_transmit_span_s':22.5,'coap_max_transmit_wait_s':46.5,'coap_max_rtt_s':201,
             'coap_exchange_lifetime_s':223.5,'coap_non_lifetime_s':122.5}
    assert registry.validate_parameters('coap',changed)['status']=='VALID'
    assert registry.validate_parameters('coap',{**changed,'coap_congestion_control_verified':False})['status']=='INVALID'
    assert registry.validate_parameters('coap',{**base,'coap_max_retransmit':1000000})['status']=='INVALID'
    assert registry.validate_parameters('coap',{'coap_transport':'UDP','coap_non_repeat':False,'coap_non_lifetime_s':100,'coap_max_latency_s':100})['status']=='VALID'


def test_coap_native_tokens_blocks_message_sizes_and_uris_are_transport_specific():
    udp={'coap_transport':'UDP','coap_token_format':'BASE_8','coap_token_bytes':8,'coap_block_kind':'BLOCK2',
         'coap_block_usage':'DESCRIPTIVE','coap_block_szx':0,'coap_block_more':True,'payload_bytes':16,
         'coap_header_bytes':4,'coap_options_bytes':2,'coap_payload_marker_bytes':1,'coap_message_bytes':31,'coap_uri':'coap://[2001:db8::1]/sensor'}
    assert registry.validate_parameters('coap',udp)['status']=='VALID'
    for patch in ({'coap_token_bytes':9},{'payload_bytes':15},{'coap_block_szx':7},{'coap_message_bytes':30},
                  {'coap_payload_marker_bytes':0},{'coap_uri':'coap+tcp://example.org/sensor'},
                  {'coap_uri':'coap://user:secret@example.org/sensor'},{'coap_uri':'coap://example.org:70000/sensor'},
                  {'coap_observe_kind':'REQUEST','coap_observe_value':2}):
        assert registry.validate_parameters('coap',{**udp,**patch})['status']=='INVALID',patch
    bert={'coap_transport':'TLS','coap_uri':'coaps+tcp://example.org/sensor','coap_token_format':'EXTENDED_RFC8974',
          'coap_token_bytes':32,'coap_peer_token_limit':32,'coap_csm_max_message_bytes':4096,'coap_csm_blockwise_supported':True,
          'coap_block_usage':'DESCRIPTIVE','coap_block_more':True,'coap_block_szx':7,'payload_bytes':2048,'coap_message_bytes':2200}
    assert registry.validate_parameters('coap',bert)['status']=='VALID'
    for patch in ({'coap_csm_blockwise_supported':False},{'coap_csm_max_message_bytes':1152},{'payload_bytes':2049},
                  {'coap_peer_token_limit':31},{'coap_message_type':'CON'},{'coap_multicast':True}):
        assert registry.validate_parameters('coap',{**bert,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('coap',{'coap_transport':'UDP','coap_message_type':'RST','payload_bytes':1})['status']=='INVALID'
    assert registry.validate_parameters('coap',{'coap_transport':'UDP','coap_mtu_policy':'UNKNOWN_PATH_RFC7252','payload_bytes':1025})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('coap'),ids=lambda field:'coap/'+field['key'])
def test_every_coap_parameter_has_independent_type_and_boundary_checks(field):
    transport='TCP' if field['key'].startswith('coap_csm_') else 'UDP'
    base={'coap_transport':transport}
    options=field.get('options',[])
    preferred={'coap_uri':'coap://example.org/sensor','coap_header_bytes':4,'coap_ack_timeout_s':0.001,'coap_default_leisure_s':0.001,'coap_probing_rate_Bps':0.001}
    value=preferred.get(field['key'],field.get('default',options[0] if options else False if field['type']=='boolean' else 'actual-peer-reference' if field['type']=='text' else field.get('min',0)))
    assert registry.validate_parameters('coap',{**base,field['key']:value})['status']=='VALID'
    assert registry.validate_parameters('coap',{**base,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('coap',{**base,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'


def test_coap_actual_reliable_parameters_and_capabilities_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={'coap_transport':'TLS','coap_port':5684,'coap_uri':'coaps+tcp://example.org/sensor',
            'coap_token_format':'EXTENDED_RFC8974','coap_token_bytes':32,'coap_peer_token_limit':32,
            'coap_csm_max_message_bytes':8192,'coap_csm_blockwise_supported':True,'payload_bytes':2048}
    parameters={'technology':'coap',**values,'technology_parameters':{'coap':{'values':values,
                'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['coap']['values']['coap_transport']='UDP'
    bad['technology_parameters']['coap']['provenance']['coap_transport']['value']='UDP'
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_cip_safety_does_not_inherit_can_or_ethernet_defaults_or_certify_safety():
    fields={item['key']:item for item in registry.parameter_fields('cip_safety')}
    profile=registry.profile('cip_safety')
    assert profile['domain']=='generic_networking' and profile['default_bitrate'] is None
    assert profile['default_stack']==['cip_safety'] and profile['max_payload_bytes']==250
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('cip_safety')['values']=={}
    assert fields['cips_transport']['required'] and 'default' not in fields['cips_transport']
    assert fields['cips_baseline']['default']=='MODERN_EXTENDED' and fields['cips_format']['default']=='EXTENDED'
    assert fields['cips_max_fault_number']['conditional_defaults']==[{'when':{'cips_baseline':'MODERN_EXTENDED'},'value':2}]
    assert not {'bitrate','qos_priority','retry_limit','sync_method','retransmission_enabled'} & fields.keys()
    assert registry.validate_parameters('cip_safety',{})['status']=='UNVERIFIED'
    for transport in ('ETHERNET_IP','DEVICENET','SERCOS_III'):
        assert registry.validate_parameters('cip_safety',{'cips_transport':transport})['status']=='VALID'
        assert registry.validate_parameters('cip_safety',{'cips_transport':transport,'bitrate':125000})['status']=='INVALID'
    for key in ('payload_bytes','cips_snn','cips_rpi_ms','cips_crtl_ms','cips_safety_connection_established','cips_configuration_locked'):
        assert 'default' not in fields[key]


def test_cip_safety_own_size_and_age_constraints_distinguish_certified_legacy_and_transport():
    base={'cips_transport':'ETHERNET_IP','cips_baseline':'MODERN_EXTENDED','cips_format':'EXTENDED','cips_max_fault_number':2,
          'cips_data_size':'SHORT','payload_bytes':2,'cips_connection':'UNICAST','cips_consumers':1,'cips_snn':'4919_0473_9A84',
          'cips_ip_address':'192.168.1.10','cips_crtl_ms':40.064,'cips_data_age_bound_ms':30,'cips_application_reaction_limit_ms':45}
    assert registry.validate_parameters('cip_safety',base)['status']=='VALID'
    for patch in ({'cips_format':'BASE'},{'cips_max_fault_number':5},{'payload_bytes':3},{'cips_consumers':2},
                  {'cips_snn':'4919_0473'},{'cips_ip_address':'192.168.999.1'},{'cips_crtl_ms':0},
                  {'cips_data_age_bound_ms':41},{'cips_application_reaction_limit_ms':39},
                  {'cips_transport':'DEVICENET'},{'cips_devicenet_node':1},{'cips_time_correction_bound_ms':0}):
        assert registry.validate_parameters('cip_safety',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('cip_safety',{**base,'cips_baseline':'CERTIFIED_LEGACY','cips_format':'BASE','cips_max_fault_number':5})['status']=='VALID'
    assert registry.validate_parameters('cip_safety',{**base,'cips_connection':'MULTICAST','cips_consumers':15,'cips_time_correction_bound_ms':0.1,'cips_data_size':'LONG','payload_bytes':250})['status']=='VALID'
    assert registry.validate_parameters('cip_safety',{**base,'cips_connection':'MULTICAST','cips_consumers':16})['status']=='INVALID'
    output={'cips_transport':'ETHERNET_IP','cips_device_profile':'GUARDLOGIX_SAFETY_IO','cips_direction':'OUTPUT','cips_rpi_ms':10,'cips_safety_task_ms':10,
            'cips_timeout_multiplier':2,'cips_network_delay_percent':200}
    assert registry.validate_parameters('cip_safety',output)['status']=='VALID'
    for patch in ({'cips_rpi_ms':11},{'cips_timeout_multiplier':5},{'cips_network_delay_percent':9}):
        assert registry.validate_parameters('cip_safety',{**output,**patch})['status']=='INVALID'
    assert registry.validate_parameters('cip_safety',{**output,'cips_device_profile':'DEVICE_SPECIFIC','cips_direction':'PEER','cips_timeout_multiplier':5})['status']=='VALID'


@pytest.mark.parametrize('field',registry.parameter_fields('cip_safety'),ids=lambda field:'cip_safety/'+field['key'])
def test_every_cip_safety_field_has_individual_type_and_range_validation(field):
    options=field.get('options',[])
    preferred={'cips_snn':'4919_0473_9A84','cips_ip_address':'192.168.1.10','cips_devicenet_node':1,
               'cips_rpi_ms':0.00001,'cips_safety_task_ms':0.00001,'cips_crtl_ms':0.00001,'cips_application_reaction_limit_ms':0.00001}
    value=preferred.get(field['key'],field.get('default',options[0] if options else False if field['type']=='boolean' else 'actual-device-reference' if field['type']=='text' else field.get('min',0)))
    base={'cips_transport':'DEVICENET' if field['key']=='cips_devicenet_node' else 'ETHERNET_IP'}
    assert registry.validate_parameters('cip_safety',{**base,field['key']:value})['status']=='VALID'
    assert registry.validate_parameters('cip_safety',{**base,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('cip_safety',{**base,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'


def test_cip_safety_confirmed_parameters_persist_without_fabricating_safe_state():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={'cips_transport':'DEVICENET','cips_devicenet_node':63,'cips_snn':'491904739A84','cips_baseline':'MODERN_EXTENDED',
            'cips_format':'EXTENDED','cips_max_fault_number':2,'cips_connection':'MULTICAST','cips_consumers':3,
            'cips_data_size':'LONG','payload_bytes':32,'cips_crtl_ms':40.064,'cips_data_age_bound_ms':20}
    parameters={'technology':'cip_safety',**values,'technology_parameters':{'cip_safety':{'values':values,
                'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    assert 'cips_safety_connection_established' not in parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['cip_safety']['values']['cips_max_fault_number']=5
    bad['technology_parameters']['cip_safety']['provenance']['cips_max_fault_number']['value']=5
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_ccp_owns_calibration_fields_without_universal_can_rate_or_xcp_fd():
    fields={item['key']:item for item in registry.parameter_fields('ccp')}
    profile=registry.profile('ccp')
    assert profile['domain']=='generic_networking' and profile['default_bitrate'] is None
    assert profile['default_stack']==['can','ccp'] and profile['max_payload_bytes']==8
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('ccp')['values']=={}
    assert fields['ccp_revision']['default']=='2.1'
    for key in ('bitrate','payload_bytes','ccp_station_address','ccp_cro_id','ccp_dto_id','ccp_response_timeout_ms','ccp_connected','ccp_byte_order'):
        assert 'default' not in fields[key]
    assert fields['ccp_station_byte_order']['default']=='LITTLE_ENDIAN'
    assert not {'co_node_id','ccie_variant','data_bitrate','retry_limit','qos_priority'} & fields.keys()
    assert registry.validate_parameters('ccp',{'bitrate':123456.7})['status']=='VALID'
    assert registry.validate_parameters('ccp',{'bitrate':500000,'data_bitrate':2000000})['status']=='INVALID'


def test_ccp_native_objects_and_actual_response_counter_cannot_be_interchanged():
    base={'bitrate':500000,'ccp_object':'CRM','payload_bytes':8,'can_dlc':8,'ccp_pid':255,
          'ccp_command_counter':255,'ccp_response_counter':255,'ccp_data_bytes':5,
          'ccp_response_timeout_ms':15,'ccp_response_bound_ms':12}
    assert registry.validate_parameters('ccp',base)['status']=='VALID'
    for patch in ({'ccp_response_counter':0},{'ccp_pid':254},{'payload_bytes':7},{'ccp_data_bytes':6},
                  {'ccp_response_bound_ms':16},{'ccp_response_timeout_ms':0},{'can_frame_type':'REMOTE'},
                  {'ccp_cro_id_format':'BASE_11','ccp_cro_id':2048}):
        assert registry.validate_parameters('ccp',{**base,**patch})['status']=='INVALID',patch
    daq={'bitrate':125000,'ccp_object':'DAQ','ccp_pid':253,'payload_bytes':3,'can_dlc':3,'ccp_data_bytes':2}
    assert registry.validate_parameters('ccp',daq)['status']=='VALID'
    for patch in ({'payload_bytes':4},{'ccp_pid':254},{'ccp_error_code':0},{'payload_bytes':64}):
        assert registry.validate_parameters('ccp',{**daq,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('ccp',{'bitrate':500000,'ccp_object':'EVENT','payload_bytes':8,'ccp_pid':254})['status']=='VALID'
    assert registry.validate_parameters('ccp',{'bitrate':500000,'ccp_object':'EVENT','ccp_response_counter':1})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('ccp'),ids=lambda field:'ccp/'+field['key'])
def test_every_ccp_parameter_has_independent_types_and_boundaries(field):
    options=field.get('options',[])
    value=field.get('default',options[0] if options else False if field['type']=='boolean' else 'actual-device.a2l' if field['type']=='text' else field.get('min',0))
    if field['key'] in {'ccp_response_timeout_ms','ccp_event_period_ms'}:
        value=0.00001
    base={'bitrate':500000}
    assert registry.validate_parameters('ccp',{**base,field['key']:value})['status']=='VALID'
    wrong='invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('ccp',{**base,field['key']:wrong})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('ccp',{**base,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'


def test_ccp_actual_calibration_configuration_survives_sql_without_session_confirmation():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={'bitrate':125000,'ccp_station_address':257,'ccp_cro_id':1513,'ccp_dto_id':1514,'ccp_byte_order':'BIG_ENDIAN',
            'ccp_object':'DAQ','payload_bytes':3,'ccp_data_bytes':2,'ccp_pid':3,'ccp_daq_prescaler':2,'ccp_a2l_source':'actual-device.a2l'}
    parameters={'technology':'ccp',**values,'technology_parameters':{'ccp':{'values':values,
                'provenance':{key:{'value':value,'source':'USER_CONFIRMED','status':'CONFIRMED','device_reference':'actual-device.a2l'} for key,value in values.items()}}}}
    saved=service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    assert 'ccp_connected' not in saved['parameters']
    bad=deepcopy(parameters)
    bad['payload_bytes']=4
    bad['technology_parameters']['ccp']['values']['payload_bytes']=4
    bad['technology_parameters']['ccp']['provenance']['payload_bytes']['value']=4
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_cclink_ie_requires_actual_variant_and_proposes_only_its_own_speed():
    fields={item['key']:item for item in registry.parameter_fields('cc_link_ie')}
    profile=registry.profile('cc_link_ie')
    assert registry.parameter_defaults_review('cc_link_ie')['values']=={}
    assert profile['default_bitrate'] is None and profile['max_payload_bytes'] is None
    assert profile['domain']=='generic_networking' and profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert fields['ccie_variant']['required'] and 'default' not in fields['ccie_variant']
    assert 'default' not in fields['bitrate']
    assert fields['bitrate']['conditional_defaults']==[
        {'when':{'ccie_variant':'CONTROLLER'},'value':1000000000},{'when':{'ccie_variant':'FIELD'},'value':1000000000},
        {'when':{'ccie_variant':'FIELD_BASIC'},'value':100000000},{'when':{'ccie_variant':'TSN'},'value':100000000}]
    assert registry.validate_parameters('cc_link_ie',{'bitrate':1000000000})['status']=='UNVERIFIED'
    for variant in ('CONTROLLER','FIELD','FIELD_BASIC','TSN'):
        assert registry.validate_parameters('cc_link_ie',{'ccie_variant':variant,'bitrate':1000000000})['status']=='VALID'
    for variant in ('CONTROLLER','FIELD'):
        assert registry.validate_parameters('cc_link_ie',{'ccie_variant':variant,'bitrate':100000000})['status']=='INVALID'
    for variant in ('FIELD_BASIC','TSN'):
        assert registry.validate_parameters('cc_link_ie',{'ccie_variant':variant,'bitrate':100000000})['status']=='VALID'
    for key in ('ccie_link_scan_bound_ms','ccie_device_response_bound_ms','ccie_station_number','ccie_access','payload_bytes','ccie_tsn_cycle_us'):
        assert 'default' not in fields[key]
    assert not {'sync_method','qos_priority','retry_limit','mtu_bytes','vlan_id'} & fields.keys()


def test_cclink_ie_variant_native_dependencies_and_device_limits():
    basics={'ccie_variant':'FIELD_BASIC','bitrate':100000000,'ccie_access':'UDP_MANAGER_POLLING','ccie_phy':'100BASE_TX',
            'ccie_occupied_stations':4,'ccie_station_number':61,'ccie_station_rx_bits':256,'ccie_station_rwr_words':128,
            'ccie_basic_controller':'MELSEC_IQ_F','ccie_basic_timeout_ms':20,'ccie_basic_disconnect_count':3}
    assert registry.validate_parameters('cc_link_ie',basics)['status']=='VALID'
    for patch in ({'ccie_access':'TOKEN_PASSING'},{'ccie_station_number':62},{'ccie_station_rx_bits':257},
                  {'ccie_station_rwr_words':129},{'ccie_basic_timeout_ms':19},{'ccie_basic_disconnect_count':4},
                  {'ccie_tsn_class':'A'},{'ccie_topology':'RING'},{'ccie_controller_mode':'NORMAL'},
                  {'ccie_phy':'1000BASE_T'},{'ccie_device_slots':65},{'ccie_network_rx_bits':4097}):
        assert registry.validate_parameters('cc_link_ie',{**basics,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('cc_link_ie',{**basics,'bitrate':1000000000,'ccie_phy':'1000BASE_T','ccie_basic_optional_1g_supported':False})['status']=='INVALID'
    controller={'ccie_variant':'CONTROLLER','bitrate':1000000000,'ccie_phy':'1000BASE_SX','ccie_topology':'RING',
                'ccie_nodes':120,'ccie_link_length_m':550,'ccie_controller_mode':'NORMAL','ccie_controller_lb_bits':16384}
    assert registry.validate_parameters('cc_link_ie',controller)['status']=='VALID'
    for patch in ({'ccie_nodes':121},{'ccie_link_length_m':551},{'ccie_topology':'LINE'}, {'ccie_controller_lb_bits':16385}):
        assert registry.validate_parameters('cc_link_ie',{**controller,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('cc_link_ie',{**controller,'ccie_controller_mode':'EXTENDED','ccie_controller_lb_bits':32768,'ccie_transient_limit_bytes':1920,'ccie_transient_bytes':1920})['status']=='VALID'
    assert registry.validate_parameters('cc_link_ie',{**controller,'ccie_transient_limit_bytes':960,'ccie_transient_bytes':961})['status']=='INVALID'
    tsn={'ccie_variant':'TSN','bitrate':100000000,'ccie_access':'TIME_SHARING','ccie_tsn_class':'B','ccie_tsn_cycle_us':250,'ccie_tsn_guard_us':10}
    assert registry.validate_parameters('cc_link_ie',tsn)['status']=='VALID'
    assert registry.validate_parameters('cc_link_ie',{**tsn,'ccie_tsn_guard_us':251})['status']=='INVALID'
    assert registry.validate_parameters('cc_link_ie',{**tsn,'ccie_basic_cyclic_udp_port':61450})['status']=='INVALID'
    assert registry.validate_parameters('cc_link',{'bitrate':156000,'ccie_variant':'FIELD_BASIC'})['status']=='INVALID'


def test_cclink_ie_physical_realization_cannot_treat_fiber_as_copper_or_basic_as_token():
    from backend.communication.technologies.core.physical import validate_physical_realization
    actual={'technology':'cc_link_ie','ccie_variant':'CONTROLLER','phy_variant':'1000BASE_SX','topology':'RING','length_m':550}
    result=validate_physical_realization(actual)
    assert result['status']=='VALID' and result['resolved_medium_access_model']=='TOKEN_PASSING'
    for patch in ({'length_m':551},{'conductors':['CAN_H','CAN_L']},{'topology':'LINE'},{'ccie_variant':'FIELD_BASIC'}):
        assert validate_physical_realization({**actual,**patch})['status']=='INVALID',patch
    basic={'technology':'cc_link_ie','ccie_variant':'FIELD_BASIC','phy_variant':'100BASE_TX','pair_count':2,'topology':'STAR','length_m':100}
    result=validate_physical_realization(basic)
    assert result['status']=='VALID' and result['resolved_medium_access_model']=='MASTER_SCHEDULED'
    assert validate_physical_realization({**basic,'pair_count':4})['status']=='INVALID'
    assert validate_physical_realization({'technology':'cc_link_ie','topology':'LINE'})['status']=='REVIEW_REQUIRED'
    assert validate_physical_realization({**basic,'ccie_variant':'TSN'})['status']=='REVIEW_REQUIRED'


@pytest.mark.parametrize('field',registry.parameter_fields('cc_link_ie'),ids=lambda field:'cc_link_ie/'+field['key'])
def test_every_cclink_ie_parameter_has_individual_type_and_range_checks(field):
    variant='CONTROLLER' if field['key'].startswith('ccie_controller_') else 'TSN' if field['key'].startswith('ccie_tsn_') else 'FIELD_BASIC'
    base={'bitrate':1000000000,'ccie_variant':variant}
    options=field.get('options',[])
    preferred={'bitrate':1000000000,'ccie_variant':'FIELD_BASIC','ccie_access':'UDP_MANAGER_POLLING','ccie_phy':'1000BASE_T',
               'ccie_basic_optional_1g_supported':True}
    value=preferred.get(field['key'],field.get('default',options[0] if options else False if field['type']=='boolean' else field.get('min',0)))
    assert registry.validate_parameters('cc_link_ie',{**base,field['key']:value})['status']=='VALID'
    assert registry.validate_parameters('cc_link_ie',{**base,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('cc_link_ie',{**base,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'


def test_cclink_ie_confirmed_variant_and_device_values_persist_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={'bitrate':100000000,'ccie_variant':'FIELD_BASIC','ccie_phy':'100BASE_TX','ccie_basic_cyclic_udp_port':61450,
            'ccie_occupied_stations':2,'ccie_station_number':63,'ccie_station_rx_bits':128,'ccie_link_scan_bound_ms':20}
    parameters={'technology':'cc_link_ie',**values,'technology_parameters':{'cc_link_ie':{'values':values,
                'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['cc_link_ie']['values']['ccie_variant']='CONTROLLER'
    bad['technology_parameters']['cc_link_ie']['provenance']['ccie_variant']['value']='CONTROLLER'
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_cclink_defaults_do_not_use_peak_rate_or_fake_wire_payload_cap():
    fields={item['key']:item for item in registry.parameter_fields('cc_link')}
    assert registry.parameter_defaults_review('cc_link')['values']=={'bitrate_bps':156000}
    assert fields['bitrate']['default']==156000
    assert fields['ccl_protocol_version']['default']=='1.10'
    assert fields['ccl_extended_cycle']['default']==1
    assert fields['ccl_termination_ohms']['default']==110
    assert 'default' not in fields['payload_bytes'] and 'max' not in fields['payload_bytes']
    assert 'default' not in fields['ccl_station_number'] and 'default' not in fields['ccl_link_scan_bound_ms']
    assert 'default' not in fields['ccl_q_retry_count']
    assert fields['ccl_q_retry_count']['conditional_defaults']==[{'when':{'ccl_controller_profile':'QJ61BT11N'},'value':3}]
    for rate in (156000,625000,2500000,5000000,10000000):
        assert registry.validate_parameters('cc_link',{'bitrate':rate})['status']=='VALID'
    for rate in (10000,156250,500000,100000000):
        assert registry.validate_parameters('cc_link',{'bitrate':rate})['status']=='INVALID'
    profile=registry.profile('cc_link')
    assert profile['physical_layer_profile_id']=='CCLINK_DEDICATED_EIA485'
    assert profile['medium_access_model']=='MASTER_SCHEDULED'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert profile['max_payload_bytes'] is None and profile['domain']=='generic_networking'
    assert not {'qos_priority','sync_method','reserved_bandwidth_percent','retry_limit','retransmission_enabled'} & fields.keys()


def test_cclink_station_slots_native_cyclic_areas_and_vendor_buffers():
    base={'bitrate':156000,'ccl_protocol_version':'2.00','ccl_occupied_stations':4,'ccl_extended_cycle':8,
          'ccl_station_role':'REMOTE_DEVICE','ccl_station_number':61,'ccl_rx_bits':896,'ccl_rwr_words':128}
    assert registry.validate_parameters('cc_link',base)['status']=='VALID'
    for patch in ({'ccl_protocol_version':'1.10'}, {'ccl_station_number':62}, {'ccl_extended_cycle':3},
                  {'ccl_rx_bits':897}, {'ccl_rwr_words':129}, {'ccl_total_occupied_stations':2,'ccl_device_count':3},
                  {'ccl_station_role':'MANAGER'}, {'ccl_station_number':0}, {'ccl_protocol_version':'1.10','ccl_extended_cycle':1,'ccl_total_rwr_words':257},
                  {'ccl_controller_profile':'DEVICE_SPECIFIC','ccl_q_retry_count':3},
                  {'ccl_controller_profile':'QJ61BT11N','ccl_q_transient_send_words':4096,'ccl_q_transient_receive_words':64},
                  {'ccl_q_transient_send_words':1},{'ccl_q_transient_auto_words':64}):
        assert registry.validate_parameters('cc_link',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('cc_link',{'bitrate':156000,'ccl_station_role':'MANAGER','ccl_station_number':0})['status']=='VALID'
    for occ in range(1,5):
        for cycle in (1,2,4,8):
            bits=32*occ if cycle==1 else (2*occ-1)*16*cycle
            values={'bitrate':156000,'ccl_protocol_version':'2.00','ccl_occupied_stations':occ,'ccl_extended_cycle':cycle,'ccl_rx_bits':bits,'ccl_rwr_words':4*occ*cycle}
            assert registry.validate_parameters('cc_link',values)['status']=='VALID'
            assert registry.validate_parameters('cc_link',{**values,'ccl_rx_bits':bits+1})['status']=='INVALID'
    assert registry.validate_parameters('can',{'bitrate':500000,'ccl_station_number':1})['status']=='INVALID'


def test_cclink_cable_versions_rate_length_and_tbranch_are_independent():
    for rate,limit in ((156000,1200),(625000,900),(2500000,400),(5000000,160),(10000000,100)):
        values={'bitrate':rate,'ccl_cable_version':'1.10','ccl_topology':'LINE','ccl_main_length_m':limit,'ccl_remote_spacing_m':0.2}
        assert registry.validate_parameters('cc_link',values)['status']=='VALID'
        assert registry.validate_parameters('cc_link',{**values,'ccl_main_length_m':limit+.1})['status']=='INVALID'
    ten={'bitrate':10000000,'ccl_cable_version':'1.10','ccl_topology':'LINE','ccl_main_length_m':100,'ccl_device_count':10,'ccl_consecutive_ten_span_m':10}
    assert registry.validate_parameters('cc_link',ten)['status']=='VALID'
    assert registry.validate_parameters('cc_link',{**ten,'ccl_consecutive_ten_span_m':9.999})['status']=='INVALID'
    assert registry.validate_parameters('cc_link',{**ten,'ccl_main_length_m':80,'ccl_consecutive_ten_span_m':9})['status']=='VALID'
    for rate,spacing,length in ((5000000,.5999999999,110),(5000000,.6,150),(10000000,.3,50),(10000000,.6,80),(10000000,1,100)):
        values={'bitrate':rate,'ccl_cable_version':'1.00_STANDARD','ccl_topology':'LINE','ccl_remote_spacing_m':spacing,'ccl_main_length_m':length}
        assert registry.validate_parameters('cc_link',values)['status']=='VALID'
        assert registry.validate_parameters('cc_link',{**values,'ccl_main_length_m':length+.1})['status']=='INVALID'
    branches={'bitrate':625000,'ccl_topology':'T_BRANCH','ccl_main_length_m':100,'ccl_branch_length_m':8,'ccl_branch_total_m':50,'ccl_branch_devices':6,'ccl_remote_spacing_m':.31}
    assert registry.validate_parameters('cc_link',branches)['status']=='VALID'
    for patch in ({'bitrate':2500000},{'ccl_main_length_m':100.1},{'ccl_branch_length_m':8.1}, {'ccl_branch_total_m':50.1}, {'ccl_branch_devices':7},
                  {'ccl_remote_spacing_m':.3},{'ccl_special_nodes_present':True,'ccl_special_spacing_m':2}):
        assert registry.validate_parameters('cc_link',{**branches,**patch})['status']=='INVALID',patch
    from backend.communication.technologies.core.physical import validate_physical_realization
    assert validate_physical_realization({'technology':'cc_link','topology':'STAR','conductors':['CAN_H','CAN_L']})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('cc_link'),ids=lambda field:'cc_link/'+field['key'])
def test_every_cclink_parameter_has_individual_type_and_range_checks(field):
    base={'bitrate':156000}
    value=field.get('default',field.get('options',[None])[0] if field.get('options') else False if field['type']=='boolean' else field.get('min',0))
    assert registry.validate_parameters('cc_link',{**base,field['key']:value})['status']=='VALID'
    assert registry.validate_parameters('cc_link',{**base,field['key']:'invalid' if field['type']=='number' else 1})['status']=='INVALID'
    for boundary in ('min','max'):
        if boundary in field:
            assert registry.validate_parameters('cc_link',{**base,field['key']:field[boundary]+(-1 if boundary=='min' else 1)})['status']=='INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('cc_link',{**base,field['key']:option})['status']=='VALID'


def test_cclink_confirmed_configuration_is_preserved_and_bad_slot_edits_rejected_in_sql():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service=WorkflowStatusService(current_project_id())
    values={'bitrate':625000,'ccl_protocol_version':'2.00','ccl_station_role':'REMOTE_DEVICE','ccl_station_number':61,'ccl_occupied_stations':4,
            'ccl_extended_cycle':8,'ccl_rx_bits':896,'ccl_rwr_words':128,'ccl_cable_version':'1.10','ccl_topology':'LINE','ccl_main_length_m':600}
    parameters={'technology':'cc_link',**values,'technology_parameters':{'cc_link':{'values':values,
                'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters)
    bad['technology_parameters']['cc_link']['values']['ccl_station_number']=62
    bad['technology_parameters']['cc_link']['provenance']['ccl_station_number']['value']=62
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_canopen_rates_and_recommendations_are_distinct_from_can_defaults():
    fields = {item['key']:item for item in registry.parameter_fields('canopen')}
    assert registry.parameter_defaults_review('canopen')['values']=={'bitrate_bps':10000}
    assert registry.parameter_defaults_review('can')['values']=={}
    assert fields['bitrate']['default']==10000 and fields['sample_point_percent']['default']==87.5
    assert fields['co_sync_can_id']['default']==128 and fields['co_sync_counter_overflow']['default']==0
    assert fields['co_error_control']['default']=='HEARTBEAT'
    assert registry.profile('canopen')['domain']=='generic_networking'
    for key in ('co_node_id','co_pdo_transmission_type','co_nmt_state','co_heartbeat_producer_ms','co_heartbeat_consumer_ms','co_sdo_response_bound_ms'):
        assert 'default' not in fields[key]
    for rate in (10000,20000,50000,125000,250000,500000,800000,1000000):
        assert registry.validate_parameters('canopen',{'bitrate':rate})['status']=='VALID'
    for rate in (9600,19200,100000,2000000):
        assert registry.validate_parameters('canopen',{'bitrate':rate})['status']=='INVALID'
    assert not {'sync_method','qos_priority','retry_limit','data_bitrate'} & fields.keys()
    assert registry.profile('canopen')['capacity_evidence']['status']=='MODEL_MISSING'


def test_canopen_service_payloads_mapping_sdo_and_sync_use_native_rules():
    base = {'bitrate':10000}
    for service,length in (('NMT',2),('SDO',8),('HEARTBEAT',1),('BOOTUP',1),('TIME',6),('EMCY',8)):
        assert registry.validate_parameters('canopen',{**base,'co_service':service,'payload_bytes':length})['status']=='VALID'
        assert registry.validate_parameters('canopen',{**base,'co_service':service,'payload_bytes':length-1})['status']=='INVALID'
    assert registry.validate_parameters('canopen',{**base,'co_service':'SYNC','co_sync_counter_overflow':0,'payload_bytes':0})['status']=='VALID'
    assert registry.validate_parameters('canopen',{**base,'co_service':'SYNC','co_sync_counter_overflow':10,'payload_bytes':1})['status']=='VALID'
    for patch in ({'co_service':'SYNC','co_sync_counter_overflow':0,'payload_bytes':1},
                  {'co_service':'SYNC','co_sync_counter_overflow':10,'payload_bytes':0},
                  {'co_service':'PDO','payload_bytes':1,'co_pdo_mapped_bits':9},
                  {'co_sdo_variant':'EXPEDITED','co_sdo_application_bytes':5},
                  {'co_pdo_transmission_type':241},{'co_pdo_transmission_type':251},
                  {'co_pdo_transmission_type':252,'co_rtr_allowed':False},
                  {'co_sync_counter_overflow':1},{'co_sync_period_us':1000,'co_sync_window_us':1001},
                  {'co_sync_counter_overflow':10,'co_pdo_sync_start':11},
                  {'co_sync_frame_format':'BASE_11','co_sync_can_id':2048},
                  {'co_node_id':0},{'co_node_id':128},{'co_nmt_command':3},
                  {'co_service':'SDO','can_frame_type':'REMOTE'}):
        assert registry.validate_parameters('canopen',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('canopen',{**base,'co_pdo_transmission_type':252,'co_rtr_allowed':True})['status']=='VALID'
    assert registry.validate_parameters('canopen',{**base,'co_service':'HEARTBEAT','payload_bytes':1,'co_pdo_mapped_bits':64})['status']=='VALID'
    assert registry.validate_parameters('can',{'bitrate':500000,'co_node_id':1})['status']=='INVALID'


def test_canopen_bit_timing_table_has_rate_specific_cable_bounds_without_can_fallback():
    base = {'bitrate':500000,'can_phy':'HIGH_SPEED','can_bus_length_m':100,'can_stub_length_m':5.5,'co_accumulated_stub_length_m':27.5}
    assert registry.validate_parameters('canopen',base)['status']=='VALID'
    for patch in ({'can_bus_length_m':100.1},{'can_stub_length_m':5.6},{'co_accumulated_stub_length_m':27.6}, {'bitrate':1000000}):
        assert registry.validate_parameters('canopen',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('can',{'bitrate':500000,'can_phy':'HIGH_SPEED','can_bus_length_m':100.1})['status']=='VALID'
    # A realizable installed75% sample point remains valid, rather than being overwritten by87.5% recommendation.
    clock = {'bitrate':500000,'can_clock_hz':8000000,'can_prescaler':1,'can_tseg1_tq':11,'can_tseg2_tq':4,'sample_point_percent':75}
    assert registry.validate_parameters('canopen',clock)['status']=='VALID'
    assert registry.validate_parameters('canopen',{**clock,'sample_point_percent':87.5})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('canopen'),ids=lambda field:'canopen/'+field['key'])
def test_every_canopen_parameter_is_individually_typed_and_constrained(field):
    base = {'bitrate':10000}
    value = field.get('default',field.get('options',[None])[0] if field.get('options') else
                      False if field['type']=='boolean' else field.get('min',0))
    assert registry.validate_parameters('canopen',{**base,field['key']:value})['status']=='VALID'
    wrong = 'invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('canopen',{**base,field['key']:wrong})['status']=='INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('canopen',{**base,field['key']:field['min']-1})['status']=='INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('canopen',{**base,field['key']:field['max']+1})['status']=='INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('canopen',{**base,field['key']:option})['status']=='VALID'


def test_canopen_confirmed_fields_survive_sql_and_conflicting_pdo_mapping_is_rejected():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate':125000,'co_node_id':12,'co_service':'PDO','payload_bytes':8,'can_dlc':8,
              'co_pdo_transmission_type':1,'co_pdo_mapped_bits':64,'co_sync_period_us':10000,'co_heartbeat_producer_ms':1000}
    parameters = {'technology':'canopen',**values,'technology_parameters':{'canopen':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['canopen']['values']['payload_bytes']=4
    bad['technology_parameters']['canopen']['provenance']['payload_bytes']['value']=4
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_can_xl_has_its_own_two_phases_addressing_and_unknown_hardware():
    fields = {item['key']:item for item in registry.parameter_fields('can_xl')}
    profile = registry.profile('can_xl')
    assert registry.parameter_defaults_review('can_xl')['values']=={}
    assert profile['default_bitrate'] is None and profile['domain']=='generic_networking'
    assert fields['can_xl_revision']['default']=='ISO_2024'
    assert fields['can_xl_pcrc_bits']['default']==13 and fields['can_xl_fcrc_bits']['default']==32
    assert not {'bitrate','can_identifier','can_dlc','can_frame_format','can_fd_brs','sync_method','retry_limit','retransmission_enabled'} & fields.keys()
    for key in ('arbitration_bitrate','data_bitrate','can_xl_priority_id','can_xl_acceptance_field',
                'can_xl_sdt','can_xl_vcid','can_xl_phy','can_xl_mode_switching','sample_point_percent'):
        assert 'default' not in fields[key]
    assert profile['physical_layer_profile_id']=='CAN_XL_PHY_EXPLICIT'
    assert profile['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.validate_parameters('can_xl',{'arbitration_bitrate':500000})['status']=='UNVERIFIED'
    assert registry.validate_parameters('can_xl',{'arbitration_bitrate':500000,'data_bitrate':25000000})['status']=='VALID'


def test_can_xl_dlc_is_length_minus_one_and_priority_is_not_address():
    base = {'arbitration_bitrate':500000,'data_bitrate':10000000,
            'can_xl_priority_id':1,'can_xl_acceptance_field':4294967295,'can_xl_sdt':255,'can_xl_vcid':255}
    for length in (1,8,9,12,16,64,65,1024,2048):
        assert registry.validate_parameters('can_xl',{**base,'payload_bytes':length,'can_xl_dlc':length-1})['status']=='VALID'
        assert registry.validate_parameters('can_xl',{**base,'payload_bytes':length,'can_xl_dlc':length})['status']=='INVALID'
    for patch in ({'payload_bytes':0},{'can_xl_priority_id':2048},{'can_xl_acceptance_field':4294967296},
                  {'can_xl_sdt':256},{'can_xl_vcid':256},{'can_xl_fcrc_bits':21},
                  {'can_xl_pcrc_bits':17},{'can_fd_dlc':9},{'can_identifier':1},
                  {'can_xl_mode_switching':True,'can_xl_phy':'CAN_HS'}):
        assert registry.validate_parameters('can_xl',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('can_xl',{**base,'can_xl_phy':'CAN_SIC_XL','can_xl_mode_switching':True})['status']=='VALID'
    assert registry.validate_parameters('can_fd',{'arbitration_bitrate':500000,'data_bitrate':2000000,'can_xl_priority_id':1})['status']=='INVALID'


def test_can_xl_explicit_xcan_clock_shared_prescaler_and_pwm_functional_values():
    base = {'arbitration_bitrate':500000,'data_bitrate':10000000,'can_controller_profile':'X_CAN_3_9',
            'can_clock_hz':80000000,'can_prescaler':1,'can_tseg1_tq':127,'can_tseg2_tq':32,'can_sjw_tq':4,
            'sample_point_percent':80,'can_xl_data_prescaler':1,'can_xl_data_tseg1_tq':5,'can_xl_data_tseg2_tq':2,
            'can_xl_data_sample_point_percent':75,'can_xl_data_sjw_tq':1,
            'can_xl_phy':'CAN_SIC_XL','can_xl_mode_switching':True,
            'can_xl_pwm_short_clocks':1,'can_xl_pwm_long_clocks':2,'can_xl_pwm_offset_clocks':2}
    assert registry.validate_parameters('can_xl',base)['status']=='VALID'
    for patch in ({'can_prescaler':33},{'can_tseg1_tq':513},{'can_tseg2_tq':129},
                  {'can_xl_data_prescaler':2},{'can_xl_data_tseg1_tq':257},{'can_xl_data_tseg2_tq':1},
                  {'can_xl_data_sjw_tq':3},{'can_xl_data_sample_point_percent':80},
                  {'can_xl_pwm_offset_clocks':3},{'can_xl_pwm_long_clocks':65},
                  {'can_controller_profile':'M_CAN_3_3_1'}):
        assert registry.validate_parameters('can_xl',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('can_xl',{'arbitration_bitrate':500000,'data_bitrate':25000000,'can_controller_profile':'X_CAN_3_9'})['status']=='INVALID'
    assert registry.validate_parameters('can_xl',{'arbitration_bitrate':500000,'data_bitrate':10000000,'can_xl_transceiver_max_bps':8000000})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('can_xl'),ids=lambda field:'can_xl/'+field['key'])
def test_every_can_xl_parameter_has_separate_type_options_and_bounds(field):
    base = {'arbitration_bitrate':500000,'data_bitrate':10000000}
    value = field.get('default',field.get('options',[None])[0] if field.get('options') else
                      False if field['type']=='boolean' else field.get('min',0))
    if field['key']=='can_xl_transceiver_max_bps':
        base['data_bitrate']=value
    assert registry.validate_parameters('can_xl',{**base,field['key']:value})['status']=='VALID'
    wrong = 'invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('can_xl',{**base,field['key']:wrong})['status']=='INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('can_xl',{**base,field['key']:field['min']-1})['status']=='INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('can_xl',{**base,field['key']:field['max']+1})['status']=='INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('can_xl',{**base,field['key']:option})['status']=='VALID'


def test_can_xl_sql_preserves_confirmed_native_fields_and_bad_edits_do_not_replace_them():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'arbitration_bitrate':500000,'data_bitrate':10000000,'can_xl_priority_id':14,
              'can_xl_acceptance_field':4000000000,'can_xl_vcid':4,'can_xl_sdt':5,
              'payload_bytes':1024,'can_xl_dlc':1023,'can_xl_phy':'CAN_SIC_XL','can_xl_mode_switching':True}
    parameters = {'technology':'can_xl',**values,'technology_parameters':{'can_xl':{'values':values,
        'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['can_xl']['values']['can_xl_dlc']=1024
    bad['technology_parameters']['can_xl']['provenance']['can_xl_dlc']['value']=1024
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_can_fd_defaults_keep_optional_brs_and_actual_hardware_rates_separate():
    fields = {item['key']:item for item in registry.parameter_fields('can_fd')}
    assert registry.parameter_defaults_review('can_fd')['values']=={}
    assert registry.profile('can_fd')['default_bitrate'] is None
    assert registry.profile('can_fd')['domain']=='generic_networking'
    assert not {'arbitration_bitrate','data_bitrate'} & _parameter_defaults('can_fd').keys()
    assert fields['can_fd_brs']['default'] is False
    assert fields['can_fd_revision']['default']=='ISO_2015_2024'
    assert fields['can_frame_type']['options']==['DATA']
    assert 'default' not in fields['sample_point_percent'] and 'default' not in fields['can_fd_data_sample_point_percent']
    assert not {'qos_priority','retry_limit','sync_method'} & fields.keys()
    assert registry.validate_parameters('can_fd',{'arbitration_bitrate':500000,'can_fd_brs':False})['status']=='VALID'
    assert registry.validate_parameters('can_fd',{'arbitration_bitrate':500000,'can_fd_brs':True})['status']=='UNVERIFIED'
    # No generic8M ceiling borrowed from an unspecified transceiver.
    values = {'arbitration_bitrate':500000,'data_bitrate':10000000}
    assert registry.validate_parameters('can_fd',values)['status']=='VALID'
    assert registry.validate_parameters('can_fd',{**values,'can_fd_transceiver_max_bps':8000000})['status']=='INVALID'


def test_can_fd_dlc_padding_crc_and_actual_esi_dependencies():
    from backend.communication.technologies.catalog import CAN_FD_DATA_LENGTHS
    base = {'arbitration_bitrate':500000,'data_bitrate':2000000,'can_fd_brs':True}
    for dlc,length in enumerate(CAN_FD_DATA_LENGTHS):
        values = {**base,'can_fd_dlc':dlc,'can_fd_wire_data_bytes':length,'payload_bytes':length,
                  'can_fd_crc_bits':17 if length<=16 else 21}
        assert registry.validate_parameters('can_fd',values)['status']=='VALID'
        assert registry.validate_parameters('can_fd',{**values,'payload_bytes':length+1})['status']=='INVALID'
        assert registry.validate_parameters('can_fd',{**values,'can_fd_crc_bits':21 if length<=16 else 17})['status']=='INVALID'
    assert registry.validate_parameters('can_fd',{**base,'payload_bytes':9,'can_fd_wire_data_bytes':12,'can_fd_dlc':9})['status']=='VALID'
    for patch in ({'can_fd_wire_data_bytes':9},{'can_frame_type':'REMOTE'},
                  {'can_fd_dlc':15,'can_fd_wire_data_bytes':48},
                  {'can_error_state':'ERROR_ACTIVE','can_fd_error_passive':True},
                  {'can_error_state':'ERROR_PASSIVE','can_fd_error_passive':False},
                  {'can_frame_format':'BASE_11','can_identifier':2048}):
        assert registry.validate_parameters('can_fd',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('can',{'bitrate':500000,'can_fd_brs':True})['status']=='INVALID'


def test_can_fd_actual_two_phase_timing_and_mcan_tdc_constraints():
    base = {'arbitration_bitrate':500000,'data_bitrate':2000000,'can_fd_brs':True,
            'can_clock_hz':8000000,'can_controller_profile':'M_CAN_3_3_1',
            'can_prescaler':1,'can_tseg1_tq':11,'can_tseg2_tq':4,'sample_point_percent':75,
            'can_fd_data_prescaler':1,'can_fd_data_tseg1_tq':1,'can_fd_data_tseg2_tq':2,
            'can_fd_data_sample_point_percent':50,'can_fd_data_sjw_tq':1,
            'can_fd_tdc_enabled':True,'can_fd_mcan_delay_mtq':8,'can_fd_mcan_tdco_mtq':2,'can_fd_mcan_ssp_mtq':10}
    assert registry.validate_parameters('can_fd',base)['status']=='VALID'
    for patch in ({'can_fd_data_sample_point_percent':75},{'can_fd_data_prescaler':3},
                  {'can_fd_data_sjw_tq':3},{'can_fd_data_tseg1_tq':33},
                  {'can_fd_data_tseg2_tq':1},{'can_fd_mcan_ssp_mtq':11},
                  {'can_fd_mcan_delay_mtq':22,'can_fd_mcan_ssp_mtq':24}):
        assert registry.validate_parameters('can_fd',{**base,**patch})['status']=='INVALID',patch
    assert registry.validate_parameters('can_fd',{'arbitration_bitrate':500000,'data_bitrate':250000,'can_controller_profile':'M_CAN_3_3_1'})['status']=='INVALID'


@pytest.mark.parametrize('field',registry.parameter_fields('can_fd'),ids=lambda field:'can_fd/'+field['key'])
def test_every_can_fd_parameter_has_its_own_type_options_and_bounds(field):
    base = {'arbitration_bitrate':500000,'data_bitrate':2000000}
    value = field.get('default',field.get('options',[None])[0] if field.get('options') else
                      False if field['type']=='boolean' else field.get('min',0))
    if field['key']=='can_fd_transceiver_max_bps':
        base['data_bitrate']=value  # The tested minimum capability must cover the explicitly configured phase.
    assert registry.validate_parameters('can_fd',{**base,field['key']:value})['status']=='VALID'
    wrong = 'invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('can_fd',{**base,field['key']:wrong})['status']=='INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('can_fd',{**base,field['key']:field['min']-1})['status']=='INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('can_fd',{**base,field['key']:field['max']+1})['status']=='INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('can_fd',{**base,field['key']:option})['status']=='VALID'


def test_can_fd_capacity_brs_and_padding_do_not_use_faster_unconfirmed_phases():
    from backend.engineering.capacity.calculators import estimate_frame,can_frame_time_bound_ms
    base = {'arbitration_bitrate':500000,'data_bitrate':2000000}
    slow = estimate_frame('CAN_FD',9,{**base,'can_fd_brs':False})
    switched = estimate_frame('CAN_FD',9,{**base,'can_fd_brs':True})
    unknown = estimate_frame('CAN_FD',9,base)
    assert slow.frame_bits==240 and unknown.transmission_time_s==slow.transmission_time_s
    assert switched.transmission_time_s<slow.transmission_time_s
    assert estimate_frame('CAN_FD',9,{**base,'can_fd_dlc':15}).frame_bits==760
    assert estimate_frame('CAN_FD',9,{'arbitration_bitrate':500000,'can_fd_brs':False}).transmission_time_available
    assert not estimate_frame('CAN_FD',9,{'arbitration_bitrate':500000,'can_fd_brs':True}).transmission_time_available
    assert can_frame_time_bound_ms('CAN_FD',9,{'arbitration_bitrate':500000,'can_fd_brs':False})>0
    for patch in ({'can_fd_wire_data_bytes':8},{'can_fd_dlc':16},{'can_fd_dlc':9,'can_fd_wire_data_bytes':64}):
        with pytest.raises(ValueError):
            estimate_frame('CAN_FD',9,{**base,**patch})
    values = {'technology':'can_fd','arbitration_bitrate':500000,'can_fd_brs':False}
    assert parameters_for_protocol('can_fd',values,confirmed_parameters=values)['_rate_evidenced']
    assert not parameters_for_protocol('can_fd',{**values,'can_fd_brs':True},confirmed_parameters={**values,'can_fd_brs':True})['_rate_evidenced']


def test_can_fd_brs_and_wire_length_storage_preserve_actual_values(tmp_path):
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'arbitration_bitrate':500000,'can_fd_brs':False,'can_fd_dlc':9,'can_fd_wire_data_bytes':12,'payload_bytes':9}
    group = {'values':values,'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}
    parameters = {'technology':'can_fd',**values,'technology_parameters':{'can_fd':group}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['can_fd']['values']['can_fd_wire_data_bytes']=8
    bad['technology_parameters']['can_fd']['provenance']['can_fd_wire_data_bytes']['value']=8
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters
    config = SimulationService().prepare_config({'technology':'can_fd','arbitration_bitrate':500000,'can_fd_brs':False},tmp_path)
    assert config['parameters']['can_fd_brs'] is False


def test_registered_can_timing_consumers_receive_ide_brs_and_wire_length():
    model = registry.resolve_stack(('can_fd',))['timing_model']
    no_switch = model.transmission_time_us(9,arbitration_bitrate=500000,can_fd_brs=False,can_fd_dlc=9)
    switched = model.transmission_time_us(9,arbitration_bitrate=500000,data_bitrate=2000000,can_fd_brs=True,can_fd_dlc=9)
    assert no_switch==480 and switched<no_switch
    calculator = registry.resolve_stack(('can_fd',))['load_calculator']
    result = calculator.calculate(payload_bytes=9,cycle_ms=100,arbitration_bitrate=500000,can_fd_brs=False,can_fd_dlc=9)
    assert result['transmission_time_us']==480
    assert model.transmission_time_us(9,arbitration_bitrate=500000,can_fd_brs=False,can_fd_dlc=15)>no_switch
    with pytest.raises(ValueError):
        model.transmission_time_us(9,arbitration_bitrate=500000,can_fd_brs=False,can_fd_dlc=8)
    can = registry.resolve_stack(('can',))['timing_model']
    assert can.transmission_time_us(8,500000,can_frame_format='BASE_11')<can.transmission_time_us(8,500000,can_frame_format='EXTENDED_29')
    with pytest.raises(ValueError,match='not applicable'):
        registry.resolve_stack(('lin',))['timing_model'].transmission_time_us(8,19200,can_fd_brs=False)


def test_can_aerospace_separates_body_header_lower_can_and_example_rates():
    profile = registry.profile('can_aerospace')
    fields = {item['key']:item for item in registry.parameter_fields('can_aerospace')}
    assert profile['max_payload_bytes'] == 4 and profile['overhead_bytes'] == 4
    assert registry.parameter_defaults_review('can_aerospace')['values'] == {}
    assert profile['default_bitrate'] is None and 'default' not in fields['bitrate']
    assert fields['payload_bytes']['max'] == 4 and 'default' not in fields['payload_bytes']
    assert fields['can_frame_type']['options'] == ['DATA']
    assert fields['canas_byte_order']['default'] == 'BIG_ENDIAN'
    assert fields['canas_response_deadline_ms']['default'] == 100
    assert 'default' not in fields['canas_node_id'] and 'default' not in fields['canas_response_bound_ms']
    assert not {'qos_priority','sync_method','retry_limit','data_bitrate'} & fields.keys()
    assert profile['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_can_aerospace_header_type_lengths_and_identifier_priority_groups():
    base = {'bitrate':500000,'can_frame_type':'DATA','can_frame_format':'BASE_11',
            'can_identifier':304,'canas_base_identifier':304,'canas_redundancy_level':0,
            'canas_message_class':'NOD','canas_distribution_id':0,'canas_data_type':2,
            'canas_node_id':1,'payload_bytes':4,'can_dlc':8}
    assert registry.validate_parameters('can_aerospace',base)['status'] == 'VALID'
    for patch in ({'payload_bytes':8},{'can_dlc':4},{'can_frame_type':'REMOTE'},
                  {'canas_data_type':9},{'canas_data_type':32},{'canas_node_id':256},
                  {'canas_message_class':'NSH'},{'canas_redundancy_level':1},
                  {'canas_ids_supported':False},{'canas_distribution_id':1},{'canas_response_bound_ms':101},
                  {'canas_byte_order':'LITTLE_ENDIAN'},{'canas_service_channel':36},
                  {'canas_nod_service_code_used':False,'canas_service_code_octet':1}):
        assert registry.validate_parameters('can_aerospace',{**base,**patch})['status'] == 'INVALID',patch
    assert registry.validate_parameters('can_aerospace',{**base,'can_frame_format':'EXTENDED_29',
        'canas_redundancy_level':1,'can_identifier':65840})['status'] == 'VALID'
    assert registry.validate_parameters('can_aerospace',{**base,'canas_data_type':0,'payload_bytes':0,'can_dlc':4})['status'] == 'VALID'
    assert registry.validate_parameters('can_aerospace',{**base,'canas_data_type':100})['status'] == 'VALID'
    for data_type,length in {0:0,2:4,6:2,9:1,12:4,18:2,21:4,23:1,24:2,25:4,26:3,29:3,30:4,31:4}.items():
        values = {**base,'canas_data_type':data_type,'payload_bytes':length,'can_dlc':length+4}
        assert registry.validate_parameters('can_aerospace',values)['status'] == 'VALID'
    clock = {**base,'can_controller_profile':'M_CAN_3_3_1','can_clock_hz':8000000,
             'can_prescaler':1,'can_tseg1_tq':11,'can_tseg2_tq':4,'sample_point_percent':75}
    assert registry.validate_parameters('can_aerospace',clock)['status'] == 'VALID'
    assert registry.validate_parameters('can_aerospace',{**clock,'sample_point_percent':87.5})['status'] == 'INVALID'
    assert registry.validate_parameters('can',{'bitrate':500000,'canas_node_id':1})['status'] == 'INVALID'


@pytest.mark.parametrize('kind,channel,role,identifier',[
    ('NSH',0,'REQUEST',128),('NSH',35,'RESPONSE',199),
    ('NSL',100,'REQUEST',2000),('NSL',115,'RESPONSE',2031)])
def test_can_aerospace_service_channel_uses_its_own_identifier_pair(kind,channel,role,identifier):
    values = {'bitrate':125000,'canas_message_class':kind,'canas_distribution_id':0,
              'canas_service_channel':channel,'canas_service_role':role,
              'canas_base_identifier':identifier,'can_identifier':identifier,'canas_redundancy_level':0}
    assert registry.validate_parameters('can_aerospace',values)['status'] == 'VALID'
    assert registry.validate_parameters('can_aerospace',{**values,'canas_base_identifier':identifier-1})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('can_aerospace'), ids=lambda field:'can_aerospace/'+field['key'])
def test_every_can_aerospace_parameter_has_its_individual_type_options_and_bounds(field):
    value = field.get('default',field.get('options',[None])[0] if field.get('options') else
                      True if field['type']=='boolean' else field.get('min',0))
    base = {} if field['key']=='bitrate' else {'bitrate':125000}
    assert registry.validate_parameters('can_aerospace',{**base,field['key']:value})['status']=='VALID'
    wrong = 'invalid' if field['type']=='number' else 1
    assert registry.validate_parameters('can_aerospace',{**base,field['key']:wrong})['status']=='INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('can_aerospace',{**base,field['key']:field['min']-1})['status']=='INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('can_aerospace',{**base,field['key']:field['max']+1})['status']=='INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('can_aerospace',{**base,field['key']:option})['status']=='VALID'


def test_can_aerospace_review_storage_preserves_header_and_source_identity():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate':125000,'canas_node_id':1,'canas_data_type':9,'payload_bytes':1,'can_dlc':5,
              'canas_response_bound_ms':80,'canas_ids_supported':True}
    group = {'values':values,'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}
    parameters = {'technology':'can_aerospace',**values,'technology_parameters':{'can_aerospace':group}}
    service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['can_aerospace']['values']['canas_data_type']=2
    bad['technology_parameters']['can_aerospace']['provenance']['canas_data_type']['value']=2
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters']==parameters


def test_can_cc_defaults_do_not_borrow_canopen_or_can_fd_profiles():
    fields = {item['key']: item for item in registry.parameter_fields('can')}
    assert registry.profile('can')['domain'] == 'generic_networking'
    assert registry.profile('can')['default_bitrate'] is None
    assert registry.parameter_defaults_review('can')['values'] == {}
    assert 'bitrate' not in _parameter_defaults('can')
    assert 'default' not in fields['bitrate'] and 'default' not in fields['sample_point_percent']
    assert fields['can_phy']['default'] == 'HIGH_SPEED'
    assert fields['retransmission_enabled']['default'] is True
    assert 'default' not in fields['can_identifier'] and fields['payload_bytes']['min'] == 0
    assert not {'qos_priority','sync_method','retry_limit','data_bitrate','arbitration_bitrate'} & fields.keys()
    for patch in ({'data_bitrate': 2000000}, {'bitrate': 1000001}, {'retransmission_enabled': False},
                  {'can_identifier': 536870912}, {'can_dlc': 9}, {'payload_bytes': 9},
                  {'bacnet_udp_port': 47808}, {'ble_tx_phy': 'LE_1M'}):
        assert registry.validate_parameters('can', {'bitrate': 10000, **patch})['status'] == 'INVALID', patch
    # Neither 1 bit/s nor 5 kbit/s is a proposed operating default; no unsupported CANopen minimum.
    assert registry.validate_parameters('can', {'bitrate': 5000})['status'] == 'VALID'


def test_can_cc_identifier_rtr_and_controller_timing_dependencies():
    base = {'bitrate': 500000, 'can_clock_hz': 8000000, 'can_prescaler': 1,
            'can_tseg1_tq': 11, 'can_tseg2_tq': 4, 'can_sjw_tq': 4,
            'sample_point_percent': 75, 'can_controller_profile': 'M_CAN_3_3_1',
            'can_frame_type': 'DATA', 'can_frame_format': 'BASE_11',
            'can_identifier': 2047, 'can_dlc': 8, 'payload_bytes': 8}
    assert registry.validate_parameters('can', base)['status'] == 'VALID'
    for patch in ({'can_identifier': 2048}, {'can_frame_type': 'REMOTE'}, {'can_dlc': 7},
                  {'sample_point_percent': 87.5}, {'can_clock_hz': 16000000}, {'can_prescaler': 2},
                  {'can_sjw_tq': 5}, {'can_tseg1_tq': 1}, {'can_tseg2_tq': 129}):
        assert registry.validate_parameters('can', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('can', {**base, 'can_frame_format': 'EXTENDED_29', 'can_identifier': 536870911})['status'] == 'VALID'
    assert registry.validate_parameters('can', {**base, 'can_frame_type': 'REMOTE', 'payload_bytes': 0})['status'] == 'VALID'
    assert registry.validate_parameters('can', {'bitrate': 10000, 'can_controller_profile': 'DEVICE_SPECIFIC', 'can_prescaler': 1024})['status'] == 'VALID'
    for patch in ({'can_error_state': 'ERROR_ACTIVE', 'can_tx_error_count': 128},
                  {'can_error_state': 'ERROR_ACTIVE', 'can_rx_error_count': 128},
                  {'can_error_state': 'BUS_OFF', 'can_tx_error_count': 255},
                  {'can_error_state': 'ERROR_PASSIVE', 'can_tx_error_count': 256},
                  {'can_error_state': 'ERROR_PASSIVE', 'can_tx_error_count': 0, 'can_rx_error_count': 0}):
        assert registry.validate_parameters('can', {'bitrate': 10000, **patch})['status'] == 'INVALID', patch


@pytest.mark.parametrize('field', registry.parameter_fields('can'), ids=lambda field: 'can/' + field['key'])
def test_every_can_cc_field_uses_its_own_types_and_bounds(field):
    value = field.get('default', field.get('options', [None])[0] if field.get('options') else field.get('min', 0))
    base = {} if field['key'] == 'bitrate' else {'bitrate': 10000}
    assert registry.validate_parameters('can', {**base, field['key']: value})['status'] == 'VALID'
    wrong = 'invalid' if field['type'] == 'number' else 1
    assert registry.validate_parameters('can', {**base, field['key']: wrong})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('can', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('can', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('can', {**base, field['key']: option})['status'] == 'VALID'


def test_can_cc_frame_bound_accounts_for_ide_and_remote_requests():
    from backend.engineering.capacity.calculators import estimate_frame
    base = {'bitrate': 500000, 'can_frame_format': 'BASE_11'}
    assert estimate_frame('CAN', 8, base).frame_bits == 135
    extended = estimate_frame('CAN', 8, {**base, 'can_frame_format': 'EXTENDED_29'})
    assert extended.frame_bits == 160
    assert estimate_frame('CAN', 8, {'bitrate': 500000}).frame_bits == extended.frame_bits
    remote = estimate_frame('CAN', 0, {**base, 'can_frame_type': 'REMOTE', 'can_dlc': 8})
    assert remote.frame_bits == 55 and remote.payload_bytes == 0
    for payload, parameters in ((9, base), (8, {**base, 'can_frame_type': 'REMOTE'})):
        with pytest.raises(ValueError):
            estimate_frame('CAN', payload, parameters)
    assert not estimate_frame('CAN', 8, {'_rate_evidenced': False, 'bitrate': 500000}).transmission_time_available


def test_can_cc_confirmed_device_values_survive_rejected_parameter_edits():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 500000, 'can_frame_format': 'EXTENDED_29', 'can_frame_type': 'DATA',
              'can_identifier': 123456, 'can_dlc': 8, 'payload_bytes': 8, 'can_ack_receiver_count': 1}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key,value in values.items()}}
    parameters = {'technology': 'can', **values, 'technology_parameters': {'can': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['can']['values']['can_frame_format'] = 'BASE_11'
    bad['technology_parameters']['can']['provenance']['can_frame_format']['value'] = 'BASE_11'
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_http_schema_is_registered_profile_schema_for_every_technology():
    # Detect future API-local definitions that silently replace the canonical schema.
    for profile in registry.profiles():
        expected = [{**spec, 'key': PARAMETER_UI_ALIASES.get(key, key)}
                    for key, spec in profile['parameter_schema'].items() if spec.get('label')]
        assert SimulationService._parameter_schema(profile['id'], profile) == expected
        assert all(field.get('parameter_origin') and field.get('source') for field in expected)


def test_5g_has_no_historical_peak_rate_as_a_standard_default():
    fields = registry.parameter_fields('5g')
    rate = next(field for field in fields if field['key'] == 'bitrate')
    assert 'default' not in rate
    assert registry.parameter_defaults_review('5g')['values'] == {}
    assert 'bitrate' not in _parameter_defaults('5g')
    assert rate['default_review']['source'].startswith('https://www.etsi.org/')
    device = [field for field in fields if field['key'].startswith('nr_')]
    assert len(device) == 9
    assert all(field['parameter_origin'] == 'DEVICE_CONFIGURATION' and 'default' not in field for field in device)
    assert registry.profile('5g')['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert registry.profile('5g')['default_bitrate'] is None
    assert registry.profile('5g')['max_payload_bytes'] is None
    assert 'max' not in next(field for field in fields if field['key'] == 'payload_bytes')
    assert not {'arbitration_bitrate', 'data_bitrate', 'sample_point_percent', 'duplex', 'mtu_bytes', 'vlan_id'} & {field['key'] for field in fields}


def test_5g_general_analysis_controls_are_explicit_nis_scenarios():
    fields = registry.parameter_fields('5g')
    for field in fields:
        if field['parameter_origin'] == 'NIS_SCENARIO':
            assert field['source_revision'] == 'NIS_SCENARIO_POLICY_V1'
            assert not field['required']
            assert field['default_status'] in {'PROPOSED', 'UNKNOWN'}


def test_adc_does_not_require_bus_or_frame_parameters():
    profile = registry.profile('adc')
    assert profile['max_payload_bytes'] is None
    assert profile['default_bitrate'] is None
    assert profile['capacity_evidence']['status'] == 'NOT_APPLICABLE'
    assert registry.parameter_defaults_review('adc')['values'] == {}
    fields = registry.parameter_fields('adc')
    assert fields and all(field['parameter_origin'] == 'NIS_SCENARIO' and not field['required'] for field in fields)
    names = {field['key'] for field in fields}
    assert not {'bitrate', 'payload_bytes', 'mtu_bytes', 'queue_size', 'queue_policy',
                'target_bus_load_percent', 'retry_limit', 'sync_method'} & names
    assert registry.validate_parameters('adc', {})['status'] == 'VALID'
    assert registry.validate_parameters('adc', {'bitrate': 500_000})['status'] == 'INVALID'
    assert registry.validate_parameters('adc', {'queue_size': 256})['status'] == 'INVALID'
    local = profile['local_timing_schema']
    assert {item['key'] for item in local} == {'sample_bound_ms', 'conversion_bound_ms'}
    assert all('default' not in item and item['default_status'] == 'UNKNOWN' and item['source'].startswith('https://') for item in local)


def test_adc_device_bounds_require_source_and_actual_numeric_values():
    valid = {'technology': 'adc', 'sample_bound_ms': 0.01, 'conversion_bound_ms': 0.005,
             'confirmed': True, 'source': 'Selected ADC datasheet, timing table'}
    assert registry.validate_parameters('adc', {'local_timing_evidence': valid})['status'] == 'VALID'
    for patch in ({'source': ''}, {'conversion_bound_ms': None}, {'sample_bound_ms': -1},
                  {'sample_bound_ms': True}, {'sample_bound_ms': float('inf')}, {'technology': 'can'}):
        assert registry.validate_parameters('adc', {'local_timing_evidence': {**valid, **patch}})['status'] == 'INVALID'
    assert registry.validate_parameters('adc', {'local_timing_evidence': {'confirmed': False}})['status'] == 'VALID'


def test_adc_device_evidence_storage_rejects_invalid_update_and_preserves_previous_bounds():
    from backend.engineering.repository import create_object, update_object, get_object
    node = create_object('HardwareNode', {'name': 'MeasurementController', 'device_type': 'EmbeddedController'})
    local = {'technology': 'adc', 'sample_bound_ms': 0.01, 'conversion_bound_ms': 0.005,
             'confirmed': True, 'source': 'Selected device datasheet'}
    port = create_object('HardwareNetworkInterface', {'name': 'AnalogueInput', 'technology': 'ADC',
        'hardware_node_id': str(node['id']), 'capabilities': {'local_timing_evidence': local}})
    assert port['capabilities']['local_timing_evidence'] == local
    with pytest.raises(ValueError, match='LOCAL_TIMING_EVIDENCE_INVALID'):
        update_object('HardwareNetworkInterface', str(port['id']), {'expected_version': port['version'],
            'capabilities': {'local_timing_evidence': {**local, 'conversion_bound_ms': -1}}})
    assert get_object('HardwareNetworkInterface', str(port['id']))['capabilities']['local_timing_evidence'] == local


def test_global_parameter_save_rejects_foreign_fields_without_blocking_partial_drafts():
    with pytest.raises(ValueError, match='NOT_APPLICABLE'):
        WorkflowStatusService._validate_parameter_reviews({'technology': 'can', 'bitrate': 10_000, 'nr_direction': 'UL'}, {})
    WorkflowStatusService._validate_parameter_reviews({'technology': '5g', 'nr_direction': 'UL'}, {})
    WorkflowStatusService._validate_parameter_reviews({'technology': 'adc', 'cycle_ms': 10}, {})


def test_unchanged_retired_group_is_preserved_but_not_accepted_as_an_edited_group():
    old = {'technology_parameters': {'adc': {'values': {'queue_size': 256}, 'provenance': {
        'queue_size': {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': 256}}}}}
    WorkflowStatusService._validate_parameter_reviews(old, old)
    with pytest.raises(ValueError, match='Fremde Parameter'):
        WorkflowStatusService._validate_parameter_reviews(old, {})


def test_afdx_uses_its_own_link_limits_and_virtual_link_configuration():
    review = registry.parameter_defaults_review('afdx')
    assert review['values'] == {'bitrate_bps': 100_000_000}
    assert review['basis'] == 'LITERATURE_DEFAULT'
    base = {'bitrate': 100_000_000, 'duplex': 'FULL', 'payload_bytes': 17, 'afdx_lmax_frame_bytes': 64}
    assert registry.validate_parameters('afdx', base)['status'] == 'VALID'
    for patch in ({'bitrate': 1_000_000_000}, {'duplex': 'HALF'}, {'afdx_bag_ms': '3'},
                  {'afdx_lmax_frame_bytes': 63}, {'payload_bytes': 18}, {'payload_bytes': 0},
                  {'afdx_jitter_bound_us': 501}, {'afdx_vl_id': 1.5}, {'mtu_bytes': 65535}, {'sync_method': 'PTP'}):
        assert registry.validate_parameters('afdx', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.profile('afdx')['capacity_evidence']['status'] == 'MODEL_MISSING'


@pytest.mark.parametrize('field', registry.parameter_fields('afdx'), ids=lambda field: 'afdx/' + field['key'])
def test_every_afdx_form_field_validates_its_own_options_types_and_bounds(field):
    value = field.get('default', field.get('options', [None])[0] if field.get('options') else field.get('min', 0))
    base = {'bitrate': 100_000_000}
    assert registry.validate_parameters('afdx', {**base, field['key']: value})['status'] == 'VALID'
    assert registry.validate_parameters('afdx', {**base, field['key']: 'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('afdx', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('afdx', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('afdx', {**base, field['key']: option})['status'] == 'VALID'


def test_afdx_reviewed_virtual_link_storage_does_not_turn_into_capacity_evidence():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 100_000_000, 'afdx_bag_ms': '8', 'afdx_lmax_frame_bytes': 1518,
              'afdx_vl_id': 10, 'afdx_redundancy': 'BOTH', 'payload_bytes': 1471}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': 'afdx', **values, 'technology_parameters': {'afdx': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['afdx']['values']['afdx_bag_ms'] = '3'
    bad['technology_parameters']['afdx']['provenance']['afdx_bag_ms']['value'] = '3'
    with pytest.raises(ValueError, match='OUT_OF_RANGE'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters
    assert registry.profile('afdx')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_amqp_native_defaults_are_not_can_or_ethernet_message_limits():
    fields = {item['key']: item for item in registry.parameter_fields('amqp')}
    expected = {'amqp_version': '1.0', 'amqp_max_frame_size_bytes': 4294967295,
                'amqp_channel_max': 65535, 'amqp_idle_timeout_ms': 0,
                'amqp_sender_settle_mode': 'MIXED', 'amqp_receiver_settle_mode': 'FIRST',
                'amqp_incomplete_unsettled': False, 'amqp_message_priority': 4, 'amqp_durable': False,
                'amqp_max_message_size_bytes': '0'}
    assert {key: fields[key]['default'] for key in expected} == expected
    assert fields['amqp_max_frame_size_bytes']['min'] == 512
    assert 'default' not in fields['amqp_link_credit'] and 'default' not in fields['amqp_ttl_ms']
    assert 'max' not in fields['payload_bytes']
    assert registry.profile('amqp')['max_payload_bytes'] is None
    for value in ('0', '18446744073709551615'):
        assert registry.validate_parameters('amqp', {'bitrate': 10_000_000, 'amqp_max_message_size_bytes': value})['status'] == 'VALID'
    for value in ('-1', '1.5', '18446744073709551616', 18446744073709551615):
        assert registry.validate_parameters('amqp', {'bitrate': 10_000_000, 'amqp_max_message_size_bytes': value})['status'] == 'INVALID'
    assert registry.validate_parameters('amqp', {'bitrate': 10_000_000, 'payload_bytes': 100_000})['status'] == 'VALID'
    assert registry.validate_parameters('amqp', {'bitrate': 250_000})['status'] == 'INVALID'
    assert registry.validate_parameters('amqp', {'bitrate': 10_000_000, 'amqp_max_frame_size_bytes': 511})['status'] == 'INVALID'
    assert registry.validate_parameters('amqp', {'bitrate': 10_000_000, 'qos_priority': 3})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('amqp'), ids=lambda field: 'amqp/' + field['key'])
def test_every_amqp_field_uses_its_own_type_options_bounds(field):
    value = field.get('default', field.get('options', [None])[0] if field.get('options') else field.get('min', 0))
    base = {'bitrate': 10_000_000}
    assert registry.validate_parameters('amqp', {**base, field['key']: value})['status'] == 'VALID'
    wrong = 'invalid' if field['type'] == 'number' else 1 if field['type'] in {'boolean', 'select', 'text'} else None
    assert registry.validate_parameters('amqp', {**base, field['key']: wrong})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('amqp', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('amqp', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('amqp', {**base, field['key']: option})['status'] == 'VALID'


def test_standalone_requires_explicit_technology_and_distinguishes_missing_execution_model(tmp_path):
    with pytest.raises(ValueError, match='TECHNOLOGY_PROFILE_MISSING'):
        SimulationService().prepare_config({}, tmp_path)
    with pytest.raises(ValueError, match='DIRECT_IO_BINDING_REQUIRED'):
        SimulationService().prepare_config({'technology': 'adc'}, tmp_path)
    with pytest.raises(ValueError, match='TECHNOLOGY_EXECUTION_MODEL_MISSING'):
        SimulationService().prepare_config({'technology': 'amqp', 'bitrate': 10_000_000}, tmp_path)


def test_amqp_exact_limits_and_settlement_roundtrip_without_confirming_capacity():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 10_000_000, 'payload_bytes': 100_000, 'amqp_max_frame_size_bytes': 512,
              'amqp_max_message_size_bytes': '18446744073709551615', 'amqp_sender_settle_mode': 'MIXED'}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': 'amqp', **values, 'technology_parameters': {'amqp': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['amqp']['values']['amqp_channel_max'] = 65536
    bad['technology_parameters']['amqp']['provenance']['amqp_channel_max'] = {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': 65536}
    with pytest.raises(ValueError, match='OUT_OF_RANGE'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters
    assert registry.profile('amqp')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_arinc429_nominal_modes_are_not_tolerance_minima_or_continuous_ranges():
    review = registry.parameter_defaults_review('arinc429')
    assert review['values'] == {'bitrate_bps': 12500}
    assert review['basis'] == 'LOWEST_NOMINAL_MODE'
    assert _parameter_defaults('arinc429')['bitrate'] == 12500
    for rate in (12000, 12500, 14500, 99000, 100000, 101000):
        assert registry.validate_parameters('arinc429', {'bitrate': rate})['status'] == 'VALID'
    for rate in (11999, 14501, 50000, 98999, 101001):
        assert registry.validate_parameters('arinc429', {'bitrate': rate})['status'] == 'INVALID'
    assert registry.validate_parameters('arinc429', {'bitrate': 100000, 'arinc429_speed_mode': 'LOW'})['status'] == 'INVALID'
    assert registry.validate_parameters('arinc429', {'bitrate': 12500, 'arinc429_speed_mode': 'HIGH'})['status'] == 'INVALID'


def test_arinc429_word_fields_and_waveform_constraints_are_separate():
    base = {'bitrate': 12500, 'payload_bytes': 4, 'arinc429_sdi': 0, 'arinc429_ssm': 3, 'arinc429_data_bits': 19}
    assert registry.validate_parameters('arinc429', base)['status'] == 'VALID'
    for patch in ({'payload_bytes': 3}, {'arinc429_data_bits': 20}, {'arinc429_parity': 'EVEN'},
                  {'arinc429_gap_bit_times': 3.99}, {'arinc429_receiver_count': 21},
                  {'arinc429_label': 256}, {'arinc429_sdi': 1.5}, {'qos_priority': 3},
                  {'retry_limit': 1}, {'sync_method': 'PTP'}, {'arinc429_rise_time_us': 1.5}):
        assert registry.validate_parameters('arinc429', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('arinc429', {'bitrate': 100000, 'arinc429_fall_time_us': 10})['status'] == 'INVALID'
    assert registry.validate_parameters('arinc429', {'bitrate': 100000, 'arinc429_fall_time_us': 1.5})['status'] == 'VALID'
    assert registry.validate_parameters('arinc429', {'bitrate': 12500, 'arinc429_data_bits': 23})['status'] == 'VALID'
    assert registry.profile('arinc429')['capacity_evidence']['status'] == 'MODEL_MISSING'


@pytest.mark.parametrize('field', registry.parameter_fields('arinc429'), ids=lambda field: 'arinc429/' + field['key'])
def test_every_arinc429_parameter_validates_its_type_options_and_bounds(field):
    value = field.get('default', field.get('options', ['Transmitter'])[0] if field.get('options') or field['type'] == 'text' else field.get('min', 0))
    if field['key'] in {'arinc429_rise_time_us', 'arinc429_fall_time_us'}:
        value = 10  # Low-speed waveform; the high-speed lower bound is not valid here.
    base = {'bitrate': 12500}
    assert registry.validate_parameters('arinc429', {**base, field['key']: value})['status'] == 'VALID'
    wrong = 'invalid' if field['type'] == 'number' else 1
    assert registry.validate_parameters('arinc429', {**base, field['key']: wrong})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('arinc429', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('arinc429', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        option_base = {'bitrate': 100000 if field['key'] == 'arinc429_speed_mode' and option == 'HIGH' else 12500}
        assert registry.validate_parameters('arinc429', {**option_base, field['key']: option})['status'] == 'VALID'


def test_arinc429_low_speed_configuration_roundtrips_without_overwriting_other_profiles():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 12500, 'arinc429_speed_mode': 'LOW', 'payload_bytes': 4,
              'arinc429_gap_bit_times': 4, 'arinc429_label': 66, 'arinc429_parity': 'ODD',
              'arinc429_receiver_count': 2}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': 'arinc429', **values, 'technology_parameters': {'arinc429': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters


    bad = deepcopy(parameters)
    bad['technology_parameters']['arinc429']['values']['bitrate'] = 50000
    bad['technology_parameters']['arinc429']['provenance']['bitrate']['value'] = 50000
    with pytest.raises(ValueError, match='OUT_OF_RANGE'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters


def test_arinc429_standalone_adapter_preserves_native_channel_and_word_parameters(tmp_path):
    config = SimulationService().prepare_config({'technology': 'arinc429', 'bitrate': 12500,
        'arinc429_speed_mode': 'LOW', 'arinc429_gap_bit_times': 6, 'arinc429_label': 66,
        'payload_bytes': 4}, tmp_path)
    assert config['parameters']['technology'] == 'arinc429'
    assert config['networks'][0]['parameters']['arinc429_gap_bit_times'] == 6
    assert config['networks'][0]['parameters']['arinc429_speed_mode'] == 'LOW'
    assert config['communications'][0]['parameters']['arinc429_label'] == 66


def test_mstp_default_and_medium_are_distinct_from_ip_and_generic_serial():
    fields = {item['key']: item for item in registry.parameter_fields('bacnet_mstp')}
    assert registry.parameter_defaults_review('bacnet_mstp')['values'] == {'bitrate_bps': 9600}
    assert fields['mstp_frame_format']['default'] == 'CLASSIC'
    assert fields['mstp_max_master']['default'] == 127
    assert fields['mstp_max_info_frames']['default'] == 1
    assert fields['mstp_serial_format']['options'] == ['8N1']
    profile = registry.profile('bacnet_mstp')
    assert profile['physical_layer_profile_id'] == 'BACNET_MSTP_EIA485'
    assert profile['medium_access_model'] == 'TOKEN_PASSING'
    from backend.communication.technologies.core.physical import physical_profile, validate_physical_realization
    assert physical_profile('bacnet_mstp').duplex_mode == 'HALF_DUPLEX'
    invalid_physical = validate_physical_realization({'technology':'bacnet_mstp', 'topology':'STAR',
                                                     'conductors':['A','B'], 'pair_count':1, 'termination_count':2})
    assert 'PHYSICAL_TOPOLOGY_INVALID' in {item['code'] for item in invalid_physical['findings']}
    for patch in ({'bitrate': 10000000}, {'bitrate': 153600}, {'bitrate': 12345}, {'mstp_serial_format': '8E1'},
                  {'bacnet_udp_port': 47808}, {'mtu_bytes': 1500}, {'qos_priority': 3}, {'retry_limit': 3}):
        assert registry.validate_parameters('bacnet_mstp', {'bitrate': 9600, **patch})['status'] == 'INVALID', patch
    for rate in (9600,19200,38400,57600,76800,115200):
        assert registry.validate_parameters('bacnet_mstp', {'bitrate': rate})['status'] == 'VALID'


def test_mstp_role_frame_format_and_timer_dependencies_use_the_actual_profile():
    base = {'bitrate':9600,'mstp_frame_format':'CLASSIC','mstp_node_role':'MASTER',
            'mstp_mac_address':42,'mstp_max_master':42,'bacnet_max_apdu_bytes':480,
            'payload_bytes':480,'mstp_npdu_bytes':501,'mstp_frame_abort_bit_times':60}
    assert registry.validate_parameters('bacnet_mstp', base)['status'] == 'VALID'
    for patch in ({'mstp_mac_address':128}, {'mstp_max_master':41}, {'payload_bytes':481},
                  {'bacnet_max_apdu_bytes':481}, {'mstp_npdu_bytes':502}, {'mstp_npdu_bytes':481},
                  {'mstp_frame_abort_bit_times':961}, {'mstp_max_master_modifiable':False},
                  {'mstp_max_info_frames_modifiable':False,'mstp_max_info_frames':2}):
        assert registry.validate_parameters('bacnet_mstp', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('bacnet_mstp', {**base,'mstp_node_role':'SLAVE','mstp_mac_address':254})['status'] == 'VALID'
    assert registry.validate_parameters('bacnet_mstp', {**base,'mstp_node_role':'SLAVE','mstp_mac_address':255})['status'] == 'INVALID'
    assert registry.validate_parameters('bacnet_mstp', {**base,'mstp_frame_format':'EXTENDED','bacnet_max_apdu_bytes':1476,
            'payload_bytes':1476,'mstp_npdu_bytes':1497})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('bacnet_mstp'), ids=lambda field: 'bacnet_mstp/' + field['key'])
def test_every_mstp_field_validates_its_native_type_options_and_bounds(field):
    value = field.get('default', field.get('options', [False])[0] if field.get('options') or field['type'] == 'boolean' else field.get('min', 0))
    base = {'bitrate':9600}
    assert registry.validate_parameters('bacnet_mstp', {**base, field['key']:value})['status'] == 'VALID'
    assert registry.validate_parameters('bacnet_mstp', {**base, field['key']:'invalid' if field['type'] == 'number' else 1})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('bacnet_mstp', {**base,field['key']:field['min']-1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('bacnet_mstp', {**base,field['key']:field['max']+1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('bacnet_mstp', {**base,field['key']:option})['status'] == 'VALID'


def test_mstp_confirmed_values_roundtrip_and_foreign_ip_settings_are_rejected():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate':9600,'mstp_node_role':'SLAVE','mstp_mac_address':254,'mstp_frame_format':'CLASSIC',
              'bacnet_max_apdu_bytes':256,'payload_bytes':206,'mstp_npdu_bytes':208}
    group = {'values':values,'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}
    parameters = {'technology':'bacnet_mstp',**values,'technology_parameters':{'bacnet_mstp':group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['bacnet_mstp']['values']['bacnet_udp_port'] = 47808
    bad['technology_parameters']['bacnet_mstp']['provenance']['bacnet_udp_port'] = {'source':'USER_CONFIRMED','status':'CONFIRMED','value':47808}
    with pytest.raises(ValueError,match='NOT_APPLICABLE'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters
    assert registry.profile('bacnet_mstp')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_bluetooth_le_mandatory_phy_default_and_radio_profile_remain_industry_independent():
    from backend.communication.technologies.core.physical import physical_profile, validate_physical_realization
    fields = {field['key']:field for field in registry.parameter_fields('bluetooth_le')}
    assert registry.parameter_defaults_review('BLE')['values'] == {'bitrate_bps':1000000}
    assert registry.parameter_defaults_review('BLE')['basis'] == 'LOWEST_MANDATORY_PHY'
    assert fields['ble_tx_phy']['default'] == 'LE_1M'
    assert fields['ble_subrate_factor']['default'] == 1 and fields['ble_continuation_number']['default'] == 0
    assert fields['ble_ifs_us']['default'] == 150
    assert 'default' not in fields['ble_rx_phy'] and 'default' not in fields['ble_supervision_timeout_ms']
    assert fields['payload_bytes']['min'] == 0 and fields['payload_bytes']['max'] == 251 and 'default' not in fields['payload_bytes']
    assert not {'arbitration_bitrate','data_bitrate','mtu_bytes','duplex','sync_method','retry_limit','qos_priority'} & fields.keys()
    assert physical_profile('BLE').medium_type == 'RADIO'
    assert registry.profile('ble')['medium_access_model'] == 'CENTRAL_SCHEDULED_FREQUENCY_HOPPING'
    assert validate_physical_realization({'technology':'BLE','topology':'BUS','conductors':['CAN_H','CAN_L']})['status'] == 'INVALID'
    assert registry.profile('bluetooth_le')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_bluetooth_le_phy_capabilities_interval_grids_and_supervision_are_distinct():
    base = {'bitrate':1000000,'ble_tx_phy':'LE_1M','ble_interval_set':'BASELINE','ble_connection_interval_us':7500,
            'ble_subrate_factor':1,'ble_peripheral_latency':0,'ble_supervision_timeout_ms':100}
    assert registry.validate_parameters('ble', base)['status'] == 'VALID'
    for patch in ({'bitrate':2000000}, {'bitrate':500000}, {'ble_connection_interval_us':7600},
                  {'ble_connection_interval_us':1250}, {'ble_supervision_timeout_ms':101},
                  {'ble_peripheral_latency':6}, {'ble_subrate_factor':501}, {'ble_continuation_number':1}):
        assert registry.validate_parameters('ble', {**base,**patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('ble', {**base,'ble_connection_interval_us':50000})['status'] == 'INVALID'
    assert registry.validate_parameters('ble', {**base,'ble_connection_interval_us':50000,'ble_supervision_timeout_ms':110})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {**base,'ble_interval_set':'EXTENDED','ble_connection_interval_us':375})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {**base,'ble_interval_set':'EXTENDED','ble_connection_interval_us':375,'ble_short_intervals_supported':False})['status'] == 'INVALID'
    for phy,rate in (('LE_2M',2000000),('LE_CODED_S2',500000),('LE_CODED_S8',125000)):
        assert registry.validate_parameters('ble', {**base,'ble_tx_phy':phy,'bitrate':rate})['status'] == 'VALID'
        feature = 'ble_remote_2m_supported' if phy == 'LE_2M' else 'ble_remote_coded_supported'
        assert registry.validate_parameters('ble', {**base,'ble_tx_phy':phy,'bitrate':rate,feature:False})['status'] == 'INVALID'
    assert registry.validate_parameters('ble', {'bitrate':1000000,'ble_subrate_factor':2,'ble_peripheral_latency':250})['status'] == 'INVALID'


def test_bluetooth_le_data_lengths_and_timing_follow_actual_local_and_remote_features():
    base = {'bitrate':1000000,'payload_bytes':27,'ble_local_max_tx_octets':27,'ble_remote_max_rx_octets':27,
            'ble_dle_supported':False,'ble_coded_supported':False,'ble_cte_supported':False,'ble_local_max_tx_time_us':328}
    assert registry.validate_parameters('ble', base)['status'] == 'VALID'
    for patch in ({'payload_bytes':28},{'ble_local_max_tx_octets':28},{'ble_local_max_tx_time_us':329},
                  {'ble_supported_max_tx_octets':26}):
        assert registry.validate_parameters('ble', {**base,**patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('ble', {**base,'ble_dle_supported':True,'ble_local_max_tx_octets':251,
        'ble_remote_max_rx_octets':251,'payload_bytes':251,'ble_local_max_tx_time_us':2120})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {**base,'ble_coded_supported':True,'ble_local_max_tx_time_us':2704})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {**base,'ble_coded_supported':True,'ble_local_max_tx_time_us':2705})['status'] == 'INVALID'
    assert registry.validate_parameters('ble', {'bitrate':1000000,'payload_bytes':0})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {'bitrate':2000000,'ble_local_max_tx_octets':27,'ble_local_max_tx_time_us':2120})['status'] == 'VALID'


@pytest.mark.parametrize('field', registry.parameter_fields('bluetooth_le'), ids=lambda field:'bluetooth_le/'+field['key'])
def test_every_bluetooth_le_field_validates_type_bounds_and_options(field):
    value = field.get('default',field.get('options',[False])[0] if field.get('options') or field['type']=='boolean'
                      else 'actual-node' if field['type']=='text' else field.get('min',0))
    base = {'bitrate':1000000}
    if field['key'] == 'ble_connection_interval_us':
        value = 7500
    assert registry.validate_parameters('ble', {**base,field['key']:value})['status'] == 'VALID'
    assert registry.validate_parameters('ble', {**base,field['key']:'invalid' if field['type']=='number' else 1})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('ble', {**base,field['key']:field['min']-1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('ble', {**base,field['key']:field['max']+1})['status'] == 'INVALID'
    for option in field.get('options',[]):
        rate = {'LE_1M':1000000,'LE_2M':2000000,'LE_CODED_S2':500000,'LE_CODED_S8':125000}[option] if field['key']=='ble_tx_phy' else 1000000
        assert registry.validate_parameters('ble', {**base,'bitrate':rate,field['key']:option})['status'] == 'VALID'


def test_ble_actual_values_roundtrip_and_invalid_can_or_supervision_changes_preserve_them():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate':1000000,'ble_interval_set':'BASELINE','ble_connection_interval_us':50000,
              'ble_subrate_factor':1,'ble_peripheral_latency':0,'ble_supervision_timeout_ms':110,
              'ble_rx_phy':'LE_CODED_S8','ble_encryption_active':False}
    group = {'values':values,'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}
    parameters = {'technology':'bluetooth_le',**values,'technology_parameters':{'bluetooth_le':group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    for key,value in (('arbitration_bitrate',500000),('ble_supervision_timeout_ms',100)):
        bad = deepcopy(parameters)
        bad['technology_parameters']['bluetooth_le']['values'][key] = value
        bad['technology_parameters']['bluetooth_le']['provenance'][key] = {'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}
        with pytest.raises(ValueError):
            service.save_parameters(bad)
        assert service.get()['parameters'] == parameters


def test_bacnet_sc_has_own_transport_identity_security_and_timer_defaults():
    fields = {field['key']:field for field in registry.parameter_fields('bacnet_sc')}
    assert registry.profile('bacnet_sc')['default_bitrate'] is None
    assert registry.parameter_defaults_review('bacnet_sc')['rate_profile'] == 'ethernet'
    assert registry.parameter_defaults_review('bacnet_sc')['values'] == {'bitrate_bps':10000000}
    assert fields['sc_connect_wait_s']['default'] == 10
    assert fields['sc_tls_version']['default'] == '1.3'
    assert fields['sc_cipher_suite']['default'] == 'TLS_AES_128_GCM_SHA256'
    assert fields['sc_signature_algorithm']['default'] == 'ecdsa_secp256r1_sha256'
    assert fields['sc_key_exchange_group']['default'] == 'secp256r1'
    assert 'default' not in fields['sc_vmac'] and 'default' not in fields['sc_device_uuid']
    assert 'default' not in fields['sc_disconnect_wait_s']
    assert fields['payload_bytes']['max'] == 61325 and 'default' not in fields['payload_bytes']
    assert not {'bacnet_udp_port','bacnet_broadcast_role','bacnet_foreign_device_ttl_s','mstp_mac_address',
                'qos_priority','vlan_id','sync_method','retry_limit','arbitration_bitrate','data_bitrate'} & fields.keys()
    for patch in ({'bacnet_udp_port':47808},{'sc_mutual_tls_required':False}, {'sc_tls_version':'1.2'},
                  {'sc_websocket_subprotocol':'asn.bacnet.org'}, {'sc_vmac':'000000000000'},
                  {'sc_vmac':'FFFFFFFFFFFF'}, {'sc_bvlc_base_header_bytes':5}):
        assert registry.validate_parameters('bacnet_sc', {'bitrate':10000000,**patch})['status'] == 'INVALID', patch
    assert registry.profile('bacnet_sc')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_bacnet_sc_header_sizes_cap_peer_messages_without_using_ethernet_mtu():
    base = {'bitrate':10000000,'mtu_bytes':1500,'payload_bytes':6000,'bacnet_max_apdu_bytes':6000,
            'sc_npdu_bytes':6021,'sc_npci_header_bytes':21,'sc_bvlc_base_header_bytes':16,
            'sc_destination_options_bytes':0,'sc_data_options_bytes':4192,
            'sc_peer_max_npdu_bytes':6021,'sc_peer_max_bvlc_bytes':10229}
    assert registry.validate_parameters('bacnet_sc', base)['status'] == 'VALID'
    for patch in ({'payload_bytes':6001}, {'sc_npdu_bytes':6022}, {'sc_peer_max_bvlc_bytes':10228},
                  {'sc_data_options_bytes':4193}, {'sc_npci_header_bytes':22}):
        assert registry.validate_parameters('bacnet_sc', {**base,**patch})['status'] == 'INVALID', patch
    # A blank header is unknown, never an inferred zero-byte header or capacity proof.
    assert registry.validate_parameters('bacnet_sc', {**base,'sc_data_options_bytes':None})['status'] == 'VALID'


def test_bacnet_sc_peer_purpose_fixed_timer_ranges_and_secure_uri_constraints():
    base = {'bitrate':10000000,'sc_connection_type':'DIRECT','sc_websocket_subprotocol':'dc.bsc.bacnet.org',
            'sc_min_reconnect_s':10,'sc_max_reconnect_s':600,'sc_reconnect_timeout_modifiable':False,
            'sc_heartbeat_s':30,'sc_heartbeat_timeout_modifiable':False,
            'sc_vmac_kind':'RANDOM_48','sc_vmac':'122233445566'}
    assert registry.validate_parameters('bacnet_sc', base)['status'] == 'VALID'
    for patch in ({'sc_websocket_subprotocol':'hub.bsc.bacnet.org'}, {'sc_min_reconnect_s':2},
                  {'sc_min_reconnect_s':31}, {'sc_max_reconnect_s':601}, {'sc_max_reconnect_s':9},
                  {'sc_heartbeat_s':3}, {'sc_heartbeat_s':301}, {'sc_vmac':'102233445566'}):
        assert registry.validate_parameters('bacnet_sc', {**base,**patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('bacnet_sc', {**base,'sc_heartbeat_timeout_modifiable':True,
                                                     'sc_heartbeat_s':500,'sc_connect_wait_s':500})['status'] == 'VALID'
    for uri in ('wss://hub.example.test/sc','wss://[2001:db8::1]:50050/bacnet', ''):
        assert registry.validate_parameters('bacnet_sc', {**base,'sc_primary_hub_uri':uri})['status'] == 'VALID'
    for uri in ('ws://hub.example.test/sc','wss://','wss://hub.test:0/sc','wss://hub.test:65536/sc',
                'wss://hub.test:abc/sc','wss://hub.test/sc#fragment','wss://user:secret@hub.test/sc','wss://hub .test/sc'):
        assert registry.validate_parameters('bacnet_sc', {**base,'sc_primary_hub_uri':uri})['status'] == 'INVALID', uri


@pytest.mark.parametrize('field', registry.parameter_fields('bacnet_sc'), ids=lambda field:'bacnet_sc/'+field['key'])
def test_every_bacnet_sc_parameter_validates_type_bounds_and_native_options(field):
    examples = {'sc_vmac':'122233445566','sc_device_uuid':'12345678-1234-4123-8123-123456789abc'}
    value = examples.get(field['key'], field.get('default',field.get('options',[False])[0] if field.get('options')
            or field['type'] == 'boolean' else 'wss://hub.example.test/sc' if field.get('format') == 'WSS_URI'
            else 'device-reference' if field['type'] == 'text' else field.get('min',0)))
    base = {'bitrate':10000000}
    assert registry.validate_parameters('bacnet_sc', {**base,field['key']:value})['status'] == 'VALID'
    assert registry.validate_parameters('bacnet_sc', {**base,field['key']:'invalid' if field['type']=='number' else 1})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('bacnet_sc', {**base,field['key']:field['min']-1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('bacnet_sc', {**base,field['key']:field['max']+1})['status'] == 'INVALID'
    for option in field.get('options',[]):
        assert registry.validate_parameters('bacnet_sc', {**base,field['key']:option})['status'] == 'VALID'


def test_sc_confirmed_installation_facts_survive_rejected_ip_and_security_edits():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate':10000000,'sc_device_uuid':'12345678-1234-4123-8123-123456789abc',
              'sc_primary_hub_uri':'wss://hub.example.test/sc','sc_min_reconnect_s':20,
              'sc_reconnect_timeout_modifiable':False,'bacnet_max_apdu_bytes':6000,'payload_bytes':5000}
    group = {'values':values,'provenance':{key:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':value} for key,value in values.items()}}
    parameters = {'technology':'bacnet_sc',**values,'technology_parameters':{'bacnet_sc':group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    for key,value in (('bacnet_udp_port',47808),('sc_mutual_tls_required',False)):
        bad = deepcopy(parameters)
        bad['technology_parameters']['bacnet_sc']['values'][key] = value
        bad['technology_parameters']['bacnet_sc']['provenance'][key] = {'source':'USER_CONFIRMED','status':'CONFIRMED','value':value}
        with pytest.raises(ValueError):
            service.save_parameters(bad)
        assert service.get()['parameters'] == parameters


def test_bacnet_ip_defaults_distinguish_link_device_and_service_parameters():
    fields = {item['key']: item for item in registry.parameter_fields('bacnet_ip')}
    assert registry.profile('bacnet_ip')['default_bitrate'] is None
    assert registry.parameter_defaults_review('bacnet_ip')['rate_profile'] == 'ethernet'
    assert fields['bacnet_udp_port']['default'] == 47808
    assert fields['bacnet_apdu_retries']['default'] == 3
    assert fields['bacnet_segment_timeout_ms']['default'] == 2000
    assert fields['bacnet_apdu_timeout_ms']['conditional_defaults'] == [
        {'when': {'bacnet_apdu_timeout_modifiable': True}, 'value': 3000},
        {'when': {'bacnet_apdu_timeout_modifiable': False}, 'value': 60000}]
    for name in ('bacnet_apdu_timeout_ms', 'bacnet_apdu_timeout_modifiable', 'bacnet_max_apdu_bytes',
                 'bacnet_segmentation', 'bacnet_device_instance', 'payload_bytes', 'duplex', 'bacnet_broadcast_role'):
        assert 'default' not in fields[name], name
    for patch in ({'qos_priority': 3}, {'retry_limit': 3}, {'sync_method': 'NTP'},
                  {'arinc429_label': 1}, {'bacnet_device_instance': 4194303}, {'bacnet_foreign_device_ttl_s': 65536}):
        assert registry.validate_parameters('bacnet_ip', {'bitrate': 10000000, **patch})['status'] == 'INVALID', patch


def test_bacnet_ip_native_transaction_constraints_do_not_replace_actual_pics():
    base = {'bitrate': 10000000, 'bacnet_max_apdu_bytes': 256, 'payload_bytes': 206,
            'bacnet_apdu_retries': 3, 'bacnet_apdu_timeout_ms': 3000, 'bacnet_segment_timeout_ms': 2000}
    assert registry.validate_parameters('bacnet_ip', base)['status'] == 'VALID'
    for patch in ({'payload_bytes': 257}, {'bacnet_apdu_timeout_ms': 0}, {'bacnet_segment_timeout_ms': 0}):
        assert registry.validate_parameters('bacnet_ip', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('bacnet_ip', {**base, 'bacnet_apdu_retries': 0,
            'bacnet_apdu_timeout_ms': 0, 'bacnet_segment_timeout_ms': 0})['status'] == 'VALID'
    # Read-only does not make 60000 ms a mandatory operating value. The source defines a default.
    assert registry.validate_parameters('bacnet_ip', {**base, 'bacnet_apdu_timeout_modifiable': False})['status'] == 'VALID'
    assert registry.validate_parameters('can', {'bitrate': 10000, 'bacnet_udp_port': 47808})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('bacnet_ip'), ids=lambda field: 'bacnet_ip/' + field['key'])
def test_every_bacnet_ip_parameter_validates_type_bounds_and_options(field):
    value = field.get('default', field.get('options', [False])[0] if field.get('options') or field['type'] == 'boolean' else field.get('min', 0))
    base = {'bitrate': 10000000}
    assert registry.validate_parameters('bacnet_ip', {**base, field['key']: value})['status'] == 'VALID'
    wrong = 'invalid' if field['type'] == 'number' else 1
    assert registry.validate_parameters('bacnet_ip', {**base, field['key']: wrong})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('bacnet_ip', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('bacnet_ip', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('bacnet_ip', {**base, field['key']: option})['status'] == 'VALID'


def test_bacnet_ip_parameter_storage_preserves_actual_device_facts_and_rejects_bad_edits():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 10000000, 'bacnet_device_instance': 42, 'bacnet_max_apdu_bytes': 256,
              'bacnet_apdu_retries': 3, 'bacnet_apdu_timeout_modifiable': False, 'bacnet_apdu_timeout_ms': 3000,
              'bacnet_segmentation': 'NONE', 'payload_bytes': 206}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': 'bacnet_ip', **values, 'technology_parameters': {'bacnet_ip': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['bacnet_ip']['values']['payload_bytes'] = 257
    bad['technology_parameters']['bacnet_ip']['provenance']['payload_bytes']['value'] = 257
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters
    assert registry.profile('bacnet_ip')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_avb_baseline_does_not_accept_plain_ethernet_or_tsn_guarantees():
    fields = {item['key']: item for item in registry.parameter_fields('avb')}
    assert registry.profile('avb')['domain'] == 'generic_networking'
    assert registry.parameter_defaults_review('avb')['values'] == {'bitrate_bps': 100_000_000}
    assert fields['queue_policy']['default'] == 'CBS' and fields['queue_policy']['options'] == ['CBS']
    assert fields['sync_method']['default'] == 'GPTP' and fields['duplex']['options'] == ['FULL']
    assert 'default' not in fields['qos_priority'] and 'default' not in fields['vlan_id']
    for patch in ({'bitrate': 10_000_000}, {'duplex': 'HALF'}, {'queue_policy': 'TAS'},
                  {'sync_method': 'NTP'}, {'retry_limit': 1}, {'afdx_vl_id': 1}):
        assert registry.validate_parameters('avb', {'bitrate': 100_000_000, **patch})['status'] == 'INVALID', patch
    assert registry.profile('avb')['capacity_evidence']['status'] == 'MODEL_MISSING'


def test_avb_native_stream_constraints_use_selected_class_and_link():
    base = {'bitrate': 100_000_000, 'avb_sr_class': 'A', 'avb_measurement_interval_us': 125,
            'avb_idle_slope_bps': 25_000_000, 'avb_send_slope_bps': -75_000_000,
            'avb_stream_id': '0001234567890001', 'avb_destination_mac': '91:e0:f0:00:fe:00',
            'avb_max_frame_size_bytes': 1000, 'payload_bytes': 1000}
    assert registry.validate_parameters('avb', base)['status'] == 'VALID'
    for patch in ({'avb_sr_class': 'B'}, {'avb_measurement_interval_us': 250},
                  {'avb_idle_slope_bps': 100_000_001}, {'avb_send_slope_bps': -5},
                  {'avb_stream_id': 'not-a-stream-id'}, {'avb_destination_mac': '00:01:02:03:04:05'},
                  {'payload_bytes': 1001}, {'avb_max_interval_frames': 65536},
                  {'avb_accumulated_latency_ns': 4294967296}):
        assert registry.validate_parameters('avb', {**base, **patch})['status'] == 'INVALID', patch
    assert registry.validate_parameters('avb', {**base, 'avb_sr_class': 'B', 'avb_measurement_interval_us': 250})['status'] == 'VALID'
    assert registry.validate_parameters('can', {'bitrate': 10000, 'avb_sr_class': 'A'})['status'] == 'INVALID'


@pytest.mark.parametrize('field', registry.parameter_fields('avb'), ids=lambda field: 'avb/' + field['key'])
def test_every_avb_field_uses_native_type_options_and_bounds(field):
    text = {'avb_stream_id': '0001234567890001', 'avb_destination_mac': '91:e0:f0:00:fe:00'}
    value = field.get('default', text.get(field['key'], field.get('options', [False])[0] if field.get('options') or field['type'] == 'boolean' else field.get('min', 0)))
    base = {'bitrate': 100_000_000}
    assert registry.validate_parameters('avb', {**base, field['key']: value})['status'] == 'VALID'
    wrong = 'invalid' if field['type'] == 'number' else 1
    assert registry.validate_parameters('avb', {**base, field['key']: wrong})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('avb', {**base, field['key']: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('avb', {**base, field['key']: field['max'] + 1})['status'] == 'INVALID'
    for option in field.get('options', []):
        assert registry.validate_parameters('avb', {**base, field['key']: option})['status'] == 'VALID'


def test_avb_stream_review_storage_does_not_certify_srp_or_cbs_execution():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 100_000_000, 'avb_sr_class': 'B', 'avb_measurement_interval_us': 250,
              'avb_stream_id': '0001234567890001', 'avb_max_interval_frames': 1,
              'avb_as_capable': False, 'avb_reservation_state': 'UNRESERVED'}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': 'avb', **values, 'technology_parameters': {'avb': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    bad = deepcopy(parameters)
    bad['technology_parameters']['avb']['values']['avb_measurement_interval_us'] = 125
    bad['technology_parameters']['avb']['provenance']['avb_measurement_interval_us']['value'] = 125
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(bad)
    assert service.get()['parameters'] == parameters
    assert registry.profile('avb')['capacity_evidence']['status'] == 'MODEL_MISSING'


@pytest.mark.parametrize('field', registry.parameter_fields('adc'), ids=lambda field: 'adc/' + field['key'])
def test_every_adc_form_field_validates_its_type_and_bounds(field):
    name = field['key']
    assert registry.validate_parameters('adc', {name: field['default']})['status'] == 'VALID'
    bad = 'invalid' if field['type'] == 'number' else 1
    assert registry.validate_parameters('adc', {name: bad})['status'] == 'INVALID'
    if field.get('min') is not None:
        assert registry.validate_parameters('adc', {name: field['min'] - 1})['status'] == 'INVALID'
    if field.get('max') is not None:
        assert registry.validate_parameters('adc', {name: field['max'] + 1})['status'] == 'INVALID'


def test_5g_radio_settings_validate_types_modes_and_counts_without_guessing():
    assert registry.validate_parameters('5g', {'bitrate_bps': 1_000_000, 'nr_carrier_count': 1,
                                             'nr_direction': 'UL', 'nr_scaling_factor': '0.8'})['status'] == 'VALID'
    for name, value in [('nr_carrier_count', 1.5), ('nr_carrier_count', True),
                        ('nr_channel_bandwidth_mhz', 0), ('nr_direction', 'SEND'),
                        ('nr_subcarrier_spacing_khz', '999'), ('nr_scaling_factor', '0')]:
        assert registry.validate_parameters('5g', {'bitrate_bps': 1_000_000, name: value})['status'] == 'INVALID', name
    result = registry.validate_parameters('can', {'bitrate_bps': 10_000, 'nr_direction': 'UL'})
    assert result['status'] == 'INVALID'
    assert 'TECHNOLOGY_PARAMETER_NOT_APPLICABLE' in {finding['code'] for finding in result['findings']}
    changed = registry.change_parameters('5g', 'can', {'nr_direction': 'UL', 'note': 'preserve'})
    assert changed['parameters'] == {'note': 'preserve'}
    assert changed['invalidated_fields'] == ['nr_direction']


def test_5g_dependencies_use_the_selected_frequency_range_and_direction():
    base = {'bitrate_bps': 1_000_000, 'nr_frequency_range': 'FR1', 'nr_subcarrier_spacing_khz': '15'}
    assert registry.validate_parameters('5g', {**base, 'nr_channel_bandwidth_mhz': 50})['status'] == 'VALID'
    assert registry.validate_parameters('5g', {**base, 'nr_channel_bandwidth_mhz': 100})['status'] == 'INVALID'
    assert registry.validate_parameters('5g', {**base, 'nr_subcarrier_spacing_khz': '120'})['status'] == 'INVALID'
    assert registry.validate_parameters('5g', {'bitrate': 1_000_000, 'nr_subcarrier_spacing_khz': '240'})['status'] == 'INVALID'
    fr2 = {**base, 'nr_frequency_range': 'FR2', 'nr_subcarrier_spacing_khz': '60'}
    assert registry.validate_parameters('5g', {**fr2, 'nr_channel_bandwidth_mhz': 400})['status'] == 'INVALID'
    assert registry.validate_parameters('5g', {**fr2, 'nr_subcarrier_spacing_khz': '120', 'nr_channel_bandwidth_mhz': 400})['status'] == 'VALID'
    assert registry.validate_parameters('5g', {**base, 'nr_direction': 'UL', 'nr_mimo_layers': 8})['status'] == 'INVALID'
    assert registry.validate_parameters('5g', {**base, 'nr_direction': 'DL', 'nr_mimo_layers': 8})['status'] == 'VALID'


def test_planned_profiles_validate_parameters_without_claiming_executable_models():
    local = TechnologyRegistry()
    profile = registry.profile('5g')
    profile['implementation_status'] = 'PLANNED'
    local.register_defaults([profile])
    assert local.validate_parameters('5g', {'bitrate': 1_000_000, 'nr_carrier_count': 0})['status'] == 'INVALID'
    with pytest.raises(LookupError):
        local.resolve_binding('5g')


def test_ui_aliases_reject_conflicts_and_foreign_phase_fields():
    assert registry.validate_parameters('lin', {'bitrate': 9_600, 'bitrate_bps': 19_200})['status'] == 'INVALID'
    assert registry.validate_parameters('lin', {'bitrate': 9_600, 'data_bitrate': 1_000_000})['status'] == 'INVALID'
    assert registry.validate_parameters('can_fd', {'bitrate': 2_000_000, 'arbitration_bitrate': 500_000,
                                                  'data_bitrate': 2_000_000})['status'] == 'VALID'


def test_capacity_does_not_carry_radio_or_ethernet_fields_into_other_buses():
    values = {'technology': '5g', 'bitrate': 1_000_000, 'nr_direction': 'UL', 'mtu_bytes': 1500,
              'cycle_ms': 50, 'networks': [{'id': 'can-1', 'technology': 'can', 'bitrate': 10_000}]}
    resolved = parameters_for_protocol('can', values, network_id='can-1', confirmed_parameters=values)
    assert resolved['_rate_evidenced']
    assert not {'nr_direction', 'mtu_bytes'} & resolved.keys()
    assert resolved['cycle_ms'] == 50


def test_workflow_network_validation_includes_non_rate_parameters():
    before = {'networks': [{'id': 'radio', 'technology': '5g', 'bitrate': 1_000_000}]}
    changed = {'networks': [{'id': 'radio', 'technology': '5g', 'bitrate': 1_000_000, 'nr_direction': 'SEND'}]}
    with pytest.raises(ValueError, match='OUT_OF_RANGE'):
        WorkflowStatusService._validate_parameter_reviews(changed, before)


def test_standalone_validates_selected_profile_fields_not_only_rates(tmp_path):
    with pytest.raises(ValueError, match='NOT_APPLICABLE'):
        SimulationService().prepare_config({'technology': 'can', 'bitrate': 10_000, 'nr_direction': 'UL'}, tmp_path)


@pytest.mark.parametrize('field', registry.parameter_fields('5g'), ids=lambda field: '5g/' + field['key'])
def test_every_5g_form_field_validates_its_own_type_options_and_bounds(field):
    base = {'bitrate_bps': 1_000_000}
    name = field['key']
    value = field.get('default', field.get('options', [None])[0] if field.get('options') else
                      'n78' if field['type'] == 'text' else False if field['type'] == 'boolean' else field.get('min', 0))
    if name == 'bitrate':
        base = {}
    assert registry.validate_parameters('5g', {**base, name: value})['status'] == 'VALID'
    bad = 'invalid' if field['type'] == 'number' else 1 if field['type'] == 'boolean' else 0
    assert registry.validate_parameters('5g', {**base, name: bad})['status'] == 'INVALID'
    if field['type'] == 'number':
        if field.get('min') is not None:
            assert registry.validate_parameters('5g', {**base, name: field['min'] - 1})['status'] == 'INVALID'
        if field.get('max') is not None:
            assert registry.validate_parameters('5g', {**base, name: field['max'] + 1})['status'] == 'INVALID'
    if field['type'] == 'select':
        for option in field['options']:
            assert registry.validate_parameters('5g', {**base, name: option})['status'] == 'VALID'


def test_reviewed_radio_parameters_roundtrip_and_rejected_edits_preserve_saved_values():
    from backend.engineering.project_context import current_project_id
    from copy import deepcopy
    service = WorkflowStatusService(current_project_id())
    values = {'bitrate': 1_000_000, 'nr_direction': 'UL', 'nr_frequency_range': 'FR1',
              'nr_subcarrier_spacing_khz': '30', 'nr_channel_bandwidth_mhz': 20, 'nr_mimo_layers': 2}
    group = {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
                                             for key, value in values.items()}}
    parameters = {'technology': '5g', **values, 'cycle_ms': 100, 'payload_bytes': 8,
                  'formats': ['universal-jsonl'], 'technology_parameters': {'5g': group}}
    service.save_parameters(parameters)
    assert service.get()['parameters'] == parameters
    changed = deepcopy(parameters)
    changed['technology_parameters']['5g']['values']['nr_mimo_layers'] = 8
    changed['technology_parameters']['5g']['provenance']['nr_mimo_layers']['value'] = 8
    with pytest.raises(ValueError, match='DEPENDENCY_MISMATCH'):
        service.save_parameters(changed)
    assert service.get()['parameters'] == parameters
