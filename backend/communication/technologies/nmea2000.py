"""NMEA2000 qualified CAN-CC/packet and installation parameters."""
P='https://www.nmea.org/nmea-2000.html'
GUIDE='https://actisense.com/wp-content/uploads/2021/08/Complete-Guide-to-NMEA-2000_Revision_4_2021.pdf'
WC='https://www.can-cia.org/fileadmin/cia/documents/publications/cnlm/june_2024/cnlm_24-1_p9_nmea_2000_conformance_testing_and_product_certification_dr_chris_quigley_warwick_control_technologies.pdf'
SS='https://simmasoftware.com/assets/images/nmea-2000-users-manual.pdf'
COMMIT='5b7b9fc3ccc18e30ebfba92da6486cffc6251595'
LIB='https://raw.githubusercontent.com/ttlappalainen/NMEA2000/'+COMMIT+'/src/NMEA2000.cpp'
HDR='https://raw.githubusercontent.com/ttlappalainen/NMEA2000/'+COMMIT+'/src/NMEA2000.h'
MSG='https://raw.githubusercontent.com/ttlappalainen/NMEA2000/'+COMMIT+'/src/N2kMsg.h'
SOURCES={P:'NMEA publisher version3.000 with amendments overview, retrieved2026-10-02. Licensed Main/Appendices A/B/C not read.',
 GUIDE:'Actisense Complete Guide Rev4 2021: network/cable/power/termination pp4-10, device24V compatibility not standard9..16V.',
 WC:'Warwick Control Technologies author DrChrisQuigley CANNewsletter2/2024 pp9-11: 250k,50physicaldevices,85..90% samplepoint,auto retransmission,isolation and actual certification/interoperability scope.',
 SS:'Simma ssNMEA2000-Multi manual1.3 April23 2013: pp6-11 CAN/NAME,16-22 packet/API,24-25 selected implementation buffers/tick. Public manual only, no software package/license acceptance.',
 LIB:'TimoLappalainen implementation pinned '+COMMIT+': ID PDU1/PDU2, fastpacket6+31*7, sequence0..7, actual buffers/transport support.',
 HDR:'TimoLappalainen header pinned '+COMMIT+': maxsource251, null254,100ms buffer timeout,60s heartbeat are implementation settings, not generic J1939 defaults.',
 MSG:'TimoLappalainen N2kMsg pinned '+COMMIT+': current storage223 bytes, application data may exceed8; physical CAN frame remains<=8.'}
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,u=None,opts=None,src=LIB,integer=False):
 DECLARATIONS.append(dict(key='n2_'+k,type=t,description=meaning,min=lo,max=hi,unit=u,options=opts,source=src,source_revision=SOURCES[src],integer=integer))
