"""MQTT 3.1.1/5.0 session and packet declarations; explicit ordered lower transport."""
P3='https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html'
P5='https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html'
E3='https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/errata01/os/mqtt-v3.1.1-errata01-os.html'
SOURCES={P3:'OASIS MQTT3.1.1 October29 2014 sections1.5/2/3.1/3.3/3.8/4.2-4.7/5.3; packet, UTF8, sessions and ordered transport',
 P5:'OASIS MQTT5.0 March7 2019 sections1.5/2/3.1-3.3/3.8/4.2-4.9/4.12/5.3; version-specific property absence defaults, directional flow control and connection-scoped aliases',
 E3:'OASIS Approved Errata01 December10 2015 section2.1; corrected RemainingLength decoder range check accepts fourth byte through268435455, no conformance changes; NIS parameter validation is not a complete packet decoder'}
KINDS=['CONNECT','CONNACK','PUBLISH','PUBACK','PUBREC','PUBREL','PUBCOMP','SUBSCRIBE','SUBACK','UNSUBSCRIBE','UNSUBACK','PINGREQ','PINGRESP','DISCONNECT','AUTH']
DECLARATIONS=[]
def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,v5=False,**kw):
    DECLARATIONS.append(dict(key='mq_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,options=options,
        source=P5 if v5 else P3,source_revision=SOURCES[P5 if v5 else P3],v5=v5,**kw))
