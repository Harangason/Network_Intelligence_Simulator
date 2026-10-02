"""MQTT-SN1.2 message declarations with an explicitly qualified lower datagram path."""
P='https://raw.githubusercontent.com/oasis-open/mqtt-sn-sample-resources/1f1fd60538cce4f6d8cf76f9a54c9c166c628367/docs/MQTT-SN_spec_v1.2.pdf'
DRAFT='https://groups.oasis-open.org/discussion/mqtt-sn-20-draft-june-2026-uploaded'
SOURCES={P:'IBM MQTT-SN1.2 November14 2013 pp6-27 sections5/6/7; OASIS input specification, not an OASIS ratified2.0 standard; SHA256d0897de1bd7e698436c668b658dce4e3e0c67000886baee0f181ac5f3dc9ec79',
 DRAFT:'OASIS MQTT TC June19 2026 MQTT-SN2.0 working draft announcement; reviewed1.2 rules must not be applied silently to2.0'}
KINDS={'ADVERTISE':0,'SEARCHGW':1,'GWINFO':2,'CONNECT':4,'CONNACK':5,'WILLTOPICREQ':6,'WILLTOPIC':7,
 'WILLMSGREQ':8,'WILLMSG':9,'REGISTER':10,'REGACK':11,'PUBLISH':12,'PUBACK':13,'PUBCOMP':14,'PUBREC':15,
 'PUBREL':16,'SUBSCRIBE':18,'SUBACK':19,'UNSUBSCRIBE':20,'UNSUBACK':21,'PINGREQ':22,'PINGRESP':23,
 'DISCONNECT':24,'WILLTOPICUPD':26,'WILLTOPICRESP':27,'WILLMSGUPD':28,'WILLMSGRESP':29,'ENCAPSULATED':254}
DECLARATIONS=[]
def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None):
    DECLARATIONS.append(dict(key='sn_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,
        options=options,integer=kind=='number' and unit!='s',source=P,source_revision=SOURCES[P]))
