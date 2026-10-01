"""Cancel running work, not just its registry status or an unstarted Future."""
from concurrent.futures import CancelledError
from pathlib import Path
import json
import multiprocessing
import threading

import pytest

from backend.app.job_service import JobService, _run_simulation_process
from backend.app.simulation_service import SimulationService
from backend.app.trace_storage import TraceStorage
from backend.tests.test_model_based_simulation import simulation_config
from simulation_cancellation import cancellation_scope, check_cancellation, request_cancellation


def _long_config(output):
    config = simulation_config(output)
    config.update(duration_s=60, max_events=100_000, formats=['universal-jsonl'])
    return config


def _pause_inside_generation(reached, proceed):
    import universal_trace
    original = universal_trace.check_cancellation
    calls = 0

    def checkpoint(*, force=False):
        nonlocal calls
        calls += 1
        if calls == 200:
            reached.set()
            if not proceed.wait(10):
                raise RuntimeError('Test did not release the running generator.')
        original(force=force)

    return original, checkpoint


def _spawn_worker(config, output, reached, proceed, result):
    import universal_trace
    _, universal_trace.check_cancellation = _pause_inside_generation(reached, proceed)
    try:
        _run_simulation_process('spawn-job', {'config': config}, False, output)
    except CancelledError:
        result.put('canceled')
    except Exception as error:
        result.put(f'{type(error).__name__}: {error}')
    else:
        result.put('completed')


def _spawn_import_probe(result):
    from backend.app.job_service import JOBS
    result.put({'persist': JOBS.persist, 'jobs': JOBS.list()})


def test_cancellation_context_is_reset_and_other_attempts_are_independent(tmp_path):
    canceled = tmp_path / 'old-attempt'
    with pytest.raises(CancelledError):
        with cancellation_scope(canceled):
            request_cancellation(canceled)
            check_cancellation(force=True)
    check_cancellation(force=True)
    with cancellation_scope(tmp_path / 'another-attempt'):
        check_cancellation(force=True)


def test_already_canceled_attempt_never_enters_the_worker_body(tmp_path):
    request_cancellation(tmp_path)
    with pytest.raises(CancelledError):
        with cancellation_scope(tmp_path):
            pytest.fail('An already canceled attempt must not start.')


def test_cancel_stops_a_real_running_thread_generator(monkeypatch, tmp_path):
    import universal_trace
    reached, proceed = threading.Event(), threading.Event()
    _, checkpoint = _pause_inside_generation(reached, proceed)
    monkeypatch.setattr(universal_trace, 'check_cancellation', checkpoint)
    service = JobService(simulation_service=SimulationService(), synchronous=False,
                         persist=False, storage=TraceStorage(default_root=tmp_path / 'traces'))
    job = service.submit({'config': _long_config(tmp_path)})
    try:
        assert reached.wait(10), service.get(job['id'])
        future = service._futures[job['id']]
        assert service.cancel(job['id'])['status'] == 'canceled'
        proceed.set()
        future.result(timeout=10)
        assert service.get(job['id'])['status'] == 'canceled'
        assert service.get(job['id'])['result'] is None
        assert not (Path(job['output_dir']) / 'simulation_result.json').exists()
    finally:
        proceed.set()
        service.shutdown()


def test_cancel_marker_stops_the_real_spawn_worker_entry(tmp_path):
    context = multiprocessing.get_context('spawn')
    reached, proceed, result = context.Event(), context.Event(), context.Queue()
    output = tmp_path / 'spawn-attempt'
    worker = context.Process(target=_spawn_worker, args=(_long_config(output), str(output), reached, proceed, result))
    service = JobService(synchronous=True, persist=False)
    service._jobs['spawn-job'] = {'id': 'spawn-job', 'project_id': 'default', 'status': 'running',
                                 'output_dir': str(output), 'result': None}
    worker.start()
    try:
        assert reached.wait(15), 'Spawn worker must enter real event generation.'
        assert service.cancel('spawn-job')['status'] == 'canceled'
        proceed.set()
        worker.join(timeout=10)
        assert not worker.is_alive(), 'Canceled computation must release its worker process.'
        assert worker.exitcode == 0
        assert result.get(timeout=2) == 'canceled'
        assert not (output / 'simulation_result.json').exists()
    finally:
        proceed.set()
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        result.close()


def test_spawn_import_without_pytest_flag_does_not_rewrite_parent_registry(monkeypatch, tmp_path):
    runtime = tmp_path / 'isolated-child-runtime'
    registry = runtime / 'jobs' / 'registry.json'
    registry.parent.mkdir(parents=True)
    original = json.dumps({'jobs': [{'id': f'parent-{status}', 'project_id': 'isolated',
        'status': status, 'workflow_snapshot_id': f'snapshot-{status}',
        'output_dir': str(runtime / status)} for status in ['queued', 'running']]})
    registry.write_text(original, encoding='utf8')
    context = multiprocessing.get_context('spawn')
    result = context.Queue()
    worker = context.Process(target=_spawn_import_probe, args=(result,))
    try:
        # Without removing this flag, JobService's test-only persist=False
        # default would mask the real production import regression.
        with monkeypatch.context() as environment:
            environment.delenv('PYTEST_CURRENT_TEST', raising=False)
            environment.setenv('SIMULATOR_RUNTIME_ROOT', str(runtime))
            environment.setenv('DATABASE_URL', 'postgresql://nis_test:disabled@127.0.0.1:1/nis_test_spawn_probe')
            environment.setenv('ENGINEERING_TEST_DATABASE_URL', 'postgresql://nis_test:disabled@127.0.0.1:1/nis_test_spawn_probe')
            worker.start()
        worker.join(timeout=15)
        assert not worker.is_alive()
        assert worker.exitcode == 0
        assert result.get(timeout=2) == {'persist': False, 'jobs': []}
        assert registry.read_text(encoding='utf8') == original
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        result.close()
