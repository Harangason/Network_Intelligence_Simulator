"""Source-qualified PWM waveform/driver parameters; frequency is not a bitrate."""
DOC='https://docs.kernel.org/6.18/driver-api/pwm.html'
HDR='https://raw.githubusercontent.com/torvalds/linux/v6.18/include/linux/pwm.h'
CORE='https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/pwm/core.c'
DT='https://raw.githubusercontent.com/torvalds/linux/v6.18/include/dt-bindings/pwm/pwm.h'
ST='https://www.st.com/content/ccc/resource/technical/document/application_note/54/0f/67/eb/47/34/45/40/DM00042534.pdf/files/DM00042534.pdf/jcr:content/translations/en.DM00042534.pdf'
SOURCES={DOC:'Linux6.18 PWM overview: platform-specific arguments, requested versus hardware state, disabled output not guaranteed inactive, apply/capture interfaces.',
 HDR:'Linux v6.18 include/linux/pwm.h: UInt64 nanosecond state/waveform, polarity, init duty0/usage_powerFalse, hardware-state getter and driver capabilities.',
 CORE:'Linux v6.18 drivers/pwm/core.c: enabled-only state validity, waveform S64_MAX/duty/offset bounds, exact versus integer-ns rounding, standard DT translation.',
 DT:'Linux v6.18 standard PWM DT binding flags: bit0 inverted, not a universal hardware polarity.',
 ST:'ST AN4013 Rev14 February2026 pp10-17/19/24/32-34: actual timer width/clock, prescaler/ARR, center versus edge cycle, PWM1/2/pin polarity, preload/UEV/capture and device-qualified deadtime/break. Public PDF read through browser; original local download unavailable.'}
