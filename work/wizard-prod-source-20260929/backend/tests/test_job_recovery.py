"""Registry recovery preserves job identity and frozen workflow authority."""
import json
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from backend.app.job_service import JobService
from backend.app.simulation_service import SimulationService
from backend.engineering.workflow.service import WorkflowStatusService


def interrupted(tmp_path, **overrides):
    output = tmp_path / 'original'
    output.mkdir()
    (output / 'partial.jsonl').write_text('incomplete\n', encoding='utf-8')
    row = {'id': 'original-job', 'project_id': 'project-a', 'workflow_snapshot_id': 'snapshot-a',
           'status': 'running', 'output_dir': str(output), 'created_at': '2026-09-14T00:00:00Z',
           'updated_at': '2026-09-14T00:00:00Z', 'validate_only': False, **overrides}
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'jobs': [row]}), encoding='utf-8')
    return JobService(registry_path=registry, persist=True, synchronous=True), output


def test_restart_reuses_job_and_snapshot_once_with_fresh_attempt_output(monkeypatch, tmp_path):
    service, original = interrupted(tmp_path)
    snapshot = {'status': 'RUNNING', 'job_id': 'original-job', 'is_outdated': False,
                'configuration': {'frozen_marker': 'confirmed', 'duration_s': 10}}
    reads, executions = [], []
    def read(authority, snapshot_id, *, require_current=False):
        assert require_current is True
        reads.append((authority.project_id, snapshot_id))
        return snapshot
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', read)
    def execute(job_id, payload, validate_only):
        executions.append((job_id, payload, validate_only))
        service._update(job_id, status='completed', result={'status': 'completed'})
    monkeypatch.setattr(service, '_execute', execute)
    assert service.recover_interrupted() == 1
    assert service.recover_interrupted() == 0
    assert reads == [('project-a', 'snapshot-a')]
    assert len(service.list('project-a')) == 1
    assert executions == [('original-job', {'project_id': 'project-a', 'workflow_snapshot_id': 'snapshot-a',
        'workflow_managed': True, 'config': snapshot['configuration'], 'simulation_job_id': 'original-job'}, False)]
    job = service.get('original-job')
    assert job['status'] == 'completed' and job['recovery_count'] == 1
    assert job['output_dir'] == str(original / 'recovery-1')
    assert job['interrupted_outputs'] == [str(original)]
    assert (original / 'partial.jsonl').read_text(encoding='utf-8') == 'incomplete\n'


@pytest.mark.parametrize('snapshot', [None,
    {'status': 'RUNNING', 'is_outdated': True, 'job_id': 'original-job'},
    {'status': 'RUNNING', 'job_id': 'other-job'},
    {'status': 'CANCELED', 'job_id': 'original-job'},
    {'status': 'FAILED', 'job_id': 'original-job'},
    {'status': 'COMPLETED', 'job_id': 'original-job', 'result': None},
    {'status': 'RUNNING', 'job_id': 'original-job', 'configuration': None},
])
def test_restart_does_not_run_stale_canceled_failed_or_foreign_snapshot(monkeypatch, tmp_path, snapshot):
    service, _ = interrupted(tmp_path)
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', lambda *_, **__: snapshot)
    monkeypatch.setattr(service, '_execute', lambda *_: pytest.fail('Snapshot must not execute'))
    assert service.recover_interrupted() == 0
    assert service.get('original-job')['status'] in {'failed', 'canceled'}


def test_completed_snapshot_reconciles_lost_registry_write_without_second_execution(monkeypatch, tmp_path):
    service, _ = interrupted(tmp_path)
    result = {'status': 'completed', 'artifacts': ['retained-result.json']}
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', lambda *_, **__: {
        'status': 'COMPLETED', 'job_id': 'original-job', 'result': result})
    monkeypatch.setattr(service, '_execute', lambda *_: pytest.fail('Completed snapshot must not execute twice'))
    assert service.recover_interrupted() == 1
    assert service.get('original-job')['status'] == 'completed'
    assert service.get('original-job')['result'] == result


def test_explicit_cancellation_is_not_recovered(monkeypatch, tmp_path):
    service, _ = interrupted(tmp_path, cancellation_requested=True)
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', lambda *_, **__: pytest.fail('Canceled job cannot resume'))
    assert service.recover_interrupted() == 0


