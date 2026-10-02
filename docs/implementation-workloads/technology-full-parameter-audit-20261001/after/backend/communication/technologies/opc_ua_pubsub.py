"""OPC UA PubSub is edition/mapping/bearer dependent, not always UDP."""
P14='https://reference.opcfoundation.org/specs/OPC-10000-14/full'
EDITION='OPC10000_14_1.05.06'
SOURCES={P14:'OPC10000-14 v1.05.06 current publisher HTML read2026-10-02: common configuration, UADP/JSON, sequences, UDP/DTLS/Ethernet/MQTT transport and topic tables. AnnexB mappings informative, not universal transport guarantees.'}
UINT32=4294967295
BINDINGS=('UDP','DTLS','ETHERNET','MQTT','REGISTERED')
TOPICS=('data','metadata','application','endpoints','status','connection','action-request','action-response','action-metadata','action-responder')
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,u=None,opts=None,integer=False):
 DECLARATIONS.append(dict(key='ps_'+k,type=t,description=meaning,min=lo,max=hi,unit=u,options=opts,source=P14,source_revision=SOURCES[P14],integer=integer))
for k,meaning,opts in[
 ('edition','Actual PubSub mapping edition; distinct current Client/Server Part4/6 edition.',[EDITION]),
 ('binding','Actual transport selection; no physical Ethernet/IP/UDP imposed by application label.',list(BINDINGS)),
 ('encoding','Actual message mapping, UADP binary or JSON; not inferred from bearer.', ['UADP','JSON']),
 ('role','Actual Publisher or Subscriber; identities/addresses have different scope.',['PUBLISHER','SUBSCRIBER']),
 ('dataset_kind','Actual cyclic data, acyclic events, or heartbeat, with distinct key-frame rules.',['CYCLIC','ACYCLIC','HEARTBEAT']),
 ('publisher_type','Actual configured PublisherId type; integers preserved as decimal text, JSON identifier rendered as text.',['UINT8','UINT16','UINT32','UINT64','STRING']),
 ('assignment','Actual WriterGroupId external versus internal allocator range.',['EXTERNAL','INTERNAL']),
 ('dataset_assignment','Actual DataSetWriterId allocator, independent WriterGroupId allocator.',['EXTERNAL','INTERNAL']),
 ('delivery','Actual RequestedDeliveryGuarantee; broker QoS does not prove functional processing.',['AtMostOnce','BestEffort','AtLeastOnce','ExactlyOnce']),
 ('ordering','Actual DataSetOrdering, default Undefined does not imply fixed layout.',['Undefined','AscendingWriterId','AscendingWriterIdSingle']),
 ('network_mode','Actual UDP addressing mode; DTLS allows only unicast.',['UNICAST','MULTICAST','BROADCAST']),
 ('ip_version','Actual network IP version, absent on direct Ethernet.',['IPv4','IPv6']),
 ('budget_layer','Actual layer defining MTU budget; IP packet differs whole Ethernet frame or broker packet.',['IP_PACKET','COMPLETE_LINK_FRAME','BROKER_PACKET','REGISTERED']),
 ('mqtt_version','Configured MQTT version selection versus actual negotiated version.',['BestAvailable','3.1.1','5.0']),
 ('mqtt_actual_version','Actual broker connection MQTT version, not automatically BestAvailable.',['3.1.1','5.0']),
 ('topic_kind','Actual standard topic message class, with class-dependent RETAIN. ',list(TOPICS)),
 ('security_mode','Actual NetworkMessage security mode, separate DTLS/TLS and key-service authorization.',['None','Sign','SignAndEncrypt']),
 ('sequence_phase','Actual first/new transmit sequence or receiver comparison, not UASC chunk token sequence.',['FIRST','NEXT','RECEIVE']),
 ('sequence_result','Actual receiver freshness classification under modular half-range rules.',['NEW','OLD','INVALID']),
 ('outcome','Actual data/action outcome, separate metadata/transport validity.',['ACCEPTED','REJECTED','PENDING','UNKNOWN']),
]:d(k,'select',meaning,opts=opts)
for k,meaning in[
 ('profile_uri','Actual TransportProfileUri selects both transport and message mapping.'),
 ('address','Actual configured transport address, not a generic default multicast or localhost destination.'),
 ('writer_address','Actual WriterGroup UDP unicast send address; must be absent for multicast/broadcast.'),
 ('interface','Actual network interface; required for multicast/broadcast when multiple interfaces exist.'),
 ('publisher_id','Actual PublisherId, nonzero unsigned integer as lossless decimal text or nonempty string.'),
 ('publisher_filter','Actual expected PublisherId for received-message filtering, not source IP alone.'),
 ('metadata_source','Actual DataSetMetaData/field types/configuration version and reader agreement.'),
 ('profile_source','Actual edition, transport profile, address/identity and mapping source.'),
 ('peer_source','Actual Publisher/Subscriber/broker implementation limits and capabilities.'),
 ('physical_source','Actual chosen bearer, MTU/header overhead/topology and link-service evidence.'),
 ('security_source','Actual message/transport/key-service policy and trust evidence; not tokens or secret keys.'),
 ('schedule_source','Actual publish/sampling/offset/delta/keyframe/event/repeat and network/broker service bounds.'),
 ('acceptance_source','Actual correlated dataset/action result, status and source-age acceptance.'),
 ('registered_source','Actual separately registered transport, including informative AMQP mapping when selected.'),
 ('topic_prefix','Actual MQTT topic convention prefix; literature proposal opcua.'),
 ('topic','Actual publish topic, not subscription wildcard filter.'),
 ('content_type','Actual MQTT5 content type identifies binary UADP versus JSON.'),
 ('security_group_id','Actual SecurityGroup scope for non-None message security.'),
 ('flags1_hex','Actual UADP DataSetFlags1 byte as hex, decoded field encoding/validity/sequence presence.'),
 ('publish_offsets_ms_json','Actual ordered PublishingOffset array in milliseconds as JSON numbers; negative values mark not configured, not zero-latency proof.'),
]:d(k,'text',meaning)
for k,meaning,lo,hi,u,integer in[
 ('writer_group_id','Actual UInt16 WriterGroupId, zero is null not an assigned group.',1,65535,None,True),
 ('dataset_writer_id','Actual UInt16 DataSetWriterId, explicit metadata identity.',1,65535,None,True),
 ('keyframe_count','Cyclic keyframe multiplier>=1, acyclic0, heartbeat1; not CAN retry count.',0,UINT32,None,True),
 ('publish_ms','Actual PublishingInterval,0 only when every writer is acyclic/keyframe0; no universal100ms.',0,None,'ms',False),
 ('keepalive_ms','Actual keepalive interval, strictly positive and at least PublishingInterval.',0,None,'ms',False),
 ('receive_timeout_ms','Actual maximum time between new DataSetMessages; heartbeat/keepalive reset as defined, not request timeoutHint.',0,None,'ms',False),
 ('priority','Actual WriterGroup relative priority Byte, not VLAN PCP.',0,255,None,True),
 ('max_network_bytes','Actual MaxNetworkMessageSize includes padding/signature, excludes added bearer headers.',0,UINT32,'byte',True),
 ('network_bytes','Actual complete encoded NetworkMessage including security/padding; not application object bytes.',0,UINT32,'byte',True),
 ('headers_bytes','Actual bearer added headers/FCS under selected transport; not always Ethernet22+IPv420+UDP8.',0,None,'byte',True),
 ('wire_bytes','Actual NetworkMessage plus selected bearer overhead, no physical baud inferred.',0,None,'byte',True),
 ('path_mtu','Actual path MTU at the explicitly declared layer, not inherited CAN payload or unconditional1500.',1,None,'byte',True),
 ('ip_header_bytes','Actual IP header bytes incl selected options/extensions, distinct MAC/FCS/UDP.',20,None,'byte',True),
 ('ip_packet_bytes','Actual whole IP packet=NetworkMessage+IPheader+UDP8; excludes Ethernet/FCS.',0,None,'byte',True),
 ('transport_overhead_bytes','Actual DTLS record/header/tag/padding bytes between UA message and UDP; plainUDP has zero.',0,None,'byte',True),
 ('port','Actual UDP/DTLS destination port; source proposals4840/4843, other ports allowed.',1,65535,None,True),
 ('discovery_max_bytes','Actual DiscoveryMaxMessageSize, transport-specific proposal4096 only UDP.',0,UINT32,'byte',True),
 ('discovery_announce_s','Actual datagram discovery announcement period seconds; source default0 probe-response-only.',0,UINT32,'s',True),
 ('repeat_count','Actual datagram MessageRepeatCount Byte; source default0 disables repeat, not retry-limitCAN.',0,255,None,True),
 ('repeat_delay_ms','Actual delay between datagram repeats; ignored when repeat_count0.',0,None,'ms',False),
 ('sampling_offset_ms','Actual UADP creation offset within publish cycle; any negative means unspecified.',None,None,'ms',False),
 ('receive_offset_ms','Actual UADP expected receive offset, negative means unspecified; not measured delay.',None,None,'ms',False),
 ('processing_offset_ms','Actual UADP application processing offset, negative means unspecified.',None,None,'ms',False),
 ('publish_offsets_count','Actual count of the ordered publishing-offset array; no invented offset per packet.',0,None,None,True),
 ('uadp_version','Actual four-bit UADP NetworkMessage version; current mapping version1.',0,15,None,True),
 ('ether_type','Actual direct Ethernet UADP EtherType0xB62C, not IPv4/UDP framing.',0,65535,None,True),
 ('vlan','Actual direct Ethernet VID where explicitly configured, not generic application parameter.',0,4094,None,True),
 ('pcp','Actual direct Ethernet Priority Code Point, distinct WriterGroup priority.',0,7,None,True),
 ('interface_count','Actual available network interfaces for multicast interface selection.',1,None,None,True),
 ('dtls_version','Actual DTLS version for selected transport; current mapping requires1.3.',None,None,None,False),
 ('mqtt_qos','Actual MQTT publish/subscribe QoS mapping for delivery guarantee.',0,2,None,True),
 ('mqtt_keepalive_s','Actual connection Keep Alive separate per-writer keepalive milliseconds.',0,65535,'s',True),
 ('max_group_keepalive_ms','Actual maximum KeepAliveTime across writers on broker connection.',0,None,'ms',False),
 ('broker_packet_limit','Actual negotiated broker/device complete MQTT packet limit, not PubSub payload65507.',1,None,'byte',True),
 ('mqtt_packet_bytes','Actual encoded MQTT packet with all headers/properties/topic and UA payload.',1,None,'byte',True),
 ('configured_dataset_bytes','Actual UADP ConfiguredSize,0 dynamic; undersize marks dataset invalid rather than silent truncation.',0,65535,'byte',True),
 ('dataset_bytes','Actual encoded DataSetMessage excluding zero padding; no universal scalar payload limit.',0,None,'byte',True),
 ('dataset_padded_bytes','Actual occupied size including configured zero padding.',0,None,'byte',True),
 ('network_message_number','Actual UADP message ordinal,0 dynamic; fixed one-message layout requires1.',0,65535,None,True),
 ('dataset_offset','Actual UADP byte position from NetworkMessage start;0 dynamic.',0,65535,'byte',True),
 ('network_messages_per_interval','Actual messages generated by group per interval, at most65535.',1,65535,None,True),
 ('version_major','Actual DataSet configuration major version, zero for heartbeat.',0,UINT32,None,True),
 ('version_minor','Actual DataSet configuration minor version, zero for heartbeat.',0,UINT32,None,True),
 ('sequence_width','Actual sequence-header width16 or32, selected by encoding/header context.',16,32,'bit',True),
 ('sequence','Actual UInt16/UADP or UInt32/JSON sequence, exact wrap arithmetic.',0,UINT32,None,True),
 ('previous_sequence','Actual last sent or last processed sequence for same writer/group context.',0,UINT32,None,True),
 ('sequence_distance','Exact(new-1-last) modulo2^N, not raw subtraction or UASC lifetime rule.',0,UINT32,None,True),
 ('field_encoding','Decoded DataSetFlags1 field encoding0Variant/1RawData/2DataValue;3reserved.',0,2,None,True),
 ('age_ms','Actual accepted source data age, distinct receive-timeout/network latency.',0,None,'ms',False),
 ('freshness_limit_ms','Actual application accepted data-age limit, no universal PubSub standard.',0,None,'ms',False),
]:d(k,'number',meaning,lo,hi,u,integer=integer)
for k,meaning in[
 ('no_ip_fragmentation','Explicit chosen requirement to fit NetworkMessage and IP/UDP headers in actual IP MTU.'),
 ('membership_reported','Actual receiver IGMP/MLD membership setup for UDP multicast.'),
 ('metadata_matches','Actual received metadata/version/type compatibility, not a missing-header guess.'),
 ('dataset_valid','Actual DataSet valid flag; oversized fixed ConfiguredSize invalidates message.'),
 ('sequence_present','Actual sequence enabled; absence is not sequence0 and changes new-message detection.'),
 ('retain','Actual MQTT RETAIN class-specific; data override requires explicit property.'),
 ('data_retain_override','Actual configured data RETAIN override, not metadata/default inference.'),
 ('tls','Actual MQTT TLS connection state, separate end-to-end UADP message security.'),
 ('data_accepted','Actual application consumption/action accepted, not merely authenticated delivery.'),
]:d(k,'boolean',meaning)
REQUIRED=('edition','binding','encoding','role','profile_uri','address','publisher_type','publisher_id','profile_source','peer_source','physical_source','security_source','schedule_source','acceptance_source','metadata_source')
REMOVED={k:'No universal OPC-UA-PubSub '+k+'; actual selected mapping/bearer/device-specific property replaces foreign shared assumptions.'for k in('bitrate','mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','rate_limit_bit_s','retry_limit','retransmission_enabled','retransmission_rate','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms','sync_method')}
def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter=k if k in('bitrate_bps','local_timing_evidence','payload_bytes')else'ps_'+k,when={'ps_'+a:b for a,b in(w or{}).items()},source=P14,source_revision=SOURCES[P14],**kw))
 for k in REQUIRED:r(k,required=True)
 for k in('bitrate_bps','local_timing_evidence'):r(k,allowed=[])
 r('registered_source',{'binding':'REGISTERED'},required=True)
 r('uadp_version',{'encoding':'UADP'},allowed=[1])
 r('publish_offsets_ms_json',{'encoding':'UADP'},json_number_array={'count_parameter':'ps_publish_offsets_count'})
 r('publish_offsets_count',when_present=['ps_publish_offsets_ms_json'],required=True)
 for kind,width in(('UINT8',8),('UINT16',16),('UINT32',32),('UINT64',64)):
  r('publisher_id',{'publisher_type':kind},pattern=r'0*[1-9][0-9]*',integer_text_maximum=2**width-1)
 for kind,count in(('ACYCLIC',0),('HEARTBEAT',1)):r('keyframe_count',{'dataset_kind':kind},allowed=[count])
 r('keyframe_count',{'dataset_kind':'CYCLIC'},minimum=1)
 r('keyframe_count',{'publish_ms':0},allowed=[0]);r('keepalive_ms',minimum_parameter='ps_publish_ms',exclusive_minimum=0)
 r('writer_group_id',{'assignment':'EXTERNAL'},maximum=32767);r('writer_group_id',{'assignment':'INTERNAL'},minimum=32768)
 r('dataset_writer_id',{'dataset_assignment':'EXTERNAL'},maximum=32767);r('dataset_writer_id',{'dataset_assignment':'INTERNAL'},minimum=32768)
 for k in('version_major','version_minor'):r(k,{'dataset_kind':'HEARTBEAT'},allowed=[0])
 r('network_bytes',maximum_parameter='ps_max_network_bytes');r('max_network_bytes',when_present=['ps_network_bytes'],required=True)
 r('network_bytes',minimum_parameter='payload_bytes')
 r('wire_bytes',equal_expression={'sum':['ps_network_bytes','ps_headers_bytes']})
 for k in('network_bytes','headers_bytes'):r(k,when_present=['ps_wire_bytes'],required=True)
 for b in('UDP','DTLS','ETHERNET'):r('encoding',{'binding':b},allowed=['UADP'])
 for b in('UDP','DTLS'):
  w={'binding':b};r('port',w,required=True);r('ip_version',w,required=True)
  r('address',w,pattern=r'opc\.udp://.+'if b=='UDP'else r'opc\.dtls://.+')
  r('wire_bytes',w,maximum=65535)
  for k in('network_bytes','max_network_bytes'):r(k,w,maximum=65535)
  r('ip_header_bytes',{**w,'ip_version':'IPv4'},minimum=20)
  r('ip_header_bytes',{**w,'ip_version':'IPv6'},minimum=40)
  r('ip_packet_bytes',w,equal_expression={'sum':['ps_network_bytes','ps_ip_header_bytes','ps_transport_overhead_bytes',8]})
  for k in('network_bytes','ip_header_bytes','transport_overhead_bytes'):r(k,w,when_present=['ps_ip_packet_bytes'],required=True)
  if b=='UDP':r('transport_overhead_bytes',w,allowed=[0])
  r('budget_layer',{**w,'no_ip_fragmentation':True},allowed=['IP_PACKET'],required=True)
  r('ip_packet_bytes',{**w,'no_ip_fragmentation':True},maximum_parameter='ps_path_mtu',required=True)
  r('path_mtu',{**w,'no_ip_fragmentation':True},required=True)
  for k in('ether_type','vlan','pcp'):r(k,w,allowed=[])
 r('network_mode',{'binding':'DTLS'},allowed=['UNICAST'],required=True);r('dtls_version',{'binding':'DTLS'},allowed=[1.3],required=True)
 for mode in('MULTICAST','BROADCAST'):
  w={'binding':'UDP','network_mode':mode};r('writer_address',w,allowed=[])
  r('interface',w,when_greater_than={'ps_interface_count':1},required=True)
 r('membership_reported',{'binding':'UDP','network_mode':'MULTICAST','role':'SUBSCRIBER'},allowed=[True],required=True)
 r('writer_address',{'binding':'UDP','network_mode':'UNICAST','role':'PUBLISHER'},required=True)
 w={'binding':'ETHERNET'};r('address',w,pattern=r'opc\.eth://.+');r('ether_type',w,allowed=[0xB62C],required=True);r('wire_bytes',w,maximum=1522)
 r('budget_layer',w,allowed=['COMPLETE_LINK_FRAME'])
 for k in('ip_version','port','ip_header_bytes','ip_packet_bytes','dtls_version','mqtt_version','mqtt_qos'):r(k,w,allowed=[])
 w={'binding':'MQTT'};r('mqtt_actual_version',w,required=True)
 for version in('3.1.1','5.0'):r('mqtt_actual_version',{**w,'mqtt_version':version},allowed=[version])
 for delivery,qos in(('AtMostOnce',0),('BestEffort',0),('AtLeastOnce',1),('ExactlyOnce',2)):r('mqtt_qos',{**w,'delivery':delivery},allowed=[qos])
 r('topic',w,pattern=r'[^+#\x00]+')
 r('mqtt_packet_bytes',w,maximum_parameter='ps_broker_packet_limit',minimum_parameter='ps_network_bytes')
 r('broker_packet_limit',w,when_present=['ps_mqtt_packet_bytes'],required=True)
 for encoding,mime in(('UADP','application/opcua+uadp'),('JSON','application/json')):r('content_type',{**w,'mqtt_actual_version':'5.0','encoding':encoding},allowed=[mime])
 for kind in TOPICS:
  if kind!='data':r('retain',{**w,'topic_kind':kind},allowed=[kind not in('action-request','action-response')])
 r('data_retain_override',{**w,'topic_kind':'data','retain':True},allowed=[True],required=True)
 r('mqtt_keepalive_s',w,when_positive=['ps_max_group_keepalive_ms'],exclusive_minimum_expression={'product':['ps_max_group_keepalive_ms',.001]})
 r('budget_layer',w,allowed=['BROKER_PACKET'])
 for k in('dtls_version','writer_address','ether_type','vlan','pcp','ip_version','port','ip_header_bytes','ip_packet_bytes'):r(k,w,allowed=[])
 for mode in('Sign','SignAndEncrypt'):r('security_group_id',{'security_mode':mode},required=True)
 r('sequence_width',allowed=[16,32])
 r('sequence_width',when_present=['ps_sequence'],required=True)
 r('sequence',maximum_expression={'subtract':[{'power':[2,'ps_sequence_width']},1]})
 r('previous_sequence',maximum_expression={'subtract':[{'power':[2,'ps_sequence_width']},1]})
 r('sequence',{'sequence_phase':'FIRST'},allowed=[0])
 r('sequence',{'sequence_phase':'NEXT'},equal_expression={'integer_remainder':[{'sum':['ps_previous_sequence',1]},{'power':[2,'ps_sequence_width']}]})
 for k in('previous_sequence','sequence_width'):r(k,{'sequence_phase':'NEXT'},required=True)
 r('sequence_distance',{'sequence_phase':'RECEIVE'},equal_expression={'integer_remainder':[{'subtract':[{'subtract':['ps_sequence',1]},'ps_previous_sequence']},{'power':[2,'ps_sequence_width']}]})
 for k in('sequence_width','sequence','previous_sequence','sequence_distance','sequence_result'):r(k,{'sequence_phase':'RECEIVE'},required=True)
 for width in(16,32):
  w={'sequence_phase':'RECEIVE','sequence_width':width};lo=2**(width-2);hi=2**width-lo
  r('sequence_result',w,when_ranges={'ps_sequence_distance':[0,lo-1]},allowed=['NEW'])
  r('sequence_result',w,when_ranges={'ps_sequence_distance':[lo,hi]},allowed=['INVALID'])
  r('sequence_result',w,when_ranges={'ps_sequence_distance':[hi+1,2**width-1]},allowed=['OLD'])
 r('sequence_width',{'encoding':'UADP'},allowed=[16]);r('sequence_width',{'encoding':'JSON'},allowed=[32])
 r('publisher_id',{'role':'SUBSCRIBER'},equal_parameter='ps_publisher_filter')
 r('publisher_filter',{'role':'SUBSCRIBER'},required=True)
 r('flags1_hex',{'encoding':'UADP'},pattern=r'[0-9A-Fa-f]{2}',integer_bitfields=[dict(offset=0,width=1,parameter='ps_dataset_valid',boolean=True),dict(offset=1,width=2,parameter='ps_field_encoding'),dict(offset=3,width=1,parameter='ps_sequence_present',boolean=True)])
 r('dataset_padded_bytes',{'encoding':'UADP'},when_positive=['ps_configured_dataset_bytes'],equal_parameter='ps_configured_dataset_bytes')
 r('dataset_padded_bytes',{'encoding':'UADP','configured_dataset_bytes':0},equal_parameter='ps_dataset_bytes')
 r('dataset_bytes',{'dataset_valid':True},when_positive=['ps_configured_dataset_bytes'],maximum_parameter='ps_configured_dataset_bytes')
 r('dataset_offset',maximum_parameter='ps_network_bytes')
 for k in('configured_dataset_bytes','dataset_padded_bytes','dataset_offset','network_message_number','flags1_hex','field_encoding','uadp_version','sampling_offset_ms','receive_offset_ms','processing_offset_ms','publish_offsets_ms_json','publish_offsets_count'):r(k,{'encoding':'JSON'},allowed=[])
 for k in('metadata_matches','dataset_valid'):r(k,{'data_accepted':True},allowed=[True],required=True)
 r('outcome',{'data_accepted':True},allowed=['ACCEPTED'],required=True)
 r('age_ms',maximum_parameter='ps_freshness_limit_ms');r('freshness_limit_ms',when_present=['ps_age_ms'],required=True)
 return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['ps_'+k for k in REQUIRED],native_parameter_prefixes=['ps_'],parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
  physical_layer_profile_id='explicit_pubsub_transport_mapping_and_bearer',medium_access_model='UADP_JSON_ON_ACTUAL_DATAGRAM_OR_BROKER',arbitration_model_id='ACTUAL_WRITER_GROUP_AND_BEARER_SERVICE',
  mechanisms={'framing':['TRANSPORT_QUALIFIED_NETWORKMESSAGE_LIMITS','METADATA_QUALIFIED_UADP_JSON'],
   'delivery':['CYCLIC_KEYFRAME_DELTA_ACYCLIC_EVENTS','MODULAR_SEQUENCE_AND_RECEIVE_MONITORING','BROKER_QOS_DISTINCT_FUNCTIONAL_ACCEPTANCE'],
   'qualification':['NO_CAN_ETHERNET_UDP_RATE_FALLBACK','LOSSLESS_PUBLISHER_ID_AND_EXPLICIT_SECURITY_SCOPE']})
