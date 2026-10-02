"""Explicit OBD application/vehicle transport/adapter host separation."""
ELM='https://www.elmelectronics.com/wp-content/uploads/2017/01/ELM327DS.pdf'
STN='https://www.obdsol.com/wp-content/uploads/stn2120-ds.pdf'
SAE='https://saemobilus.sae.org/standards/j1979-2_202604-e-e-diagnostic-test-modes-obdonuds'
SOURCES={ELM:'ELM327DSK ELM327v2.2 public95-page data sheet: protocol table26/37, serial8, headers39-42, ISO-TP45/61/62, pending46, timers27/53/70, electrical7. URL2017 is not the hardware edition.',
 STN:'STN2120DSA public25-page device sheet: UART theoretical62..8M actual hardware-dependent, operating3..3.6V/-40..85 versus absolute limits. Device discontinued per current OBD Solutions page.',
 SAE:'SAE publisher J1979-2_202604 OBDonUDS metadata retrieved2026-10-02; headerApril21 versus citation/revisionMay inconsistency retained. Full licensed service/DigitalAnnex text not read.'}
CAN=('CAN_11_250','CAN_29_250','CAN_11_500','CAN_29_500')
KLINE=('ISO9141_5BAUD','KWP_5BAUD','KWP_FAST')
RATES={'J1850_PWM':41600,'J1850_VPW':10400,**{t:10400 for t in KLINE},**{t:250000 if t.endswith('250') else 500000 for t in CAN}}
CODES={'J1850_PWM':1,'J1850_VPW':2,'ISO9141_5BAUD':3,'KWP_5BAUD':4,'KWP_FAST':5,'CAN_11_500':6,'CAN_29_500':7,'CAN_11_250':8,'CAN_29_250':9}
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,u=None,opts=None,src=ELM,integer=False):
 DECLARATIONS.append(dict(key='o_'+k,type=t,description=meaning,min=lo,max=hi,unit=u,options=opts,source=src,source_revision=SOURCES[src],integer=integer))
