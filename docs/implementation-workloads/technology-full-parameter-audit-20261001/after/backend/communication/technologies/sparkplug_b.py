"""Sparkplug B session/metric semantics, independent from MQTT bearer capacity.

Copyright (c) 2016-2022 Eclipse Foundation. This software includes material
derived from the Sparkplug Specification: https://www.eclipse.org/tahu/spec/sparkplug_spec.pdf
"""
from .native_review_support import declaration,fields as build_fields,WIRE_KEYS,ETHERNET_KEYS
SPEC='https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf'
SOURCES={SPEC:'Eclipse Sparkplug3.0.0 November16 2022 original141-page PDF; selected chapters2,4,5,6 read. Namespace spBv1.0 denotes encoding not specification edition. No full TCK certification.'}
DECLARATIONS=[]
def d(k,t,meaning,**kw):DECLARATIONS.append(declaration('spb_',k,t,meaning,SPEC,SOURCES[SPEC],**kw))
MESSAGES=['NBIRTH','NDEATH','DBIRTH','DDEATH','NDATA','DDATA','NCMD','DCMD','STATE']
for k,meaning,opts in[
 ('edition','Actual selected Sparkplug edition.',['SPARKPLUG_3_0','REGISTERED_ACTUAL']),
 ('proposal_mode','Explicit source baseline proposals versus commissioned values.',['ACTUAL_CONFIG','SOURCE_BASELINE']),
 ('namespace','Actual topic namespace encodes payload version.',['spBv1.0','spAv1.0']),
 ('mqtt_version','Actual bound MQTT protocol edition, separate own MQTT profile.',['3.1.1','5.0']),
 ('message','Actual Sparkplug message role. Edge will death differs from retained host STATE. ',MESSAGES),
 ('encoding','Actual STATE JSON UTF8 versus other Sparkplug Google Protobuf payload.',['PROTOBUF_B','JSON_UTF8']),
 ('reporting','Actual reporting choice; RBE recommended, periodic allowed, no guessed scan interval.',['RBE','PERIODIC']),
 ('quality','Actual consuming data quality; historic values are not realtime acceptance.',['GOOD','BAD','STALE']),
 ('template_kind','Actual template definition versus instance.',['DEFINITION','INSTANCE']),
 ('outcome','Actual independently correlated consuming application result.',['ACCEPTED','STALE','MISSING','UNKNOWN']),
]:d(k,'select',meaning,options=opts)
for k,meaning,lo,hi,unit in[
 ('qos','Actual message MQTT QoS, STATE1, edge NDEATHwill1, other publishes0.',0,2,None),
 ('subscribe_qos','Actual command/STATE subscription QoS1, distinct publishing QoS0.',0,2,None),
 ('seq','Actual edge message sequence8bit shared across node and device topics; absent NDEATH.',0,255,None),
 ('previous_seq','Actual last message sequence from same edge node, not independent per-topic counter.',0,255,None),
 ('bdseq','Actual INT64-valued birth/death connection counter constrained0..255.',0,255,None),
 ('previous_bdseq','Actual previous connection counter, not message seq.',0,255,None),
 ('will_bdseq','Actual bdSeq in current MQTT CONNECTwill.',0,255,None),
 ('birth_bdseq','Actual correlated NBIRTH counter for NDEATH matching.',0,255,None),
 ('bdseq_datatype','Actual bdSeq Sparkplug datatype INT64 enum4, distinct protobuf uint64 representation.',0,34,None),
 ('session_expiry_s','Actual MQTT5 session expiry0 required, distinct application connection persistence.',0,4294967295,'s'),
 ('timestamp_ms','Actual payload UTC publish timestamp; unsigned64 actual epoch millisecond count.',0,18446744073709551615,'ms'),
 ('will_timestamp_ms','Actual STATE CONNECTwill timestamp matched by host birth.',0,18446744073709551615,'ms'),
 ('previous_state_ms','Actual latest accepted STATE timestamp per host/session.',0,18446744073709551615,'ms'),
 ('metric_timestamp_ms','Actual metric acquisition UTC timestamp, separate publish timestamp.',0,18446744073709551615,'ms'),
 ('alias','Actual unsigned64 metric alias unique across whole edge node, including devices.',0,18446744073709551615,None),
 ('datatype','Actual metric Sparkplug enum basic1..14/additional15..19/arrays22..34; PropertySet20/21 not metric.',0,34,None),
 ('quality_code','Actual Quality property value0 BAD/192 GOOD/500 STALE.',0,500,None),
 ('quality_datatype','Actual Quality PropertyValue datatype INT32 enum3.',0,34,None),
 ('metrics_count','Actual payload metric count; NDEATH onlybdSeq, no generic payload cap.',0,None,None),
 ('birth_metric_count','Actual complete known birth catalogue of node/device metrics.',0,None,None),
 ('serialized_bytes','Actual encoded complete payload, not sum of fixed8byte metric values.',0,None,'byte'),
 ('mqtt_payload_budget','Actual independently qualified MQTT message payload budget including version/broker restrictions.',0,None,'byte'),
 ('property_keys_count','Actual PropertySet keys array count.',0,None,None),
 ('property_values_count','Actual PropertySet PropertyValue array count matches keys.',0,None,None),
 ('property_datatype','Actual PropertyValue basic1..14 orPropertySet20/21, not additional metric types.',0,34,None),
 ('dataset_columns','Actual DataSet number of columns, unsigned64; no presumed8channel dataset.',0,18446744073709551615,None),
 ('dataset_headers','Actual DataSet columns array count.',0,None,None),
 ('dataset_types','Actual DataSet type array count.',0,None,None),
 ('dataset_row_elements','Actual selected row element count versus declared columns.',0,None,None),
 ('dataset_datatype','Actual selected column basic datatype1..14.',0,34,None),
 ('template_members','Actual selected template instance member count.',0,None,None),
 ('template_defined_members','Actual complete birth template member catalogue.',0,None,None),
 ('template_parameter_datatype','Actual selected template parameter basic datatype1..14.',0,34,None),
 ('metadata_size','Actual optional byte-array/file total size, not whole MQTT frame.',0,18446744073709551615,'byte'),
 ('metadata_seq','Actual optional multipart metric part sequence unsigned64, distinct edge message seq8bit.',0,18446744073709551615,None),
 ('reorder_ms','Actual configurable host reorder timeout; source permits0 with qualified in-order broker, no2second default.',0,None,'ms'),
 ('elapsed_reorder_ms','Actual elapsed selected reorder window.',0,None,'ms'),
 ('source_bound_ms','Actual source acquisition/encoding bound.',0,None,'ms'),
 ('broker_path_bound_ms','Actual complete MQTT path including broker queue/security/forwarding.',0,None,'ms'),
 ('consumer_bound_ms','Actual decoding/type/session/metric acceptance bound.',0,None,'ms'),
 ('e2e_bound_ms','Actual sum source/brokerpath/consumer, not QoS1delivery functional success.',0,None,'ms'),
 ('e2e_limit_ms','Actual independent functional deadline.',0,None,'ms'),
 ('age_ms','Actual consumed sample age, historical flag alone does not determine all age.',0,None,'ms'),
 ('freshness_ms','Actual functional data age limit.',0,None,'ms'),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=unit!='ms' or k in('timestamp_ms','will_timestamp_ms','previous_state_ms','metric_timestamp_ms'))
