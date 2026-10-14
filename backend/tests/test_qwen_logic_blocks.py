"""Independent exhaustive expectations for the actual QWEN-authored shared blocks."""
from copy import deepcopy
import itertools
import pytest
from backend.nis.simulation.signals.core.function_block import QwenFunctionBlock,EcuRuntime,inspect_logic_expression,validate_function_spec,verify_function_cases
from backend.nis.simulation.signals.core.registry import SignalBehaviorRegistry
from backend.nis.agent.orchestration.tool_selection import select_tools

TABLES={'AND':[False,False,False,True],'OR':[False,True,True,True],'XOR':[False,True,True,False],
 'NOT':[True,False],'NAND':[True,True,True,False],'NOR':[True,False,False,False],'XNOR':[True,False,False,True],
 'BUFFER':[False,True],'IMPLIES':[True,True,False,True],'SELECT':[False,True,False,True,False,False,True,True],
 'DECISION_ABCD':[False,False,False,False,False,False,True,False,False,False,True,False,False,False,True,False]}

def standard(name):
    return SignalBehaviorRegistry.get_function_block_standard(name)

def specification(name):
    selected=standard(name)
    return {'function_block':selected['definition'],'block_parameters':{},
      'transport_inputs':{key:{'signal_id':key,'type':'boolean','unit':'','max_age_ms':100.,'on_stale':'fallback','fallback':False}
                          for key in selected['input_types']}, 'on_invalid':'hold_output','invalid_output':False}

@pytest.mark.parametrize('name',TABLES)
def test_actual_qwen_gate_complete_independent_truth_table_and_pure_boolean_output(name):
    selected=standard(name)
    definition=selected['definition']
    block=QwenFunctionBlock(definition)
    names=list(selected['input_types'])
    vectors=list(itertools.product((False,True),repeat=len(names)))
    assert [block.step(dict(zip(names,vector)),{},19.).value for vector in vectors]==TABLES[name]
    assert all(type(block.step(dict(zip(names,vector)),{},0.).value) is bool for vector in vectors)
    assert block.state=={}
    assert definition['provenance']['generated_by']=='QWEN'
    assert definition['standard_origin']['owner']=='SignalBehaviorRegistry'

def test_shared_standard_discovery_includes_original_scalar_blocks_and_returns_copies():
    catalog=SignalBehaviorRegistry.function_block_standards()
    assert len(catalog['standards'])==18
    assert {'Hysteresis','FirstOrderFilter','OnDelay','RateLimiter','ValidityGate','Threshold'} <= {row['id'] for row in catalog['standards']}
    original=standard('AND')
    original['definition']['source_code']='forged'
    assert standard('and')['definition']['source_code']!='forged'
    assert 'source_code' not in catalog['standards'][0]
    assert SignalBehaviorRegistry.function_block_standards('XOR',True)['standards'][0]['source_code']
    with pytest.raises(ValueError,match='Unknown function standard'):
        standard('UNKNOWN')

def test_grouped_user_expression_has_exact_tree_and_xor_is_explicit():
    rule=inspect_logic_expression('(A ODER B) UND C UND NICHT D')
    assert rule['inputs']==['A','B','C','D']
    assert rule['tree']=={'operator':'AND','operands':[{'operator':'OR','operands':[{'input':'A'},{'input':'B'}]},
                           {'input':'C'},{'operator':'NOT','operands':[{'input':'D'}]}]}
    assert inspect_logic_expression('XOR(A, B, C)')['tree']['operator']=='XOR'
    assert inspect_logic_expression('A != B')['tree']['operator']=='XOR'

@pytest.mark.parametrize('expression',['A + B','A > 0','__import__("os")','A.attr','A ^ B','JOIN(A,B)','SELECT(A,B)','A and 1'])
def test_boolean_rule_rejects_numeric_truthiness_code_injection_and_invalid_join(expression):
    with pytest.raises(ValueError):
        inspect_logic_expression(expression)

def test_logic_bindings_types_coverage_and_statelessness_are_mandatory():
    parameters=specification('AND')
    validate_function_spec(parameters)
    bad=deepcopy(parameters)
    bad['transport_inputs']['A']['type']='number'
    with pytest.raises(ValueError,match='Boolean'):
        validate_function_spec(bad)
    bad=deepcopy(parameters)
    bad['function_block']['verification_cases'][0]['steps'].pop()
    with pytest.raises(ValueError,match='complete truth table'):
        validate_function_spec(bad)
    with pytest.raises(ValueError,match='True/False'):
        QwenFunctionBlock(parameters['function_block']).step({'A':1,'B':True},{},0.)
    bad=deepcopy(parameters['function_block'])
    bad.pop('source_sha256')
    bad['source_code']=bad['source_code'].replace('return ', 'return dt > 1 or ',1)
    with pytest.raises(ValueError,match='independent of time'):
        QwenFunctionBlock(bad)
    physical={'A':{'unit':'','data_type':'float','min_value':0,'max_value':100,'length_bits':16},
              'B':{'unit':'','data_type':'bool','min_value':0,'max_value':1,'length_bits':1}}
    with pytest.raises(ValueError,match='canonical Boolean'):
        validate_function_spec(parameters,physical)