def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][3:];item={key:value for key,value in spec.items()if value is not None}
  item.update(label=k.replace('_',' '),category='timing'if spec.get('unit')in('ms','s')else'communication',scope='route',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  if k=='edition':item.update(default=EDITION,default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE')
  conditions=[]
  if k=='port':conditions=[({'ps_binding':'UDP'},4840),({'ps_binding':'DTLS'},4843)]
  if k=='discovery_max_bytes':conditions=[({'ps_binding':'UDP'},4096)]
  if k in('discovery_announce_s','repeat_count'):conditions=[({'ps_binding':b},0)for b in('UDP','DTLS','ETHERNET')]
  if k=='uadp_version':conditions=[({'ps_encoding':'UADP'},1)]
  if k=='ether_type':conditions=[({'ps_binding':'ETHERNET'},0xB62C)]
  if k in('configured_dataset_bytes','network_message_number','dataset_offset'):conditions=[({'ps_encoding':'UADP'},0)]
  if k=='ordering':conditions=[({'ps_encoding':'UADP'},'Undefined')]
  if k=='keyframe_count':conditions=[({'ps_dataset_kind':'CYCLIC'},1),({'ps_dataset_kind':'ACYCLIC'},0),({'ps_dataset_kind':'HEARTBEAT'},1)]
  if k=='mqtt_version':conditions=[({'ps_binding':'MQTT'},'BestAvailable')]
  if k=='topic_prefix':conditions=[({'ps_binding':'MQTT'},'opcua')]
  if k=='retain':conditions=[({'ps_binding':'MQTT','ps_topic_kind':topic},topic not in('data','action-request','action-response'))for topic in TOPICS]
  if conditions:item.update(conditional_defaults=[dict(when={**when,'ps_edition':EDITION},value=value,source=P14,source_revision=SOURCES[P14])for when,value in conditions],default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
  if k=='publisher_type':item.update(conditional_defaults=[dict(when={'ps_encoding':e,'ps_edition':EDITION},value=t,source=P14,source_revision=SOURCES[P14])for e,t in(('UADP','UINT64'),('JSON','STRING'))],default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
  result.append(item)
 return result
