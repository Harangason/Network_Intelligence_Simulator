import errno
import importlib
import json
from pathlib import Path

import pytest
from backend.app import create_app
from backend.app.job_service import JobService
from backend.app.trace_service import read_trace_window


def test_trace_window_pages_without_gaps_and_filters_on_server(tmp_path):
    path = tmp_path / 'trace.jsonl'
    records = [{'time_s': i / 10, 'sequence': i, 'network': 'CAN' if i % 2 else 'LIN'} for i in range(1200)]
    path.write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf-8')
    first = read_trace_window(path, limit=500)
    second = read_trace_window(path, cursor=first['next_cursor'], limit=500)
    last = read_trace_window(path, cursor=second['next_cursor'], limit=500)
    assert first['events'] + second['events'] + last['events'] == records
    assert last['next_cursor'] is None
    filtered = read_trace_window(path, start_s=10, end_s=11, query='CAN')
    assert [item['sequence'] for item in filtered['events']] == [101, 103, 105, 107, 109]


def test_sparse_index_seeks_late_windows_and_does_not_lose_equal_timestamps(tmp_path):
    from universal_trace import write_jsonl
    path = tmp_path / 'indexed.jsonl'
    records = [{'time_s': i // 1200, 'sequence': i} for i in range(20000)]
    write_jsonl(path, records)
    page = read_trace_window(path, start_s=12, end_s=12, limit=2000)
    assert page['events'] == [r for r in records if r['time_s'] == 12]
    assert page['next_cursor'] is None
    assert page['scanned'] < 1800
    with path.open('ab') as handle:
        handle.write(b'{"time_s":0,"sequence":20000}\n')
    page = read_trace_window(path, start_s=0, end_s=0, limit=2000)
    assert page['has_more'] and page['scanned'] == 10000


def test_unsorted_traces_never_use_an_ordered_time_shortcut(tmp_path):
    from universal_trace import write_jsonl
    path = tmp_path / 'unsorted.jsonl'
    write_jsonl(path, [{'time_s': 3}, {'time_s': 1}])
    assert read_trace_window(path, start_s=1, end_s=1)['events'] == [{'time_s': 1}]


@pytest.mark.parametrize('arguments', [{'cursor': -1}, {'limit': 0}, {'limit': 2001}, {'start_s': float('nan')}, {'start_s': 2, 'end_s': 1}])
def test_trace_window_rejects_invalid_bounds(tmp_path, arguments):
    with pytest.raises(ValueError):
        read_trace_window(tmp_path / 'trace.jsonl', **arguments)


def test_readiness_reports_unavailable_storage_without_hiding_failure(monkeypatch, tmp_path):
    api = importlib.import_module('backend.app.api')
    monkeypatch.setattr(api, 'RUNTIME_ROOT', tmp_path / 'missing')
    response = create_app(testing=True).test_client().get('/api/ready')
    assert response.status_code == 503
    assert response.get_json()['status'] == 'unavailable'


def test_http_trace_window_is_project_scoped_and_reports_io_failure(monkeypatch, tmp_path):
    api = importlib.import_module('backend.app.api')
    jobs = JobService(persist=False)
    path = tmp_path / 'job' / 'universal_trace.jsonl'
    path.parent.mkdir()
    path.write_text('{"time_s":0,"signals":[]}\n', encoding='utf-8')
    jobs._jobs['job'] = {'id': 'job', 'project_id': 'isolated', 'result': {'artifacts': [str(path)]}}
    monkeypatch.setattr(api, 'JOBS', jobs)
    monkeypatch.setattr('backend.app.job_service.TRACE_ROOT', tmp_path)
    client = create_app(testing=True).test_client()
    assert client.get('/api/simulations/job/trace-window', headers={'X-Project-ID': 'other'}).status_code == 404
    assert client.get('/api/simulations/job/trace-window?limit=5000', headers={'X-Project-ID': 'isolated'}).status_code == 400
    response = client.get('/api/simulations/job/trace-window', headers={'X-Project-ID': 'isolated'})
    assert response.status_code == 200
    assert response.get_json()['count'] == 1
    def unavailable(*args, **kwargs):
        raise OSError(errno.EIO, 'Input/output error')
    monkeypatch.setattr(jobs, 'artifact', unavailable)
    response = client.get('/api/simulations/job/trace-window', headers={'X-Project-ID': 'isolated'})
    assert response.status_code == 503
