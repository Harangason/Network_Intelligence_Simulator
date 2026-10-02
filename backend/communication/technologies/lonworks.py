"""Source-qualified LonTalk channels, addressing and device buffers."""
GUIDE='https://www.lonmark.org/wp-content/uploads/2020/01/LmPhy34.pdf'
XCVR='https://www.lonmark.org/wp-content/uploads/2020/06/stdXcvr.zip'
ROUTER='https://www.renesas.com/en/document/mat/lonworks-router-user-s-guide?r=1609871'
PROGRAM='https://www.renesas.com/en/document/mat/neuron-c-programmers-guide'
REFERENCE='https://www.renesas.cn/zh/document/mat/neuron-c-reference-guide'
PROTO='https://pahl.de/download/dissertation/ds2os.lab/files/lontalk_protocol_spec.pdf'
CURRENT='https://www.lonmark.org/technology/technical-resources/guidelines/'
SOURCES={GUIDE:'LonMark Layer1-6 guidelines3.4 September2005/078-0120-01G: channel tables,TPFT/FO/IP852,sharedchannelparameters,buffers,transactions',
 XCVR:'LonMark StdXcvr7.32.1.32,2006-06-21: exact XML selected eight transceiver entries; encoded Timing values not inferred microseconds',
 ROUTER:'Echelon router078-0018-01H copyright2014; appendix firmware5plus,network versus chipinterface rates,router buffers; not every node',
 PROGRAM:'Echelon NeuronC2.2 programmer078-0002-02H copyright2009: NV31,application-data228,services/authentication/explicitaddressing andcompilerbuffer defaults',
 REFERENCE:'Echelon NeuronC2.3 reference078-0140-01G copyright2014: chip-series address-tablelimits; utilityCRC is not wireCRC proof',
 PROTO:'Echelon LonTalk3.0 original1989-1994,archived primary-authored document atPahl; reviewed address/MAC/CRC/transport/timer/management/PDU sections; notcurrentlicensedISO',
 CURRENT:'LonMark publisherguidelines/resources accessed2026-10-02; exact implementation/ISOrevision required independently'}
OLD='LONTALK_3_1994'
G='GUIDELINES_3_4_2005'
X='STD_XCVR_7_32_1_32'
R='ROUTER_FW5PLUS_01H'
# Nominal medium rates in the guideline are distinct from effective transceiver
# network rates and the faster Neuron-to-transceiver interface clock.
GUIDELINE_CHANNELS={
 'TP_XF_1250':(1250000,16,10,'DIFFERENTIAL'),
 'TP_XF_78':(78000,4,5,'DIFFERENTIAL'),
 'TP_RS485_39':(39000,4,5,'SINGLE_ENDED'),
 'TP_FT_10':(78125,4,5,'SINGLE_ENDED'),
 'PL_20_LN':(5000,8,1.25,'SPECIAL_PURPOSE'),
 'PL_20_LE':(5000,8,1.25,'SPECIAL_PURPOSE'),
 'PL_20A_LN':(3600,8,1.25,'SPECIAL_PURPOSE'),
 'FO_20S':(1250000,16,10,'SINGLE_ENDED'),
 'FO_20L':(1250000,16,10,'SINGLE_ENDED')}
# Exact XML values; raw timing codes have deliberately no invented time unit.
STANDARD_TRANSCEIVERS={
 'TP_XF_1250':(1,1250000,16,5,1,(140,0,250,0,10,0,40,70)),
 'TP_XF_78':(2,78125,4,4,1,(29,0,240,0,10,0,10,50)),
 'TP_RS485_39':(3,39063,4,4,0,(20,0,40,0,10,0,10,40)),
 'TP_FT_10':(7,78125,4,4,0,(90,0,240,0,0,0,40,40)),
 'PL_20C':(8,3987,8,3,2,(73,16,101,175,335,0,0,0)),
 'PL_20N':(9,3987,8,3,2,(73,16,101,175,335,0,0,0)),
 'FO_20S':(24,1250000,4,5,0,(1450,40,40,40,10,0,40,80)),
 'FO_20L':(152,1250000,4,5,0,(12900,40,40,40,10,0,40,80))}
RAW_TIMINGS=['rcv_start_delay','rcv_end_delay','indeterm_time','min_interpkt','preamble','turnaround','missed_pream','packet_qual']
CHANNELS=sorted(set(GUIDELINE_CHANNELS)|set(STANDARD_TRANSCEIVERS)|{'IP_852','PL_10_DEPRECATED','PL_30_DEPRECATED','REGISTERED_CHANNEL'})
DECLARATIONS=[]


def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,integer=False,source=GUIDE,**extra):
    DECLARATIONS.append(dict(key='lw_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,options=options,
        integer=integer,source=source,source_revision=SOURCES[source],**extra))


