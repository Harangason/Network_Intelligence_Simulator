"""LIN edition, LDF schedule, frame class and actual physical bus are explicit."""
SPEC='https://www.lin-cia.org/fileadmin/microsites/lin-cia.org/resources/documents/LIN_2.2A.pdf'
CURRENT='https://www.lin-cia.org/standards/'
MICROCHIP='https://developerhelp.microchip.com/xwiki/bin/view/applications/lin/data-link-layer/'
SOURCES={SPEC:'LIN Consortium2.2A,2010-12-31 primary194pagepackage; reviewed declared protocol/schedule/networkmanagement/transport/PHY/NCF/LDF parameter sections; not fullcurrentISO2025conformance',
 CURRENT:'CiA standards accessed2026-10-02; ISO17987 parts1/2/3/4/6/7 updated2025 and separateDC-LIN part8;2010constants do not qualify currentregisteredPHY/profile',
 MICROCHIP:'Microchip developer data-link overview2023-11-10; checked against Consortium2.2A; overview typo normalidentifier0-50 notused(normative0-59), legacy2/4/8lengthclasses notcopiedinto2.2A'}
OLD='LIN_2_2A_2010'
DECLARATIONS=[]


def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,integer=False,source=SPEC):
    DECLARATIONS.append(dict(key='lin_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,options=options,
        integer=integer,source=source,source_revision=SOURCES[source]))


for key,meaning,options in [
 ('edition','Actual selected2.2A versus currentISO/SAE or registerededition; not silently oldLIN fornew24V/DC-LIN. ',[OLD,'ISO_17987_REGISTERED','SAE_J2602_REGISTERED','REGISTERED_EDITION']),
 ('physical_profile','Actual LIN2.2A8..18V singlewirephysical layer versus independently registered24V/DC-LIN/otherPHY.',['LIN_2_2A_SINGLE_WIRE','REGISTERED_PHY']),
 ('node_role','Actual commander/mastertask versus responder/slavetask,notonegenericCANnode.',['COMMANDER','RESPONDER']),
 ('frame_kind','Actual scheduledunconditional/eventtriggered/sporadic versus diagnosticrequest/response/sleep/wake.',['UNCONDITIONAL','EVENT_TRIGGERED','SPORADIC','DIAGNOSTIC_REQUEST','DIAGNOSTIC_RESPONSE','GO_TO_SLEEP','WAKE_UP','REGISTERED_FRAME']),
 ('publisher_role','Actual responsepublisher; commanderalsocontainsresponderslavetask.',['COMMANDER','RESPONDER','EVENT_CANDIDATES']),
 ('checksum_model','Actual perframe classicdata-only versus enhancedPID+data,end-aroundcarry notCRC16.',['CLASSIC','ENHANCED']),
 ('responder_version','Actualselectedresponsepublisher1.x versus2.x compatiblechecksum.',['LIN_1_X','LIN_2_X','REGISTERED_VERSION']),
 ('state','Actual initialization/operational/sleep; ordinary frames onlywhileoperational.',['INITIALIZING','OPERATIONAL','BUS_SLEEP']),
 ('sync_mode','Actual calibratedresponder versus sync-measured clock; different tolerances.',['NO_SYNC','SYNC_MEASURED']),
 ('diag_class','ActualNCFdiagnosticclassI/II/III,notUDSoverCANcapabilities.',['I','II','III']),
 ('pdu_type','ActualdiagnosticSingle/First/ConsecutivePDU,noLINflowcontrolPDU.',['SF','FF','CF']),
 ('nad_kind','ActualphysicalNAD1..125/function126/broadcast127/user128..255; zeroonlysleepcommand.',['PHYSICAL','FUNCTIONAL','BROADCAST','USER_DEFINED']),
 ('data_order','Actualwirebits andmulti-byteapplicationquantitieslittle-endian.',['LSB_FIRST']),
 ('uart_parity','ActualLINbytefield8N1;PIDparityseparatefromUARTparity.',['NONE']),
 ('supply_role','Actualphysicalpull-up commander1kohm versus responder30kohm typical.',['COMMANDER','RESPONDER'])]:d(key,'select',meaning,options=options)

