"""Wireless V1.1.3: radio packet/track scheduling is independent from wired COM."""
SPEC='https://io-link.com/fileadmin/user_upload/Downloads/Package_2024/IOLW-Spec_V1.1.3Jun23_Corrigendum_1.pdf'
SOURCES={SPEC:'IO-Link Wireless V1.1.3 June2023 Corrigendum document status2023-07-25, publisher download SHA manifest; chapters4/5/AnnexA,B,C,H reviewed',
 'https://io-link.com/downloads':'Publisher current released Wireless1.1.3 versus2026 review draft1.1.4 accessed2026-10-01'}
SYNCWORDS=['3E9459','B3A314','1A2DEE','94A3DB','9C92E8','38D2EE','D8C6A9','91B5E3','2DA313','69D139',
 'D8721D','91DBE2','E95C13','C7A614','446B63','A772D2','314DED','963915','685D72','C6742B','38B715',
 'C92917','8D1C4B','DC9A5C','49DC5C','925D73','6CDC2D','A79C2D','68A373','A47317']
DECLARATIONS=[]


def d(key,kind,meaning,unit=None,options=None,minimum=None,maximum=None,**extra):
    DECLARATIONS.append(dict(key='iolw_'+key,type=kind,description=meaning,source=SPEC,source_revision=SOURCES[SPEC],
        unit=unit,options=options,min=minimum,max=maximum,**extra))


d('specification','select','Explicit reviewed wireless edition/corrigendum; draft1.1.4 and wired1.1.5 are distinct.',options=['V1_1_3_CORR1'],default='V1_1_3_CORR1')
d('role','select','Actual W-Master/W-Device/W-Bridge; bridge wired port requires separately registered COM/device evidence.',options=['W_MASTER','W_DEVICE','W_BRIDGE'])
d('mode','select','Actual cyclic configuration mode; ServiceMode scan/pairing uses reserved configuration channels.',options=['CYCLIC','SERVICE_SCAN','SERVICE_PAIRING'])
d('direction','select','Actual radio packet direction; downlink multicast and assigned-slot uplink are distinct.',options=['DOWNLINK','UPLINK'])
d('packet_kind','select','Actual pre/full downlink versus single/double uplink or configuration packet.',options=['PRE_DOWNLINK','FULL_DOWNLINK','UPLINK_SSLOT','UPLINK_DSLOT','CONFIG_DOWNLINK','CONFIG_UPLINK'])
d('slot_type','select','Actual assigned uplink width; DSlot starts at even position and consumes two slots.',options=['SSLOT','DSLOT'])
d('device_mode','select','Actual Normal/Roaming/LowEnergy behavior, persistence and ISDU/receiver restrictions.',options=['NORMAL','ROAMING','LOW_ENERGY'])
d('hopping_table','select','Actual HT01/approved update; orthogonality and blocklists require selected master evidence.',options=['HT01'],default='HT01')
d('data_syncword','select','Actual Table5 octets in transmit-buffer order, not reversed on-air numeric display.',options=SYNCWORDS,default='3E9459')
d('config_syncword','select','Specified configuration syncword transmit-buffer octet order.',options=['3E9459'],default='3E9459')
d('modulation','select','Binary GFSK, no inherited wired8E1 framing or Bluetooth application parameters.',options=['GFSK'],default='GFSK')
d('application_cycle_mode','select','Actual WCycleTime FreeRunning versus5ms-multiplier application release, independent from1664us subcycle.',options=['FREE_RUNNING','MULTIPLIER_5MS'])
d('crc32_initial_rule','select','Actual common initial state for configuration/downlink versus device-distinguishing-ID XOR for cyclic uplink.',options=['COMMON_FFFFFFFF','XOR_DEVICE_DISTINGUISHER'])
d('crc_order','select','CRC result most-significant bit first, input octets/data differ.',options=['MSB_FIRST'],default='MSB_FIRST')
d('data_bit_order','select','Data octets over air least-significant bit first, CRC result is different.',options=['LSB_FIRST'],default='LSB_FIRST')
d('power_encoding','select','Actual vendor power-level mapping versus normative fallback mapping; requested level is corrected to radio-supported value.',options=['VENDOR_DEFINED','SPEC_FALLBACK'])
for key,meaning in [('device_source','Actual firmware, radio capabilities, identities and device-specific limits.'),
 ('master_source','Actual selected W-Master/track allocation and configuration.'),('iodd_source','Actual W-Device/IODD/bridge parameter and data description.'),
 ('binding_source','Actual canonical W-Port, slot/track and wireless cell binding.'),('radio_source','Actual carrier/antenna/sensitivity/power/region/PHY limits.'),
 ('hopping_source','Actual orthogonal HT01 tables/blocklist/hash/update and coexistence evidence.'),('encoding_source','Actual W-Message/packet/control/CRC/whitening/segmentation layout.'),
 ('schedule_source','Actual radio slots/retries/IMA/application release and upper-path schedule.'),('acceptance_source','Actual complete functional freshness/quality/safety/E2E acceptance.'),
 ('power_source','Actual supported corrected radio power mapping and EIRP/antenna/region evidence.'),('crc_source','Actual CRC initial state, identity XOR, coverage, bit order, residue and golden vectors.'),
 ('capacity_source','Actual RF channel/link budget/error independence/coexistence and full schedule evidence.'),
 ('wired_binding','Actual independent wired IO-Link port/COM/IODD path for W-Bridge.'),('unique_id','Actual8-octet unique device identity, no factory identity0.')]:d(key,'text',meaning)
