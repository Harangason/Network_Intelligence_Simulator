"""PWM driver semantics and hardware evidence stay separate from framed buses."""
from copy import deepcopy
import pytest
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import pwm as P
def actual(profile='LINUX_STATE_6_18'):
 return {**{'pwm_'+k:'synthetic-'+k for k in P.REQUIRED},'pwm_profile':profile}
def status(x):return registry.validate_parameters('pwm',x)['status']
def test_pwm_no_rate_payload_ceiling_can_queue_or_capacity_claim():
 p=registry.profile('pwm');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['local_timing_schema']==[]  # Retired loose bounds are not the native driver/waveform model.
 assert p['capacity_evidence']['status']=='NOT_APPLICABLE'and status(actual())=='VALID'
 f=registry.parameter_fields('pwm');assert len(f)==len({v['key']for v in f})and not set(P.REMOVED)&{v['key']for v in f}
 assert status({})=='UNVERIFIED'
 for bad in({'bitrate_bps':500000},{'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'
 assert status({**actual(),'payload_bytes':2000})=='VALID'

def test_disabled_legacy_evidence_groups_are_not_offered_by_any_device_schema():
 for profile in registry.profiles():
  rejects_local=any(rule.get('parameter')=='local_timing_evidence'and rule.get('allowed')==[]
   and not rule.get('when')and not rule.get('when_present')and not rule.get('when_positive')
   for rule in profile.get('parameter_constraints',[]))
  if rejects_local:assert profile['local_timing_schema']==[],profile['id']
@pytest.mark.parametrize('field',registry.parameter_fields('pwm'),ids=lambda f:f['key'])
def test_pwm_each_exported_field_type_and_outer_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,delta in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+delta})=='INVALID'
def test_pwm_default_only_explicit_platform_initialization_not_servo_or_bitrate():
 f={v['key']:v for v in registry.parameter_fields('pwm')};assert 'bitrate'not in f
 for k in('frequency_hz','period_ns','polarity','voltage_high_v','safe_state_verified','device_source'):
  assert 'default'not in f['pwm_'+k]and 'conditional_defaults'not in f['pwm_'+k]
 for k,value in [('duty_ns',0),('usage_power',False)]:
  v=f['pwm_'+k]['conditional_defaults'][0];assert v['value']==value and v['when']=={'pwm_profile':'LINUX_STATE_6_18','pwm_phase':'LINUX_INIT_STATE'}
 assert f['pwm_clock_source']['conditional_defaults'][0]['when']=={'pwm_profile':'STM32_TIM_AN4013_R14'}
@pytest.mark.parametrize('period,duty',[(1,0),(100,100),(P.U64,P.U64)])
def test_pwm_enabled_state_positive_period_duty_within_period(period,duty):
 x={**actual(),'pwm_enabled':True,'pwm_period_ns':period,'pwm_duty_ns':duty};assert status(x)=='VALID'
 assert status({**x,'pwm_period_ns':0})=='INVALID'
 if period<P.U64:assert status({**x,'pwm_duty_ns':period+1})=='INVALID'
def test_pwm_disabled_state_ignores_inapplicable_period_and_duty_not_forced_low():
 x={**actual(),'pwm_enabled':False,'pwm_period_ns':0,'pwm_duty_ns':1,'pwm_disabled_level':'HIGH'}
 assert status(x)=='VALID'
 assert status({**x,'pwm_signal_accepted':True})=='UNVERIFIED'
def test_pwm_enabled_missing_requested_state_is_unverified():
 assert status({**actual(),'pwm_enabled':True})=='UNVERIFIED'
@pytest.mark.parametrize('period,duty,offset',[(0,0,0),(100,0,0),(100,100,99),(100,75,50),(P.S64,0,0)])
def test_pwm_waveform_can_wrap_active_segment_and_zero_period_disables(period,duty,offset):
 x={**actual('LINUX_WAVEFORM_6_18'),'pwm_period_ns':period,'pwm_duty_ns':duty,'pwm_offset_ns':offset};assert status(x)=='VALID'
 assert status({**x,'pwm_duty_ns':period+1})=='INVALID'
 assert status({**x,'pwm_offset_ns':max(1,period)})=='INVALID'
 assert status({**x,'pwm_period_ns':P.S64+1})=='INVALID'
def test_pwm_waveform_has_all_three_actual_fields_required():
 x={**actual('LINUX_WAVEFORM_6_18'),'pwm_period_ns':100,'pwm_duty_ns':50,'pwm_offset_ns':0}
 for k in('period_ns','duty_ns','offset_ns'):
  y=deepcopy(x);y.pop('pwm_'+k);assert status(y)=='UNVERIFIED'
