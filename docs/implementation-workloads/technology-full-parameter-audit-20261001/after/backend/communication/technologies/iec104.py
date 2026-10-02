"""IEC104 APCI/ASDU profiles, independently reviewed from serial IEC101."""
BASE='https://raw.githubusercontent.com/mz-automation/lib60870/v2.3.2/'
CLIENT=BASE+'lib60870-C/src/iec60870/cs104/cs104_connection.c'
SERVER=BASE+'lib60870-C/src/iec60870/cs104/cs104_slave.c'
GUIDE=BASE+'user_guide.adoc'
ASDU=BASE+'lib60870-C/src/iec60870/cs101/cs101_asdu.c'
COMMON=BASE+'lib60870-C/src/inc/api/iec60870_common.h'
ABB='https://library.e.abb.com/public/61bef3eada2edfb8c1257b130056cca1/COM600_3.5_IEC_60870-5-104_Master_OPC_usg_756704_ENc.pdf'
IANA='https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml?search=60870'
SOURCES={CLIENT:'lib60870C pinned tagv2.3.2 CS104 client/APCI defaults and frame/state counters',
 SERVER:'lib60870C pinned tagv2.3.2 CS104 server defaults, TLS port and redundancy queues',
 GUIDE:'lib60870C tagv2.3.2 user guide labelledv2.3.0 CS104 transport/ASDU/command/redundancy',
 ASDU:'lib60870C tagv2.3.2 shared application-layer ASDU encoder; IEC104 TCP framing remains independent',
 COMMON:'lib60870C tagv2.3.2 application/APCI parameter declarations and units',
 ABB:'COM6003.5 1MRS756704C 2011-06-30 sections3.4.3/3.4.4 and interoperability appendix pp69-70; vendor configuration versus baseline recommendations',
 IANA:'IANA IEC1042404 TCP/UDP registrations and secure19998TCP registration accessed2026-10-01; registration alone does not validate a UDP transport model'}
DECLARATIONS=[]