d('blocklist','text','Actual normalized NIS channel1..80 left-to-right bit string; channel2/79 blocked, configuration channels excluded separately.',pattern=r'[01]{80}')
for key,meaning,minimum,maximum,unit in [
 ('bitrate_bps','Specified gross1M radio bitrate, not per-track application throughput.',1000000,1000000,'bit/s'),
 ('bit_time_us','Specified1us radio bit time.',1,1,'us'),('protocol_revision','Specified wireless RevisionID0x11, independent from wired revision.',17,17,None),
 ('master_id','Actual assigned cyclic master ID1..29; no automatically assigned project ID1.',1,29,None),
 ('track_index','Actual assigned track number0..4.',0,4,None),('track_count','Actual enabled radio tracks, not universal5.',1,5,None),
 ('slot_index','Actual0..7 slot position; DSlots consume even+next.',0,7,None),
 ('single_slots','Actual occupied SSlots in selected track.',0,8,None),('double_slots','Actual occupied DSlots in selected track.',0,4,None),
 ('track_devices','Actual selected track device count, not occupied slot count.',0,8,None),('total_devices','Actual whole master devices, max40 only all-SSlot5-track layout.',0,40,None),
 ('frequency_channel','Actual channel3..78 cyclic versus1/80 configuration.',1,80,None),('carrier_mhz','Actual carrier2400+channel in own hopping sequence.',2401,2480,'MHz'),
 ('track_spacing_mhz','Actual simultaneous-track separation at least3MHz.',3,None,'MHz'),
 ('carrier_error_ppm','Actual frequency offset, not generic CAN oscillator tolerance.',-20,20,'ppm'),
 ('gfsk_bt','Specified Gaussian filter bandwidth-bit product0.5.',.5,.5,None),('modulation_index','Nominal0.5 with own allowed tolerance0.45..0.55.',.45,.55,None),
 ('tx_eirp_dbm','Actual radiated power including antenna;10dBm ceiling is not a default operating power.',None,10,'dBm'),
 ('tx_power_level','Actual corrected encoded power level; no unconditional max31 default.',1,31,None),
 ('tx_nominal_dbm','Actual nominal transceiver mapping, not EIRP without antenna/cable evidence.',None,None,'dBm'),
 ('receiver_sensitivity_dbm','Actual verified receiver sensitivity at specified error-test condition.',None,-94,'dBm'),
 ('range_m','Actual verified coverage, not a fixed10/20m deployment guarantee.',0,None,'m'),
 ('subcycle_us','Specified W-Sub-cycle1664us; not a full5ms application cycle.',1664,1664,'us'),
 ('control_interval_us','Specified frequency/radio control interval208us.',208,208,'us'),('downlink_interval_us','Specified full downlink416us.',416,416,'us'),
 ('uplink_interval_us','Specified all-uplink window832us.',832,832,'us'),('guard_us','Specified interslot guard8us, not extra per-payload UART bits.',8,8,'us'),
 ('slot_tx_us','Actual SSlot96us versus DSlot200us excluding guard.',0,None,'us'),
 ('slot_with_guard_us','Actual selected transmission+guard104/208us.',0,None,'us'),
 ('max_retry','Specified adjustable retry count2..31, default2; attempts include primary.',2,31,None),
 ('minimum_retry_window_ms','Actual retry subcycle window; not the application nominal5ms encoding.',0,None,'ms'),
 ('ima_time_ms','Actual device/master I-am-alive bound, own configured min/max required.',0,600000,'ms'),
 ('device_ima_min_ms','Actual advertised device minimum IMA.',0,600000,'ms'),('device_ima_max_ms','Actual advertised device maximum IMA.',0,600000,'ms'),
 ('ima_time_base','Actual IMA base1..4,0 reserved;5ms shorthand has3subcycles.',1,4,None),('ima_multiplier','Actual IMA multiplier1..255.',1,255,None),
 ('ima_subcycles','Actual encoded IMA in subcycles, distinct from nominal ms shorthand.',1,None,None),
 ('application_multiplier','Actual WCycleTime6-bit multiplier1..63 when enabled.',1,63,None),
 ('application_cycle_ms','Actual nominal5ms multiplier1..63, FreeRunning is not0ms release.',5,315,'ms'),
 ('application_subcycles','Actual WCycleTime3subcycles per5ms nominal unit.',3,189,None),
 ('device_min_input_cycle_ms','Actual W-Device minimum input application cycle.',0,None,'ms'),('device_min_output_cycle_ms','Actual W-Device minimum output cycle.',0,None,'ms'),
 ('preamble_octets','Specified two-octet preamble, not wired UART start/stop.',2,2,'Byte'),('syncword_octets','Specified3-octet synchronization word.',3,3,'Byte'),
 ('pre_crc_bits','Specified16bit pre-downlink integrity.',16,16,'bit'),('full_crc_bits','Specified32bit full DL/UL integrity.',32,32,'bit'),
 ('crc16_polynomial','Specified0x1021 polynomial, bit ordering checked separately.',4129,4129,None),('crc32_polynomial','Specified0x04C11DB7 polynomial, not reflected numeric default.',79764919,79764919,None),
 ('crc16_initial','Specified0xFFFF initial state.',65535,65535,None),('crc16_final_xor','Specified0 final XOR.',0,0,None),
 ('crc32_initial_value','Actual initial state after relevant device identity salt for cyclic UL.',0,4294967295,None),
 ('crc32_final_xor','Specified0xFFFFFFFF final XOR; device identity is separate.',4294967295,4294967295,None),
 ('device_distinguisher','Actual32bit Device Distinguishing ID, not substituted master/node address.',0,4294967295,None),
 ('packet_octets','Actual entire on-air packet, excluding guard.',0,None,'Byte'),('packet_payload_octets','Actual packet payload incl W-Message controls, not application PD.',0,None,'Byte'),
 ('uplink_user_octets','Actual single-slot1 or double-slot14 W-Message user bytes; whole PD32 can require segmentation.',0,None,'Byte'),
 ('pd_input_octets','Actual whole W-Device input PD up to32, distinct from per-slot payload.',0,32,'Byte'),('pd_output_octets','Actual whole W-Device output PD up to32.',0,32,'Byte'),
 ('isdu_record_octets','Actual indexed ISDU data, independent from slot/packet capacities.',0,232,'Byte'),
 ('isdu_total_octets','Actual full encoded ISDU through wireless On-Request service.',0,238,'Byte'),
 ('scan_timeout_ms','Configured scan ServiceMode timeout; publisher5000 proposal is role-scoped.',0,None,'ms'),
 ('unique_pair_timeout_ms','Actual unique-ID pairing timeout; W-Master5s versus W-Device200ms.',0,None,'ms'),
 ('button_pair_timeout_ms','Actual button pairing timeout; W-Master at least5s, Device200ms.',0,None,'ms'),
 ('upper_path_ms','Actual upper fieldbus/host/network delay, no automatic Ethernet/CAN estimate.',0,None,'ms'),
 ('functional_bound_ms','Actual full sensor-controller-actuator E2E deadline.',0,None,'ms')]:d(key,'number',meaning,minimum=minimum,maximum=maximum,unit=unit)