for k,meaning,opts,src in[
 ('application','Actual legacyJ1979/ISO15031 versus currentOBDonUDS services. Do not turn every OBD request intoUDS.',['LEGACY_J1979','OBDONUDS','REGISTERED'],SAE),
 ('implementation','Actual identified adapter/device and firmware, not clonedELM version banner only.',['ELM327_V2_2','STN2120','REGISTERED'],ELM),
 ('transport','Actual detected vehicle binding. Automatic search is not a concrete CAN/Ethernet selection.',['J1850_PWM','J1850_VPW',*KLINE,*CAN,'DOIP_UDS','REGISTERED'],ELM),
 ('addressing','Actual functional request toall relevantECUs versus addressedphysical ECU.',['FUNCTIONAL','PHYSICAL','REGISTERED'],ELM),
 ('init','Actual vehicle initialization method;5baud initiation isnot10400baud data phase.',['NONE','SLOW_5_BAUD','FAST','REGISTERED'],ELM),
 ('can_address_mode','Actual normal ISO-TP versus extra data-byteextendedaddress; 29bitIDdoesnot meanextendedaddress.',['NORMAL','EXTENDED','REGISTERED'],ELM),
 ('packet_type','Actual selectedclassicISO-TP single/first/consecutive/flowcontrol frame.',['SF','FF','CF','FC'],ELM),
 ('fc_mode','Actual ELM flowcontrol mode0automatic,1customID+data,2receivedID+customdata.',['AUTO','CUSTOM_ID_DATA','RECEIVED_ID_CUSTOM_DATA'],ELM),
 ('host','Actual PC-to-adapter UART orseparatelyqualifiedUSB/Bluetooth/IPwrapper. Notvehiclebus.',['UART','USB_SERIAL','BLUETOOTH_SERIAL','IP_SERIAL','REGISTERED'],ELM),
 ('host_baud_pin','Actual selectedELM factorypin6LOW9600/HIGHPP0C38400onlyifunchanged, otherwiseconfigured.',['LOW_FACTORY','HIGH_FACTORY','CONFIGURED'],ELM),
 ('outcome','Actual response outcome; NO_DATA/adapterpromptdoesnot proveECU service success.',['POSITIVE','NEGATIVE','PENDING','NO_DATA','UNKNOWN'],ELM),
]:d(k,'select',meaning,opts=opts,src=src)
for k,meaning,src in[
 ('device_source','Actual adapter silicon/firmware/driver andcurrentconfiguration evidence.',ELM),
 ('transport_source','Actual detectedvehicleprotocol/address/bitrate/initialization and lower-layer configuration.',ELM),
 ('service_source','Actual service/DigitalAnnexedition and supportedPID/DID/request-response encoding, not arbitrarymode22 manufacturerdata.',SAE),
 ('schedule_source','Actual testerqueries/allECUs/othertraffic/adapterbuffers/currentresponsebounds.',ELM),
 ('acceptance_source','Actual application timing/freshness/quality acceptance independentresponse/no-data timeout.',SAE),
 ('host_source','Actual adapter-PC UART settings/flowcontrol/driver/wrapper andservice bound.',ELM),
 ('registered_source','Actual alternate service/transport/adapter specification and revision.',SAE),
 ('request_hex','Actual encodedvehicle request bytes ascompletehex octets, not ASCIIATcommandlength.',ELM),
 ('response_hex','Actual complete decodedvehicle response, includes SID/status/payload before semanticcodec.',ELM),
 ('fc_hex','Actual configured flowcontrol data bytes, independent actual ID andextendedaddress byte.',ELM),
 ('wake_hex','Actual configured K-line wake header+data excluding adapter-addedchecksum.',ELM),
 ('filter_source','Actual responseECU IDs/masks/extendedreceiveaddress andexpectedECU count.',ELM),
 ('pending_source','Actual pendingECU/SID correlation and boundednumber/duration ofextensions.',ELM),
 ('physical_source','Actual transceiver/pins/connector/cable/voltage/load proof; chipVDDnotOBDconnectorbattery.',STN),
]:d(k,'text',meaning,src=src)
for k,meaning,lo,hi,u,src,integer in[
 ('protocol_code','Actual ELM detectedprotocol1..9,0search andA/B/CnonOBDextensions notconcrete standardbinding.',0,12,None,ELM,True),
 ('can_id_bits','Actual selectedCAN11or29 identifier, separateISO-TPextendedaddressbyte.',0,29,'bit',ELM,True),
 ('request_id','Actual vehicleCAN requestID, functional versusphysical selected independently.',0,536870911,None,ELM,True),
 ('response_id','Actual matchingECU CAN responseID, not requestIDplus8 inferredwithoutsource.',0,536870911,None,ELM,True),
 ('fc_id','Actual custom flowcontrolCAN identifier, requiredonlycustomIDmode.',0,536870911,None,ELM,True),
 ('target_address','Actual extendedaddress byte orKline target, not universaldefault04.',0,255,None,ELM,True),
 ('tester_address','Actual source/testerbyte, defaultF1qualifiedspecificELMconfiguration only.',0,255,None,ELM,True),
 ('can_frame_bytes','Actual classicISO15765-4 OBD frame8 including PCI/padding; no8byteapplicationdefault.',0,8,'byte',ELM,True),
 ('request_bytes','Actual service/PID encodedrequest length, separate3header/checksum/PCI/padding.',0,None,'byte',ELM,True),
 ('response_bytes','Actual complete reassembledservice response length, selected implementation bound.',0,None,'byte',ELM,True),
 ('address_bytes','Actual ISO-TP extraaddress0normal/1extended, not CANIDlength.',0,1,'byte',ELM,True),
 ('pci_bytes','Actual SF/CF1, FF2, FC3 protocol bytes separateextendedaddress andpadding.',1,3,'byte',ELM,True),
 ('frame_data_bytes','Actual service data carried bythis frame, not whole reassembledresponse.',0,7,'byte',ELM,True),
 ('padding_bytes','Actual reviewed classicframe padding afteraddress/PCI/data.',0,8,'byte',ELM,True),
 ('frame_sequence','Actual CF4bit sequence0..15 rollover, not fastpacket5bitindex.',0,15,None,ELM,True),
 ('fc_bytes','Actual configuredflowcontrol data bytecount, optionalextendedaddress included.',0,8,'byte',ELM,True),
 ('pid_count','Actual countofrequestedPIDs; selectedlegacyCAN supports<=6, otherlegacy pathsone.',0,None,None,ELM,True),
 ('service_id','Actual requestedSID/modeoctet; currentOBDonUDSserviceusesregisterededitioncodec.',0,255,None,SAE,True),
 ('response_service_id','Actual positivelegacy responseSID=request+0x40; negatives/pending differ.',0,255,None,ELM,True),
 ('negative_code','Actual negative response status,0x78pendingnot positiveor successfuldata.',0,255,None,ELM,True),
 ('expected_ecus','Actual responseECU count before optional earlyreturn; neverguess1forfunctionalbroadcast.',0,None,None,ELM,True),
 ('returned_ecus','Actual currentmatchingreplies, separate totalexpectedECUs.',0,None,None,ELM,True),
 ('st_count','Actual8bitATSTparameter;0restorePP03default ratherthanzeroms.',0,255,None,ELM,True),
 ('pp_st_count','ActualcurrentPP03basecount, not alwaysfactoryhex32(decimal50).',1,255,None,ELM,True),
 ('effective_st_count','Actualpositive effectiveSTcount after0restoresPP03.',1,255,None,ELM,True),
 ('timer_multiplier','Actual ELM CANCTM1orCTM5, not universalISOresponse multiplier.',1,5,None,ELM,True),
 ('timeout_ms','ActualselectedELM basecount*4.096ms*CTM, adaptivetimingmayusethevalueasceiling.',0,None,'ms',ELM,False),
 ('adaptive_mode','ActualELMAT0off/AT1normal/AT2aggressive, factory1deviceproposal.',0,2,None,ELM,True),
 ('pending_extension_ms','ActualELMv2.1+ pending waitnominal5000 permessage, not finiteE2E bound.',0,None,'ms',ELM,False),
 ('pending_count','Actual pendingmessages fromcorrelatedECU, no universalretry3.',0,None,None,ELM,True),
 ('pending_budget_ms','Actualboundedapplicationbudget forpendingECUs, not inferredfromrate.',0,None,'ms',ELM,False),
 ('sw_count','Actual8bitSWperiodcount,0disablewake ratherthan restoretimerdefault.',0,255,None,ELM,True),
 ('wake_interval_ms','ActualELMKlineSWcount*20.48ms, nominal3sdefaulthex92=146steps.',0,None,'ms',ELM,False),
 ('wake_bytes','Actualwakeheader+data1..6whenconfigured, excludingaddedchecksum.',0,6,'byte',ELM,True),
 ('slow_init_baud','Actual5baud initializationphase; separate10400baud vehicledata.',5,5,'bit/s',ELM,True),
 ('host_baud','Actual adapterhostUART rate, neverCAN250k orKline10400inferred.',1,None,'bit/s',ELM,False),
 ('host_data_bits','ActualELMhost8databits, separatevehicletelegram.',8,8,'bit',ELM,True),
 ('host_stop_bits','ActualELMhost1stopbit.',1,1,'bit',ELM,True),
 ('host_parity_bits','ActualELMhost0paritybits.',0,0,'bit',ELM,True),
 ('host_wire_bits','Actualhost1start+8data+1stop=10bitsperASCIIcharacter.',10,10,'bit',ELM,True),
 ('chip_vdd_v','ActualinterpreterICrail, separateOBDconnectorbattery/transceivervoltage.',0,None,'V',STN,False),
 ('ambient_c','Actualqualifiedchipoperatingambient, not absolutestorage/stress capability.',None,None,'C',STN,False),
 ('age_ms','Actualreceiveddata age relevantapplicationdeadline.',0,None,'ms',SAE,False),
 ('freshness_limit_ms','Actualapplication freshness/deadline, not adapterdefaulttimeout.',0,None,'ms',SAE,False),
]:d(k,'number',meaning,lo,hi,u,src=src,integer=integer)
for k,meaning in[
 ('auto_search','Actual allowedadaptersearchonfailure; currentdetectedbusstillmandatory.'),
 ('allow_long','ActualELM AllowLong permits8byte sends versusnormal7. Longreceives still constrained byselectedCAN12bit descriptor.'),
 ('auto_format','ActualELMCAF1insertsPCI/removesPCIforhost, CAF0requiresrawbytes.'),
 ('auto_flow_control','ActualCFC1emitsflowcontrol onlyselectedISO15765format.'),
 ('variable_dlc','ActualexperimentalELMV1 variableDLC outsideclassicOBD8bytebinding.'),
 ('fd','ActualclassicELM reviewedbindingfalse; newerCANFDrequiresownregisteredtransport.'),
 ('brs','ActualclassicELMbindingfalse, separatehostUARTspeed.'),
 ('early_return','Actualrequesttrailinghexresponsecount, requiresknownmatchingECUcount.'),
 ('pending_supported','Actual selectedELMv2.2pending support, not everycloned/olderadapter.'),
 ('wake_enabled','ActualperiodicKlineidlemessage enable; not availableonELMCAN.'),
 ('data_accepted','Actualrequesttoacceptparseddata requirespositiveandcodec/freshness source.'),
]:d(k,'boolean',meaning)
REQUIRED=('application','implementation','transport','device_source','transport_source','service_source','schedule_source','acceptance_source','host_source')
REMOVED={k:'No universal OBD-II '+k+'; actual selectedvehicleprotocol/service/adapter configuration replaces foreign CAN/Ethernet defaults.'for k in('mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','retry_limit','retransmission_enabled','retransmission_rate','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms','sync_method')}
def semantics():
 rules=[]
 def r(k,w=None,src=ELM,**kw):
  rules.append(dict(parameter=k if k in('payload_bytes','bitrate_bps','local_timing_evidence')else'o_'+k,when={'o_'+key:value for key,value in(w or{}).items()},source=src,source_revision=SOURCES[src],**kw))
 for k in REQUIRED:r(k,required=True)
 r('local_timing_evidence',allowed=[])
 for k,v in RATES.items():r('bitrate_bps',{'transport':k},allowed=[v],required=True)
 for k in('DOIP_UDS','REGISTERED'):
  r('bitrate_bps',{'transport':k},allowed=[]);r('registered_source',{'transport':k},required=True,src=SAE)
 r('application',{'transport':'DOIP_UDS'},allowed=['OBDONUDS','REGISTERED'],src=SAE)
 for k in('application','implementation'):
  r('registered_source',{k:'REGISTERED'},required=True,src=SAE)
 r('registered_source',{'application':'OBDONUDS'},required=True,src=SAE)
 r('application',{'implementation':'ELM327_V2_2'},allowed=['LEGACY_J1979','REGISTERED'],src=ELM)
 for t,code in CODES.items():r('protocol_code',{'transport':t,'implementation':'ELM327_V2_2'},allowed=[code])
 for t in RATES:
  r('init',{'transport':t},allowed=['SLOW_5_BAUD'if t in('ISO9141_5BAUD','KWP_5BAUD')else'FAST'if t=='KWP_FAST'else'NONE'])
 for t in CAN:
  w={'transport':t};bits=11 if '_11_'in t else 29
  r('can_id_bits',w,allowed=[bits]);r('can_frame_bytes',w,allowed=[8]);r('fd',w,allowed=[False]);r('brs',w,allowed=[False])
  r('variable_dlc',{**w,'application':'LEGACY_J1979'},allowed=[False])
  for k in('request_id','response_id','fc_id'):r(k,w,maximum=2047 if bits==11 else 536870911)
  r('request_id',{**w,'addressing':'FUNCTIONAL','application':'LEGACY_J1979'},allowed=[0x7df if bits==11 else 0x18db33f1])
  r('pid_count',{**w,'application':'LEGACY_J1979'},maximum=6)
  r('wake_enabled',{**w,'implementation':'ELM327_V2_2'},allowed=[False])
 for t in('J1850_PWM','J1850_VPW',*KLINE,'DOIP_UDS'):
  w={'transport':t}
  for k in('can_id_bits','request_id','response_id','can_frame_bytes','packet_type','frame_sequence','pci_bytes','fc_mode','fd','brs'):
   r(k,w,allowed=[])
  if t!='DOIP_UDS':r('pid_count',{**w,'application':'LEGACY_J1979'},maximum=1)
 for t in('ISO9141_5BAUD','KWP_5BAUD'):r('slow_init_baud',{'transport':t},allowed=[5])
 r('request_hex',pattern=r'(?:[0-9A-Fa-f]{2})+',hex_bytes_parameter='o_request_bytes',hex_octets=[dict(offset=0,width=1,parameter='o_service_id')])
 r('response_hex',pattern=r'(?:[0-9A-Fa-f]{2})+',hex_bytes_parameter='o_response_bytes')
 r('fc_hex',pattern=r'(?:[0-9A-Fa-f]{2})+',hex_bytes_parameter='o_fc_bytes')
 r('wake_hex',pattern=r'(?:[0-9A-Fa-f]{2})+',hex_bytes_parameter='o_wake_bytes')
 for text,count in [('request_hex','request_bytes'),('response_hex','response_bytes'),('fc_hex','fc_bytes'),('wake_hex','wake_bytes')]:r(count,when_present=['o_'+text],required=True)
 for mode,address_bytes in [('NORMAL',0),('EXTENDED',1)]:r('address_bytes',{'can_address_mode':mode},allowed=[address_bytes])
 for kind,pci in [('SF',1),('FF',2),('CF',1),('FC',3)]:r('pci_bytes',{'packet_type':kind},allowed=[pci])
 r('can_frame_bytes',equal_expression={'sum':['o_address_bytes','o_pci_bytes','o_frame_data_bytes','o_padding_bytes']})
 r('frame_data_bytes',maximum_expression={'subtract':[8,{'sum':['o_address_bytes','o_pci_bytes']}]})
 for k in('target_address','tester_address'):r(k,{'can_address_mode':'EXTENDED'},required=True)
 r('fc_id',{'fc_mode':'CUSTOM_ID_DATA'},required=True);r('fc_hex',{'fc_mode':'CUSTOM_ID_DATA'},required=True)
 r('fc_hex',{'fc_mode':'RECEIVED_ID_CUSTOM_DATA'},required=True)
 r('fc_id',{'fc_mode':'RECEIVED_ID_CUSTOM_DATA'},allowed=[])
 r('effective_st_count',{'st_count':0},equal_parameter='o_pp_st_count');r('pp_st_count',{'st_count':0},required=True)
 r('effective_st_count',when_positive=['o_st_count'],equal_parameter='o_st_count')
 r('timer_multiplier',allowed=[1,5]);r('timeout_ms',equal_expression={'product':['o_effective_st_count',4.096,'o_timer_multiplier']})
 for k in('effective_st_count','timer_multiplier'):r(k,when_present=['o_timeout_ms'],required=True)
 for t in('J1850_PWM','J1850_VPW',*KLINE):r('timer_multiplier',{'transport':t},allowed=[1])
 r('wake_interval_ms',equal_expression={'product':['o_sw_count',20.48]})
 r('wake_enabled',{'sw_count':0},allowed=[False]);r('wake_bytes',when_present=['o_wake_hex'],minimum=1)
 r('expected_ecus',{'early_return':True},required=True,minimum=1);r('filter_source',{'early_return':True},required=True)
 r('returned_ecus',maximum_parameter='o_expected_ecus');r('expected_ecus',when_present=['o_returned_ecus'],required=True)
 r('pending_source',{'outcome':'PENDING'},required=True);r('negative_code',{'outcome':'PENDING'},allowed=[0x78])
 r('pending_budget_ms',when_present=['o_pending_count'],required=True)
 r('response_service_id',{'outcome':'POSITIVE','application':'LEGACY_J1979'},equal_expression={'sum':['o_service_id',64]})
 r('response_hex',{'outcome':'POSITIVE'},hex_octets=[dict(offset=0,width=1,parameter='o_response_service_id')])
 r('outcome',{'data_accepted':True},allowed=['POSITIVE'],required=True)
 r('age_ms',maximum_parameter='o_freshness_limit_ms')
 r('freshness_limit_ms',when_present=['o_age_ms'],required=True,src=SAE)
 elm={'implementation':'ELM327_V2_2'}
 r('request_bytes',elm,maximum=8)
 r('request_bytes',{**elm,'allow_long':False},maximum=7)
 r('request_bytes',{**elm,'application':'LEGACY_J1979'},maximum=7)
 for t in CAN:r('response_bytes',{**elm,'transport':t},maximum=4095)
 r('fc_bytes',elm,minimum=1,maximum=5)
 r('pending_extension_ms',elm,allowed=[5000])
 for pin,baud in [('LOW_FACTORY',9600),('HIGH_FACTORY',38400)]:r('host_baud',{**elm,'host_baud_pin':pin},allowed=[baud])
 r('chip_vdd_v',elm,minimum=4.2,maximum=5.5)
 r('chip_vdd_v',{'implementation':'STN2120'},minimum=3,maximum=3.6,src=STN)
 r('ambient_c',{'implementation':'STN2120'},minimum=-40,maximum=85,src=STN)
 r('host_baud',{'implementation':'STN2120'},minimum=62,maximum=8000000,src=STN)
 r('physical_source',when_present=['o_chip_vdd_v'],required=True,src=STN)
 return dict(rate_model={'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'minimum_bps':1,'optional_fields_when':{'bitrate_bps':{'o_transport':['DOIP_UDS','REGISTERED']}}},
  required_parameters=['o_'+k for k in REQUIRED],native_parameter_prefixes=['o_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',
  physical_layer_profile_id='obd_actual_vehicle_binding_and_adapter_host',medium_access_model='SELECTED_VEHICLE_TRANSPORT_AND_TESTER_REQUEST_RESPONSE',arbitration_model_id='OBD_SELECTED_LOWER_LAYER_AND_ACTUAL_ECU_SERVICE',
  mechanisms={'framing':['LEGACY_MODE_PID_OR_REGISTERED_OBDONUDS_SERVICE','CLASSIC_ISOTP_NORMAL_OR_EXTENDED_ADDRESS','KLINE_J1850_DISTINCT_INITIALIZATION'],
   'qualification':['ACTUAL_DETECTED_TRANSPORT_NO_CAN_UDS_ETHERNET_FALLBACK','ADAPTER_TIMEOUT_HOST_RATE_SEPARATE_FROM_VEHICLE_E2E']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][2:];item={key:value for key,value in spec.items()if value is not None}
  item.update(label=k.replace('_',' '),category='communication',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  defaults=[]
  factory=dict(st_count=50,pp_st_count=50,timer_multiplier=1,adaptive_mode=1,pending_extension_ms=5000,auto_format=True,auto_flow_control=True,allow_long=False,variable_dlc=False,host_data_bits=8,host_stop_bits=1,host_parity_bits=0,host_wire_bits=10)
  if k in factory:defaults=[dict(when={'o_implementation':'ELM327_V2_2'},value=factory[k],source=ELM,source_revision=SOURCES[ELM])]
  if k=='wake_interval_ms':defaults=[dict(when={'o_implementation':'ELM327_V2_2','o_transport':t,'o_sw_count':146},value=2990.08,source=ELM,source_revision=SOURCES[ELM])for t in KLINE]
  if k=='protocol_code':defaults=[dict(when={'o_implementation':'ELM327_V2_2','o_transport':t},value=code,source=ELM,source_revision=SOURCES[ELM])for t,code in CODES.items()]
  if defaults:item.update(conditional_defaults=defaults,default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
  result.append(item)
 return result
