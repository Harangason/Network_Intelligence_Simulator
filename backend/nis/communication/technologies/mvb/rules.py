"""MVB native frame/scan declarations; historical controller and current monitor qualifiers."""
ABB='https://www.daube.ch/ddd/files/mvb_kit_c2.pdf'
IMC='https://www.imc-tm.cn/fileadmin/Public/Downloads/Datasheets/imc_optional_accessories/imc_Accessories_EN_TDs/TD_Digital_Fieldbus.pdf'
CABLE='https://www.lapp.ch/media/PIM_NEU/Datenbl%C3%A4tter/DB2173001EN.pdf'
IEC='https://webstore.iec.ch/en/publication/5402'
SOURCES={ABB:'ABB MVBVirtualTerminal/PCNode TN-AC-95/185 December19 1995 chapter2 pp2-2..2-7 and2-10..2-18 on technical author website; source contains no2-8/2-9; historical controller qualifier, not all-edition IECconformance',
 IMC:'imc fieldbusinterfaces datasheet4.15 February27 2026 pp17-18; hardwarewiredEMD orESD+ logging periodicdata, not configurable transmitter/busadministrator',
 CABLE:'LAPP UNITRONICTRAINMVB2173001 DB2173001EN Version06 November27 2025 pp1-2; cable-specific electrical/mechanical/thermal limits',
 IEC:'IEC61375-3-1:2012 Edition1 publicationJune21 2012/stability2030 primarypublisher metadata only; fulllicensed268page normative text not read'}
DECLARATIONS=[]
def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,source=ABB,integer=False):
    DECLARATIONS.append(dict(key='mv_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,
        options=options,source=source,source_revision=SOURCES[source],integer=integer))
