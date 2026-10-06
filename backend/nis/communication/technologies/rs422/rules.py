"""RS422 single-driver balanced pair; independent from multipoint RS485."""
TI='https://www.ti.com/lit/an/slla070d/slla070d.pdf'
SOURCES={TI:'TI SLLA070D May2010 actual selectedpp3-8/12-18/21-23. Public authored electrical summary; originalfigures/testconditions and source typos checked, no full licensed ANSI standard claim.'}
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,integer=False):
 DECLARATIONS.append(dict(key='rs422_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,integer=integer,source=TI,source_revision=SOURCES[TI]))
for k,meaning,opts in [
 ('profile','Actual selected electrical reference or independently qualified device/cable implementation.',['TIA_422_TI2010','DEVICE_QUALIFIED','REGISTERED_ACTUAL']),
 ('signal_kind','Actual balanced data stream versus clock pair or static logic signal; no universal packet framing.',['DATA_STREAM','CLOCK_PAIR','LEVEL']),
 ('topology','Per-pair one driver, one receiver or one driver with up to10 standard receivers.',['POINT_TO_POINT','MULTIDROP']),
 ('direction','Per-pair simplex; duplex consists of two independently qualified pairs.',['SIMPLEX','TWO_PAIR_DUPLEX']),
 ('termination','Actual none, parallel or AC resistor/capacitor; RS422 is not two-endRS485termination.',['NONE','PARALLEL','AC']),
 ('termination_position','Actual termination at last receiver far end; arbitrarymidline not standardmultidrop.',['FAR_RECEIVER','NONE','REGISTERED_ACTUAL']),
 ('unterminated_basis','Actual qualified lowrate shortline versus rise>4onedelay or commissioned reflection measurement.',['LOW_RATE_SHORT_LINE','RISE_GT_FOUR_DELAYS','MEASURED_REGISTERED']),
 ('load_scope','Actual unloaded,100ohm standardtest or installed application load.',['OPEN_CIRCUIT','STANDARD_100_OHM','APPLICATION']),
 ('power_state','Actual active versus offstate leakage; highZ/failsafe is not valid functional data.',['ACTIVE','POWER_OFF','HIGH_Z']),
 ('fault','Actual normal, idle, open or short input; conventional receiver near0differential is indeterminate.',['NORMAL','IDLE','OPEN','SHORT']),
 ('failsafe','Actual proven receiver behavior or not specified; failsafe output is not new decoded data.',['NOT_SPECIFIED','INTERNAL_PROVEN','EXTERNAL_PROVEN']),
 ('logic_mapping','Actual device truth table and wire mapping; A/B labels alone do not establish polarity.',['POSITIVE_IS_1','POSITIVE_IS_0','REGISTERED_ACTUAL']),
 ('decoded_logic','Actual observed resulting logical bit, qualified by signed pair differential.',['ONE','ZERO']),
 ('encoding','Actual higher-layer wire codec or independent clock; no mandatory8N1/8b10b. Any selected block code needs registered actual widths/source.',['RAW_BITS','START_STOP','REGISTERED_ACTUAL','CLOCK_ONLY']),
 ('outcome','Actual waveform/codec/functional result, not validrate or powerstate alone.',['ACCEPTED','ELECTRICAL_FAULT','FRAMING_ERROR','STALE','UNKNOWN']),
]:d(k,'select',meaning,options=opts)
for k,meaning,lo,hi,unit,integer in [
 ('bitrate_bps','Actual data-pair bit rate under exactdevice/cable/load; no normative lowest mode/default10M.',0,None,'bit/s',False),
 ('clock_hz','Actual clock-pair cyclefrequency; not automatically a data bitrate.',0,None,'Hz',False),
 ('device_max_bps','Actual transmitter capability under stated load.',0,None,'bit/s',False),
 ('peer_max_bps','Actual receiving interface capability under same conditions.',0,None,'bit/s',False),
 ('drivers','Actual connected per-pairdriver count; standard422 permits exactly1, not sequentialmultidrivers.',1,None,None,True),
 ('receivers','Actual connected receiver count; standardfull-load reference1..10.',1,None,None,True),
 ('receiver_input_ohm','Actual receiver input resistance under sourceI/Vfixture;>=4k.',0,None,'ohm',False),
 ('driver_diff_abs_v','Actual magnitude ofdifferential output, distinctindividualpin/common-mode voltage.',0,None,'V',False),
 ('driver_a_v','Actual signed driverAvoltage under statedload.',None,None,'V',False),
 ('driver_b_v','Actual signed driverBvoltage under statedload.',None,None,'V',False),
 ('driver_offset_abs_v','Actual driveroffsetmagnitude<=3V loadedstandardfixture.',0,None,'V',False),
 ('driver_diff_delta_abs_v','Actual outputpolaritydifferential imbalance<=0.4V.',0,None,'V',False),
 ('driver_offset_delta_abs_v','Actual offsetimbalance<=0.4V.',0,None,'V',False),
 ('driver_short_abs_ma','Actualshorttogroundoutputcurrentlimit<=150mA, not normaldrivecurrent.',0,None,'mA',False),
 ('off_test_v','Actual appliedunpowereddrivervoltage-.25..6V leakagetest.',None,None,'V',False),
 ('off_leak_abs_ua','Actualunpowereddriverleakage under statedappliedvoltage<=100uA.',0,None,'uA',False),
 ('receiver_a_v','Actual signed receiverpinAvoltage; sourceTable1typos notunitdefaults.',None,None,'V',False),
 ('receiver_b_v','Actual signed receiverpinBvoltage.',None,None,'V',False),
 ('receiver_common_v','Actual(VA+VB)/2; standardreceivercommonmode-7..7V, notRS485+12V.',None,None,'V',False),
 ('receiver_diff_v','Actual signedVA-VB, data thresholdregionwithin±.2Vundefined withoutprovenfailsafe.',None,None,'V',False),
 ('receiver_diff_abs_v','Actual receiveddifferentialmagnitude up10V with200mVsensitivity.',0,None,'V',False),
 ('fixture_load_ohm','Declared standard waveformtestload100ohm; not automatically installedtermination.',0,None,'ohm',False),
 ('rise_ns','Actual 10..90percentfull differentialsignalrise under stated load, notUARTbitinterval.',0,None,'ns',False),
 ('fall_ns','Actualfullsignal fall under statedload.',0,None,'ns',False),
 ('unit_interval_ns','Actual dataUI1e9/bitrate, not a genericframeperiod.',0,None,'ns',False),
 ('overshoot_percent','Actualposttransitionexcursion aspercentof fullVSS;standardfixture<=10.',0,None,'percent',False),
 ('cable_m','Actualinstalled cable length; no normative universal1200mmaximumindependentfromrate.',0,None,'m',False),
 ('cable_impedance_ohm','Actualselectedlinecharacteristicimpedance, not universal100/120ohm.',0,None,'ohm',False),
 ('termination_ohm','Actualparallel/ACresistance within20percentof selectedlineimpedance.',0,None,'ohm',False),
 ('termination_pf','ActualACcapacitor requiringtiming/reflectionqualification;1000pFisTIexperimentonly.',0,None,'pF',False),
 ('termination_count','Actualperpairfar-end terminationcount1 whenused.',0,None,None,True),
 ('delay_ns','Actualone-way cable propagationdelay includingphysicalroute.',0,None,'ns',False),
 ('stub_m','Actualreceiverstub length independentlyqualified, no arbitrary1mdefault.',0,None,'m',False),
 ('noise_abs_mv','Actualmaximum differentialnoise atreceiver.',0,None,'mV',False),
 ('noise_margin_mv','Actualdifferential margin after200mVthresholdandmeasurednoise.',None,None,'mV',False),
 ('word_data_bits','Actualcodecdata width, not electrical8bitpayload.',1,None,'bit',True),
 ('word_wire_bits','Actualencodedwire positionsinclframe/encodingoverhead.',1,None,'bit',True),
 ('words','Actualtransactionwordcount.',0,None,None,True),
 ('wire_bits','Actualboundedserialized wirecount fromselectedcodec.',0,None,'bit',True),
 ('wire_time_ms','Actualserializedbitstime, excludesprocessing/queue/twowayexchange.',0,None,'ms',False),
 ('process_bound_ms','Actualreceivercodec/applicationprocessingbound.',0,None,'ms',False),
 ('transaction_bound_ms','Actualwire+receiverprocessingboundforselecteddirection.',0,None,'ms',False),
 ('transaction_limit_ms','Actualfunctionaltransactiontimingrequirement.',0,None,'ms',False),
 ('age_ms','Actualcorrelateddecodeddataage.',0,None,'ms',False),
 ('freshness_ms','Actualfunctionalconsumerfreshnessbound.',0,None,'ms',False),
]:d(k,'number',meaning,lo,hi,unit,integer=integer)
for k,meaning in [('signal_accepted','Observed data/clock/levelaccepted underitsownfunctionalrequirements.'),('electrical_valid','Actual loaded waveform/voltage/cable validated.'),('mapping_valid','Actualtruthtable/codec/identity/value mappingvalidated.'),('monotonic','Actual10..90percentwaveformmonotonicity, not presetTrue.'),('termination_verified','Actual reflectedwave/termination/cablequalification.'),('clock_verified','Actual independentclockpairfrequency/jitterconsumeracceptance.'),('codec_verified','Actualdataframe integrityanddecode acceptance.')]:d(k,'boolean',meaning)
for k,meaning in [('device_source','Actualtransmitteredition/load/clockdatasheet.'),('peer_source','Actualreceiversourceandappliedconfiguration.'),('binding_source','Actualperpairdriver/receiver/pins/duplexdirectionbinding.'),('physical_source','Actualloadedwaveform/cable/ground/faulttestsource.'),('codec_source','Actualdataframingorclock/levelmapping specification.'),('schedule_source','Actualserializedtransactionandschedulerbound.'),('acceptance_source','Actualindependentfunctionalacceptancerequirement.'),('registered_source','Independentlyqualifieddevice/load/rate/topology/codecsource.'),('polarity_source','ActualdeviceVA-VBtruth table and installed wiremap.'),('termination_source','Actualterminatingnetwork/receiverreflectionqualification.'),('failsafe_source','Actualdevice/appfailsafenoise/faultprofile, notdefaultHIGH.'),('wave_source','Actualcorrelatedloadedwaveformanddecodeobservation.'),('clock_source','Actualcorrelatedclockorigin/uncertainty/source.')]:d(k,'text',meaning)
REQUIRED=('profile','signal_kind','topology','direction','encoding','drivers','receivers','device_source','peer_source','binding_source','physical_source','codec_source','schedule_source','acceptance_source')
REMOVED={k:'Not a universal RS422 property; actual balancedpair/electrical/codecparameters replace foreignfallback.'for k in('bitrate','arbitration_bitrate','data_bitrate','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter=k if k=='local_timing_evidence'else'rs422_'+k,when={'rs422_'+a:b for a,b in(w or{}).items()},source=TI,source_revision=SOURCES[TI],**kw))
 r('local_timing_evidence',allowed=[])
 for k in('profile','encoding','termination_position','logic_mapping'):r('registered_source',{k:'REGISTERED_ACTUAL'},required=True)
 r('registered_source',{'profile':'DEVICE_QUALIFIED'},required=True)
 for k in('bitrate_bps','clock_hz','device_max_bps','peer_max_bps','cable_impedance_ohm','fixture_load_ohm'):r(k,exclusive_minimum=0)
 r('bitrate_bps',maximum_parameter='rs422_device_max_bps');r('bitrate_bps',maximum_parameter='rs422_peer_max_bps')
 for k in('device_max_bps','peer_max_bps'):r(k,{'profile':'DEVICE_QUALIFIED'},when_present=['rs422_bitrate_bps'],required=True)
 w={'profile':'TIA_422_TI2010'}
 r('drivers',w,allowed=[1]);r('receivers',w,maximum=10);r('bitrate_bps',w,maximum=10000000)
 r('receiver_input_ohm',w,minimum=4000);r('driver_diff_abs_v',w,maximum=10)
 r('driver_diff_abs_v',{**w,'load_scope':'STANDARD_100_OHM'},minimum=2)
 for k in('driver_a_v','driver_b_v'):r(k,{**w,'load_scope':'OPEN_CIRCUIT'},minimum=-6,maximum=6)
 for k,limit in [('driver_offset_abs_v',3),('driver_diff_delta_abs_v',.4),('driver_offset_delta_abs_v',.4),('driver_short_abs_ma',150),('off_leak_abs_ua',100)]:r(k,w,maximum=limit)
 r('off_test_v',w,minimum=-.25,maximum=6);r('off_test_v',w,when_present=['rs422_off_leak_abs_ua'],required=True)
 r('fixture_load_ohm',{**w,'load_scope':'STANDARD_100_OHM'},allowed=[100])
 r('receiver_common_v',w,minimum=-7,maximum=7);r('receiver_diff_abs_v',w,maximum=10)
 r('receiver_common_v',equal_expression={'product':[.5,{'sum':['rs422_receiver_a_v','rs422_receiver_b_v']}]})
 r('receiver_diff_v',equal_expression={'subtract':['rs422_receiver_a_v','rs422_receiver_b_v']})
 for k in('receiver_common_v','receiver_diff_v'):
  for ref in('receiver_a_v','receiver_b_v'):r(ref,when_present=['rs422_'+k],required=True)
 r('receiver_diff_abs_v',equal_expression={'maximum':['rs422_receiver_diff_v',{'product':[-1,'rs422_receiver_diff_v']}]})
 r('receiver_diff_v',when_present=['rs422_receiver_diff_abs_v'],required=True)
 for mapping,pos,neg in [('POSITIVE_IS_1','ONE','ZERO'),('POSITIVE_IS_0','ZERO','ONE')]:
  r('receiver_diff_v',{**w,'logic_mapping':mapping,'decoded_logic':pos},minimum=.2,maximum=10)
  r('receiver_diff_v',{**w,'logic_mapping':mapping,'decoded_logic':neg},minimum=-10,maximum=-.2)
 r('polarity_source',when_present=['rs422_logic_mapping'],required=True)
 r('receivers',{'topology':'POINT_TO_POINT'},allowed=[1])
 r('termination_count',{'termination':'NONE'},allowed=[0]);r('termination_position',{'termination':'NONE'},allowed=['NONE'])
 for term in('PARALLEL','AC'):
  r('termination_count',{'termination':term},required=True,allowed=[1]);r('termination_position',{'termination':term},required=True,allowed=['FAR_RECEIVER','REGISTERED_ACTUAL'])
  r('cable_impedance_ohm',{'termination':term},when_present=['rs422_termination_ohm'],required=True)
  r('termination_ohm',{'termination':term},minimum_expression={'product':[.8,'rs422_cable_impedance_ohm']},maximum_expression={'product':[1.2,'rs422_cable_impedance_ohm']})
 r('termination_pf',{'termination':'AC'},required=True,exclusive_minimum=0)
 r('termination_source',{'termination':'AC'},required=True)
 r('unterminated_basis',{'termination':'NONE'},required=True)
 r('bitrate_bps',{'termination':'NONE','unterminated_basis':'LOW_RATE_SHORT_LINE'},maximum=200000)
 r('termination_source',{'termination':'NONE'},required=True)
 r('rise_ns',{'termination':'NONE','unterminated_basis':'RISE_GT_FOUR_DELAYS'},required=True,exclusive_minimum_expression={'product':[4,'rs422_delay_ns']})
 r('delay_ns',{'termination':'NONE','unterminated_basis':'RISE_GT_FOUR_DELAYS'},required=True)
 r('registered_source',{'unterminated_basis':'MEASURED_REGISTERED'},required=True)
 r('unit_interval_ns',equal_ratio={'numerator_offset':1000000000,'denominator_product':['rs422_bitrate_bps'],'denominator_offset':1})
 r('bitrate_bps',when_present=['rs422_unit_interval_ns'],required=True)
 for k in('rise_ns','fall_ns'):r(k,{**w,'load_scope':'STANDARD_100_OHM'},when_present=['rs422_unit_interval_ns'],maximum_expression={'maximum':[20,{'product':[.1,'rs422_unit_interval_ns']}]})
 r('overshoot_percent',{**w,'load_scope':'STANDARD_100_OHM'},maximum=10)
 for k in('INTERNAL_PROVEN','EXTERNAL_PROVEN'):r('failsafe_source',{'failsafe':k},required=True)
 r('word_wire_bits',minimum_parameter='rs422_word_data_bits')
 r('wire_bits',equal_expression={'product':['rs422_words','rs422_word_wire_bits']})
 for k in('words','word_wire_bits'):r(k,when_present=['rs422_wire_bits'],required=True)
 r('wire_time_ms',equal_ratio={'numerator_parameter':'rs422_wire_bits','factor':1000,'denominator_product':['rs422_bitrate_bps'],'denominator_offset':1})
 r('wire_time_ms',{'wire_bits':0},allowed=[0])
 for k in('wire_bits','bitrate_bps'):r(k,when_present=['rs422_wire_time_ms'],required=True)
 r('transaction_bound_ms',equal_expression={'sum':['rs422_wire_time_ms','rs422_process_bound_ms']})
 for k in('wire_time_ms','process_bound_ms'):r(k,when_present=['rs422_transaction_bound_ms'],required=True)
 r('transaction_bound_ms',maximum_parameter='rs422_transaction_limit_ms');r('age_ms',maximum_parameter='rs422_freshness_ms')
 r('noise_margin_mv',equal_expression={'subtract':[{'subtract':[{'product':[1000,'rs422_receiver_diff_abs_v']},200]},'rs422_noise_abs_mv']})
 w={'signal_accepted':True}
 for k,v in [('outcome','ACCEPTED'),('electrical_valid',True),('mapping_valid',True),('termination_verified',True),('fault','NORMAL'),('power_state','ACTIVE')]:r(k,w,required=True,allowed=[v])
 for k in('wave_source','clock_source','polarity_source','termination_source','age_ms','freshness_ms'):r(k,w,required=True)
 for k in('termination','receiver_common_v','receiver_diff_abs_v','logic_mapping','decoded_logic'):r(k,w,required=True)
 r('monotonic',{'signal_accepted':True,'profile':'TIA_422_TI2010','load_scope':'STANDARD_100_OHM'},required=True,allowed=[True])
 r('noise_margin_mv',w,minimum=0)
 for k in('bitrate_bps','transaction_bound_ms','transaction_limit_ms','codec_verified'):
  r(k,{'signal_accepted':True,'signal_kind':'DATA_STREAM'},required=True,**({'allowed':[True]}if k=='codec_verified'else{}))
 for k in('clock_hz','clock_verified'):r(k,{'signal_accepted':True,'signal_kind':'CLOCK_PAIR'},required=True,**({'allowed':[True]}if k=='clock_verified'else{}))
 return dict(rate_model={'type':'RS422_ACTUAL_BALANCED_PAIR_DEVICE_AND_CODEC','fields':[]},required_parameters=['rs422_'+k for k in REQUIRED],native_parameter_prefixes=['rs422_'],parameter_constraints=rules,
  parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='rs422_actual_single_driver_pair',medium_access_model='ONE_DRIVER_PER_PAIR_MULTIDROP',arbitration_model_id='DEDICATED_DRIVER_NO_BUS_ARBITRATION',
  mechanisms={'encoding':['ACTUAL_HIGHER_LAYER_OR_CLOCK'],'qualification':['RS422_NOT_MULTIPOINT_RS485','NO_NORMATIVE_MINIMUM_OPERATING_RATE','ELECTRICAL_LIMIT_NOT_TRANSACTION_CAPACITY']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][6:];v={a:b for a,b in spec.items()if b is not None}
  v.update(label=k.replace('_',' '),category='physical',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  if k=='fixture_load_ohm':v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'rs422_profile':'TIA_422_TI2010','rs422_load_scope':'STANDARD_100_OHM'},value=100,source=TI,source_revision=SOURCES[TI])])
  result.append(v)
 return result
