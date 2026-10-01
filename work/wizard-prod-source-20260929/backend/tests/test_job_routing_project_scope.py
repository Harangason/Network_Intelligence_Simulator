"""Actual executor/callback SQL writes use the immutable job owner, not ContextVars."""
from concurrent.futures import Future, ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from backend.app.job_service import JobService
from backend.app.trace_storage import TraceStorage
from backend.engineering.project_context import current_project_id
from backend.tests.test_model_ownership import db_project
from backend.tests.test_routing_result_batch import seed, result, stored


def test_thread_job_persists_owner_routes_and_restores_default_scope(db_project, tmp_path):
    own = seed(db_project, 1)[0]
    foreign = seed(db_project + '-foreign', 1)[0]
    scopes = []
    def simulate(*args, **kwargs):
        scopes.append(current_project_id())
        return result()
    service = JobService(simulation_service=SimpleNamespace(run=simulate), synchronous=False,
                         max_workers=1, persist=False, storage=TraceStorage(default_root=tmp_path))
    try:
        job = service.submit({'project_id': db_project, 'config': {'routing_entry_ids': [own, foreign]}})
        # A second task in the same executor runs only after the real completion
        # write and observes whether its temporary project binding was restored.
        assert service.executor.submit(current_project_id).result(timeout=10) == 'default'
        assert scopes == ['default']
        assert service.get(job['id'])['status'] == 'completed'
        relations, audit = stored(db_project)
        assert [str(row['source_id']) for row in relations] == [own]
        assert [str(row['route_id']) for row in audit] == [own]
        assert stored(db_project + '-foreign') == ([], [])
        assert current_project_id() == db_project
    finally:
        service.shutdown()


def test_process_completion_callback_uses_job_owner_from_fresh_thread(db_project, tmp_path):
    own = seed(db_project, 1)[0]
    foreign = seed(db_project + '-foreign', 1)[0]
    service = JobService(synchronous=True, persist=False, storage=TraceStorage(default_root=tmp_path))
    job = str(uuid4())
    service._jobs[job] = {'id': job, 'project_id': db_project, 'status': 'running'}
    completed = Future()
    completed.set_result(result())
    def callback():
        assert current_project_id() == 'default'
        service._complete_process_job(job, {'project_id': db_project,
            'config': {'routing_entry_ids': [own, foreign]}}, False, completed)
        assert current_project_id() == 'default'
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(callback).result(timeout=10)
    assert service.get(job)['status'] == 'completed'
    relations, audit = stored(db_project)
    assert [str(row['source_id']) for row in relations] == [own]
    assert [str(row['route_id']) for row in audit] == [own]
    assert stored(db_project + '-foreign') == ([], [])
    assert current_project_id() == db_project


def test_optional_observation_failure_restores_callback_project_scope(db_project, monkeypatch):
    from backend.engineering.routing import repository
    def fail(*args):
        assert current_project_id() == db_project
        raise RuntimeError('injected observation persistence failure')
    monkeypatch.setattr(repository, 'record_simulation_results', fail)
    def callback():
        JobService._record_routing_results({'project_id': db_project,
            'config': {'routing_entry_ids': [str(uuid4())]}}, False, str(uuid4()), result())
        assert current_project_id() == 'default'
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(callback).result(timeout=10)