for key,meaning,source in [
 ('revision','Actualcompleteprotocol/physical/transport/diagnosticrevision andcompatibledevices.',CURRENT),
 ('registered_source','ActualregisteredISO2025/J2602/DC-LIN/alternateframe/PHYschemasourceandimplementation.',CURRENT),
 ('device_source','Actualtransceiver/MCU/firmware,clockandsupportedframe/diagcapabilities.',SPEC),
 ('binding_source','ActualcanonicalLINchannel,exactcommanderandresponders,independentlyqualifiedgatewayotherbus.',SPEC),
 ('physical_source','Actualwiring/pull-up/diodes/voltage/load/capacitance/groundshift/slew/clockevidence.',SPEC),
 ('ldf_source','ActualprojectLDFrevision/nominalspeed/framepublishers/IDs/signals/schedules,not19.2kbpsexample.',SPEC),
 ('ncf_source','ActualnodeNCF/diagnosticcapability/initialNAD/timing/message-buffer/supportedSIDs.',SPEC),
 ('encoding_source','ActualPID/data/checksum/reservedones/signalatomicity/LINPDUwirecodec.',SPEC),
 ('schedule_source','Actualtimebase/jitter/slots/modechanges/eventcollisionresolution/alltrafficanddiagnostics.',SPEC),
 ('capacity_source','ActualwholeLINsharedschedule/PHY/wake/diagnostic/gatewaycapacityproof.',SPEC),
 ('acceptance_source','ActualfunctionalE2E/freshness/safety,independentofsuccessf ul_transfer/response_error.',SPEC),
 ('commander_node_id','Actualassignedsinglecommanderidentity,notguessedECUreference.',SPEC),
 ('publisher_node_id','Actualdesignatedsinglepublisherofunconditionalframe,notnumericdefaultaddress.',SPEC),
 ('collision_schedule_source','Actualeventassociatedunconditionalframesandmandatorycollisionresolutionschedule.',SPEC),
 ('signal_source','Actualsignalbitpositions/lengths/publisher/initialvalues/unusedones,noinventedactuatorencoding.',SPEC),
 ('diag_source','Actualdiagnosticmessage/schedule/SID/RSID/NAD/segmentation/timers,notCANFCframes.',SPEC),
 ('checksum_source','Actualencodedbytearray/PID/end-aroundcarrychecksumtestproof.',SPEC)]:d(key,'text',meaning,source=source)