def test_boolean_runtime_hold_on_invalid_input_and_run_isolation():
    parameters=specification('OR')
    runtime=EcuRuntime()
    assert runtime.evaluate('ecu','output',parameters,{'A':False,'B':True},0.,True)[0] is True
    value,evidence=runtime.evaluate('ecu','output',parameters,{},.1,False)
    assert value is True and evidence['status']=='INVALID_INPUT_HOLD_OUTPUT'
    assert EcuRuntime().evaluate('ecu','output',parameters,{},.1,False)[0] is False
    assert runtime.evaluate('ecu','output',parameters,{'A':False,'B':False},.2,True)[0] is False

@pytest.mark.parametrize('prompt',['Baukasten: XOR und logische Verknüpfungen der Signale','JOIN(N, A, B)'])
def test_logic_intent_discovers_registry_and_parser_without_losing_identity_tools(prompt):
    tools=[{'name':name} for name in ['inspect_project','inspect_object','search_model','discover_engineering_tools',
        'ask_engineering_question','inspect_function_block_standards','inspect_logic_expression','generate_function_block_proposal']]
    selected={row['name'] for row in select_tools(prompt,tools)}
    assert {'inspect_project','inspect_function_block_standards','inspect_logic_expression','generate_function_block_proposal'} <= selected

@pytest.mark.parametrize('standard_name',['OR','JOIN'])
def test_boolean_joined_condition_uses_distinct_actually_received_fields_and_keeps_loss_evidence(tmp_path,standard_name):
    from backend.tests.test_transport_cascades import cascade_config
    from backend.nis.simulation.hardware_profile import normalize_hardware_config
    from backend.nis.traces.universal_trace import generate_universal_events
    config=cascade_config(tmp_path,'can_fd')
    signals=config['engineering_model']['signals']
    signals[0].update(length_bits=1,min_value=0,max_value=1,data_type='bool',unit='')
    second=deepcopy(signals[0])
    second.update(id='condition-B',name='Condition B',start_bit=1)
    signals.append(second)
    behaviors=config['engineering_model']['behaviors']
    behaviors[0]['parameters']['value']=0.
    behaviors.append({'signal_id':'condition-B','behavior_type':'CONSTANT','dependencies':[],'parameters':{'value':1.}})
    input_ids=['s0','condition-B']
    if standard_name=='JOIN':
        for bit,name in enumerate(('C','D'),start=2):
            extra=deepcopy(second)
            extra.update(id='condition-'+name,name='Condition '+name,start_bit=bit)
            signals.append(extra)
            behaviors.append({'signal_id':extra['id'],'behavior_type':'CONSTANT','dependencies':[],'parameters':{'value':0.}})
            input_ids.append(extra['id'])
    config['communications'][0]['signal_ids']=input_ids
    parameters=specification(standard_name)
    parameters['transport_inputs']['A'].update(signal_id='s0',max_age_ms=15.)
    parameters['transport_inputs']['B'].update(signal_id='condition-B',max_age_ms=15.)
    if standard_name=='JOIN':
        parameters['block_parameters']={'N':1}
        for name in ('C','D'):
            parameters['transport_inputs'][name].update(signal_id='condition-'+name,max_age_ms=15.)
    parameters['on_invalid']='fallback'
    behaviors[1]={'signal_id':'s1','behavior_type':'FUNCTION_BLOCK','parameters':parameters,'dependencies':input_ids}
    signals[1].update(length_bits=1,min_value=0,max_value=1,data_type='bool',unit='',dependencies=input_ids)
    _,events=generate_universal_events(config,normalize_hardware_config(config),start_utc=1700000000)
    outputs=[event for event in events if event['route_id']=='route-1']
    good=next(event for event in outputs if event['signals'][0]['value']==1)
    evidence=good['signals'][0]['dependency_evidence']
    assert {item['signal_id'] for item in evidence['inputs']}==set(input_ids)
    assert all(item['source_event_id'] in {event['event_id'] for event in events} for item in evidence['inputs'])
    assert any(event['signals'][0]['quality']=='STALE_INPUT' and event['signals'][0]['value']==0 for event in outputs)
    assert int(good['payload_hex'][:2],16)&1==1

