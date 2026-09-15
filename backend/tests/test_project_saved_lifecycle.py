import json
from uuid import uuid4
import pytest
from backend.app import create_app
from backend.app.saved_storage import project_folder, save_bundle
from backend.app.trace_storage import TraceStorage

def test_saved_folders_are_project_scoped_and_reject_escape(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    assert TraceStorage(container=False).root_for('alpha') == tmp_path/'alpha'/'runs'
    assert TraceStorage(container=False).root_for('beta') == tmp_path/'beta'/'runs'
    for key in ('..', '../escape', '/escape'):
        with pytest.raises(ValueError): project_folder(key)
    output = save_bundle({'project_id':'alpha', 'value':1})
    save_bundle({'project_id':'alpha', 'value':2})
    assert json.loads(output.read_text())['value'] == 2

def test_project_save_delete_and_stale_tab_cannot_recreate(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    client = create_app().test_client()
    project = 'lifecycle-' + uuid4().hex
    other = 'lifecycle-' + uuid4().hex
    for key in (project, other):
        assert client.patch('/api/engineering/workflow/context', headers={'X-Project-ID':key}, json={'engineering_wizard_settings':{'project_name':key,'model_type':'custom'}}).status_code == 200
    headers={'X-Project-ID':project}
    saved = client.post('/api/engineering/projects/save', headers=headers, json={})
    assert saved.status_code == 200, saved.json
    assert (project_folder(project)/'project.nis-project.json').is_file()
    assert client.post('/api/engineering/projects/delete', headers=headers,json={'confirm_project_id':other}).status_code == 400
    deleted = client.post('/api/engineering/projects/delete',headers=headers,json={'confirm_project_id':project})
    assert deleted.status_code == 200, deleted.json
    assert not project_folder(project).exists()
    assert project_folder(other).is_dir()
    assert client.post('/api/engineering/projects/delete',headers=headers,json={'confirm_project_id':project}).status_code == 200
    assert client.patch('/api/engineering/workflow/context',headers=headers,json={}).status_code == 400
    assert client.get('/api/engineering/workflow',headers=headers).status_code == 400
    assert project not in [p['project_id'] for p in client.get('/api/engineering/projects').json['items']]

def test_active_agent_prevents_project_deletion(tmp_path, monkeypatch):
    from backend.engineering.workflow.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project='lifecycle-active-'+uuid4().hex
    client=create_app().test_client()
    WorkflowStatusService(project).set_context({'agent_execution':{'state':'RUNNING','run_id':'active-run'}})
    response=client.post('/api/engineering/projects/delete',headers={'X-Project-ID':project},json={'confirm_project_id':project})
    assert response.status_code==400
    assert 'Agent arbeitet' in response.json['error']
    assert WorkflowStatusService(project).get()['context']['agent_execution']['state']=='RUNNING'


@pytest.mark.parametrize('status,allowed', [('queued',False),('running',False),('completed',True),('failed',True),('canceled',True)])
def test_project_deletion_obeys_simulation_lifecycle(tmp_path, monkeypatch, status, allowed):
    from backend.app.job_service import JOBS
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT',str(tmp_path))
    client=create_app().test_client()
    project='lifecycle-simulation-'+uuid4().hex
    headers={'X-Project-ID':project}
    assert client.patch('/api/engineering/workflow/context',headers=headers,json={}).status_code==200
    monkeypatch.setattr(JOBS,'_jobs',{'run':{'id':'run','project_id':project,'status':status,'created_at':'2026-09-15T00:00:00Z'}})
    monkeypatch.setattr(JOBS,'_persist_locked',lambda:None)
    response=client.post('/api/engineering/projects/delete',headers=headers,json={'confirm_project_id':project})
    assert response.status_code==(200 if allowed else 400),response.json
    assert ('run' in JOBS._jobs) is not allowed
    assert project_folder(project).exists() is not allowed
