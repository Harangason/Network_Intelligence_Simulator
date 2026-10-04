"""Independent Sparkplug session and metric boundary regressions."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.sparkplug_b import rules as R
def actual():
 x={'spb_'+k:'synthetic-'+k for k in R.REQUIRED}
 x.update(spb_edition='SPARKPLUG_3_0',spb_proposal_mode='ACTUAL_CONFIG',spb_mqtt_version='3.1.1',spb_message='NDATA',spb_clean_session=True,spb_group_id='group',spb_edge_id='node',spb_seq=1,spb_previous_seq=0,spb_timestamp_ms=1000,spb_metric_timestamp_ms=999,spb_node_online=True)
 return x
def status(x):return registry.validate_parameters('sparkplug_b',x)['status']
def msg(kind):
 x={**actual(),'spb_message':kind,'spb_topic':'spBv1.0/group/'+kind+'/node','spb_qos':1 if kind in('NDEATH','STATE')else 0,'spb_retain':kind=='STATE','spb_encoding':'JSON_UTF8'if kind=='STATE'else'PROTOBUF_B'}
 if kind.startswith('D'):x.update(spb_device_id='device',spb_topic=x['spb_topic']+'/device')
 if kind=='DDATA':x['spb_device_online']=True
 if kind in('NBIRTH','DBIRTH'):x.update(spb_datatype=3,spb_name_present=True)
 if kind=='NBIRTH':x.update(spb_seq=0,spb_bdseq=0,spb_will_bdseq=0,spb_rebirth_control=False)
 if kind=='NDEATH':x.pop('spb_seq');x.update(spb_metrics_count=1)
 if kind=='STATE':x.update(spb_host_id='host',spb_topic='spBv1.0/STATE/host')
 return x

def test_sparkplug_explicit_application_not_ethernet_defaults():
 p=registry.profile('sparkplug_b');assert p['max_payload_bytes']is None and p['rate_model']['fields']==[]
 assert p['capacity_evidence']['status']=='MODEL_MISSING' and p['default_stack']==['sparkplug_b']
 assert status(actual())=='VALID' and status({})=='UNVERIFIED'
 f={v['key']:v for v in registry.parameter_fields('sparkplug_b')};assert not set(R.REMOVED)&set(f)
 for k in('payload_bytes','spb_reorder_ms','spb_alias','spb_bdseq','spb_metric_timestamp_ms'):
  assert 'default'not in f[k]and'conditional_defaults'not in f[k]
 for bad in({'nominal_bitrate_bps':500000},{'mtu_bytes':1500},{'local_timing_evidence':{'confirmed':True}}):assert status({**actual(),**bad})=='INVALID'

@pytest.mark.parametrize('field',registry.parameter_fields('sparkplug_b'),ids=lambda f:f['key'])
def test_every_sparkplug_field_type_and_bounds(field):
 k=field['key'];assert status({**actual(),k:'wrong'if field['type']=='number'else 1})=='INVALID'
 for edge,offset in [('min',-1),('max',1)]:
  if field.get(edge)is not None:assert status({**actual(),k:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('kind',R.MESSAGES)
def test_each_message_topic_encoding_qos_retention_and_device_scope(kind):
 x=msg(kind);assert status(x)=='VALID'
 for bad in({'spb_topic':'spBv1.0/other/node'},{'spb_qos':2},{'spb_retain':not x['spb_retain']},{'spb_encoding':'PROTOBUF_B'if kind=='STATE'else'JSON_UTF8'}):assert status({**x,**bad})=='INVALID'
 if not kind.startswith('D'):assert status({**x,'spb_device_id':'extra'})=='INVALID'
 else:assert status({k:v for k,v in x.items()if k!='spb_device_id'})=='UNVERIFIED'

@pytest.mark.parametrize('key',['group_id','edge_id','device_id','host_id'])
@pytest.mark.parametrize('bad',['a/b','a+b','a#b','a\x00b'])
def test_case_sensitive_topic_tokens_forbid_wildcards_and_separator(key,bad):
 x=msg('DDATA')if key=='device_id'else msg('STATE')if key=='host_id'else actual()
 assert status({**x,'spb_'+key:bad})=='INVALID'

def test_node_wide_sequence_wrap_and_birth_strict_clause_zero():
 x={**actual(),'spb_previous_seq':255,'spb_seq':0};assert status(x)=='VALID'
 assert status({**x,'spb_seq':256})=='INVALID';assert status({**x,'spb_seq':1})=='INVALID'
 assert status({**msg('NBIRTH'),'spb_seq':1})=='INVALID'
 assert status({**msg('NDEATH'),'spb_seq':1})=='INVALID'

def test_bdseq_separate_connection_counter_and_death_match():
 x={**actual(),'spb_initial_connect':False,'spb_previous_bdseq':255,'spb_bdseq':0};assert status(x)=='VALID'
 assert status({**x,'spb_bdseq':1})=='INVALID'
 assert status({**msg('NBIRTH'),'spb_will_bdseq':1})=='INVALID'
 x={**msg('NDEATH'),'spb_bdseq':0,'spb_birth_bdseq':1,'spb_death_matches':False};assert status(x)=='VALID'
 assert status({**x,'spb_death_matches':True})=='INVALID'
 assert status({**x,'spb_bdseq':1,'spb_death_matches':True})=='VALID'
 assert status({**x,'spb_bdseq_datatype':3})=='INVALID'

def test_mqtt_clean_rules_distinct_from_persistent_application_connection():
 assert status({**actual(),'spb_clean_session':False})=='INVALID'
 x={**actual(),'spb_mqtt_version':'5.0','spb_clean_start':True,'spb_session_expiry_s':0};assert status(x)=='VALID'
 assert status({**x,'spb_clean_start':False})=='INVALID';assert status({**x,'spb_session_expiry_s':1})=='INVALID'

def test_state_birth_will_timestamp_match_and_boolean_online():
 x={**msg('STATE'),'spb_state_birth':True,'spb_state_online':True,'spb_will_timestamp_ms':1000};assert status(x)=='VALID'
 assert status({**x,'spb_state_online':False})=='INVALID';assert status({**x,'spb_timestamp_ms':1001})=='INVALID'
 assert status({**x,'spb_state_birth':False,'spb_state_online':False,'spb_timestamp_ms':2000})=='VALID'

def test_current_device_birth_not_inferred_from_node_online():
 assert status({**msg('DDATA'),'spb_device_online':False})=='INVALID'
 assert status({**msg('DBIRTH'),'spb_node_online':False})=='INVALID'

def test_alias_birth_name_required_data_name_excluded_current_mapping():
 x={**msg('DBIRTH'),'spb_alias_used':True,'spb_alias':18446744073709551615,'spb_alias_unique':True};assert status(x)=='VALID'
 assert status({**x,'spb_name_present':False})=='INVALID';assert status({**x,'spb_alias_unique':False})=='INVALID'
 x={**actual(),'spb_alias_used':True,'spb_alias':0,'spb_name_present':False,'spb_alias_bound':True};assert status(x)=='VALID'
 assert status({**x,'spb_name_present':True})=='INVALID';assert status({**x,'spb_alias_bound':False})=='INVALID'

@pytest.mark.parametrize('bad',[{'spb_datatype':20},{'spb_property_datatype':19},{'spb_dataset_datatype':16},{'spb_template_parameter_datatype':22}])
def test_datatype_scope_not_one_shared_enum_for_every_construct(bad):assert status({**actual(),**bad})=='INVALID'

@pytest.mark.parametrize('quality,code',[('BAD',0),('GOOD',192),('STALE',500)])
def test_quality_property_code_and_int32_type(quality,code):
 x={**actual(),'spb_quality':quality,'spb_quality_code':code,'spb_quality_datatype':3};assert status(x)=='VALID'
 assert status({**x,'spb_quality_datatype':4})=='INVALID';assert status({**x,'spb_quality_code':1})=='INVALID'

def test_null_zero_and_historical_do_not_become_current_values():
 assert status({**actual(),'spb_null':False,'spb_value_present':False})=='INVALID'
 assert status({**actual(),'spb_null':True,'spb_value_present':False})=='VALID'
 assert status({**actual(),'spb_data_accepted':True,'spb_historical':True})=='INVALID'

def test_property_and_dataset_array_cardinality():
 x={**actual(),'spb_property_keys_count':2,'spb_property_values_count':2,'spb_dataset_columns':3,'spb_dataset_headers':3,'spb_dataset_types':3,'spb_dataset_row_elements':3};assert status(x)=='VALID'
 for k in('property_values_count','dataset_headers','dataset_types','dataset_row_elements'):assert status({**x,'spb_'+k:4})=='INVALID'

def test_templates_definition_only_node_birth_and_instance_bound_subset():
 x={**msg('NBIRTH'),'spb_template_kind':'DEFINITION','spb_template_ref_present':False};assert status(x)=='VALID'
 assert status({**x,'spb_message':'DBIRTH'})=='INVALID';assert status({**x,'spb_template_ref':'extra'})=='INVALID'
 x={**actual(),'spb_template_kind':'INSTANCE','spb_template_ref_present':True,'spb_template_ref':'schema','spb_template_definition_bound':True,'spb_template_members':1,'spb_template_defined_members':3};assert status(x)=='VALID'
 assert status({**x,'spb_template_members':4})=='INVALID';assert status({**x,'spb_template_definition_bound':False})=='INVALID'
 assert status({**msg('DBIRTH'),**{k:v for k,v in x.items()if k.startswith('spb_template')}})=='INVALID'

def test_complete_serialized_payload_budget_not_mqtt_remaininglength_cap():
 x={**actual(),'payload_bytes':10000,'spb_serialized_bytes':10000,'spb_mqtt_payload_budget':12000};assert status(x)=='VALID'
 assert status({**x,'payload_bytes':8})=='INVALID';assert status({**x,'spb_mqtt_payload_budget':9999})=='INVALID'

def test_reordering_timeout_source_no_universal_two_seconds():
 x={**actual(),'spb_sequence_gap':True,'spb_reorder_ms':200,'spb_elapsed_reorder_ms':199,'spb_rebirth_requested':False};assert status(x)=='VALID'
 assert status({**x,'spb_elapsed_reorder_ms':200})=='INVALID'
 assert status({**x,'spb_elapsed_reorder_ms':200,'spb_rebirth_requested':True})=='VALID'
 assert status({**x,'spb_reorder_ms':0,'spb_elapsed_reorder_ms':0,'spb_rebirth_requested':True})=='VALID'

def test_functional_timing_complete_broker_path_and_freshness():
 x={**actual(),'spb_source_bound_ms':1,'spb_broker_path_bound_ms':2,'spb_consumer_bound_ms':3,'spb_e2e_bound_ms':6,'spb_e2e_limit_ms':6,'spb_age_ms':5,'spb_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'spb_e2e_bound_ms':3},{'spb_e2e_limit_ms':5},{'spb_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 assert status({**x,'spb_data_accepted':True})=='UNVERIFIED'

def test_literal_defaults_are_scoped_source_proposals():
 f={v['key']:v for v in registry.parameter_fields('sparkplug_b')}
 assert {v['value']for v in f['spb_qos']['conditional_defaults']}=={0,1}
 assert all(v['when']['spb_proposal_mode']=='SOURCE_BASELINE'for v in f['spb_qos']['conditional_defaults'])