for key,meaning,options in [
 ('protocol','Actual LonTalk3 versus independently registered currentISO/other implementation; no implied 1994 conformance.',[OLD,'REGISTERED_PROTOCOL']),
 ('channel_profile','Actual source-qualified channel parameter set; conflicting guide/XML/router rows remain distinct.',[G,X,R,'REGISTERED_PROFILE']),
 ('channel','Actual physical channel/transceiver; TPFT,Powerline,fiber andIP852 are not interchangeable.',CHANNELS),
 ('role','Actual application node,network tool,router/repeater/gateway; no CANmaster/slave inference.',['APPLICATION','NETWORK_TOOL','ROUTER','REPEATER','GATEWAY']),
 ('comm_port_mode','Actual Neuron physical communications port mode,not UART8N1.',['SINGLE_ENDED','DIFFERENTIAL','SPECIAL_PURPOSE','IP_TUNNEL','REGISTERED_MODE']),
 ('payload_kind','Actual network variable versus explicit application/foreign-frame versus management traffic.',['NETWORK_VARIABLE','APPLICATION_MESSAGE','FOREIGN_FRAME','RESPONDER_OFFLINE','FOREIGN_RESPONDER_OFFLINE','NETWORK_DIAGNOSTIC','NETWORK_MANAGEMENT','REGISTERED_PAYLOAD']),
 ('service','Actual ACKD,UNACKD,UNACKD_RPT orrequest/response,not universal CANretry.',['ACKD','UNACKD','UNACKD_RPT','REQUEST']),
 ('address_format','Actual destination format andgroupACK returnformat; physicalNeuronID is notlogicalnodeaddress.',['BROADCAST','GROUP','SUBNET_NODE','GROUP_ACK','NEURON_ID']),
 ('node_state','Actual unconfigured/applicationoffline/online state,not automatic successful operation.',['UNCONFIGURED','OFFLINE','ONLINE']),
 ('topology','Actual terminatedbus/free topology versusactivefiber path.',['DOUBLE_TERMINATED_BUS','SINGLE_TERMINATED_FREE','ACTIVE_RING','ACTIVE_BUS','REGISTERED_TOPOLOGY']),
 ('cable_profile','Actual source-qualified cable; other cable limits needregisteredsource.',['CAT5_24AWG_568A','UL_LEVEL_IV_22AWG','FIBER_62_5_125_492AAAA_A','REGISTERED_CABLE']),
 ('buffer_profile','Actual Neuron2.2 compiler versusactualRTR10/RTR3150router orotherbuffers.',['NEURON_C_2_2','RTR10_01H','RTR3150_01H','REGISTERED_BUFFERS']),
 ('router_firmware','Actual RTR10 firmware A/B/C; their total memory capacities differ, not a universal1254-byte queue budget.',['A','B','C','REGISTERED_FIRMWARE']),
 ('chip_series','Actual legacy3120/3100/5000 versus6000 implementation andfirmware.',['3120','3100','5000','6000','REGISTERED_CHIP']),
 ('authentication_profile','Actuallegacy48bit challenge-response versuscurrentregisteredsecurity; notencryption.',['LEGACY_48_BIT','REGISTERED_SECURITY']),
 ('timer_policy','Actual transactiontiming versus optionalsingle-channel1994recommendation; multi-channel measured independently.',['ACTUAL_TRANSACTION_BOUND','LONTALK3_SINGLE_CHANNEL_RECOMMENDATION']),
 ('wire_bit_order','Actualcodec-resolved ordering; source appendixLSB andmanagementtextMSB conflict, no default assumption.',['LSB_FIRST','MSB_FIRST']),
 ('temperature_profile','Actualsource-qualifiedTPXFambient/load envelope; no blanket64nodes at extendedtemperature.',['RANGE_0_70','XF78_MINUS40_85','XF1250_MINUS20_85','XF1250_MINUS40_70','REGISTERED_ENVIRONMENT']),
 ('wiring_case','Actualworst-case versus exacttypicalbenchmark20C/5V/64evennodes; typicallength isnotgenericmaximum.',['WORST_CASE','TYPICAL_ROOM_5V_64_EVEN','REGISTERED_WIRING']),
 ('pl_coupling','ActualPowerlineline-neutral versusline-earth coupling.',['LINE_NEUTRAL','LINE_EARTH']),
 ('modulation','Actualselectedmediumencoding,notCANbitstuffing.',['BPSK','DIFFERENTIAL_MANCHESTER','REGISTERED_MODULATION'])]:d(key,'select',meaning,options=options,source=ROUTER if key=='router_firmware' else GUIDE)
for key,meaning,source in [
 ('revision','Actual complete protocol/channel/security/device/firmware revisions.',CURRENT),
 ('registered_source','Actual registeredalternative/currentchannel/protocol/cable/buffer/security schema.',CURRENT),
 ('device_source','Actual chip/transceiver/board/firmware/XIF andcapabilities.',GUIDE),
 ('transceiver_source','Actual source-qualifiedtransceiverentry andchannel parameters,not generic78000.',XCVR),
 ('binding_source','Actual canonical Lon channel/port; other routed/gateway/media independently registered.',GUIDE),
 ('physical_source','Actualcable/power/terminators/noise/link-budget/clock/propagation realization.',GUIDE),
 ('commissioning_source','Actualdomain/subnet/node/group/channel uniqueness,XIF andresourcefiles.',PROTO),
 ('encoding_source','ActualSNVT/UNVT/SCPT/messagecode/PDU/CRC/order; no guessed8bytevalveencoding.',PROTO),
 ('schedule_source','Actualbacklog/priority/beta/retries/ACKs/routers/alltraffic sharedcapacity.',GUIDE),
 ('capacity_source','Actual completechannel andeachrouter/gateway/PHY capacity evidence.',GUIDE),
 ('acceptance_source','Actual functionalE2E/freshness/safety,notACK/CRC accepted as completedactuation.',GUIDE),
 ('security_source','Actualcredential/provisioning/challenge/response/securityedition evidence.',PROGRAM),
 ('key_ref','Actualsecretreference only; never manufactured default credential.',PROGRAM),
 ('power_source','Actual linkpowerPSU/loading proof separatefromlogicalnodecounts.',GUIDE),
 ('router_source','Actualrouterfirmware/mode/forwardingtables/buffering/channelclocklimits.',ROUTER),
 ('timer_source','Actualencodedtimer mapping,transactiontime/retries/serverprocessing/multichannel measurements.',PROTO),
 ('domain_id','Actualcanonicaldomainhex,0/1/3/6bytes; noautoallocateddomain.',PROTO),
 ('neuron_id','Actualmanufactureassigned48bitNeuronID,not changing logicalsubnet/node.',PROTO),
 ('resource_type','ActualselectedSNVT/UNVT/SCPT definition/version andsignalcodec.',PROGRAM)]:d(key,'text',meaning,source=source)