for key,meaning,options,source in [
 ('implementation','Actual qualified historical ABB controller, current imc logging device or registered implementation; no silent interchange.',['ABB_PC_NODE_1995','IMC_LOGGING_4_15','REGISTERED'],IMC),
 ('transfer','Actual periodic processdata, messagepoll or supervisory/event procedure; eventpoll12bits are parameters not genericdestination.',['PROCESS_DATA','MESSAGE_DATA','SUPERVISORY_EVENT'],ABB),
 ('port_role','Actual configured source, sink or passive monitor; process port has oneproducer and potentially manyconsumers.',['SOURCE','SINK','MONITOR'],ABB),
 ('phy','Actual physically wired electricalshort/middle/extendedshort or optical media; not interchangeable CAN/ethernet port.',['ESD','ESD_PLUS','EMD','OGF','REGISTERED'],IMC),
 ('topology','Actual bus versus opticalstar or qualifiedalternative.',['BUS','STAR','REGISTERED'],ABB),
 ('encoding','Actual native Manchester MVB signalling, not NRZ UART and not two payload bits percarrierbit.',['MVB_MANCHESTER'],ABB),
 ('address_scope','Actual12bit master field meaning logicalport/deviceaddress/eventpollparameters.',['LOGICAL_PORT','DEVICE_ADDRESS','EVENT_PARAMETERS'],ABB),
 ('check_profile','Actual TC57 eightbit check permax64databits; no CANCRC or ModbusCRC16 fallback.',['TC57_8_PER_MAX64','REGISTERED'],ABB),
 ('cable_profile','Actual selected LAPPpart or other qualified copper/fibre; no universal120ohm assumption.',['LAPP_2173001_V06','REGISTERED'],CABLE),
 ('cable_installation','Actual fixed or occasionalflex installation affects minimumradius.',['FIXED','OCCASIONAL_FLEX'],CABLE),
 ('cable_loss_point','Actual supported attenuation measurement frequency versus registered spectrum.',['F1_5_MHZ','F3_MHZ','REGISTERED'],CABLE),
]:d(key,'select',meaning,options=options,source=source)
for key,meaning,source in [
 ('device_source','Actual device/controller/datasheet/edition and qualification, not manufacturername inferred fromindustry.',IMC),
 ('master_ref','Actual current busadministrator; backup master count does not allow concurrentmasterframes.',ABB),
 ('source_ref','Actual oneproducer device for selectedlogicalport; masteradministrator may be anotherdevice.',ABB),
 ('mapping_source','Actual source/sink/port/device/fixeddataset assignment and addresses.',ABB),
 ('codec_source','Actual native encodedframe/enddelimiters/check/bytebitorder/applicationdataset ormessageheader.',ABB),
 ('schedule_source','Actual administrator scanlist/periodic-sporadic budget/mastership/retry response and queues.',ABB),
 ('physical_source','Actual wiredPHY/length/coupling/repeaters/terminators/slowest redundantline measurements.',IMC),
 ('acceptance_source','Actual freshness/deadline/security/safety criteria; portupdates alone are notE2Eacceptance.',ABB),
 ('registered_source','Actual selectedalternative implementation/PHY/CRC/schedule/registered qualification.',IEC),
 ('wired_phy','Actual immutable hardwarechosen PHY on imc logging device; mustmatchbusphysically.',IMC),
 ('master_word_hex','Actual fourhex characters representingtwooctets/16informationbits: Fcodehigh4 plusaddress/parameterslow12.',ABB),
 ('cable_source','Actual installedpart/datasheet/measurement; qualifiedpartselection is notinstallationproof.',CABLE),
 ('cable_characterization_source','Actual otherfrequency/impedance/attenuation/coupling/temperature source.',CABLE),
 ('freshness_source','Actual perport update age/application acceptance and behavior onstale data.',ABB),
]:d(key,'text',meaning,source=source)
for key,meaning,lo,hi,unit,source,integer in [
 ('function_code','Actual4bit Fcode: PD0..4,5..7/10/11reserved,8mastership/9event/12message/13..15poll.',0,15,None,ABB,True),
 ('address_field','Actual12bit value including logicalport0..4095 or devices/parameters, not IPaddress.',0,4095,None,ABB,True),
 ('message_station_address','Actual8bit message station destination/source, distinct12bit deviceaddress.',0,255,None,IMC,True),
 ('dataset_bits','Actual configuredport16/32/64/128/256bit full data, not everyapplicationvariablebytecount.',16,256,'bit',IMC,True),
 ('delimiter_bits','Actual ninebit native master/slave startdelimiter includingManchester violations.',1,None,'bit',ABB,True),
 ('master_info_bits','Actual fourFcode+12address informationbits, excludingdelimiter/check.',1,None,'bit',ABB,True),
 ('master_check_bits','Actual eightbit master check, not CRC16.',1,None,'bit',ABB,True),
 ('master_frame_bits','Actual33nativebit-times=9+16+8; enddelimiter/guard is separatelyqualified.',1,None,'bit',ABB,True),
 ('check_blocks','Actual number of8bit check sequences overup to64bit datablocks.',1,4,None,ABB,True),
 ('check_bits_per_block','Actual eightcheckbits permax64databits.',1,None,'bit',ABB,True),
 ('slave_frame_bits','Actual start9+data+8*ceil(data/64), excluding separatelyqualifiedenddelimiter/guard.',1,None,'bit',ABB,True),
 ('master_serial_us','Actual serialized33bit-times at1.5Mbit/s=22us, not complete telegramincludingturnaround.',0,None,'us',ABB,False),
 ('slave_serial_us','Actual nativeframebit-times serialization withoutseparate enddelimiter/turnaround.',0,None,'us',ABB,False),
 ('end_guard_us','Actual media-specific enddelimiter/idle shaping and guard, sourcequalified not guessedonebyte.',0,None,'us',ABB,False),
 ('reply_at_slave_us','Actual endmaster->startslave atsource, ABBhistorical1.4..4us only.',0,None,'us',ABB,False),
 ('reply_at_master_us','Actual endmaster->startslave atmaster, includesroundtrip/repeater/accessdelay; historical<=42.7us.',0,None,'us',ABB,False),
 ('line_a_reply_us','Actual lineA roundtrip/reply bound, separate redundant lineB.',0,None,'us',ABB,False),
 ('line_b_reply_us','Actual lineB roundtrip/reply bound; worstredundantline governs not average.',0,None,'us',ABB,False),
 ('next_master_gap_us','Actual controller gap afterresponse, not a universalCANintermission.',0,None,'us',ABB,False),
 ('telegram_bound_us','Actual master+reply+slave+endguard+nextmastergap bound; no wholebusywindow/schedulecertificate.',0,None,'us',ABB,False),
 ('active_masters','Actual atmostone activeadministrator, tokenrotationbackup not simultaneousmasters.',0,None,None,ABB,True),
 ('source_count','Actual processport producer count, exactlyone; eventpoll can involve multiplebidders.',0,None,None,ABB,True),
 ('sink_count','Actual number ofsubscribed consumers; framebroadcast not perconsumer duplicated.',0,None,None,ABB,True),
 ('segment_m','Actual selectedmedium segmentlength; historicalESD20/EMD200/OGF2000 andimc200 qualifiers.',0,None,'m',IMC,False),
 ('segment_nodes','Actual segmenttaps; imcselected32max, not allnetworks4095 devices ononewire.',1,None,None,IMC,True),
 ('base_cycle_ms','Actual ABB1ms standardtarget versusqualified0.833ms60Hzsetting; no globalCAN100ms.',0,None,'ms',ABB,False),
 ('basic_multiple','Actual ABBbasicperiod1/2/4/8 multiplesof selectedbasecycle.',1,8,None,ABB,True),
 ('basic_period_ms','Actual basecycle timesbasicmultiple, distinctindividualportpollperiod.',0,None,'ms',ABB,False),
 ('poll_exponent','Actual poweroftwo multiplier forindividual portpollcycle.',0,10,None,ABB,True),
 ('poll_period_ms','Actual basicperiod times2^exponent; historical1024msupperlimit qualified.',0,None,'ms',ABB,False),
 ('macro_period_ms','Actual longestindividualpollperiod inactualscanlist, not assumed1024ms cycle.',0,None,'ms',ABB,False),
 ('master_frame_interval_ms','Actual masterframe monitoringinterval, ABBhistorical<=1.3ms.',0,None,'ms',ABB,False),
 ('periodic_us','Actual periodicphase reservedbudget inbasicperiod.',0,None,'us',ABB,False),
 ('supervisory_us','Actual supervisoryphase budget, includingmastership/status.',0,None,'us',ABB,False),
 ('event_us','Actual eventphase budget/queues/responses, not a CANidentifierpriority.',0,None,'us',ABB,False),
 ('guard_us','Actual guardphase budget untilnextperiod; no newframe iflongestresponse cannotfinish.',0,None,'us',ABB,False),
 ('turn_macrocycles','Actual controller mastership turncount, tokenhandover stateactual.',1,None,None,ABB,True),
 ('remaining_us','Actual time untilnextbasicperiod; cannotstartlongesttelegram beyondthis.',0,None,'us',ABB,False),
 ('longest_telegram_us','Actual configuredlongestmaster-response withalloverhead/slowestline.',0,None,'us',ABB,False),
 ('message_header_bytes','Actual messageport transportheaderwithin256bitdata; no fabricated zeroheader.',0,32,'byte',ABB,True),
 ('variable_offset_bits','Actual applicationvariable bitoffsetwithinfixeddataset.',0,255,'bit',ABB,True),
 ('variable_bits','Actual application encoding width, not inferredfromfrequency/function.',1,256,'bit',ABB,True),
 ('update_age_ms','Actual sinkport lastupdate age, not genericlinklatency.',0,None,'ms',ABB,False),
 ('freshness_limit_ms','Actual applicationaccepted freshnesslimit, not universalbusstandard.',0,None,'ms',ABB,False),
 ('clock_tolerance_ppm','Actual declaredclock tolerance fromselectedhardware; no guessed universal50ppm.',0,None,'ppm',IMC,False),
 ('measured_rate_bps','Actual measuredrate distinctnominal1.5M carrier; comparisonrequiresactualclock tolerance.',1,None,'bit/s',IMC,False),
 ('cable_impedance_ohm','Actual cableimpedance atqualifiedfrequency; LAPP120±10% ispart-specific.',0,None,'ohm',CABLE,False),
 ('cable_r_ohm_km','Actual20Cconductorresistance, LAPP<=40.1ohm/km.',0,None,'ohm/km',CABLE,False),
 ('cable_insulation_ohm_km','Actual20Cinsulationresistance lengthproduct, LAPP>=5Gohm*km.',0,None,'ohm*km',CABLE,False),
 ('cable_cap_nf_km','Actual20Cmutualcapacitance at1.5MHz, LAPP<=46nF/km.',0,None,'nF/km',CABLE,False),
 ('cable_coupling_pf_km','Actual20Ccapacitivecoupling at1.5MHz, LAPP<=1500pF/km.',0,None,'pF/km',CABLE,False),
 ('cable_attenuation_db_km','Actual attenuation atselectedqualifiedfrequency, not fixedwholeline loss.',0,None,'dB/km',CABLE,False),
 ('cable_frequency_mhz','Actual cablecharacterizationfrequency, sourcequalified0.75..3MHzimpedanceband.',0,None,'MHz',CABLE,False),
 ('cable_lab_temperature_c','Actual electricalqualification labtemperature20C, distinctoperatingtemperature.',None,None,'C',CABLE,False),
 ('cable_cap_frequency_mhz','Actual1.5MHzcapacitance/coupling testpoint, separate loss/impedance/transferimpedance.',0,None,'MHz',CABLE,False),
 ('cable_xtalk_frequency_mhz','Actual0.75..3MHznearendcrosstalk testpoint.',0,None,'MHz',CABLE,False),
 ('cable_transfer_frequency_mhz','Actual20MHztransferimpedance testpoint, not the1.5Mbit/s carrierfrequency.',0,None,'MHz',CABLE,False),
 ('cable_crosstalk_db_km','Actual20Cnearendcrosstalk at0.75..3MHz, LAPP>=45dB/km.',0,None,'dB/km',CABLE,False),
 ('cable_transfer_mohm_m','Actualtransferimpedance at20MHz, LAPP<=20milliohm/m.',0,None,'milliohm/m',CABLE,False),
 ('cable_velocity_c','Actual nominalpropagation velocityfraction0.74c forselectedLAPPpart, not allmedia6us/km.',0,1,None,CABLE,False),
 ('operating_voltage_v','Actual cableoperatingvoltage<=125V, not a transmitamplitude orpowersupplyrating.',0,None,'V',CABLE,False),
 ('cable_outer_mm','Actual installedouterdiameter; nominal7.6mm proposalrequirespartverification.',0,None,'mm',CABLE,False),
 ('bending_radius_mm','Actual installedminimumradius3*diamfixed/10*diamoccasionalflex.',0,None,'mm',CABLE,False),
 ('temperature_c','Actual fixedinstallationtemperature, LAPP−40..90C; no universaltransceiverthermalrange.',None,None,'C',CABLE,False),
]:d(key,'number',meaning,lo,hi,unit,source=source,integer=integer)
for key,meaning in [
 ('redundant','Actual duplicatedmedia sendboth/receiveone, no twiceusefulpayloadallocation.'),
 ('fixed_dataset','Actual processdataset size/formatfixedatinitialization; runtimeformat changes not allowed.'),
 ('variables_nonoverlap','Actual codec/layout verifiednooverlappingprocessvariables.'),
 ('word_bit_order_qualified','Actual host/controller endian andbit/wordmixingqualification; no implicitlittleendian.'),
 ('start_permitted','Actual controllerabouttostartmasterframe; longestresponsemustfitremainingperiod.'),
]:d(key,'boolean',meaning)
REQUIRED=['implementation','transfer','port_role','phy','topology','encoding','master_ref','device_source','mapping_source',
 'codec_source','schedule_source','physical_source','acceptance_source','active_masters','redundant']
