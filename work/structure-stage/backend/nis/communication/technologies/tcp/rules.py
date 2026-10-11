"""TCP RFC9293 stream/segment, explicitly selected extensions and algorithms.

Parameter relations are independent of IP/PHY capacity and of application
framing and acceptance. This module does not emulate an operating-system TCP.
"""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS, ETHERNET_KEYS
BASE='https://www.rfc-editor.org/rfc/rfc9293.html'
WS='https://www.rfc-editor.org/rfc/rfc7323.html'
RTO='https://www.rfc-editor.org/rfc/rfc6298.html'
RENO='https://www.rfc-editor.org/rfc/rfc5681.html'
CUBIC='https://www.rfc-editor.org/rfc/rfc9438.pdf'
IW10='https://www.rfc-editor.org/rfc/rfc6928.html'
SOURCES={BASE:'RFC9293 August2022 sections2/3.1-3.8; base TCP no physical clock/application-message boundary.',WS:'RFC7323 September2014 sections2-5; WS/TS negotiated, SYN window unscaled, PAWS clock distinct UTC.',RTO:'RFC6298 June2011 sections2-5: first/subsequentRTT, Karn, backoff; SHOULD defaults not hardware facts.',RENO:'RFC5681 September2009 sections2-4: Reno congestion/receive windows separate and loss recovery.',CUBIC:'RFC9438 August2023 sections3/4/5.1; originalPDF figures1/2 visually reviewed onprinted9. Own CUBIC windows use SMSS-sized segments not byte counters.',IW10:'RFC6928 April2013 Experimental sections1/2: optional IW10 upperbound, not universal default and no1500byteMTU assumption.'}
DECLARATIONS=[]
def d(k,t,meaning,source=BASE,**kw):DECLARATIONS.append(declaration('tcp_',k,t,meaning,source,SOURCES[source],**kw))
for k,meaning,opts in[
 ('edition','Actual base edition or separately qualified variant.',['RFC9293_2022','REGISTERED_ACTUAL']),
 ('proposal_mode','Explicit source baseline proposal versus actual negotiated configuration.',['SOURCE_BASELINE','ACTUAL_CONFIG']),
 ('ip_version','Actual bound IP version; TCP not implicitly Ethernet.',['IPV4','IPV6']),
 ('phase','Actual transmitted vs received segment; unknown receiver reserved bits ignored.',['SEND','RECEIVE']),
 ('state','Actual endpoint state, ACK does not prove application consumption.',['CLOSED','LISTEN','SYN_SENT','SYN_RECEIVED','ESTABLISHED','FIN_WAIT_1','FIN_WAIT_2','CLOSE_WAIT','CLOSING','LAST_ACK','TIME_WAIT']),
 ('congestion','Actual selected algorithm; no Reno rule applied to CUBIC/registered algorithms.',['RENO_RFC5681','CUBIC_RFC9438','REGISTERED_ACTUAL']),
 ('iw_profile','Actual initial-window policy independent of congestion avoidance algorithm.',['RFC5681','RFC6928_EXPERIMENT','REGISTERED_ACTUAL']),
 ('rto_profile','Actual timer policy; standard SHOULD floor vs separately evidenced deviation.',['RFC6298_BASELINE','REGISTERED_ACTUAL']),
 ('rto_phase','Actual initial, first RTT, updatedRTT or timeout state.',['INITIAL','FIRST_SAMPLE','SUBSEQUENT_SAMPLE','TIMEOUT']),
 ('recovery_phase','Actual no loss, slow start, Renoavoidance, timeout or fast recovery.',['NORMAL','SLOW_START','CONGESTION_AVOIDANCE','TIMEOUT','FAST_RECOVERY']),
 ('outcome','Actual correlated application data freshness/acceptance.',['ACCEPTED','STALE','ERROR','UNKNOWN']),
]:d(k,'select',meaning,options=opts,source=RENO if k in('congestion','iw_profile','recovery_phase')else RTO if k.startswith('rto_')else BASE)
for k,meaning,lo,hi,unit,integer in[
 ('src_port','Actual16-bit source port; wire value0 not a guessed service. ',0,65535,None,True),('dst_port','Actual16-bit destination port, endpoint binding must be explicit.',0,65535,None,True),
 ('sequence','Actual32bit first-octet/ISN number, modulo2^32.',0,4294967295,None,True),('acknowledgment','Actual32bit next expected octet, meaningful only ACKset.',0,4294967295,None,True),
 ('next_sequence','Actual sequence after data+SYN+FIN modulo2^32.',0,4294967295,None,True),('syn_units','Actual SYN consumes1 sequenceunit when set.',0,1,None,True),('fin_units','Actual FIN consumes1 sequenceunit when set.',0,1,None,True),
 ('data_offset','Actual count of32bit headerwords5..15.',5,15,'word',True),('header_bytes','Actual TCPheader20..60bytes includes options/pad.',20,60,'byte',True),
 ('options_bytes','Actual option+padding space, header−20.',0,40,'byte',True),('option_kind','Actual IANAoption kind; mandatory0/1/2 and selected3/8 checked.',0,255,None,True),
 ('option_length','Actual complete optionlength includes kind+length; EOL/NOP have no lengthfield.',0,40,'byte',True),
 ('reserved_bits','Actual4bit reservedfield, SENDzero unless separately registeredextension; receiverignore.',0,15,None,True),
 ('urgent_pointer','Actual16bit offset to octet afterurgentdata, not out-of-band deliveryproof.',0,65535,None,True),
 ('checksum','Actualmandatory16bit onescomplement checksum overheader/data/pseudoheader.',0,65535,None,True),('pseudoheader_bytes','ActualconceptualIPv4pseudoheader12/IPv640, not transmitted TCPbytes.',0,40,'byte',True),
 ('ip_protocol','ActualIPv4protocol/IPv6upperlayerNextHeader6.',0,255,None,True),
 ('data_bytes','Actualsegmentdata, no relationship to socketwrite boundaries.',0,None,'byte',True),('segment_bytes','Actual TCPheader+data, excludesIPheader/pseudoheader.',20,None,'byte',True),
 ('mss_received','Actual16bit peerMSS offer or sourcefallback when absent.',1,65535,'byte',True),('mss_advertised','ActuallocalofferedMSS limitedbyreceiveIPmessage−20.',1,65535,'byte',True),
 ('effective_mss','Actualeffective sendbudget afterTCP/IPoptions andpath/reassemblylimits.',0,None,'byte',True),
 ('mms_s','Actual IPmaximum transportmessage sendcapacity excludesfixedIPheader.',20,None,'byte',True),('mms_r','Actual IPreceive/reassemblymaximumtransportmessage capacity.',20,None,'byte',True),
 ('ip_options_bytes','ActualIPv4options/IPv6extensionheaders perpacket, notalways0.',0,None,'byte',True),
 ('window_wire','Actualunsigned16bit advertisedwindow; zero can persist.',0,65535,'byte',True),('window_effective','Actualscaledreceivewindow strictlyless1GiB.',0,1073725440,'byte',True),
 ('window_scale','Actuallocaltransmittedshift0..14, notglobaldefault14.',0,14,None,True),('window_scale_received','Actualreceived8bitshift, >14clampedwhenimplemented.',0,255,None,True),('window_scale_effective','Actualclamped receivedshift max14.',0,14,None,True),
 ('cwnd_bytes','Actualsendercongestionwindow byteunit, separate rwnd.',0,None,'byte',True),('rwnd_bytes','Actualreceiverwindow byteunit.',0,1073725440,'byte',True),
 ('flight_bytes','Actualoutstandingunacknowledgedbytecount, notcwnd.',0,None,'byte',True),('new_data_bytes','Actualadditionalnewdata allocation.',0,None,'byte',True),
 ('smss','Actualsendermaximumsegmentsizeusedby congestioncontrol.',1,None,'byte',True),('initial_window_bytes','Actualinitialcongestionwindow underselectedpolicy.',0,None,'byte',True),
 ('ssthresh_bytes','ActualRenoslowstartthreshold afterselectedlossevent.',0,None,'byte',True),('cwnd_increment_bytes','ActualReno cwndgrowth per selectedACK/RTT scope.',0,None,'byte',True),('newly_acked_bytes','Actualnewly cumulativelyacknowledgedbytes.',0,None,'byte',True),
 ('duplicate_acks','Actualsame-window/nonadvancingdupACKcount, notarbitraryrepeatmessages.',0,None,None,True),
 ('tsval','Actual32bit monotonicTCPtimestampclock, notUnixepoch.',0,4294967295,None,True),('tsecr','Actual32bit echotimestamp, onlyACKmeaningful.',0,4294967295,None,True),
 ('timestamp_tick_s','Actualtimestampclockinterval, maynotwrapwithinMSL.',0,None,'s',False),('timestamp_recycle_s','Actual2^32*tick fullrecycletime.',0,None,'s',False),
 ('msl_s','Actualmaximumsegmentlifetime bound, source2minutes isdesignproposal notactualpathproof.',0,None,'s',False),('time_wait_s','ActualTIME_WAITduration normally2MSL.',0,None,'s',False),
 ('idle_s','Actualidle time pertinent to PAWS staleclock.',0,None,'s',False),('keepalive_idle_s','Actualconfigurableidleprobeinterval; defaultatleast7200, commissioningmaydiffer.',0,None,'s',False),('keepalive_failures','Actualcountmissedprobes, onecannotdeclareddead.',0,None,None,True),
 ('delayed_ack_s','ActualACKdelay strictlyless0.5s, no500msinclusive.',0,.5,'s',False),('ack_every_segments','Actualsourcebaselineeverysecondfullsegments recommendation.',1,None,None,True),
 ('initial_rto_s','ActualinitialRTO1secondSHOULDbaseline; largerallowed.',0,None,'s',False),('rtt_sample_s','Actualunambiguous RTTsample.',0,None,'s',False),
 ('srtt_s','ActualsmoothedRTT, no guessedLAN1ms.',0,None,'s',False),('rttvar_s','ActualRTTvariation before4*multiplier.',0,None,'s',False),('previous_srtt_s','ActualoldSRTTusedbeforeupdate.',0,None,'s',False),('previous_rttvar_s','ActualoldRTTVAR.',0,None,'s',False),
 ('rto_s','ActualqualifiedRTOafterfloor/cap.',0,None,'s',False),('raw_rto_s','ActualSRTT+max(G,4RTTVAR).',0,None,'s',False),('previous_rto_s','Actualprevioustimeout beforebackoff.',0,None,'s',False),('rto_max_s','ActualoptionalRTOmaximum≥60s.',0,None,'s',False),
 ('clock_granularity_s','ActualclockgranularityG, notuniversal1ms.',0,None,'s',False),('alpha','ActualSRTTupdateweight, source1/8SHOULDproposal.',0,1,None,False),('beta','Actualvariationupdateweight, source1/4SHOULDproposal.',0,1,None,False),
 ('source_ms','Actualsource/applicationframing/serializerbound.',0,None,'ms',False),('transport_ms','Actualhandshake/queue/stream/retransmit/IP/PHYbound.',0,None,'ms',False),('consumer_ms','Actualreassembly/applicationframing/consume bound.',0,None,'ms',False),
 ('e2e_ms','Actualcomplete source+transport+consumerbound.',0,None,'ms',False),('deadline_ms','Actualindependentfunctionaldeadline.',0,None,'ms',False),('age_ms','Actualcorrelatedconsumingdataage.',0,None,'ms',False),('freshness_ms','Actualallowedage.',0,None,'ms',False),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=integer,source=RTO if k in('initial_rto_s','rtt_sample_s','srtt_s','rttvar_s','previous_srtt_s','previous_rttvar_s','rto_s','raw_rto_s','previous_rto_s','rto_max_s','clock_granularity_s','alpha','beta')else WS if k.startswith('window_scale')or k in('timestamp_tick_s','timestamp_recycle_s','tsval','tsecr','idle_s')else RENO if k in('cwnd_bytes','rwnd_bytes','flight_bytes','new_data_bytes','smss','initial_window_bytes','ssthresh_bytes','cwnd_increment_bytes','newly_acked_bytes','duplicate_acks')else BASE)