def test_durable_cancel_marker_survives_crash_before_registry_and_snapshot_write(monkeypatch, tmp_path):
    from simulation_cancellation import request_cancellation
    service, original = interrupted(tmp_path)
    request_cancellation(original)
    updates = []
    monkeypatch.setattr(service, '_update_workflow_snapshot', lambda payload, status, job_id:
                        updates.append((payload['workflow_snapshot_id'], status, job_id)))
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot',
                        lambda *_, **__: pytest.fail('A durable cancellation cannot resume.'))
    monkeypatch.setattr(service, '_execute', lambda *_: pytest.fail('Canceled attempt executed.'))
    assert service.recover_interrupted() == 0
    assert service.get('original-job')['status'] == 'canceled'
    assert service.get('original-job')['recovery_pending'] is False
    assert service.get('original-job')['output_dir'] == str(original)
    assert not (original / 'recovery-1').exists()
    assert updates == [('snapshot-a', 'CANCELED', 'original-job')]


def test_marker_is_detected_when_loading_an_old_running_registry(tmp_path):
    from simulation_cancellation import request_cancellation
    output = tmp_path / 'canceled-attempt'
    request_cancellation(output)
    registry = tmp_path / 'old-registry.json'
    registry.write_text(json.dumps({'jobs': [{'id': 'old', 'status': 'running',
        'project_id': 'project-a', 'output_dir': str(output)}]}), encoding='utf8')
    service = JobService(registry_path=registry, persist=True, synchronous=True)
    assert service.get('old')['status'] == 'canceled'
    assert service.get('old')['cancellation_requested'] is True


def test_recovery_persists_two_trace_records_under_original_job_ids(monkeypatch, tmp_path):
    from backend.engineering import simulation
    from backend.engineering.project_context import current_project_id
    project_id = current_project_id()
    rows = [{'id': f'original-job-{index}', 'project_id': project_id, 'workflow_snapshot_id': f'snapshot-{index}',
             'status': 'running', 'output_dir': str(tmp_path / f'original-job-{index}'),
             'created_at': '2026-09-14T00:00:00Z'} for index in range(2)]
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'jobs': rows}), encoding='utf-8')
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', lambda _, snapshot_id, **__: {
        'status': 'RUNNING', 'job_id': f'original-job-{snapshot_id[-1]}', 'is_outdated': False,
        'configuration': {'duration_s': 1, 'seed': 42, 'scenario': {'mode': 'NORMAL'}}})
    monkeypatch.setattr(WorkflowStatusService, 'update_simulation_snapshot', lambda *_, **__: None)
    monkeypatch.setattr(simulation, 'enrich_simulation_config', lambda config, *_, **__: config)
    monkeypatch.setattr(simulation, 'validate_scenario', lambda scenario, _: scenario)
    simulations = SimulationService()
    def simulate(config, **_):
        artifact = Path(config['output_dir']) / 'trace.jsonl'
        artifact.write_text('completed\n', encoding='utf-8')
        return {'status': 'completed', 'trace': {'events': 1}, 'artifacts': [str(artifact)]}
    simulations.simulator = SimpleNamespace(run=simulate)
    simulations.runtime_load_monitor = SimpleNamespace(analyze=lambda *_: {'network_count': 1})
    service = JobService(simulations, registry_path=registry, persist=True, synchronous=True)
    assert service.recover_interrupted() == 2
    for index in range(2):
        job_id = f'original-job-{index}'
        assert service.get(job_id)['status'] == 'completed'
        records = simulation.trace_metadata(job_id)
        assert len(records) == 1
        assert records[0]['simulation_id'] == job_id
        assert records[0]['artifact_paths'] == [str(tmp_path / job_id / 'recovery-1' / 'trace.jsonl')]
    assert simulation.trace_metadata('recovery-1') == []


def test_schedule_overrides_caller_supplied_simulation_identity(monkeypatch, tmp_path):
    service, _ = interrupted(tmp_path)
    seen = []
    monkeypatch.setattr(service, '_execute', lambda job_id, payload, _: seen.append(payload['simulation_job_id']))
    service._schedule('original-job', {'simulation_job_id': 'foreign-job'}, False)
    assert seen == ['original-job']