for key,meaning,options in [
 ('version','Actual reviewed1.2 revision;2.0 draft has separate formats and is not silently accepted.',['V1_2']),
 ('transport','Actual bidirectional lower datagram binding, not an own radio/Ethernet carrier.',['UDP_IPV4','UDP_IPV6','ZIGBEE_APS','REGISTERED_DATAGRAM']),
 ('binding_profile','Actual qualified network revision;60octet legacy ZigBee observation is not every modern APS network.',['IBM_2013_ZIGBEE_APS','REGISTERED']),
 ('endpoint_role','Actual transmitting endpoint client, gateway or forwarder.',['CLIENT','GATEWAY','FORWARDER']),
 ('direction','Actual direction; gateway discovery can be sent by other clients.',['CLIENT_TO_GATEWAY','GATEWAY_TO_CLIENT','CLIENT_BROADCAST','GATEWAY_BROADCAST','FORWARDER_TO_GATEWAY','GATEWAY_TO_FORWARDER']),
 ('gateway_kind','Actual transparent perclient MQTT connections versus aggregating MQTT connection.',['TRANSPARENT','AGGREGATING','INTEGRATED_SERVER']),
 ('discovery','Actual known gateway versus optional broadcast discovery requiring lower broadcast service.',['PRECONFIGURED','BROADCAST']),
 ('packet_kind','Actual1.2 control message, distinct MQTT control byte and2.0 draft.',list(KINDS)),
 ('phase','Actual first transmission, response or supervised retransmission.',['NEW','RESPONSE','RETRY']),
 ('topic_kind','Actual TopicIdType00normal/01predefined/10twooctet short;11reserved.',['NORMAL','PREDEFINED','SHORT']),
 ('client_state','Actual gateway-observed active/asleep/awake/disconnected/lost state; awake ends on buffer-complete PINGRESP.',['ACTIVE','ASLEEP','AWAKE','DISCONNECTED','LOST']),
 ('timer_profile','Selected literature recommendations versus actual registered timing policy; recommendations are not guarantees.',['IBM_1_2_RECOMMENDED','REGISTERED']),
]:d(key,'select',meaning,options=options)
for key,meaning in [
 ('binding_source','Actual lower network/PHY/MTU/fragmentation/security qualification and revision.'),
 ('peer_source','Actual client/gateway implementation and supported1.2 features/revision.'),
 ('codec_source','Actual complete message encoding, lengths, topic mapping and forwarding codec/revision.'),
 ('schedule_source','Actual datagram contention/retry/queues/gateway/backend MQTT workload and response bounds.'),
 ('acceptance_source','Actual application deadline/freshness/security/safety requirements; per-hop QoS alone is insufficient.'),
 ('client_ref','Actual perclient identity for gateway/topic mappings, not a generated default.'),
 ('gateway_ref','Actual selected gateway identity/address; no invented GwId.'),
 ('gateway_address','Actual lower-network gateway address, separate numeric gateway ID.'),
 ('preconfigured_gateway_source','Actual a-priori destination for QoSminus1 publishing without connection setup.'),
 ('mapping_source','Actual receiver topicname/id mapping scoped to this client and selected gateway.'),
 ('mapping_client_ref','Actual client identity for accepted normal or predefined mapping; no shared unqualified pool.'),
 ('mapping_gateway_ref','Actual gateway identity for the mapping; IDs are not universal across gateways.'),
 ('request_client_ref','Actual original request client identity for acknowledgment correlation.'),
 ('request_gateway_ref','Actual original request gateway identity for acknowledgment correlation.'),
 ('gateway_backend_source','Actual MQTT/server connection/resource mapping; no fabricated broker capacity.'),
 ('timer_source','Actual timer tolerance/custom policy and deployed source, not literature confirmation.'),
 ('wireless_node_id_hex','Actual opaque lower node identifier in forwarding encapsulation, not necessarily a twooctet ZigBee address.'),
 ('packet_hex','Actual complete encoded message octets; optional scalar/header consistency is not a complete1.2 parser.'),
]:d(key,'text',meaning)
for key,meaning,lo,hi,unit in [
 ('protocol_id','Actual1.2 CONNECT ProtocolId01; all other values reserved.',0,255,None),
 ('port','Actual UDP/service endpoint; no universal1884 port declaration in1.2.',1,65535,None),
 ('network_packet_max','Actual lower-layer supported complete MQTT-SN datagram size after its own overhead/security/reassembly.',1,None,'byte'),
 ('length_bytes','Actual Length field1or3octets; extended uses marker01 and16bit bigendian.',1,3,'byte'),
 ('length_value','Actual encoded Length ordinary total, but ENCAPSULATED prefix excludes inner message.',2,65535,'byte'),
 ('packet_bytes','Actual complete ordinary message max65535 or forwarding prefix plus inner up to65790.',2,65790,'byte'),
 ('variable_bytes','Actual ordinary variablepart excludes Length+MsgType; forwarding exception includes Ctrl/node/inner.',0,65786,'byte'),
 ('msg_type','Actual onebyte MsgType from1.2 table, not MQTT highnibble.',0,255,None),
 ('flags','Actual1.2 byte: DUP7/QoS6..5/Retain4/Will3/Clean2/TopicIdType1..0; planned unused bits zero.',0,255,None),
 ('qos','Actual QoSminus1/0/1/2; minus1 is client-only unconnected publish, not reservedMQTT QoS3.',-1,2,None),
 ('topic_type','Actual flag bits00normal/01predefined/10short;11reserved.',0,2,None),
 ('topic_id','Actual16bit TopicId; operational IDs1..65534, clientREGISTER/wildcardSUBACK use0.',0,65535,None),
 ('request_topic_id','Actual original PUBLISH TopicId echoed by PUBACK, including two shorttopic octets.',0,65535,None),
 ('msg_id','Actual16bit transactionID; QoS0/minus1 PUBLISH containszero, not absent MQTTidentifier.',0,65535,None),
 ('request_msg_id','Actual tracked original MsgId for acknowledgments and retransmissions.',0,65535,None),
 ('return_code','Actual accepted00/congestion01/invalidtopic02/notsupported03; other values reserved.',0,3,None),
 ('gateway_id','Actual advertised onebyte gateway identity, distinct node address.',0,255,None),
 ('gateway_address_bytes','Actual GWINFO address encoding length including network-specific address type where present.',1,None,'byte'),
 ('radius','Actual SEARCHGW lower broadcast radius0..255;0 means allnodes.',0,255,None),
 ('connected_gateways','Actual perclient simultaneous connected gateway count; at mostone.',0,1,None),
 ('active_clients','Actual gateway activeclient count, no standard broker resource cap.',0,None,None),
 ('backend_connections','Actual gateway/server MQTT connections; transparent perclient and aggregating differ.',0,None,None),
 ('register_outstanding','Actual client pending REGISTER count; at mostone.',0,1,None),
 ('publish_outstanding','Actual client pending QoS1/2 PUBLISH exchange count; at mostone.',0,1,None),
 ('subscription_outstanding','Actual client shared SUBSCRIBE/UNSUBSCRIBE transaction count; at mostone.',0,1,None),
 ('keepalive_s','Actual16bit CONNECT keepalive duration; no inherited MQTT60second proposal.',0,65535,'s'),
 ('sleep_s','Actual optional16bit DISCONNECT sleep duration, separate keepalive.',0,65535,'s'),
 ('advertise_s','Actual16bit ADVERTISE interval; recommended greater900seconds, not a forced default900.',0,65535,'s'),
 ('advertise_misses','Actual number of missed advertisements; literature recommended2..3, not packetretry counter.',1,None,None),
 ('search_delay_s','Actual random SEARCHGW window0..TSEARCHGW, literatureTSEARCHGW5s.',0,None,'s'),
 ('gwinfo_delay_s','Actual client random GWINFO window0..TGWINFO, literatureTGWINFO5s.',0,None,'s'),
 ('wait_s','Actual congestion holdoff; literature recommendation strictly greater300s, no equality300 default.',0,None,'s'),
 ('retry_s','Actual unicast expected-response retry timer; literature recommendation10..15s.',0,None,'s'),
 ('retry_limit','Actual retransmission counter limit; literature recommendation3..5, not allmessages or QoSminus1.',0,None,None),
 ('retry_attempt','Actual retransmission count for supervised outstanding exchange.',0,None,None),
 ('watchdog_duration_s','Actual activekeepalive/asleepsleep duration being supervised; neither implies E2Edeadline.',0,65535,'s'),
 ('watchdog_bound_s','Actual gateway tolerance bound; recommended1.1duration above60s,1.5below60s; exactly60 requires actual policy.',0,None,'s'),
 ('wireless_node_id_bytes','Actual forwarder opaque node identifier bytes; prefix Length=3+identifier.',1,252,'byte'),
 ('forward_radius','Actual two low Ctrlbits0..3, separate onebyte SEARCHGW radius.',0,3,None),
 ('forward_ctrl','Actual forwarding Ctrlbyte; bits7..2reserved, selected planned encoding equals radius.',0,255,None),
 ('inner_packet_bytes','Actual complete independently encoded inner1.2 message, not counted in outerprefix Length.',2,65535,'byte'),
 ('inner_msg_type','Actual ordinary inner type, no unqualified recursive forwarding.',0,255,None),
]:d(key,'number',meaning,lo,hi,unit)
# The serialized Duration fields are uint16seconds even though other timers may be fractional.
for spec in DECLARATIONS:
    if spec['key'] in ('sn_keepalive_s','sn_sleep_s','sn_advertise_s','sn_watchdog_duration_s'):spec['integer']=True