DECLARATIONS=[]
U64=18446744073709551615
S64=9223372036854775807
def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,source=CORE,integer=False):
 DECLARATIONS.append(dict(key='pwm_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,integer=integer,source=source,source_revision=SOURCES[source]))
for k,meaning,opts,src in [
 ('profile','Actual reviewed API/peripheral edition or separately registered device profile.',['LINUX_STATE_6_18','LINUX_WAVEFORM_6_18','STM32_TIM_AN4013_R14','REGISTERED_ACTUAL'],DOC),
 ('phase','Actual operation versus explicitly requested platform-argument initialization proposal.',['ACTUAL','LINUX_INIT_STATE'],HDR),
 ('polarity','Normal activeHIGH/inversed activeLOW in the Linux state API; separate STM OC mode.',['NORMAL','INVERSED'],HDR),
 ('readback','Requested software state is not implemented hardware state or an observed waveform.',['REQUESTED_STATE','HARDWARE_STATE','CAPTURED_WAVEFORM','UNKNOWN'],DOC),
 ('disabled_level','Actual disabled output may remain active/inactive/high impedance/toggling; never assume LOW.',['HIGH','LOW','HIGH_Z','TOGGLING','UNKNOWN'],DOC),
 ('clock_source','Selected conventional STM TIM clock, not a universal PWM frequency default.',['INTERNAL_RCC','TI1','TI2','ETR','ITR','REGISTERED_ACTUAL'],ST),
 ('count_mode','Actual edge up/down or full up/down center triangle, not update-event frequency.',['UP','DOWN','CENTER'],ST),
 ('oc_mode','Actual STM output-reference comparator mode, independent of physical pin polarity.',['PWM1','PWM2','ASYMMETRIC','COMBINED','ONE_PULSE','REGISTERED_ACTUAL'],ST),
 ('pin_polarity','Actual physical output inversion after STM OC reference.',['ACTIVE_HIGH','ACTIVE_LOW'],ST),
 ('dt_translation','Actual source-qualified Linux standard DT translator or device-specific binding.',['STANDARD_LINUX_6_18','REGISTERED_ACTUAL'],CORE),
 ('outcome','Actual functional consumer acceptance, not valid driver configuration.',['ACCEPTED','REJECTED','PENDING','UNKNOWN'],DOC),
]:d(k,'select',meaning,options=opts,source=src)
for k,meaning,src in [
 ('device_source','Actual chip/timer firmware/driver/API version and supported period/duty/atomic/capture capabilities.',DOC),
 ('clock_source_evidence','Actual timer clock routing, stability, prescaling and achievable resolution.',ST),
 ('wiring_source','Actual assigned output/input pin, driver electrical levels, reference ground and load.',DOC),
 ('mapping_source','Actual consumer duty/pulse/value mapping, polarity and permitted operating range.',DOC),
 ('waveform_source','Actual correlated implemented/readback/captured waveform and rounding evidence.',CORE),
 ('acceptance_source','Actual consumer action, sample age, application update and fault/safe-state requirements.',DOC),
 ('registered_source','Actual separately registered alternate peripheral/mode/codec limits and semantics.',ST),
 ('chip_id','Actual Linux chip/peripheral identity, not CAN ECU or inferred bus master.',HDR),
 ('pin_id','Actual electrically connected PWM pin, not an invented signal address.',ST),
 ('safe_state_source','Actual plant/device required fault-state electrical behavior and observation, not disabled=>safe.',DOC),
]:d(k,'text',meaning,source=src)
for k,meaning,lo,hi,unit,src in [
 ('period_ns','Actual requested state period or waveform period; state0 allowed only disabled, waveform0 disables.',0,U64,'ns',HDR),
 ('duty_ns','Actual active duration; Linux inverse polarity active means LOW, not always physical HIGH.',0,U64,'ns',HDR),
 ('offset_ns','Actual waveform offset;0 permitted, positive must be strictly less than waveform period.',0,S64,'ns',CORE),
 ('inactive_ns','Actual non-active duration in the physically meaningful enabled waveform.',0,U64,'ns',HDR),
 ('high_ns','Actual physical HIGH duration; polarity affects relation with active duration.',0,U64,'ns',HDR),
 ('low_ns','Actual physical LOW duration, not always period-minus-HIGH inferred for disabled output.',0,U64,'ns',HDR),
 ('implemented_period_ns','Actual hardware-returned integer-ns period; requested state alone does not prove this.',0,U64,'ns',CORE),
 ('implemented_duty_ns','Actual hardware-returned active duration; fractional sub-ns quantization may remain.',0,U64,'ns',CORE),
 ('implemented_offset_ns','Actual returned waveform offset, not invented phase0.',0,S64,'ns',CORE),
 ('args_period_ns','Actual board/firmware reference argument, not hardware state or a generic servo20ms.',0,U64,'ns',HDR),
 ('dt_flags','Actual standard DT polarity bit; device-specific translators need their own binding source.',0,4294967295,None,DT),
 ('channel','Actual perchip channel index0..npwm-1; exclusive consumer ownership required.',0,4294967295,None,HDR),
 ('channels','Actual hardware npwm count, not inferred4channels for every timer.',1,4294967295,None,HDR),
 ('counter_bits','Actual selected conventional STM TIM counter width16 or32, not all PWM hardware.',1,64,'bit',ST),
 ('psc','Actual conventional STM 16bit prescaler register; division is PSC+1.',0,65535,None,ST),
 ('arr','Actual selected timer auto-reload register; device width bounds apply.',0,4294967295,None,ST),
 ('ccr','Actual compare register; CCR greater than ARR can represent constant level, not invalid by itself.',0,4294967295,None,ST),
 ('rcr','Actual supported repetition counter; updates differ from physical PWM periods.',0,65535,None,ST),
 ('rcr_bits','Actual selected timer repetition-register width, not a universal16bit capability.',1,16,'bit',ST),
 ('period_ticks','Actual full edge ARR+1 or center2*ARR counter ticks; repetition does not extend PWM period.',1,None,'tick',ST),
 ('psc_divider','Actual derived PSC+1 divider, including valid PSC0=>divide1.',1,65536,None,ST),
 ('repetition_divider','Actual derived RCR+1 update divider, not full waveform frequency divisor.',1,65536,None,ST),
 ('capture_period_ns','Actual Linux capture UInt32 nanosecond period, not generic waveform UInt64.',1,4294967295,'ns',HDR),
 ('capture_duty_ns','Actual Linux capture active duration, measured separately from requested output.',0,4294967295,'ns',HDR),
 ('capture_timeout_ms','Actual capture-call timeout in milliseconds, not waveform nanoseconds.',0,4294967295,'ms',HDR),
]:d(k,'number',meaning,lo,hi,unit,source=src,integer=True)
for k,meaning,lo,hi,unit,src in [
 ('frequency_hz','Actual full PWM cycle rate; does not encode bit/s or a framed payload.',0,None,'Hz',ST),
 ('duty_percent','Actual active fraction0..100%, not necessarily physical HIGH percentage.',0,100,'%',HDR),
 ('timer_clock_hz','Actual clock reaching the STM prescaler, after external routing/dividers where selected.',0,None,'Hz',ST),
 ('counter_clock_hz','Actual counter clock after PSC+1; device PLL/RCC default not invented.',0,None,'Hz',ST),
 ('update_event_hz','Actual overflow/underflow UEV cadence including RCR; distinct full PWM cycle.',0,None,'Hz',ST),
 ('capture_counter_hz','Actual counter frequency used by STM paired PWM-input capture.',0,None,'Hz',ST),
 ('capture_ccr_period','Actual reset-on-edge period capture register, not a software nanosecond value.',0,None,'tick',ST),
 ('capture_ccr_active','Actual paired active-duration capture register.',0,None,'tick',ST),
 ('captured_frequency_hz','Actual PWM-input measured frequency from counterclock/periodcapture.',0,None,'Hz',ST),
 ('captured_duty_percent','Actual measured active percentage from paired capture counts.',0,100,'%',ST),
 ('voltage_high_v','Actual electrical HIGH at loaded output, not a generic3.3V proposal.',0,None,'V',DOC),
 ('voltage_low_v','Actual electrical LOW at loaded output, not automatically0V.',0,None,'V',DOC),
 ('receiver_vih_v','Actual receiver guaranteed HIGH recognition lower limit.',0,None,'V',DOC),
 ('receiver_vil_v','Actual receiver guaranteed LOW recognition upper limit.',0,None,'V',DOC),
 ('update_bound_ms','Actual command-to-applied waveform/consumer bound, not a bus queue.',0,None,'ms',DOC),
 ('age_ms','Actual consumed setting/sample age.',0,None,'ms',DOC),
 ('freshness_ms','Actual application freshness requirement, no universal500ms.',0,None,'ms',DOC),
 ('deadtime_ns','Actual device-qualified complementary-output deadtime, not all timers support it.',0,None,'ns',ST),
 ('resolution_ns','Actual achieved timer/output timing quantum, not requested integer-ns precision.',0,None,'ns',CORE),
 ('jitter_bound_ns','Actual verified edge jitter bound, not default0.',0,None,'ns',DOC),
]:d(k,'number',meaning,lo,hi,unit,source=src)
for k,meaning,src in [
 ('enabled','Actual requested Linux PWM state enable, not proof of electrical output.',HDR),
 ('usage_power','Actual permission for driver phase optimization preserving power; cannot imply scheduled edges.',DOC),
 ('atomic_context','Actual Linux apply from non-sleeping context requiring atomic-capable chip.',CORE),
 ('chip_atomic','Actual selected driver/chip atomic apply capability, not enabled by default.',CORE),
 ('exclusive_owner','Actual channel allocation belongs to the intended consumer.',CORE),
 ('exact_integer_ns','Actual Linux waveform exact integer-ns request; not proof of zero fractional physical error.',CORE),
 ('waveform_verified','Actual independent implementation/readback/capture evidence is valid.',DOC),
 ('mapping_valid','Actual consumer mapping and polarity checked.',DOC),
 ('electrical_valid','Actual wiring/load/levels/ground checked against both endpoint specifications.',DOC),
 ('signal_accepted','Actual new functional PWM signal accepted by mapped consumer.',DOC),
 ('safe_state_verified','Actual requested fault/safe state observed, not inferred from disable.',DOC),
 ('preload','Actual STM ARR/CCR preload used; next UEV must latch settings.',ST),
 ('update_latched','Actual expected STM UEV latched preloaded output settings.',ST),
 ('advanced_capability','Actual asymmetric/combined/onepulse/complementary/break hardware support.',ST),
 ('complementary','Actual paired complementary outputs; deadtime/wiring/fault requirements separate.',ST),
 ('break_enabled','Actual selected STM break input protection configuration.',ST),
 ('break_active','Actual break event may force predefined OIS state; normal waveform not implied.',ST),
]:d(k,'boolean',meaning,source=src)
REQUIRED=['profile','device_source','clock_source_evidence','wiring_source','mapping_source','acceptance_source']
REMOVED={k:'PWM direct signal does not define '+k+'; actual waveform/driver/consumer parameters replace foreign packet transport.' for k in ('bitrate','mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','rate_limit_bit_s','retry_limit','retransmission_enabled','retransmission_rate','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms','sync_method')}
def semantics():
 rules=[]
 def r(k,w=None,source=CORE,**kw):rules.append(dict(parameter=k if k=='local_timing_evidence'else'pwm_'+k,when={'pwm_'+a:b for a,b in(w or{}).items()},source=source,source_revision=SOURCES[source],**kw))
 for k in REQUIRED:r(k,required=True)
 r('local_timing_evidence',allowed=[])
 for k in ('profile','clock_source','oc_mode','dt_translation'):r('registered_source',{k:'REGISTERED_ACTUAL'},required=True)
 w={'profile':'LINUX_STATE_6_18','enabled':True}
 r('period_ns',w,required=True,minimum=1);r('duty_ns',w,required=True,maximum_parameter='pwm_period_ns')
 w={'profile':'LINUX_WAVEFORM_6_18'}
 r('period_ns',w,required=True,maximum=S64);r('duty_ns',w,required=True,maximum_parameter='pwm_period_ns');r('offset_ns',w,required=True)
 r('offset_ns',w,when_positive=['pwm_offset_ns'],exclusive_maximum_expression='pwm_period_ns')
 r('enabled',{'profile':'LINUX_WAVEFORM_6_18','period_ns':0},allowed=[False])
 r('enabled',w,when_positive=['pwm_period_ns'],allowed=[True])
 r('implemented_duty_ns',w,maximum_parameter='pwm_implemented_period_ns')
 r('implemented_period_ns',w,when_present=['pwm_implemented_duty_ns'],required=True,maximum=S64)
 r('implemented_offset_ns',w,when_positive=['pwm_implemented_offset_ns'],exclusive_maximum_expression='pwm_implemented_period_ns')
 r('implemented_period_ns',w,when_present=['pwm_implemented_offset_ns'],required=True,maximum=S64)
 for profile in('LINUX_STATE_6_18','LINUX_WAVEFORM_6_18'):
  for k in('clock_source','count_mode','oc_mode','pin_polarity','counter_bits','psc','arr','ccr','rcr','rcr_bits','period_ticks','psc_divider','repetition_divider','timer_clock_hz','counter_clock_hz','update_event_hz','capture_counter_hz','capture_ccr_period','capture_ccr_active','captured_frequency_hz','captured_duty_percent','preload','update_latched'):
   r(k,{'profile':profile},allowed=[],source=ST)
 for k in('offset_ns','exact_integer_ns'):r(k,{'profile':'LINUX_STATE_6_18'},allowed=[])
 r('channel',exclusive_maximum_expression='pwm_channels');r('channels',when_present=['pwm_channel'],required=True)
 r('exclusive_owner',when_present=['pwm_channel'],required=True,allowed=[True])
 r('chip_atomic',{'atomic_context':True},required=True,allowed=[True])
 r('polarity',{'dt_translation':'STANDARD_LINUX_6_18','dt_flags':0},allowed=['NORMAL'])
 r('polarity',{'dt_translation':'STANDARD_LINUX_6_18','dt_flags':1},allowed=['INVERSED'])
 # Unknown standard-DT flag bits must not silently become device capabilities.
 r('dt_flags',{'dt_translation':'STANDARD_LINUX_6_18'},allowed=[0,1],source=DT)
 for k in('frequency_hz','duty_percent','inactive_ns','high_ns','low_ns'):
  r('period_ns',when_present=['pwm_'+k],required=True,minimum=1)
 r('frequency_hz',equal_ratio={'numerator_offset':1000000000,'denominator_product':['pwm_period_ns'],'denominator_offset':1})
 r('duty_percent',equal_ratio={'numerator_parameter':'pwm_duty_ns','factor':100,'denominator_product':['pwm_period_ns'],'denominator_offset':1})
 r('duty_percent',{'duty_ns':0},allowed=[0])
 for k in('duty_percent','inactive_ns'):r('duty_ns',when_present=['pwm_'+k],required=True)
 r('inactive_ns',equal_expression={'subtract':['pwm_period_ns','pwm_duty_ns']})
 for polarity,high,low in [('NORMAL','pwm_duty_ns',{'subtract':['pwm_period_ns','pwm_duty_ns']}),('INVERSED',{'subtract':['pwm_period_ns','pwm_duty_ns']},'pwm_duty_ns')]:
  r('high_ns',{'polarity':polarity},equal_expression=high);r('low_ns',{'polarity':polarity},equal_expression=low)
 for k in('high_ns','low_ns'):r('polarity',when_present=['pwm_'+k],required=True);r('duty_ns',when_present=['pwm_'+k],required=True)
 r('capture_duty_ns',maximum_parameter='pwm_capture_period_ns');r('capture_period_ns',when_present=['pwm_capture_duty_ns'],required=True)
 for k in('period_ns','duty_ns','offset_ns'):
  r('implemented_'+k,{'profile':'LINUX_WAVEFORM_6_18','exact_integer_ns':True},equal_parameter='pwm_'+k)
 # Hardware integer-ns agreement does not certify finer physical timing or electrical safety.
 for k in('timer_clock_hz','counter_clock_hz','capture_counter_hz','capture_ccr_period','resolution_ns'):r(k,exclusive_minimum=0)
 w={'profile':'STM32_TIM_AN4013_R14'}
 r('counter_bits',w,allowed=[16,32],source=ST)
 for k in('arr','ccr'):r(k,w,maximum_expression={'subtract':[{'power':[2,'pwm_counter_bits']},1]},source=ST);r('counter_bits',w,when_present=['pwm_'+k],required=True,source=ST)
 r('rcr',w,maximum_expression={'subtract':[{'power':[2,'pwm_rcr_bits']},1]},source=ST);r('rcr_bits',w,when_present=['pwm_rcr'],required=True,source=ST)
 r('psc_divider',w,equal_expression={'sum':['pwm_psc',1]},source=ST)
 r('repetition_divider',w,equal_expression={'sum':['pwm_rcr',1]},source=ST)
 r('psc',w,when_present=['pwm_psc_divider'],required=True,source=ST)
 r('rcr',w,when_present=['pwm_repetition_divider'],required=True,source=ST)
 r('counter_clock_hz',w,equal_ratio={'numerator_parameter':'pwm_timer_clock_hz','denominator_product':['pwm_psc_divider'],'denominator_offset':1},source=ST)
 for k in('psc_divider','timer_clock_hz'):r(k,w,when_present=['pwm_counter_clock_hz'],required=True,source=ST)
 for mode in('UP','DOWN'):
  x={**w,'pwm_count_mode':mode};x={k.removeprefix('pwm_'):v for k,v in x.items()}
  r('period_ticks',x,equal_expression={'sum':['pwm_arr',1]},source=ST)
  r('update_event_hz',x,equal_ratio={'numerator_parameter':'pwm_counter_clock_hz','denominator_product':['pwm_period_ticks','pwm_repetition_divider'],'denominator_offset':1},source=ST)
 r('period_ticks',{'profile':'STM32_TIM_AN4013_R14','count_mode':'CENTER'},equal_expression={'product':[2,'pwm_arr']},source=ST)
 r('arr',{'profile':'STM32_TIM_AN4013_R14','count_mode':'CENTER'},minimum=1,source=ST)
 r('update_event_hz',{'profile':'STM32_TIM_AN4013_R14','count_mode':'CENTER'},equal_ratio={'numerator_parameter':'pwm_counter_clock_hz','factor':2,'denominator_product':['pwm_period_ticks','pwm_repetition_divider'],'denominator_offset':1},source=ST)
 for k in('period_ticks','update_event_hz'):r('arr',w,when_present=['pwm_'+k],required=True,source=ST);r('count_mode',w,when_present=['pwm_'+k],required=True,source=ST)
 for k in('counter_clock_hz','period_ticks','repetition_divider'):r(k,w,when_present=['pwm_update_event_hz'],required=True,source=ST)
 # Full PWM cadence excludes repetition-counter division; use declared full-cycle ticks.
 r('frequency_hz',w,equal_ratio={'numerator_parameter':'pwm_counter_clock_hz','denominator_product':['pwm_period_ticks'],'denominator_offset':1},source=ST)
 for k in('counter_clock_hz','period_ticks'):r(k,w,when_present=['pwm_frequency_hz'],required=True,source=ST)
 r('captured_frequency_hz',w,equal_ratio={'numerator_parameter':'pwm_capture_counter_hz','denominator_product':['pwm_capture_ccr_period'],'denominator_offset':1},source=ST)
 r('captured_duty_percent',w,equal_ratio={'numerator_parameter':'pwm_capture_ccr_active','factor':100,'denominator_product':['pwm_capture_ccr_period'],'denominator_offset':1},source=ST)
 r('captured_duty_percent',{'profile':'STM32_TIM_AN4013_R14','capture_ccr_active':0},allowed=[0],source=ST)
 for k in('captured_frequency_hz','captured_duty_percent'):
  r('capture_ccr_period',w,when_present=['pwm_'+k],required=True,source=ST)
 r('capture_counter_hz',w,when_present=['pwm_captured_frequency_hz'],required=True,source=ST)
 r('capture_ccr_active',w,when_present=['pwm_captured_duty_percent'],required=True,source=ST)
 r('capture_ccr_active',w,maximum_parameter='pwm_capture_ccr_period',source=ST)
 for mode in('ASYMMETRIC','COMBINED','ONE_PULSE'):r('advanced_capability',{'profile':'STM32_TIM_AN4013_R14','oc_mode':mode},required=True,allowed=[True],source=ST);r('registered_source',{'profile':'STM32_TIM_AN4013_R14','oc_mode':mode},required=True,source=ST)
 for k in('complementary','break_enabled'):r('advanced_capability',{k:True},required=True,allowed=[True],source=ST)
 r('deadtime_ns',{'complementary':True},required=True,source=ST)
 r('voltage_high_v',minimum_parameter='pwm_receiver_vih_v');r('voltage_low_v',maximum_parameter='pwm_receiver_vil_v')
 r('receiver_vil_v',maximum_parameter='pwm_receiver_vih_v')
 r('age_ms',maximum_parameter='pwm_freshness_ms');r('freshness_ms',when_present=['pwm_age_ms'],required=True)
 r('signal_accepted',{'break_active':True},allowed=[False],source=ST)
 r('update_latched',{'profile':'STM32_TIM_AN4013_R14','preload':True,'signal_accepted':True},required=True,allowed=[True],source=ST)
 w={'signal_accepted':True}
 for k,values in [('outcome',['ACCEPTED']),('waveform_verified',[True]),('mapping_valid',[True]),('electrical_valid',[True]),('exclusive_owner',[True]),('readback',['HARDWARE_STATE','CAPTURED_WAVEFORM'])]:r(k,w,required=True,allowed=values)
 for k in('waveform_source','age_ms','freshness_ms','update_bound_ms'):r(k,w,required=True)
 r('safe_state_source',{'safe_state_verified':True},required=True)
 r('waveform_source',{'safe_state_verified':True},required=True)
 return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['pwm_'+k for k in REQUIRED],native_parameter_prefixes=['pwm_'],
  parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='explicit_pwm_driver_waveform',medium_access_model='DEDICATED_DIRECT_SIGNAL',
  arbitration_model_id='ACTUAL_CHIP_CHANNEL_EXCLUSIVE_OWNER',mechanisms={'encoding':['ACTUAL_PERIOD_ACTIVE_DURATION_POLARITY'],
   'qualification':['NO_UNIVERSAL_FREQUENCY_OR_BITRATE','REQUESTED_STATE_IS_NOT_OBSERVED_WAVEFORM','DISABLED_OUTPUT_LEVEL_UNSPECIFIED']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][4:];v={a:b for a,b in spec.items()if b is not None}
  v.update(label=k.replace('_',' '),category='timing'if spec.get('unit')in('ns','ms','Hz','tick')else'physical',scope='route',editable=True,
   required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  # Source-defined initialization values are conditional; actual device settings are retained.
  if k in('duty_ns','usage_power'):
   v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'pwm_profile':'LINUX_STATE_6_18','pwm_phase':'LINUX_INIT_STATE'},value=0 if k=='duty_ns'else False,source=HDR,source_revision=SOURCES[HDR])])
  if k=='clock_source':v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'pwm_profile':'STM32_TIM_AN4013_R14'},value='INTERNAL_RCC',source=ST,source_revision=SOURCES[ST])])
  result.append(v)
 return result
