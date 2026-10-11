"""Native OBD vehicle transports, adapter settings and preservation."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import obd2 as O
def actual(transport='CAN_11_250',impl='ELM327_V2_2'):
 x={'o_'+k:'synthetic-actual-'+k for k in O.REQUIRED}
 x.update(o_application='LEGACY_J1979',o_implementation=impl,o_transport=transport,o_host='UART')
 if transport in O.RATES:x['bitrate_bps']=O.RATES[transport]
 else:x.update(o_registered_source='synthetic-registered-transport',o_application='OBDONUDS')
 return x
def status(x):return registry.validate_parameters('obd2',x)['status']
def test_obd2_own_application_binding_no_forced_can_uds_ethernet_or4095_default():
 x=actual();assert status(x)=='VALID'
 p=registry.profile('obd2');assert p['default_stack']==['obd2'];assert p['domain']=='generic_networking'
 assert p['capacity_evidence']['status']=='MODEL_MISSING';assert registry.parameter_defaults_review('obd2')['values']=={}
 keys=[f['key']for f in registry.parameter_fields('obd2')];assert len(keys)==len(set(keys));assert not set(keys)&set(O.REMOVED)
 for patch in({'mtu_bytes':1500},{'can_controller_profile':'M_CAN_3_3_1'},{'mq_qos':1},{'bitrate_bps':100000000},
  {'bitrate_bps':4800},{'o_fd':True},{'o_can_frame_bytes':64},{'o_variable_dlc':True}):assert status({**x,**patch})=='INVALID'
 for key in('payload_bytes','o_request_id','o_expected_ecus','o_service_id','o_chip_vdd_v','o_acceptance_source'):
  f=next(f for f in registry.parameter_fields('obd2')if f['key']==key);assert 'default'not in f;assert not f.get('conditional_defaults')
@pytest.mark.parametrize('field',registry.parameter_fields('obd2'),ids=lambda f:f['key'])
def test_obd2_each_declared_field_type_unit_and_applicable_bound(field):
 bad='not-number'if field['type']=='number' else 1
 assert status({**actual(),field['key']:bad})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'
@pytest.mark.parametrize('transport,rate,code,init',[
 ('J1850_PWM',41600,1,'NONE'),('J1850_VPW',10400,2,'NONE'),('ISO9141_5BAUD',10400,3,'SLOW_5_BAUD'),
 ('KWP_5BAUD',10400,4,'SLOW_5_BAUD'),('KWP_FAST',10400,5,'FAST'),('CAN_11_500',500000,6,'NONE'),
 ('CAN_29_500',500000,7,'NONE'),('CAN_11_250',250000,8,'NONE'),('CAN_29_250',250000,9,'NONE')])
def test_obd2_each_actual_vehicle_protocol_has_own_baseline_not_auto_search_or_host_uart(transport,rate,code,init):
 x={**actual(transport),'bitrate_bps':rate,'o_protocol_code':code,'o_init':init};assert status(x)=='VALID'
 for patch in({'bitrate_bps':rate+1},{'o_protocol_code':0},{'o_protocol_code':10},{'o_init':'REGISTERED'}):assert status({**x,**patch})=='INVALID'
 x.pop('bitrate_bps');assert status(x)=='UNVERIFIED'
 f=next(f for f in registry.parameter_fields('obd2')if f['key']=='bitrate')
 assert any(d['when']=={'o_transport':transport}and d['value']==rate for d in f['conditional_defaults'])
 if transport in O.KLINE:
  assert status({**actual(transport),'o_slow_init_baud':5})=='VALID'
  assert status({**actual(transport),'bitrate_bps':5})=='INVALID'
@pytest.mark.parametrize('transport,bits,functional',[(t,11 if '_11_'in t else 29,0x7df if '_11_'in t else 0x18db33f1)for t in O.CAN])
def test_obd2_can11_29_functional_vs_physical_and_not_extended_addressing(transport,bits,functional):
 x={**actual(transport),'o_can_id_bits':bits,'o_addressing':'FUNCTIONAL','o_request_id':functional,'o_pid_count':6};assert status(x)=='VALID'
 for patch in({'o_can_id_bits':29 if bits==11 else 11},{'o_request_id':functional+1},{'o_pid_count':7}):assert status({**x,**patch})=='INVALID'
 x.update(o_addressing='PHYSICAL',o_request_id=0x7e0 if bits==11 else 0x18da10f1);assert status(x)=='VALID'
 if bits==11:assert status({**x,'o_response_id':2048})=='INVALID'
@pytest.mark.parametrize('packet,pci,data,padding',[('SF',1,7,0),('FF',2,6,0),('CF',1,7,0),('FC',3,0,5)])
def test_obd2_classic_pci_address_padding_and_full_response_are_separate(packet,pci,data,padding):
 x={**actual(),'o_packet_type':packet,'o_pci_bytes':pci,'o_can_address_mode':'NORMAL','o_address_bytes':0,
  'o_frame_data_bytes':data,'o_padding_bytes':padding,'o_can_frame_bytes':8,'o_response_bytes':4095,'payload_bytes':5000}
 assert status(x)=='VALID'
 for patch in({'o_pci_bytes':3 if pci!=3 else 1},{'o_can_frame_bytes':7},{'o_frame_data_bytes':data+1}):assert status({**x,**patch})=='INVALID'
 if data:
  x.update(o_can_address_mode='EXTENDED',o_address_bytes=1,o_frame_data_bytes=data-1,o_target_address=4,o_tester_address=241);assert status(x)=='VALID'
  x.pop('o_target_address');assert status(x)=='UNVERIFIED'
def test_obd2_hex_service_encoding_response_sid_and_negative_pending_quality():
 x={**actual(),'o_request_hex':'010C','o_request_bytes':2,'o_service_id':1,'o_response_hex':'410C17B8',
  'o_response_bytes':4,'o_response_service_id':65,'o_outcome':'POSITIVE','o_data_accepted':True};assert status(x)=='VALID'
 for patch in({'o_service_id':2},{'o_response_service_id':66},{'o_request_hex':'AT010C'},
  {'o_response_bytes':3},{'o_request_hex':'010'},{'o_outcome':'PENDING'}):assert status({**x,**patch})=='INVALID'
 x.update(o_outcome='PENDING',o_response_hex='7F0178',o_response_bytes=3,o_negative_code=0x78,o_data_accepted=False,
  o_pending_source='synthetic-correlated-ECU-service',o_pending_extension_ms=5000,o_pending_count=3,o_pending_budget_ms=18000);assert status(x)=='VALID'
 assert status({**x,'o_negative_code':0})=='INVALID';assert status({**x,'o_data_accepted':True})=='INVALID'
def test_obd2_st_zero_restores_current_pp_and_tick_is4_096_not_global200ms():
 x={**actual(),'o_st_count':0,'o_pp_st_count':60,'o_effective_st_count':60,'o_timer_multiplier':1,'o_timeout_ms':245.76,'o_adaptive_mode':1};assert status(x)=='VALID'
 for patch in({'o_timeout_ms':0},{'o_timeout_ms':200},{'o_effective_st_count':50},{'o_timer_multiplier':2}):assert status({**x,**patch})=='INVALID'
 x.update(o_st_count=50,o_effective_st_count=50,o_timeout_ms=204.8);assert status(x)=='VALID'
 x.update(o_timer_multiplier=5,o_timeout_ms=1024);assert status(x)=='VALID'
 x.update(o_transport='J1850_PWM',bitrate_bps=41600);assert status(x)=='INVALID'
def test_obd2_sw_zero_disables_kline_wake_not_can_or_timeout():
 x={**actual('KWP_5BAUD'),'o_sw_count':146,'o_wake_interval_ms':2990.08,'o_wake_enabled':True,'o_wake_hex':'C133F13E','o_wake_bytes':4};assert status(x)=='VALID'
 assert status({**x,'o_wake_interval_ms':3000})=='INVALID'
 x.update(o_sw_count=0,o_wake_interval_ms=0,o_wake_enabled=False);assert status(x)=='VALID'
 assert status({**x,'o_wake_enabled':True})=='INVALID'
 assert status({**actual(),'o_wake_enabled':True})=='INVALID'
def test_obd2_flowcontrol_modes_known_ecu_early_return_and_long_requests_not_inferred():
 x={**actual(),'o_fc_mode':'CUSTOM_ID_DATA','o_fc_id':0x7e0,'o_fc_hex':'300000','o_fc_bytes':3};assert status(x)=='VALID'
 x.pop('o_fc_id');assert status(x)=='UNVERIFIED'
 x.update(o_fc_mode='RECEIVED_ID_CUSTOM_DATA');assert status(x)=='VALID'
 assert status({**x,'o_fc_id':0x7e0})=='INVALID';assert status({**x,'o_fc_bytes':6})=='INVALID'
 x={**actual(),'o_early_return':True};assert status(x)=='UNVERIFIED'
 x.update(o_expected_ecus=2,o_returned_ecus=2,o_filter_source='synthetic-matching-ECUs');assert status(x)=='VALID'
 assert status({**x,'o_returned_ecus':3})=='INVALID'
 x={**actual(),'o_request_bytes':8,'o_allow_long':True};assert status(x)=='INVALID'
 x.update(o_application='REGISTERED',o_registered_source='synthetic-extended-service');assert status(x)=='VALID'
 x.update(o_allow_long=False);assert status(x)=='INVALID'
def test_obd2_host_uart_and_chip_rails_are_device_qualified_not_vehicle_rates_or_absolute_stress():
 x={**actual(),'o_host_baud_pin':'LOW_FACTORY','o_host_baud':9600,'o_chip_vdd_v':4.2,'o_physical_source':'synthetic-chip-rail'};assert status(x)=='VALID'
 assert status({**x,'o_host_baud':10400})=='INVALID';assert status({**x,'o_chip_vdd_v':7.5})=='INVALID'
 x.update(o_host_baud_pin='HIGH_FACTORY',o_host_baud=38400);assert status(x)=='VALID'
 x.update(o_implementation='STN2120',o_host_baud_pin='CONFIGURED',o_host_baud=8000000,o_chip_vdd_v=3.6,o_ambient_c=85);assert status(x)=='VALID'
 for patch in({'o_host_baud':8000001},{'o_chip_vdd_v':4},{'o_ambient_c':125}):assert status({**x,**patch})=='INVALID'
def test_obd2_obdonuds_doip_has_no_classic_can_rate_ids_legacy_pids_or_4095_maximum():
 x=actual('DOIP_UDS','REGISTERED');x.update(o_response_bytes=5000);assert status(x)=='VALID'
 for patch in({'bitrate_bps':100000000},{'o_request_id':0x7df},{'o_application':'LEGACY_J1979'},{'o_packet_type':'FF'}):assert status({**x,**patch})=='INVALID'
 x.pop('o_registered_source');assert status(x)=='UNVERIFIED'
def test_obd2_confirmed_kline_timeout_adapter_settings_and_byte_identity_preserved():
 from backend.engineering.workflow.service import WorkflowStatusService
 from backend.engineering.project_context import current_project_id
 x={**actual('KWP_FAST'),'o_st_count':0,'o_pp_st_count':60,'o_effective_st_count':60,'o_timer_multiplier':1,
  'o_timeout_ms':245.76,'o_request_hex':'010C','o_request_bytes':2,'o_host_baud':115200,'o_host_baud_pin':'CONFIGURED'}
 g={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
 p={'technology':'obd2','technology_parameters':{'obd2':g}}
 service=WorkflowStatusService(current_project_id());service.save_parameters(p);assert service.get()['parameters']==p
 bad=deepcopy(p);bad['technology_parameters']['obd2']['values']['bitrate_bps']=250000
 with pytest.raises(ValueError):service.save_parameters(bad)
 assert service.get()['parameters']==p