REMOVED={k:'MVB requires own administrator/frame/PHY/scan evidence, not genericCAN/Ethernet '+k+' defaults.'for k in
 ('mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
  'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms')}

def semantics():
    rules=[]
    def r(key,when=None,source=ABB,**kw):
        rules.append(dict(parameter=key if key in('payload_bytes','bitrate','local_timing_evidence')else'mv_'+key,
            when={'mv_'+k:v for k,v in(when or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('local_timing_evidence',allowed=[])
    for key in REQUIRED:r(key,required=True)
    r('active_masters',allowed=[1]);r('registered_source',{'implementation':'REGISTERED'},required=True,source=IEC)
    r('phy',{'implementation':'IMC_LOGGING_4_15'},allowed=['EMD','ESD_PLUS'],source=IMC)
    r('wired_phy',{'implementation':'IMC_LOGGING_4_15'},required=True,equal_parameter='mv_phy',source=IMC)
    r('port_role',{'implementation':'IMC_LOGGING_4_15'},allowed=['MONITOR'],source=IMC)
    r('transfer',{'implementation':'IMC_LOGGING_4_15'},allowed=['PROCESS_DATA'],source=IMC)
    r('topology',{'implementation':'IMC_LOGGING_4_15'},allowed=['BUS'],source=IMC)
    r('segment_m',{'implementation':'IMC_LOGGING_4_15'},maximum=200,source=IMC)
    r('segment_nodes',{'implementation':'IMC_LOGGING_4_15'},maximum=32,source=IMC)
    for phy,length in [('ESD',20),('EMD',200),('OGF',2000)]:r('segment_m',{'implementation':'ABB_PC_NODE_1995','phy':phy},maximum=length)
    r('registered_source',{'phy':'REGISTERED'},required=True,source=IEC)
    r('registered_source',{'check_profile':'REGISTERED'},required=True)
    for key,value in [('delimiter_bits',9),('master_info_bits',16),('master_check_bits',8),('master_frame_bits',33),('check_bits_per_block',8)]:r(key,allowed=[value])
    r('dataset_bits',allowed=[16,32,64,128,256],source=IMC)
    r('check_blocks',equal_expression={'ceiling':[{'product':['mv_dataset_bits',1/64]}]},exact_decimal_equality=True)
    r('slave_frame_bits',equal_expression={'sum':[9,'mv_dataset_bits',{'product':[8,'mv_check_blocks']}]},exact_decimal_equality=True)
    r('master_frame_bits',equal_expression={'sum':['mv_delimiter_bits','mv_master_info_bits','mv_master_check_bits']},exact_decimal_equality=True)
    r('master_serial_us',allowed=[22])
    r('slave_serial_us',equal_expression={'product':['mv_slave_frame_bits',2/3]})
    r('telegram_bound_us',minimum_expression={'sum':['mv_master_serial_us','mv_reply_at_master_us','mv_slave_serial_us','mv_end_guard_us','mv_next_master_gap_us']})
    r('reply_at_master_us',{'implementation':'ABB_PC_NODE_1995'},maximum=42.7)
    r('reply_at_slave_us',{'implementation':'ABB_PC_NODE_1995'},minimum=1.4,maximum=4)
    r('reply_at_master_us',minimum_parameter='mv_reply_at_slave_us')
    for line in ('line_a_reply_us','line_b_reply_us'):r('reply_at_master_us',{'redundant':True},minimum_parameter='mv_'+line)
    for code,bits in enumerate((16,32,64,128,256)):
        r('dataset_bits',{'transfer':'PROCESS_DATA','function_code':code},allowed=[bits])
    for key in ('function_code','address_field','dataset_bits','source_ref','source_count','fixed_dataset','variables_nonoverlap','word_bit_order_qualified'):
        r(key,{'transfer':'PROCESS_DATA'},required=True)
    r('function_code',{'transfer':'PROCESS_DATA'},allowed=list(range(5)))
    r('address_scope',{'transfer':'PROCESS_DATA'},required=True,allowed=['LOGICAL_PORT'])
    r('source_count',{'transfer':'PROCESS_DATA'},allowed=[1])
    for key in ('fixed_dataset','variables_nonoverlap','word_bit_order_qualified'):r(key,{'transfer':'PROCESS_DATA'},allowed=[True])
    r('payload_bytes',maximum_expression={'product':['mv_dataset_bits',1/8]})
    r('function_code',{'transfer':'MESSAGE_DATA'},required=True,allowed=[12])
    r('dataset_bits',{'transfer':'MESSAGE_DATA'},required=True,allowed=[256])
    r('address_scope',{'transfer':'MESSAGE_DATA'},required=True,allowed=['DEVICE_ADDRESS'])
    r('message_header_bytes',{'transfer':'MESSAGE_DATA'},required=True)
    r('payload_bytes',{'transfer':'MESSAGE_DATA'},maximum_expression={'subtract':[32,'mv_message_header_bytes']})
    r('function_code',{'transfer':'SUPERVISORY_EVENT'},required=True,allowed=[8,9,13,14,15])
    r('address_scope',{'transfer':'SUPERVISORY_EVENT','function_code':9},required=True,allowed=['EVENT_PARAMETERS'])
    r('master_word_hex',pattern=r'[0-9a-fA-F]{4}',integer_bitfields=[dict(offset=12,width=4,parameter='mv_function_code'),dict(offset=0,width=12,parameter='mv_address_field')])
    r('variable_offset_bits',maximum_expression={'subtract':['mv_dataset_bits','mv_variable_bits']})
    r('freshness_source',when_present=['mv_update_age_ms'],required=True)
    r('freshness_limit_ms',when_present=['mv_update_age_ms'],required=True)
    r('update_age_ms',maximum_parameter='mv_freshness_limit_ms')
    r('clock_tolerance_ppm',when_present=['mv_measured_rate_bps'],required=True,source=IMC)
    r('measured_rate_bps',minimum_expression={'product':[1500000,{'subtract':[1,{'product':['mv_clock_tolerance_ppm',0.000001]}]}]},source=IMC)
    r('measured_rate_bps',maximum_expression={'product':[1500000,{'sum':[1,{'product':['mv_clock_tolerance_ppm',0.000001]}]}]},source=IMC)
    r('base_cycle_ms',{'implementation':'ABB_PC_NODE_1995'},allowed=[1,0.833])
    r('basic_multiple',{'implementation':'ABB_PC_NODE_1995'},allowed=[1,2,4,8])
    r('basic_period_ms',equal_expression={'product':['mv_base_cycle_ms','mv_basic_multiple']},exact_decimal_equality=True)
    r('poll_period_ms',equal_expression={'product':['mv_basic_period_ms',{'power':[2,'mv_poll_exponent']}]},exact_decimal_equality=True)
    r('poll_period_ms',{'implementation':'ABB_PC_NODE_1995'},maximum=1024)
    r('macro_period_ms',{'implementation':'ABB_PC_NODE_1995'},maximum=1024,minimum_parameter='mv_poll_period_ms')
    r('master_frame_interval_ms',{'implementation':'ABB_PC_NODE_1995'},maximum=1.3)
    r('periodic_us',equal_expression={'subtract':[{'product':[1000,'mv_basic_period_ms']},{'sum':['mv_supervisory_us','mv_event_us','mv_guard_us']}]},exact_decimal_equality=True)
    r('periodic_us',{'implementation':'ABB_PC_NODE_1995'},maximum_expression={'subtract':[{'product':[1000,'mv_basic_period_ms']},350]})
    for key in ('remaining_us','longest_telegram_us'):r(key,{'start_permitted':True},required=True)
    r('remaining_us',{'start_permitted':True},minimum_parameter='mv_longest_telegram_us')
    r('longest_telegram_us',minimum_parameter='mv_telegram_bound_us')
    r('cable_source',when_present=['mv_cable_profile'],required=True,source=CABLE)
    r('cable_characterization_source',{'cable_profile':'REGISTERED'},required=True,source=CABLE)
    for key in ('cable_r_ohm_km','cable_insulation_ohm_km','cable_cap_nf_km','cable_coupling_pf_km'):
        r('cable_lab_temperature_c',{'cable_profile':'LAPP_2173001_V06'},when_present=['mv_'+key],required=True,allowed=[20],source=CABLE)
    for key in ('cable_cap_nf_km','cable_coupling_pf_km'):
        r('cable_cap_frequency_mhz',{'cable_profile':'LAPP_2173001_V06'},when_present=['mv_'+key],required=True,allowed=[1.5],source=CABLE)
    r('cable_xtalk_frequency_mhz',{'cable_profile':'LAPP_2173001_V06'},when_present=['mv_cable_crosstalk_db_km'],required=True,minimum=0.75,maximum=3,source=CABLE)
    r('cable_transfer_frequency_mhz',{'cable_profile':'LAPP_2173001_V06'},when_present=['mv_cable_transfer_mohm_m'],required=True,allowed=[20],source=CABLE)
    for key,lo,hi in [('cable_impedance_ohm',108,132),('cable_r_ohm_km',0,40.1),('cable_insulation_ohm_km',5000000000,None),
        ('cable_cap_nf_km',0,46),('cable_coupling_pf_km',0,1500),('cable_crosstalk_db_km',45,None),('cable_transfer_mohm_m',0,20),
        ('operating_voltage_v',0,125)]:r(key,{'cable_profile':'LAPP_2173001_V06'},minimum=lo,maximum=hi,source=CABLE)
    r('phy',{'cable_profile':'LAPP_2173001_V06'},allowed=['ESD','ESD_PLUS','EMD'],source=CABLE)
    r('cable_frequency_mhz',when_present=['mv_cable_impedance_ohm'],required=True,source=CABLE)
    r('cable_frequency_mhz',{'cable_profile':'LAPP_2173001_V06'},when_present=['mv_cable_impedance_ohm'],minimum=0.75,maximum=3,source=CABLE)
    r('cable_loss_point',when_present=['mv_cable_attenuation_db_km'],required=True,source=CABLE)
    for point,freq,limit in [('F1_5_MHZ',1.5,15),('F3_MHZ',3,20)]:
        r('cable_frequency_mhz',{'cable_profile':'LAPP_2173001_V06','cable_loss_point':point},required=True,allowed=[freq],source=CABLE)
        r('cable_attenuation_db_km',{'cable_profile':'LAPP_2173001_V06','cable_loss_point':point},maximum=limit,source=CABLE)
    r('cable_characterization_source',{'cable_loss_point':'REGISTERED'},required=True,source=CABLE)
    r('bending_radius_mm',{'cable_profile':'LAPP_2173001_V06','cable_installation':'FIXED'},minimum_expression={'product':[3,'mv_cable_outer_mm']},source=CABLE)
    r('bending_radius_mm',{'cable_profile':'LAPP_2173001_V06','cable_installation':'OCCASIONAL_FLEX'},minimum_expression={'product':[10,'mv_cable_outer_mm']},source=CABLE)
    r('temperature_c',{'cable_profile':'LAPP_2173001_V06','cable_installation':'FIXED'},minimum=-40,maximum=90,source=CABLE)
    r('cable_characterization_source',{'cable_profile':'LAPP_2173001_V06','cable_installation':'OCCASIONAL_FLEX'},when_present=['mv_temperature_c'],required=True,source=CABLE)
    return dict(rate_model={'type':'FIXED_LINK_RATE','fields':['bitrate_bps'],'fixed_bps':1500000},
        required_parameters=['mv_'+k for k in REQUIRED],native_parameter_prefixes=['mv_'],parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
        physical_layer_profile_id='mvb_actual_wired_medium_and_redundant_lines',medium_access_model='ONE_ACTIVE_ADMINISTRATOR_MASTER_SLAVE_TELEGRAM',
        arbitration_model_id='PERIODIC_SCAN_SPORADIC_EVENT_AND_TOKEN_MASTER_TRANSFER',
        mechanisms={'encoding':['MVB_MANCHESTER_WITH_DISTINCT_MASTER_SLAVE_DELIMITERS'],
         'medium_access':['ONE_MASTER_SCAN_AND_SLAVE_RESPONSE','SPORADIC_EVENT_POLL_NOT_CAN_ARBITRATION'],
         'framing':['FCODE_AND_12BIT_ADDRESS_SCOPE','8CHECK_BITS_PER_MAX64_DATA_BITS'],
         'redundancy':['DUPLICATED_MEDIA_SEND_BOTH_RECEIVE_ONE','WORST_LINE_RESPONSE_BOUND'],
         'timing':['FIXED_DATASET_AND_ACTUAL_PORT_FRESHNESS','QUALIFIED_ADMINISTRATOR_SCAN_LIST']})

def fields():
    result=[]
    constants={'encoding':'MVB_MANCHESTER','delimiter_bits':9,'master_info_bits':16,'master_check_bits':8,
        'master_frame_bits':33,'master_serial_us':22,'check_bits_per_block':8,'check_profile':'TC57_8_PER_MAX64','active_masters':1}
    for spec in DECLARATIONS:
        key=spec['key'][3:];item={k:v for k,v in spec.items()if v is not None}
        item.update(label=key.replace('_',' '),category='physical',scope='network',editable=True,required=key in REQUIRED,
            parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        if key in constants:item.update(default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
            conditional_defaults=[dict(when={'mv_implementation':profile},value=constants[key],source=spec['source'],source_revision=spec['source_revision'])
                for profile in ('ABB_PC_NODE_1995','IMC_LOGGING_4_15')])
        if key=='base_cycle_ms':item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'mv_implementation':'ABB_PC_NODE_1995'},value=1,source=ABB,source_revision=SOURCES[ABB])])
        if key in('cable_outer_mm','cable_velocity_c'):item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'mv_cable_profile':'LAPP_2173001_V06'},value=7.6 if key=='cable_outer_mm'else 0.74,source=CABLE,source_revision=SOURCES[CABLE])])
        result.append(item)
    return result
