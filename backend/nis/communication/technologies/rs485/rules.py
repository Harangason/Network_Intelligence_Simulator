"""RS485 electrical multipoint bus, independent from its selected wire protocol."""
TI='https://www.ti.com/lit/an/slla070d/slla070d.pdf'
GUIDE='https://www.ti.com/lit/an/slla272d/slla272d.pdf'
SOURCES={TI:'TI SLLA070D revisedMay2010 actualpp9-13/17-18/20-23; selected electrical test conditions, not full licensed ANSI standard.',GUIDE:'TI SLLA272D revisedMay2021 actualpp1-7; topology, UL, physical design formulas, actual recommendations not universal device guarantees.'}
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,integer=False,source=TI):
 DECLARATIONS.append(dict(key='rs485_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,integer=integer,source=source,source_revision=SOURCES[source]))
for k,meaning,opts in [
 ('profile','Selected electrical test reference versus independently qualified actual devices.',['TIA_485_TI2010','DEVICE_QUALIFIED','REGISTERED_ACTUAL']),
 ('topology','Actual balanced bus with electrically short stubs, or independently qualified alternative.',['BUS_DAISY_CHAIN','REGISTERED_ACTUAL']),
 ('direction','Half duplex uses one pair; full duplex two independently controlled pairs, not simultaneous competing drivers per pair.',['HALF_DUPLEX_ONE_PAIR','FULL_DUPLEX_TWO_PAIRS']),
 ('load_model','Actual homogeneous identical UL contribution versus individually measured aggregate bus load.',['HOMOGENEOUS_ACTUAL','AGGREGATE_MEASURED']),
 ('cable_profile','Selected TI recommended120ohm UTP proposal versus actual independently selected cable.',['TI_RECOMMENDED_120_OHM_UTP','ACTUAL_OTHER']),
 ('termination','Actual two-end parallel or split termination, qualified unterminated/alternative implementation.',['PARALLEL_TWO_ENDS','SPLIT_TWO_ENDS','NONE_QUALIFIED','REGISTERED_ACTUAL']),
 ('load_scope','Actual electrical fixture: open,54ohm with50pF waveform,60ohm with375ohm commonmode loading, or application.',['OPEN_CIRCUIT','STANDARD_54_OHM','STANDARD_CM_60_375','APPLICATION']),
 ('activity','Actual scheduled frame, idle, open, short, or contention state. Failsafe idle is not a new valid message.',['FRAME','IDLE','OPEN','SHORT','CONTENTION']),
 ('logic_mapping','Actual VA-VB device truth table; A/B letters alone do not prove logical polarity.',['POSITIVE_IS_1','POSITIVE_IS_0','REGISTERED_ACTUAL']),
 ('decoded_logic','Actual observed resulting logical bit.',['ONE','ZERO']),
 ('failsafe','Actual commissioned internal/external failsafe or no specified behavior.',['NOT_SPECIFIED','INTERNAL_PROVEN','EXTERNAL_PROVEN']),
 ('ground_scheme','Actual return path/ground potential and optional isolation commissioning, never automatic protective-earth return.',['QUALIFIED_COMMON_REFERENCE','SIGNAL_AND_SUPPLY_ISOLATED','REGISTERED_ACTUAL']),
 ('wire_protocol','Actual codec and media scheduling separate from electrical RS485.',['REGISTERED_ACTUAL']),
 ('outcome','Actual complete decoded transaction and functional acceptance status.',['ACCEPTED','ELECTRICAL_FAULT','CONTENTION','FRAMING_ERROR','STALE','UNKNOWN']),
]:d(k,'select',meaning,options=opts)
for k,meaning,lo,hi,unit,integer in [
 ('bitrate_bps','Actual serialized rate under selected driver/receiver/cable; no normative minimum or default10Mbps.',0,None,'bit/s',False),
 ('device_max_bps','Actual driver maximum under commissioned electrical conditions.',0,None,'bit/s',False),
 ('peer_max_bps','Actual receiver maximum under same conditions.',0,None,'bit/s',False),
 ('nodes','Actual connected transceiver count;32UL is not automatically32devices.',1,None,None,True),
 ('drivers','Actual connected drivers per pair, many allowed but only one active.',1,None,None,True),
 ('active_drivers','Actual simultaneously enabled drivers per pair;0idle/1frame, never2without contention.',0,None,None,True),
 ('unit_load','Actual receiver/poweroff driver UL per node, not universal1/8UL.',0,None,'UL',False),
 ('receiver_load_ul','Actual aggregate receiver/poweroff driver bus load.',0,None,'UL',False),
 ('bias_load_ul','Actual externally applied failsafe loading, not universal20UL.',0,None,'UL',False),
 ('total_load_ul','Actual receiver/poweroff driver plus bias total; selected standard driver supports32UL.',0,None,'UL',False),
 ('driver_diff_abs_v','Actual differential output magnitude under declared fixture.',0,None,'V',False),
 ('driver_a_v','Actual signed individual outputA under unloaded fixture.',None,None,'V',False),
 ('driver_b_v','Actual signed individual outputB under unloaded fixture.',None,None,'V',False),
 ('driver_offset_v','Actual signed offset -1..3V in selected loaded test, not absolute-value misreading.',None,None,'V',False),
 ('driver_diff_delta_abs_v','Actual output polarity imbalance<=.2V.',0,None,'V',False),
 ('driver_offset_delta_abs_v','Actual offset imbalance<=.2V.',0,None,'V',False),
 ('short_test_v','Actual applied output short stress -7..12V, not normal bus differential voltage.',None,None,'V',False),
 ('short_current_abs_ma','Actual short current<=250mA under stated stress and duration.',0,None,'mA',False),
 ('receiver_a_v','Actual signed receiver pinA waveform.',None,None,'V',False),
 ('receiver_b_v','Actual signed receiver pinB waveform.',None,None,'V',False),
 ('receiver_common_v','Actual(VA+VB)/2, standard -7..12V differs RS422±7V.',None,None,'V',False),
 ('receiver_diff_v','Actual VA-VB signed differential, conventional±200mV sensitivity.',None,None,'V',False),
 ('receiver_diff_abs_v','Actual differential magnitude, must also satisfy selected device absolute limits.',0,None,'V',False),
 ('fixture_ohm','Actual54ohm waveform fixture only, not installed termination.',0,None,'ohm',False),
 ('fixture_pf','Actual50pF waveform fixture only, not cable capacitance.',0,None,'pF',False),
 ('rise_ns','Actual monotonic10-90percent loaded rise, standard<=.3UI.',0,None,'ns',False),
 ('fall_ns','Actual loaded fall under same fixture.',0,None,'ns',False),
 ('unit_interval_ns','Actual1e9/bitrate bit interval.',0,None,'ns',False),
 ('overshoot_percent','Actual overshoot/undershoot after transition<=10percent full differential swing.',0,None,'percent',False),
 ('cable_m','Actual cable length;1200m/10Mbps examples not simultaneous guaranteed limits.',0,None,'m',False),
 ('cable_impedance_ohm','Actual cable characteristic impedance;120ohm is source recommendation, not every installed cable.',0,None,'ohm',False),
 ('termination_ohm','Actual effective per-end termination matching line characteristic impedance.',0,None,'ohm',False),
 ('termination_count','Actual per-pair termination count, two cable ends in parallel/split design.',0,None,None,True),
 ('split_resistor_ohm','Actual each split resistor, sum pair forms effective per-end termination.',0,None,'ohm',False),
 ('split_filter_pf','Actual split commonmode filter capacitor,220pF sourceexample not a standard default.',0,None,'pF',False),
 ('stub_m','Actual transceiver-to-trunk branch length.',0,None,'m',False),
 ('velocity_fraction','Actual cable propagation speed as fraction of vacuum light speed, not generic78percent.',0,1,None,False),
 ('stub_delay_ns','Actual one-way electrical stub delay; TIguideline<=rise/10.',0,None,'ns',False),
 ('media_pf_m','Actual distributed medium capacitance per metre.',0,None,'pF/m',False),
 ('node_cap_pf','Actual lumped node load including pins/connector/PCB/protection.',0,None,'pF',False),
 ('spacing_m','Actual minimum node separation; TIguideline>5.25CL/Cmedia.',0,None,'m',False),
 ('loaded_impedance_ohm','Actual loaded distributed impedance, TIguideline>.4Z0.',0,None,'ohm',False),
 ('noise_abs_mv','Actual maximum differential noise for commissioned failsafe margin.',0,None,'mV',False),
 ('bias_diff_v','Actual external failsafe differential including200mV threshold+noise.',0,None,'V',False),
 ('bias_supply_min_v','Actual minimum bias supply used for resistor calculation.',0,None,'V',False),
 ('bias_max_ohm','Source guide maximum bias resistance Vmin*375*Z0/[VAB*(Z0+1500)], distinct selected resistor.',0,None,'ohm',False),
 ('bias_selected_ohm','Actual installed bias resistor each, not universal523ohm.',0,None,'ohm',False),
 ('ground_diff_v','Actual installed ground potential difference and noise incorporated into receivercommonmode.',None,None,'V',False),
 ('word_data_bits','Actual higher codec data width; no mandatory UART8N1.',1,None,'bit',True),
 ('word_wire_bits','Actual serialized positions including selected framing/encoding overhead.',1,None,'bit',True),
 ('words','Actual bounded word count.',0,None,None,True),
 ('wire_bits','Actual total serial positions.',0,None,'bit',True),
 ('wire_time_ms','Actual wire_bits/rate elapsed time, separate media-access wait and turnaround.',0,None,'ms',False),
 ('grant_wait_ms','Actual higher protocol/scheduler grant wait bound; RS485 supplies no arbitration protocol.',0,None,'ms',False),
 ('enable_delay_ms','Actual enabledriver setup time before firstbit.',0,None,'ms',False),
 ('turnaround_ms','Actual driver disable/line release/peer switch bound.',0,None,'ms',False),
 ('process_ms','Actual complete receiver frame verification/decode/application bound.',0,None,'ms',False),
 ('transaction_bound_ms','Actual grant+enable+wire+turnaround+processing chain.',0,None,'ms',False),
 ('transaction_limit_ms','Actual independent application transaction acceptance requirement.',0,None,'ms',False),
 ('age_ms','Actual correlated decoded data age.',0,None,'ms',False),
 ('freshness_ms','Actual consumer freshness requirement.',0,None,'ms',False),
]:d(k,'number',meaning,lo,hi,unit,integer=integer,source=GUIDE if k in('nodes','unit_load','receiver_load_ul','bias_load_ul','total_load_ul','cable_m','cable_impedance_ohm','termination_ohm','termination_count','split_resistor_ohm','split_filter_pf','stub_m','stub_delay_ns','velocity_fraction','media_pf_m','node_cap_pf','spacing_m','loaded_impedance_ohm','noise_abs_mv','bias_diff_v','bias_supply_min_v','bias_max_ohm','bias_selected_ohm','ground_diff_v')else TI)
for k,meaning in [('value_accepted','Actual complete transaction accepted by consumer.'),('de_control_verified','Actual mutually exclusive per-pair driver-enable schedule verified.'),('electrical_valid','Actual installed electrical/waveform/load test valid.'),('mapping_valid','Actual device identity/truth table/codec/value mapping valid.'),('codec_verified','Actual frame/codec integrity verified.'),('physical_verified','Actual cable/termination/stubs/load/ground commissioning verified.'),('monotonic','Actual standard waveform monotonic10-90percent transition.'),('short_indefinite_verified','Actual device passes full-voltage indefinite short stress; current alone does not prove this.')]:d(k,'boolean',meaning)
for k,meaning in [('device_source','Actual transmitter datasheet/edition/load conditions.'),('peer_source','Actual receiver datasheet/edition/configuration.'),('binding_source','Actual per-pair pin/device/direction wiring.'),('physical_source','Actual cable/ground/termination/UL/waveform qualification.'),('codec_source','Actual independent wire protocol/serialization/CRC source.'),('schedule_source','Actual independent driver-enable arbitration/grant/turnaround bounds.'),('acceptance_source','Actual independent application functional timing acceptance.'),('registered_source','Actual independently qualified alternative profile/topology/rate/protocol.'),('polarity_source','Actual device signed differential truth table and installed wiring.'),('termination_source','Actual two-end/reflection/load qualification.'),('failsafe_source','Actual idle/open/short and noise-qualified failsafe proof.'),('ground_source','Actual return-current/ground potential/isolation commissioning.'),('wave_source','Actual correlated waveform and decoded frame observation.'),('clock_source','Actual timestamp origins/correlation/uncertainty.'),('short_source','Actual full applied stress/time/device compliance source.')]:d(k,'text',meaning)
REQUIRED=('profile','topology','direction','wire_protocol','device_source','peer_source','binding_source','physical_source','codec_source','schedule_source','acceptance_source','registered_source')
REMOVED={k:'RS485 defines electrical multipoint bus, not CAN arbitration, Ethernet bandwidth/MTU or generic UART framing. Actual scoped values replace foreign fallback.'for k in('bitrate','arbitration_bitrate','data_bitrate','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
 rules=[]
 def r(k,w=None,source=TI,**kw):rules.append(dict(parameter=k if k=='local_timing_evidence'else'rs485_'+k,when={'rs485_'+a:b for a,b in(w or{}).items()},source=source,source_revision=SOURCES[source],**kw))
 r('local_timing_evidence',allowed=[])
 for k in('bitrate_bps','device_max_bps','peer_max_bps','cable_impedance_ohm','unit_load','media_pf_m','bias_diff_v','bias_supply_min_v','bias_max_ohm','bias_selected_ohm','velocity_fraction'):r(k,exclusive_minimum=0)
 r('bitrate_bps',maximum_parameter='rs485_device_max_bps');r('bitrate_bps',maximum_parameter='rs485_peer_max_bps')
 for k in('device_max_bps','peer_max_bps'):r(k,{'profile':'DEVICE_QUALIFIED'},when_present=['rs485_bitrate_bps'],required=True)
 w={'profile':'TIA_485_TI2010'}
 r('bitrate_bps',w,maximum=10000000);r('total_load_ul',w,maximum=32)
 r('active_drivers',maximum=1);r('active_drivers',{'activity':'FRAME'},allowed=[1]);r('active_drivers',{'activity':'IDLE'},allowed=[0])
 r('receiver_load_ul',{'load_model':'HOMOGENEOUS_ACTUAL'},source=GUIDE,equal_expression={'product':['rs485_unit_load','rs485_nodes']})
 for k in('unit_load','nodes'):r(k,{'load_model':'HOMOGENEOUS_ACTUAL'},when_present=['rs485_receiver_load_ul'],required=True)
 r('total_load_ul',source=GUIDE,equal_expression={'sum':['rs485_receiver_load_ul','rs485_bias_load_ul']})
 for k in('receiver_load_ul','bias_load_ul'):r(k,when_present=['rs485_total_load_ul'],required=True)
 r('driver_diff_abs_v',{**w,'load_scope':'OPEN_CIRCUIT'},minimum=1.5,maximum=6)
 for k in('driver_a_v','driver_b_v'):r(k,{**w,'load_scope':'OPEN_CIRCUIT'},minimum=-6,maximum=6)
 for scope in('STANDARD_54_OHM','STANDARD_CM_60_375'):r('driver_diff_abs_v',{**w,'load_scope':scope},minimum=1.5,maximum=5)
 r('driver_offset_v',w,minimum=-1,maximum=3)
 for k in('driver_diff_delta_abs_v','driver_offset_delta_abs_v'):r(k,w,maximum=.2)
 r('short_test_v',w,minimum=-7,maximum=12);r('short_current_abs_ma',w,maximum=250)
 r('short_test_v',when_present=['rs485_short_current_abs_ma'],required=True)
 r('short_source',{'short_indefinite_verified':True},required=True)
 r('receiver_common_v',w,minimum=-7,maximum=12)
 r('receiver_common_v',equal_expression={'product':[.5,{'sum':['rs485_receiver_a_v','rs485_receiver_b_v']}]})
 r('receiver_diff_v',equal_expression={'subtract':['rs485_receiver_a_v','rs485_receiver_b_v']})
 for k in('receiver_common_v','receiver_diff_v'):
  for ref in('receiver_a_v','receiver_b_v'):r(ref,when_present=['rs485_'+k],required=True)
 r('receiver_diff_abs_v',equal_expression={'maximum':['rs485_receiver_diff_v',{'product':[-1,'rs485_receiver_diff_v']}]})
 r('receiver_diff_v',when_present=['rs485_receiver_diff_abs_v'],required=True)
 for mapping,pos,neg in [('POSITIVE_IS_1','ONE','ZERO'),('POSITIVE_IS_0','ZERO','ONE')]:
  r('receiver_diff_v',{'logic_mapping':mapping,'decoded_logic':pos},minimum=.2)
  r('receiver_diff_v',{'logic_mapping':mapping,'decoded_logic':neg},maximum=-.2)
 r('polarity_source',when_present=['rs485_logic_mapping'],required=True)
 r('unit_interval_ns',equal_ratio={'numerator_offset':1000000000,'denominator_product':['rs485_bitrate_bps'],'denominator_offset':1})
 r('bitrate_bps',when_present=['rs485_unit_interval_ns'],required=True)
 for k in('rise_ns','fall_ns'):r(k,{**w,'load_scope':'STANDARD_54_OHM'},when_present=['rs485_unit_interval_ns'],maximum_expression={'product':[.3,'rs485_unit_interval_ns']})
 r('overshoot_percent',{**w,'load_scope':'STANDARD_54_OHM'},maximum=10)
 for k,v in('fixture_ohm',54),('fixture_pf',50):r(k,{**w,'load_scope':'STANDARD_54_OHM'},allowed=[v])
 r('termination_count',{'termination':'NONE_QUALIFIED'},allowed=[0])
 for term in('PARALLEL_TWO_ENDS','SPLIT_TWO_ENDS'):
  r('termination_count',{'termination':term},source=GUIDE,required=True,allowed=[2])
  r('termination_ohm',{'termination':term},source=GUIDE,equal_expression='rs485_cable_impedance_ohm')
  r('cable_impedance_ohm',{'termination':term},when_present=['rs485_termination_ohm'],required=True)
 r('termination_ohm',{'termination':'SPLIT_TWO_ENDS'},source=GUIDE,equal_expression={'product':[2,'rs485_split_resistor_ohm']})
 for k in('split_resistor_ohm','split_filter_pf'):r(k,{'termination':'SPLIT_TWO_ENDS'},required=True,exclusive_minimum=0)
 for term in('NONE_QUALIFIED','REGISTERED_ACTUAL'):r('termination_source',{'termination':term},required=True)
 r('stub_delay_ns',source=GUIDE,maximum_expression={'product':[.1,'rs485_rise_ns']})
 r('rise_ns',when_present=['rs485_stub_delay_ns'],required=True)
 r('stub_m',source=GUIDE,maximum_expression={'product':[.0299792458,'rs485_rise_ns','rs485_velocity_fraction']})
 for k in('rise_ns','velocity_fraction'):r(k,when_present=['rs485_stub_m'],required=True)
 r('spacing_m',source=GUIDE,exclusive_minimum_expression={'product':[5.25,'rs485_node_cap_pf',{'power':['rs485_media_pf_m',-1]}]})
 for k in('node_cap_pf','media_pf_m'):r(k,when_present=['rs485_spacing_m'],required=True)
 r('loaded_impedance_ohm',source=GUIDE,exclusive_minimum_expression={'product':[.4,'rs485_cable_impedance_ohm']})
 r('cable_impedance_ohm',when_present=['rs485_loaded_impedance_ohm'],required=True)
 for fail in('INTERNAL_PROVEN','EXTERNAL_PROVEN'):r('failsafe_source',{'failsafe':fail},required=True)
 r('bias_diff_v',{'failsafe':'EXTERNAL_PROVEN'},source=GUIDE,minimum_expression={'sum':[.2,{'product':[.001,'rs485_noise_abs_mv']}]})
 for k in('bias_diff_v','noise_abs_mv','bias_supply_min_v','bias_selected_ohm','bias_load_ul'):r(k,{'failsafe':'EXTERNAL_PROVEN'},required=True)
 r('bias_max_ohm',source=GUIDE,equal_ratio={'numerator_offset':1,'numerator_product':['rs485_bias_supply_min_v','rs485_cable_impedance_ohm'],'factor':375,'denominator_sum':['rs485_cable_impedance_ohm'],'denominator_offset':1500,'denominator_product':['rs485_bias_diff_v']})
 for k in('bias_supply_min_v','cable_impedance_ohm','bias_diff_v'):r(k,when_present=['rs485_bias_max_ohm'],required=True)
 r('bias_selected_ohm',maximum_parameter='rs485_bias_max_ohm')
 r('word_wire_bits',minimum_parameter='rs485_word_data_bits')
 r('wire_bits',equal_expression={'product':['rs485_words','rs485_word_wire_bits']})
 for k in('words','word_wire_bits'):r(k,when_present=['rs485_wire_bits'],required=True)
 r('wire_time_ms',equal_ratio={'numerator_parameter':'rs485_wire_bits','factor':1000,'denominator_product':['rs485_bitrate_bps'],'denominator_offset':1})
 r('wire_time_ms',{'wire_bits':0},allowed=[0])
 for k in('wire_bits','bitrate_bps'):r(k,when_present=['rs485_wire_time_ms'],required=True)
 chain=('grant_wait_ms','enable_delay_ms','wire_time_ms','turnaround_ms','process_ms')
 r('transaction_bound_ms',equal_expression={'sum':['rs485_'+k for k in chain]})
 for k in chain:r(k,when_present=['rs485_transaction_bound_ms'],required=True)
 r('transaction_bound_ms',maximum_parameter='rs485_transaction_limit_ms');r('age_ms',maximum_parameter='rs485_freshness_ms')
 w={'value_accepted':True}
 for k,v in [('outcome','ACCEPTED'),('activity','FRAME'),('active_drivers',1),('de_control_verified',True),('electrical_valid',True),('mapping_valid',True),('codec_verified',True),('physical_verified',True)]:r(k,w,required=True,allowed=[v])
 for k in('bitrate_bps','nodes','drivers','total_load_ul','load_model','ground_scheme','ground_source','ground_diff_v','termination','termination_source','receiver_common_v','receiver_diff_abs_v','logic_mapping','decoded_logic','polarity_source','wave_source','clock_source','transaction_bound_ms','transaction_limit_ms','age_ms','freshness_ms'):r(k,w,required=True)
 for k in('TIA_485_TI2010',):r('monotonic',{'value_accepted':True,'profile':k,'load_scope':'STANDARD_54_OHM'},required=True,allowed=[True])
 return dict(rate_model={'type':'RS485_ACTUAL_ELECTRICAL_BUS_AND_SELECTED_PROTOCOL','fields':[]},required_parameters=['rs485_'+k for k in REQUIRED],native_parameter_prefixes=['rs485_'],parameter_constraints=rules,
  parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='rs485_actual_electrical_multipoint',medium_access_model='ACTUAL_DRIVER_ENABLE_SCHEDULE',arbitration_model_id='INDEPENDENT_HIGHER_LAYER_GRANT_PROTOCOL',
  mechanisms={'qualification':['32_UNIT_LOADS_NOT32DEVICES','ONE_ACTIVE_DRIVER_PER_PAIR','NO_NORMATIVE_MINIMUM_OPERATING_RATE','ELECTRICAL_RATE_NOT_TRANSACTION_CAPACITY'],'topology':['ACTUAL_1PAIR_HALF_OR2PAIR_FULL']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][6:];v={a:b for a,b in spec.items()if b is not None}
  v.update(label=k.replace('_',' '),category='physical',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  when=None;value=None
  if k in('fixture_ohm','fixture_pf'):when={'rs485_profile':'TIA_485_TI2010','rs485_load_scope':'STANDARD_54_OHM'};value=54 if k=='fixture_ohm'else 50
  if k=='cable_impedance_ohm':when={'rs485_cable_profile':'TI_RECOMMENDED_120_OHM_UTP'};value=120
  if when is not None:v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when=when,value=value,source=spec['source'],source_revision=spec['source_revision'])])
  result.append(v)
 return result
