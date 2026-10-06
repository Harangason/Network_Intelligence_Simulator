"""TRDP: independently scoped process/message data and TCNOpen 3.0.0 source.

Library defaults are source proposals, not commissioned device configuration,
Ethernet capacity, or an IEC61375/SDT safety certification.
"""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS, ETHERNET_KEYS
MANUAL='https://downloads.sourceforge.net/project/tcnopen/TRDP/3.0.0.0/TCN-TRDP2-D-BOM-033-11%20-%20TRDP%20Reference%20Manual%203.0.0.0.pdf'
CODE='https://downloads.sourceforge.net/project/tcnopen/TRDP/3.0.0.0/3.0.0.0.zip'
SOURCES={MANUAL:'TCNOpen TRDP Light Reference Manual 3.0.0.0 BOM-033-11, selected configuration/types and printed65-74 macros; library defaults are edition-specific, not all IEC61375 implementations.',CODE:'Official TCNOpen release3.0.0.0: src/api/iec61375-2-3.h/trdp_types.h; src/common/trdp_private.h,pdcom,mdcom,utils,tau_marshall; VOS crc32 and POSIX QoS. Actual build/platform behavior remains independently qualified.'}
DECLARATIONS=[]
def d(k,t,meaning,source=CODE,**kw):DECLARATIONS.append(declaration('tr_',k,t,meaning,source,SOURCES[source],**kw))
for k,meaning,opts in [
 ('review_profile','Reviewed implementation baseline or separately registered actual edition.',['TCNOPEN_3_0_0','REGISTERED_ACTUAL']),
 ('proposal_mode','Source library proposals separate from actual commissioned values.',['SOURCE_BASELINE','ACTUAL_CONFIG']),
 ('mode','Process data and message data have different headers/limits/timers.',['PD','MD']),
 ('transport','Actual transport binding; PD UDP, MD UDP or TCP.',['UDP','TCP']),
 ('phase','Actual header emission versus received compatibility checks.',['SEND','RECEIVE']),
 ('variant','Actual SOA build uses protocolminor1; base uses minor0.',['BASE','SOA']),
 ('message_type','Actual TRDP PD/MD message kind, not MQTT publication.',['Pd','Pp','Pr','Pe','Pt','Mn','Mr','Mp','Mq','Mc','Me']),
 ('socket_profile','Actual VOS platform mapping, not every platform identical.',['POSIX_DSCP','REGISTERED_ACTUAL']),
 ('timeout_behavior','PD timeout behavior: zero means inherit actual session setting.',['INHERIT','SET_TO_ZERO','KEEP_LAST_VALUE']),
 ('outcome','Actual correlated functional result; old/zeroed data is not fresh.',['ACCEPTED','STALE','ERROR','UNKNOWN']),
]:d(k,'select',meaning,options=opts)
for k,meaning,lo,hi,unit,integer in [
 ('port','Actual 16bit UDP/TCP destination port;17224PD/17225MD are library proposals.',1,65535,None,True),
 ('qos','Actual API uint8 priority; POSIX mapping only0..7, not generic CAN priority.',0,255,None,True),
 ('ds_field','Actual POSIX IPv4 DS byte when QoS1..7 is applied, qos<<5 and ECN0.',0,255,None,True),
 ('ttl','Actual configured API TTL0 means socket default/inherit, not zero remaining hops.',0,255,None,True),
 ('retries','Actual API resend limit; not equivalent to TCP retries or all multicast retries.',0,255,None,True),
 ('effective_retries','Actual retries only UDP unicast with configured expectedreply1; otherwise0.',0,255,None,True),
 ('expected_replies','Actual effective MD request count; unicast1, multicast0 means unknown count.',0,4294967295,None,True),
 ('configured_expected_replies','Actual input expected replies before unicast request normalization.',0,4294967295,None,True),
 ('replies_received','Actual matching reply count; unknown expected0 is not zero completeness.',0,4294967295,None,True),
 ('header_bytes','Actual PD40/MD116 header, distinct IP/UDP/TCP/Ethernet overhead.',0,None,'byte',True),
 ('data_bytes','Actual wire dataset length excludes header and4byte packet padding.',0,4294967295,'byte',True),
 ('padding_bytes','Actual packet padding to4octets, not application data.',0,3,'byte',True),
 ('packet_bytes','Actual complete TRDP header+dataset+padding.',0,None,'byte',True),
 ('peer_max_data_bytes','Actual independently qualified peer dataset maximum.',0,None,'byte',True),
 ('sequence','Actual stream/session sequence32bit; PD and pulledPD counters separate.',0,4294967295,None,True),
 ('next_sequence','Actual counter increment modulo2^32;0 can indicate PD reset.',0,4294967295,None,True),
 ('protocol_version','Actual version16bit; receive checks majorFF00, not blanketminor0.',0,65535,None,True),
 ('message_code','Actual bigendian twocharacter message type value.',0,65535,None,True),
 ('com_id','Actual32bit communication identifier bound to dataset mapping.',0,4294967295,None,True),
 ('etb_topology','Actual ETB topology counter, zero local consist only when appropriate.',0,4294967295,None,True),
 ('operational_topology','Actual operation/direction/side topology counter.',0,4294967295,None,True),
 ('etb_filter','Actual topology comparison filter; filter0 wildcard, not everycounter0 wildcard.',0,4294967295,None,True),
 ('operational_filter','Actual explicit filter for this comparison role.',0,4294967295,None,True),
 ('reserved','Actual PD reserved field0 in BASE; SOA service/instance encoding separately qualified.',0,4294967295,None,True),
 ('reply_com_id','Actual PD request replyComId32bit, not inherited receiveComId.',0,4294967295,None,True),
 ('reply_ip_raw','Actual PD request IPv4 replyaddress32bit encoding.',0,4294967295,None,True),
 ('reply_status','Actual signed MD replystatus; negative protocol errors distinct nonnegativeuser status.',-2147483648,2147483647,None,True),
 ('header_crc','Actual IEEE reflected CRC32 over header excluding FCS, transmitted little endian.',0,4294967295,None,True),
 ('source_uri_bytes','Actual user part wire32octets, not host/global URI.',0,32,'byte',True),
 ('destination_uri_bytes','Actual destinationuser wire32octets; API buffer33 includes terminator.',0,32,'byte',True),
 ('reply_timeout_us','Actual MD request wire timeout0 means infinite only forMr.',0,4294967295,'us',True),
 ('api_reply_timeout_us','Actual API timeout;0xffffffff sentinel differs from infinite wire0.',0,4294967295,'us',True),
 ('confirm_timeout_us','Actual MD confirmation timeout;source1s proposal not functionaldeadline.',0,4294967295,'us',True),
 ('connection_timeout_us','Actual TCP idle connection timeout, not perpacket latency.',0,4294967295,'us',True),
 ('sending_timeout_us','Actual MD sending timeout, separate TCPconnect and replywait.',0,4294967295,'us',True),
 ('pd_timeout_us','Actual receiver PD timeout, behavior independently selected.',0,4294967295,'us',True),
 ('library_process_cycle_us','Actual session worker process cadence, not every dataset periodminimum.',1,None,'us',True),
 ('publish_cycle_us','Actual configured PD period,0 means noncyclic/onrequest.',0,4294967295,'us',True),
 ('timer_granularity_us','Actual compiled timer resolution500us indexed/TSN else5000.',1,None,'us',True),
 ('dataset_id','Actual registry dataset id; custom ids>1000, managedids actual mapping.',0,4294967295,None,True),
 ('dataset_reserved','Actual dataset descriptor reserved16bit must0.',0,65535,None,True),
 ('dataset_elements','Actual descriptor elementcount16bit.',0,65535,None,True),
 ('element_type','Actual scalarid1..16 or qualified composite>30;17..30 reserved, managed31..1000 need registeredmap.',0,4294967295,None,True),
 ('element_size','Actual descriptor element itemcount;0means variable, not empty encodeddata.',0,4294967295,None,True),
 ('element_count','Actual resolved itemcount from actual codec/precedingcount, not guessed0.',0,4294967295,None,True),
 ('element_width_bytes','Actual scalar wirewidth or complete composite width; not C memoryalignment.',0,None,'byte',True),
 ('element_bytes','Actual complete array bytes for resolved count.',0,None,'byte',True),
 ('scale','Actual visualization scaling factor, not wire-value type conversion.',None,None,None,False),
 ('offset','Actual visualization signed32offset.',-2147483648,2147483647,None,True),
 ('raw_value','Actual independently decoded numerical scalar;64bit lossless rawencoding separately required.',None,None,None,False),
 ('display_value','Actual visualization scale*raw+offset.',None,None,None,False),
 ('time_microseconds','Actual TIMEDATE64 fractional microseconds, not unconstrained32bit scalar.',0,999999,'us',True),
 ('source_ms','Actual producer/encode/queue envelope.',0,None,'ms',False),
 ('transport_ms','Actual IP/PHY/switch/queue/reply/confirm envelope.',0,None,'ms',False),
 ('consumer_ms','Actual decode/use envelope.',0,None,'ms',False),
 ('e2e_ms','Actual whole source+transport+consumer envelope.',0,None,'ms',False),
 ('deadline_ms','Actual independently specified functional deadline.',0,None,'ms',False),
 ('age_ms','Actual correlated source-to-use age.',0,None,'ms',False),
 ('freshness_ms','Actual independently specified acceptable dataage.',0,None,'ms',False),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=integer)