@pytest.mark.parametrize('polarity,high,low',[('NORMAL',25,75),('INVERSED',75,25)])
def test_pwm_active_duration_is_not_always_physical_high(polarity,high,low):
 x={**actual(),'pwm_enabled':True,'pwm_period_ns':100,'pwm_duty_ns':25,'pwm_polarity':polarity,
  'pwm_inactive_ns':75,'pwm_high_ns':high,'pwm_low_ns':low,'pwm_frequency_hz':10000000,'pwm_duty_percent':25}
 assert status(x)=='VALID'
 for bad in({'pwm_high_ns':26},{'pwm_frequency_hz':100},{'pwm_duty_percent':75},{'pwm_inactive_ns':25}):assert status({**x,**bad})=='INVALID'
def test_pwm_zero_active_fraction_still_checked_not_skipped_ratio():
 x={**actual(),'pwm_period_ns':100,'pwm_duty_ns':0,'pwm_duty_percent':0};assert status(x)=='VALID'
 assert status({**x,'pwm_duty_percent':50})=='INVALID'
 x.pop('pwm_duty_ns');assert status(x)=='UNVERIFIED'
def test_pwm_chip_channel_exclusive_and_atomic_require_actual_capabilities():
 x={**actual(),'pwm_channel':3,'pwm_channels':4,'pwm_exclusive_owner':True,'pwm_atomic_context':True,'pwm_chip_atomic':True};assert status(x)=='VALID'
 for bad in({'pwm_channel':4},{'pwm_exclusive_owner':False},{'pwm_chip_atomic':False}):assert status({**x,**bad})=='INVALID'
 for k in('channels','exclusive_owner','chip_atomic'):
  y=deepcopy(x);y.pop('pwm_'+k);assert status(y)=='UNVERIFIED'
@pytest.mark.parametrize('flags,polarity',[(0,'NORMAL'),(1,'INVERSED')])
def test_pwm_standard_dt_bit0_is_not_universal_device_polarity(flags,polarity):
 x={**actual(),'pwm_dt_translation':'STANDARD_LINUX_6_18','pwm_dt_flags':flags,'pwm_polarity':polarity};assert status(x)=='VALID'
 assert status({**x,'pwm_polarity':'NORMAL'if polarity=='INVERSED'else'INVERSED'})=='INVALID'
 assert status({**x,'pwm_dt_flags':2})=='INVALID'
 assert status({**x,'pwm_dt_translation':'REGISTERED_ACTUAL','pwm_dt_flags':2})=='UNVERIFIED'
def test_pwm_exact_integer_ns_does_not_accept_different_returned_integer_waveform():
 x={**actual('LINUX_WAVEFORM_6_18'),'pwm_period_ns':100,'pwm_duty_ns':40,'pwm_offset_ns':10,'pwm_exact_integer_ns':True,
  'pwm_implemented_period_ns':100,'pwm_implemented_duty_ns':40,'pwm_implemented_offset_ns':10};assert status(x)=='VALID'
 for k in('period_ns','duty_ns','offset_ns'):assert status({**x,'pwm_implemented_'+k:x['pwm_'+k]-1})=='INVALID'
def test_pwm_linux_state_waveform_and_stm_timer_fields_not_interchangeable():
 for bad in({'pwm_arr':9},{'pwm_clock_source':'INTERNAL_RCC'},{'pwm_offset_ns':0},{'pwm_exact_integer_ns':True}):assert status({**actual(),**bad})=='INVALID'
 x={**actual('LINUX_WAVEFORM_6_18'),'pwm_period_ns':0,'pwm_duty_ns':0,'pwm_offset_ns':0};assert status(x)=='VALID'
 assert status({**x,'pwm_enabled':True})=='INVALID'
 assert status({**x,'pwm_implemented_period_ns':100,'pwm_implemented_duty_ns':101})=='INVALID'
def timer(mode='UP'):
 ticks=10 if mode!='CENTER'else 18
 return {**actual('STM32_TIM_AN4013_R14'),'pwm_timer_clock_hz':1000000,'pwm_psc':0,'pwm_psc_divider':1,'pwm_counter_clock_hz':1000000,
  'pwm_counter_bits':16,'pwm_arr':9,'pwm_ccr':12,'pwm_count_mode':mode,'pwm_period_ticks':ticks,'pwm_rcr':1,'pwm_rcr_bits':8,
  'pwm_repetition_divider':2,'pwm_update_event_hz':1000000/(ticks*2)*(2 if mode=='CENTER'else 1),
  'pwm_period_ns':ticks*1000,'pwm_frequency_hz':1000000/ticks}
@pytest.mark.parametrize('mode',['UP','DOWN','CENTER'])
def test_pwm_stm_full_cycle_not_rcr_update_event_cadence_or_arr_plus_one_center(mode):
 x=timer(mode);assert status(x)=='VALID'
 for bad in({'pwm_psc_divider':2},{'pwm_repetition_divider':1},{'pwm_update_event_hz':100},{'pwm_period_ticks':11},{'pwm_frequency_hz':100}):assert status({**x,**bad})=='INVALID'
def test_pwm_stm_zero_psc_and_rcr_are_valid_divide_by_one():
 x={**timer(),'pwm_rcr':0,'pwm_repetition_divider':1,'pwm_update_event_hz':100000};assert status(x)=='VALID'
 assert status({**x,'pwm_counter_clock_hz':500000})=='INVALID'