@pytest.mark.parametrize('count',range(5))
def test_actual_qwen_join_exact_count_all_vectors_and_configurable_n(count):
    parameters=specification('JOIN')
    parameters['block_parameters']={'N':count}
    block=validate_function_spec(parameters)
    vectors=list(itertools.product((False,True),repeat=4))
    # Independently enumerate the user's exact-count requirement for every N.
    for vector in vectors:
        result=block.step(dict(zip(('A','B','C','D'),vector)),{'N':count},13.)
        assert type(result.value) is bool
        assert result.value == (vector.count(True)==count)
        assert result.state=={}
    assert 'default' not in block.schema['N']

@pytest.mark.parametrize('value',[-1,5,1.5,True,False,float('nan'),float('inf')])
def test_join_rejects_invalid_model_count_before_execution(value):
    parameters=specification('JOIN')
    parameters['block_parameters']={'N':value}
    with pytest.raises(ValueError):
        validate_function_spec(parameters)

def test_join_requires_n_full_parameter_coverage_and_all_boolean_cases():
    parameters=specification('JOIN')
    with pytest.raises(ValueError,match='missing'):
        validate_function_spec(parameters)
    parameters['block_parameters']={'N':2}
    validate_function_spec(parameters)
    bad=deepcopy(parameters)
    bad['function_block']['verification_cases'].pop()
    with pytest.raises(ValueError,match='complete truth table'):
        validate_function_spec(bad)
    bad=deepcopy(parameters)
    bad['function_block'].pop('verification_cases')
    with pytest.raises(ValueError,match='complete independent'):
        validate_function_spec(bad)
    bad=deepcopy(parameters)
    bad['function_block']['verification_cases'][2]['steps'].pop()
    with pytest.raises(ValueError,match='complete truth table'):
        validate_function_spec(bad)
    bad=deepcopy(parameters)
    bad['function_block']['verification_cases'][2]['parameter_values']={'N':True}
    with pytest.raises(ValueError,match='integer model parameter'):
        validate_function_spec(bad)
    with pytest.raises(ValueError,match='True/False'):
        QwenFunctionBlock(parameters['function_block']).step({'A':1,'B':False,'C':True,'D':False},{'N':2},0.)

def test_join_expression_declares_count_separately_from_inputs_and_supports_composition():
    rule=inspect_logic_expression('JOIN(N, A, B, (C OR D)) AND NOT E')
    assert rule['inputs']==['A','B','C','D','E']
    assert rule['parameter_schema']['N']['maximum']==3
    assert rule['tree']['operands'][0]['count_parameter']=='N'
    assert inspect_logic_expression('JOIN(N, A, JOIN(N, B, C, D))')['parameter_schema']['N']['maximum']==2
    assert inspect_logic_expression('JOIN(N, A)')['parameter_schema']['N']['maximum']==1
    assert inspect_logic_expression('JOIN(N, A,B,C,D,E,F,G,H)')['parameter_schema']['N']['maximum']==8
    for expression in ['JOIN(2,A,B)','JOIN(N)','JOIN(M,A,B)','JOIN(N,A,1)','JOIN(N,A,B,C,D,E,F,G,H,I)','N OR A']:
        with pytest.raises(ValueError):
            inspect_logic_expression(expression)

def test_join_runtime_freezes_n_and_keeps_invalid_input_evidence():
    parameters=specification('JOIN')
    parameters['block_parameters']={'N':2}
    runtime=EcuRuntime()
    inputs={'A':True,'B':True,'C':False,'D':False}
    value,evidence=runtime.evaluate('ecu','output',parameters,inputs,0.,True)
    assert value is True and evidence['parameters']=={'N':2}
    value,evidence=runtime.evaluate('ecu','output',parameters,{},.1,False)
    assert value is True and evidence['input_valid'] is False
    changed=deepcopy(parameters)
    changed['block_parameters']['N']=1
    with pytest.raises(ValueError,match='frozen simulation'):
        runtime.evaluate('ecu','output',changed,inputs,.2,True)
    assert EcuRuntime().evaluate('ecu','output',changed,inputs,0.,True)[0] is False

def test_boolean_expectations_cannot_use_numeric_tolerance_or_nonboolean_invalid_outputs():
    parameters=specification('OR')
    bad=deepcopy(parameters)
    bad['invalid_output']=1
    with pytest.raises(ValueError,match='invalid output'):
        validate_function_spec(bad)
    bad=deepcopy(parameters)
    step=bad['function_block']['verification_cases'][0]['steps'][0]
    step.update(expected=True,tolerance=1)
    with pytest.raises(ValueError,match='failed independent case'):
        validate_function_spec(bad)