for k,meaning,opts,src in[
 ('implementation','Actual current installed stack/device, not inferred from project industry.',['TIMO_PINNED','SIMMA_1_3','REGISTERED'],LIB),
 ('edition','Actual implemented Main/Appendix/PGN edition; latest publisher metadata does not certify hardware.',['3.000','REGISTERED'],P),
 ('packet_class','Actual PGN transport registration: length alone does not select single or fast packet. ISO transport separate.',['SINGLE','FAST_PACKET','ISO_TP_BAM','ISO_TP_RTS_CTS','REGISTERED'],LIB),
 ('claim_status','Actual latest address claim state and NAME collision outcome, not a proposed source address.',['CLAIMED','CANNOT_CLAIM','LISTEN_ONLY','UNVERIFIED'],HDR),
 ('role','Actual active CAN participant versus silent receive-only monitor; silent monitor does not retransmit.',['ACTIVE','SILENT_MONITOR'],HDR),
 ('cable','Actual installed backbone cable grade; drop cable restrictions distinct.',['MICRO_LITE','MID','MINI_HEAVY','REGISTERED'],GUIDE),
 ('cable_catalog','Actual cable/connector rating revision; 2021 catalog current limits must not be universal.',['ACTISENSE_2021','REGISTERED'],GUIDE),
 ('power_profile','Actual standard9..16V versus separately device-qualified extended24V installation.',['STANDARD_9_16','DEVICE_24V_REGISTERED'],GUIDE),
 ('power_method','Actual bus power versus separately powered auxiliary device circuitry.',['BUS_ONLY','AUXILIARY_SEPARATE'],GUIDE),
]:d(k,'select',meaning,opts=opts,src=src)
for k,meaning,src in[
 ('device_source','Actual product/firmware/controller/physical compatibility proof.',WC),
 ('edition_source','Actual licensed PGN edition/source and applicable amendments/fields/scaling.',P),
 ('codec_source','Actual PGN field encoding, unavailable/reserved values, units and supported RX/TX lists.',P),
 ('transport_mapping_source','Actual PGN SINGLE/FAST/ISO-TP and supported reassembly registration.',LIB),
 ('claim_source','Actual NAME/address claim response, competing devices and persistent last source.',HDR),
 ('schedule_source','Actual PGNs/rates/priorities/all network traffic, CAN errors/automatic retries and interference bound.',WC),
 ('physical_source','Actual cable topology/connectors/termination/signal/samplepoint/isolation/loading proof.',GUIDE),
 ('power_source','Actual supply/fuse/ground/branch currents and both conductors of voltage-drop path.',GUIDE),
 ('acceptance_source','Actual application freshness/deadline/quality/interoperability acceptance separate from CAN CRC.',WC),
 ('registered_source','Actual alternative stack/cable/power/transport specification and revision.',P),
 ('name_hex','Actual lossless64bit unique NAME as16hex characters; never JavaScript floating point ID.',SS),
 ('tx_pgn_source','Actual declared transmit PGNs and timing/priority/instance configuration services.',WC),
 ('rx_pgn_source','Actual declared receive PGNs, filters and reassembly concurrency.',WC),
 ('certification_source','Actual product-specific NMEA certification evidence. Library presence is not certification.',P),
 ('model_id','Actual registered product model, not placeholder productcode666.',HDR),
 ('software_version','Actual current installed product software version, separate from edition.',HDR),
 ('serial_code','Actual unique product serial string, no manufacturer example copied.',HDR),
]:d(k,'text',meaning,src=src)
for k,meaning,lo,hi,u,src in[
 ('priority','Actual3bit identifier priority; PGN-specific default requires actual edition.',0,7,None,LIB),
 ('dp','Actual data page bit in pinned classic NMEA identifier, not J1939 extended-page variants.',0,1,None,LIB),
 ('edp','Actual reserved extended page bit; reviewed classic NMEA binding0.',0,0,None,LIB),
 ('pf','Actual PDU format octet: below240 addressedPDU1, otherwisePGN group extension.',0,255,None,LIB),
 ('ps','Actual PDU-specific octet: destination forPDU1 orPGN extension forPDU2.',0,255,None,LIB),
 ('source_address','Actual wire source. Claimed current pinned stack<=251, null254 special; no arbitrary CAN node default.',0,255,None,HDR),
 ('destination','Actual PDU1 destination or255 implicitglobal forPDU2.',0,255,None,LIB),
 ('pgn','Actual PGN1data-page/PF/group-extension number; PDU1lowoctet0.',0,131071,None,LIB),
 ('can_id','Actual29bit extended classicCAN identifier reconstructed frompriority/DP/PF/PS/source.',0,536870911,None,LIB),
 ('id_bits','Actual extended CAN29bit identifier, not11bitCAN or CANFD/BRS.',29,29,'bit',LIB),
 ('frame_bytes','Actual classicCAN DLC0..8, not application message length223.',0,8,'byte',SS),
 ('data_bytes','Actual complete PGN encoded application bytes, selected transport/storage dependent.',0,1785,'byte',SS),
 ('packet_frames','Actual number of data CAN frames; TP management frames are additional.',1,255,None,SS),
 ('fast_sequence','Actual wire3bit sequence perPGN; Simma API8bit argument is not wire255.',0,7,None,LIB),
 ('fast_frame_index','Actual wire5bit frame index0..31, lastframe must matchmessage packetcount.',0,31,None,LIB),
 ('fast_header','Actual fastpacket firstoctet32*sequence+frameindex.',0,255,None,LIB),
 ('tp_packet_sequence','Actual ISO transport data sequence1..255, separate FastPacket0..31.',1,255,None,SS),
 ('reassembly_ms','Actual selected stack timeout bound; not general recovery or100ms appdeadline.',0,None,'ms',HDR),
 ('sample_point_percent','Actual controller samplepoint after bit-timing configuration.',85,90,'%',WC),
 ('node_count','Actual physical devices onone network, not multiplelogical NAMEinstances.',1,50,None,WC),
 ('backbone_m','Actual terminator-to-terminator length ofselectedcable.',0,None,'m',GUIDE),
 ('drop_m','Actual longest instrumentdrop<=6m, distinct backbone extension.',0,6,'m',GUIDE),
 ('sum_drops_m','Actual sum ofall instrumentdrops<=78m.',0,78,'m',GUIDE),
 ('termination_count','Actual external harness end terminators, never soldered insidedevice.',2,2,None,GUIDE),
 ('termination_ohm','Actual nominalindividual end resistor120ohm; measured tolerance has own proof.',120,120,'ohm',GUIDE),
 ('nominal_parallel_ohm','Nominal120/2=60 equivalent, not fabricated measuredresistance.',60,60,'ohm',GUIDE),
 ('power_feed_v','Actual sourcepower feed voltage includingselectedextendedproof.',0,None,'V',GUIDE),
 ('device_v','Actual deviceTconnector voltage after loadedbranch drop.',0,None,'V',GUIDE),
 ('loop_ohm','Actual totalpositive+return branch resistance, not one conductor only.',0,None,'ohm',GUIDE),
 ('branch_current_a','Actual sumdraw onthis cable/connector branch, not one deviceLEN only.',0,None,'A',GUIDE),
 ('len','Actualdeclared LoadEquivalencyNumber;1LEN50mA isupperallocation, not measurement.',0,255,None,GUIDE),
 ('device_bus_current_ma','Actual maximum current fromNMEA supply; separateaux currentexcluded.',0,None,'mA',GUIDE),
 ('ground_points','Actual singleground point for networkpower, independent isolatedaux I/O.',1,1,None,GUIDE),
 ('product_code','Actual NMEA-assigned productcode; no library default666 auto-confirmation.',0,65535,None,SS),
 ('manufacturer_code','Actual registered11bit NAMEmanufacturer code, no example402.',0,2047,None,SS),
 ('identity_number','Actual assigned21bit NAMEidentity number, unique undermanufacturer.',0,2097151,None,SS),
 ('industry_group','Actual3bit NAMEfield; project industry andbusprotocolindependent.',0,7,None,SS),
 ('device_class','Actual7bit NAMEdeviceclass.',0,127,None,SS),
 ('class_instance','Actual4bit classinstance.',0,15,None,SS),
 ('function','Actual8bit devicefunction.',0,255,None,SS),
 ('function_instance','Actual5bit functioninstance.',0,31,None,SS),
 ('ecu_instance','Actual3bit deviceinstance.',0,7,None,SS),
 ('heartbeat_ms','Actual configuredheartbeat, library60s proposal onlyselectedstack.',0,None,'ms',HDR),
 ('tick_ms','Actual fixedSimma updatecallperiod, default10msnot10ms buscycle.',0,None,'ms',SS),
 ('bip_percent','ActualSimma allowabletransmit percentage;100 disablesprotection, not assuredcapacity.',0,100,'%',SS),
 ('bip_window_ms','ActualSimma250ms monitoringwindow, not universalwatchdog.',250,250,'ms',SS),
 ('tp_rx_buffers','ActualSimma simultaneousincomingISOtransport buffers, default10device-qualified.',0,None,None,SS),
 ('tp_tx_buffers','ActualSimma simultaneousoutgoingISOtransport buffers, default3device-qualified.',0,None,None,SS),
 ('tp_rx_bytes','ActualSimma ISOreceivebuffer<=1785; factory128nottransportmaximum.',0,1785,'byte',SS),
 ('tp_tx_bytes','ActualSimma ISOtransmitbuffer<=1785; factory128nottransportmaximum.',0,1785,'byte',SS),
 ('fp_rx_bytes','ActualSimmaFastPacket receivebuffer<=223; factory128not223guarantee.',0,223,'byte',SS),
 ('message_buffer_bytes','Actualselectedreassemblystorage, pinnedTimo223 notISO1785 universalstorage.',0,None,'byte',MSG),
 ('retry_bound_ms','Actual CAN error/retransmission servicebound; mandatoryautomaticretrydoesnotprovefinite bound.',0,None,'ms',WC),
 ('age_ms','Actual ageofacceptedPGNdata, unrelated reassembly/heartbeat.',0,None,'ms',WC),
 ('freshness_limit_ms','Actual applicationdeadline/freshness requirement, no CAN100ms fallback.',0,None,'ms',WC),
]:d(k,'number',meaning,lo,hi,u,src=src,integer=u not in('ms','%','m','ohm','A','V','mA'))
for k,meaning,src in[
 ('fd','Actual CANFD false inreviewed classic NMEA2000.',LIB),
 ('brs','Actual BRS false inclassicNMEA2000.',LIB),
 ('automatic_retransmission','Actual activeCAN automaticretransmission mandatory, separatefrom upperpacketretry.',WC),
 ('built_in_termination','Actual deviceinternaltermination notallowed forcertifiableNMEAdevice.',WC),
 ('arbitrary_address_capable','Actual1bit NAMEcapability, not achievedaddressclaim.',SS),
 ('isolated_io','Actual current AC/DC isolation proof, not catalognameassumedTrue.',WC),
 ('certified','Actual productcertification evidence, not certification ofthisparameterchecker.',P),
 ('extended_power_warning','Actual24V compatibility warning plusallconnecteddevicelimits.',GUIDE),
]:d(k,'boolean',meaning,src=src)
REQUIRED=('implementation','edition','packet_class','role','device_source','edition_source','codec_source','transport_mapping_source','schedule_source','acceptance_source')
REMOVED={k:'No universalNMEA2000 '+k+'; actual nativeCAN-CC/PGN/transport/device configuration replaces foreignnetworkpolicy.'for k in('mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','retry_limit','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms')}
def semantics():
 rules=[]
 def r(k,w=None,src=LIB,**kw):
  rules.append(dict(parameter=k if k in('payload_bytes','bitrate_bps','local_timing_evidence')else'n2_'+k,when={'n2_'+key:value for key,value in(w or{}).items()},source=src,source_revision=SOURCES[src],**kw))
 for k in REQUIRED:r(k,required=True)
 r('local_timing_evidence',allowed=[]);r('fd',allowed=[False]);r('brs',allowed=[False]);r('built_in_termination',allowed=[False],src=WC)
 r('registered_source',{'implementation':'REGISTERED'},required=True,src=P)
 for k in('automatic_retransmission','claim_status','claim_source','name_hex','source_address'):
  r(k,{'role':'ACTIVE'},required=True,src=WC)
 r('automatic_retransmission',{'role':'ACTIVE'},allowed=[True],src=WC)
 r('claim_status',{'role':'SILENT_MONITOR'},allowed=['LISTEN_ONLY'],src=HDR)
 r('automatic_retransmission',{'role':'SILENT_MONITOR'},allowed=[False],src=HDR)
 r('source_address',{'claim_status':'CLAIMED','implementation':'TIMO_PINNED'},maximum=251,src=HDR)
 r('source_address',{'claim_status':'CANNOT_CLAIM'},allowed=[254],src=HDR)
 r('name_hex',pattern=r'[0-9A-Fa-f]{16}',src=SS)
 for k in('priority','dp','pf','ps','source_address'):r(k,when_present=['n2_can_id'],required=True)
 r('can_id',equal_expression={'sum':[{'product':['n2_priority',67108864]},{'product':['n2_dp',16777216]},{'product':['n2_pf',65536]},{'product':['n2_ps',256]},'n2_source_address']})
 r('pgn',when_ranges={'n2_pf':[0,239]},equal_expression={'sum':[{'product':['n2_dp',65536]},{'product':['n2_pf',256]}]})
 r('destination',when_ranges={'n2_pf':[0,239]},equal_parameter='n2_ps')
 r('pgn',when_ranges={'n2_pf':[240,255]},equal_expression={'sum':[{'product':['n2_dp',65536]},{'product':['n2_pf',256]},'n2_ps']})
 r('destination',when_ranges={'n2_pf':[240,255]},allowed=[255])
 for k in('dp','pf','ps'):r(k,when_present=['n2_pgn'],required=True)
 r('data_bytes',when_present=['payload_bytes'],required=True,equal_parameter='payload_bytes',src=SS)
 r('data_bytes',{'packet_class':'SINGLE'},maximum=8,src=SS);r('packet_frames',{'packet_class':'SINGLE'},allowed=[1],src=SS)
 r('frame_bytes',{'packet_class':'SINGLE'},equal_parameter='n2_data_bytes',src=SS)
 r('data_bytes',{'packet_class':'FAST_PACKET'},maximum=223,src=MSG)
 r('packet_frames',{'packet_class':'FAST_PACKET'},equal_expression={'sum':[1,{'ceiling':[{'product':[{'maximum':[0,{'subtract':['n2_data_bytes',6]}]},1/7]}]}]})
 r('frame_bytes',{'packet_class':'FAST_PACKET'},allowed=[8]);r('fast_frame_index',{'packet_class':'FAST_PACKET'},exclusive_maximum_expression='n2_packet_frames')
 r('fast_header',{'packet_class':'FAST_PACKET'},equal_expression={'sum':[{'product':['n2_fast_sequence',32]},'n2_fast_frame_index']})
 for k in('fast_sequence','fast_frame_index'):r(k,when_present=['n2_fast_header'],required=True)
 for klass in('ISO_TP_BAM','ISO_TP_RTS_CTS'):
  w={'packet_class':klass};r('data_bytes',w,minimum=9,maximum=1785,src=SS)
  r('packet_frames',w,equal_expression={'ceiling':[{'product':['n2_data_bytes',1/7]}]},src=SS)
  r('data_bytes',{**w,'implementation':'TIMO_PINNED'},maximum=223,src=MSG)
 r('destination',{'packet_class':'ISO_TP_BAM'},allowed=[255],src=SS)
 r('destination',{'packet_class':'ISO_TP_RTS_CTS'},maximum=253,src=SS)
 r('tp_packet_sequence',maximum_parameter='n2_packet_frames',src=SS)
 r('message_buffer_bytes',{'implementation':'TIMO_PINNED'},maximum=223,src=MSG)
 for k in('cable','physical_source'):r(k,when_present=['n2_backbone_m'],required=True,src=GUIDE)
 for k in('registered_source',):
  r(k,{'cable':'REGISTERED'},required=True,src=GUIDE)
  r(k,{'cable_catalog':'REGISTERED'},required=True,src=GUIDE)
 r('cable_catalog',when_present=['n2_branch_current_a'],required=True,src=GUIDE)
 r('power_profile',when_present=['n2_device_v'],required=True,src=GUIDE)
 for cable,limit in [('MICRO_LITE',100),('MID',250),('MINI_HEAVY',250)]:r('backbone_m',{'cable':cable},maximum=limit,src=GUIDE)
 for cable,amp in [('MICRO_LITE',3),('MID',4),('MINI_HEAVY',8)]:
  r('branch_current_a',{'cable':cable,'cable_catalog':'ACTISENSE_2021'},maximum=amp,src=GUIDE)
 r('power_feed_v',{'power_profile':'STANDARD_9_16'},minimum=9,maximum=16,src=GUIDE)
 r('device_v',{'power_profile':'STANDARD_9_16'},minimum=9,maximum=16,src=GUIDE)
 for k in('registered_source','extended_power_warning'):r(k,{'power_profile':'DEVICE_24V_REGISTERED'},required=True,src=GUIDE)
 r('extended_power_warning',{'power_profile':'DEVICE_24V_REGISTERED'},allowed=[True],src=GUIDE)
 r('device_v',equal_expression={'subtract':['n2_power_feed_v',{'product':['n2_loop_ohm','n2_branch_current_a']}]},src=GUIDE)
 for k in('power_feed_v','loop_ohm','branch_current_a','power_source'):r(k,when_present=['n2_device_v'],required=True,src=GUIDE)
 r('device_bus_current_ma',maximum_expression={'product':['n2_len',50]},src=GUIDE)
 r('len',{'power_method':'BUS_ONLY'},maximum=20,src=GUIDE)
 r('len',when_present=['n2_device_bus_current_ma'],required=True,src=GUIDE)
 r('certification_source',{'certified':True},required=True,src=P)
 r('physical_source',{'isolated_io':True},required=True,src=WC)
 r('age_ms',maximum_parameter='n2_freshness_limit_ms',src=WC)
 for k in('freshness_limit_ms','acceptance_source'):r(k,when_present=['n2_age_ms'],required=True,src=WC)
 r('sample_point_percent',{'implementation':'SIMMA_1_3'},maximum=87.5,src=SS)
 r('tick_ms',{'implementation':'SIMMA_1_3'},exclusive_minimum=0,maximum=25,src=SS)
 return dict(rate_model={'type':'FIXED_LINK_RATE','fields':['bitrate_bps'],'fixed_bps':250000},required_parameters=['bitrate_bps',*['n2_'+k for k in REQUIRED]],
  native_parameter_prefixes=['n2_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',
  physical_layer_profile_id='nmea2000_can_cc_250k_qualified_topology',medium_access_model='CAN_CC_PRIORITY_ARBITRATION_WITH_ERROR_RETRY',
  arbitration_model_id='NMEA2000_PGN_IDENTIFIER_PRIORITY_AND_ACTUAL_RETRY_BOUNDS',
  mechanisms={'framing':['CLASSIC_CAN_EXTENDED_29','SINGLE_FAST_PACKET_REGISTERED_PGN_ISO_TP'],
   'addressing':['ACTUAL_UNIQUE_64BIT_NAME_ADDRESS_CLAIM','ACTUAL_PGN_TX_RX_CODEC'],
   'physical':['QUALIFIED_BACKBONE_DROP_TERMINATION_POWER_ISOLATION'],
   'qualification':['NO_GENERIC_J1939_OR_ETHERNET_PARAMETER_FALLBACK','CERTIFICATION_INTEROPERABILITY_AND_E2E_SEPARATE']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][3:];item={key:value for key,value in spec.items()if value is not None}
  item.update(label=k.replace('_',' '),category='communication',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  defaults=[]
  if k in('id_bits','fd','brs','edp','built_in_termination'):
   defaults=[dict(when={'n2_role':'ACTIVE'},value={'id_bits':29,'fd':False,'brs':False,'edp':0,'built_in_termination':False}[k],source=LIB,source_revision=SOURCES[LIB])]
  if k=='automatic_retransmission':defaults=[dict(when={'n2_role':'ACTIVE'},value=True,source=WC,source_revision=SOURCES[WC])]
  if k in('heartbeat_ms','reassembly_ms'):defaults=[dict(when={'n2_implementation':'TIMO_PINNED'},value=60000 if k=='heartbeat_ms' else 100,source=HDR,source_revision=SOURCES[HDR])]
  simma=dict(tick_ms=10,bip_percent=25,bip_window_ms=250,tp_rx_buffers=10,tp_tx_buffers=3,tp_rx_bytes=128,tp_tx_bytes=128,fp_rx_bytes=128,sample_point_percent=87.5)
  if k in simma:defaults=[dict(when={'n2_implementation':'SIMMA_1_3'},value=simma[k],source=SS,source_revision=SOURCES[SS])]
  if defaults:item.update(conditional_defaults=defaults,default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
  result.append(item)
 return result