@pytest.mark.parametrize('cancel_during_submit', [False, True])
def test_failed_recovery_submission_stays_retryable_without_undoing_cancel(monkeypatch, tmp_path, cancel_during_submit):
    service, _ = interrupted(tmp_path)
    service.synchronous = False
    service.execution_mode = 'thread'
    monkeypatch.setattr(WorkflowStatusService, 'get_simulation_snapshot', lambda *_, **__: {
        'status': 'RUNNING', 'job_id': 'original-job', 'configuration': {}, 'is_outdated': False})
    monkeypatch.setattr(WorkflowStatusService, 'update_simulation_snapshot', lambda *_, **__: None)
    executions = []
    def fail_submission(*_):
        if cancel_during_submit:
            service.cancel('original-job')
        raise RuntimeError('executor temporarily unavailable')
    monkeypatch.setattr(service, '_get_executor', lambda: SimpleNamespace(submit=fail_submission))
    assert service.recover_interrupted() == 0
    failed = service.get('original-job')
    assert failed['status'] == ('canceled' if cancel_during_submit else 'failed')
    assert bool(failed.get('recovery_pending')) is not cancel_during_submit
    def execute(job_id, payload, validate_only):
        executions.append(job_id)
        service._update(job_id, status='completed', result={'status': 'completed'})
    monkeypatch.setattr(service, '_execute', execute)
    def submit(function, *args):
        future = Future()
        function(*args)
        future.set_result(None)
        return future
    monkeypatch.setattr(service, '_get_executor', lambda: SimpleNamespace(submit=submit))
    assert service.recover_interrupted() == (0 if cancel_during_submit else 1)
    assert executions == ([] if cancel_during_submit else ['original-job'])
    assert service.recover_interrupted() == 0


@pytest.mark.parametrize('process_callback', [False, True])
def test_cancel_queued_future_does_not_deadlock_its_registry_callback(monkeypatch, tmp_path, process_callback):
    service, _ = interrupted(tmp_path)
    service._update('original-job', status='queued')
    future = Future()
    service._futures['original-job'] = future
    if process_callback:
        future.add_done_callback(lambda done: service._complete_process_job('original-job', {}, False, done))
    else:
        future.add_done_callback(lambda _: service._forget_future('original-job'))
    monkeypatch.setattr(WorkflowStatusService, 'update_simulation_snapshot', lambda *_, **__: None)
    results = []
    thread = threading.Thread(target=lambda: results.append(service.cancel('original-job')), daemon=True)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive(), 'Future.cancel must not invoke its callbacks while holding the registry lock'
    assert results[0]['status'] == 'canceled'
    assert future.cancelled()
    assert service._futures == {}


def stored_snapshot(*, status='RUNNING', outdated=False):
    from psycopg.types.json import Jsonb
    from backend.engineering.db import get_connection
    from backend.engineering.project_context import current_project_id
    project_id = current_project_id()
    workflow = WorkflowStatusService(project_id)
    state = workflow.get(summary=True)
    with get_connection() as connection:
        row = connection.execute('''INSERT INTO engineering_simulation_snapshots
            (project_id, source_versions, configuration, status, job_id, is_outdated, result)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id''',
            (project_id, Jsonb(state['versions']), Jsonb({'duration_s': 1}), status, 'original-job',
             outdated, Jsonb({'marker': 'preserve-original-result'}))).fetchone()
    return project_id, str(row['id']), workflow


@pytest.mark.parametrize('status', ['RUNNING', 'COMPLETED'])
@pytest.mark.parametrize('source_revision', ['different', 'missing', 'null'])
def test_recovery_rejects_unproven_snapshot_revision_without_outdated_flag(monkeypatch, tmp_path, status, source_revision):
    from backend.engineering.db import get_connection
    from psycopg.types.json import Jsonb

    project_id, snapshot_id, workflow = stored_snapshot(status=status)
    with get_connection() as connection:
        project = connection.execute('SELECT * FROM engineering_workflow_projects WHERE project_id = %s',
                                     (project_id,)).fetchone()
        versions = dict(project['versions'])
        if source_revision == 'different':
            versions['simulation'] += 1
        elif source_revision == 'missing':
            versions.pop('simulation')
        else:
            versions['simulation'] = None
        connection.execute('UPDATE engineering_simulation_snapshots SET source_versions = %s WHERE id = %s',
                           (Jsonb(versions), snapshot_id))
        before = connection.execute('SELECT * FROM engineering_simulation_snapshots WHERE id = %s',
                                    (snapshot_id,)).fetchone()
    assert before['is_outdated'] is False
    service, original = interrupted(tmp_path, project_id=project_id, workflow_snapshot_id=snapshot_id)
    monkeypatch.setattr(WorkflowStatusService, '_ensure',
                        lambda *_: pytest.fail('Recovery snapshot reads must not write or initialize projects'))
    monkeypatch.setattr(service, '_execute', lambda *_: pytest.fail('Unproven revision executed'))
    assert workflow.get_simulation_snapshot(snapshot_id) is not None  # Historical evidence remains readable.
    assert workflow.get_simulation_snapshot(snapshot_id, require_current=True) is None
    assert service.recover_interrupted() == 0
    job = service.get('original-job')
    assert job['status'] == 'failed' and job['recovery_pending'] is False
    assert job.get('result') is None  # Stale COMPLETED evidence must not reconcile this job.
    assert job['output_dir'] == str(original) and not (original / 'recovery-1').exists()
    restarted = JobService(registry_path=tmp_path / 'registry.json', persist=True, synchronous=True)
    assert restarted.recover_interrupted() == 0
    assert restarted.get('original-job')['status'] == 'failed'
    with get_connection() as connection:
        assert connection.execute('SELECT * FROM engineering_simulation_snapshots WHERE id = %s',
                                  (snapshot_id,)).fetchone() == before
        assert connection.execute('SELECT * FROM engineering_workflow_projects WHERE project_id = %s',
                                  (project_id,)).fetchone() == project


