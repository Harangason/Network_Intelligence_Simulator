"""PA synchronous framing/power/device profile must not borrow DP/CAN/FF models."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profibus_pa as P
def actual():
 x={'pa_'+k:'synthetic-'+k for k in P.REQUIRED}
 x.update(bitrate_bps=31250,pa_phy='MBP',pa_layout='PNO1997_PART9',pa_device_profile='EH_O200_3_02',pa_coupling='NATIVE_MASTER',pa_role='SLAVE')
 return x
def status(x):return registry.validate_parameters('profibus_pa',x)['status']
def test_pa_own_mbp_path_not_dp_uart_can_or_ff_las():
 p=registry.profile('profibus_pa');assert p['default_stack']==['profibus_pa']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'
 fields=registry.parameter_fields('profibus_pa');keys=[v['key']for v in fields];assert len(keys)==len(set(keys))and not set(keys)&set(P.REMOVED)
 for bad in({'bitrate_bps':12000000},{'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'pa_encoding':'NRZ_UART'},{'pa_duplex':'FULL'}):
  assert status({**actual(),**bad})=='INVALID'
 assert status({'bitrate_bps':31250})=='UNVERIFIED'
@pytest.mark.parametrize('field',registry.parameter_fields('profibus_pa'),ids=lambda f:f['key'])
def test_pa_every_declared_field_type_and_outer_bound(field):
 k='bitrate_bps'if field['key']=='bitrate'else field['key']
 assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'
def test_pa_literature_proposals_distinct_unknown_device_and_examples():
 f={v['key']:v for v in registry.parameter_fields('profibus_pa')};assert f['bitrate']['default']==31250
 for k,val in P.DEFAULTS.items():
  assert f['pa_'+k]['conditional_defaults'][0]['value']==val
  assert f['pa_'+k]['conditional_defaults'][0]['when']=={'pa_layout':'PNO1997_PART9'}
 for k in('station','trunk_m','all_spurs_m','supply_v','device_current_ma','supply_capacity_ma','watchdog_ms','poll_interval_ms','protection_verified'):
  assert 'default'not in f['pa_'+k]
def test_pa_total_length_all_spurs_not_only_trunk_and_equipment_spur_limit():
 x={**actual(),'pa_trunk_m':1600,'pa_all_spurs_m':300,'pa_segment_total_m':1900,'pa_longest_spur_m':60,'pa_spur_limit_m':60}
 assert status(x)=='VALID'
 for bad in({'pa_trunk_m':1601},{'pa_segment_total_m':1600},{'pa_longest_spur_m':61}):assert status({**x,**bad})=='INVALID'
 x.pop('pa_spur_limit_m');assert status(x)=='UNVERIFIED'
def test_pa_segment_devices_require_real_power_or_intrinsic_safety_limit():
 x={**actual(),'pa_segment_devices':16,'pa_segment_device_limit':16,'pa_phy':'MBP_IS','pa_protection':'FISCO','pa_protection_source':'synthetic-IS-assessment'}
 assert status(x)=='VALID'
 assert status({**x,'pa_segment_devices':17})=='INVALID'
 assert status({**x,'pa_protection':'ORDINARY'})=='INVALID'
 x.pop('pa_protection_source');assert status(x)=='UNVERIFIED'
def test_pa_voltage_loop_resistance_ma_conversion_and_actual_device_minimum():
 x={**actual(),'pa_supply_v':28,'pa_loop_ohm_km':44,'pa_path_loop_m':500,'pa_path_current_ma':300,'pa_barrier_drop_v':1,
  'pa_terminal_v':20.4,'pa_device_voltage_min_v':10,'pa_device_voltage_max_v':32}
 assert status(x)=='VALID'
 for bad in({'pa_terminal_v':27},{'pa_device_voltage_min_v':21},{'pa_device_voltage_max_v':24}):assert status({**x,**bad})=='INVALID'
 x.pop('pa_path_current_ma');assert status(x)=='UNVERIFIED'
def test_pa_supply_budget_includes_barriers_fault_and_explicit_spare():
 x={**actual(),'pa_device_currents_total_ma':288,'pa_barrier_current_ma':18,'pa_fault_reserve_ma':40,'pa_spare_current_ma':60,
  'pa_required_current_ma':406,'pa_supply_capacity_ma':500}
 assert status(x)=='VALID'
 for bad in({'pa_required_current_ma':288},{'pa_supply_capacity_ma':405},{'pa_spare_current_ma':0}):assert status({**x,**bad})=='INVALID'
 x.pop('pa_fault_reserve_ma');assert status(x)=='UNVERIFIED'
def test_pa_device_current_not_universal_and_aggregation_separate():
 assert status({**actual(),'pa_device_current_ma':16})=='VALID'
 assert status({**actual(),'pa_device_current_ma':10})=='INVALID'
 x={**actual(),'pa_device_profile':'REGISTERED_ACTUAL','pa_registered_source':'synthetic-other-GSD','pa_device_current_ma':10};assert status(x)=='VALID'
 x.update(pa_coupling='ADDRESS_AGGREGATING_LINK',pa_coupler_source='synthetic-link',pa_coupler_mapping_valid=True,
  pa_link_aggregated_bytes=244,pa_input_bytes=244,pa_output_bytes=244,payload_bytes=488)
 assert status(x)=='VALID';assert status({**x,'pa_link_aggregated_bytes':245})=='INVALID'
 x.pop('pa_coupler_mapping_valid');assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('frame,size,wire',[('SDL1',6,72),('SDL3',14,136),('SDL4',5,64),('SDL5',3,48)])
def test_pa_crc_protected_physical_frames_not_dp_sizes(frame,size,wire):
 x={**actual(),'pa_frame':frame,'pa_fdl_bytes':size,'pa_phy_bytes':size+3,'pa_preamble_bytes':1,'pa_phy_sd_bytes':1,'pa_phy_ed_bytes':1,
  'pa_wire_bits':wire,'pa_serialization_us':wire*32,'pa_crc_bytes':2,'pa_crc_polynomial':7623}
 assert status(x)=='VALID'
 for bad in({'pa_fdl_bytes':size-1},{'pa_wire_bits':(size+3)*11},{'pa_crc_bytes':1},{'pa_crc_polynomial':40961}):assert status({**x,**bad})=='INVALID'
def test_pa_variable_frame_extensions_crc_and_application_bytes():
 x={**actual(),'pa_frame':'SDL2','pa_service':'ACYCLIC','pa_user_bytes':244,'pa_address_extension_bytes':2,'pa_data_unit_bytes':246,
  'pa_le':249,'pa_le_repeat':249,'pa_fdl_bytes':255,'pa_preamble_bytes':1,'pa_phy_sd_bytes':1,'pa_phy_ed_bytes':1,'pa_phy_bytes':258,'pa_wire_bits':2064}
 assert status(x)=='VALID'
 for bad in({'pa_le_repeat':248},{'pa_data_unit_bytes':244},{'pa_phy_bytes':255},{'pa_service':'CYCLIC'}):assert status({**x,**bad})=='INVALID'
def test_pa_native_bit_timing_and_postgap_not_dp33bits():
 x={**actual(),'pa_post_gap_bits':4,'pa_setup_bits':2,'pa_safety_margin_bits':6,'pa_ready_bits':8,'pa_min_tsdr_bits':10,
  'pa_max_tsdr_bits':30,'pa_initiator_delay_bits':15,'pa_idle1_bits':15,'pa_idle2_bits':30,'pa_peer_idle1_max_bits':20,
  'pa_propagation_bits':2,'pa_preamble_bytes':1,'pa_slot_bits':64,'pa_slot_us':2048}
 assert status(x)=='VALID'
 for bad in({'pa_post_gap_bits':33},{'pa_ready_bits':4},{'pa_ready_bits':10},{'pa_idle1_bits':37},{'pa_slot_bits':100},{'pa_slot_us':64}):
  assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('module,slot,inp,out,value,sts',[
 ('AI',1,5,0,4,1),('TOTAL',5,5,0,4,1),('AO',8,0,5,4,1),('DI',9,2,0,1,1),('DO',11,0,2,1,1),
 ('SETTOT_TOTAL',6,5,1,4,1),('SETTOT_MODETOT_TOTAL',7,5,2,4,1),('EMPTY',13,0,0,0,0)])
def test_pa_eh_module_byte_and_slot_mapping(module,slot,inp,out,value,sts):
 x={**actual(),'pa_module':module,'pa_slot':slot,'pa_module_input_bytes':inp,'pa_module_output_bytes':out,'pa_value_bytes':value,'pa_status_bytes':sts}
 assert status(x)=='VALID'
 for bad in({'pa_module_input_bytes':inp+1},{'pa_module_output_bytes':out+1},{'pa_status_bytes':1-sts}):assert status({**x,**bad})=='INVALID'
 if module!='EMPTY':assert status({**x,'pa_slot':13 if module!='DO'else 1})=='INVALID'
def test_pa_functional_acceptance_needs_actual_quality_mapping_and_freshness():
 x={**actual(),'pa_data_accepted':True,'pa_outcome':'ACCEPTED','pa_frame_valid':True,'pa_mapping_valid':True,'pa_state':'DATA_EXCHANGE',
  'pa_quality':'GOOD','pa_status_octet':128,'pa_quality_code':2,'pa_age_ms':5,'pa_freshness_ms':10}
 assert status(x)=='VALID'
 for bad in({'pa_status_octet':0},{'pa_quality':'UNCERTAIN'},{'pa_mapping_valid':False},{'pa_frame_valid':False},
  {'pa_quality_code':1},{'pa_state':'WAIT_CFG'},{'pa_age_ms':11}):assert status({**x,**bad})=='INVALID'
 x.pop('pa_status_octet');assert status(x)=='UNVERIFIED'
def test_pa_existing_values_preserved_under_foreign_defaults():
 x={**actual(),'pa_station':17,'pa_watchdog_ms':1234,'pa_poll_interval_ms':250,'pa_trunk_m':450};before=deepcopy(x)
 assert status({**x,'nominal_bitrate_bps':500000})=='INVALID'
 assert x==before and status(x)=='VALID'