for key,meaning,options,v5 in [
 ('version','Actual MQTT3.1.1 protocollevel4 versus5.0 level5; never infer from topic or industry.',['V3_1_1','V5_0'],False),
 ('transport','Actual ordered lossless bidirectional connection, distinct MQTT-SN UDP.',['TCP','TLS','WS','WSS','REGISTERED_ORDERED_STREAM'],False),
 ('role','Actual endpoint MQTT client or server, distinct publisher/subscriber and transport initiator.',['CLIENT','SERVER'],False),
 ('direction','Actual packet direction; negotiated receive limits apply to receiver on this connection.',['CLIENT_TO_SERVER','SERVER_TO_CLIENT'],False),
 ('packet_kind','Actual control packet kind; AUTH only version5.0, no implicit PUBLISH defaults.',KINDS,False),
 ('phase','Actual new packet, response or re-delivery of outstanding packet; no timed retry policy.',['NEW','RESPONSE','REDELIVERY'],False),
 ('client_id_profile','Actual broker minimum portable alphanumeric1..23byte support or registered broker acceptance.',['PORTABLE_1_23','SERVER_ASSIGNED','REGISTERED'],False),
 ('subscription_kind','Actual non-shared or MQTT5 shared subscription, shared delivery not broadcast all clients.',['NON_SHARED','SHARED'],True),
]:d(key,'select',meaning,options=options,v5=v5)
for key,meaning,v5 in [
 ('connection_id','Actual network connection identity, scoped independently from persistent MQTT session.',False),
 ('session_id','Actual broker/client session identity and persistence binding; no generated client ID.',False),
 ('binding_source','Actual selected TCP/TLS/WebSocket/other ordered connection and lower technology path.',False),
 ('peer_source','Actual client/broker implementation/revision, negotiated limits and supported capabilities.',False),
 ('codec_source','Actual complete packet lengths/properties/UTF8/application serialization and revision.',False),
 ('schedule_source','Actual broker/client queues, flow, lower traffic and response/processing/schedule bounds.',False),
 ('acceptance_source','Actual application timing, freshness, security and safety requirements; MQTT QoS is hop delivery.',False),
 ('registered_source','Actual registered stream transport or extended broker ClientID acceptance.',False),
 ('credential_source','Actual credential reference/authorization method and policy; no plaintext credential default.',False),
 ('security_source','Actual selected TLS/WSS authentication/encryption and lower transport qualification.',False),
 ('alias_connection_id','Actual receiver alias mapping network connection, never persistent session scope.',True),
 ('request_connection_id','Actual original packet network connection for current response correlation.',False),
]:d(key,'text',meaning,v5=v5)
for key,meaning,lo,hi,v5,unit in [
 ('protocol_level','Actual CONNECT level4 or5 selected by revision.',0,255,False,None),
 ('port','Actual transport port; registered TCP1883 andTLS8883 proposals, WS/WSS binding separate.',1,65535,False,None),
 ('qos','Actual per-hop PUBLISH quality0/1/2; reserved3 invalid and not IP priority.',0,2,False,None),
 ('subscription_qos','Actual requested subscription maximum0/1/2; not restricted by server publish MaximumQoS.',0,2,False,None),
 ('maximum_qos','Effective server-supported publishMaximumQoS; absent5property means2, encoded property only0/1.',0,2,True,None),
 ('packet_id','Actual nonzero16bit outstanding packet identifier, absent onQoS0 PUBLISH.',1,65535,False,None),
 ('request_packet_id','Actual original/outstanding identifier echoed by acknowledgments and redelivery.',1,65535,False,None),
 ('flags','Actual low4 fixed-header bits; PUBLISH QoS/DUP/RETAIN versus reserved packet-kind flags.',0,15,False,None),
 ('remaining_length','Actual complete variable header plus payload, excludes fixed header and own VBI bytes.',0,268435455,False,'byte'),
 ('remaining_length_bytes','Actual minimal1..4bytes of RemainingLength VBI, not payload size.',1,4,False,'byte'),
 ('variable_header_bytes','Actual selected control-packet variable header, includes property length/data in5.',0,268435455,False,'byte'),
 ('packet_payload_bytes','Actual control packet payload; PUBLISH application payload, CONNECT fields differ.',0,268435455,False,'byte'),
 ('packet_bytes','Actual full MQTT control packet=1+remainingVBI+remaining, max268435460.',2,268435460,False,'byte'),
 ('properties_bytes','Actual encoded5-property set, distinct own variable length field.',0,268435455,True,'byte'),
 ('property_length_bytes','Actual minimal1..4bytes of5 property-length VBI.',1,4,True,'byte'),
 ('receive_maximum','Effective receiver cap1..65535 QoS1/2 outstanding PUBLISH only; absentproperty65535.',1,65535,True,None),
 ('initial_quota','Actual initial directional send quota1..receiver maximum, not preserved betweenconnections.',1,65535,True,None),
 ('send_quota','Actual current send quota may reach0; other control packets continue, QoS0 unaffected.',0,65535,True,None),
 ('inflight','Actual direction QoS1/2 unacknowledged publish count; QoS0 not counted by ReceiveMaximum.',0,65535,True,None),
 ('maximum_packet_size','Actual explicit5 receiver full-packet cap fourbyte nonzero, absent no extra cap.',1,4294967295,True,'byte'),
 ('topic_alias_maximum','Actual directional accepted alias upperbound; absentproperty0 disallows aliases.',0,65535,True,None),
 ('topic_alias','Actual nonzero alias identifier1..65535 within receiver cap, mapping perconnection.',1,65535,True,None),
 ('subscription_identifier','Actual optional5 nonzero VBI subscription ID1..268435455, not packet ID.',1,268435455,True,None),
 ('keepalive_s','Actual CONNECT seconds0..65535;0 disables MQTT timer, no universal60seconds.',0,65535,False,'s'),
 ('server_keepalive_s','Actual5 server override seconds0..65535, including0 disabling timer.',0,65535,True,'s'),
 ('effective_keepalive_s','Actual client interval uses5 server override ifpresent, otherwise CONNECT interval.',0,65535,False,'s'),
 ('session_expiry_s','Actual5 uint32seconds; absent0 ends session onclose, FFFFFFFF noexpiry.',0,4294967295,True,'s'),
 ('message_expiry_s','Actual5 optional uint32message lifetime; absence means noexpiry,0 notinfinite.',0,4294967295,True,'s'),
 ('will_delay_s','Actual5 delayseconds; absent0, will at delay or session end whicheverfirst.',0,4294967295,True,'s'),
 ('will_qos','Actual0/1/2 CONNECT willQoS, must0 if WillFlagFalse.',0,2,False,None),
 ('will_payload_bytes','Actual length-prefixed binary will payload0..65535, not full packet payload cap.',0,65535,False,'byte'),
 ('payload_format','Actual5 indicator0 unspecifiedbytes or1UTF8 character data; absent0.',0,1,True,None),
 ('username_bytes','Actual optional username UTF8bytes0..65535, credential reference instead of secret text.',0,65535,False,'byte'),
 ('password_bytes','Actual optional binary password/token bytes0..65535; may be independent username in5.',0,65535,False,'byte'),
 ('authentication_data_bytes','Actual5 binary challenge/response bytes0..65535; actual agreedmethod required.',0,65535,True,'byte'),
 ('retain_handling','Actual5 subscription policy0always/1ifnew/2never; reserved3 invalid.',0,2,True,None),
]:d(key,'number',meaning,lo,hi,unit,v5=v5,integer=True)
d('disconnect_silence_s','number','Actual server no-control-packet disconnect bound1.5*effectiveKeepAlive ifnonzero; not E2Edeadline.',0,None,'s')
for key,meaning,v5 in [
 ('ordered_stream','Actual transport provides ordered bytes, not unordered bare UDP.',False),
 ('lossless_stream','Actual lower connection presents lossless byte stream, not sensor packet loss claim.',False),
 ('bidirectional_stream','Actual network connection carries ordered stream in both directions.',False),
 ('dup','Actual PUBLISH duplicate flag, QoS0 alwaysfalse; not application message uniqueness.',False),
 ('retain','Actual PUBLISH retained flag; empty retained payload deletes retained value.',False),
 ('packet_id_unused','Actual new ID unused among sender outstanding commands; opposite direction independent.',False),
 ('pending_match','Actual response matches tracked outstanding request in directional session.',False),
 ('clean_session','Actual3.1.1 CleanSession flag; no5 session-expiry field substitution.',False),
 ('clean_start','Actual5 CleanStart flag resets previous session independently of expiry duration.',True),
 ('session_present','Actual CONNACK session flag; reset clean session/start requiresfalse.',False),
 ('reconnected','Actual re-delivery after new connection, with existing session and unacknowledged state.',False),
 ('will_flag','Actual CONNECT will presence; whenfalse no willtopic/payload.',False),
 ('will_retain','Actual CONNECT willretained flag; mustfalse if WillFlagFalse.',False),
 ('username_flag','Actual CONNECT username presence; credential authorization policy not inferred.',False),
 ('password_flag','Actual CONNECT password/token presence;3 requiresusernameflag,5 permitsindependent.',False),
 ('maximum_qos_present','Actual5 server MaximumQoSproperty presence; encodedvalue0/1 only.',True),
 ('receive_maximum_present','Actual5 receivercap property presence; absence effective65535.',True),
 ('topic_alias_maximum_present','Actual5 receiveralias cap property presence; absence effective0.',True),
 ('alias_mapped','Actual alias is already established at receiver on this networkconnection for empty topic.',True),
 ('server_keepalive_present','Actual5 CONNACK keepalive override property present.',True),
 ('session_expiry_present','Actual5 CONNECT SessionExpiryproperty present; absent0.',True),
 ('will_delay_present','Actual5 WillDelayproperty present; absent0.',True),
 ('payload_format_present','Actual5 PayloadFormatproperty present; absent0.',True),
 ('retain_available','Effective5 server retained support; absentpropertyTrue.',True),
 ('retain_available_present','Actual5 CONNACK retained availability property present.',True),
 ('request_response_info','Effective5 CONNECT RequestResponseInformation; absentFalse.',True),
 ('request_response_info_present','Actual5 CONNECT RequestResponseInformation property present.',True),
 ('request_problem_info','Effective5 CONNECT RequestProblemInformation; absentTrue.',True),
 ('request_problem_info_present','Actual5 CONNECT RequestProblemInformation property present.',True),
 ('no_local','Actual5 subscription option forbids self-publish, cannotTrue shared subscription.',True),
 ('retain_as_published','Actual5 forwarded RETAIN bit preservation option, not shared retained history.',True),
]:d(key,'boolean',meaning,v5=v5)
TEXTS={
 'client_id':('Actual ClientIDUTF8, portable1..23alphanumeric or broker-qualified extended/server-assigned.',False),
 'assigned_client_id':('Actual5 server allocatedunique ClientID, not invented default.',True),
 'topic':('Actual PUBLISH TopicNameUTF8 no+#;5 empty only currentconnectionmappedalias.',False),
 'topic_filter':('Actual subscription UTF8filter with +wholelevel and #terminalwholelevel, no normalization.',False),
 'will_topic':('Actual will TopicNameUTF8 nonempty/no+#, distinct application payload content.',False),
 'response_topic':('Actual5 response TopicNameUTF8 nonempty/no+#, no mandatoryreplydeadline.',True),
 'authentication_method':('Actual5 negotiated enhanced authentication method; no universal SASL name.',True),
 'connect_authentication_method':('Actual5 initial CONNECTmethod to match AUTH/CONNACK, sourcequalified.',True),
 'user_property_name':('Actual5 user propertyname UTF8string; duplicates allowed, application meaningactual.',True),
 'user_property_value':('Actual5 user propertyvalue UTF8string; preserves BOM/whitespace/case.',True),
 'content_type':('Actual5 optional payload MIME/contextUTF8; opaque protocol property, no default contentcodec.',True),
 'payload_text':('Actual5 UTF8 character payload whenindicator1; U+0000 allowedpayload, unlike MQTTstrings.',True),
}
for key,(meaning,v5)in TEXTS.items():
    d(key,'text',meaning,v5=v5)
    if key!='payload_text':d(key+'_bytes','number','Actual UTF8 encoded '+key+' octets, not codepoints/UTF16units.',0,65535,'byte',v5=v5,integer=True)