for key,meaning,lo,hi,unit,integer in [
 ('bitrate_bps','ActualprojectLDFnominal1..20kbit/s for reviewedPHY; no universal19.2kbpsdefault.',1,None,'bit/s',True),
 ('commander_count','ActualsinglecommandertaskononeLINcluster.',1,1,None,True),
 ('node_count','Actualtotalphysicalnodes;2010 recommendationmax16includingcommander,not16respondersplus1.',1,None,None,True),
 ('frame_id','Actual6bitrawidentifier0..63,diagnostic60/61,reserved62/63forbiddenin2.x.',0,63,None,True),
 ('pid','Actual8bitprotectedidentifierwithP0/P1,notrawID copiedasPID.',0,255,None,True),
 ('data_octets','Actualperframeagreedresponse1..8octets;diagnosticfixed8,notlegacyIDlengthclass.',1,8,'Byte',True),
 ('start_bits','Actualonezero-dominantstartbitperbytefield.',1,1,'bit',True),
 ('data_bits','Actual8databitsperbytefield.',8,8,'bit',True),
 ('stop_bits','Actualonerecessivestopbitperbytefield.',1,1,'bit',True),
 ('byte_bits','Actual10bitsperbytefield,notKNX13bitsorCANframebits.',10,10,'bit',True),
 ('break_bits','Actualcommanderbreakdominantatleast13nominalbits.',0,None,'bit',False),
 ('delimiter_bits','Actualcommanderrecessivedelimiteratleast1nominalbit;UARTroundingnotignored.',0,None,'bit',False),
 ('sync_byte','Actualsync0x55,notdatapayloadvalue.',85,85,None,True),
 ('header_nominal_bits','Nominalreference34bits13break+1delimiter+sync/PID20,notactualpaddedheader.',34,34,'bit',True),
 ('response_nominal_bits','Nominalreference10*(data_octets+1checksum).',0,None,'bit',True),
 ('frame_nominal_bits','Nominalreferenceheader34+responsebits,excludingoptionalspace.',0,None,'bit',True),
 ('header_actual_ms','Actualmeasuredheaderduration,limitedby1.4*nominalunder2.2A.',0,None,'ms',False),
 ('response_actual_ms','Actualmeasuredresponseincludingresponsespace/interbytegaps,limitedby1.4*nominal.',0,None,'ms',False),
 ('frame_max_ms','Derived2.2Aupperbound1.4*(34+10*(N+1))/rate,notmeasuredE2E.',0,None,'ms',False),
 ('response_space_ms','ActualnonnegativePID-firstdataresponsegap,notdefault0guarantee.',0,None,'ms',False),
 ('inter_byte_ms','Actualnonnegativeinter-bytegapwithinwhole1.4 timingbound.',0,None,'ms',False),
 ('time_base_ms','Actualcommanderschedulertimebase,usual5/10msproposalfromnormativetext.',0,None,'ms',False),
 ('slot_ticks','Actualpositivetimebaseintegermultipleperslot.',1,None,None,True),
 ('slot_ms','Actualslot=Tbase*ticks,strictlygreaterthanactualjitter+TFrameMax.',0,None,'ms',False),
 ('jitter_ms','Actualmaximum-minus-minimumheaderstartdelay,notassumedzero.',0,None,'ms',False),
 ('commander_clock_error_percent','Actualmagnitudenominalcommanderclockerrorstrictly<0.5percent.',0,None,'%',False),
 ('unsynced_clock_error_percent','Actualresponderclockerrorbeforesyncstrictly<14percent.',0,None,'%',False),
 ('synced_clock_error_percent','Actualresponder-relativecommandererroraftersyncstrictly<2percent.',0,None,'%',False),
 ('no_sync_clock_error_percent','Actualcalibratedrespondernominalerrorstrictly<1.5percent.',0,None,'%',False),
 ('peer_clock_difference_percent','Actualdifferencebetweenresponderclocksstrictly<2percent;notonechipaccuracyalone.',0,None,'%',False),
 ('pullup_ohm','Actualqualifiedsinglewirepull-up commander900..1100/responder20000..60000ohm.',0,None,'ohm',False),
 ('supply_v','Actuallocalconnectorvoltage;2010guaranteedcommunication8..18V,notnewISO24V.',0,None,'V',False),
 ('bus_capacitance_nf','Actualaggregatemaster+allresponders+cablecapacitance1..10nF.',0,None,'nF',False),
 ('rc_time_us','ActualoverallRCtimeconstant1..5us,notCAN120ohmtermination.',0,None,'us',False),
 ('bus_length_m','Actual2010singlewirebuslengthatmost40m.',0,None,'m',False),
 ('wake_pulse_us','Actualgeneratedwakedominantpulse250..5000us.',0,None,'us',False),
 ('wake_detect_us','Actualreceivewakedominantpulselongerthan150us.',0,None,'us',False),
 ('responder_ready_ms','Actualresponderinitializationwithin100msafterwakeend.',0,None,'ms',False),
 ('wake_retry_ms','Actualretrywindow150..250mswithoutheader/otherwake.',0,None,'ms',False),
 ('wake_block_attempts','Actual3failedwakerequestsperblockbeforeretrypause.',1,None,None,True),
 ('wake_block_pause_ms','Actualatleast1500msafter3failedrequests;notwholeE2Etimeout.',0,None,'ms',False),
 ('sleep_idle_ms','Actualautomaticbusinactivitysleepbetween4000..10000ms.',0,None,'ms',False),
 ('diag_nad','ActualdiagnosticaddressdistinctfromframeID,notallocateddefault1.',0,255,None,True),
 ('message_octets','ActualdiagnosticSID-inclusivemessagelength1..4095;singlePDUupto6.',1,4095,'Byte',True),
 ('pdu_payload_octets','ActualSFup6/FF5/CF6SIDinclusivebytesin8byteLINPDU.',1,6,'Byte',True),
 ('pci','ActualPCItype/length/CFsequencebyte,notISO-TPextendedSF_CANFDencoding.',0,255,None,True),
 ('ff_length_low','ActualFirstFrameLENlow8bits of completeSID-inclusivelength,notCANextendedFF32bitlength.',0,255,None,True),
 ('cf_sequence','Actual4bitCFsequencefirst1/wrap15to0,notCANblocksize.',0,15,None,True),
 ('sid','ActualsupporteddiagnosticserviceID,NCFsubsetnotautomaticallUDS.',0,255,None,True),
 ('p2_min_ms','ActualNCFminimumdiagnosticresponsepreparationdefault50ms.',50,500,'ms',False),
 ('st_min_ms','ActualNCFdiagnosticseparationdefault0ms,notCANFCSTminbyte.',0,None,'ms',False),
 ('n_as_timeout_ms','ActualNCFtransmittimeoutdefault1000ms.',0,None,'ms',False),
 ('n_cr_timeout_ms','ActualNCFnextCFreceivertimeoutdefault1000ms.',0,None,'ms',False),
 ('n_cs_ms','ActualsendernextCFpreparationtime;(Ncs+Nas)<.9*Ncrtimeout.',0,None,'ms',False),
 ('n_as_actual_ms','Actualsendcompletiontimeusedinstrictschedulingperformancebound.',0,None,'ms',False),
 ('padding_octet','ActualunuseddiagnosticPDUbytesallones0xff.',255,255,None,True),
 ('functional_bound_ms','ActualapplicationfunctionalE2EbudgetseparatefromLINschedule/diagnostics.',0,None,'ms',False)]:d(key,'number',meaning,lo=lo,hi=hi,unit=unit,integer=integer)