for k,meaning in [
 ('multicast','Actual destination classification checked against commissioned IPv4 address.'),
 ('tsn_build','Actual TSN_SUPPORT build available, not TSNschedule evidence.'),
 ('indexed_build','Actual HIGH_PERF_INDEXED build available.'),
 ('custom_dataset','Actual application-owned dataset namespace rather than managed definition.'),
 ('marshalling','Actual library marshalling enabled; raw caller encoding still needs codec source.'),
 ('pd_expired','Actual receiver deadline expired; old or zero data cannot qualify fresh acceptance.'),
 ('header_verified','Actual complete packet/header/version/FCS checked.'),
 ('dataset_verified','Actual full encoding/length/comId mapping checked independently of headerCRC.'),
 ('path_verified','Actual complete IP/PHY/queue/loss/schedule bounded.'),
 ('topology_verified','Actual applicable ETB/operation counter comparison validated.'),
 ('replies_complete','Actual correlated required replies complete, not count0 assumption.'),
 ('confirmation_received','Actual matchingMq/Mc session confirmation received.'),
 ('data_accepted','Actual consumer accepted the correlated current dataset.'),
]:d(k,'boolean',meaning)
for k,meaning in [
 ('revision','Actual implementation/IEC edition and build revision.'),('configuration_source','Actual PD/MD transport/socket/default resolution evidence.'),
 ('codec_source','Actual dataset/comId/scalar/nesting/variablelength/marshalling qualification.'),('path_source','Actual bound IP/PHY/switch/queue/capacity path.'),
 ('schedule_source','Actual publication/reply/confirmation/timeout/processing schedule.'),('acceptance_source','Actual independent function/deadline/freshness contract.'),
 ('registered_source','Actual independent variant/edition extension qualification.'),('observation_source','Actual correlated dataset/header/sequence/session/source-to-use trace.'),
 ('socket_source','Actual platform socket DSCP/TTL/transport mapping.'),('composite_source','Actual nested/managed dataset mapping and recursivewirecodec.'),
 ('variable_count_source','Actual count-bearing precedingfield and array bounds.'),('tsn_source','Actual TSN scheduling/PHY/device realization;Ptflag alone is insufficient.'),
 ('source_address','Actual IPv4 sourcebinding.'),('destination_address','Actual IPv4 destinationbinding.'),
 ('header_hex','Actual complete header wireoctets, not payload CRC.'),('session_hex','Actual16byte UUID encoded without fabricated default.'),
 ('source_uri','Actual32octet userURIpart encoded using commissioned codec.'),('destination_uri','Actual32octet destination userURIpart.'),
 ('scalar_hex','Actual lossless scalar wireencoding, independent of JavaScript64bit floating precision.'),
]:d(k,'text',meaning,**({'format':'IP_ADDRESS'}if k.endswith('address')else {}))
REQUIRED=('review_profile','revision','mode','transport','configuration_source','codec_source','path_source','schedule_source','acceptance_source')
REMOVED={k:'TRDP binds its own PD/MD UDP/TCP dataset path. PHY rate/MTU, CAN retries and gateway quotas belong to independently selected lower layers.'for k in(*WIRE_KEYS,*ETHERNET_KEYS)}
TYPE_CODES={'Pd':0x5064,'Pp':0x5070,'Pr':0x5072,'Pe':0x5065,'Pt':0x5074,'Mn':0x4d6e,'Mr':0x4d72,'Mp':0x4d70,'Mq':0x4d71,'Mc':0x4d63,'Me':0x4d65}
TYPE_WIDTHS={1:1,2:1,3:2,4:1,5:2,6:4,7:8,8:1,9:2,10:4,11:8,12:4,13:8,14:4,15:6,16:8}
def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='tr_'+k,when={'tr_review_profile':'TCNOPEN_3_0_0',**{'tr_'+a:b for a,b in(w or{}).items()}},source=CODE,**kw))
 rules.append(dict(parameter='tr_registered_source',when={'tr_review_profile':'REGISTERED_ACTUAL'},required=True,source=CODE))
 rules.extend(dict(parameter=k,when={},allowed=[],source=CODE)for k in REMOVED)
 r('transport',{'mode':'PD'},allowed=['UDP'])
 r('message_type',{'mode':'PD'},allowed=['Pd','Pp','Pr','Pe','Pt']);r('message_type',{'mode':'MD'},allowed=['Mn','Mr','Mp','Mq','Mc','Me'])
 r('tsn_build',{'message_type':'Pt'},required=True,allowed=[True]);r('tsn_source',{'message_type':'Pt'},required=True)
 for variant,v in [('BASE',0x100),('SOA',0x101)]:r('protocol_version',{'phase':'SEND','variant':variant},allowed=[v])
 r('protocol_version',{'phase':'RECEIVE'},minimum=0x100,maximum=0x1ff)
 r('reserved',{'variant':'BASE','mode':'PD','phase':'SEND'},allowed=[0])
 for kind,code in TYPE_CODES.items():r('message_code',{'message_type':kind},allowed=[code])
 for mode,header,maxdata in [('PD',40,1432),('MD',116,65388)]:
  r('header_bytes',{'mode':mode},allowed=[header]);r('data_bytes',{'mode':mode},maximum=maxdata)
  r('header_hex',{'mode':mode},hex_bytes_parameter='tr_header_bytes',hex_crc32_ieee_parameter='tr_header_crc',hex_crc32_prefix_bytes=header-4,
    hex_octets=[dict(parameter='tr_'+k,offset=o,width=n,**extra)for k,o,n,extra in [
     ('sequence',0,4,{}),('protocol_version',4,2,{}),('message_code',6,2,{}),('com_id',8,4,{}),('etb_topology',12,4,{}),('operational_topology',16,4,{}),('data_bytes',20,4,{}),
     *(([('reserved',24,4,{}),('reply_com_id',28,4,{}),('reply_ip_raw',32,4,{})])if mode=='PD'else[('reply_status',24,4,{'signed':True}),('reply_timeout_us',44,4,{})]),
     ('header_crc',header-4,4,{'byte_order':'little'})]])
 r('data_bytes',maximum_parameter='tr_peer_max_data_bytes')
 for k in('header_bytes','header_crc','protocol_version','message_code','sequence','com_id','data_bytes'):r(k,when_present=['tr_header_hex'],required=True)
 r('padding_bytes',equal_expression={'integer_remainder':[{'subtract':[4,{'integer_remainder':['tr_data_bytes',4]}]},4]})
 r('packet_bytes',equal_expression={'sum':['tr_header_bytes','tr_data_bytes','tr_padding_bytes']})
 r('next_sequence',equal_expression={'integer_remainder':[{'sum':['tr_sequence',1]},4294967296]})
 for k in('source_address','destination_address'):r(k,ip_address_version=4)
 r('session_hex',pattern=r'[0-9A-Fa-f]{32}')
 for k in('source_uri','destination_uri'):r(k,text_encoding='utf-8',encoded_bytes_parameter='tr_'+k+'_bytes')
 r('qos',{'socket_profile':'POSIX_DSCP'},maximum=7);r('socket_source',when_present=['tr_socket_profile'],required=True)
 r('ds_field',{'socket_profile':'POSIX_DSCP'},when_ranges={'tr_qos':[1,7]},equal_expression={'product':['tr_qos',32]})
 r('timer_granularity_us',{'indexed_build':True},allowed=[500]);r('timer_granularity_us',{'tsn_build':True},allowed=[500])
 r('timer_granularity_us',{'indexed_build':False,'tsn_build':False},allowed=[5000])
 r('expected_replies',{'mode':'MD','message_type':'Mr','multicast':False},allowed=[1])
 r('effective_retries',{'mode':'MD','transport':'TCP'},allowed=[0]);r('effective_retries',{'mode':'MD','multicast':True},allowed=[0])
 r('effective_retries',{'mode':'MD','transport':'UDP','multicast':False,'configured_expected_replies':1},equal_parameter='tr_retries')
 r('effective_retries',{'mode':'MD','transport':'UDP','multicast':False},when_present=['tr_configured_expected_replies'],when_not={'tr_configured_expected_replies':1},allowed=[0])
 r('replies_received',{'replies_complete':True},when_greater_than={'tr_expected_replies':0},minimum_parameter='tr_expected_replies')
 r('reply_timeout_us',{'message_type':'Mr','api_reply_timeout_us':0xffffffff},allowed=[0])
 r('reply_timeout_us',{'message_type':'Mr'},when_present=['tr_api_reply_timeout_us'],when_not={'tr_api_reply_timeout_us':0xffffffff},equal_parameter='tr_api_reply_timeout_us')
 for k,filt in [('etb_topology','etb_filter'),('operational_topology','operational_filter')]:r(k,{'topology_verified':True},when_greater_than={'tr_'+filt:0},equal_parameter='tr_'+filt)
 r('dataset_reserved',allowed=[0]);r('dataset_id',{'custom_dataset':True},minimum=1001)
 r('element_type',when_ranges={'tr_element_type':[17,30]},allowed=[])
 r('composite_source',when_greater_than={'tr_element_type':30},required=True)
 r('variable_count_source',{'element_size':0},required=True);r('element_count',{'element_size':0},required=True)
 r('element_count',when_greater_than={'tr_element_size':0},equal_parameter='tr_element_size')
 for t,n in TYPE_WIDTHS.items():r('element_width_bytes',{'element_type':t},allowed=[n])
 r('element_bytes',equal_expression={'product':['tr_element_width_bytes','tr_element_count']})
 r('display_value',equal_expression={'sum':[{'product':['tr_scale','tr_raw_value']},'tr_offset']})
 for t,n in TYPE_WIDTHS.items():r('scalar_hex',{'element_type':t},pattern=r'[0-9a-fA-F]{'+str(2*n)+'}')
 for t in(7,11,13):r('scalar_hex',{'element_type':t},when_present=['tr_raw_value'],required=True)
 r('e2e_ms',equal_expression={'sum':['tr_source_ms','tr_transport_ms','tr_consumer_ms']},maximum_parameter='tr_deadline_ms')
 r('age_ms',maximum_parameter='tr_freshness_ms')
 for k in('source_ms','transport_ms','consumer_ms'):r(k,when_present=['tr_e2e_ms'],required=True)
 for k in('source_address','destination_address','port','message_type','observation_source','e2e_ms','deadline_ms','age_ms','freshness_ms'):r(k,{'data_accepted':True},required=True)
 for k,v in [('header_verified',True),('dataset_verified',True),('path_verified',True),('topology_verified',True),('pd_expired',False),('outcome','ACCEPTED')]:r(k,{'data_accepted':True},required=True,allowed=[v])
 return dict(rate_model={'type':'EXPLICIT_TRANSPORT_BINDING','fields':[]},parameter_evidence_scope='EXPLICIT_LAYER',required_parameters=['tr_'+k for k in REQUIRED],native_parameter_prefixes=['tr_'],parameter_constraints=rules,medium_access_model='ACTUAL_PD_UDP_OR_MD_UDP_TCP',arbitration_model_id='ACTUAL_BOUND_LOWER_LAYER',mechanisms={'application':['PD_CYCLIC_PULL_TIMEOUT','MD_REQUEST_REPLY_CONFIRM_SESSION'],'timing':['ACTUAL_TRANSPORT_DATASET_SCHEDULE','HEADER_CRC_NOT_PAYLOAD_OR_SAFETY_PROOF','CONSUMER_FRESHNESS_SEPARATE']})