for key in ('pd_valid','isdu_supported','paired','crc_confirmed','rf_confirmed','schedule_confirmed'):
    d(key,'boolean','Actual '+key+' status/capability/confirmation; literature alone cannot confirm deployment.')

REMOVED={key:'Removed inherited '+key+': Wireless radio MAC/track/slot/CRC/retry/IMA profiles have their own settings; no wired COM/UART, CAN queue or generic gateway defaults.'for key in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['specification','role','mode','direction','packet_kind','device_mode','bitrate_bps','device_source','master_source','iodd_source',
 'binding_source','radio_source','hopping_source','encoding_source','schedule_source','acceptance_source','power_source','crc_source','capacity_source']


def semantics():
    rules=[]
    def r(key,when=None,**kw):rules.append(dict(parameter='iolw_'+key,when={'iolw_'+k:v for k,v in (when or {}).items()},source=SPEC,source_revision=SOURCES[SPEC],**kw))
    for mode in ('SERVICE_SCAN','SERVICE_PAIRING'):
        r('frequency_channel',{'mode':mode},allowed=[1,80]);r('packet_kind',{'mode':mode},allowed=['CONFIG_DOWNLINK','CONFIG_UPLINK'])
        r('crc32_initial_rule',{'mode':mode},allowed=['COMMON_FFFFFFFF']);r('crc32_initial_value',{'mode':mode},allowed=[4294967295])
    r('frequency_channel',{'mode':'CYCLIC'},minimum=3,maximum=78)
    r('packet_kind',{'mode':'CYCLIC'},allowed=['PRE_DOWNLINK','FULL_DOWNLINK','UPLINK_SSLOT','UPLINK_DSLOT'])
    r('carrier_mhz',equal_expression={'sum':[2400,'iolw_frequency_channel']})
    r('track_index',maximum_expression={'subtract':['iolw_track_count',1]})
    r('track_devices',equal_expression={'sum':['iolw_single_slots','iolw_double_slots']})
    r('single_slots',maximum_expression={'subtract':[8,{'product':[2,'iolw_double_slots']}]})
    r('total_devices',maximum_expression={'product':[8,'iolw_track_count']})
    r('slot_index',{'slot_type':'DSLOT'},multiple_of=2,maximum=6)
    for slot,tx in [('SSLOT',96),('DSLOT',200)]:
        r('slot_tx_us',{'slot_type':slot},allowed=[tx]);r('slot_with_guard_us',{'slot_type':slot},allowed=[tx+8])
    r('minimum_retry_window_ms',equal_expression={'product':[1.664,{'sum':['iolw_max_retry',1]}]})
    r('ima_time_ms',minimum_expression={'product':[1.664,{'sum':['iolw_max_retry',1]}]},minimum_parameter='iolw_device_ima_min_ms',maximum_parameter='iolw_device_ima_max_ms')
    r('device_ima_min_ms',maximum_parameter='iolw_device_ima_max_ms')
    for base,time,cycles in [(1,1.664,1),(2,5,3),(3,1000,600),(4,60000,36000)]:
        r('ima_time_ms',{'ima_time_base':base},equal_expression={'product':[time,'iolw_ima_multiplier']})
        r('ima_subcycles',{'ima_time_base':base},equal_expression={'product':[cycles,'iolw_ima_multiplier']})
    r('application_cycle_ms',{'application_cycle_mode':'MULTIPLIER_5MS'},equal_expression={'product':[5,'iolw_application_multiplier']})
    r('application_subcycles',{'application_cycle_mode':'MULTIPLIER_5MS'},equal_expression={'product':[3,'iolw_application_multiplier']})
    r('application_cycle_ms',minimum_parameter='iolw_device_min_input_cycle_ms')
    r('application_cycle_ms',minimum_parameter='iolw_device_min_output_cycle_ms')
    for key in ('application_cycle_ms','application_subcycles','application_multiplier'):r(key,{'application_cycle_mode':'FREE_RUNNING'},allowed=[])
    for packet,slot,wire,payload,user in [('UPLINK_SSLOT','SSLOT',12,2,1),('UPLINK_DSLOT','DSLOT',25,15,14)]:
        when={'packet_kind':packet};r('direction',when,allowed=['UPLINK']);r('slot_type',when,allowed=[slot]);r('packet_octets',when,allowed=[wire]);r('packet_payload_octets',when,maximum=payload);r('uplink_user_octets',when,maximum=user)
        r('crc32_initial_rule',when,allowed=['XOR_DEVICE_DISTINGUISHER']);r('device_distinguisher',when,required=True)
    for packet in ('PRE_DOWNLINK','FULL_DOWNLINK','CONFIG_DOWNLINK'):
        r('direction',{'packet_kind':packet},allowed=['DOWNLINK'])
        r('crc32_initial_rule',{'packet_kind':packet},allowed=['COMMON_FFFFFFFF'])
    r('direction',{'packet_kind':'CONFIG_UPLINK'},allowed=['UPLINK'])
    r('crc32_initial_value',{'crc32_initial_rule':'COMMON_FFFFFFFF'},allowed=[4294967295])
    r('packet_octets',{'packet_kind':'FULL_DOWNLINK'},allowed=[52]);r('packet_payload_octets',{'packet_kind':'FULL_DOWNLINK'},maximum=37)
    r('packet_payload_octets',{'packet_kind':'PRE_DOWNLINK'},maximum=2)
    r('isdu_supported',allowed=[True])
    r('unique_id',pattern=r'[0-9A-Fa-f]{16}')
    r('blocklist',pattern=r'[01]1[01]{76}1[01]')
    r('wired_binding',{'role':'W_BRIDGE'},required=True)
    r('tx_nominal_dbm',{'power_encoding':'SPEC_FALLBACK'},equal_expression={'subtract':['iolw_tx_power_level',21]})
    # The printed Table186 contains an apparent Level30 hexadecimal typo; actual
    # supported mapping/correction is mandatory, never blindly equated to EIRP.
    r('button_pair_timeout_ms',{'role':'W_MASTER'},minimum=5000)
    return {'rate_model':{'type':'IO_LINK_WIRELESS_RADIO_TRACK_PROFILE','fields':[]},'required_parameters':['iolw_'+key for key in REQUIRED],
        'native_parameter_prefixes':['iolw_'],'parameter_constraints':rules,'mechanisms':{'framing':['PRE_FULL_DOWNLINK_AND_SSLOT_DSLOT_UPLINK'],
        'arbitration':['SYNCHRONIZED_FDMA_TDMA_HT01_BLOCKLIST'],'addressing':['ASSIGNED_MASTER_TRACK_SLOT_AND_UNIQUE_DEVICE'],
        'integrity':['CRC16_PREDOWNLINK_CRC32_FULL_AND_DISTINGUISHER_XOR'],'physical':['GFSK_1M_2401_TO_2480_ROLE_AND_REGION_PROOF'],
        'acceptance':['IMA_RETRIES_PD_VALID_SEPARATE_FROM_FUNCTIONAL_E2E']}}


def fields():
    result=[];required=set(semantics()['required_parameters'])
    fixed={'bitrate_bps':1000000,'bit_time_us':1,'protocol_revision':17,'subcycle_us':1664,'control_interval_us':208,
        'downlink_interval_us':416,'uplink_interval_us':832,'guard_us':8,'gfsk_bt':.5,'modulation_index':.5,
        'max_retry':2,'preamble_octets':2,'syncword_octets':3,'pre_crc_bits':16,'full_crc_bits':32,
        'crc16_polynomial':4129,'crc32_polynomial':79764919,'crc16_initial':65535,'crc16_final_xor':0,'crc32_final_xor':4294967295,'isdu_supported':True}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('iolw_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,integer=spec['type']=='number'and spec['unit']not in ('ms','us','m','MHz','ppm','dBm')and key not in('gfsk_bt','modulation_index'),
            parameter_origin='DEVICE_CONFIGURATION',default_status='PROPOSED_STANDARD'if'default'in item else'UNKNOWN',validation_relevant=True,simulation_relevant=False)
        if key in fixed:item.update(default=fixed[key],default_status='PROPOSED_STANDARD')
        if key in ('scan_timeout_ms','unique_pair_timeout_ms','button_pair_timeout_ms'):
            proposals=[]
            service_mode='SERVICE_SCAN'if key=='scan_timeout_ms'else'SERVICE_PAIRING'
            if key!='button_pair_timeout_ms':proposals.append({'when':{'iolw_role':'W_MASTER','iolw_mode':service_mode},'value':5000})
            if key!='scan_timeout_ms':proposals.extend({'when':{'iolw_role':role,'iolw_mode':service_mode},'value':200}for role in ('W_DEVICE','W_BRIDGE'))
            item.update(conditional_defaults=[{**v,'source':SPEC,'source_revision':SOURCES[SPEC]}for v in proposals],default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