for key,meaning,lo,hi,unit,integer,source in [
 ('medium_nominal_bps','Source-qualified nominalchannelrate; not effectivePLnetwork orchipinterface rate.',1,None,'bit/s',True,GUIDE),
 ('network_bitrate_bps','Actualselectedtransceiver networkrate,independentfromNeuroninterface.',1,None,'bit/s',True,XCVR),
 ('neuron_interface_bps','ActualNeurontoexternaltransceiverclock; PL20interface156250 is not network3987.',1,None,'bit/s',True,ROUTER),
 ('channel_min_clock_mhz','Configuredsource-qualified minimumchipclock; not measurementofactualoscillator.',0,None,'MHz',False,GUIDE),
 ('device_clock_mhz','Actualchipclock; must meetselectedchannelminimumanddevicecapability.',0,None,'MHz',False,GUIDE),
 ('oscillator_error_ppm','Actualabsoluteoscillatorerroracrossinstalledtemperature;200ppm ismaximum,notdefaultactualerror.',0,None,'ppm',False,GUIDE),
 ('priority_slots','Actualchannelmaxprioritycount; sourcequalified4/8/16proposals canbechangedbytool; allnodesmustmatch.',0,127,None,True,PROTO),
 ('device_priority_slot','Actualuniqueslotallocatedbytool; applicationmustnotuseslot1.',0,127,None,True,PROTO),
 ('avg_packet_estimate_octets','Configuredbacklog-estimatoraveragepacket15octetproposal,notactualpayloadlength.',1,None,'Byte',True,GUIDE),
 ('backlog','ActualpredictiveCSMAbacklog≥1; notguessedoneguarantee.',1,None,None,True,PROTO),
 ('backlog_increment','Actual6bitL2expectedresponsesincrement.',0,63,None,True,PROTO),
 ('random_window_base','ConfiguredCSMAbasewindow16 recommendation,notlatencyguarantee.',1,None,None,True,PROTO),
 ('propagation_us','Actualmaximumphysicalpropagationtime.',0,None,'us',False,PROTO),
 ('mac_turnaround_us','Actualdetection/transmissionstartdelay,notdefault0.',0,None,'us',False,PROTO),
 ('beta1_us','Actualidledetectionperiod>onebittime+2propagation+MACdelay indirectmode.',0,None,'us',False,PROTO),
 ('beta2_us','Actualrandomslotwidthstrictly>2propagation+MACdelay.',0,None,'us',False,PROTO),
 ('reference_preamble_us','Source-qualifiedFO10MHz reference221.4..229.8us; not genericallmedium preamble.',0,None,'us',False,GUIDE),
 ('reference_packet_cycle_us','FO10MHz table reference4020us,notactualworstpacketduration.',0,None,'us',False,GUIDE),
 ('reference_beta2_us','FO10MHz tableS132/L1056us,notinterchangeable.',0,None,'us',False,GUIDE),
 ('packet_cycle_bound_us','Actualwholetransaction packetcycle bound,notaveragetabletakenasguarantee.',0,None,'us',False,PROTO),
 ('tx_completion_margin_us','Actualreceiverprocessing/ACKcompletion marginforchosenrecommendation.',0,None,'us',False,PROTO),
 ('retry_count','Actual4bitretrycount0..15;2..5recommendationonlyselectedsingle-channelpolicy.',0,15,None,True,PROTO),
 ('tx_timer_code','Actual4bittransmittimerencoding,requiresdevicecodec; notmilliseconds.',0,15,'encoded',True,PROTO),
 ('receive_timer_code','Actual4bitgroupreceivetimerencoding.',0,15,'encoded',True,PROTO),
 ('repeat_timer_code','Actual4bitUNACKD_RPTintervalencoding.',0,15,'encoded',True,PROTO),
 ('transmit_timer_ms','Actualqualifiedretransmittimer,resetonACK/challenge; no universal500ms.',0,None,'ms',False,PROTO),
 ('receive_timer_ms','Actualreceive-recordlifetime>=xmit*(retry+2)onlychosenrecommendation;NeuronID8secondsqualifiedcompiler.',0,None,'ms',False,PROGRAM),
 ('repeat_interval_ms','ActualUNACKD_RPTrepeatinterval,notCANretransmissiondelay.',0,None,'ms',False,PROTO),
 ('local_powered_nodes','ActualTPFTlocallypoweredcount.',0,None,None,True,GUIDE),
 ('link_powered_nodes','ActualTPFTlinkpoweredcount; needsactualPSU.',0,None,None,True,GUIDE),
 ('node_count','Actualphysicalsegmentpopulation,not127logicalsubnetasallPHYlimit.',1,None,None,True,GUIDE),
 ('total_wire_m','Actualsumwirelengthinsegment,notshortestpath.',0,None,'m',False,GUIDE),
 ('device_distance_m','Actuallongestdevice-device/device-PSUpathincludingloops.',0,None,'m',False,GUIDE),
 ('stub_m','Actualmaximumstub.',0,None,'m',False,GUIDE),
 ('mains_hz','ActualPowerlinemainsfrequencyandcouplingprofile.',0,None,'Hz',False,GUIDE),
 ('domain_octets','ActualdomainIDlength0/1/3/6,notIPv4addresssize.',0,6,'Byte',True,PROTO),
 ('source_subnet','Actualcommissionedsource1..255;0onlyexplicitunconfiguredstate.',0,255,None,True,PROTO),
 ('source_node','Actualassigned7bitlogicalsource1..127;0unconfiguredonly.',0,127,None,True,PROTO),
 ('destination_subnet','Actualunicastsubnet1..255/domainbroadcast0.',0,255,None,True,PROTO),
 ('destination_node','Actualunicastnode1..127.',1,127,None,True,PROTO),
 ('group','Actual8bitgroupidentity,notnodeindex.',0,255,None,True,PROTO),
 ('group_member','Actual6bitacknowledgedgroupmember.',0,63,None,True,PROTO),
 ('group_size','Actualgrouprecipients;acknowledgedgroup≤64,UNACKDcanlarger.',1,None,None,True,PROTO),
 ('domain_index','ActualNeuron2.2tableindex0/1,notarbitrarydomainidentity.',0,1,None,True,PROGRAM),
 ('domain_entries','ActualNeuron2.2oneortwodomainentries;conditionalcompilerproposal2.',1,2,None,True,PROGRAM),
 ('address_entries','Actualchipdependentaddress-tablecapacity;3100/5000≤15,6000≤254.',0,None,None,True,REFERENCE),
 ('transaction_number','Actual4bittransactionidentifier;reset0special,ordinarysequence1..15.',0,15,None,True,PROTO),
 ('nv_selector','Actual14bitnetworkvariableselector,notCANID.',0,16383,None,True,PROGRAM),
 ('message_code','Actualapplication/foreign/diagnostic/management/NV8bitcode.',0,255,None,True,PROGRAM),
 ('nv_octets','ActualNeuron2.2NVelement≤31octets,notCAN8.',0,31,'Byte',True,PROGRAM),
 ('app_data_octets','ActualNeuron2.2msg_outdata≤228 withactualappbuffer; not universalLonTalkpayloadlimit.',0,228,'Byte',True,PROGRAM),
 ('largest_encoded_message_octets','Actuallargestapplication/NV/response sizefornetbuffer22byteoverheadrequirement.',0,None,'Byte',True,GUIDE),
 ('network_input_buffer_octets','Actualnetworkinputbuffer;guidelinesminimum66.',1,None,'Byte',True,GUIDE),
 ('network_output_buffer_octets','Actualnetoutputbuffer≥42andlargestactualmessage+22.',1,None,'Byte',True,GUIDE),
 ('required_output_buffer_octets','Actualpacketrequiredoutputbuffer;ACKD/REQUESTmustnotrequire>66under3.4guideline.',1,None,'Byte',True,GUIDE),
 ('app_output_buffer_octets','ActualNeurondeclaredappbuffer;explicitaddressing adds17versus6dataoverhead.',1,None,'Byte',True,PROGRAM),
 ('input_buffer_count','Actualqualifiedcompiler/routerinputqueuecount;notgeneric256.',1,None,None,True,PROGRAM),
 ('output_buffer_count','Actualqualifiedcompiler/routeroutputqueuecount.',1,None,None,True,PROGRAM),
 ('priority_buffer_count','Actualprioritynetworkoutputqueuecount.',0,None,None,True,PROGRAM),
 ('router_other_memory_octets','Actual per-router-side application buffers and transaction-record memory, beyond the three network queues.',0,None,'Byte',True,ROUTER),
 ('router_allocated_memory_octets','Actual total per-router-side allocation including network queues, application buffers and transaction records; requires firmware-qualified capacity.',1,None,'Byte',True,ROUTER),
 ('router_available_memory_octets','Firmware-qualified RTR10 total record/buffer memory:1500 A/C versus1408 B; not the old generic1254-byte network-buffer statement.',1,None,'Byte',True,ROUTER),
 ('nonconfig_input_nv_count','ActualinputNVcountforreceive-transactionminformula.',0,None,None,True,GUIDE),
 ('receive_transaction_count','Actualsimultaneousrecords,uniqueaddress+priority vector;notqueue_size.',1,None,None,True,GUIDE),
 ('l2_header_octets','ActualLonTalk3L2priority/altpath/backlogheaderonebyte.',1,1,'Byte',True,PROTO),
 ('npdu_header_octets','Actualversion/PDU/address/domainlengthheaderonebyte.',1,1,'Byte',True,PROTO),
 ('address_octets','Actualaddress-formatdependent3/4/6/9bytes.',0,None,'Byte',True,PROTO),
 ('enclosed_pdu_octets','ActualcompleteTPDU/SPDU/APDU/AuthPDUwithcode/data/header,notjustapplicationdata.',0,None,'Byte',True,PROTO),
 ('lpdu_octets','ActualL2hdr+NPDUhdr+address+domain+enclosedPDU+CRC; excludesmediumsync.',0,None,'Byte',True,PROTO),
 ('crc_octets','ActualLonTalk3CRC16twooctets.',2,2,'Byte',True,PROTO),
 ('crc_polynomial','ActualLonTalk3CCITT x16+x12+x5+1lower16bits0x1021;utilityCRCnotwireproof.',4129,4129,None,True,PROTO),
 ('key_octets','Actuallegacy6bytekey;noimpliedmodernsecurity.',1,None,'Byte',True,PROGRAM),
 ('challenge_octets','Actuallegacy64bitnonce8octets;notfixednoncevalue.',1,None,'Byte',True,PROGRAM),
 ('ip_normal_port','ActualIP852UDPnormalport;1628recommendednotmandatory.',1,65535,None,True,GUIDE),
 ('ip_urgent_port','ActualIP852urgentport;1629optionalrecommended.',1,65535,None,True,GUIDE),
 ('functional_bound_ms','ActualapplicationfunctionalE2Econstraint separatefromnetworkdelivery.',0,None,'ms',False,GUIDE),
 ('standard_xcvr_id','ActualStdXcvrstd_id,notnecessarilywireXID/channeltypenumber.',0,None,'encoded',True,XCVR),
 ('minimum_clock_id','ActualrawStdXcvrclockID,notMHzconversionbyguess.',0,None,'encoded',True,XCVR),
 ('comm_mode_code','ActualrawStdXcvrcomm_mode0/1/2.',0,2,'encoded',True,XCVR)]:d(key,'number',meaning,lo=lo,hi=hi,unit=unit,integer=integer,source=source)