REQUIRED=['version','transport','role','direction','packet_kind','phase','connection_id','session_id','binding_source','peer_source','codec_source','schedule_source','acceptance_source','ordered_stream','lossless_stream','bidirectional_stream']
REMOVED={k:'MQTT has no own '+k+' or foreign CAN/Ethernet default; explicit ordered connection, direction/session/peer resource and packet declarations required.'for k in
 ('bitrate','mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
  'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms',
  'gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
    rules=[]
    def r(key,when=None,source=P5,**kw):
        rules.append(dict(parameter=key if key in ('payload_bytes','local_timing_evidence')else'mq_'+key,
          when={'mq_'+k:v for k,v in(when or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('local_timing_evidence',allowed=[])
    for key in ('ordered_stream','lossless_stream','bidirectional_stream'):r(key,allowed=[True],source=P3)
    for k in REQUIRED:r(k,required=True)
    for version,level,source in [('V3_1_1',4,P3),('V5_0',5,P5)]:r('protocol_level',{'version':version},allowed=[level],source=source)
    for port,flag in [('TLS','security_source'),('WSS','security_source'),('REGISTERED_ORDERED_STREAM','registered_source')]:r(flag,{'transport':port},required=True)
    r('clean_session',{'version':'V5_0'},allowed=[])
    for spec in DECLARATIONS:
        if spec['v5']:r(spec['key'][3:],{'version':'V3_1_1'},allowed=[],source=P3,
                       text_encoding='utf-8' if spec['type']=='text' else None)
    r('packet_kind',{'version':'V3_1_1'},forbidden=['AUTH'],source=P3)
    client_packets=['CONNECT','SUBSCRIBE','UNSUBSCRIBE','PINGREQ'];server_packets=['CONNACK','SUBACK','UNSUBACK','PINGRESP']
    for kind,direction in [(k,'CLIENT_TO_SERVER')for k in client_packets]+[(k,'SERVER_TO_CLIENT')for k in server_packets]:
        r('direction',{'packet_kind':kind},allowed=[direction],source=P3)
    r('direction',{'version':'V3_1_1','packet_kind':'DISCONNECT'},allowed=['CLIENT_TO_SERVER'],source=P3)
    for kind in KINDS:
        if kind!='PUBLISH':r('flags',{'packet_kind':kind},allowed=[2 if kind in ('PUBREL','SUBSCRIBE','UNSUBSCRIBE')else 0])
    for qos in (0,1,2):
        for dup in (False,True):
            for retain in (False,True):
                r('flags',{'packet_kind':'PUBLISH','qos':qos,'dup':dup,'retain':retain},allowed=[8*int(dup)+2*qos+int(retain)])
    for kind in ('PINGREQ','PINGRESP'):r('remaining_length',{'packet_kind':kind},allowed=[0],source=P3)
    r('remaining_length',{'version':'V3_1_1','packet_kind':'DISCONNECT'},allowed=[0],source=P3)
    r('remaining_length',equal_expression={'sum':['mq_variable_header_bytes','mq_packet_payload_bytes']},exact_decimal_equality=True)
    r('packet_bytes',equal_expression={'sum':[1,'mq_remaining_length_bytes','mq_remaining_length']},exact_decimal_equality=True)
    r('packet_bytes',maximum_parameter='mq_maximum_packet_size')
    for length,size in [('remaining_length','remaining_length_bytes'),('properties_bytes','property_length_bytes')]:
        for lo,hi,n in [(0,127,1),(128,16383,2),(16384,2097151,3),(2097152,268435455,4)]:
            r(size,when_ranges={'mq_'+length:[lo,hi]},allowed=[n])
            if length=='remaining_length':
                r(size,{'version':'V3_1_1'},when_ranges={'mq_'+length:[lo,hi]},allowed=[n],source=E3)
    for key in ('client_id','assigned_client_id','topic','topic_filter','will_topic','response_topic','authentication_method',
                'connect_authentication_method','user_property_name','user_property_value','content_type'):
        pattern=r'[^\x00\ud800-\udfff]*'
        if key in ('topic','will_topic','response_topic'):pattern=r'[^\x00+#\ud800-\udfff]*'
        r(key,text_encoding='utf-8',encoded_bytes_parameter='mq_'+key+'_bytes',pattern=pattern)
        r(key,when_present=['mq_'+key+'_bytes'],required=True,allow_empty_text=True,text_encoding='utf-8')
        r(key+'_bytes',when_present=['mq_'+key],required=True)
    for key in ('topic_filter','will_topic','response_topic','assigned_client_id'):r(key+'_bytes',minimum=1)
    r('topic_filter',pattern=r'(?:[^\x00/+#]*|\+)(?:/(?:[^\x00/+#]*|\+))*(?:/#)?|#')
    r('topic_filter',{'subscription_kind':'SHARED'},pattern=r'\$share/[^/+#]+/.+')
    r('no_local',{'subscription_kind':'SHARED'},allowed=[False])
    r('topic_filter',{'subscription_kind':'NON_SHARED'},pattern=r'(?!\$share/)[\s\S]*')
    r('client_id',{'client_id_profile':'PORTABLE_1_23'},pattern=r'[0-9A-Za-z]{1,23}')
    r('registered_source',{'client_id_profile':'REGISTERED'},required=True)
    r('client_id_bytes',{'client_id_profile':'SERVER_ASSIGNED'},allowed=[0])
    r('clean_session',{'version':'V3_1_1','client_id_bytes':0},allowed=[True],required=True,source=P3)
    r('assigned_client_id',{'version':'V5_0','client_id_bytes':0,'packet_kind':'CONNACK'},required=True)
    for key in ('client_id','client_id_bytes'):r(key,{'packet_kind':'CONNECT'},required=True,allow_empty_text=True,text_encoding='utf-8'if key=='client_id'else None)
    for clean,version in [('clean_session','V3_1_1'),('clean_start','V5_0')]:
        r(clean,{'version':version,'packet_kind':'CONNECT'},required=True)
        r('session_present',{'version':version,clean:True},allowed=[False])
    for key in ('qos','dup','retain','topic','topic_bytes'):
        r(key,{'packet_kind':'PUBLISH'},required=True,allow_empty_text=True,text_encoding='utf-8'if key=='topic'else None)
    r('topic_bytes',{'version':'V3_1_1','packet_kind':'PUBLISH'},minimum=1,source=P3)
    r('topic_alias',{'version':'V5_0','topic_bytes':0},required=True)
    r('alias_mapped',{'version':'V5_0','topic_bytes':0},required=True,allowed=[True])
    r('alias_connection_id',when_present=['mq_topic_alias'],equal_parameter='mq_connection_id',required=True)
    r('topic_alias',maximum_parameter='mq_topic_alias_maximum')
    r('topic_alias_maximum',when_present=['mq_topic_alias'],required=True)
    r('qos',{'direction':'CLIENT_TO_SERVER'},maximum_parameter='mq_maximum_qos')
    r('dup',{'packet_kind':'PUBLISH','qos':0},allowed=[False],source=P3)
    r('packet_id',{'packet_kind':'PUBLISH','qos':0},allowed=[],source=P3)
    r('packet_payload_bytes',{'packet_kind':'PUBLISH'},equal_parameter='payload_bytes')
    for qos,pid in [(0,0),(1,2),(2,2)]:
        for version,props in [('V3_1_1',0),('V5_0',{'sum':['mq_property_length_bytes','mq_properties_bytes']})]:
            r('variable_header_bytes',{'packet_kind':'PUBLISH','qos':qos,'version':version},
              equal_expression={'sum':[2,'mq_topic_bytes',pid,props]},exact_decimal_equality=True)
    pid_kinds=['PUBACK','PUBREC','PUBREL','PUBCOMP','SUBSCRIBE','SUBACK','UNSUBSCRIBE','UNSUBACK']
    for kind in pid_kinds:r('packet_id',{'packet_kind':kind},required=True,source=P3)
    for qos in (1,2):r('packet_id',{'packet_kind':'PUBLISH','qos':qos},required=True,source=P3)
    for kind in ('CONNECT','CONNACK','PINGREQ','PINGRESP','DISCONNECT','AUTH'):r('packet_id',{'packet_kind':kind},allowed=[])
    for kind in ('SUBSCRIBE','UNSUBSCRIBE','PUBLISH'):
        r('packet_id_unused',{'packet_kind':kind,'phase':'NEW'},when_present=['mq_packet_id'],allowed=[True],required=True)
    for kind in ('PUBACK','PUBREC','PUBREL','PUBCOMP','SUBACK','UNSUBACK'):
        r('packet_id',{'packet_kind':kind},equal_parameter='mq_request_packet_id')
        for key in ('request_packet_id','request_connection_id','pending_match'):r(key,{'packet_kind':kind},required=True)
        r('connection_id',{'packet_kind':kind},equal_parameter='mq_request_connection_id')
        r('pending_match',{'packet_kind':kind},allowed=[True])
    for key in ('receive_maximum','initial_quota','inflight'):r(key,maximum_parameter='mq_receive_maximum')
    r('send_quota',maximum_parameter='mq_initial_quota')
    for qos in (1,2):r('send_quota',{'packet_kind':'PUBLISH','phase':'NEW','qos':qos},minimum=1)
    r('receive_maximum',{'receive_maximum_present':False},allowed=[65535])
    r('maximum_qos',{'maximum_qos_present':False},allowed=[2]);r('maximum_qos',{'maximum_qos_present':True},allowed=[0,1])
    r('topic_alias_maximum',{'topic_alias_maximum_present':False},allowed=[0])
    for key,present,value in [('session_expiry_s','session_expiry_present',0),('will_delay_s','will_delay_present',0),
       ('payload_format','payload_format_present',0),('retain_available','retain_available_present',True),
       ('request_response_info','request_response_info_present',False),('request_problem_info','request_problem_info_present',True)]:
        r(key,{present:False},allowed=[value])
    for key in ('retain','will_retain'):r(key,{'retain_available':False,'direction':'CLIENT_TO_SERVER'},allowed=[False])
    r('will_qos',maximum_parameter='mq_maximum_qos')
    r('effective_keepalive_s',{'server_keepalive_present':True},equal_parameter='mq_server_keepalive_s')
    r('server_keepalive_s',{'server_keepalive_present':True},required=True)
    r('effective_keepalive_s',{'server_keepalive_present':False},equal_parameter='mq_keepalive_s')
    r('effective_keepalive_s',{'version':'V3_1_1'},equal_parameter='mq_keepalive_s')
    r('disconnect_silence_s',when_positive=['mq_effective_keepalive_s'],equal_expression={'product':['mq_effective_keepalive_s',1.5]},exact_decimal_equality=True)
    r('disconnect_silence_s',{'effective_keepalive_s':0},allowed=[])
    r('payload_text',{'payload_format':1},text_encoding='utf-8',encoded_bytes_parameter='payload_bytes')
    for key in ('will_topic','will_payload_bytes'):r(key,{'will_flag':False},allowed=[],text_encoding='utf-8'if key=='will_topic'else None)
    r('will_qos',{'will_flag':False},allowed=[0]);r('will_retain',{'will_flag':False},allowed=[False])
    for key in ('will_topic','will_topic_bytes','will_payload_bytes','will_qos','will_retain'):r(key,{'will_flag':True},required=True)
    r('password_flag',{'version':'V3_1_1','username_flag':False},allowed=[False],source=P3)
    for flag,key in [('username_flag','username_bytes'),('password_flag','password_bytes')]:
        r(key,{flag:False},allowed=[]);r(key,{flag:True},required=True)
        r('credential_source',{flag:True},required=True)
    r('authentication_method',when_present=['mq_authentication_data_bytes'],required=True)
    r('authentication_method',{'packet_kind':'AUTH'},equal_parameter='mq_connect_authentication_method',required=True)
    r('connect_authentication_method',{'packet_kind':'AUTH'},required=True)
    for key in ('reconnected','session_present'):r(key,{'version':'V5_0','phase':'REDELIVERY'},allowed=[True],required=True)
    r('packet_kind',{'phase':'REDELIVERY'},allowed=['PUBLISH','PUBREL'])
    r('clean_start',{'version':'V5_0','phase':'REDELIVERY'},allowed=[False],required=True)
    r('clean_session',{'version':'V3_1_1','phase':'REDELIVERY'},allowed=[False],required=True,source=P3)
    r('packet_id',{'phase':'REDELIVERY'},equal_parameter='mq_request_packet_id',required=True)
    r('request_packet_id',{'phase':'REDELIVERY'},required=True)
    r('qos',{'packet_kind':'PUBLISH','phase':'REDELIVERY'},allowed=[1,2])
    r('dup',{'packet_kind':'PUBLISH','phase':'REDELIVERY'},allowed=[True])
    return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['mq_'+k for k in REQUIRED],
        native_parameter_prefixes=['mq_'],parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
        mechanisms={'transport':['EXPLICIT_ORDERED_LOSSLESS_BIDIRECTIONAL_STREAM'],
          'framing':['FIXED_HEADER_REMAINING_LENGTH_VBI','VERSION_SPECIFIC_PROPERTIES'],
          'delivery':['PER_HOP_QOS0_1_2','DIRECTIONAL_IDENTIFIERS_AND_FLOW_CONTROL'],
          'session':['REVISION_SCOPED_SESSION_PERSISTENCE','CONNECTION_SCOPED_TOPIC_ALIAS']})

def fields():
    result=[]
    conditional={'protocol_level':[({'version':'V3_1_1'},4),({'version':'V5_0'},5)],
        'port':[({'transport':'TCP'},1883),({'transport':'TLS'},8883)],
        'receive_maximum':[({'version':'V5_0','receive_maximum_present':False},65535)],
        'maximum_qos':[({'version':'V5_0','maximum_qos_present':False},2)],
        'topic_alias_maximum':[({'version':'V5_0','topic_alias_maximum_present':False},0)],
        'session_expiry_s':[({'version':'V5_0','session_expiry_present':False},0)],
        'will_delay_s':[({'version':'V5_0','will_delay_present':False},0)],
        'payload_format':[({'version':'V5_0','payload_format_present':False},0)],
        'retain_available':[({'version':'V5_0','retain_available_present':False},True)],
        'request_response_info':[({'version':'V5_0','request_response_info_present':False},False)],
        'request_problem_info':[({'version':'V5_0','request_problem_info_present':False},True)]}
    for spec in DECLARATIONS:
        key=spec['key'][3:];item={k:v for k,v in spec.items()if v is not None and k!='v5'}
        item.update(label=key.replace('_',' '),category='timing' if spec.get('unit')=='s' else 'qos',scope='route',
          editable=True,required=key in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
          validation_relevant=True,simulation_relevant=False)
        if spec['v5']:item['schema_when']={'mq_version':'V5_0'}
        if key=='clean_session':item['schema_when']={'mq_version':'V3_1_1'}
        if key in conditional:item.update(default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
            conditional_defaults=[dict(when={'mq_'+k:v for k,v in when.items()},value=value,source=spec['source'],source_revision=spec['source_revision'])for when,value in conditional[key]])
        result.append(item)
    return result
