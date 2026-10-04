"""DSI packet, direction, pixel, bridge and RX regressions in isolated SQL."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.mipi_dsi import rules as DS

def actual(device='TI83'):
    x={'ds_'+k:'synthetic-actual-'+k for k in DS.REQUIRED}
    x.update(ds_family='DSI',ds_version='1.02',ds_phy='DPHY_CLASSIC',ds_device=device,ds_direction='BRIDGE_RX',
      ds_mode='VIDEO_BURST',ds_clock_mode='CONTINUOUS',ds_lanes=4,ds_lane_bitrate_bps=800000000,
      ds_header='CLASSIC',ds_control_network_id='synthetic-csr-bus',ds_control_source='synthetic-ADDR-pin',
      ds_lvds_network_id='synthetic-output',ds_pll_source='synthetic-pll-settings',ds_sequence_source='synthetic-reset')
    if device=='REGISTERED':x.update(ds_registered_source='synthetic-registered-endpoints',ds_direction='HOST_TX')
    elif device.startswith('LATTICE'):
        x.update(ds_family='DSI2',ds_version='2.2',ds_direction='DISPLAY_RX',ds_ppi_source='synthetic-generated-IP',
          ds_buffer_source='synthetic-buffer',ds_timing_source='synthetic-source-timings')
    return x

def long(count=2400,device='TI83'):
    return {**actual(device),'ds_packet':'LONG','ds_packet_direction':'HOST_TO_DISPLAY','ds_vc':0,'ds_data_type':62,
      'ds_data_id':62,'ds_word_count':count,'payload_bytes':count,'ds_header_bytes':4,'ds_footer_bytes':2,'ds_packet_bytes':count+6}

def status(x):return registry.validate_parameters('mipi_dsi',x)['status']

def test_dsi_no_universal_two_point_five_g_can_queues_or_csi_semantics():
    fields={f['key']:f for f in registry.parameter_fields('mipi_dsi')}
    assert not set(DS.REMOVED)&set(fields)
    assert registry.profile('mipi_dsi')['rate_model']['fields']==[]
    assert registry.parameter_defaults_review('mipi_dsi')['values']=={}
    assert {v['value']for v in fields['ds_lane_bitrate_bps']['conditional_defaults']}=={80000000,160000000}
    assert 'default'not in fields['payload_bytes']
    assert status(actual())=='VALID'
    for patch in ({'bitrate':2500000000},{'bitrate_bps':2500000000},{'queue_size':1024},{'retry_limit':3},
      {'cs_lane_bitrate_bps':800000000},{'local_timing_evidence':{'source':'i2c','confirmed':True}}):
        assert status({**actual(),**patch})=='INVALID'
    assert registry.profile('mipi_dsi')['capacity_evidence']['status']=='MODEL_MISSING'

@pytest.mark.parametrize('field',registry.parameter_fields('mipi_dsi'),ids=lambda f:f['key'])
def test_dsi_declared_field_types_and_own_applicable_bounds(field):
    context=actual('LATTICE_HARD')if field.get('schema_when',{}).get('ds_device')==['LATTICE_SOFT','LATTICE_HARD']else actual()
    wrong='bad-number'if field['type']=='number'else 1
    assert status({**context,field['key']:wrong})=='INVALID'
    for limit,offset in [('min',-1),('max',1)]:
        if field.get(limit)is not None:assert status({**context,field['key']:field[limit]+offset})=='INVALID'

@pytest.mark.parametrize('direction,packet,dt',[
 ('HOST_TO_DISPLAY','SHORT',55),('HOST_TO_DISPLAY','SHORT',49),('HOST_TO_DISPLAY','LONG',9),
 ('HOST_TO_DISPLAY','LONG',10),('DISPLAY_TO_HOST','SHORT',33),('DISPLAY_TO_HOST','LONG',26)])
def test_dsi_direction_specific_packet_types_differ_from_csi_numeric_split(direction,packet,dt):
    x={**actual('REGISTERED'),'ds_packet_direction':direction,'ds_packet':packet,'ds_data_type':dt}
    assert status(x)=='VALID'
    assert status({**x,'ds_packet':'SHORT'if packet=='LONG'else'LONG'})=='INVALID'
    assert status({**x,'ds_data_type':63})=='INVALID'

@pytest.mark.parametrize('fmt,depth,wire,dt,pixels,count',[
 ('RGB565',16,16,14,3,6),('RGB666_PACKED',18,18,30,4,9),
 ('RGB666_LOOSE',18,24,46,4,12),('RGB888',24,24,62,4,12)])
def test_dsi_pixel_groups_preserve_loose18_as_wire24_and_do_not_round_packed_pixels(fmt,depth,wire,dt,pixels,count):
    x={**long(count,'REGISTERED'),'ds_format':fmt,'ds_pixel_bits':depth,'ds_wire_pixel_bits':wire,
      'ds_data_type':dt,'ds_data_id':dt,'ds_line_pixels':pixels,'ds_packing_remainder':0}
    assert status(x)=='VALID'
    for patch in ({'ds_word_count':count+1},{'ds_wire_pixel_bits':wire+1},{'ds_packet_bytes':count+4},
      {'ds_data_type':dt^1},{'ds_footer_bytes':0}):assert status({**x,**patch})=='INVALID'
    assert status({**x,'ds_vc':3,'ds_data_id':192+dt})=='VALID'
    if fmt=='RGB666_PACKED':assert status({**x,'ds_line_pixels':5,'ds_packing_remainder':1})=='INVALID'
    assert status({k:v for k,v in x.items()if k!='ds_packing_remainder'})=='UNVERIFIED'

@pytest.mark.parametrize('command,count,dt,packet',[('GENERIC_WRITE',0,3,'SHORT'),('GENERIC_WRITE',2,35,'SHORT'),
 ('GENERIC_WRITE',3,41,'LONG'),('GENERIC_READ',1,20,'SHORT'),('DCS_WRITE',1,5,'SHORT'),
 ('DCS_WRITE',2,21,'SHORT'),('DCS_WRITE',3,57,'LONG'),('DCS_READ',1,6,'SHORT'),('SET_MAX_RETURN',2,55,'SHORT')])
def test_dsi_command_length_includes_dcs_opcode_and_short_data_stays_in_header(command,count,dt,packet):
    x={**actual('REGISTERED'),'ds_command':command,'ds_command_bytes':count,'ds_data_type':dt,'ds_packet':packet,
      'ds_packet_direction':'HOST_TO_DISPLAY','ds_readback':True,'ds_feature_source':'synthetic-command-endpoints'}
    if packet=='LONG':x.update(ds_word_count=count,ds_packet_bytes=count+6)
    assert status(x)=='VALID'
    assert status({**x,'ds_data_type':dt^1})=='INVALID'
    if packet=='SHORT':assert status({**x,'payload_bytes':count})=='INVALID'
    if command=='DCS_WRITE':assert status({**x,'ds_command_bytes':0})=='INVALID'
    if command.endswith('READ'):assert status({**x,'ds_readback':False})=='INVALID'

def test_dsi_ti_clock_buckets_and_clock_origin_are_not_lane_or_pixel_rates():
    x={**actual(),'ds_clock_hz':400000000,'ds_dsi_clock_range_code':80,'ds_lvds_clock_source':'DSI_HS',
      'ds_clock_divider_code':7,'ds_clock_multiplier_code':0,'ds_lvds_clock_hz':50000000,'ds_lvds_clock_range_code':1}
    assert status(x)=='VALID'
    for patch in ({'ds_clock_hz':800000000},{'ds_dsi_clock_range_code':79},{'ds_clock_multiplier_code':1},
      {'ds_clock_mode':'NONCONTINUOUS'},{'ds_clock_divider_code':25},{'ds_lvds_clock_range_code':2}):assert status({**x,**patch})=='INVALID'
    y={**x,'ds_clock_hz':500000000,'ds_lane_bitrate_bps':1000000000,'ds_dsi_clock_range_code':100,
      'ds_clock_divider_code':9,'ds_lvds_clock_hz':50000000}
    assert status(y)=='VALID'
    assert status({**y,'ds_dsi_clock_range_code':99})=='INVALID'
    z={**x,'ds_lvds_clock_source':'REFCLK','ds_reference_clock_hz':25000000,'ds_clock_divider_code':0,
      'ds_clock_multiplier_code':3,'ds_lvds_clock_hz':100000000,'ds_lvds_clock_range_code':3}
    assert status(z)=='VALID'
    assert status({**z,'ds_clock_divider_code':1})=='INVALID'

def test_dsi_ti_no_virtual_channel_reverse_commands_or_test_pattern_as_whole_link_evidence():
    x=long(12);x.update(ds_format='RGB666_LOOSE',ds_pixel_bits=18,ds_wire_pixel_bits=24,ds_line_pixels=4,
      ds_packing_remainder=0,ds_data_type=46,ds_data_id=46,ds_control_address=45,ds_control_rate_bps=330000,
      ds_sync_delay_pixels=32,ds_lvds_format='18BPP')
    assert status(x)=='VALID'
    for patch in ({'ds_vc':1},{'ds_readback':True},{'ds_bta':True},{'ds_mode':'COMMAND'},
      {'ds_control_address':90},{'ds_control_rate_bps':400001},{'ds_sync_delay_pixels':31},
      {'ds_lvds_format':'24BPP_FORMAT1'},{'ds_test_vlines':800,'ds_test_pattern':False}):assert status({**x,**patch})=='INVALID'
    assert status({**x,'ds_lanes':3})=='VALID'
    assert status({**x,'ds_test_vlines':800,'ds_test_pattern':True})=='VALID'
    assert registry.profile('mipi_dsi')['capacity_evidence']['status']=='MODEL_MISSING'

def test_dsi_bridge_receiver_physics_use_their_own_limits_and_reserved_table_row_is_not_fabricated():
    x={**actual(),'ds_measurement_source':'synthetic-fixture','ds_hs_diff_mv':70,'ds_hs_common_mv':330,
      'ds_rx_diff_ohm':125,'ds_setup_ui':.15,'ds_hold_ui':.15,'ds_vcc_v':1.65,'ds_temperature_c':85,
      'ds_lvds_term_ohm':200,'ds_swing_code':2,'ds_data_vod_mv':428,'ds_clock_vod_mv':334}
    assert status(x)=='VALID'
    for patch in ({'ds_hs_diff_mv':69.99},{'ds_rx_diff_ohm':125.1},{'ds_setup_ui':.14999},
      {'ds_vcc_v':2.175},{'ds_temperature_c':105},{'ds_data_vod_mv':428.01},{'ds_clock_vod_mv':334.01}):assert status({**x,**patch})=='INVALID'
    y={**x,'ds_lvds_term_ohm':100,'ds_data_vod_mv':430,'ds_clock_vod_mv':335}
    assert status(y)=='UNVERIFIED'  # Source repeats clock code01; no guessed code10 correction.
    assert status({**y,'ds_registered_source':'synthetic-manufacturer-row-clarification'})=='VALID'
    assert status({**actual('LATTICE_HARD'),'ds_rx_diff_ohm':80})=='UNVERIFIED'

@pytest.mark.parametrize('device,width,lanes,controller,wc',[
 ('LATTICE_SOFT',8,4,32,14),('LATTICE_HARD',8,4,32,14),('LATTICE_HARD',16,4,64,34),('LATTICE_HARD',16,2,32,14)])
def test_dsi_lattice_rx_minimum_packet_and_generated_ppi_do_not_use_csi_values(device,width,lanes,controller,wc):
    x={**long(wc,device),'ds_phy_width_bits':width,'ds_lanes':lanes,'ds_controller_bits':controller,
      'ds_byte_clock_hz':800000000/width,'ds_reference_clock_hz':60000000,'ds_free_clock_hz':100000000,
      'ds_csr_clock_hz':60000000,'ds_interface':'MBSI','ds_axis_width_bits':controller,'ds_ecc_check':True,
      'ds_eotp':True,'ds_buffer_depth':512,'ds_stall_cycles':511}
    assert status(x)=='VALID'
    for patch in ({'ds_word_count':wc-1},{'ds_controller_bits':64 if controller==32 else 32},
      {'ds_ecc_check':False},{'ds_ulps':True},{'ds_bta':True},{'ds_direction':'HOST_TX'},
      {'ds_free_clock_hz':59999999},{'ds_stall_cycles':512}):assert status({**x,**patch})=='INVALID'
    assert status({**x,'ds_eotp':False})=='UNVERIFIED'
    assert status({**x,'ds_eotp':False,'ds_error_acceptance_source':'synthetic-accepted-error-strategy'})=='VALID'

def test_dsi_lattice_soft_source_prepare_zero_and_idle_require_own_clock_evidence():
    x={**actual('LATTICE_SOFT'),'ds_phy_width_bits':8,'ds_byte_clock_hz':100000000,
      'ds_reference_clock_hz':60000000,'ds_ui_ns':1.25,'ds_hs_prepare_ns':45,'ds_hs_zero_ns':250,
      'ds_idle_ns':100,'ds_mipi_idle_min_ns':100}
    assert status(x)=='VALID'
    assert status({**x,'ds_hs_zero_ns':245})=='INVALID'
    assert status({**x,'ds_idle_ns':79.99})=='INVALID'
    y={**actual('LATTICE_HARD'),'ds_phy_width_bits':16,'ds_byte_clock_hz':50000000,
      'ds_reference_clock_hz':60000000,'ds_idle_ns':370,'ds_mipi_idle_min_ns':100}
    assert status(y)=='VALID'
    assert status({**y,'ds_idle_ns':369.99})=='INVALID'

def test_dsi_confirmed_nondefault_address_and_pixel_packing_survive_rejected_isolated_sql_edit():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x=long(2430);x.update(ds_format='RGB666_PACKED',ds_line_pixels=1080,ds_packing_remainder=0,
      ds_data_type=30,ds_data_id=30,ds_control_address=45,ds_control_rate_bps=330000,ds_lane_bitrate_bps=640000000)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'mipi_dsi','technology_parameters':{'mipi_dsi':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['mipi_dsi']['values']['ds_word_count']=2431
    bad['technology_parameters']['mipi_dsi']['provenance']['ds_word_count']['value']=2431
    with pytest.raises(ValueError,match='DEPENDENCY_MISMATCH'):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