for key in RAW_TIMINGS:d('raw_'+key,'number','Actualsource-qualifiedStdXcvr '+key+' encodedsetting; not automatically microseconds or measuredPHYbound.',lo=0,integer=True,unit='encoded',source=XCVR)
for key,meaning,unit in [
 ('temperature_min_c','Actuallowestambienttemperatureinqualifiedloadenvelope.','C'),
 ('temperature_max_c','Actualhighestambienttemperatureinqualifiedloadenvelope.','C'),
 ('ambient_c','Actual20Ctypicalbenchmark condition,not defaultambientmeasurement.','C'),
 ('supply_v','Actualmodule5Vtypicalbenchmark condition,notdefaultmeasuredsupply.','V'),
 ('stub_capacitance_pf_m','ActualstubmutualcapacitanceusedwithqualifiedTPXFstublimits.','pF/m'),
 ('nodes_per_16m','ActualTPXF1250distributionmaximum8per16m.','nodes'),
 ('carrier_khz','Actualpowerlinecarrierfrequencyinsidequalifiedband;notautomatically125kHz.','kHz'),
 ('qualified_band_low_khz','Selectedsource-definedlowerbandedge,notactualcarriermeasurement.','kHz'),
 ('qualified_band_high_khz','Selectedsource-definedupperbandedge,notactualcarriermeasurement.','kHz')]:d(key,'number',meaning,unit=unit,integer=key=='nodes_per_16m')