def fields():
 baseline={'tr_review_profile':'TCNOPEN_3_0_0','tr_proposal_mode':'SOURCE_BASELINE'}
 proposals={}
 for k,v,w in [('port',17224,{'tr_mode':'PD'}),('port',17225,{'tr_mode':'MD'}),('qos',5,{'tr_mode':'PD'}),('qos',3,{'tr_mode':'MD'}),('ttl',64,{}),('retries',0,{'tr_mode':'PD'}),('retries',2,{'tr_mode':'MD'}),('header_bytes',40,{'tr_mode':'PD'}),('header_bytes',116,{'tr_mode':'MD'}),('pd_timeout_us',100000,{'tr_mode':'PD'}),('library_process_cycle_us',10000,{}),('reply_timeout_us',5000000,{'tr_mode':'MD'}),('confirm_timeout_us',1000000,{'tr_mode':'MD'}),('connection_timeout_us',60000000,{'tr_mode':'MD','tr_transport':'TCP'}),('sending_timeout_us',5000000,{'tr_mode':'MD'}),('timer_granularity_us',500,{'tr_indexed_build':True}),('timer_granularity_us',500,{'tr_tsn_build':True}),('timer_granularity_us',5000,{'tr_indexed_build':False,'tr_tsn_build':False})]:
  proposals.setdefault('tr_'+k,[]).append(dict(when={**baseline,**w},value=v,source=CODE,source_revision=SOURCES[CODE]))
 out=build_fields(DECLARATIONS,['tr_'+k for k in REQUIRED],proposals)
 for f in out:
  if f['key']not in {'tr_'+k for k in REQUIRED}|{'tr_proposal_mode','tr_registered_source'}:f['schema_when']={'tr_review_profile':'TCNOPEN_3_0_0'}
 return out