for k,meaning in[
 ('syn','ActualSYNcontrolbit.'),('fin','ActualFINcontrolbit.'),('ack','ActualACKcontrolbit.'),('rst','ActualRSTcontrolbit.'),('urg','ActualURGcontrolbit.'),('psh','ActualPSHflag doesnotpreserveapplicationmessages.'),('ece','ActualECNecho underseparatelyqualifiedECN.'),('cwr','ActualECNwindow-reducedflag.'),
 ('mss_option_received','ActualpeerMSSoptionreceivedin handshake.'),('ws_local_offer','ActuallocalWSoptionin SYN.'),('ws_peer_offer','ActualpeerWSoptioninSYN.'),('ws_negotiated','ActualbothsidesofferedWS.'),
 ('ts_local_offer','ActuallocalTSoptioninSYN.'),('ts_peer_offer','ActualpeerTSoptioninSYN.'),('ts_negotiated','ActualbothsidesnegotiatedTS.'),('timestamp_present','ActualTSoptionpresent inthissegment.'),('timestamp_unambiguous','Actualcorrelatedecho identifies retransmissionRTTsample.'),
 ('sample_retransmitted','ActualRTTsample wouldderivefromretransmittedsegment.'),('keepalive_enabled','Actualoptionalkeepalive enabled, defaultoff.'),('connection_dead','Actualconnection declareddead, singlemissedprobe insufficient.'),
 ('rto_cap_enabled','ActualconfiguredRTOcap, not an assumed60seconddefault.'),
 ('paws_recent_valid','ActualTS.Recentclockstillvalid, >24dayidle mustinvalidate.'),('checksum_verified','ActualwholeTCP+IPpseudoheader checksumvalidation.'),('padding_zero','ActualheaderpaddingafterEOLzero.'),
 ('nagle_enabled','Actualshortsegmentcoalescing, applicationmustbeabletodisable.'),('nagle_disable_supported','Actualperconnectionapplicationcontrol.'),('sws_verified','Actualsender/receiverSWSavoidancequalified.'),('zero_window_probe_verified','Actualzero-window probes supported.'),
 ('ip_binding_verified','ActualseparateIPandlowerPHYpathconfiguration verified.'),('framing_verified','Actualapplicationmessageframing/reassemblyverified.'),('congestion_verified','Actualselectedalgorithmimplementationqualification.'),('data_accepted','Actualconsumingapplicationaccepted independently.'),
]:d(k,'boolean',meaning,source=WS if k.startswith(('ws_','ts_','timestamp','paws'))else RTO if k in('sample_retransmitted','rto_cap_enabled')else BASE)
for k,meaning in[
 ('revision','ActualOS/firmware/TCPimplementation revision.'),('binding_source','Actualendpointtuple/IPversion/lowerprofilebinding.'),('configuration_source','Actualconnection/socket/negotiationconfiguration.'),
 ('path_source','ActualIP/PHY/PMTU/reassembly/queue/pathqualification.'),('algorithm_source','Actualcongestion/recovery/RTO/extensionimplementation source.'),('framing_source','Actualapplicationcodec/framing/reassemblyrules.'),('schedule_source','Actualwholehandshake/queue/loss/probe/service/timingbounds.'),
 ('acceptance_source','Actualfunctional deadline/consumingage/behavior requirement.'),('observation_source','Actualcorrelatedsource/segment/ACK/consumertrace.'),('registered_source','Actualseparatelyregisteredversions/algorithms/extensionsschema.'),
 ('source_address','ActualboundunicastsourceIPaddress, nosocketdefaultguess.'),('destination_address','ActualboundunicastdestinationIPaddress.'),
]:d(k,'text',meaning,**({'format':'IP_ADDRESS'}if k.endswith('address')else {}))
for k,meaning,lo,hi,unit in[
 ('cubic_c','ActualCUBICaggressivenessconstant, source0.4SHOULD.',0,None,'segment/s^3'),('cubic_beta','ActualCUBICmultiplicativedecrease source0.7SHOULD, notReno0.5.',0,1,None),
 ('cubic_t_s','Actualeligibleelapsedavoidancetime excludesapplicationlimitedidle.',0,None,'s'),('cubic_k_s','Actualsignedcube-root time from(Wmax−epochwindow)/C.',None,None,'s'),
 ('cubic_wmax','Actualprior saturationwindow inSMSS-sizedsegments.',0,None,'segment'),('cubic_epoch_window','Actualwindowatavoidanceepoch inSMSS-sizedsegments.',0,None,'segment'),
 ('cubic_window','ActualC*(t−K)^3+Wmax, segmentunit.',0,None,'segment'),('cubic_target','ActualclampednextRTTtarget between cwnd and1.5*cwnd.',0,None,'segment'),('cubic_cwnd','ActualCUBICcurrentcwnd inSMSS-sizedsegments, notbytes.',0,None,'segment'),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=False,source=CUBIC)
