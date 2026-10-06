import json
from uuid import uuid4
import pytest
from backend.nis.app import create_app
from backend.nis.infrastructure.storage.saved_storage import project_folder
from backend.nis.infrastructure.storage.saved_storage import save_bundle
from backend.nis.infrastructure.storage.saved_storage import save_user_defined_values
from backend.nis.infrastructure.storage.saved_storage import load_user_defined_values
from backend.nis.infrastructure.storage.trace_storage import TraceStorage

def test_saved_folders_are_project_scoped_and_reject_escape(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    assert TraceStorage(container=False).root_for('alpha') == tmp_path/'alpha'/'runs'
    assert TraceStorage(container=False).root_for('beta') == tmp_path/'beta'/'runs'
    for key in ('..', '../escape', '/escape'):
        with pytest.raises(ValueError): project_folder(key)
    output = save_bundle({'project_id':'alpha', 'value':1})
    save_bundle({'project_id':'alpha', 'value':2})
    assert json.loads(output.read_text())['value'] == 2


def test_user_defined_values_keep_project_identity_types_and_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    parameters = {'technology': 'can_fd', 'can_clock_hz': 80000000,
                  'technology_defaults': {'can_fd': {'can_clock_hz': 40000000}},
                  'defaults_source': 'technology-registry',
                  'simulation_parameter_assumptions': {'can_fd': {
                      'values': {'can_fd_tdc_enabled': False, 'can_fd_mcan_tdco_mtq': 0},
                      'provenance': {'can_fd_tdc_enabled': {'source': 'NIS_SIMULATION_ASSUMPTION',
                                                         'status': 'ASSUMED', 'hardware_evidence': False}}}},
                  'exact_counter': '18446744073709551615'}
    path = save_user_defined_values('20261005103106027-d3a78a2c', parameters)
    assert path == tmp_path/'network-project-20261005103106027-d3a78a2c'/'user_defined_values.json'
    document = load_user_defined_values('network-project-20261005103106027-d3a78a2c')
    assert document['value_origin'] == 'USER_DEFINED_VALUE'
    assert document['parameters'] == {key: value for key, value in parameters.items()
                                      if key not in {'technology_defaults', 'defaults_source'}}
    assert load_user_defined_values('another-project') is None
    assert not (tmp_path/'default').exists()
    assert not list(path.parent.glob('*.tmp'))
    assert parameters['technology_defaults']['can_fd']['can_clock_hz'] == 40000000


def test_user_values_reject_foreign_project_document(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    path = save_user_defined_values('first-project', {'can_clock_hz': 80000000})
    data = json.loads(path.read_text()); data['project_id'] = 'other-project'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='projektspezifische'):
        load_user_defined_values('first-project')


def _assumed_clock(value):
    return {'industry': 'custom', 'technology': 'can_fd',
            'simulation_parameter_assumptions': {'can_fd': {
                'values': {'can_clock_hz': value},
                'provenance': {'can_clock_hz': {'source': 'NIS_SIMULATION_ASSUMPTION', 'status': 'ASSUMED',
                                               'technology': 'can_fd', 'hardware_evidence': False, 'value': value}}}}}


def test_parameter_api_persists_user_file_and_preserves_defaults_and_neighbour(tmp_path, monkeypatch):
    from pathlib import Path
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    profile = Path('backend/nis/communication/technologies/can_fd/profile.json')
    original_profile = profile.read_bytes()
    project, neighbour = 'user-values-' + uuid4().hex, 'user-values-' + uuid4().hex
    WorkflowStatusService(neighbour).save_parameters({'duration_s': 17})
    neighbour_file = (project_folder(neighbour)/'user_defined_values.json').read_bytes()
    client = create_app().test_client(); headers = {'X-Project-ID': project}
    initial = client.get('/api/engineering/workflow/parameters', headers=headers).json
    values = _assumed_clock(80000000)
    saved = client.patch('/api/engineering/workflow/parameters', headers=headers,
                         json={'parameters': values, 'expected_token': initial['edit_token']})
    assert saved.status_code == 200, saved.json
    stored = client.get('/api/engineering/workflow/parameters/user-defined-values', headers=headers)
    assert stored.status_code == 200 and stored.json['parameters'] == values
    assert stored.json['value_origin'] == 'USER_DEFINED_VALUE' and stored.json['project_id'] == project
    assert load_user_defined_values(project)['parameters'] == values
    reloaded = create_app().test_client().get('/api/engineering/workflow/parameters', headers=headers)
    assert reloaded.json['parameters'] == values
    assert reloaded.json['parameter_storage']['source'] == 'PROJECT_USER_DEFINED_VALUES'
    assert profile.read_bytes() == original_profile
    assert (project_folder(neighbour)/'user_defined_values.json').read_bytes() == neighbour_file
    assert client.patch('/api/engineering/workflow/parameters', headers=headers,
                        json={'parameters': _assumed_clock(40000000), 'expected_token': initial['edit_token']}).status_code == 409
    assert load_user_defined_values(project)['parameters'] == values


def test_parameter_file_write_failure_rolls_back_project_sql(tmp_path, monkeypatch):
    from backend.nis.infrastructure.storage import saved_storage
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project = 'user-values-failure-' + uuid4().hex
    previous = _assumed_clock(40000000); WorkflowStatusService(project).save_parameters(previous)
    file = project_folder(project)/'user_defined_values.json'; before = file.read_bytes()
    original_write = saved_storage._save_json
    def fail(project_id, filename, document):
        if filename == 'user_defined_values.json':
            raise OSError('isolated disk write failure')
        return original_write(project_id, filename, document)
    monkeypatch.setattr(saved_storage, '_save_json', fail)
    client = create_app().test_client(); headers = {'X-Project-ID': project}
    token = client.get('/api/engineering/workflow/parameters', headers=headers).json['edit_token']
    response = client.patch('/api/engineering/workflow/parameters', headers=headers,
                            json={'parameters': _assumed_clock(80000000), 'expected_token': token})
    assert response.status_code == 503
    assert file.read_bytes() == before
    from backend.nis.infrastructure.persistence.db import get_connection
    with get_connection() as connection:
        row = connection.execute('SELECT parameters FROM engineering_workflow_projects WHERE project_id=%s', (project,)).fetchone()
    assert row['parameters'] == previous


def test_sql_commit_failure_restores_previous_user_file(tmp_path, monkeypatch):
    from backend.nis.infrastructure.persistence.db import RequestUnit, get_connection
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project = 'user-values-commit-' + uuid4().hex
    previous = _assumed_clock(40000000); WorkflowStatusService(project).save_parameters(previous)
    file = project_folder(project)/'user_defined_values.json'; before = file.read_bytes()
    unit = RequestUnit(project)
    try:
        WorkflowStatusService(project).save_parameters(_assumed_clock(80000000))
        assert file.read_bytes() == before  # Still staged, not published.
        original_context = unit.pool_context
        class FailedCommit:
            def __exit__(self, *args):
                error = RuntimeError('isolated commit failure')
                original_context.__exit__(type(error), error, error.__traceback__)
                raise error
        unit.pool_context = FailedCommit()
        with pytest.raises(RuntimeError, match='commit failure'):
            unit.finish(True)
    finally:
        unit.close()
    assert file.read_bytes() == before
    with get_connection() as connection:
        row = connection.execute('SELECT parameters FROM engineering_workflow_projects WHERE project_id=%s', (project,)).fetchone()
    assert row['parameters'] == previous


def test_user_parameter_file_leads_runtime_copy_and_bundle_clone(tmp_path, monkeypatch):
    from backend.nis.infrastructure.persistence.db import get_connection
    from backend.nis.engineering.projects.project_bundle import ProjectBundleService
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project, clone = 'user-values-source-' + uuid4().hex, 'user-values-clone-' + uuid4().hex
    values = _assumed_clock(80000000); WorkflowStatusService(project).save_parameters(values)
    state = WorkflowStatusService(project).set_context({'selected_network': 'can-one'})
    assert '_user_values_revision' not in state['context']
    assert state['parameter_storage']['source'] == 'PROJECT_USER_DEFINED_VALUES'
    # Simulate a lost SQL runtime projection; the project file remains leading.
    with get_connection() as connection:
        connection.execute("UPDATE engineering_workflow_projects SET parameters='{}'::jsonb WHERE project_id=%s", (project,))
    assert WorkflowStatusService(project).get()['parameters'] == values
    bundle = ProjectBundleService().export(project, target_project_id=clone)
    ProjectBundleService().import_bundle(bundle, target_project_id=clone)
    assert load_user_defined_values(clone)['parameters'] == values
    assert load_user_defined_values(project)['parameters'] == values
    ProjectBundleService().reset_workspace(clone)
    assert load_user_defined_values(clone) is None
    assert WorkflowStatusService(clone).get()['parameters'] == {}
    assert load_user_defined_values(project)['parameters'] == values


def test_pending_file_does_not_change_committed_parameter_snapshot(tmp_path, monkeypatch):
    from backend.nis.infrastructure.persistence.db import RequestUnit, get_connection
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project = 'user-values-snapshot-' + uuid4().hex
    service = WorkflowStatusService(project)
    previous = _assumed_clock(40000000)
    service.save_parameters(previous)
    with get_connection() as connection:
        committed = connection.execute('SELECT * FROM engineering_workflow_projects WHERE project_id=%s', (project,)).fetchone()
    unit = RequestUnit(project)
    try:
        service.save_parameters(_assumed_clock(80000000))
        resource = next(iter(unit.resources.values()))
        resource.prepare()
        assert load_user_defined_values(project)['parameters'] == _assumed_clock(80000000)
        assert service._state(committed)['parameters'] == previous
        resource.rollback()
        unit.finish(False)
    finally:
        unit.close()
    assert service.get()['parameters'] == previous


def test_caught_savepoint_failure_discards_its_pending_file(tmp_path, monkeypatch):
    from backend.nis.infrastructure.persistence.db import RequestUnit, get_connection
    from backend.nis.infrastructure.storage.saved_storage import stage_user_defined_values
    from backend.nis.workflow.services.service import WorkflowStatusService
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    project = 'user-values-savepoint-' + uuid4().hex
    service = WorkflowStatusService(project)
    previous = _assumed_clock(40000000)
    service.save_parameters(previous)
    before = (project_folder(project)/'user_defined_values.json').read_bytes()
    unit = RequestUnit(project)
    try:
        with pytest.raises(ValueError, match='caught savepoint'):
            with get_connection() as connection:
                stage_user_defined_values(project, _assumed_clock(80000000), connection)
                raise ValueError('caught savepoint')
        assert not unit.resources
        unit.finish(True)
    finally:
        unit.close()
    assert (project_folder(project)/'user_defined_values.json').read_bytes() == before
    assert service.get()['parameters'] == previous

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
    from backend.nis.workflow.services.service import WorkflowStatusService
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
    from backend.nis.simulation.job_service import JOBS
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