for k,meaning in[
 ('retain','Actual STATE retainedtrue, edge publications false.'),('clean_session','Actual MQTT3.1.1 CONNECT clean sessiontrue.'),
 ('clean_start','Actual MQTT5 CONNECT clean starttrue.'),('initial_connect','Actual first connection versus reconnect.'),
 ('node_online','Actual node NBIRTH/session status, no proof that attached devices have DBIRTH.'),
 ('device_online','Actual current device birth status in current node session.'),('primary_required','Actual configured primary host dependency.'),
 ('primary_online','Actual accepted matching primary host STATE.'),('alias_used','Actual metric uses alias assigned in current birth.'),
 ('name_present','Actual selected metric name present in payload.'),('alias_unique','Actual aliases checked across whole node catalogue.'),
 ('alias_bound','Actual data/command alias matches current birth catalogue.'),('historical','Actual stored historical metric, cannot certify realtime.'),
 ('transient','Actual metric not intended for historian storage.'),('null','Actual explicit null value flag, distinct numeric0.'),
 ('value_present','Actual metric oneof value present and valid for declared datatype.'),('metric_schema_verified','Actual complete current birth/data/properties/template codec and datatype mapping verified.'),
 ('birth_complete','Actual birth includes every reportable metric and template definition.'),('rebirth_control','Actual NBIRTH NodeControl/Rebirth booleanfalse.'),
 ('death_matches','Actual received NDEATH bdSeq matches current birth, stale old death must not invalidate new session.'),
 ('state_online','Actual STATE JSONonline flag.'),('state_birth','Actual host STATEbirth versus death.'),
 ('sequence_gap','Actual missing sequence after reordering.'),('rebirth_requested','Actual mandatory NCMDrebirth sent after missing-sequence timeout.'),
 ('template_definition_bound','Actual template instance references current NBIRTH definition and declared members/parameters.'),
 ('template_ref_present','Actual template ref omitted fordefinition and present forinstance.'),
 ('data_accepted','Actual independent current functional application acceptance.'),
]:d(k,'boolean',meaning)
for k,meaning in[
 ('group_id','Actual case-sensitive nonwildcard topic group identity.'),('edge_id','Actual case-sensitive edge identity unique withgroup.'),
 ('device_id','Actual identity unique within node, can repeat across nodes.'),('host_id','Actual host identity globally unique.'),
 ('topic','Actual complete case-sensitive topic, distinct subscribe wildcard filter.'),('metric_name','Actual friendly UTF8 metric hierarchy, no blanketASCII/specialcharacter ban.'),
 ('uuid','Actual optional payload schema identity, no generated confirmation.'),('template_ref','Actual NBIRTH definition metric name.'),
 ('metadata_content_type','Actual optional MIME content type.'),('metadata_file_name','Actual optional file name.'),
 ('metadata_file_type','Actual optional file type.'),('metadata_md5','Actual optional file/byte MD5 representation.'),('metadata_description','Actual optional freeform metadata.'),
 ('device_source','Actual implementation/version/broker/session capabilities.'),('binding_source','Actual explicit MQTTtransport/security/topic endpoint identities.'),
 ('codec_source','Actual protobufschema/oneof/metric/alias/properties/dataset/template serializer.'),('acceptance_source','Actual independent consumer timing/freshness/state requirements.'),
 ('observation_source','Actual correlated source/broker/session/sequence/birth/consumer trace.'),('registered_source','Actual independently qualified alternative edition.'),
]:d(k,'text',meaning)
REQUIRED=('edition','proposal_mode','mqtt_version','message','device_source','binding_source','codec_source','acceptance_source')
REMOVED={k:'Explicit Sparkplug state/topic/metric layer; foreign link/rate/retry/gateway capacity belongs to independently bound MQTT and PHY.'for k in WIRE_KEYS+ETHERNET_KEYS}

