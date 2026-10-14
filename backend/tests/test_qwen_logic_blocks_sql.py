"""Actual standard reuse through canonical review/apply; prescribed isolated SQL runner."""
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from backend.tests.test_qwen_function_blocks_sql import model_fixture
from backend.nis.agent.tools.function_blocks import generate_proposal,QwenBlockGenerator
from backend.nis.agent.tools.model import model_revision
from backend.nis.agent.tools import proposal_service as proposals
from backend.nis.infrastructure.persistence.db import RequestUnit,get_connection
from backend.nis.infrastructure.persistence.repository import create_object,update_object
from backend.nis.infrastructure.storage.saved_storage import ProjectArtifactStore
from backend.nis.engineering.projects.project_context import current_project_id
from backend.nis.simulation.signals.core.registry import SignalBehaviorRegistry

def setup_logic():
    source,output,ecu=model_fixture(device_class=4)
    source=update_object('Signal',str(source['id']),{'name':'A','unit':'','data_type':'bool',
        'min_value':0,'max_value':1,'length_bits':1,'expected_version':source['version']})
    sources={'A':source}
    for name in ('B','C','D'):
        sources[name]=create_object('Signal',{'name':name,'message_id':str(source['message_id']),
            'unit':'','data_type':'bool','min_value':0,'max_value':1,'length_bits':1})
    return sources,output,ecu

def arguments(sources,output,standard='DECISION_ABCD'):
    selected=SignalBehaviorRegistry.get_function_block_standard(standard)
    return {'signal_id':str(output['id']),'model_revision':model_revision(),'requirements':'Explicit grouped Boolean decision for this class-4 function',
       'standard_id':standard,'input_bindings':{name:{'signal_id':str(sources[name]['id']),'type':'boolean','unit':'',
              'max_age_ms':100.,'on_stale':'fallback','fallback':False} for name in selected['input_types']},
       'parameter_values':{},'verification_cases':deepcopy(selected['definition']['verification_cases']),
       'on_invalid':'hold_output','invalid_output':False}

def test_standard_is_reused_without_llm_call_and_review_apply_saved_origin_preserved(monkeypatch,tmp_path):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT',str(tmp_path))
    sources,output,ecu=setup_logic()
    monkeypatch.setattr(QwenBlockGenerator,'generate',lambda *_: (_ for _ in ()).throw(AssertionError('Standard reuse must not regenerate code')))
    unit=RequestUnit(current_project_id())
    try:
        result=generate_proposal(arguments(sources,output))
        unit.finish(True)
    finally:
        unit.close()
    validated=proposals.validate(result['proposal_id'])
    assert validated['validation_result']['valid'],validated['validation_result']
    with pytest.raises(PermissionError):
        proposals.apply(result['proposal_id'],actor='test',trace_id='unreviewed')
    proposals.review(result['proposal_id'],revision=validated['revision'],decision='approve',actor='human-review',trace_id=str(uuid4()))
    unit=RequestUnit(current_project_id())
    try:
        applied=proposals.apply(result['proposal_id'],actor='human-review',trace_id=str(uuid4()))
        unit.finish(True)
    finally:
        unit.close()
    assert applied['status']=='APPLIED'
    with get_connection() as connection:
        row=connection.execute('SELECT parameters FROM engineering_signal_behaviors WHERE project_id=%s AND signal_id=%s',
          (current_project_id(),str(output['id']))).fetchone()
    definition=row['parameters']['function_block']
    assert definition['logic_rule']['inputs']==['A','B','C','D']
    assert definition['standard_origin']['standard_id']=='DECISION_ABCD'
    assert definition['provenance']['generated_by']=='QWEN'
    store=ProjectArtifactStore(current_project_id())
    manifest=json.loads(store.path('manifest.json').read_text())
    assert manifest['function_blocks']
    source_ref=manifest['function_blocks'][0]['source']
    assert store.path(source_ref['path']).read_text()==definition['source_code']

def test_custom_grouped_rule_is_given_to_qwen_as_data_and_verified(monkeypatch,tmp_path):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT',str(tmp_path))
    sources,output,_=setup_logic()
    args=arguments(sources,output)
    args.pop('standard_id')
    args['logic_expression']='(A ODER B) UND C UND NICHT D'
    recorded={}
    def generated(_self,requirements,context,bindings,parameters):
        recorded.update(context)
        return SignalBehaviorRegistry.get_function_block_standard('DECISION_ABCD')['definition']
    monkeypatch.setattr(QwenBlockGenerator,'generate',generated)
    unit=RequestUnit(current_project_id())
    try:
        result=generate_proposal(args)
        unit.finish(True)
    finally:
        unit.close()
    assert result['proposal_id']
    assert recorded['logic_rule']['tree']['operator']=='AND'
    assert recorded['project_id']==current_project_id()

def test_standard_rejects_missing_truth_vector_and_stale_revision_before_creating_proposal():
    sources,output,_=setup_logic()
    args=arguments(sources,output)
    args['verification_cases'][0]['steps'].pop()
    with pytest.raises(ValueError,match='complete truth table'):
        generate_proposal(args)
    args=arguments(sources,output)
    args['model_revision']='stale'
    with pytest.raises(ValueError,match='revision'):
        generate_proposal(args)
    with get_connection() as connection:
        assert not connection.execute('SELECT 1 FROM engineering_signal_behaviors WHERE project_id=%s',(current_project_id(),)).fetchone()

def test_join_model_parameter_survives_real_review_apply_and_saved_definition(monkeypatch,tmp_path):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT',str(tmp_path))
    sources,output,_=setup_logic()
    args=arguments(sources,output,'JOIN')
    args['parameter_values']={'N':2}
    monkeypatch.setattr(QwenBlockGenerator,'generate',lambda *_: (_ for _ in ()).throw(AssertionError('Reuse original QWEN JOIN')))
    unit=RequestUnit(current_project_id())
    try:
        result=generate_proposal(args)
        unit.finish(True)
    finally:
        unit.close()
    validated=proposals.validate(result['proposal_id'])
    assert validated['validation_result']['valid'],validated['validation_result']
    proposals.review(result['proposal_id'],revision=validated['revision'],decision='approve',actor='human-review',trace_id=str(uuid4()))
    unit=RequestUnit(current_project_id())
    try:
        applied=proposals.apply(result['proposal_id'],actor='human-review',trace_id=str(uuid4()))
        unit.finish(True)
    finally:
        unit.close()
    assert applied['status']=='APPLIED'
    with get_connection() as connection:
        row=connection.execute('SELECT parameters FROM engineering_signal_behaviors WHERE project_id=%s AND signal_id=%s',
            (current_project_id(),str(output['id']))).fetchone()
    assert row['parameters']['block_parameters']=={'N':2}
    definition=row['parameters']['function_block']
    assert definition['standard_origin']['standard_id']=='JOIN'
    assert len(definition['verification_cases'])==5
    store=ProjectArtifactStore(current_project_id())
    manifest=json.loads(store.path('manifest.json').read_text())
    assert store.path(manifest['function_blocks'][0]['source']['path']).read_text()==definition['source_code']