def d(key,kind,meaning,source=CLIENT,unit=None,options=None,minimum=None,maximum=None,**extra):
    DECLARATIONS.append(dict(key='iec104_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        unit=unit,options=options,min=minimum,max=maximum,**extra))


d('implementation','select','Actual device/library revision. Industry does not select protocol transport or timers.',options=['ACTUAL_DEVICE','LIB60870_C_2_3_2','ABB_COM600_3_5'])
d('parameter_profile','select','Baseline interoperability proposals versus actual configured device/factory profile; no overwriting confirmed settings.',options=['INTEROPERABILITY_BASELINE','CONFIGURED_DEVICE','FACTORY_PROFILE'],default='INTEROPERABILITY_BASELINE',source=ABB)
d('role','select','Actual controlling TCP client or controlled TCP listener; distinct from active/standby redundancy state.',options=['CONTROLLING','CONTROLLED'],source=GUIDE)
d('transport','select','Actual plain TCP versus TLS/TCP binding. No UDP path inferred merely from IANA registration.',options=['TCP','TLS_TCP'],source=GUIDE)
d('ip_version','select','Actual IPv4/IPv6 addressing of the bound TCP path.',options=['IPV4','IPV6'],source=GUIDE)
d('port','number','Actual remote/listening service port.2404 and19998 are transport-qualified proposals, not physical bit rates.',minimum=1,maximum=65535,source=IANA)
d('local_port','number','Actual local TCP port; ephemeral allocation must be represented by its policy, never guessed as the service port.',minimum=1,maximum=65535,source=GUIDE)
d('lib_int_bits','number','Actual C ABI signed-int width for the pinned library. Timer multiplication must fit before unsigned casts; no invented32-bit ABI.',minimum=16,maximum=64,source=COMMON)
d('abi_source','text','Actual compiler/target ABI evidence for lib60870 integer timer arithmetic.',source=COMMON)
for key,meaning in [('peer_endpoint','Actual configured remote hostname/IP and connection identity.'),
 ('local_endpoint','Actual local address/interface/listener binding, not loopback example.'),
 ('transport_binding','Actual registered lower-layer TCP/IP/physical path, each layer with its own technology profile.'),
 ('device_source','Actual device/library/firmware capabilities and accepted settings.'),
 ('interoperability_source','Actual shared ASDU sizes/types/addressing/security agreement with peers.'),
 ('physical_source','Actual underlying link/route/PHY/MTU/propagation facts; IEC104 has no universal Ethernet speed.'),
 ('schedule_source','Actual traffic/APCI windows/ACK/TCP recovery and redundancy schedule.'),
 ('type_source','Actual type-specific information object/quality/time/private ASDU encoding.'),
 ('address_source','Actual common address/originator/IOA assignment, not constructor0/1 examples.'),
 ('command_source','Actual direct/select/execute/cancel and ACT_CON/ACT_TERM acceptance; separate from TCP/APCI ACK.'),
 ('tls_source','Actual TLS security edition, negotiated version/ciphers/certificates/trust/authorization and record layout.'),
 ('redundancy_source','Actual approved redundancy groups, client assignments, active connection and event retention.'),
 ('time_source','Actual CP24/CP56 clock/time-zone/invalid/rollover/synchronization and freshness handling.')]:
    d(key,'text',meaning,source=GUIDE)
for key,meaning in [('k','Actual maximum outstanding I-format APDUs before APCI acknowledgment, not a generic Ethernet queue.'),
                    ('w','Actual latest acknowledgment after receiving this many I-format APDUs;2/3k is a recommendation, not a hard format bound.')]:
    d(key,'number',meaning,minimum=1,maximum=32767,source=ABB,unit='APDU')
for key,meaning in [('t0_ms','Connection establishment timeout, separate from reconnect interval.'),
 ('t1_ms','I-format/U-test acknowledgment timeout; not application command acceptance.'),
 ('t2_ms','Delayed I-format acknowledgment timeout, strictly less than t1.'),
 ('t3_ms','Idle link-test interval; disabling tests requires a device-qualified policy.')]:
    d(key,'number','Actual '+meaning+' Baseline and factory t0 differ.',minimum=0,source=ABB,unit='ms')
d('reconnect_ms','number','Actual connection retry interval, distinct from t0 and TCP retransmission.',minimum=0,source=ABB,unit='ms')
d('command_confirmation_ms','number','Actual application ACT_CON response bound, not t1.',minimum=0,source=ABB,unit='ms')
d('command_termination_ms','number','Actual application ACT_TERM bound when termination is required.',minimum=0,source=ABB,unit='ms')
d('termination_required','boolean','Actual application procedure expects ACT_TERM; omission needs peer/device evidence.',source=ABB)
d('parallel_commands','boolean','Actual allowed concurrent application commands, independent from APCI k window.',source=ABB)
d('format','select','Actual I-data, S-acknowledgment or U-control APCI format with own sequence/content rules.',options=['I','S','U'])
d('u_function','select','Actual STARTDT/STOPDT/TESTFR activation/confirmation, never equivalent to functional completion.',options=['STARTDT_ACT','STARTDT_CON','STOPDT_ACT','STOPDT_CON','TESTFR_ACT','TESTFR_CON'])
d('transfer_state','select','Actual stopped/starting/started/stopping connection data state.',options=['STOPPED','STARTING','STARTED','STOPPING'])
d('send_sequence','number','Actual15-bit N(S) modulo32768; not CAN arbitration identifier.',minimum=0,maximum=32767)
d('receive_sequence','number','Actual15-bit N(R) modulo32768; acknowledgment refers to APCI sequence, not application acceptance.',minimum=0,maximum=32767)
d('outstanding_apdus','number','Actual unacknowledged I APDUs bounded by configured k.',minimum=0,maximum=32767)
d('unacknowledged_received','number','Actual receive count awaiting acknowledgment; instantaneous count need not be a queue capacity.',minimum=0,maximum=32767)
d('length_l','number','Actual one-byte length covers4 APCI control bytes plus ASDU; bounded253, separate from2-byte start/length prefix.',minimum=4,maximum=253,unit='Byte')
d('length_limit','number','Actual peer accepted APCI length-L limit; reduced negotiated limit may differ from protocol ceiling253.',minimum=4,maximum=253,unit='Byte')
d('apdu_bytes','number','Actual complete APDU stream bytes: lengthL+2, at most255; not Ethernet frame or ASDU size.',minimum=6,maximum=255,unit='Byte')
for key,upper in [('type_id_bytes',1),('vsq_bytes',1),('cot_bytes',2),('ca_bytes',2),('ioa_bytes',3)]:
    d(key,'number','Actual agreed '+key+' width. Baseline1/1/2/2/3; device-agreed reductions need their own interoperability profile.',minimum=1,maximum=upper,unit='Byte',source=ASDU)
for key,upper,meaning in [('common_address',65535,'Actual ASDU common address for configured width.'),
 ('originator',255,'Actual originator when COT2; absent under COT1.'),
 ('first_ioa',16777215,'Actual first information object address for configured1/2/3-byte width.'),
 ('type_id',255,'Actual ASDU type ID/private type with encoding evidence.'),
 ('cot',63,'Actual6-bit cause of transmission; negative/test flags remain separate.'),
 ('object_count',127,'Actual VSQ7-bit information object count; SQ sequence addresses must remain within width.')]:
    d(key,'number',meaning,minimum=1 if key=='type_id'else 0,maximum=upper,source=ASDU)
for key,meaning in [('test','Actual ASDU test flag.'),('negative','Actual ASDU negative-confirmation flag.'),
                    ('sequence','Actual SQ contiguous objects/one IOA versus individually addressed objects.')]:
    d(key,'boolean',meaning,source=ASDU)
d('object_layout','select','Actual fixed-size objects versus explicitly encoded private/variable objects.',options=['FIXED_OBJECT_SIZE','EXPLICIT_ENCODED'],source=ASDU)
d('object_bytes','number','Actual encoded fixed object size including quality/time, excluding IOA.',minimum=0,unit='Byte',source=ASDU)
d('objects_encoded_bytes','number','Actual full object encoding including required IOAs.',minimum=0,unit='Byte',source=ASDU)
d('asdu_bytes','number','Actual ASDU header plus information objects; max249 separate from lengthL253/APDU255.',minimum=0,maximum=249,unit='Byte',source=ASDU)
d('asdu_limit','number','Actual peer accepted ASDU limit; constructor249 does not prove a custom peer supports that value.',minimum=1,maximum=249,unit='Byte',source=CLIENT)
d('abb_message_limit_bytes','number','Actual COM600 Maximum Message Length setting; documentation gives230 default but does not resolve full-APDU versus length-L versus ASDU scope.',minimum=20,maximum=255,unit='Byte',source=ABB)
d('abb_message_scope','select','Actual proven mapping of the vendor message length setting; unresolved scope prevents a capacity claim.',options=['UNRESOLVED','LENGTH_L','FULL_APDU','ASDU'],source=ABB)
d('abb_message_scope_source','text','Actual device/revision proof of vendor message-length scope; no silent255-byte payload conversion.',source=ABB)
d('byte_order','select','Application Mode1 least-significant octet first; type-specific float/text representations still require evidence.',options=['LITTLE_ENDIAN_MODE1'],default='LITTLE_ENDIAN_MODE1',source=ABB)
d('time_format','select','Actual NONE/CP24/CP56 ASDU representation, including validity and synchronization semantics.',options=['NONE','CP24TIME2A','CP56TIME2A'],source=GUIDE)
d('command_procedure','select','Actual direct-execute or select-before-operate matching both stations.',options=['DIRECT_EXECUTE','SELECT_BEFORE_OPERATE'],source=GUIDE)
d('server_mode','select','Actual library single/per-connection/multiple redundancy groups and distinct queue-retention semantics.',options=['SINGLE_REDUNDANCY_GROUP','CONNECTION_IS_GROUP','MULTIPLE_REDUNDANCY_GROUPS'],source=GUIDE)
for key in ('group_count','active_connections','active_per_group','max_connections','low_queue','high_queue'):
    d(key,'number','Actual '+key+' for configured server/group; no queue256, topology or connection count fabricated.',minimum=0,source=SERVER)
d('low_queue_overflow','select','Actual event retention/overflow policy; lib drops oldest low-priority event when full.',options=['DROP_OLDEST','DEVICE_POLICY'],source=GUIDE)
d('tcp_segment_bytes','number','Actual stream segmentation/reassembly bound from lower TCP profile; APDUs may span/coalesce segments.',minimum=1,unit='Byte',source=GUIDE)
d('tls_record_bytes','number','Actual negotiated TLS wire record size including security overhead; not constant Ethernet overhead.',minimum=1,unit='Byte',source=GUIDE)

REMOVED={key:'Removed inherited '+key+': IEC104 application/APCI depends on an explicitly bound TCP/IP/physical path and actual device scheduling; no CAN/Ethernet physical defaults.'
 for key in ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','mtu_bytes','vlan_id','duplex',
             'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms',
             'gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['implementation','role','transport','peer_endpoint','transport_binding','device_source','interoperability_source','physical_source','schedule_source']


def semantics():
    rules=[]
    def r(key,when=None,source=CLIENT,**kw):
        rules.append(dict(parameter='iec104_'+key,when={'iec104_'+k:v for k,v in (when or {}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('t2_ms',maximum_expression={'subtract':['iec104_t1_ms',1]},source=ABB)
    r('lib_int_bits',{'implementation':'LIB60870_C_2_3_2'},required=True,allowed=[16,32,64],source=COMMON)
    r('abi_source',{'implementation':'LIB60870_C_2_3_2'},required=True,source=COMMON)
    for key in ('t0_ms','t1_ms','t2_ms','t3_ms'):
        r(key,{'parameter_profile':'INTEROPERABILITY_BASELINE'},minimum=1000,maximum=255000,multiple_of=1000,source=ABB)
        r(key,{'implementation':'LIB60870_C_2_3_2'},minimum=1000,multiple_of=1000)
        for bits in (16,32,64):
            r(key,{'implementation':'LIB60870_C_2_3_2','lib_int_bits':bits},maximum=2**(bits-1)-1,source=COMMON)
    for key,limit,quantum in [('t0_ms',65535,1),('t1_ms',255000,1000),('t2_ms',100000,1000),
        ('t3_ms',65535000,1000),('reconnect_ms',255000,1000),('command_confirmation_ms',255000,1000),('command_termination_ms',255000,1000)]:
        r(key,{'implementation':'ABB_COM600_3_5'},maximum=limit,multiple_of=quantum,source=ABB)
    r('outstanding_apdus',maximum_parameter='iec104_k')
    r('length_l',maximum_parameter='iec104_length_limit')
    r('apdu_bytes',equal_expression={'sum':[2,'iec104_length_l']})
    r('length_l',{'format':'I'},equal_expression={'sum':[4,'iec104_asdu_bytes']})
    r('transfer_state',{'format':'I'},required=True,allowed=['STARTED'])
    r('u_function',{'format':'I'},allowed=[])
    r('u_function',{'format':'S'},allowed=[])
    r('u_function',{'format':'U'},required=True)
    r('send_sequence',{'format':'S'},allowed=[])
    for fmt in ('S','U'):
        r('length_l',{'format':fmt},allowed=[4])
        r('asdu_bytes',{'format':fmt},allowed=[0])
    for key in ('send_sequence','receive_sequence'):r(key,{'format':'U'},allowed=[])
    for width in (1,2):r('common_address',{'ca_bytes':width},maximum=2**(8*width)-1,source=ASDU)
    r('originator',{'cot_bytes':1},allowed=[],source=ASDU)
    for width in (1,2,3):
        r('first_ioa',{'ioa_bytes':width},maximum=2**(8*width)-1,source=ASDU)
        r('first_ioa',{'ioa_bytes':width,'sequence':True},maximum_expression={'subtract':[2**(8*width),'iec104_object_count']},source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','object_count':0},allowed=[0],source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','sequence':True},when_positive=['iec104_object_count'],
      equal_expression={'sum':['iec104_ioa_bytes',{'product':['iec104_object_count','iec104_object_bytes']}]},source=ASDU)
    r('objects_encoded_bytes',{'object_layout':'FIXED_OBJECT_SIZE','sequence':False},
      equal_expression={'product':['iec104_object_count',{'sum':['iec104_ioa_bytes','iec104_object_bytes']}]},source=ASDU)
    r('asdu_bytes',{'format':'I'},equal_expression={'sum':[2,'iec104_cot_bytes','iec104_ca_bytes','iec104_objects_encoded_bytes']},source=ASDU)
    r('asdu_bytes',maximum_parameter='iec104_asdu_limit',source=ASDU)
    for scope,key in [('LENGTH_L','length_l'),('FULL_APDU','apdu_bytes'),('ASDU','asdu_bytes')]:
        r(key,{'implementation':'ABB_COM600_3_5','abb_message_scope':scope},maximum_parameter='iec104_abb_message_limit_bytes',source=ABB)
        r('abb_message_scope_source',{'implementation':'ABB_COM600_3_5','abb_message_scope':scope},required=True,source=ABB)
    r('type_source',when_present=['iec104_type_id'],required=True,source=ASDU)
    r('tls_source',{'transport':'TLS_TCP'},required=True,source=GUIDE)
    r('tls_record_bytes',{'transport':'TCP'},allowed=[],source=GUIDE)
    r('command_source',when_present=['iec104_command_procedure'],required=True,source=GUIDE)
    r('time_source',when_present=['iec104_time_format'],when_not={'iec104_time_format':'NONE'},required=True,source=GUIDE)
    for mode in ('SINGLE_REDUNDANCY_GROUP','MULTIPLE_REDUNDANCY_GROUPS'):
        r('active_per_group',{'server_mode':mode},maximum=1,source=GUIDE)
    r('active_connections',{'server_mode':'SINGLE_REDUNDANCY_GROUP'},maximum=1,source=GUIDE)
    r('active_connections',{'server_mode':'MULTIPLE_REDUNDANCY_GROUPS'},maximum_parameter='iec104_group_count',source=GUIDE)
    r('active_connections',maximum_parameter='iec104_max_connections',source=GUIDE)
    r('redundancy_source',when_present=['iec104_server_mode'],required=True,source=GUIDE)
    return {'rate_model':{'type':'IEC104_BOUND_TRANSPORT','fields':[]},'required_parameters':['iec104_'+k for k in REQUIRED],
            'native_parameter_prefixes':['iec104_'],'parameter_constraints':rules,
            'mechanisms':{'framing':['APCI_I_S_U_AND_EXPLICIT_ASDU'], 'addressing':['TCP_ENDPOINT_AND_CA_IOA_SEPARATE'],
                'arbitration':['BOUND_TCP_PATH_AND_APCI_WINDOWS'], 'integrity':['BOUND_TCP_TLS_AND_APPLICATION_QUALITY'],
                'acceptance':['TCP_ACK_APCI_ACK_ACT_CON_ACT_TERM_SEPARATE']}}


def fields():
    result=[];required=set(semantics()['required_parameters'])
    baseline={'iec104_parameter_profile':'INTEROPERABILITY_BASELINE'}
    lib={'iec104_implementation':'LIB60870_C_2_3_2','iec104_parameter_profile':'FACTORY_PROFILE'}
    abb={'iec104_implementation':'ABB_COM600_3_5','iec104_parameter_profile':'FACTORY_PROFILE'}
    base_values={'k':12,'w':8,'t0_ms':30000,'t1_ms':15000,'t2_ms':10000,'t3_ms':20000}
    lib_values={**base_values,'t0_ms':10000,'type_id_bytes':1,'vsq_bytes':1,'cot_bytes':2,'ca_bytes':2,'ioa_bytes':3,'asdu_limit':249}
    abb_values={'k':12,'w':8,'t1_ms':15000,'t2_ms':10000,'reconnect_ms':30000,'command_confirmation_ms':10000,
                'command_termination_ms':60000,'termination_required':True,'parallel_commands':False,'cot_bytes':2,'ca_bytes':2,'ioa_bytes':3,
                't3_ms':20000,'abb_message_limit_bytes':230}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('iec104_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,integer=spec['type']=='number',parameter_origin='DEVICE_CONFIGURATION',
            default_status='PROPOSED_STANDARD'if 'default'in item else 'UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[]
        for when,values,source in [(baseline,base_values,ABB),(lib,lib_values,CLIENT),(abb,abb_values,ABB)]:
            if key in values:proposals.append({'when':when,'value':values[key],'source':source,'source_revision':SOURCES[source]})
        if key=='port':
            proposals.extend({'when':{'iec104_transport':transport},'value':port,'source':IANA}for transport,port in [('TCP',2404),('TLS_TCP',19998)])
        if key=='server_mode':proposals.append({'when':{**lib,'iec104_role':'CONTROLLED'},'value':'SINGLE_REDUNDANCY_GROUP','source':SERVER})
        if key=='low_queue_overflow':proposals.append({'when':{**lib,'iec104_role':'CONTROLLED'},'value':'DROP_OLDEST','source':GUIDE})
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
