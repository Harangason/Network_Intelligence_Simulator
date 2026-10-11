"""SpaceWire DS symbols, link credit, physical realization and routed paths."""
ECSS='https://ecss.nl/wp-content/uploads/2019/05/ECSS-E-ST-50-12C-Rev.1%2815May2019%29.pdf'
SOURCES={ECSS:'ECSS-E-ST-50-12C Rev1 May15 2019, original124-page PDF with publisher MD5 matched; selected physical/encoding/rate/credit/state/packet/broadcast/router sections5.3-5.6 read. Overview speed examples are not universal device limits.'}
DECLARATIONS=[]

def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,integer=False):
 DECLARATIONS.append(dict(key='spw_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,integer=integer,source=ECSS,source_revision=SOURCES[ECSS]))

for k,meaning,opts in [
 ('edition','Selected ECSS 2019 revision versus independently qualified alternative.',['ECSS_2019','REGISTERED_ACTUAL']),
 ('proposal_mode','Actual commissioned configuration versus explicit source baseline proposals.',['ACTUAL_CONFIG','SOURCE_BASELINE']),
 ('minimum_capability','Full2Mbps capability versus qualified device with higher minimum up to initial11Mbps.',['FULL_2M','LIMITED_ACTUAL']),
 ('phy','Actual point-to-point LVDS versus short internal LVTTL or independently qualified other drivers.',['SPW_LVDS','SPW_LVTTL','REGISTERED_OTHER']),
 ('connector','Actual LVDS TypeA/TypeB versus distinct non-LVDS connector; no unsafe driver interchange.',['TYPE_A','TYPE_B','OTHER']),
 ('state','Actual link state; packet/broadcast traffic only in Run, not initialized from bitrate alone.',['ERROR_RESET','ERROR_WAIT','READY','STARTED','CONNECTING','RUN']),
 ('traffic','Actual packet, broadcast or link-maintenance transaction.',['PACKET','BROADCAST','LINK_CONTROL']),
 ('symbol','Actual encoded data/control/code symbol, not a UART8N1 frame.',['DATA','FCT','EOP','EEP','NULL','BROADCAST']),
 ('end','Actual normal or error end marker, EEP cannot certify a successful packet.',['EOP','EEP']),
 ('encoding','Actual Data-Strobe encoding, receiver recovers clock by XOR.',['DATA_STROBE','UART','NRZ']),
 ('parity','Actual odd parity covers previous character data and current flag, not independent UART byte parity.',['ODD','EVEN','NONE']),
 ('bit_order','Data byte transmission order least significant first.',['LSB_FIRST','MSB_FIRST']),
 ('addressing','Actual path addressing with deletion versus mapped logical addressing.',['PATH','LOGICAL','DIRECT']),
 ('broadcast_kind','Actual time-code versus interrupt or matching interrupt acknowledgement.',['TIME_CODE','INTERRUPT','INTERRUPT_ACK']),
 ('interrupt_mode','Interrupt only versus independently coordinated acknowledgement mode.',['INTERRUPT_ONLY','WITH_ACK']),
 ('arbitration','Actual router output arbitration, ECSS requires fairness; no assumed global CAN priority.',['FAIR','UNFAIR']),
 ('outcome','Actual correlated consumer result and link/packet errors.',['ACCEPTED','EEP','PARITY_ERROR','CREDIT_ERROR','DISCONNECT','MISSING','STALE','UNKNOWN']),
]:d(k,'select',meaning,options=opts)

for k,meaning,lo,hi,unit,integer in [
 ('tx_bps','Actual selected output bit signalling rate; start10±1Mbps, Run speed device/PHY qualified.',1,None,'bit/s',False),
 ('rx_bps','Actual opposite direction rate, can differ from transmit direction.',1,None,'bit/s',False),
 ('local_receive_max_bps','Actual local receiver qualified maximum for the opposite direction.',1,None,'bit/s',False),
 ('device_min_bps','Actual supported output minimum, limited capability must still support initial9..11Mbps.',1,None,'bit/s',False),
 ('device_max_bps','Actual qualified output maximum;200/400Mbps overview is not a fixed cap.',1,None,'bit/s',False),
 ('peer_receive_max_bps','Actual far-end supported receive maximum for this direction.',1,None,'bit/s',False),
 ('cable_m','Actual qualified assembly length,10m/200Mbps is an example not universal safe envelope.',0,None,'m',False),
 ('termination_ohm','Actual receiver differential termination, ECSS mandatory90..110ohm,100±1% recommended external.',0,None,'ohm',False),
 ('tx_cm_v','Actual transmitter common-mode voltage with specified100ohm test fixture1.125..1.45V.',0,None,'V',False),
 ('tx_diff_peak_v','Actual differential peak magnitude with100ohm fixture.247..454V, not peak-to-peak.',0,None,'V',False),
 ('tx_single_peak_v','Actual single output peak about common mode.124..227V.',0,None,'V',False),
 ('tx_cm_imbalance_v','Actual common-mode difference between logic levels, strictly below50mV.',0,None,'V',False),
 ('tx_single_imbalance_v','Actual single output steady-state level magnitude imbalance, below50mV.',0,None,'V',False),
 ('tx_dynamic_imbalance_v','Actual dynamic single output imbalance, below150mV.',0,None,'V',False),
 ('rise_ps','Actual monotonic transition at least260ps and below.3 bit interval;3ns is recommendation.',0,None,'ps',False),
 ('fall_ps','Actual falling transition at least260ps and below.3 bit interval.',0,None,'ps',False),
 ('ringing_abs_v','Actual differential ringing magnitude no greater than.4 differential peak.',0,None,'V',False),
 ('rx_diff_v','Actual signed receiver differential voltage, meaningful logic outside±100mV and magnitude≤600mV.',-.6,.6,'V',False),
 ('rx_cm_v','Actual receiver common mode checked with each pin relative to receiver ground.',0,None,'V',False),
 ('rx_p_v','Actual receiver positive pin=common+signed differential/2,0..2.4V.',0,2.4,'V',False),
 ('rx_n_v','Actual receiver negative pin=common-signed differential/2,0..2.4V.',0,2.4,'V',False),
 ('ground_diff_v','Actual signed endpoint ground difference, magnitude strictly below1V.',-1,1,'V',False),
 ('tx_skew_ps','Actual worst transmitter Data-Strobe skew including transmitter jitter.',0,None,'ps',False),
 ('cable_skew_ps','Actual aggregate cable Data-Strobe skew including multiple cable assemblies.',0,None,'ps',False),
 ('cable_jitter_ps','Actual worst frequency/data dependent cable jitter.',0,None,'ps',False),
 ('receiver_min_sep_ps','Actual qualified minimum separation tolerated by receiver, not automatic clock period.',0,None,'ps',False),
 ('minimum_ui_ps','Qualified sum of skew/jitter/receiver separation plus10%margin, no source example3980ps default.',0,None,'ps',False),
 ('bit_ui_ps','Actual transmit bit interval1e12/tx_bps.',0,None,'ps',False),
 ('disconnect_ns','Actual disconnect threshold, strictly above727ns and at most1000ns; nominal850ns proposal.',0,None,'ns',False),
 ('error_reset_us','Actual reset delay nominal6.4us, permitted5.82..7.22us.',0,None,'us',False),
 ('error_wait_us','Actual wait/start/connect delay nominal12.8us, permitted11.64..14.33us.',0,None,'us',False),
 ('symbol_bits','Actual DATA10/control4/NULL8/broadcast14 bits; ESC prefixes included in codes.',1,None,'bit',True),
 ('symbol_wire_ns','Actual complete symbol bit serialization time, not full network latency.',0,None,'ns',False),
 ('packet_data_chars','Actual packet data characters including address/header/cargo, no fixed65535byte limit.',0,None,None,True),
 ('address_bytes','Actual serialized address bytes, not number of device nodes.',0,None,'byte',True),
 ('higher_header_bytes','Actual independently bound higher protocol bytes, SpaceWire defines no automatic CRC/ack/RMAP.',0,None,'byte',True),
 ('packet_bits','Actual packet data chars*10+4 end marker bits, excludes all interleaved maintenance/broadcast/stalls.',4,None,'bit',True),
 ('trace_data_chars','Actual standalone data characters in selected direction/window, excludes broadcast embedded data.',0,None,None,True),
 ('trace_controls','Actual standalone FCT/EOP/EEP controls, excludes ESCs belonging to NULL/broadcast codes.',0,None,None,True),
 ('trace_nulls','Actual complete idle NULL codes in trace.',0,None,None,True),
 ('trace_broadcasts','Actual complete14-bit broadcast codes in trace.',0,None,None,True),
 ('trace_bits','Actual10D+4control+8NULL+14broadcast aggregate encoded bits.',0,None,'bit',True),
 ('trace_wire_ns','Actual aggregate bit serialization time, excludes credit/router/application waiting.',0,None,'ns',False),
 ('tx_credit','Actual currently granted transmit N-Char count,0..56, not packet bytes.',0,56,None,True),
 ('rx_credit','Actual outstanding requested N-Chars, no more than selected receive credit cap.',0,56,None,True),
 ('rx_credit_max','Actual receive credit cap≤56, may be lower for smaller FIFO.',0,56,None,True),
 ('rx_fifo_free','Actual receive FIFO capacity free in N-Chars.',0,None,None,True),
 ('outstanding_fcts','Actual outstanding FCTs, at most7; each grants8NChars.',0,7,None,True),
 ('credit_before','Actual transmit credit at trace-window entry.',0,56,None,True),
 ('fcts_received','Actual FCT count over whole window, can exceed7 cumulatively.',0,None,None,True),
 ('nchars_sent','Actual sent DATA/EOP/EEP N-Chars, excludes NULL/FCT/broadcast.',0,None,None,True),
 ('credit_after','Actual credit=before+8*receivedFCTs-sentNChars; intermediate counter trace separately required.',0,56,None,True),
 ('next_nchars','Actual immediate N-Char transmission group to fit current credit; entire packet need not fit at once.',0,None,None,True),
 ('path_port','Actual leading path address0configurationport/1..31external/FIFO port.',0,31,None,True),
 ('logical_address','Actual leading mapped logical address32..254;255 reserved, no default32 assignment.',0,255,None,True),
 ('router_ports','Actual external/FIFO router ports1..31.',1,31,None,True),
 ('broadcast_type','Actual2-bit broadcast type0 timecode,2interrupt/ack;1/3 discarded.',0,3,None,True),
 ('broadcast_value','Actual6-bit time value or interrupt ID with acknowledgement bit5.',0,63,None,True),
 ('time_value','Actual6-bit time-code register value, no sampled application-clock guarantee.',0,63,None,True),
 ('previous_time','Actual previous time register, accepted forward sequence one more modulo64.',0,63,None,True),
 ('time_masters','Actual single time-code master application, not number of redundant endpoints.',0,None,None,True),
 ('interrupt_id','Actual interrupt identity0..31, distinct from time value.',0,31,None,True),
 ('relay_register_bits','Actual supported interrupt register width, may be smaller than32.',1,32,None,True),
 ('interrupt_sources','Actual sources for selected interrupt; acknowledgement mode requires one.',0,None,None,True),
 ('interrupt_acknowledgers','Actual acknowledgers for selected interrupt, one in acknowledgement mode.',0,None,None,True),
 ('interrupt_propagation_ns','Actual worst interrupt code propagation across entire network.',0,None,'ns',False),
 ('ack_propagation_ns','Actual worst acknowledgement network propagation.',0,None,'ns',False),
 ('ack_handler_max_ns','Actual maximum qualified handler delay before acknowledgement generation.',0,None,'ns',False),
 ('ack_handler_actual_ns','Actual handler delay, strictly above interrupt propagation and below qualified maximum.',0,None,'ns',False),
 ('interrupt_repeat_ns','Actual repeat interval for same interrupt value, greater than propagation/whole acknowledgement chain.',0,None,'ns',False),
 ('interrupt_timeout_ns','Actual TR/TRA, greater than worst applicable propagation/handler chain.',0,None,'ns',False),
 ('source_bound_ms','Actual application serialization/production bound.',0,None,'ms',False),
 ('network_bound_ms','Actual all-hop wormhole/arbitration/FCT stall/recovery bound; not sum of Ethernet store-forward defaults.',0,None,'ms',False),
 ('consumer_bound_ms','Actual decoded packet/application consumption bound.',0,None,'ms',False),
 ('e2e_bound_ms','Actual source+network+consumer bound.',0,None,'ms',False),
 ('e2e_limit_ms','Actual independent functional timing requirement.',0,None,'ms',False),
 ('age_ms','Actual correlated information age at consuming application.',0,None,'ms',False),
 ('freshness_ms','Actual permitted application age.',0,None,'ms',False),
]:d(k,'number',meaning,lo,hi,unit,integer=integer)

for k,meaning in [('logic','Actual decoded binary receiver logic, with qualified differential level.'),('monotonic','Actual measured signal edges monotonic.'),('got_null','Actual initial NULL with parity checks received.'),('got_fct','Actual FCT received after initial NULL.'),('link_disabled','Actual port disabled, not inferred from idle packet absence.'),('parity_ok','Actual preceding-data/current-flag odd parity trace valid.'),('credit_trace_verified','Actual complete intermediate credit counters/buffer availability checked.'),('physical_verified','Actual PHY/pins/cables/termination/skew/rate capability checked.'),('route_verified','Actual full port/logical mapping and all-hop arbitration/FCT stall bound checked.'),('broadcast_supported','Actual nodes/routers support selected optional broadcast mechanism.'),('time_valid','Actual time-code sequential validity; invalid still updates register but does not propagate.'),('data_accepted','Actual independent application consumer acceptance.')]:d(k,'boolean',meaning)

for k,meaning in [('device_source','Actual port/firmware/edition/rate/receive/FIFO capabilities.'),('binding_source','Canonical endpoints and directional Data-Strobe/PHY/port binding.'),('physical_source','Actual test fixture/pin/termination/cable/ground/skew/jitter qualification.'),('codec_source','Actual symbol/parity/packet/independent higher protocol layout.'),('route_source','Actual all-hop router/fair arbitration/credit blocking/path qualification.'),('acceptance_source','Actual independent functional timing/freshness/error requirements.'),('observation_source','Actual correlated signal/symbol/credit/route/application trace.'),('registered_source','Actual independently qualified alternative edition or physical driver realization.'),('interrupt_source','Actual per-ID node/relay/acknowledger/register/timer allocation.'),('time_source','Actual single master/register/endpoint/sequence distribution.')]:d(k,'text',meaning)

REQUIRED=('edition','proposal_mode','minimum_capability','phy','state','traffic','device_source','binding_source','physical_source','codec_source','route_source','acceptance_source')
REMOVED={k:'SpaceWire own DS signalling/symbols/credits/wormhole paths replace implicit CAN/Ethernet/UART settings; NIS scenario controls remain separate.'for k in('bitrate','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='spw_'+k,when={'spw_'+a:b for a,b in(w or{}).items()},source=ECSS,source_revision=SOURCES[ECSS],**kw))
 rules.append(dict(parameter='local_timing_evidence',allowed=[],source=ECSS))
 r('registered_source',{'edition':'REGISTERED_ACTUAL'},required=True);r('registered_source',{'phy':'REGISTERED_OTHER'},required=True)
 for k,v in [('encoding','DATA_STROBE'),('parity','ODD'),('bit_order','LSB_FIRST')]:r(k,{'edition':'ECSS_2019'},allowed=[v])
 r('device_min_bps',{'minimum_capability':'FULL_2M'},allowed=[2000000])
 r('device_min_bps',{'minimum_capability':'LIMITED_ACTUAL'},required=True,exclusive_minimum=2000000,maximum=11000000)
 for state in('ERROR_RESET','ERROR_WAIT','READY','STARTED','CONNECTING'):r('tx_bps',{'edition':'ECSS_2019','state':state},minimum=9000000,maximum=11000000)
 r('tx_bps',{'edition':'ECSS_2019','state':'RUN'},minimum=2000000)
 r('tx_bps',minimum_parameter='spw_device_min_bps',maximum_parameter='spw_device_max_bps')
 r('tx_bps',maximum_parameter='spw_peer_receive_max_bps')
 r('rx_bps',{'edition':'ECSS_2019','state':'RUN'},minimum=2000000)
 r('rx_bps',maximum_parameter='spw_local_receive_max_bps')
 r('device_max_bps',minimum=9000000)
 r('connector',{'phy':'SPW_LVTTL'},allowed=['OTHER']);r('connector',{'phy':'REGISTERED_OTHER'},allowed=['OTHER'])
 r('cable_m',{'phy':'SPW_LVTTL'},exclusive_maximum=.3)
 w={'phy':'SPW_LVDS'}
 for k,lo,hi in [('termination_ohm',90,110),('tx_cm_v',1.125,1.45),('tx_diff_peak_v',.247,.454),('tx_single_peak_v',.124,.227)]:r(k,w,minimum=lo,maximum=hi)
 for k,hi in [('tx_cm_imbalance_v',.05),('tx_single_imbalance_v',.05),('tx_dynamic_imbalance_v',.15)]:r(k,w,exclusive_maximum=hi)
 for k in('rise_ps','fall_ps'):r(k,w,minimum=260,exclusive_maximum_expression={'product':[.3,'spw_bit_ui_ps']})
 r('monotonic',w,allowed=[True]);r('ringing_abs_v',w,maximum_expression={'product':[.4,'spw_tx_diff_peak_v']})
 r('ground_diff_v',w,exclusive_minimum=-1,exclusive_maximum=1)
 r('rx_diff_v',{**w,'logic':True},exclusive_minimum=.1);r('rx_diff_v',{**w,'logic':False},exclusive_maximum=-.1)
 r('rx_p_v',w,equal_expression={'sum':['spw_rx_cm_v',{'product':[.5,'spw_rx_diff_v']}]})
 r('rx_n_v',w,equal_expression={'subtract':['spw_rx_cm_v',{'product':[.5,'spw_rx_diff_v']}]})
 r('bit_ui_ps',equal_ratio={'numerator_offset':1,'denominator_parameter':'spw_tx_bps','factor':1e12})
 r('tx_bps',when_present=['spw_bit_ui_ps'],required=True)
 skew=('tx_skew_ps','cable_skew_ps','cable_jitter_ps','receiver_min_sep_ps')
 r('minimum_ui_ps',equal_expression={'product':[1.1,{'sum':['spw_'+k for k in skew]}]})
 for k in skew:r(k,when_present=['spw_minimum_ui_ps'],required=True)
 r('bit_ui_ps',exclusive_minimum_expression='spw_minimum_ui_ps')
 r('disconnect_ns',exclusive_minimum=727,maximum=1000)
 r('error_reset_us',minimum=5.82,maximum=7.22);r('error_wait_us',minimum=11.64,maximum=14.33)
 for symbol,bits in [('DATA',10),('FCT',4),('EOP',4),('EEP',4),('NULL',8),('BROADCAST',14)]:r('symbol_bits',{'symbol':symbol},allowed=[bits])
 r('symbol_wire_ns',equal_ratio={'numerator_parameter':'spw_symbol_bits','denominator_parameter':'spw_tx_bps','factor':1e9})
 for k in('symbol_bits','tx_bps'):r(k,when_present=['spw_symbol_wire_ns'],required=True)
 r('packet_data_chars',equal_expression={'sum':['payload_bytes','spw_address_bytes','spw_higher_header_bytes']})
 for k in('address_bytes','higher_header_bytes'):r(k,when_present=['spw_packet_data_chars'],required=True)
 rules.append(dict(parameter='payload_bytes',when_present=['spw_packet_data_chars'],required=True,source=ECSS))
 r('packet_bits',equal_expression={'sum':[{'product':[10,'spw_packet_data_chars']},4]})
 trace=('trace_data_chars','trace_controls','trace_nulls','trace_broadcasts')
 r('trace_bits',equal_expression={'sum':[{'product':[n,'spw_'+k]}for k,n in zip(trace,(10,4,8,14))]})
 for k in trace:r(k,when_present=['spw_trace_bits'],required=True)
 r('trace_wire_ns',equal_ratio={'numerator_parameter':'spw_trace_bits','denominator_parameter':'spw_tx_bps','factor':1e9})
 for k in('trace_bits','tx_bps'):r(k,when_present=['spw_trace_wire_ns'],required=True)
 r('trace_wire_ns',{'trace_bits':0},allowed=[0])
 r('rx_credit',maximum_parameter='spw_rx_credit_max');r('rx_credit',maximum_parameter='spw_rx_fifo_free')
 r('next_nchars',maximum_parameter='spw_tx_credit')
 r('credit_after',equal_expression={'subtract':[{'sum':['spw_credit_before',{'product':[8,'spw_fcts_received']}]},'spw_nchars_sent']})
 for k in('tx_credit','rx_credit'):r(k,{'state':'ERROR_RESET'},allowed=[0])
 r('path_port',{'addressing':'PATH'},maximum_parameter='spw_router_ports')
 r('logical_address',{'addressing':'LOGICAL'},minimum=32,maximum=254)
 r('arbitration',{'edition':'ECSS_2019'},allowed=['FAIR'])
 for kind,code in [('TIME_CODE',0),('INTERRUPT',2),('INTERRUPT_ACK',2)]:r('broadcast_type',{'broadcast_kind':kind},allowed=[code])
 r('broadcast_value',{'broadcast_kind':'TIME_CODE'},equal_parameter='spw_time_value')
 r('broadcast_value',{'broadcast_kind':'INTERRUPT'},equal_parameter='spw_interrupt_id')
 r('broadcast_value',{'broadcast_kind':'INTERRUPT_ACK'},equal_expression={'sum':['spw_interrupt_id',32]})
 r('time_masters',{'broadcast_kind':'TIME_CODE'},allowed=[1])
 r('time_value',{'time_valid':True},equal_expression={'integer_remainder':[{'sum':['spw_previous_time',1]},64]})
 for k in('time_value','previous_time'):r(k,{'time_valid':True},required=True)
 r('interrupt_id',exclusive_maximum_expression='spw_relay_register_bits')
 for k in('interrupt_sources','interrupt_acknowledgers'):r(k,{'interrupt_mode':'WITH_ACK'},allowed=[1])
 for k in('interrupt_repeat_ns','interrupt_timeout_ns'):
  r(k,{'interrupt_mode':'INTERRUPT_ONLY'},exclusive_minimum_expression='spw_interrupt_propagation_ns')
  r(k,{'interrupt_mode':'WITH_ACK'},exclusive_minimum_expression={'sum':['spw_interrupt_propagation_ns','spw_ack_handler_max_ns','spw_ack_propagation_ns']})
 r('ack_handler_actual_ns',exclusive_minimum_expression='spw_interrupt_propagation_ns',exclusive_maximum_expression='spw_ack_handler_max_ns')
 chain=('source_bound_ms','network_bound_ms','consumer_bound_ms')
 r('e2e_bound_ms',equal_expression={'sum':['spw_'+k for k in chain]})
 for k in chain:r(k,when_present=['spw_e2e_bound_ms'],required=True)
 r('e2e_bound_ms',maximum_parameter='spw_e2e_limit_ms');r('age_ms',maximum_parameter='spw_freshness_ms')
 w={'data_accepted':True}
 for k,v in [('state','RUN'),('got_null',True),('got_fct',True),('link_disabled',False),('parity_ok',True),('credit_trace_verified',True),('physical_verified',True),('route_verified',True),('outcome','ACCEPTED')]:r(k,w,required=True,allowed=[v])
 for k in('tx_bps','rx_bps','local_receive_max_bps','device_min_bps','device_max_bps','peer_receive_max_bps','encoding','parity','bit_order','bit_ui_ps','minimum_ui_ps','observation_source','e2e_bound_ms','e2e_limit_ms','age_ms','freshness_ms'):r(k,w,required=True)
 for k in('connector','termination_ohm','tx_cm_v','tx_diff_peak_v','tx_single_peak_v','tx_cm_imbalance_v','tx_single_imbalance_v','tx_dynamic_imbalance_v','rise_ps','fall_ps','monotonic','ringing_abs_v','ground_diff_v','logic','rx_diff_v','rx_cm_v','rx_p_v','rx_n_v'):
  r(k,{'data_accepted':True,'phy':'SPW_LVDS'},required=True)
 w={'data_accepted':True,'traffic':'PACKET'}
 r('end',w,required=True,allowed=['EOP'])
 for k in('packet_data_chars','packet_bits','address_bytes','higher_header_bytes'):r(k,w,required=True)
 w={'data_accepted':True,'traffic':'BROADCAST'}
 r('broadcast_supported',w,required=True,allowed=[True])
 for k in('broadcast_kind','broadcast_type','broadcast_value'):r(k,w,required=True)
 for k in('time_source','time_masters','time_value','previous_time'):r(k,{'data_accepted':True,'broadcast_kind':'TIME_CODE'},required=True)
 r('time_valid',{'data_accepted':True,'broadcast_kind':'TIME_CODE'},required=True,allowed=[True])
 for kind in('INTERRUPT','INTERRUPT_ACK'):
  for k in('interrupt_source','interrupt_id','relay_register_bits','interrupt_mode','interrupt_timeout_ns','interrupt_repeat_ns','interrupt_propagation_ns'):r(k,{'data_accepted':True,'broadcast_kind':kind},required=True)
  for k in('interrupt_sources','interrupt_acknowledgers','ack_propagation_ns','ack_handler_max_ns','ack_handler_actual_ns'):r(k,{'data_accepted':True,'broadcast_kind':kind,'interrupt_mode':'WITH_ACK'},required=True)
 return dict(rate_model={'type':'DEVICE_QUALIFIED_INDEPENDENT_SPW_DIRECTIONS','fields':[]},required_parameters=['spw_'+k for k in REQUIRED],native_parameter_prefixes=['spw_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='actual_spacewire_point_to_point_ds',medium_access_model='DIRECTIONAL_NCHAR_FCT_CREDIT',arbitration_model_id='FAIR_ROUTER_OUTPUT_WORMHOLE',mechanisms={'encoding':['DATA_STROBE_PREVIOUS_DATA_ODD_PARITY'],'flow':['FCT8_NCHAR_CREDIT56','NULL_AND_BROADCAST_OUTSIDE_NCHAR_CREDIT'],'routing':['PATH_DELETION','LOGICAL_MAPPING','FAIR_PACKET_OUTPUT_ARBITRATION'],'qualification':['PHY_SKEW_JITTER_AND_PEER_CAPABILITIES','NO_SINGLE_LINK_FUNCTIONAL_ACCEPTANCE']})

def fields():
 out=[]
 for spec in DECLARATIONS:
  k=spec['key'][4:];v={a:b for a,b in spec.items()if b is not None}
  v.update(label=k.replace('_',' '),category='technology',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  defaults=[]
  if k in('encoding','parity','bit_order','disconnect_ns','error_reset_us','error_wait_us'):
   defaults.append(dict(when={'spw_edition':'ECSS_2019','spw_proposal_mode':'SOURCE_BASELINE'},value={'encoding':'DATA_STROBE','parity':'ODD','bit_order':'LSB_FIRST','disconnect_ns':850,'error_reset_us':6.4,'error_wait_us':12.8}[k],source=ECSS,source_revision=SOURCES[ECSS]))
  if k=='tx_bps':
   for state in('ERROR_RESET','ERROR_WAIT','READY','STARTED','CONNECTING'):defaults.append(dict(when={'spw_edition':'ECSS_2019','spw_proposal_mode':'SOURCE_BASELINE','spw_state':state},value=10000000,source=ECSS,source_revision=SOURCES[ECSS]))
   defaults.append(dict(when={'spw_edition':'ECSS_2019','spw_proposal_mode':'SOURCE_BASELINE','spw_state':'RUN','spw_minimum_capability':'FULL_2M'},value=2000000,source=ECSS,source_revision=SOURCES[ECSS]))
  if k=='termination_ohm':defaults.append(dict(when={'spw_edition':'ECSS_2019','spw_proposal_mode':'SOURCE_BASELINE','spw_phy':'SPW_LVDS'},value=100,source=ECSS,source_revision=SOURCES[ECSS]))
  if defaults:v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=defaults)
  out.append(v)
 return out