REQUIRED=('edition','ip_version','revision','binding_source','configuration_source','path_source','algorithm_source','framing_source','schedule_source','acceptance_source')
REMOVED={k:'TCP is a byte stream over an actual separate IP/PHY binding. No CAN clock/retry/gateway or inheritedEthernetMTU/duplex/rate default.'for k in(*WIRE_KEYS,*ETHERNET_KEYS)}

def semantics():
 rules=[]
 def r(k,w=None,source=BASE,**kw):rules.append(dict(parameter='tcp_'+k,when={'tcp_edition':'RFC9293_2022',**{'tcp_'+a:b for a,b in(w or{}).items()}},source=source,**kw))
 rules.append(dict(parameter='tcp_registered_source',when={'tcp_edition':'REGISTERED_ACTUAL'},required=True,source=BASE))
 for k in('source_address','destination_address'):r(k,{'ip_version':'IPV4'},ip_address_version=4);r(k,{'ip_version':'IPV6'},ip_address_version=6)
 r('header_bytes',equal_expression={'product':['tcp_data_offset',4]});r('options_bytes',equal_expression={'subtract':['tcp_header_bytes',20]})
 r('segment_bytes',equal_expression={'sum':['tcp_header_bytes','tcp_data_bytes']});r('ip_protocol',allowed=[6]);r('reserved_bits',{'phase':'SEND'},allowed=[0])
 r('pseudoheader_bytes',{'ip_version':'IPV4'},allowed=[12]);r('pseudoheader_bytes',{'ip_version':'IPV6'},allowed=[40]);r('checksum_verified',allowed=[True]);r('padding_zero',allowed=[True])
 for k in('syn','fin'):r(k+'_units',{k:True},allowed=[1]);r(k+'_units',{k:False},allowed=[0])
 r('next_sequence',equal_expression={'integer_remainder':[{'sum':['tcp_sequence','tcp_data_bytes','tcp_syn_units','tcp_fin_units']},4294967296]})
 r('mss_received',{'mss_option_received':False,'ip_version':'IPV4'},allowed=[536]);r('mss_received',{'mss_option_received':False,'ip_version':'IPV6'},allowed=[1220])
 r('mss_advertised',maximum_expression={'subtract':['tcp_mms_r',20]})
 r('effective_mss',equal_expression={'subtract':[{'minimum':[{'sum':['tcp_mss_received',20]},'tcp_mms_s']},{'sum':['tcp_header_bytes','tcp_ip_options_bytes']}]})
 r('data_bytes',maximum_parameter='tcp_effective_mss')
 r('option_length',{'option_kind':2},allowed=[4]);r('option_length',{'option_kind':3},allowed=[3]);r('option_length',{'option_kind':8},allowed=[10])
 for kind in(0,1):r('option_length',{'option_kind':kind},allowed=[])
 r('syn',{'phase':'SEND','option_kind':3},required=True,allowed=[True]);r('window_scale_effective',equal_expression={'minimum':['tcp_window_scale_received',14]},source=WS)
 for k in('ws_local_offer','ws_peer_offer'):r(k,{'ws_negotiated':True},required=True,allowed=[True],source=WS)
 r('window_effective',{'syn':True},equal_parameter='tcp_window_wire',source=WS);r('window_effective',{'ws_negotiated':False},equal_parameter='tcp_window_wire',source=WS)
 r('window_effective',{'syn':False,'ws_negotiated':True},equal_expression={'product':['tcp_window_wire',{'power':[2,'tcp_window_scale_effective']}]},source=WS)
 for k in('ts_local_offer','ts_peer_offer'):r(k,{'ts_negotiated':True},required=True,allowed=[True],source=WS)
 r('timestamp_present',{'ts_negotiated':True,'rst':False},required=True,allowed=[True],source=WS)
 r('timestamp_recycle_s',equal_expression={'product':['tcp_timestamp_tick_s',4294967296]},source=WS);r('timestamp_recycle_s',exclusive_minimum_expression='tcp_msl_s',source=WS)
 r('paws_recent_valid',when_greater_than={'tcp_idle_s':2073600},allowed=[False],source=WS)
 r('time_wait_s',{'state':'TIME_WAIT'},equal_expression={'product':[2,'tcp_msl_s']})
 r('delayed_ack_s',exclusive_maximum=.5)
 for k in('nagle_disable_supported','sws_verified','zero_window_probe_verified'):r(k,allowed=[True])
 r('connection_dead',{'keepalive_enabled':True,'keepalive_failures':1},allowed=[False])
 r('initial_rto_s',{'rto_profile':'RFC6298_BASELINE'},minimum=1,source=RTO);r('rto_max_s',minimum=60,source=RTO)
 r('raw_rto_s',equal_expression={'sum':['tcp_srtt_s',{'maximum':['tcp_clock_granularity_s',{'product':[4,'tcp_rttvar_s']}]}]},source=RTO)
 r('rto_cap_enabled',when_present=['tcp_rto_s'],required=True,source=RTO)
 r('rto_max_s',{'rto_cap_enabled':True},required=True,source=RTO)
 r('rto_s',{'rto_profile':'RFC6298_BASELINE','rto_cap_enabled':False},minimum_expression={'maximum':[1,'tcp_raw_rto_s']},source=RTO)
 r('rto_s',{'rto_profile':'RFC6298_BASELINE','rto_cap_enabled':True},minimum_expression={'minimum':[{'maximum':[1,'tcp_raw_rto_s']},'tcp_rto_max_s']},source=RTO)
 r('rto_s',maximum_parameter='tcp_rto_max_s',source=RTO)
 r('srtt_s',{'rto_phase':'FIRST_SAMPLE'},equal_parameter='tcp_rtt_sample_s',source=RTO);r('rttvar_s',{'rto_phase':'FIRST_SAMPLE'},equal_expression={'product':[.5,'tcp_rtt_sample_s']},source=RTO)
 r('srtt_s',{'rto_phase':'SUBSEQUENT_SAMPLE'},equal_expression={'sum':[{'product':[{'subtract':[1,'tcp_alpha']},'tcp_previous_srtt_s']},{'product':['tcp_alpha','tcp_rtt_sample_s']}]},source=RTO)
 r('rttvar_s',{'rto_phase':'SUBSEQUENT_SAMPLE'},equal_expression={'sum':[{'product':[{'subtract':[1,'tcp_beta']},'tcp_previous_rttvar_s']},{'product':['tcp_beta',{'maximum':[{'subtract':['tcp_previous_srtt_s','tcp_rtt_sample_s']},{'subtract':['tcp_rtt_sample_s','tcp_previous_srtt_s']}]}]}]},source=RTO)
 r('timestamp_unambiguous',{'sample_retransmitted':True},required=True,allowed=[True],source=RTO)
 r('ts_negotiated',{'sample_retransmitted':True,'timestamp_unambiguous':True},required=True,allowed=[True],source=RTO)
 r('rto_s',{'rto_phase':'INITIAL'},equal_parameter='tcp_initial_rto_s',source=RTO)
 r('rto_s',{'rto_phase':'TIMEOUT','rto_cap_enabled':False},minimum_expression={'product':[2,'tcp_previous_rto_s']},source=RTO)
 r('rto_s',{'rto_phase':'TIMEOUT','rto_cap_enabled':True},minimum_expression={'minimum':[{'product':[2,'tcp_previous_rto_s']},'tcp_rto_max_s']},source=RTO)
 for phase in('FIRST_SAMPLE','SUBSEQUENT_SAMPLE'):
  for k in('srtt_s','rttvar_s','rtt_sample_s'):r(k,{'rto_phase':phase},required=True,source=RTO)
 for k in('previous_srtt_s','previous_rttvar_s','alpha','beta'):r(k,{'rto_phase':'SUBSEQUENT_SAMPLE'},required=True,source=RTO)
 r('new_data_bytes',maximum_expression={'maximum':[0,{'subtract':[{'minimum':['tcp_cwnd_bytes','tcp_rwnd_bytes']},'tcp_flight_bytes']}]},source=RENO)
 for lo,hi,n in [(0,1096,4),(1096,2191,3),(2191,None,2)]:
  r('initial_window_bytes',{'iw_profile':'RFC5681'},when_half_open_ranges={'tcp_smss':[lo,hi]},maximum_expression={'product':[n,'tcp_smss']},source=RENO)
 r('initial_window_bytes',{'iw_profile':'RFC6928_EXPERIMENT'},maximum_expression={'minimum':[{'product':[10,'tcp_smss']},{'maximum':[{'product':[2,'tcp_smss']},14600]}]},source=IW10)
 r('ssthresh_bytes',{'congestion':'RENO_RFC5681','recovery_phase':'TIMEOUT'},maximum_expression={'maximum':[{'product':[.5,'tcp_flight_bytes']},{'product':[2,'tcp_smss']}]},source=RENO)
 r('cwnd_bytes',{'congestion':'RENO_RFC5681','recovery_phase':'TIMEOUT'},maximum_parameter='tcp_smss',source=RENO)
 r('cwnd_increment_bytes',{'congestion':'RENO_RFC5681','recovery_phase':'SLOW_START'},maximum_expression={'minimum':['tcp_smss','tcp_newly_acked_bytes']},source=RENO)
 r('cwnd_increment_bytes',{'congestion':'RENO_RFC5681','recovery_phase':'CONGESTION_AVOIDANCE'},maximum_parameter='tcp_smss',source=RENO)
 for k in('algorithm_source','registered_source'):r(k,{'congestion':'REGISTERED_ACTUAL'},required=True,source=RENO)
 r('cubic_c',{'congestion':'CUBIC_RFC9438'},exclusive_minimum=0,source=CUBIC);r('cubic_beta',{'congestion':'CUBIC_RFC9438'},exclusive_minimum=0,exclusive_maximum=1,source=CUBIC)
 r('cubic_window',{'congestion':'CUBIC_RFC9438'},equal_expression={'sum':[{'product':['tcp_cubic_c',{'power':[{'subtract':['tcp_cubic_t_s','tcp_cubic_k_s']},3]}]},'tcp_cubic_wmax']},source=CUBIC)
 r('cubic_epoch_window',{'congestion':'CUBIC_RFC9438'},equal_expression={'subtract':['tcp_cubic_wmax',{'product':['tcp_cubic_c',{'power':['tcp_cubic_k_s',3]}]}]},source=CUBIC)
 cubic_next={'sum':[{'product':['tcp_cubic_c',{'power':[{'subtract':[{'sum':['tcp_cubic_t_s','tcp_srtt_s']},'tcp_cubic_k_s']},3]}]},'tcp_cubic_wmax']}
 r('cubic_target',{'congestion':'CUBIC_RFC9438'},equal_expression={'minimum':[{'maximum':[cubic_next,'tcp_cubic_cwnd']},{'product':[1.5,'tcp_cubic_cwnd']}]},source=CUBIC)
 r('cubic_target',{'congestion':'CUBIC_RFC9438'},minimum_parameter='tcp_cubic_cwnd',maximum_expression={'product':[1.5,'tcp_cubic_cwnd']},source=CUBIC)
 for k in('cubic_c','cubic_k_s','cubic_t_s','cubic_wmax'):r(k,{'congestion':'CUBIC_RFC9438'},when_present=['tcp_cubic_window'],required=True,source=CUBIC)
 for k in('cubic_c','cubic_beta'):r(k,{'congestion':'CUBIC_RFC9438'},required=True,source=CUBIC)
 for k in('cubic_c','cubic_k_s','cubic_wmax'):r(k,{'congestion':'CUBIC_RFC9438'},when_present=['tcp_cubic_epoch_window'],required=True,source=CUBIC)
 for k in('cubic_c','cubic_k_s','cubic_t_s','cubic_wmax','cubic_cwnd','srtt_s'):r(k,{'congestion':'CUBIC_RFC9438'},when_present=['tcp_cubic_target'],required=True,source=CUBIC)
 r('e2e_ms',equal_expression={'sum':['tcp_source_ms','tcp_transport_ms','tcp_consumer_ms']});r('e2e_ms',maximum_parameter='tcp_deadline_ms');r('age_ms',maximum_parameter='tcp_freshness_ms')
 for k in('source_ms','transport_ms','consumer_ms'):r(k,when_present=['tcp_e2e_ms'],required=True)
 for k in('source_address','destination_address','src_port','dst_port','state','congestion','observation_source','e2e_ms','deadline_ms','age_ms','freshness_ms'):r(k,{'data_accepted':True},required=True)
 for k,v in [('ip_binding_verified',True),('framing_verified',True),('congestion_verified',True),('outcome','ACCEPTED')]:r(k,{'data_accepted':True},required=True,allowed=[v])
 return dict(rate_model={'type':'STREAM_NO_UNIVERSAL_CLOCK','fields':[]},parameter_evidence_scope='EXPLICIT_LAYER',required_parameters=['tcp_'+k for k in REQUIRED],native_parameter_prefixes=['tcp_'],parameter_constraints=rules,medium_access_model='CONNECTION_STREAM_OVER_EXPLICIT_IP',arbitration_model_id='ACTUAL_CONGESTION_FLOW_QUEUE_AND_LOSS',mechanisms={'stream':['NO_APPLICATION_MESSAGE_BOUNDARIES','MSS_OPTION_AND_EFFECTIVE_SEND_BUDGET'],'flow':['RWND_SEPARATE_CWND','NEGOTIATED_WS_TS'],'qualification':['OWN_ALGORITHM_AND_TIMERS','IP_PHY_AND_FUNCTIONAL_EVIDENCE_SEPARATE']})