@pytest.mark.parametrize('status', ['RUNNING', 'COMPLETED'])
def test_recovery_accepts_current_sql_snapshot_with_original_identity(monkeypatch, tmp_path, status):
    project_id, snapshot_id, workflow = stored_snapshot(status=status)
    snapshot = workflow.get_simulation_snapshot(snapshot_id, require_current=True)
    service, _ = interrupted(tmp_path, project_id=project_id, workflow_snapshot_id=snapshot_id)
    executions = []
    def execute(job_id, payload, validate_only):
        executions.append((job_id, payload['workflow_snapshot_id'], payload['config']))
        service._update(job_id, status='completed', result={'executed': True})
    monkeypatch.setattr(service, '_execute', execute)
    assert service.recover_interrupted() == 1
    assert service.recover_interrupted() == 0
    job = service.get('original-job')
    assert job['status'] == 'completed' and job['workflow_snapshot_id'] == snapshot_id
    if status == 'RUNNING':
        assert executions == [('original-job', snapshot_id, snapshot['configuration'])]
        assert job['recovery_count'] == 1
    else:
        assert executions == [] and job['result'] == snapshot['result']
        assert not job.get('recovery_count')


@pytest.mark.parametrize('process_completion', [False, True])
def test_cancel_during_result_recording_remains_terminal_in_registry_and_sql(monkeypatch, tmp_path, process_completion):
    project_id, snapshot_id, workflow = stored_snapshot()
    service, _ = interrupted(tmp_path, project_id=project_id, workflow_snapshot_id=snapshot_id)
    service._update('original-job', status='running')
    payload = {'project_id': project_id, 'workflow_snapshot_id': snapshot_id, 'workflow_managed': True, 'config': {}}
    result = {'status': 'completed', 'trace': {'events': 1}}
    service.simulations = SimpleNamespace(run=lambda *_, **__: result)
    recording, proceed = threading.Event(), threading.Event()
    def record(*_):
        recording.set()
        assert proceed.wait(timeout=4), 'test must release result recording'
    monkeypatch.setattr(service, '_record_routing_results', record)
    if process_completion:
        future = Future()
        future.set_result(result)
        target = lambda: service._complete_process_job('original-job', payload, False, future)
    else:
        target = lambda: service._execute('original-job', payload, False)
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    try:
        assert recording.wait(timeout=4), 'worker must reach result recording before cancellation'
        canceled = service.cancel('original-job', project_id)
        assert canceled['status'] == 'canceled'
        at_cancel = workflow.get_simulation_snapshot(snapshot_id)
        assert at_cancel['status'] == 'CANCELED'
    finally:
        proceed.set()
        thread.join(timeout=4)
    assert not thread.is_alive()
    assert service.get('original-job')['status'] == 'canceled'
    assert service.get('original-job').get('result') is None
    after_worker = workflow.get_simulation_snapshot(snapshot_id)
    assert after_worker == at_cancel
    assert after_worker['result'] == {'marker': 'preserve-original-result'}


@pytest.mark.parametrize('status,outdated', [('CANCELED', False), ('OUTDATED', True)])
@pytest.mark.parametrize('late_status', ['RUNNING', 'COMPLETED', 'FAILED'])
def test_late_snapshot_updates_cannot_rewrite_canceled_or_outdated_evidence(status, outdated, late_status):
    _, snapshot_id, workflow = stored_snapshot(status=status, outdated=outdated)
    before = workflow.get_simulation_snapshot(snapshot_id)
    workflow.update_simulation_snapshot(snapshot_id, status=late_status, job_id='late-worker',
                                        result={'marker': 'must-not-be-written'})
    assert workflow.get_simulation_snapshot(snapshot_id) == before