for key,meaning in [('diode_present','ActualmandatoryseriesdiodewithLINpull-up,notinventedTrueequipment.'),
 ('tx_enabled','Actualenabledordinarytransmissionstate,notassumedwhileasleep.'),
 ('flow_control','LINtransportdoesnotuseFC;gatewayCANFCisindependent.'),
 ('schedule_confirmed','Actualwholescheduleandcollision/diagnosticmodeverified.'),
 ('capacity_confirmed','ActualwholeLINcapacityverified,notpositiveprofilevalidation.')]:d(key,'boolean',meaning)
REMOVED={k:'Removed inherited '+k+': LIN LDFschedule/commander/PID/checksum/diagnostic/singlewirePHY replace genericCAN/Ethernet queues/retransmission/sync/gateway assumptions.'for k in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['edition','physical_profile','node_role','frame_kind','revision','device_source','binding_source','physical_source','ldf_source',
 'encoding_source','schedule_source','capacity_source','acceptance_source','commander_node_id','bitrate_bps']


def protected_id(identifier):
    bit=lambda n:(identifier>>n)&1
    return identifier|((bit(0)^bit(1)^bit(2)^bit(4))<<6)|((1^(bit(1)^bit(3)^bit(4)^bit(5)))<<7)


def semantics():
    rules=[dict(parameter='local_timing_evidence',allowed=[],source='docs/GENERATION_RULE_MANAGER.md',source_revision='LINLDF/nativeframes/schedule/PHY are notI2C localtransactions')]
    def r(key,when=None,**kw):rules.append(dict(parameter='lin_'+key,when={'lin_'+k:v for k,v in(when or{}).items()},source=SPEC,source_revision=SOURCES[SPEC],**kw))
    old={'edition':OLD};phy={**old,'physical_profile':'LIN_2_2A_SINGLE_WIRE'}
    r('registered_source',when_not={'lin_edition':OLD},required=True)
    r('registered_source',{'physical_profile':'REGISTERED_PHY'},required=True)
    r('registered_source',{'frame_kind':'REGISTERED_FRAME'},required=True)
    r('registered_source',{'responder_version':'REGISTERED_VERSION'},required=True)
    r('bitrate_bps',phy,minimum=1000,maximum=20000)
    r('node_count',phy,maximum=16)
    r('commander_clock_error_percent',phy,exclusive_maximum=.5)
    r('unsynced_clock_error_percent',{**phy,'sync_mode':'SYNC_MEASURED'},exclusive_maximum=14)
    r('synced_clock_error_percent',{**phy,'sync_mode':'SYNC_MEASURED'},exclusive_maximum=2)
    r('no_sync_clock_error_percent',{**phy,'sync_mode':'NO_SYNC'},exclusive_maximum=1.5)
    r('peer_clock_difference_percent',phy,exclusive_maximum=2)
    r('pullup_ohm',{**phy,'supply_role':'COMMANDER'},minimum=900,maximum=1100)
    r('pullup_ohm',{**phy,'supply_role':'RESPONDER'},minimum=20000,maximum=60000)
    r('diode_present',phy,allowed=[True]);r('supply_v',phy,minimum=8,maximum=18)
    r('bus_capacitance_nf',phy,minimum=1,maximum=10);r('rc_time_us',phy,minimum=1,maximum=5);r('bus_length_m',phy,maximum=40)
    for identifier in range(62):r('pid',{**old,'frame_id':identifier},allowed=[protected_id(identifier)])
    r('frame_id',old,maximum=61)
    for kind in ('UNCONDITIONAL','EVENT_TRIGGERED','SPORADIC'):
        base={**old,'frame_kind':kind};r('frame_id',base,maximum=59)
        r('publisher_node_id',base,when_present=['lin_frame_id'],required=True)
    for kind in ('UNCONDITIONAL','SPORADIC'):
        r('publisher_role',{**old,'frame_kind':kind},forbidden=['EVENT_CANDIDATES'])
    r('publisher_role',{**old,'frame_kind':'SPORADIC'},allowed=['COMMANDER'])
    r('collision_schedule_source',{**old,'frame_kind':'EVENT_TRIGGERED'},required=True)
    r('checksum_model',{**old,'responder_version':'LIN_1_X'},allowed=['CLASSIC'])
    for kind in ('UNCONDITIONAL','EVENT_TRIGGERED','SPORADIC'):
        r('checksum_model',{**old,'frame_kind':kind,'responder_version':'LIN_2_X'},allowed=['ENHANCED'])
    for identifier in (60,61):r('checksum_model',{**old,'frame_id':identifier},allowed=['CLASSIC'])
    for kind,identifier in [('DIAGNOSTIC_REQUEST',60),('DIAGNOSTIC_RESPONSE',61),('GO_TO_SLEEP',60)]:
        base={**old,'frame_kind':kind};r('frame_id',base,allowed=[identifier]);r('data_octets',base,allowed=[8]);r('checksum_model',base,allowed=['CLASSIC'])
    r('publisher_role',{**old,'frame_kind':'DIAGNOSTIC_REQUEST'},allowed=['COMMANDER'])
    r('publisher_role',{**old,'frame_kind':'DIAGNOSTIC_RESPONSE'},allowed=['RESPONDER'])
    r('diag_nad',{**old,'frame_kind':'GO_TO_SLEEP'},allowed=[0])
    r('break_bits',old,minimum=13);r('delimiter_bits',old,minimum=1)
    r('time_base_ms',exclusive_minimum=0)
    r('response_nominal_bits',old,equal_expression={'product':[{'sum':['lin_data_octets',1]},10]})
    frame_bits={'sum':[34,{'product':[{'sum':['lin_data_octets',1]},10]}]}
    r('frame_nominal_bits',old,equal_expression=frame_bits)
    bit_ms={'product':[1000,{'power':['lin_bitrate_bps',-1]}]}
    frame_max={'product':[1.4,frame_bits,bit_ms]}
    r('frame_max_ms',old,equal_expression=frame_max)
    r('header_actual_ms',old,minimum_expression={'product':[34,bit_ms]},maximum_expression={'product':[47.6,bit_ms]})
    r('response_actual_ms',old,minimum_expression={'product':[{'sum':['lin_data_octets',1]},10,bit_ms]},
        maximum_expression={'product':[{'sum':['lin_data_octets',1]},14,bit_ms]})
    r('slot_ms',old,equal_expression={'product':['lin_time_base_ms','lin_slot_ticks']},exclusive_minimum_expression={'sum':['lin_jitter_ms',frame_max]})
    r('tx_enabled',{'state':'INITIALIZING'},allowed=[False])
    r('tx_enabled',{'state':'BUS_SLEEP'},when_not={'lin_frame_kind':'WAKE_UP'},allowed=[False])
    r('wake_pulse_us',old,minimum=250,maximum=5000);r('wake_detect_us',old,exclusive_minimum=150)
    r('responder_ready_ms',old,maximum=100);r('wake_retry_ms',old,minimum=150,maximum=250)
    r('wake_block_attempts',old,allowed=[3]);r('wake_block_pause_ms',old,minimum=1500);r('sleep_idle_ms',old,minimum=4000,maximum=10000)
    for kind,lo,hi in [('PHYSICAL',1,125),('FUNCTIONAL',126,126),('BROADCAST',127,127),('USER_DEFINED',128,255)]:
        r('diag_nad',{**old,'nad_kind':kind},minimum=lo,maximum=hi)
    for cls in ('II','III'):
        for key in ('ncf_source','diag_source'):r(key,{**old,'diag_class':cls},required=True)
    for key in ('p2_min_ms','st_min_ms','n_as_timeout_ms','n_cr_timeout_ms','n_cs_ms','n_as_actual_ms'):
        r(key,{**old,'diag_class':'I'},allowed=[])
    r('flow_control',old,allowed=[False])
    r('n_as_timeout_ms',old,exclusive_minimum=0,maximum=1000);r('n_cr_timeout_ms',old,exclusive_minimum=0,maximum=1000)
    r('n_as_actual_ms',old,maximum_parameter='lin_n_as_timeout_ms')
    r('n_cs_ms',old,maximum_expression={'subtract':[{'product':['lin_n_cr_timeout_ms',.9]},'lin_n_as_actual_ms']})
    # The normative scheduling sum is strict; using the reverse expression preserves the boundary.
    r('n_cr_timeout_ms',old,exclusive_minimum_expression={'product':[{'sum':['lin_n_cs_ms','lin_n_as_actual_ms']},1/.9]})
    r('message_octets',{**old,'pdu_type':'SF'},maximum=6)
    r('pdu_payload_octets',{**old,'pdu_type':'SF'},equal_parameter='lin_message_octets')
    r('pci',{**old,'pdu_type':'SF'},equal_parameter='lin_message_octets')
    r('message_octets',{**old,'pdu_type':'FF'},minimum=7)
    r('pdu_payload_octets',{**old,'pdu_type':'FF'},allowed=[5])
    r('pci',{**old,'pdu_type':'FF'},minimum=16,maximum=31)
    high_length={'ceiling':[{'product':[{'subtract':['lin_message_octets',255]},1/256]}]}
    r('pci',{**old,'pdu_type':'FF'},equal_expression={'sum':[16,high_length]})
    r('ff_length_low',{**old,'pdu_type':'FF'},equal_expression={'subtract':['lin_message_octets',{'product':[high_length,256]}]})
    for kind in ('SF','CF'):r('ff_length_low',{**old,'pdu_type':kind},allowed=[])
    r('pci',{**old,'pdu_type':'CF'},equal_expression={'sum':[32,'lin_cf_sequence']})
    return {'rate_model':{'type':'EXPLICIT_LIN_EDITION_LDF_PHY','fields':[]},'required_parameters':['lin_'+k for k in REQUIRED],
        'native_parameter_prefixes':['lin_'],'parameter_constraints':rules,
        'mechanisms':{'integrity':['PID_PARITY','LIN_CHECKSUM','END_AROUND_CARRY_CLASSIC_OR_ENHANCED_CHECKSUM'],
        'addressing':['FRAME_IDENTIFIER_VERSUS_DIAGNOSTIC_NAD'],
        'arbitration':['SINGLE_COMMANDER_LDF_SCHEDULE_EVENT_COLLISION_RESOLUTION'],
        'diagnostics':['LIN_SF_FF_CF_NO_FLOW_CONTROL'],
        'supervision':['RESPONSE_ERROR_AND_TRANSFER_STATUS_NOT_FUNCTIONAL_E2E']}}


def fields():
    result=[];required=set(semantics()['required_parameters'])
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('lin_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[]
        def p(value,**conditions):proposals.append(dict(when={'lin_edition':OLD,**{'lin_'+k:v for k,v in conditions.items()}},value=value,source=SPEC,source_revision=SOURCES[SPEC]))
        for field,value in [('start_bits',1),('data_bits',8),('stop_bits',1),('byte_bits',10),('sync_byte',85),('header_nominal_bits',34),('data_order','LSB_FIRST'),('uart_parity','NONE')]:
            if key==field:p(value)
        if key=='bitrate_bps':
            p(1000,physical_profile='LIN_2_2A_SINGLE_WIRE')
            proposals[-1]['basis']='USER_POLICY_LOWEST_SPECIFIED_RATE_NOT_UNIVERSAL_LIN_DEFAULT'
        if key=='break_bits':p(13)
        if key=='delimiter_bits':p(1)
        if key=='time_base_ms':p(5)
        if key=='pullup_ohm':
            for role,value in [('COMMANDER',1000),('RESPONDER',30000)]:p(value,physical_profile='LIN_2_2A_SINGLE_WIRE',supply_role=role)
        if key=='checksum_model':
            for kind in ('DIAGNOSTIC_REQUEST','DIAGNOSTIC_RESPONSE','GO_TO_SLEEP'):p('CLASSIC',frame_kind=kind)
            p('CLASSIC',responder_version='LIN_1_X')
            for kind in ('UNCONDITIONAL','EVENT_TRIGGERED','SPORADIC'):p('ENHANCED',frame_kind=kind,responder_version='LIN_2_X')
        if key in ('frame_id','data_octets'):
            for kind,identifier in [('DIAGNOSTIC_REQUEST',60),('DIAGNOSTIC_RESPONSE',61),('GO_TO_SLEEP',60)]:p(identifier if key=='frame_id'else 8,frame_kind=kind)
        if key in ('p2_min_ms','st_min_ms','n_as_timeout_ms','n_cr_timeout_ms'):
            for cls in ('II','III'):p({'p2_min_ms':50,'st_min_ms':0,'n_as_timeout_ms':1000,'n_cr_timeout_ms':1000}[key],diag_class=cls)
        if key=='padding_octet':
            for kind in ('DIAGNOSTIC_REQUEST','DIAGNOSTIC_RESPONSE'):p(255,frame_kind=kind)
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