for key,meaning in [
 ('bidirectional_datagram','Actual lower service carries datagrams client<->gateway, no lossless stream assertion.'),
 ('broadcast_supported','Actual lower network broadcast service if discovery used, not inferred fromradio name.'),
 ('protocol_fragmentation','MQTT-SN1.2 has no protocol fragmentation/reassembly; lower supported datagram size governs.'),
 ('dup','Actual retransmission DUPbit; not application event uniqueness.'),
 ('retain','Actual retained PUBLISH/Will request, not gateway buffer evidence.'),
 ('will','Actual CONNECT Willprompt flag; false withCleanFalse preserves existing Will.'),
 ('clean_session','Actual CONNECT reset includes subscriptions and Will; separate from MQTT5CleanStart.'),
 ('mapping_known','Actual peer accepted topic mapping; rejectedID cannot be repaired by assumingdefault.'),
 ('pending_match','Actual response matched original outstanding exchange for this client/gateway.'),
 ('gateway_server_connected','Actual gateway connected to MQTTserver or integrated server when advertising.'),
 ('gwinfo_address_present','Actual GWINFO address only when anotherclient advertisesgateway, not gateway itself.'),
 ('client_id_present','Actual optional PINGREQ clientID presence, required when waking sleepingclient.'),
 ('duration_present','Actual DISCONNECT Duration presence means sleep, absent closes connection.'),
 ('will_delete','Actual empty WILLTOPIC/UPD deletes both stored Willtopic andWillmessage; no flags encoded.'),
 ('wildcard_subscription','Actual normal topicfilter contains wildcard; acceptedSUBACK TopicIdzero.'),
 ('qos_minus1_supported','Actual gateway accepts QoSminus1; transparentgateway requires dedicated MQTTconnection.'),
]:d(key,'boolean',meaning)
for key,meaning,max_bytes in [
 ('client_id','Actual client identity1..23characters; encoded octets counted separately, not MQTT5serverassignment.',92),
 ('topic_name','Actual normal UTF8 topicname forREGISTER, not twooctet TopicId.',65535),
 ('topic_filter','Actual UTF8 subscriptionfilter with +wholelevel/#terminal; no MQTT5shared subscription options.',65535),
 ('short_topic','Actual exactlytwoUTF8 octets, not twoarbitrary Unicodecharacters; no registration.',2),
 ('will_topic','Actual Willtopic UTF8 sent separately fromCONNECT; emptyWilldelete is headeronly.',65535),
]:
    d(key,'text',meaning)
    d(key+'_bytes','number','Actual UTF8 encoded '+key+' octets, includes no MQTTtwooctet stringprefix.',0,max_bytes,'byte')