for key,meaning in [('priority_on','Actualmessageselection; no default highpriority.'),('authenticated','Actualrequested authentication,notpassedchallenge orencryptedpayload.'),
 ('explicit_addressing','Actualprogramusesexplicitaddressing;differentapplicationbufferoverhead.'),('receives_application_frames','Actualapp/foreignframesreceived;affectsreceive-transactionminimum.'),
 ('link_power_present','ActualinstalledPSU,notinferredfromnodecount.'),('ip_udp_supported','ActualIP852implementationmustsupportUDP;TCPcannotreplaceit.'),
 ('router_forwarding','Actualrouterforwardingdisabledwhileoffline.'),('capacity_confirmed','Actualcompletecapacityrelease,nevergeneratedTruefromcatalog.'),
 ('channel_parameters_match','Actualallnodeschannel/preamble/beta/prioritiescompatible;notdefaultTrue.'),
 ('even_distribution','Actual64nodes evenlydistributed under the exacttypicalbenchmark.'),
 ('explicit_messages_sent','ActualNeuronprogramsendsapplicationmessages;changescompilerbufferdefault.')]:d(key,'boolean',meaning)
REMOVED={key:'Removed foreign '+key+': LonTalk predictiveCSMA/priorityslots/transactionservices andsource-qualifiedbuffers replace CAN/Ethernet genericconfiguration.'for key in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['protocol','channel_profile','channel','role','revision','device_source','transceiver_source','binding_source','physical_source',
 'commissioning_source','encoding_source','schedule_source','capacity_source','acceptance_source']


def semantics():
    rules=[dict(parameter='local_timing_evidence',allowed=[],source=CURRENT,source_revision='LonTalk is not an I2C master/slave transaction')]
    def r(key,when=None,source=GUIDE,**kw):rules.append(dict(parameter='lw_'+key,when={'lw_'+k:v for k,v in(when or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    old={'protocol':OLD}
    for key,value in [('protocol','REGISTERED_PROTOCOL'),('channel_profile','REGISTERED_PROFILE'),('channel','REGISTERED_CHANNEL'),
                      ('payload_kind','REGISTERED_PAYLOAD'),('comm_port_mode','REGISTERED_MODE'),('cable_profile','REGISTERED_CABLE'),
                      ('authentication_profile','REGISTERED_SECURITY'),('buffer_profile','REGISTERED_BUFFERS'),
                      ('router_firmware','REGISTERED_FIRMWARE'),
                      ('temperature_profile','REGISTERED_ENVIRONMENT'),('wiring_case','REGISTERED_WIRING'),
                      ('modulation','REGISTERED_MODULATION')]:r('registered_source',{key:value},required=True,source=CURRENT)
    for channel,(rate,slots,clock,mode) in GUIDELINE_CHANNELS.items():
        w={'channel_profile':G,'channel':channel}
        r('medium_nominal_bps',w,allowed=[rate]);r('channel_min_clock_mhz',w,minimum=clock);r('device_clock_mhz',w,minimum=clock)
        r('comm_port_mode',w,allowed=[mode]);r('oscillator_error_ppm',w,maximum=200)
    for channel,row in STANDARD_TRANSCEIVERS.items():
        ident,rate,slots,clock,mode,timings=row;w={'channel_profile':X,'channel':channel}
        for key,value in [('standard_xcvr_id',ident),('network_bitrate_bps',rate),('comm_mode_code',mode)]:r(key,w,allowed=[value],source=XCVR)
        r('minimum_clock_id',w,minimum=clock,source=XCVR)
        r('priority_slots',w,maximum=slots,source=XCVR)
        r('oscillator_error_ppm',w,maximum=200,source=XCVR)
        for key,value in zip(RAW_TIMINGS,timings):r('raw_'+key,w,allowed=[value],source=XCVR)
    for channel in ('PL_20C','PL_20N'):
        w={'channel_profile':R,'channel':channel}
        r('network_bitrate_bps',w,allowed=[3987],source=ROUTER);r('neuron_interface_bps',w,allowed=[156250],source=ROUTER)
        r('router_source',w,required=True,source=ROUTER)
    for channel in ('PL_10_DEPRECATED','PL_30_DEPRECATED'):r('registered_source',{'channel':channel},required=True)
    r('device_clock_mhz',minimum_parameter='lw_channel_min_clock_mhz')
    r('device_priority_slot',old,maximum_parameter='lw_priority_slots',source=PROTO)
    r('device_priority_slot',{'role':'APPLICATION'},forbidden=[1])
    r('beta2_us',old,exclusive_minimum_expression={'sum':[{'product':[2,'lw_propagation_us']},'lw_mac_turnaround_us']},source=PROTO)
    for mode in ('SINGLE_ENDED','DIFFERENTIAL'):
        r('beta1_us',{**old,'comm_port_mode':mode},exclusive_minimum_expression={'sum':[
            {'product':[1000000,{'power':['lw_network_bitrate_bps',-1]}]},
            {'product':[2,'lw_propagation_us']},'lw_mac_turnaround_us']},source=PROTO)
    ft={'channel_profile':G,'channel':'TP_FT_10'}
    r('link_powered_nodes',ft,maximum_expression={'subtract':[128,{'product':[2,'lw_local_powered_nodes']}]})
    r('local_powered_nodes',ft,maximum=64);r('link_powered_nodes',ft,maximum=128)
    r('node_count',ft,equal_expression={'sum':['lw_local_powered_nodes','lw_link_powered_nodes']})
    r('link_power_present',ft,when_positive=['lw_link_powered_nodes'],allowed=[True]);r('power_source',ft,when_positive=['lw_link_powered_nodes'],required=True)
    for topology,length in [('DOUBLE_TERMINATED_BUS',900),('SINGLE_TERMINATED_FREE',450)]:
        w={**ft,'cable_profile':'CAT5_24AWG_568A','topology':topology};r('total_wire_m',w,maximum=length)
        if topology=='DOUBLE_TERMINATED_BUS':r('stub_m',w,maximum=3)
        else:r('device_distance_m',w,maximum=250)
    for channel,worst,typical,stub in [('TP_XF_78',1330,2000,3),('TP_XF_1250',130,500,.3)]:
        c={'channel_profile':G,'channel':channel,'cable_profile':'UL_LEVEL_IV_22AWG'}
        r('total_wire_m',{**c,'wiring_case':'WORST_CASE'},maximum=worst)
        w={**c,'wiring_case':'TYPICAL_ROOM_5V_64_EVEN'};r('total_wire_m',w,maximum=typical)
        for key,value in [('ambient_c',20),('supply_v',5),('node_count',64),('even_distribution',True)]:r(key,w,allowed=[value],required=True)
        r('stub_m',c,maximum=stub);r('stub_capacitance_pf_m',c,maximum=56)
        if channel=='TP_XF_1250':r('nodes_per_16m',c,maximum=8)
    for channel,profile,count,tlo,thi in [('TP_XF_78','RANGE_0_70',64,0,70),('TP_XF_78','XF78_MINUS40_85',44,-40,85),
        ('TP_XF_1250','RANGE_0_70',64,0,70),('TP_XF_1250','XF1250_MINUS20_85',32,-20,85),('TP_XF_1250','XF1250_MINUS40_70',20,-40,70)]:
        w={'channel_profile':G,'channel':channel,'temperature_profile':profile}
        r('node_count',w,maximum=count);r('temperature_min_c',w,minimum=tlo);r('temperature_max_c',w,maximum=thi)
    r('temperature_min_c',maximum_parameter='lw_temperature_max_c')
    c={'channel_profile':G,'channel':'TP_RS485_39','cable_profile':'UL_LEVEL_IV_22AWG'}
    r('node_count',c,maximum=32);r('total_wire_m',c,maximum=1200);r('stub_m',c,allowed=[0])
    for channel,count,distance,beta in [('FO_20S',64,25,132),('FO_20L',512,25,1056)]:
        w={'channel_profile':G,'channel':channel};r('node_count',w,maximum=count)
        c={**w,'cable_profile':'FIBER_62_5_125_492AAAA_A'};r('device_distance_m',c,maximum=distance);r('stub_m',c,maximum=3)
        t={**w,'device_clock_mhz':10};r('reference_preamble_us',t,minimum=221.4,maximum=229.8)
        r('reference_packet_cycle_us',t,allowed=[4020]);r('reference_beta2_us',t,allowed=[beta])
    r('mains_hz',{'channel_profile':G,'channel':'PL_20A_LN'},allowed=[50])
    for channel in ('PL_20_LN','PL_20_LE'):r('mains_hz',{'channel_profile':G,'channel':channel},allowed=[50,60])
    for channel,lo,hi,coupling in [('PL_20_LN',125,140,'LINE_NEUTRAL'),('PL_20_LE',125,140,'LINE_EARTH'),('PL_20A_LN',70,95,'LINE_NEUTRAL')]:
        w={'channel_profile':G,'channel':channel};r('carrier_khz',w,minimum=lo,maximum=hi)
        r('qualified_band_low_khz',w,allowed=[lo]);r('qualified_band_high_khz',w,allowed=[hi]);r('pl_coupling',w,allowed=[coupling]);r('modulation',w,allowed=['BPSK'])
    for key in ('ip_normal_port','ip_urgent_port','ip_udp_supported'):r(key,when_not={'lw_channel':'IP_852'},allowed=[])
    r('ip_udp_supported',{'channel':'IP_852'},allowed=[True],required=True)
    r('binding_source',{'channel':'IP_852'},required=True)
    for key in ('network_bitrate_bps','medium_nominal_bps','neuron_interface_bps'):r(key,{'channel':'IP_852'},allowed=[])
    r('domain_octets',old,allowed=[0,1,3,6],source=PROTO)
    r('domain_id',{**old,'domain_octets':0},allowed=[''],text_encoding='ascii',source=PROTO)
    for size in (1,3,6):r('domain_id',{**old,'domain_octets':size},pattern='[0-9a-fA-F]{'+str(2*size)+'}',required=True,source=PROTO)
    r('neuron_id',old,pattern='[0-9a-fA-F]{12}',source=PROTO)
    for state in ('ONLINE','OFFLINE'):
        for key in ('source_subnet','source_node'):r(key,{**old,'node_state':state},minimum=1,source=PROTO)
    for kind in ('SUBNET_NODE','GROUP_ACK','NEURON_ID'):r('destination_subnet',{**old,'address_format':kind},minimum=1,source=PROTO)
    for service in ('ACKD','REQUEST'):r('group_size',{**old,'service':service,'address_format':'GROUP'},maximum=64,source=PROTO)
    r('group_member',old,maximum_expression={'subtract':['lw_group_size',1]},source=PROTO)
    for kind,octets in [('BROADCAST',3),('GROUP',3),('SUBNET_NODE',4),('GROUP_ACK',6),('NEURON_ID',9)]:r('address_octets',{**old,'address_format':kind},allowed=[octets],source=PROTO)
    r('lpdu_octets',old,equal_expression={'sum':[1,1,'lw_address_octets','lw_domain_octets','lw_enclosed_pdu_octets',2]},source=PROTO)
    for service in ('UNACKD','UNACKD_RPT'):r('authenticated',{'service':service},allowed=[False],source=PROGRAM)
    for key in ('security_source','key_ref'):r(key,{'authenticated':True},required=True,source=PROGRAM)
    r('authentication_profile',{'authenticated':True},required=True,source=PROGRAM)
    r('key_octets',{'authentication_profile':'LEGACY_48_BIT'},allowed=[6],source=PROGRAM)
    r('challenge_octets',{'authentication_profile':'LEGACY_48_BIT'},allowed=[8],source=PROGRAM)
    for key in ('key_ref','key_octets','challenge_octets'):r(key,{'authenticated':False},allowed=[],source=PROGRAM)
    w={**old,'timer_policy':'LONTALK3_SINGLE_CHANNEL_RECOMMENDATION'}
    r('retry_count',w,minimum=2,maximum=5,source=PROTO)
    r('transmit_timer_ms',w,minimum_expression={'product':[.001,{'sum':[{'product':[3,'lw_packet_cycle_bound_us']},'lw_tx_completion_margin_us']}]},source=PROTO)
    r('receive_timer_ms',w,minimum_expression={'product':['lw_transmit_timer_ms',{'sum':['lw_retry_count',2]}]},source=PROTO)
    r('receive_timer_ms',{'buffer_profile':'NEURON_C_2_2','address_format':'NEURON_ID'},allowed=[8000],source=PROGRAM)
    for key in ('tx_timer_code','receive_timer_code','repeat_timer_code','transmit_timer_ms','receive_timer_ms','repeat_interval_ms'):
        r('timer_source',when_present=['lw_'+key],required=True,source=PROTO)
    neuron={'buffer_profile':'NEURON_C_2_2'}
    sizes=[20,21,22,24,26,30,34,42,50,66,82,114,146,210,255]
    counts=[1,2,3,5,7,11,15,23,31,47,63,95,127,191]
    for key in ('network_input_buffer_octets','network_output_buffer_octets','app_output_buffer_octets'):r(key,neuron,allowed=sizes,source=PROGRAM)
    for key in ('input_buffer_count','output_buffer_count'):r(key,neuron,allowed=counts,source=PROGRAM)
    r('priority_buffer_count',neuron,allowed=[0,*counts],source=PROGRAM);r('receive_transaction_count',neuron,maximum=16,source=PROGRAM)
    r('network_input_buffer_octets',{'channel_profile':G},minimum=66)
    r('network_output_buffer_octets',{'channel_profile':G},minimum_expression={'maximum':[42,{'sum':['lw_largest_encoded_message_octets',22]}]})
    r('required_output_buffer_octets',maximum_parameter='lw_network_output_buffer_octets')
    r('priority_buffer_count',{'channel_profile':G,'priority_on':True},minimum=1,required=True)
    for service in ('ACKD','REQUEST'):r('required_output_buffer_octets',{'channel_profile':G,'service':service},maximum=66)
    for explicit,overhead in [(False,6),(True,17)]:r('app_data_octets',{**neuron,'explicit_addressing':explicit},maximum_expression={'subtract':['lw_app_output_buffer_octets',overhead]},source=PROGRAM)
    for key,lo,hi in [('APPLICATION_MESSAGE',0,62),('FOREIGN_FRAME',64,78),('NETWORK_DIAGNOSTIC',80,95),('NETWORK_MANAGEMENT',96,127),('NETWORK_VARIABLE',128,255)]:
        r('message_code',{**neuron,'payload_kind':key},minimum=lo,maximum=hi,source=PROGRAM)
    for kind,code in [('RESPONDER_OFFLINE',63),('FOREIGN_RESPONDER_OFFLINE',79)]:r('message_code',{**neuron,'payload_kind':kind},allowed=[code],source=PROGRAM)
    for chip,max_entries in [('3120',15),('3100',15),('5000',15),('6000',254)]:r('address_entries',{'chip_series':chip},maximum=max_entries,source=REFERENCE)
    for profile in ('RTR10_01H','RTR3150_01H'):r('network_input_buffer_octets',{'buffer_profile':profile},minimum=66,source=ROUTER)
    router={'buffer_profile':'RTR10_01H'}
    for key in ('router_firmware','router_source','network_input_buffer_octets','network_output_buffer_octets',
                'input_buffer_count','output_buffer_count','priority_buffer_count','router_other_memory_octets',
                'router_allocated_memory_octets','router_available_memory_octets'):
        r(key,router,required=True,source=ROUTER)
    for firmware,memory in [('A',1500),('B',1408),('C',1500)]:
        r('router_available_memory_octets',{**router,'router_firmware':firmware},allowed=[memory],source=ROUTER)
    for key in ('network_input_buffer_octets','network_output_buffer_octets'):r(key,router,allowed=sizes,source=ROUTER)
    for key in ('input_buffer_count','output_buffer_count','priority_buffer_count'):
        r(key,router,allowed=counts[:11],source=ROUTER)
    r('router_allocated_memory_octets',router,equal_expression={'sum':[
        {'product':['lw_network_input_buffer_octets','lw_input_buffer_count']},
        {'product':['lw_network_output_buffer_octets',{'sum':['lw_output_buffer_count','lw_priority_buffer_count']}]},
        'lw_router_other_memory_octets']},maximum_parameter='lw_router_available_memory_octets',source=ROUTER)
    # At least min(16,N+2), and at least8 if application/foreign messages arrive.
    # Express min through disjoint ranges, avoiding an unsupported expression op.
    for present in (False,True):
        w={'channel_profile':G,'receives_application_frames':present}
        r('receive_transaction_count',w,when_half_open_ranges={'lw_nonconfig_input_nv_count':[0,14]},
          minimum_expression={'maximum':([8]if present else[0])+[{'sum':['lw_nonconfig_input_nv_count',2]}]})
        r('receive_transaction_count',w,when_ranges={'lw_nonconfig_input_nv_count':[14,65535]},minimum=16)
        r('receive_transaction_count',w,when_greater_than={'lw_nonconfig_input_nv_count':65535},minimum=16)
    r('router_forwarding',{'role':'ROUTER','node_state':'OFFLINE'},allowed=[False],source=ROUTER)
    return dict(rate_model={'type':'EXPLICIT_LON_CHANNEL_AND_DEVICE','fields':[]},required_parameters=['lw_'+k for k in REQUIRED],
        native_parameter_prefixes=['lw_'],parameter_constraints=rules,mechanisms={
        'integrity':['CCITT_CRC16_WITH_ACTUAL_CODEC'], 'arbitration':['PREDICTIVE_P_PERSISTENT_CSMA','CHANNEL_PRIORITY_SLOTS'],
        'addressing':['DOMAIN_SUBNET_NODE','GROUP_MEMBERS','FACTORY_NEURON_ID'],
        'services':['ACKD','REQUEST','UNACKD','UNACKD_RPT'],
        'security':['EXPLICIT_LEGACY_CHALLENGE_OR_REGISTERED_SECURITY'],
        'supervision':['DELIVERY_ACK_NOT_FUNCTIONAL_COMPLETION']})


def fields():
    result=[];required=set(semantics()['required_parameters'])
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('lw_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        if spec['source']==PROTO and key not in {'commissioning_source','encoding_source','timer_source'}:
            item['schema_when']={'lw_protocol':OLD}
        if key.startswith('raw_') or key in {'standard_xcvr_id','minimum_clock_id','comm_mode_code'}:
            item['schema_when']={'lw_channel_profile':X}
        if key in {'nv_octets','app_data_octets','domain_entries','domain_index','app_output_buffer_octets'}:
            item['schema_when']={'lw_buffer_profile':'NEURON_C_2_2'}
        if key in {'router_firmware','router_other_memory_octets','router_allocated_memory_octets','router_available_memory_octets'}:
            item['schema_when']={'lw_buffer_profile':'RTR10_01H'}
        if key in {'reference_preamble_us','reference_packet_cycle_us','reference_beta2_us'}:
            item['schema_when']={'lw_channel_profile':G,'lw_channel':['FO_20S','FO_20L'],'lw_device_clock_mhz':10}
        proposals=[]
        def p(value,source=GUIDE,**when):proposals.append(dict(when={'lw_'+k:v for k,v in when.items()},value=value,source=source,source_revision=SOURCES[source]))
        for channel,(rate,slots,clock,mode) in GUIDELINE_CHANNELS.items():
            choices={'medium_nominal_bps':rate,'priority_slots':slots,'channel_min_clock_mhz':clock,'comm_port_mode':mode,'avg_packet_estimate_octets':15}
            if key in choices:p(choices[key],channel_profile=G,channel=channel)
        for channel,row in STANDARD_TRANSCEIVERS.items():
            ident,rate,slots,clock,mode,timings=row
            choices={'standard_xcvr_id':ident,'network_bitrate_bps':rate,'priority_slots':slots,'minimum_clock_id':clock,
                     'comm_mode_code':mode,'avg_packet_estimate_octets':15,**{'raw_'+k:v for k,v in zip(RAW_TIMINGS,timings)}}
            if key in choices:p(choices[key],source=XCVR,channel_profile=X,channel=channel)
        if key in ('network_bitrate_bps','neuron_interface_bps'):
            for channel in ('PL_20C','PL_20N'):p(3987 if key=='network_bitrate_bps' else 156250,source=ROUTER,channel_profile=R,channel=channel)
        if key in ('ip_normal_port','ip_urgent_port'):p(1628 if key=='ip_normal_port' else 1629,channel_profile=G,channel='IP_852')
        if key=='random_window_base':p(16,source=PROTO,protocol=OLD)
        if key=='retry_count':p(2,source=PROTO,protocol=OLD,timer_policy='LONTALK3_SINGLE_CHANNEL_RECOMMENDATION')
        if key in ('l2_header_octets','npdu_header_octets','crc_octets','crc_polynomial'):p({'l2_header_octets':1,'npdu_header_octets':1,'crc_octets':2,'crc_polynomial':4129}[key],source=PROTO,protocol=OLD)
        if key=='domain_entries':p(2,source=PROGRAM,buffer_profile='NEURON_C_2_2')
        if key=='network_input_buffer_octets':p(66,channel_profile=G)
        if key in ('service','app_output_buffer_octets'):
            if key=='service':p('ACKD',source=PROGRAM,buffer_profile='NEURON_C_2_2',payload_kind='APPLICATION_MESSAGE')
            else:
                for explicit,size in [(False,50),(True,66)]:p(size,source=PROGRAM,buffer_profile='NEURON_C_2_2',explicit_messages_sent=True,explicit_addressing=explicit)
        if key in ('input_buffer_count','output_buffer_count'):
            if key=='input_buffer_count':p(2,source=PROGRAM,buffer_profile='NEURON_C_2_2')
            else:
                for chip,count in [('3120',1),('3100',2),('5000',2)]:p(count,source=PROGRAM,buffer_profile='NEURON_C_2_2',chip_series=chip)
        for firmware,available,input_count,output_count,priority_count in [('A',1500,2,15,2),('B',1408,3,11,3),('C',1500,2,15,2)]:
            choices={'router_available_memory_octets':available,'network_input_buffer_octets':66,'network_output_buffer_octets':66,
                     'input_buffer_count':input_count,'output_buffer_count':output_count,'priority_buffer_count':priority_count}
            if key in choices:p(choices[key],source=ROUTER,buffer_profile='RTR10_01H',router_firmware=firmware)
        for channel,lo,hi,coupling in [('PL_20_LN',125,140,'LINE_NEUTRAL'),('PL_20_LE',125,140,'LINE_EARTH'),('PL_20A_LN',70,95,'LINE_NEUTRAL')]:
            values={'qualified_band_low_khz':lo,'qualified_band_high_khz':hi,'pl_coupling':coupling,'modulation':'BPSK'}
            if key in values:p(values[key],channel_profile=G,channel=channel)
        if key=='avg_packet_estimate_octets':item['description']+=' This is an estimator input, not a measured frame.'
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
