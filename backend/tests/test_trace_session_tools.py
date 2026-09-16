import pytest

from backend.engineering.agent_tools import analysis, simulation_gateway


def test_simulation_and_golden_metadata_scan_full_stream(monkeypatch):
    monkeypatch.setattr(simulation_gateway, 'job', lambda *args, **kwargs: {'status': 'completed'})
    monkeypatch.setattr(simulation_gateway, 'iter_trace', lambda _: iter([
        {'time_s': i / 10, 'technology': 'CAN_FD' if i < 2000 else 'Ethernet', 'network': 'net'} for i in range(2001)]))
    for golden in (False, True):
        result = analysis.inspect_trace_session({'job_id': 'run-1', 'golden': golden})
        assert result['simulation_run_ref'] == 'run-1'
        assert result['total_events'] == 2001
        assert result['technologies'] == ['CAN_FD', 'Ethernet']
        assert result['source_type'] == ('GoldenTrace' if golden else 'SimulationTrace')
        assert result['time_range'] == {'start_s': 0, 'end_s': 200}
        assert result['sync_status'] == 'single_timebase'


@pytest.mark.parametrize('args', [{}, {'job_id': 'x', 'session_id': 'y'}, {'session_id': 'y', 'golden': True}])
def test_ambiguous_trace_sources_are_rejected(args):
    with pytest.raises(ValueError):
        analysis.inspect_trace_session(args)


def test_import_metadata_stays_project_gateway_scoped(monkeypatch):
    calls = []
    def read(path):
        calls.append(path)
        return {'session_id': 's', 'source_type': 'ImportTrace', 'total_events': 3000, 'events': [{}], 'count': 1}
    monkeypatch.setattr(simulation_gateway, 'request_json', read)
    result = analysis.inspect_trace_session({'session_id': 's'})
    assert calls == ['/trace-import/s?limit=1']
    assert result == {'session_id': 's', 'source_type': 'ImportTrace', 'total_events': 3000}


def test_import_window_uses_project_gateway_and_preserves_cursor(monkeypatch):
    calls = []
    def read(path):
        calls.append(path)
        return {'events': [{'time_s': 2}], 'next_cursor': 123}
    monkeypatch.setattr(simulation_gateway, 'request_json', read)
    result = analysis.window({'session_id': 'session', 'start_s': 1, 'end_s': 3,
                              'limit': 50, 'cursor': 10, 'query': 'DDS Topic'})
    assert calls == ['/trace-import/session?start_s=1&end_s=3&cursor=10&limit=50&q=DDS+Topic']
    assert result['next_cursor'] == 123 and result['validation_status'] == 'PARTIAL'
    with pytest.raises(ValueError):
        analysis.window({'session_id': 'session', 'job_id': 'job'})
    with pytest.raises(ValueError):
        analysis.window({})


@pytest.mark.parametrize('bases,status,expected', [(['unknown'], 'unknown', None),
    (['a', 'b'], 'unsynchronized', 'a'), (['a'], 'single_timebase', 'b')])
def test_view_time_rejects_incompatible_clocks(monkeypatch, bases, status, expected):
    monkeypatch.setattr(analysis, 'inspect_trace_session', lambda _: {
        'timebase': {'bases': bases}, 'sync_status': status})
    with pytest.raises(ValueError, match='TRACE_TIMEBASE_MISMATCH'):
        analysis.resolve_trace_time({'session_id': 's', 'time_s': 12.5, 'time_basis': expected})


def test_selected_gateway_hop_is_resolved_exactly_with_shared_time(monkeypatch):
    monkeypatch.setattr(analysis, 'inspect_trace_session', lambda _: {
        'session_id': 's', 'timebase': {'bases': ['simulation_relative']},
        'sync_status': 'single_timebase', 'time_range': {'start_s': 0, 'end_s': 20}})
    first = {'event_id': 'route:1:segment:0', 'time_s': 12.5, 'network': 'can'}
    selected = {'event_id': 'route:1:segment:1', 'time_s': 12.5, 'network': 'ethernet'}
    monkeypatch.setattr(analysis, 'window', lambda a: {'events': [first, selected], 'next_cursor': None})
    args = {'session_id': 's', 'time_s': 12.5, 'event_id': selected['event_id']}
    result = analysis.resolve_trace_event_context(args)
    assert result['time_s'] == 12.5 and result['synchronized']
    assert result['event'] == selected
    assert {'object_type': 'Network', 'id': 'ethernet'} in result['object_refs']
    with pytest.raises(ValueError, match='fehlt'):
        analysis.resolve_trace_event_context({**args, 'event_id': 'missing'})
    with pytest.raises(ValueError, match='außerhalb'):
        analysis.resolve_trace_time({**args, 'time_s': 21})
