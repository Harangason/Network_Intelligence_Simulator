"""SOME/IP-SD discovery state and wire options, independent of service data."""
SD='https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_SOMEIPServiceDiscoveryProtocol.pdf'
SOURCES={SD:'AUTOSAR FO R25-11 document802 November27 2025, selected sections5.1.2/5.1.3/5.1.4/5.1.5/5.1.6/5.1.7/6 actually read; source port default, configurable timers are not guessed.'}
DECLARATIONS=[]

def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,integer=False):
 DECLARATIONS.append(dict(key='sd_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,integer=integer,source=SD,source_revision=SOURCES[SD]))

for k,meaning,opts in [
 ('edition','Actual selected audited discovery edition versus independently qualified alternative.',['FO_R25_11','REGISTERED_ACTUAL']),
 ('proposal_mode','Actual deployment configuration versus explicitly selected standard proposals.',['ACTUAL_CONFIG','SOURCE_PROPOSALS']),
 ('transport','Discovery itself is UDP, independent from advertised TCP/UDP service endpoints.',['UDP','TCP']),
 ('ip_version','Actual SD message IPv4 or IPv6 binding; SD endpoint option must match sender path.',['IPV4','IPV6']),
 ('role','Actual sender or receiver; undefined flags/empty option runs have distinct sending versus receiving rules.',['SENDER','RECEIVER']),
 ('relation','Actual unicast per peer versus multicast relation; counters kept independently.',['UNICAST','MULTICAST']),
 ('byte_order','All discovery fields are network byte order, distinct service payload serialization.',['BIG_ENDIAN','LITTLE_ENDIAN']),
 ('entry','Actual entry action; shared wire types are distinguished by TTL.',['FIND','OFFER','STOP_OFFER','SUBSCRIBE','STOP_SUBSCRIBE','ACK','NACK']),
 ('option','Selected decoded option, independently from all options in the complete array.',['NONE','CONFIGURATION','LOAD_BALANCING','IPV4_ENDPOINT','IPV6_ENDPOINT','IPV4_MULTICAST','IPV6_MULTICAST','IPV4_SD_ENDPOINT','IPV6_SD_ENDPOINT','UNKNOWN']),
 ('endpoint_transport','Actual advertised service TCP/UDP versus discovery UDP; multicast endpoint uses UDP.',['UDP','TCP']),
 ('phase','Actual per-service DOWN/INITIAL_WAIT/REPETITION/MAIN state, not global CAN cycle.',['DOWN','INITIAL_WAIT','REPETITION','MAIN']),
 ('trigger','Actual initial/cyclic/find response/subscription/retry trigger.',['INITIAL','CYCLIC','MULTICAST_RESPONSE','UNICAST_RESPONSE','SUBSCRIBE','RETRY']),
 ('retry_kind','Configured finite retries versus until reboot/request cancellation under forever offer.',['FINITE','INFINITE']),
 ('event_delivery','Actual chosen client-provided endpoint or server multicast endpoint, not SD message relation.',['CLIENT_ENDPOINT','SERVER_MULTICAST']),
 ('outcome','Actual discovery/application subscription outcome; a parsed ACK can still fail resources/security checks.',['ACCEPTED','IGNORED','REJECTED','MALFORMED','TIMEOUT','UNKNOWN']),
]:d(k,'select',meaning,options=opts)

for k,meaning,lo,hi,unit in [
 ('port','Actual UDP discovery port, source default30490; not advertised application endpoint port.',1,65535,None),
 ('header_service_id','Wire SOME/IP SD service0xFFFF, distinct service ID in entries.',0,65535,None),
 ('header_method_id','Wire SOME/IP SD method0x8100, not ordinary event ID.',0,65535,None),
 ('protocol_version','Wire discovery SOME/IP protocol version1.',0,255,None),
 ('interface_version','Wire SD interface version1, distinct entry major version.',0,255,None),
 ('message_type','Wire discovery notification0x02 only, no TP flag.',0,255,None),
 ('return_code','Wire discovery return code0, not application acceptance result.',0,255,None),
 ('client_id','Wire discovery client0, single SD instance.',0,65535,None),
 ('session_id','Actual per-relation session1..65535, increment per sent message and wrap to1.',1,65535,None),
 ('old_session_id','Last received session on this same source/destination relation, not another peer.',1,65535,None),
 ('undefined_flags','Actual low six undefined flag bits, sender0 and receiver ignores.',0,63,None),
 ('reserved24','Actual24-bit reserved header field; no guessed device value.',0,16777215,None),
 ('entry_type','Actual wire entry type0/1/6/7; TTL separates stopping/NACK from positive state.',0,255,None),
 ('service_id','Actual offered/found service, wildcard0xFFFF for Find;0xFFFE distinct non-SOME/IP service.',0,65535,None),
 ('instance_id','Actual service instance, wildcard0xFFFF allowed Find only; zero reserved.',0,65535,None),
 ('major','Actual entry service major version, Find wildcard0xFF; not SD header interface1.',0,255,None),
 ('minor','Actual service minor version, Find wildcard0xFFFFFFFF.',0,4294967295,None),
 ('ttl_s','Actual24-bit lifetime in seconds,0 stop/NACK;0xFFFFFF means until reboot; Find ignores this field.',0,16777215,'s'),
 ('eventgroup_id','Actual eventgroup,zero reserved and0xFFFF all groups special selection.',0,65535,None),
 ('counter','Actual4-bit subscription differentiator; zero when counter unused.',0,15,None),
 ('expected_service_id','Actual outstanding Subscribe service ID copied into ACK/NACK.',0,65535,None),
 ('expected_instance_id','Actual outstanding Subscribe instance ID copied into ACK/NACK.',1,65534,None),
 ('expected_major','Actual outstanding Subscribe major interface version.',0,255,None),
 ('expected_eventgroup_id','Actual outstanding Subscribe eventgroup identity.',1,65535,None),
 ('expected_counter','Actual outstanding Subscribe differentiation counter.',0,15,None),
 ('expected_ttl_s','Actual outstanding Subscribe lifetime copied into ACK, not NACK zero.',1,16777215,'s'),
 ('event_reserved12','Actual eventgroup reserved12bits, transmitted zero.',0,4095,None),
 ('entries_count','Actual number of16-byte entries in full array, not device count.',0,None,None),
 ('entries_bytes','Actual entries array bytes,16 times actual entries count.',0,4294967295,'byte'),
 ('options_count','Actual number of variable-size options in full array.',0,None,None),
 ('options_bytes','Actual full options array bytes, including every option length/type field.',0,4294967295,'byte'),
 ('index1','First run starting option index, uint8; empty sender run requires zero.',0,255,None),
 ('index2','Second run starting option index, uint8; empty receiver run ignores nonzero index.',0,255,None),
 ('count1','First run option count,uint4,not full array bytes.',0,15,None),
 ('count2','Second run option count,uint4.',0,15,None),
 ('payload_bytes','Actual SD body12+entries+options, excludes16-byte SOME/IP header.',12,None,'byte'),
 ('length_bytes','Actual SOME/IP length20+entries+options, starts at request ID.',20,4294967295,'byte'),
 ('message_bytes','Actual complete UDP SOME/IP SD message28+entries+options.',28,None,'byte'),
 ('udp_budget_bytes','Actual qualified datagram/IP/security/path budget; not fixed1400 or Ethernet1500 app cap.',28,None,'byte'),
 ('option_type','Actual raw option type code, distinct decoded selected kind.',0,255,None),
 ('option_length','Actual option length excludes two-byte length and one-byte type; endpoint9/21, load5.',0,65535,'byte'),
 ('option_bytes','Actual entire option size=length+3.',3,None,'byte'),
 ('option_index','Actual position of this option in full array, SD endpoint must be first.',0,None,None),
 ('option_flags_reserved','Actual7-bit reserved option flags, sender zero.',0,127,None),
 ('option_reserved8','Actual endpoint reserved byte, zero on sending.',0,255,None),
 ('endpoint_port','Actual advertised service/discovery endpoint port; zero invalid.',1,65535,None),
 ('endpoint_protocol','Actual IANA L4 code6 TCP or17 UDP; multicast/SD UDP17 only.',0,255,None),
 ('priority','Load balancing priority lower means preferred; only applies all-instance searches.',0,65535,None),
 ('weight','Actual load balancing weight for equal-priority candidates; no universal default.',0,65535,None),
 ('configuration_sequence_bytes','Actual single DNS-TXT-style key/value sequence length,uint8 excluding length byte.',0,255,'byte'),
 ('endpoint_references','Actual entry references to service endpoint options, not SD identification option.',0,None,None),
 ('multicast_references','Actual entry references to multicast event options.',0,None,None),
 ('configuration_references','Actual configuration-option references permitted per entry.',0,None,None),
 ('load_references','Actual load balancing option references, only offers.',0,None,None),
 ('sd_endpoint_count','Actual number of SD identification endpoint options, at most one per selected message family.',0,1,None),
 ('repetitions_max','Configured number of repetition steps; zero skips phase, no universal default2.',0,None,None),
 ('repetition_index','Actual zero-based current repetition step.',0,None,None),
 ('retry_max','Actual finite max subscription retries,zero=no retry; no universal default.',0,None,None),
 ('retry_count','Actual completed retries for current eventgroup request.',0,None,None),
 ('multicast_threshold','Configured clients with distinct endpoints switching threshold;0/1 have special policies.',0,None,None),
 ('subscribed_endpoints','Actual distinct subscribed endpoints, not count of all duplicate subscriptions.',0,None,None),
]:d(k,'number',meaning,lo,hi,unit,integer=True)

for k,meaning in [
 ('initial_min_ms','Configured initial random delay minimum; protocol gives no universal value.'),
 ('initial_max_ms','Configured initial random delay maximum, at least minimum.'),
 ('initial_actual_ms','Actual chosen random delay within configured range.'),
 ('repetitions_base_ms','Configured base delay for doubling repetition steps, no default100ms from example.'),
 ('repetition_delay_ms','Actual repetition wait=2^index times base.'),
 ('response_min_ms','Configured random response delay minimum for responses to multicast triggers.'),
 ('response_max_ms','Configured response delay maximum.'),
 ('response_actual_ms','Actual response random delay; unicast response does not apply this delay.'),
 ('cyclic_offer_ms','Actual configured interval between offers in main phase, not generic CAN cycle.'),
 ('retry_delay_ms','Actual delay before missing-ACK/NACK subscription retry.'),
 ('elapsed_lifetime_s','Actual elapsed since received offer/subscription under same correlated state.'),
 ('source_bound_ms','Actual discovery generation/application request production bound.'),
 ('network_bound_ms','Actual whole UDP/IP/PHY/queue/recovery path bound.'),
 ('consumer_bound_ms','Actual discovery validation/resource/security/consumer bound.'),
 ('e2e_bound_ms','Actual discovery source+network+consumer chain, distinct service data path.'),
 ('e2e_limit_ms','Actual independent functional discovery/availability requirement.'),
 ('age_ms','Actual discovery-state age at consuming application.'),
 ('freshness_ms','Actual permitted discovery-state age.'),
]:d(k,'number',meaning,0,None,'s'if k.endswith('_s')else'ms')

for k,meaning in [
 ('reboot','Actual current relation reboot flag, true until first session wrap after boot.'),
 ('old_reboot','Last received reboot flag on the same source/destination relation.'),
 ('reboot_detected','Actual comparison result, not inferred from arbitrary lower session from another peer.'),
 ('wrapped_since_boot','Actual sender has completed first session wrap since boot.'),
 ('relation_initial','Actual first relation message without earlier receiver state.'),
 ('unicast_flag','Wire support for receiving unicast,1 for allSD messages even multicast relation.'),
 ('counter_used','Actual subscription counter differentiation configured; unused wire counter0.'),
 ('option_discardable','Unknown option can be ignored when discardable, distinct from required endpoint validity.'),
 ('option_referenced','Selected option is referenced by an entry; SD identification endpoint must not be.'),
 ('endpoint_valid','Actual address family/unicast-multicast/port/path verified under independent IP model.'),
 ('service_matches','Actual entry tuple/service-major binding matched, with only applicable wildcard rules.'),
 ('options_verified','Actual all options exist/types/lengths/conflicts/required references validated.'),
 ('state_verified','Actual per-peer counters/phase/lifetime/subscription state verified.'),
 ('security_required','Actual network security association required by service endpoint.'),
 ('security_ready','Actual required security association established and fully operational.'),
 ('tcp_required','Actual subscribed eventgroup requires already-open TCP connection.'),
 ('tcp_ready','Actual required service TCP connection exists before subscription.'),
 ('resources_ready','Actual receiver/server socket/subscription resources available.'),
 ('data_accepted','Actual independent discovery/subscription consumer acceptance, not SD header E_OK.'),
]:d(k,'boolean',meaning)

for k,meaning in [
 ('implementation_source','Actual discovery implementation/edition/capabilities.'),
 ('binding_source','Actual canonical source/destination/peer/IP/port/channel and independent lower-layer bindings.'),
 ('service_source','Actual deployed service/instance/version/eventgroup and endpoint assignments.'),
 ('state_source','Actual correlated per-relation counters/reboot/phase/lifetime state definition.'),
 ('options_source','Actual full ordered entries/options/addresses/type/length/reference definitions.'),
 ('timing_source','Actual timers/route/resource budgets, independent from service functional timing.'),
 ('acceptance_source','Actual independent availability/timing/freshness/security acceptance requirements.'),
 ('observation_source','Actual correlated datagrams/resource/security/application state observation.'),
 ('endpoint_address','Actual configured option endpoint address; independently qualified IP family and role, no guessed address.'),
 ('multicast_address','Actual configured SD multicast address, no universal vendor239-address default.'),
 ('registered_source','Actual alternative edition qualification source.'),
]:d(k,'text',meaning)

REQUIRED=('edition','proposal_mode','transport','ip_version','role','relation','entry','implementation_source','binding_source','service_source','state_source','options_source','timing_source','acceptance_source')
REMOVED={k:'SOME/IP-SD own discovery header/entry/options/lifetime/state and explicit UDP binding replace foreign link/CAN parameters; NIS scenario controls remain independent.'for k in('bitrate','reserved_bandwidth_percent','sync_method','retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s','mtu_bytes','duplex','vlan_id','rate_limit_bit_s')}
OPTIONS={'CONFIGURATION':1,'LOAD_BALANCING':2,'IPV4_ENDPOINT':4,'IPV6_ENDPOINT':6,'IPV4_MULTICAST':20,'IPV6_MULTICAST':22,'IPV4_SD_ENDPOINT':36,'IPV6_SD_ENDPOINT':38}
ENTRIES={'FIND':0,'OFFER':1,'STOP_OFFER':1,'SUBSCRIBE':6,'STOP_SUBSCRIBE':6,'ACK':7,'NACK':7}

def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='sd_'+k,when={'sd_'+a:b for a,b in(w or{}).items()},source=SD,source_revision=SOURCES[SD],**kw))
 rules.append(dict(parameter='local_timing_evidence',allowed=[],source=SD))
 r('registered_source',{'edition':'REGISTERED_ACTUAL'},required=True)
 w={'edition':'FO_R25_11'}
 for k,v in [('transport','UDP'),('header_service_id',65535),('header_method_id',33024),('protocol_version',1),('interface_version',1),('message_type',2),('return_code',0),('client_id',0),('byte_order','BIG_ENDIAN'),('unicast_flag',True)]:r(k,w,allowed=[v])
 r('undefined_flags',{'role':'SENDER'},allowed=[0])
 r('reboot',{'role':'SENDER','wrapped_since_boot':False},allowed=[True]);r('reboot',{'role':'SENDER','wrapped_since_boot':True},allowed=[False])
 r('session_id',{'role':'SENDER','relation_initial':True},allowed=[1])
 r('reboot_detected',{'role':'RECEIVER','relation_initial':True},allowed=[False])
 r('reboot_detected',{'role':'RECEIVER','relation_initial':False,'old_reboot':False,'reboot':True},allowed=[True])
 r('reboot_detected',{'role':'RECEIVER','relation_initial':False,'reboot':False},allowed=[False])
 r('session_id',{'role':'RECEIVER','relation_initial':False,'old_reboot':True,'reboot':True,'reboot_detected':True},maximum_parameter='sd_old_session_id')
 r('session_id',{'role':'RECEIVER','relation_initial':False,'old_reboot':True,'reboot':True,'reboot_detected':False},exclusive_minimum_expression='sd_old_session_id')
 r('instance_id',forbidden=[0]);r('service_id',forbidden=[0]);r('eventgroup_id',forbidden=[0])
 for entry,code in ENTRIES.items():
  w={'entry':entry};r('entry_type',w,allowed=[code])
  if entry!='FIND':r('instance_id',w,forbidden=[65535])
  if entry in('STOP_OFFER','STOP_SUBSCRIBE','NACK'):r('ttl_s',w,allowed=[0])
  elif entry in('OFFER','SUBSCRIBE','ACK'):r('ttl_s',w,minimum=1)
  if entry in('SUBSCRIBE','STOP_SUBSCRIBE','ACK','NACK'):
   r('relation',w,allowed=['UNICAST']);r('event_reserved12',w,allowed=[0])
 r('counter',{'counter_used':False},allowed=[0])
 for entry in('OFFER','SUBSCRIBE','ACK'):
  w={'entry':entry}
  r('elapsed_lifetime_s',w,when_ranges={'sd_ttl_s':[1,16777214]},exclusive_maximum_expression='sd_ttl_s')
 r('ttl_s',{'entry':'OFFER'},when_ranges={'sd_ttl_s':[1,16777214]},minimum_expression={'product':[.001,'sd_cyclic_offer_ms']})
 r('entries_bytes',equal_expression={'product':[16,'sd_entries_count']},multiple_of=16)
 body={'sum':[12,'sd_entries_bytes','sd_options_bytes']}
 r('payload_bytes',equal_expression=body)
 r('length_bytes',equal_expression={'sum':[20,'sd_entries_bytes','sd_options_bytes']})
 r('message_bytes',equal_expression={'sum':[28,'sd_entries_bytes','sd_options_bytes']},maximum_parameter='sd_udp_budget_bytes')
 rules.append(dict(parameter='payload_bytes',equal_parameter='sd_payload_bytes',source=SD))
 for k in('payload_bytes','length_bytes','message_bytes'):
  for dep in('entries_bytes','options_bytes'):r(dep,when_present=['sd_'+k],required=True)
 for run in(1,2):
  r('index'+str(run),{'role':'SENDER','count'+str(run):0},allowed=[0])
  r('index'+str(run),when_greater_than={'sd_count'+str(run):0},maximum_expression={'subtract':['sd_options_count','sd_count'+str(run)]})
 for kind,code in OPTIONS.items():
  w={'option':kind};r('option_type',w,allowed=[code]);r('option_bytes',w,equal_expression={'sum':['sd_option_length',3]})
  if kind=='LOAD_BALANCING':r('option_length',w,allowed=[5])
  if kind.startswith('IPV'):
   r('option_length',w,allowed=[9 if kind.startswith('IPV4') else 21]);r('option_discardable',w,allowed=[False])
   for key in('option_flags_reserved','option_reserved8'):r(key,{**w,'role':'SENDER'},allowed=[0])
   if kind.endswith('_MULTICAST')or kind.endswith('_SD_ENDPOINT'):
    r('endpoint_transport',w,allowed=['UDP']);r('endpoint_protocol',w,allowed=[17])
   if kind.endswith('_SD_ENDPOINT'):
    for k,v in [('ip_version','IPV4'if kind.startswith('IPV4')else'IPV6'),('option_index',0),('option_referenced',False)]:r(k,{**w,'role':'SENDER'},allowed=[v])
   if kind.endswith('_ENDPOINT')and not kind.endswith('_SD_ENDPOINT'):
    for t,code in [('TCP',6),('UDP',17)]:r('endpoint_protocol',{**w,'endpoint_transport':t},allowed=[code])
 r('option_discardable',{'role':'RECEIVER','option':'UNKNOWN','data_accepted':True},required=True,allowed=[True])
 r('configuration_references',maximum=1)
 counts={'FIND':(0,0,0),'OFFER':(2,0,1),'STOP_OFFER':(2,0,1),'SUBSCRIBE':(2,1,0),'STOP_SUBSCRIBE':(2,1,0),'ACK':(0,1,0),'NACK':(0,0,0)}
 for entry,(endpoint,multi,load)in counts.items():
  w={'role':'SENDER','entry':entry}
  for k,maxi in [('endpoint_references',endpoint),('multicast_references',multi),('load_references',load)]:r(k,w,maximum=maxi)
  if entry in('OFFER','STOP_OFFER'):r('endpoint_references',w,minimum=1)
 r('initial_max_ms',minimum_parameter='sd_initial_min_ms')
 r('initial_actual_ms',minimum_parameter='sd_initial_min_ms',maximum_parameter='sd_initial_max_ms')
 r('response_max_ms',minimum_parameter='sd_response_min_ms')
 r('response_actual_ms',{'trigger':'MULTICAST_RESPONSE'},minimum_parameter='sd_response_min_ms',maximum_parameter='sd_response_max_ms')
 r('response_actual_ms',{'trigger':'UNICAST_RESPONSE'},allowed=[0])
 r('repetition_delay_ms',equal_expression={'product':[{'power':[2,'sd_repetition_index']},'sd_repetitions_base_ms']})
 r('repetition_index',{'phase':'REPETITION'},exclusive_maximum_expression='sd_repetitions_max')
 r('phase',{'repetitions_max':0},forbidden=['REPETITION'])
 r('trigger',{'phase':'MAIN','entry':'FIND'},forbidden=['CYCLIC'])
 r('event_delivery',{'multicast_threshold':0},allowed=['CLIENT_ENDPOINT'])
 r('event_delivery',{'multicast_threshold':1},allowed=['SERVER_MULTICAST'])
 r('subscribed_endpoints',{'event_delivery':'SERVER_MULTICAST'},when_greater_than={'sd_multicast_threshold':1},minimum_parameter='sd_multicast_threshold')
 r('subscribed_endpoints',{'event_delivery':'CLIENT_ENDPOINT'},when_greater_than={'sd_multicast_threshold':1},exclusive_maximum_expression='sd_multicast_threshold')
 r('retry_count',{'retry_kind':'FINITE'},maximum_parameter='sd_retry_max')
 r('ttl_s',{'retry_kind':'INFINITE'},allowed=[16777215])
 chain=('source_bound_ms','network_bound_ms','consumer_bound_ms')
 r('e2e_bound_ms',equal_expression={'sum':['sd_'+k for k in chain]})
 for k in chain:r(k,when_present=['sd_e2e_bound_ms'],required=True)
 r('e2e_bound_ms',maximum_parameter='sd_e2e_limit_ms');r('age_ms',maximum_parameter='sd_freshness_ms')
 w={'data_accepted':True}
 for k,v in [('outcome','ACCEPTED'),('service_matches',True),('options_verified',True),('state_verified',True),('resources_ready',True)]:r(k,w,required=True,allowed=[v])
 for k in('header_service_id','header_method_id','protocol_version','interface_version','message_type','return_code','client_id','session_id','byte_order','unicast_flag','entry_type','service_id','instance_id','major','ttl_s','entries_count','entries_bytes','options_bytes','options_count','payload_bytes','length_bytes','message_bytes','udp_budget_bytes','observation_source','e2e_bound_ms','e2e_limit_ms','age_ms','freshness_ms','relation_initial','reboot'):r(k,w,required=True)
 r('security_ready',{'data_accepted':True,'security_required':True},required=True,allowed=[True])
 r('tcp_ready',{'data_accepted':True,'tcp_required':True},required=True,allowed=[True])
 for k in('old_reboot','old_session_id','reboot_detected'):r(k,{'data_accepted':True,'role':'RECEIVER','relation_initial':False},required=True)
 for entry in('SUBSCRIBE','STOP_SUBSCRIBE','ACK','NACK'):
  for k in('eventgroup_id','counter','event_reserved12'):r(k,{'data_accepted':True,'entry':entry},required=True)
 for entry in('ACK','NACK'):
  for k in('service_id','instance_id','major','eventgroup_id','counter'):
   r(k,{'entry':entry},equal_parameter='sd_expected_'+k)
   r('expected_'+k,{'data_accepted':True,'entry':entry},required=True)
 r('ttl_s',{'entry':'ACK'},equal_parameter='sd_expected_ttl_s')
 r('expected_ttl_s',{'data_accepted':True,'entry':'ACK'},required=True)
 for entry in('OFFER','SUBSCRIBE','ACK'):r('elapsed_lifetime_s',{'data_accepted':True,'entry':entry},required=True)
 for kind in OPTIONS:
  for k in('option_type','option_length','option_bytes','option_index','option_discardable'):r(k,{'data_accepted':True,'option':kind},required=True)
  if kind.startswith('IPV'):
   for k in('endpoint_transport','endpoint_protocol','endpoint_port','endpoint_address'):r(k,{'data_accepted':True,'option':kind},required=True)
   r('endpoint_valid',{'data_accepted':True,'option':kind},required=True,allowed=[True])
 return dict(rate_model={'type':'EXPLICIT_UDP_DISCOVERY_STATE_AND_ENDPOINTS','fields':[]},required_parameters=['sd_'+k for k in REQUIRED],native_parameter_prefixes=['sd_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='actual_someip_sd_udp_ip_binding',medium_access_model='INDEPENDENT_IP_UDP_LOWER_LAYER_PATH',arbitration_model_id='EXPLICIT_DISCOVERY_TIMERS_AND_RELATIONS',mechanisms={'transport':['UDP_DISCOVERY_NOT_ADVERTISED_SERVICE_TCP'],'state':['PER_PEER_RELATION_SESSIONS_REBOOT','ENTRY_LIFETIME_AND_SUBSCRIPTION'],'qualification':['HEADER_E_OK_NOT_SUBSCRIPTION_SUCCESS','NO_AUTO_ETHERNET_CAPACITY']})

def fields():
 defaults={'port':30490,'header_service_id':65535,'header_method_id':33024,'protocol_version':1,'interface_version':1,'message_type':2,'return_code':0,'client_id':0,'byte_order':'BIG_ENDIAN','unicast_flag':True,'transport':'UDP'}
 out=[]
 for spec in DECLARATIONS:
  k=spec['key'][3:];v={a:b for a,b in spec.items()if b is not None}
  v.update(label=k.replace('_',' '),category='technology',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  if k in('endpoint_address','multicast_address'):v['format']='IP_ADDRESS'
  if k in defaults:v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=[dict(when={'sd_edition':'FO_R25_11','sd_proposal_mode':'SOURCE_PROPOSALS'},value=defaults[k],source=SD,source_revision=SOURCES[SD])])
  out.append(v)
 return out