def fields():
 baseline={'tcp_edition':'RFC9293_2022','tcp_proposal_mode':'SOURCE_BASELINE'}
 proposals={}
 for k,v,source,extra in [('header_bytes',20,BASE,{'tcp_options_bytes':0}),('initial_rto_s',1,RTO,{'tcp_rto_profile':'RFC6298_BASELINE'}),('alpha',.125,RTO,{'tcp_rto_profile':'RFC6298_BASELINE'}),('beta',.25,RTO,{'tcp_rto_profile':'RFC6298_BASELINE'}),('keepalive_enabled',False,BASE,{}),('keepalive_idle_s',7200,BASE,{}),('nagle_enabled',True,BASE,{}),('ack_every_segments',2,BASE,{}),('cubic_c',.4,CUBIC,{'tcp_congestion':'CUBIC_RFC9438'}),('cubic_beta',.7,CUBIC,{'tcp_congestion':'CUBIC_RFC9438'})]:
  proposals['tcp_'+k]=[dict(when={**baseline,**extra},value=v,source=source,source_revision=SOURCES[source])]
 proposals['tcp_mss_received']=[dict(when={**baseline,'tcp_mss_option_received':False,'tcp_ip_version':version},value=value,source=BASE,source_revision=SOURCES[BASE])for version,value in [('IPV4',536),('IPV6',1220)]]
 out=build_fields(DECLARATIONS,['tcp_'+k for k in REQUIRED],proposals)
 for f in out:
  if f['key']not in {'tcp_'+k for k in REQUIRED}|{'tcp_proposal_mode','tcp_registered_source'}:f['schema_when']={'tcp_edition':'RFC9293_2022'}
 return out