def test_pwm_stm_actual_16_vs32bit_register_and_repetition_width():
 x={**actual('STM32_TIM_AN4013_R14'),'pwm_counter_bits':16,'pwm_arr':65535,'pwm_ccr':65535,'pwm_rcr_bits':8,'pwm_rcr':255};assert status(x)=='VALID'
 for bad in({'pwm_arr':65536},{'pwm_ccr':65536},{'pwm_counter_bits':24},{'pwm_rcr':256}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'pwm_counter_bits':32,'pwm_arr':4294967295})=='VALID'
def test_pwm_stm_missing_derived_inputs_not_inferred_from_hardware_defaults():
 x=timer()
 for k in('psc','psc_divider','counter_clock_hz','arr','count_mode','rcr','rcr_bits','repetition_divider'):
  y=deepcopy(x);y.pop('pwm_'+k);assert status(y)=='UNVERIFIED'
def test_pwm_stm_paired_capture_frequency_and_active_fraction_not_output_settings():
 x={**actual('STM32_TIM_AN4013_R14'),'pwm_capture_counter_hz':1000000,'pwm_capture_ccr_period':100,'pwm_capture_ccr_active':25,
  'pwm_captured_frequency_hz':10000,'pwm_captured_duty_percent':25};assert status(x)=='VALID'
 for bad in({'pwm_captured_frequency_hz':1000000},{'pwm_captured_duty_percent':75},{'pwm_capture_ccr_period':0},{'pwm_capture_ccr_active':101}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'pwm_capture_ccr_active':0,'pwm_captured_duty_percent':0})=='VALID'
 assert status({**x,'pwm_capture_ccr_active':0,'pwm_captured_duty_percent':25})=='INVALID'
def test_pwm_linux_capture_uint32_and_timeout_ms_not_uint64_ns_state():
 x={**actual(),'pwm_capture_period_ns':100,'pwm_capture_duty_ns':50,'pwm_capture_timeout_ms':10};assert status(x)=='VALID'
 assert status({**x,'pwm_capture_duty_ns':101})=='INVALID'
 assert status({**x,'pwm_capture_period_ns':4294967296})=='INVALID'
@pytest.mark.parametrize('mode',['ASYMMETRIC','COMBINED','ONE_PULSE'])
def test_pwm_advanced_modes_require_real_capability_and_independently_registered_layout(mode):
 x={**actual('STM32_TIM_AN4013_R14'),'pwm_oc_mode':mode};assert status(x)=='UNVERIFIED'
 x.update(pwm_advanced_capability=True,pwm_registered_source='synthetic-peripheral-layout');assert status(x)=='VALID'
 assert status({**x,'pwm_advanced_capability':False})=='INVALID'
def accepted():
 return {**actual(),'pwm_signal_accepted':True,'pwm_outcome':'ACCEPTED','pwm_waveform_verified':True,'pwm_mapping_valid':True,
  'pwm_electrical_valid':True,'pwm_exclusive_owner':True,'pwm_readback':'CAPTURED_WAVEFORM','pwm_waveform_source':'synthetic-scope',
  'pwm_age_ms':10,'pwm_freshness_ms':20,'pwm_update_bound_ms':5}
@pytest.mark.parametrize('bad',[{'pwm_waveform_verified':False},{'pwm_mapping_valid':False},{'pwm_electrical_valid':False},
 {'pwm_readback':'REQUESTED_STATE'},{'pwm_age_ms':21},{'pwm_break_active':True},{'pwm_outcome':'PENDING'}])
def test_pwm_requested_valid_config_or_break_does_not_prove_functional_acceptance(bad):
 assert status(accepted())=='VALID';assert status({**accepted(),**bad})=='INVALID'
def test_pwm_preload_requires_actual_update_latch_and_safe_state_independent_source():
 x={**accepted(),'pwm_profile':'STM32_TIM_AN4013_R14','pwm_preload':True};assert status(x)=='UNVERIFIED'
 assert status({**x,'pwm_update_latched':False})=='INVALID';assert status({**x,'pwm_update_latched':True})=='VALID'
 y={**actual(),'pwm_enabled':False,'pwm_disabled_level':'LOW','pwm_safe_state_verified':True};assert status(y)=='UNVERIFIED'
 y.update(pwm_safe_state_source='synthetic-requiredplantstate',pwm_waveform_source='synthetic-observation');assert status(y)=='VALID'
def test_pwm_confirmed_actuator_frequency_duty_and_polarity_are_retained():
 x={**actual(),'pwm_period_ns':2000000,'pwm_duty_ns':700000,'pwm_duty_percent':35,'pwm_frequency_hz':500,
  'pwm_polarity':'INVERSED','parameter_provenance':{'pwm_frequency_hz':{'status':'CONFIRMED','value':500}}}
 before=deepcopy(x);assert status(x)=='VALID'and x==before