d('client_characters','number','Actual Unicode scalar character count1..23 forClientID; source character wording distinct encoded octets.',1,23,None)
d('will_message_bytes','number','Actual opaqueWill bytes inWILLMSG/UPD, no MQTTlengthprefix.',0,65535,'byte')
REQUIRED=['version','transport','binding_profile','endpoint_role','direction','discovery','packet_kind','phase','client_ref','gateway_ref',
 'binding_source','peer_source','codec_source','schedule_source','acceptance_source','bidirectional_datagram','network_packet_max','protocol_fragmentation']
REMOVED={k:'MQTT-SN1.2 has no own '+k+' or foreign CAN/Ethernet default; lower network/packet/gateway/client timing must be explicit.'for k in
 ('bitrate','mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
  'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms',
  'gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
    rules=[]
    def r(key,when=None,**kw):
        rules.append(dict(parameter=key if key in ('payload_bytes','local_timing_evidence')else'sn_'+key,
          when={'sn_'+k:v for k,v in(when or{}).items()},source=P,source_revision=SOURCES[P],**kw))
    r('local_timing_evidence',allowed=[])
    for key in REQUIRED:r(key,required=True)
    r('bidirectional_datagram',allowed=[True]);r('protocol_fragmentation',allowed=[False])
    r('broadcast_supported',{'discovery':'BROADCAST'},required=True,allowed=[True])
    r('packet_bytes',maximum_parameter='sn_network_packet_max')
    r('network_packet_max',{'binding_profile':'IBM_2013_ZIGBEE_APS'},maximum=60)
    r('transport',{'binding_profile':'IBM_2013_ZIGBEE_APS'},allowed=['ZIGBEE_APS'])
    for transport in ('UDP_IPV4','UDP_IPV6'):r('port',{'transport':transport},required=True)
    r('length_bytes',allowed=[1,3])
    r('length_value',{'length_bytes':1},maximum=255)
    r('length_value',{'length_bytes':3},minimum=4)
    r('packet_bytes',when_not={'sn_packet_kind':'ENCAPSULATED'},maximum=65535,equal_parameter='sn_length_value')
    r('packet_bytes',when_not={'sn_packet_kind':'ENCAPSULATED'},equal_expression={'sum':['sn_length_bytes',1,'sn_variable_bytes']},exact_decimal_equality=True)
    for key in ('packet_bytes','length_value','length_bytes','variable_bytes','msg_type'):r(key,required=True)
    for kind,code in KINDS.items():r('msg_type',{'packet_kind':kind},allowed=[code])
    for n,offset in ((1,1),(3,3)):
        octets=[dict(offset=offset,width=1,parameter='sn_msg_type'),dict(offset=0 if n==1 else 1,width=n if n==1 else 2,parameter='sn_length_value')]
        r('packet_hex',{'length_bytes':n},hex_bytes_parameter='sn_packet_bytes',hex_octets=octets)
        r('packet_hex',{'length_bytes':n,'packet_kind':'PUBLISH'},hex_octets=[dict(offset=n+1,width=1,parameter='sn_flags')])
    r('packet_hex',{'length_bytes':3},pattern=r'01(?:[0-9a-fA-F]{2})+')
    r('wireless_node_id_hex',hex_bytes_parameter='sn_wireless_node_id_bytes')
    for key in ('client_id','topic_name','topic_filter','short_topic','will_topic'):
        r(key,text_encoding='utf-8',encoded_bytes_parameter='sn_'+key+'_bytes',pattern=r'[^\x00\ud800-\udfff]*')
        r(key,when_present=['sn_'+key+'_bytes'],required=True,allow_empty_text=True,text_encoding='utf-8')
        r(key+'_bytes',when_present=['sn_'+key],required=True)
    r('client_id',text_encoding='utf-8',text_codepoints_parameter='sn_client_characters')
    r('client_characters',when_present=['sn_client_id'],required=True)
    for role,directions in [('CLIENT',['CLIENT_TO_GATEWAY','CLIENT_BROADCAST']),('GATEWAY',['GATEWAY_TO_CLIENT','GATEWAY_BROADCAST','GATEWAY_TO_FORWARDER']),('FORWARDER',['FORWARDER_TO_GATEWAY'])]:
        r('direction',{'endpoint_role':role},allowed=directions)
    for key in ('topic_name','short_topic','will_topic'):r(key,pattern=r'[^\x00+#\ud800-\udfff]*')
    r('topic_filter',pattern=r'(?:[^\x00/+#]*|\+)(?:/(?:[^\x00/+#]*|\+))*(?:/#)?|#')
    r('topic_filter_bytes',minimum=1)
    for kind in ('PUBLISH','SUBSCRIBE','UNSUBSCRIBE'):
        r('topic_kind',{'packet_kind':kind},required=True)
        for mode,value in [('NORMAL',0),('PREDEFINED',1),('SHORT',2)]:r('topic_type',{'packet_kind':kind,'topic_kind':mode},required=True,allowed=[value])
        for key in ('short_topic','short_topic_bytes'):r(key,{'packet_kind':kind,'topic_kind':'SHORT'},required=True)
    r('short_topic_bytes',allowed=[2])
    for kind in ('PUBLISH','SUBSCRIBE','UNSUBSCRIBE'):
        for mode in ('NORMAL','PREDEFINED'):
            if mode=='NORMAL'and kind!='PUBLISH':continue
            r('topic_id',{'packet_kind':kind,'topic_kind':mode},required=True,minimum=1,maximum=65534)
    for mode in ('NORMAL','PREDEFINED'):
        for key in ('mapping_source','mapping_client_ref','mapping_gateway_ref','mapping_known'):r(key,{'packet_kind':'PUBLISH','topic_kind':mode},required=True)
        r('mapping_known',{'packet_kind':'PUBLISH','topic_kind':mode},allowed=[True])
        r('mapping_client_ref',{'packet_kind':'PUBLISH','topic_kind':mode},equal_parameter='sn_client_ref')
        r('mapping_gateway_ref',{'packet_kind':'PUBLISH','topic_kind':mode},equal_parameter='sn_gateway_ref')
    for key in ('qos','dup','retain','msg_id','flags'):r(key,{'packet_kind':'PUBLISH'},required=True)
    r('qos',{'packet_kind':'PUBLISH','endpoint_role':'GATEWAY'},allowed=[0,1,2])
    r('topic_kind',{'packet_kind':'PUBLISH','qos':-1},allowed=['PREDEFINED','SHORT'])
    r('direction',{'packet_kind':'PUBLISH','qos':-1},allowed=['CLIENT_TO_GATEWAY'])
    for key in ('preconfigured_gateway_source','gateway_address'):r(key,{'packet_kind':'PUBLISH','qos':-1},required=True)
    for qos in (-1,0):r('msg_id',{'packet_kind':'PUBLISH','qos':qos},allowed=[0])
    for qos in (1,2):r('msg_id',{'packet_kind':'PUBLISH','qos':qos},minimum=1)
    r('dup',{'packet_kind':'PUBLISH','phase':'NEW'},allowed=[False])
    r('dup',{'packet_kind':'PUBLISH','phase':'RETRY'},allowed=[True])
    for qos in (-1,0,1,2):
        for dup in (False,True):
            for retain in (False,True):
                for topic,value in [('NORMAL',0),('PREDEFINED',1),('SHORT',2)]:
                    r('flags',{'packet_kind':'PUBLISH','qos':qos,'dup':dup,'retain':retain,'topic_kind':topic},allowed=[128*dup+32*(3 if qos==-1 else qos)+16*retain+value])
    r('variable_bytes',{'packet_kind':'PUBLISH'},equal_expression={'sum':[5,'payload_bytes']},exact_decimal_equality=True)
    r('payload_bytes',{'packet_kind':'PUBLISH'},required=True)
    for key in ('will','clean_session','flags','protocol_id','keepalive_s','client_id','client_id_bytes','client_characters'):
        r(key,{'packet_kind':'CONNECT'},required=True)
    r('protocol_id',{'packet_kind':'CONNECT'},allowed=[1])
    r('variable_bytes',{'packet_kind':'CONNECT'},equal_expression={'sum':[4,'sn_client_id_bytes']},exact_decimal_equality=True)
    for will in (False,True):
        for clean in (False,True):r('flags',{'packet_kind':'CONNECT','will':will,'clean_session':clean},allowed=[8*will+4*clean])
    for kind in ('WILLTOPIC','WILLTOPICUPD'):
        r('will_delete',{'packet_kind':kind},required=True)
        r('variable_bytes',{'packet_kind':kind,'will_delete':True},allowed=[0])
        r('packet_bytes',{'packet_kind':kind,'will_delete':True},allowed=[2])
        for key in ('flags','will_topic','will_topic_bytes','qos','retain'):r(key,{'packet_kind':kind,'will_delete':False},required=True)
        r('will_topic_bytes',{'packet_kind':kind,'will_delete':False},minimum=1)
        r('qos',{'packet_kind':kind,'will_delete':False},allowed=[0,1,2])
        for key in ('flags','will_topic','will_topic_bytes'):r(key,{'packet_kind':kind,'will_delete':True},allowed=[],text_encoding='utf-8'if key=='will_topic'else None)
        r('variable_bytes',{'packet_kind':kind,'will_delete':False},equal_expression={'sum':[1,'sn_will_topic_bytes']},exact_decimal_equality=True)
        for qos in (0,1,2):
            for retain in (False,True):r('flags',{'packet_kind':kind,'will_delete':False,'qos':qos,'retain':retain},allowed=[32*qos+16*retain])
    for kind in ('WILLMSG','WILLMSGUPD'):
        r('will_message_bytes',{'packet_kind':kind},required=True)
        r('variable_bytes',{'packet_kind':kind},equal_parameter='sn_will_message_bytes')
    fixed={'ADVERTISE':3,'SEARCHGW':1,'CONNACK':1,'WILLTOPICREQ':0,'WILLMSGREQ':0,'REGACK':5,'PUBACK':5,
        'PUBREC':2,'PUBREL':2,'PUBCOMP':2,'SUBACK':6,'UNSUBACK':2,'PINGRESP':0,'WILLTOPICRESP':1,'WILLMSGRESP':1}
    for kind,size in fixed.items():r('variable_bytes',{'packet_kind':kind},allowed=[size])
    for kind in ('CONNACK','REGACK','PUBACK','SUBACK','WILLTOPICRESP','WILLMSGRESP'):r('return_code',{'packet_kind':kind},required=True)
    for kind in ('REGISTER','REGACK','PUBACK','PUBREC','PUBREL','PUBCOMP','SUBSCRIBE','SUBACK','UNSUBSCRIBE','UNSUBACK'):
        r('msg_id',{'packet_kind':kind},required=True)
        if kind!='PUBACK':r('msg_id',{'packet_kind':kind},minimum=1)
    r('topic_id',{'packet_kind':'REGISTER','endpoint_role':'CLIENT'},allowed=[0],required=True)
    r('topic_id',{'packet_kind':'REGISTER','endpoint_role':'GATEWAY'},minimum=1,maximum=65534,required=True)
    for key in ('topic_name','topic_name_bytes'):r(key,{'packet_kind':'REGISTER'},required=True)
    r('topic_name_bytes',{'packet_kind':'REGISTER'},minimum=1)
    r('variable_bytes',{'packet_kind':'REGISTER'},equal_expression={'sum':[4,'sn_topic_name_bytes']},exact_decimal_equality=True)
    r('topic_id',{'packet_kind':'REGACK','return_code':0},minimum=1,maximum=65534,required=True)
    r('topic_id',{'packet_kind':'SUBACK','return_code':0,'wildcard_subscription':True},allowed=[0],required=True)
    r('topic_id',{'packet_kind':'SUBACK','return_code':0,'wildcard_subscription':False},minimum=1,maximum=65534)
    r('flags',{'packet_kind':'SUBACK'},required=True)
    r('qos',{'packet_kind':'SUBACK'},required=True,allowed=[0,1,2])
    for qos in (0,1,2):r('flags',{'packet_kind':'SUBACK','qos':qos},allowed=[32*qos])
    for kind in ('SUBSCRIBE','UNSUBSCRIBE'):
        r('flags',{'packet_kind':kind},required=True)
        r('topic_filter',{'packet_kind':kind,'topic_kind':'NORMAL'},required=True)
        r('variable_bytes',{'packet_kind':kind,'topic_kind':'NORMAL'},equal_expression={'sum':[3,'sn_topic_filter_bytes']},exact_decimal_equality=True)
        for topic in ('PREDEFINED','SHORT'):r('variable_bytes',{'packet_kind':kind,'topic_kind':topic},allowed=[5])
    r('qos',{'packet_kind':'SUBSCRIBE'},allowed=[0,1,2],required=True)
    r('dup',{'packet_kind':'SUBSCRIBE'},required=True)
    for qos in (0,1,2):
        for dup in (False,True):
            for topic,value in [('NORMAL',0),('PREDEFINED',1),('SHORT',2)]:r('flags',{'packet_kind':'SUBSCRIBE','qos':qos,'dup':dup,'topic_kind':topic},allowed=[128*dup+32*qos+value])
    for topic,value in [('NORMAL',0),('PREDEFINED',1),('SHORT',2)]:r('flags',{'packet_kind':'UNSUBSCRIBE','topic_kind':topic},allowed=[value])
    for kind in ('REGACK','PUBACK','PUBREC','PUBREL','PUBCOMP','SUBACK','UNSUBACK'):
        for key in ('request_msg_id','request_client_ref','request_gateway_ref','pending_match'):r(key,{'packet_kind':kind},required=True)
        r('msg_id',{'packet_kind':kind},equal_parameter='sn_request_msg_id')
        r('request_client_ref',{'packet_kind':kind},equal_parameter='sn_client_ref')
        r('request_gateway_ref',{'packet_kind':kind},equal_parameter='sn_gateway_ref')
        r('pending_match',{'packet_kind':kind},allowed=[True])
    r('topic_id',{'packet_kind':'PUBACK'},equal_parameter='sn_request_topic_id',required=True)
    r('request_topic_id',{'packet_kind':'PUBACK'},required=True)
    for kind in ('CONNECT','SUBSCRIBE','UNSUBSCRIBE','WILLTOPIC','WILLMSG','WILLTOPICUPD','WILLMSGUPD'):
        r('direction',{'packet_kind':kind},allowed=['CLIENT_TO_GATEWAY'])
    for kind in ('CONNACK','WILLTOPICREQ','WILLMSGREQ','SUBACK','UNSUBACK','WILLTOPICRESP','WILLMSGRESP'):
        r('direction',{'packet_kind':kind},allowed=['GATEWAY_TO_CLIENT'])
    r('direction',{'packet_kind':'ADVERTISE'},allowed=['GATEWAY_BROADCAST'])
    r('gateway_server_connected',{'packet_kind':'ADVERTISE'},required=True,allowed=[True])
    for key in ('gateway_id','advertise_s'):r(key,{'packet_kind':'ADVERTISE'},required=True)
    r('direction',{'packet_kind':'SEARCHGW'},allowed=['CLIENT_BROADCAST'])
    r('radius',{'packet_kind':'SEARCHGW'},required=True)
    for kind in ('ADVERTISE','SEARCHGW','GWINFO'):r('broadcast_supported',{'packet_kind':kind},required=True,allowed=[True])
    r('gateway_id',{'packet_kind':'GWINFO'},required=True)
    r('gwinfo_address_present',{'packet_kind':'GWINFO'},required=True)
    r('gwinfo_address_present',{'packet_kind':'GWINFO','endpoint_role':'GATEWAY'},allowed=[False])
    r('gwinfo_address_present',{'packet_kind':'GWINFO','endpoint_role':'CLIENT'},allowed=[True])
    r('variable_bytes',{'packet_kind':'GWINFO','gwinfo_address_present':False},allowed=[1])
    for key in ('gateway_address','gateway_address_bytes'):r(key,{'packet_kind':'GWINFO','gwinfo_address_present':True},required=True)
    r('variable_bytes',{'packet_kind':'GWINFO','gwinfo_address_present':True},equal_expression={'sum':[1,'sn_gateway_address_bytes']},exact_decimal_equality=True)
    r('client_id_present',{'packet_kind':'PINGREQ'},required=True)
    r('variable_bytes',{'packet_kind':'PINGREQ','client_id_present':False},allowed=[0])
    r('client_id_present',{'packet_kind':'PINGREQ','client_state':'AWAKE'},allowed=[True])
    for key in ('client_id','client_id_bytes','client_characters'):r(key,{'packet_kind':'PINGREQ','client_id_present':True},required=True)
    r('variable_bytes',{'packet_kind':'PINGREQ','client_id_present':True},equal_parameter='sn_client_id_bytes')
    r('duration_present',{'packet_kind':'DISCONNECT'},required=True)
    r('variable_bytes',{'packet_kind':'DISCONNECT','duration_present':False},allowed=[0])
    r('variable_bytes',{'packet_kind':'DISCONNECT','duration_present':True},allowed=[2])
    r('sleep_s',{'packet_kind':'DISCONNECT','duration_present':True},required=True)
    r('direction',{'packet_kind':'DISCONNECT','duration_present':True},allowed=['CLIENT_TO_GATEWAY'])
    r('sleep_s',{'packet_kind':'DISCONNECT','duration_present':False},allowed=[])
    r('watchdog_duration_s',{'client_state':'ACTIVE'},equal_parameter='sn_keepalive_s')
    r('watchdog_duration_s',{'client_state':'ASLEEP'},equal_parameter='sn_sleep_s')
    r('watchdog_bound_s',minimum_parameter='sn_watchdog_duration_s')
    r('timer_source',when_present=['sn_watchdog_bound_s'],required=True)
    for lo,hi,multiplier in ((0,60,1.5),(60,None,1.1)):
        condition={'sn_watchdog_duration_s':[lo,hi]}
        if lo==0:r('watchdog_bound_s',{'timer_profile':'IBM_1_2_RECOMMENDED'},when_half_open_ranges=condition,equal_expression={'product':['sn_watchdog_duration_s',multiplier]},exact_decimal_equality=True)
        else:r('watchdog_bound_s',{'timer_profile':'IBM_1_2_RECOMMENDED'},when_greater_than={'sn_watchdog_duration_s':60},equal_expression={'product':['sn_watchdog_duration_s',multiplier]},exact_decimal_equality=True)
    r('retry_attempt',maximum_parameter='sn_retry_limit')
    r('timer_source',{'timer_profile':'REGISTERED'},required=True)
    r('advertise_s',{'timer_profile':'IBM_1_2_RECOMMENDED'},exclusive_minimum=900)
    r('wait_s',{'timer_profile':'IBM_1_2_RECOMMENDED'},exclusive_minimum=300)
    r('retry_s',{'timer_profile':'IBM_1_2_RECOMMENDED'},minimum=10,maximum=15)
    r('retry_limit',{'timer_profile':'IBM_1_2_RECOMMENDED'},minimum=3,maximum=5)
    r('advertise_misses',{'timer_profile':'IBM_1_2_RECOMMENDED'},minimum=2,maximum=3)
    r('backend_connections',{'gateway_kind':'TRANSPARENT'},minimum_parameter='sn_active_clients')
    r('backend_connections',{'gateway_kind':'TRANSPARENT','qos_minus1_supported':True},minimum_expression={'sum':['sn_active_clients',1]})
    r('backend_connections',{'gateway_kind':'AGGREGATING'},when_positive=['sn_active_clients'],minimum=1)
    r('gateway_backend_source',when_positive=['sn_active_clients'],required=True)
    r('length_bytes',{'packet_kind':'ENCAPSULATED'},allowed=[1])
    r('length_value',{'packet_kind':'ENCAPSULATED'},maximum=255,equal_expression={'sum':[3,'sn_wireless_node_id_bytes']},exact_decimal_equality=True)
    r('packet_bytes',{'packet_kind':'ENCAPSULATED'},equal_expression={'sum':['sn_length_value','sn_inner_packet_bytes']},exact_decimal_equality=True)
    r('variable_bytes',{'packet_kind':'ENCAPSULATED'},equal_expression={'sum':[1,'sn_wireless_node_id_bytes','sn_inner_packet_bytes']},exact_decimal_equality=True)
    for key in ('wireless_node_id_hex','wireless_node_id_bytes','inner_packet_bytes','inner_msg_type','forward_ctrl'):r(key,{'packet_kind':'ENCAPSULATED'},required=True)
    r('inner_msg_type',{'packet_kind':'ENCAPSULATED'},allowed=[v for k,v in KINDS.items()if k!='ENCAPSULATED'])
    r('direction',{'packet_kind':'ENCAPSULATED'},allowed=['FORWARDER_TO_GATEWAY','GATEWAY_TO_FORWARDER'])
    r('forward_ctrl',{'packet_kind':'ENCAPSULATED'},maximum=3,equal_parameter='sn_forward_radius')
    r('packet_hex',{'packet_kind':'ENCAPSULATED'},hex_octets=[dict(offset=2,width=1,parameter='sn_forward_ctrl')])
    r('forward_radius',{'packet_kind':'ENCAPSULATED','direction':'GATEWAY_TO_FORWARDER'},required=True)
    return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['sn_'+k for k in REQUIRED],
        native_parameter_prefixes=['sn_'],parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
        mechanisms={'transport':['EXPLICIT_BIDIRECTIONAL_DATAGRAM','NO_MQTT_SN_FRAGMENTATION'],
         'framing':['ONE_OR_THREE_OCTET_LENGTH','FORWARDER_PREFIX_LENGTH_EXCEPTION'],
         'delivery':['CLIENT_QOS_MINUS1_0_1_2','PER_CLIENT_GATEWAY_TOPIC_MAPPING','SINGLE_OUTSTANDING_CLIENT_EXCHANGES'],
         'session':['PERSISTENT_SUBSCRIPTIONS_AND_WILL','GATEWAY_DISCOVERY','ASLEEP_AWAKE_BUFFER_DELIVERY']})

def fields():
    result=[]
    conditional={'protocol_id':[({'version':'V1_2'},1)],
      'advertise_misses':[({'timer_profile':'IBM_1_2_RECOMMENDED'},2)],
      'search_delay_s':[({'timer_profile':'IBM_1_2_RECOMMENDED'},5)],
      'gwinfo_delay_s':[({'timer_profile':'IBM_1_2_RECOMMENDED'},5)],
      'retry_s':[({'timer_profile':'IBM_1_2_RECOMMENDED'},10)],
      'retry_limit':[({'timer_profile':'IBM_1_2_RECOMMENDED'},3)],
      'topic_type':[({'topic_kind':k},v)for k,v in [('NORMAL',0),('PREDEFINED',1),('SHORT',2)]],
      'msg_type':[({'packet_kind':k},v)for k,v in KINDS.items()]}
    for spec in DECLARATIONS:
        key=spec['key'][3:];item={k:v for k,v in spec.items()if v is not None}
        item.update(label=key.replace('_',' '),category='timing'if spec.get('unit')=='s'else'qos',scope='route',
          editable=True,required=key in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
          validation_relevant=True,simulation_relevant=False)
        if key in conditional:item.update(default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE',
            conditional_defaults=[dict(when={'sn_'+k:v for k,v in when.items()},value=value,source=P,source_revision=SOURCES[P])for when,value in conditional[key]])
        result.append(item)
    return result
