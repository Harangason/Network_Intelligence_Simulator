"""Agent polling must not import full completed traces through HTTP and MCP."""
import copy
import importlib
import threading

import pytest
from werkzeug.serving import make_server

from backend.app import create_app
from backend.app.job_service import JobService
from backend.engineering.agent_tools import services
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.repository import NotFoundError


@pytest.fixture
def simulation_http(monkeypatch):
    app = create_app(testing=True)
    jobs = JobService(persist=False)
    monkeypatch.setattr(importlib.import_module('backend.app.api'), 'JOBS', jobs)
    server = make_server('127.0.0.1', 0, app)
    monkeypatch.setenv('SIMULATOR_JOB_API_URL', f'http://127.0.0.1:{server.server_port}/api')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    token = activate_project('status-poll-project')
    try:
        yield jobs
    finally:
        reset_project(token)
        server.shutdown()
        worker.join(5)
        server.server_close()
        assert not worker.is_alive()


@pytest.mark.parametrize('status', ['running', 'completed', 'failed', 'canceled'])
def test_status_poll_preserves_job_identity_terminal_error_and_recovery(simulation_http, status):
    expected = {'id': 'same-recovered-job', 'project_id': 'status-poll-project',
                'workflow_snapshot_id': 'same-snapshot', 'status': status,
                'error': 'explicit runtime failure' if status == 'failed' else None,
                'recovery_count': 1, 'recovery_pending': False,
                'cancellation_requested': status == 'canceled'}
    simulation_http._jobs[expected['id']] = expected
    polled = services._simulation({'job_id': expected['id']}, 'status')
    assert all(polled[key] == value for key, value in expected.items())


def test_completed_status_never_copies_trace_but_explicit_results_import_still_does(simulation_http):
    copied = []

    class TraceFrames(list):
        def __deepcopy__(self, memo):
            copied.append(True)
            return copy.deepcopy(list(self), memo)

    frames = TraceFrames([{'signal': 'MotorTemperature', 'value': 42, 'encoded': '002a'}])
    simulation_http._jobs['same-recovered-job'] = {
        'id': 'same-recovered-job', 'project_id': 'status-poll-project',
        'status': 'completed', 'error': None, 'recovery_count': 1,
        'result': {'status': 'completed', 'artifacts': ['/traces/universal_trace.jsonl'],
                   'model_simulation': {'frames': frames}, 'assessment': {'conformance': 'PASS'}},
    }
    polled = services._simulation({'job_id': 'same-recovered-job'}, 'status')
    assert polled['id'] == 'same-recovered-job' and polled['status'] == 'completed'
    assert polled['recovery_count'] == 1
    assert 'model_simulation' not in polled['result']
    assert copied == [], 'Status polling copied the full trace before discarding it.'
    imported = services._simulation({'job_id': 'same-recovered-job'}, 'results')
    assert imported['model_simulation']['frames'] == list(frames)
    assert imported['assessment'] == {'conformance': 'PASS'}
    assert copied, 'An explicit result read must still retrieve the actual result.'

    token = activate_project('other-project')
    try:
        with pytest.raises(NotFoundError):
            services._simulation({'job_id': 'same-recovered-job'}, 'status')
    finally:
        reset_project(token)
