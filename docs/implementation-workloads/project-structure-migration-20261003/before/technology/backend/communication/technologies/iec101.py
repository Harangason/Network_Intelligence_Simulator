"""IEC101 FT1.2: explicit serial/ASDU bindings and pinned implementation proposals."""
GUIDE='https://raw.githubusercontent.com/mz-automation/lib60870/v2.3.2/user_guide.adoc'
BASE='https://raw.githubusercontent.com/mz-automation/lib60870/v2.3.2/lib60870-C/src/iec60870/'
MASTER=BASE+'cs101/cs101_master.c'
SLAVE=BASE+'cs101/cs101_slave.c'
ASDU=BASE+'cs101/cs101_asdu.c'
LINK=BASE+'link_layer/link_layer.c'
ABB='https://library.e.abb.com/public/e891a296f0af446b9f807ea7730b8e49/COM600_series_5.1_IEC_60870-5-101_Master_OPC_usm_756703_ENg.pdf'
SOURCES={GUIDE:'lib60870C pinnedv2.3.2 user guide labelledv2.3.0; serial9600/8E1 is an example, not universal default',
 MASTER:'lib60870C tagv2.3.2 master constructors and defaults',SLAVE:'lib60870C tagv2.3.2 slave constructors and defaults',
 ASDU:'lib60870C tagv2.3.2 ASDU header/VSQ/COT/addresses and sequence encoder',
 LINK:'lib60870C tagv2.3.2 FT1.2 fixed/variable/ack framing and checksum/state machines',
 ABB:'COM600series5.1 1MRS756703G 2018-03-06 sections3.4.2/3.4.3/6.1; vendor-qualified settings/interoperability'}