def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='spb_'+k,when={'spb_'+a:b for a,b in(w or{}).items()},source=SPEC,source_revision=SOURCES[SPEC],**kw))
 rules.append(dict(parameter='local_timing_evidence',allowed=[],source=SPEC))
 r('registered_source',{'edition':'REGISTERED_ACTUAL'},required=True)
 r('namespace',{'edition':'SPARKPLUG_3_0'},allowed=['spBv1.0'])
 for k in('group_id','edge_id','device_id','host_id'):r(k,pattern=r'[^+/#\x00]+')
 for msg in MESSAGES:
  w={'edition':'SPARKPLUG_3_0','message':msg}
  r('qos',w,allowed=[1 if msg in('NDEATH','STATE')else 0]);r('retain',w,allowed=[msg=='STATE'])
  r('encoding',w,allowed=['JSON_UTF8'if msg=='STATE'else'PROTOBUF_B'])
  if msg in('DBIRTH','DDATA','DDEATH','DCMD'):r('device_id',w,required=True)
  else:r('device_id',w,allowed=[])
  if msg=='STATE':
   r('host_id',w,required=True);r('topic',w,text_join=[{'literal':'spBv1.0/STATE/'},{'parameter':'spb_host_id'}])
  else:
   for k in('group_id','edge_id'):r(k,w,required=True)
   r('topic',w,text_join=[{'literal':'spBv1.0/'},{'parameter':'spb_group_id'},{'literal':'/'+msg+'/'},{'parameter':'spb_edge_id'}]+([{'literal':'/'},{'parameter':'spb_device_id'}]if msg.startswith('D')else[]))
  if msg in('NBIRTH','DBIRTH','NDATA','DDATA','DDEATH'):r('seq',w,required=True)
  if msg in('DBIRTH','NDATA','DDATA','DDEATH'):r('seq',w,equal_expression={'integer_remainder':[{'sum':['spb_previous_seq',1]},256]})
  if msg=='NDEATH':r('seq',w,allowed=[]);r('metrics_count',w,allowed=[1])
  if msg not in('DDEATH','NDEATH'):r('timestamp_ms',w,required=True)
  if msg in('NBIRTH','DBIRTH'):
   r('birth_complete',w,allowed=[True]);r('metrics_count',w,equal_parameter='spb_birth_metric_count')
   r('datatype',w,required=True);r('name_present',w,required=True,allowed=[True])
  if msg in('NBIRTH','DBIRTH','NDATA','DDATA'):r('metric_timestamp_ms',w,required=True)
  if msg=='NBIRTH':
   r('seq',w,allowed=[0]);r('bdseq',w,required=True,equal_parameter='spb_will_bdseq');r('rebirth_control',w,required=True,allowed=[False])
  if msg in('DBIRTH','NDATA','DDATA','DDEATH'):r('node_online',w,required=True,allowed=[True])
  if msg=='DDATA':r('device_online',w,required=True,allowed=[True])
 r('clean_session',{'mqtt_version':'3.1.1'},required=True,allowed=[True])
 r('clean_start',{'mqtt_version':'5.0'},required=True,allowed=[True]);r('session_expiry_s',{'mqtt_version':'5.0'},required=True,allowed=[0])
 r('subscribe_qos',allowed=[1]);r('bdseq_datatype',allowed=[4])
 r('bdseq',{'initial_connect':True},allowed=[0])
 r('bdseq',{'initial_connect':False},equal_expression={'integer_remainder':[{'sum':['spb_previous_bdseq',1]},256]})
 r('death_matches',{'message':'NDEATH'},equals_parameters_boolean=['spb_bdseq','spb_birth_bdseq'])
 r('state_online',{'message':'STATE','state_birth':True},allowed=[True])
 r('state_online',{'message':'STATE','state_birth':False},allowed=[False])
 r('timestamp_ms',{'message':'STATE','state_birth':True},equal_parameter='spb_will_timestamp_ms')
 r('primary_online',{'primary_required':True,'data_accepted':True},required=True,allowed=[True])
 for msg in('NBIRTH','DBIRTH','NDATA','DDATA','NCMD','DCMD'):
  w={'message':msg,'alias_used':True};r('alias',w,required=True);r('alias_unique',w,allowed=[True]);r('alias_bound',w,allowed=[True])
  r('name_present',w,required=True,allowed=[msg in('NBIRTH','DBIRTH')])
 r('name_present',{'alias_used':False},required=True,allowed=[True])
 r('value_present',{'null':False},required=True,allowed=[True])
 r('datatype',allowed=list(range(1,20))+list(range(22,35)))
 r('property_datatype',allowed=list(range(1,15))+[20,21]);r('dataset_datatype',minimum=1,maximum=14);r('template_parameter_datatype',minimum=1,maximum=14)
 r('quality_datatype',allowed=[3]);r('quality_code',allowed=[0,192,500])
 for quality,code in [('BAD',0),('GOOD',192),('STALE',500)]:r('quality_code',{'quality':quality},allowed=[code])
 r('property_values_count',equal_parameter='spb_property_keys_count')
 for k in('dataset_headers','dataset_types','dataset_row_elements'):r(k,equal_parameter='spb_dataset_columns')
 r('template_ref_present',{'template_kind':'DEFINITION'},allowed=[False]);r('message',{'template_kind':'DEFINITION'},allowed=['NBIRTH'])
 r('template_ref',{'template_kind':'DEFINITION'},allowed=[])
 r('template_ref_present',{'template_kind':'INSTANCE'},required=True,allowed=[True]);r('template_ref',{'template_kind':'INSTANCE'},required=True)
 r('template_definition_bound',{'template_kind':'INSTANCE'},required=True,allowed=[True])
 r('template_members',maximum_parameter='spb_template_defined_members')
 for msg in('NBIRTH','DBIRTH'):r('template_members',{'message':msg,'template_kind':'INSTANCE'},equal_parameter='spb_template_defined_members')
 r('metadata_md5',pattern=r'[0-9A-Fa-f]{32}')
 r('serialized_bytes',maximum_parameter='spb_mqtt_payload_budget');rules.append(dict(parameter='payload_bytes',equal_parameter='spb_serialized_bytes',source=SPEC))
 r('rebirth_requested',{'sequence_gap':True},when_present=['spb_elapsed_reorder_ms'],required=True)
 r('elapsed_reorder_ms',{'sequence_gap':True,'rebirth_requested':False},exclusive_maximum_expression='spb_reorder_ms')
 chain=('source_bound_ms','broker_path_bound_ms','consumer_bound_ms')
 r('e2e_bound_ms',equal_expression={'sum':['spb_'+k for k in chain]})
 for k in chain:r(k,when_present=['spb_e2e_bound_ms'],required=True)
 r('e2e_bound_ms',maximum_parameter='spb_e2e_limit_ms');r('age_ms',maximum_parameter='spb_freshness_ms')
 w={'data_accepted':True}
 for k,v in [('historical',False),('null',False),('quality','GOOD'),('sequence_gap',False),('metric_schema_verified',True),('outcome','ACCEPTED')]:r(k,w,required=True,allowed=[v])
 for k in('observation_source','topic','encoding','qos','retain','serialized_bytes','mqtt_payload_budget','e2e_bound_ms','e2e_limit_ms','age_ms','freshness_ms'):r(k,w,required=True)
 return dict(rate_model={'type':'EXPLICIT_SPARKPLUG_MQTT_SESSION','fields':[]},required_parameters=['spb_'+k for k in REQUIRED],native_parameter_prefixes=['spb_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',physical_layer_profile_id='independently_bound_mqtt_transport',medium_access_model='BROKER_PUBLISH_SUBSCRIBE',arbitration_model_id='ACTUAL_BROKER_QUEUES',mechanisms={'session':['BIRTH_DEATH_BDSEQ','NODE_WIDE_SEQUENCE','CURRENT_BIRTH_ALIAS_SCHEMA'],'quality':['GOOD_BAD_STALE','HISTORICAL_NOT_REALTIME'],'qualification':['OWN_MQTT_BEARER_AND_BROKER_EVIDENCE','NO_QOS_AS_FUNCTIONAL_TIMING_PROOF']})

def fields():
 defaults={}
 for msg in MESSAGES:
  w={'spb_edition':'SPARKPLUG_3_0','spb_proposal_mode':'SOURCE_BASELINE','spb_message':msg}
  for k,v in [('namespace','spBv1.0'),('qos',1 if msg in('NDEATH','STATE')else 0),('retain',msg=='STATE'),('encoding','JSON_UTF8'if msg=='STATE'else'PROTOBUF_B')]:
   defaults.setdefault('spb_'+k,[]).append(dict(when=w,value=v,source=SPEC,source_revision=SOURCES[SPEC]))
 for version,values in [('3.1.1',[('clean_session',True)]),('5.0',[('clean_start',True),('session_expiry_s',0)])]:
  for k,v in values:defaults['spb_'+k]=[dict(when={'spb_edition':'SPARKPLUG_3_0','spb_proposal_mode':'SOURCE_BASELINE','spb_mqtt_version':version},value=v,source=SPEC,source_revision=SOURCES[SPEC])]
 return build_fields(DECLARATIONS,['spb_'+k for k in REQUIRED],defaults)
