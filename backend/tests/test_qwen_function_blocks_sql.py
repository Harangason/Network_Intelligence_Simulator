"""Real DB proposal revision, ownership and file compensation checks, isolated runner only."""
from copy import deepcopy
import json
from uuid import uuid4
import pytest
from backend.nis.agent.tools.model import ProjectRepository, model_revision
from backend.nis.agent.tools import proposal_service as proposals
from backend.nis.agent.tools.function_blocks import generate_proposal, QwenBlockGenerator
from backend.nis.infrastructure.persistence.repository import create_object, get_object, update_object
from backend.nis.infrastructure.persistence.db import RequestUnit, get_connection
from backend.nis.infrastructure.storage.saved_storage import ProjectArtifactStore
from backend.nis.engineering.projects.project_context import current_project_id
from backend.nis.workflow.services.service import WorkflowStatusService
from backend.tests.test_qwen_function_blocks import block


def model_fixture(device_class=3):
    sensor = create_object('HardwareNode', {'name':'Process temperature sensor','device_type':'SensorController','device_class':1,'domain':'industrial'})
    ecu = create_object('HardwareNode', {'name':'Process controller','device_type':'ECU','device_class':device_class,'domain':'industrial'})
    function = create_object('Function', {'name':'Thermal control','hardware_node_id':str(ecu['id']),'function_type':'Control','configuration':{'requirements':'Heat below lower threshold; stop above upper threshold'}})
    sensor_if = create_object('Interface', {'name':'Measurement interface','hardware_node_id':str(sensor['id']),'interface_type':'CAN_FD'})
    ecu_if = create_object('Interface', {'name':'Control interface','function_id':str(function['id']),'interface_type':'CAN_FD'})
    source_message = create_object('Message', {'name':'Temperature measurement','interface_id':str(sensor_if['id']), 'direction':'tx',
        'configuration':{'transport_unit':{'producer_ref':str(sensor['id']), 'consumer_refs':[str(ecu['id'])]}}})
    out_message = create_object('Message', {'name':'Heating request','interface_id':str(ecu_if['id']),'direction':'tx'})
    source = create_object('Signal', {'name':'Temperature','message_id':str(source_message['id']), 'unit':'degC','min_value':-40,'max_value':100,'length_bits':16})
    output = create_object('Signal', {'name':'Heating requested','message_id':str(out_message['id']), 'unit':'','min_value':0,'max_value':1,'length_bits':1,'data_type':'bool'})
    return source, output, ecu


def arguments(source, output):
    return {'signal_id':str(output['id']), 'model_revision':model_revision(),
        'requirements':'Simulation design: heat below 19 degC, stop above 21 degC; equality holds state',
        'input_bindings':{'value':{'signal_id':str(source['id']),'type':'number','unit':'degC','max_age_ms':50.,'fallback':20.,'on_stale':'fallback'}},
        'parameter_values':{'lower':19.,'upper':21.,'initial':False,'active_below':True}, 'on_invalid':'hold_output','invalid_output':False,
        'verification_cases':[{'name':'Independent threshold and hold behavior','source':'User approved requirement',
            'steps':[{'inputs':{'value':value},'dt_s':.1,'expected':expected} for value,expected in [(20,False),(18,True),(19,True),(21,True),(22,False)]]}]}


def test_live_db_context_generated_proposal_review_apply_and_revision_file(monkeypatch, tmp_path):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    source, output, ecu = model_fixture()
    context = ProjectRepository().function_context(str(output['id']))
    assert context['hardware']['id'] == str(ecu['id'])
    assert str(source['id']) in {row['id'] for row in context['candidate_inputs']}
    original_parameters = deepcopy(WorkflowStatusService(current_project_id()).get()['parameters'])
    monkeypatch.setattr(QwenBlockGenerator, 'generate', lambda *_: block('Hysteresis'))
    unit = RequestUnit(current_project_id())
    try:
        proposal = generate_proposal(arguments(source, output))
        unit.finish(True)
    finally:
        unit.close()
    identifier = proposal['proposal_id']
    validated = proposals.validate(identifier)
    assert validated['validation_result']['valid'], validated['validation_result']
    with pytest.raises(PermissionError):
        proposals.apply(identifier,actor='test',trace_id='before-review')
    approved = proposals.review(identifier, revision=validated['revision'], decision='approve', actor='human-reviewer', trace_id=str(uuid4()))
    assert approved['status'] == 'APPROVED'
    unit = RequestUnit(current_project_id())
    try:
        applied = proposals.apply(identifier, actor='human-reviewer', trace_id=str(uuid4()))
        unit.finish(True)
    finally:
        unit.close()
    assert applied['status'] == 'APPLIED'
    with get_connection() as connection:
        row = connection.execute('SELECT parameters FROM engineering_signal_behaviors WHERE project_id=%s AND signal_id=%s',
            (current_project_id(),str(output['id']))).fetchone()
    assert row['parameters']['function_block']['provenance']['generated_by'] == 'QWEN'
    store = ProjectArtifactStore(current_project_id())
    manifest = json.loads(store.path('manifest.json').read_text())
    assert manifest['function_blocks']
    snapshot = json.loads(store.path(manifest['project']['path']).read_text())
    assert snapshot['source_data']['engineering_signals']
    assert snapshot['project_data']['engineering_signal_behaviors']
    assert WorkflowStatusService(current_project_id()).get()['parameters'] == original_parameters


def test_stale_generation_and_wrong_device_class_cannot_modify_model(monkeypatch):
    source, output, ecu = model_fixture(device_class=2)
    with pytest.raises(ValueError, match='class 3/4'):
        ProjectRepository().function_context(str(output['id']))
    update_object('HardwareNode',str(ecu['id']),{'device_class':4, 'expected_version':ecu['version']})
    stale = arguments(source, output)
    stale['model_revision'] = 'old'
    with pytest.raises(ValueError, match='revision'):
        generate_proposal(stale)
    with get_connection() as connection:
        assert not connection.execute('SELECT 1 FROM engineering_signal_behaviors WHERE project_id=%s', (current_project_id(),)).fetchone()


def test_failed_file_projection_rolls_back_db_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    unit = RequestUnit(current_project_id())
    identifier = None
    monkeypatch.setattr(ProjectArtifactStore, 'write', lambda *_args, **_kw: (_ for _ in ()).throw(OSError('isolated projection failure')))
    try:
        row = create_object('HardwareNode', {'name':'Rollback controller','device_type':'ECU','device_class':3})
        identifier = str(row['id'])
        with pytest.raises(OSError):
            unit.finish(True)
    finally:
        unit.close()
    with pytest.raises(LookupError):
        get_object('HardwareNode', identifier)