DECLARATIONS=[]
def d(key,kind,meaning,source=GUIDE,unit=None,options=None,minimum=None,maximum=None,**extra):
    DECLARATIONS.append(dict(key='iec101_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        unit=unit,options=options,min=minimum,max=maximum,**extra))
d('implementation','select','Actual implementation/revision, independently selected from industry.',options=['IEC_INTEROPERABILITY','LIB60870_C_2_3_2','ABB_COM600_5_1'])
d('configuration_phase','select','Actual configured profile versus explicit constructor/user-guide example proposals.',options=['CONFIGURED','LIB_FACTORY_DEFAULT','USER_GUIDE_EXAMPLE'])
d('role','select','Actual controlling/controlled station. Application role differs from primary/secondary link direction.',options=['CONTROLLING','CONTROLLED'])
d('link_mode','select','Balanced point-to-point peers versus unbalanced controlling station polling multiple addressed stations.',options=['BALANCED','UNBALANCED'])
d('physical','select','Actual serial realization; RS232/RS485/modem limits are not Ethernet link speeds.',options=['RS232','RS422','RS485','MODEM','VIRTUAL_SERIAL'])
for key,meaning in [('serial_binding','Actual canonical serial port/segment and all peers.'),('device_source','Actual device/firmware revision, serial and FT1.2 support.'),
 ('interoperability_source','Actual common agreement on link addressing, ASDU sizes/types/COT and encodings.'),
 ('physical_source','Actual transceiver/modem, wiring/termination, propagation, turnaround and serial clock bounds.'),
 ('schedule_source','Actual polling/class1/class2/retry/turnaround/response and command acceptance schedule.'),
 ('type_source','Actual ASDU type/quality/time/content interpretation; no invented payload encoding.'),
 ('command_source','Actual select/execute/cancel/ACT_CON/ACT_TERM and timeout acceptance, separate from link ACK.'),
 ('address_source','Actual link station, common ASDU and information-object address mapping, independently assigned.')]:
    d(key,'text',meaning)
d('baud_bps','number','Actual serial bit rate; ABB19200 is a device default, lib9600 is a user-guide example, neither a universal mode maximum.',unit='bit/s',minimum=1,source=ABB)
d('data_bits','number','Actual serial octet size, FT1.2 normal profile8 bits; other device settings need a separate proven encoding.',minimum=5,maximum=8,source=ABB)
d('parity','select','Actual parity; Even proposal for qualified profiles, not CAN CRC or arbitrary no-parity default.',options=['EVEN','ODD','NONE'],source=ABB)
d('stop_bits','number','Actual1/2 stop bits for configured serial port.',minimum=1,maximum=2,source=ABB)
d('character_bits','number','Actual start+data+optional parity+stop bits per character; not8 payload bits per wire byte.',minimum=7,maximum=12,source=ABB)
d('link_address_bytes','number','Actual FT1.2 link address length. Balanced interoperability can omit it; unbalanced needs1/2 bytes.',minimum=0,maximum=2,source=LINK)
for key in ('link_address','peer_link_address'):
    d(key,'number','Actual '+key+' in configured link-width; broadcast purpose explicit and never a station-default1.',minimum=0,maximum=65535,source=LINK)
d('address_purpose','select','Actual addressed station or broadcast; broadcast is all ones for configured address width.',options=['STATION','BROADCAST'],source=LINK)
d('balanced_dir','boolean','Actual balanced DIR bit; opposite peer directions required, unrelated to unbalanced PRM.',source=LINK)
d('peer_balanced_dir','boolean','Actual balanced peer DIR bit, not inferred from industry or device name.',source=LINK)
d('prm','boolean','Actual primary/secondary link function context.',source=LINK)
d('function_code','number','Actual4-bit FT1.2 function code; valid state/role-specific actions require link-layer evidence.',minimum=0,maximum=15,source=LINK)
d('frame_kind','select','Actual variable-data, fixed-control or single-character E5 ACK; each has different wire length.',options=['VARIABLE','FIXED','SINGLE_ACK'],source=LINK)
d('single_char_ack','boolean','Actual enabled single-character E5 acknowledgement for eligible responses; not application success.',source=MASTER)
d('length_l','number','Actual duplicated variable-length L: control+link address+ASDU bytes; one-byte ceiling255, not total-wire-byte ceiling255.',minimum=0,maximum=255,source=LINK,unit='Byte')
d('peer_length_limit','number','Actual peer accepted L limit, not Ethernet MTU. ABB documented230 is a device proposal.',minimum=1,maximum=255,source=ABB,unit='Byte')
d('wire_bytes','number','Actual full FT1.2 octets including length/start/checksum/stop; variableL+6, fixedaddress+4, singleACK1.',minimum=1,maximum=261,source=LINK,unit='Byte')
for key,upper in [('type_id_bytes',1),('vsq_bytes',1),('cot_bytes',2),('ca_bytes',2),('ioa_bytes',3)]:
    d(key,'number','Actual agreed '+key+' width; common address/COT/IOA differ and must match peers.',minimum=1,maximum=upper,source=ASDU,unit='Byte')
d('common_address','number','Actual ASDU common address, not link address or Ethernet endpoint.',minimum=0,maximum=65535,source=ASDU)
d('originator','number','Actual COT originator when COT2; absent for COT1, not confirmed constructor placeholder0.',minimum=0,maximum=255,source=ASDU)
d('first_ioa','number','Actual first information object address for its configured1/2/3 byte width.',minimum=0,maximum=16777215,source=ASDU)
d('type_id','number','Actual one-byte ASDU type identifier; private types require agreed content definition.',minimum=1,maximum=255,source=ASDU)
d('cot','number','Actual6-bit cause of transmission; test/negative flags are separate.',minimum=0,maximum=63,source=ASDU)
d('test','boolean','Actual ASDU test flag; not a silently disabled production requirement.',source=ASDU)
d('negative','boolean','Actual negative confirmation flag, not a bus transmission failure probability.',source=ASDU)
d('sequence','boolean','Actual SQ contiguous objects with one IOA versus individual-address objects.',source=ASDU)
d('object_count','number','Actual7-bit VSQ object count; consecutive SQ addresses must fit IOA width.',minimum=0,maximum=127,source=ASDU)
d('object_bytes','number','Actual encoded bytes per fixed-size object excluding IOA, including type-specific quality/time.',minimum=0,source=ASDU,unit='Byte')
d('objects_encoded_bytes','number','Actual full information-object encoding incl addresses; variable-size types require explicit encoded total.',minimum=0,source=ASDU,unit='Byte')
d('object_layout','select','Actual fixed-size objects versus variable/private content; no generic8-byte assumption.',options=['FIXED_OBJECT_SIZE','EXPLICIT_ENCODED'],source=ASDU)
d('asdu_bytes','number','Actual full ASDU header+encoded information objects, separate from FT1.2 L/wire size.',minimum=0,maximum=254,source=ASDU,unit='Byte')
d('asdu_limit','number','Actual peer/library ASDU limit; lib constructor249 is qualified, not universal255 payload.',minimum=1,maximum=254,source=MASTER,unit='Byte')
d('byte_order','select','IEC101 Mode1 least-significant octet first; explicit application float/text encodings remain type-specific.',options=['LITTLE_ENDIAN_MODE1'],source=ABB,default='LITTLE_ENDIAN_MODE1')
for key in ('ack_timeout_ms','repeat_timeout_ms','link_state_timeout_ms','idle_timeout_ms','poll_interval_ms',
            'class1_poll_bound_ms','class2_poll_bound_ms','turnaround_ms','cts_delay_ms','receiver_enable_delay_ms',
            'command_confirmation_ms','select_execute_ms'):
    d(key,'number','Actual '+key+' in its own link/poll/command scope; hardware-specific response/recovery evidence required.',minimum=0,source=MASTER if key in ('ack_timeout_ms','repeat_timeout_ms','link_state_timeout_ms','idle_timeout_ms') else ABB,unit='ms')
for key in ('class1_queue','class2_queue','retry_limit'):
    d(key,'number','Actual device/implementation '+key+' capacity or retry budget; no shared queue256 or guaranteed recovery.',minimum=0,source=SLAVE)
d('carrier_detect_required','boolean','Actual serial carrier gating; ABB balanced/unbalanced defaults differ.',source=ABB)
d('command_procedure','select','Actual direct execute versus select-before-operate with matching controlled-station acceptance.',options=['DIRECT_EXECUTE','SELECT_BEFORE_OPERATE'],source=GUIDE)
d('time_format','select','Actual ASDU time representation; short clock information is not a complete timestamp.',options=['NONE','CP24TIME2A','CP56TIME2A'],source=GUIDE)
d('time_source','text','Actual time-zone/clock-sync/hour-rollover/invalid-bit semantics and application freshness.',source=GUIDE)

REMOVED={key:'Removed inherited '+key+': IEC101 serial link/ASDU/polling needs explicit profile; no CAN/Ethernet queues/QoS/MTU/gateway default.'
 for key in ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method',
             'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms',
             'gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['implementation','role','link_mode','physical','serial_binding','device_source','interoperability_source','physical_source',
          'schedule_source','baud_bps','data_bits','parity','stop_bits','link_address_bytes','cot_bytes','ca_bytes','ioa_bytes']

def semantics():
    rules=[]
    def r(key,when=None,source=LINK,**kw):
        rules.append(dict(parameter='iec101_'+key,when={'iec101_'+k:v for k,v in (when or {}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('link_address_bytes',{'link_mode':'UNBALANCED'},allowed=[1,2])
    r('link_address_bytes',{'implementation':'LIB60870_C_2_3_2'},allowed=[1,2],source=MASTER)
    for key in ('balanced_dir','peer_balanced_dir'):r(key,{'link_mode':'BALANCED'},required=True)
    r('balanced_dir',{'link_mode':'BALANCED'},not_equal_parameter='iec101_peer_balanced_dir')
    for key in ('balanced_dir','peer_balanced_dir'):r(key,{'link_mode':'UNBALANCED'},allowed=[])
    for width in (0,1,2):
        for key in ('link_address','peer_link_address'):
            if width==0:r(key,{'link_address_bytes':0},allowed=[])
            else:r(key,{'link_address_bytes':width},maximum=2**(8*width)-1)
        if width:
            r('link_address',{'link_address_bytes':width,'address_purpose':'STATION'},maximum=2**(8*width)-2)
            r('link_address',{'link_address_bytes':width,'address_purpose':'BROADCAST'},allowed=[2**(8*width)-1])
    r('character_bits',{'parity':'NONE'},equal_expression={'sum':[1,'iec101_data_bits','iec101_stop_bits']},source=ABB)
    for parity in ('EVEN','ODD'):
        r('character_bits',{'parity':parity},equal_expression={'sum':[2,'iec101_data_bits','iec101_stop_bits']},source=ABB)
    r('wire_bytes',{'frame_kind':'VARIABLE'},equal_expression={'sum':[6,'iec101_length_l']})
    r('length_l',{'frame_kind':'VARIABLE'},equal_expression={'sum':[1,'iec101_link_address_bytes','iec101_asdu_bytes']})
    r('length_l',{'frame_kind':'VARIABLE'},maximum_parameter='iec101_peer_length_limit')
    r('wire_bytes',{'frame_kind':'FIXED'},equal_expression={'sum':[4,'iec101_link_address_bytes']})
    r('wire_bytes',{'frame_kind':'SINGLE_ACK'},allowed=[1])
    r('single_char_ack',{'frame_kind':'SINGLE_ACK'},required=True,allowed=[True])
    for kind in ('FIXED','SINGLE_ACK'):
        r('length_l',{'frame_kind':kind},allowed=[])
        r('asdu_bytes',{'frame_kind':kind},allowed=[0])
    for width in (1,2):
        r('common_address',{'ca_bytes':width},maximum=2**(8*width)-1,source=ASDU)
    r('originator',{'cot_bytes':1},allowed=[],source=ASDU)
    for width in (1,2,3):
        r('first_ioa',{'ioa_bytes':width},maximum=2**(8*width)-1,source=ASDU)
        r('first_ioa',{'ioa_bytes':width,'sequence':True},maximum_expression={'subtract':[2**(8*width),'iec101_object_count']},source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','object_count':0},allowed=[0],source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','sequence':True},when_positive=['iec101_object_count'],
      equal_expression={'sum':['iec101_ioa_bytes',{'product':['iec101_object_count','iec101_object_bytes']}]},source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','sequence':False},
      equal_expression={'product':['iec101_object_count',{'sum':['iec101_ioa_bytes','iec101_object_bytes']}]},source=ASDU)
    r('asdu_bytes',{'frame_kind':'VARIABLE'},equal_expression={'sum':[2,'iec101_cot_bytes','iec101_ca_bytes','iec101_objects_encoded_bytes']},source=ASDU)
    r('asdu_bytes',maximum_parameter='iec101_asdu_limit',source=ASDU)
    r('type_source',when_present=['iec101_type_id'],required=True,source=ASDU)
    for key in ('ack_timeout_ms','repeat_timeout_ms','link_state_timeout_ms','cts_delay_ms','receiver_enable_delay_ms'):
        r(key,{'implementation':'ABB_COM600_5_1'},maximum=65535,source=ABB)
    r('retry_limit',{'implementation':'ABB_COM600_5_1'},maximum=255,source=ABB)
    r('baud_bps',{'implementation':'ABB_COM600_5_1'},allowed=[300,600,1200,2400,4800,9600,19200,38400,56000,57600,115200,128000,256000],source=ABB)
    r('time_source',when_present=['iec101_time_format'],when_not={'iec101_time_format':'NONE'},required=True,source=GUIDE)
    r('command_source',{'command_procedure':'SELECT_BEFORE_OPERATE'},required=True,source=GUIDE)
    return {'rate_model':{'type':'IEC101_SERIAL_PROFILE','fields':[]},'required_parameters':['iec101_'+k for k in REQUIRED],
            'native_parameter_prefixes':['iec101_'],'parameter_constraints':rules,
            'mechanisms':{'framing':['FT1_2_FIXED_VARIABLE_E5'], 'integrity':['FT1_2_OCTET_SUM_AND_ACTUAL_SERIAL_PARITY'],
                'addressing':['LINK_ADDRESS_CA_IOA_SEPARATE'], 'arbitration':['BALANCED_PTP_OR_UNBALANCED_POLL'],
                'acceptance':['LINK_ACK_SEPARATE_FROM_ASDU_ACT_CON_ACT_TERM']}}

def fields():
    result=[];required=set(semantics()['required_parameters'])
    lib={'iec101_implementation':'LIB60870_C_2_3_2','iec101_configuration_phase':'LIB_FACTORY_DEFAULT'}
    lib_defaults={'type_id_bytes':1,'vsq_bytes':1,'cot_bytes':2,'ca_bytes':2,'ioa_bytes':3,'asdu_limit':249,
                  'link_address_bytes':1,'ack_timeout_ms':200,'repeat_timeout_ms':1000,'single_char_ack':True}
    abb={'iec101_implementation':'ABB_COM600_5_1'}
    abb_defaults={'baud_bps':19200,'data_bits':8,'parity':'EVEN','stop_bits':1,'cot_bytes':1,'ca_bytes':1,'ioa_bytes':2,
                  'link_address_bytes':1,'peer_length_limit':230,'ack_timeout_ms':2000,'retry_limit':3}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items() if v is not None};key=item['key'].removeprefix('iec101_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,integer=spec['type']=='number' and spec['unit']!='ms',parameter_origin='DEVICE_CONFIGURATION',
            default_status='PROPOSED_STANDARD' if 'default'in item else 'UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[]
        if key in lib_defaults:proposals.append({'when':lib,'value':lib_defaults[key],'source':MASTER,'source_revision':SOURCES[MASTER]})
        if key=='link_state_timeout_ms':proposals.append({'when':{**lib,'iec101_role':'CONTROLLING'},'value':5000,'source':MASTER})
        if key in abb_defaults:proposals.append({'when':abb,'value':abb_defaults[key],'source':ABB})
        if key=='baud_bps':proposals.append({'when':{'iec101_implementation':'LIB60870_C_2_3_2','iec101_configuration_phase':'USER_GUIDE_EXAMPLE'},'value':9600,'source':GUIDE})
        if key=='cts_delay_ms':
            proposals.extend({'when':{**abb,'iec101_link_mode':mode},'value':value,'source':ABB} for mode,value in [('BALANCED',50),('UNBALANCED',0)])
        if key=='carrier_detect_required':
            proposals.extend({'when':{**abb,'iec101_link_mode':mode},'value':value,'source':ABB} for mode,value in [('BALANCED',False),('UNBALANCED',True)])
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
