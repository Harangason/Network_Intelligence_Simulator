"""S31: persisted import metadata must describe the entire stream honestly."""
import json

import pytest
from flask import Flask

from backend.app import trace_sessions


def persist(tmp_path, monkeypatch, records):
    monkeypatch.setattr(trace_sessions, 'session_root', lambda: tmp_path / 'sessions')
    path = tmp_path / 'input.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf8')
    with Flask(__name__).test_request_context():
        result = trace_sessions.persist_import(path.read_bytes(), path.name, path)
        reloaded = trace_sessions.session_window(result['session_id'], limit=1)
    return result, reloaded


def test_metadata_covers_events_after_preview_and_survives_reload(tmp_path, monkeypatch):
    rows = [{'time_s': i, 'time_basis': 'relative', 'technology': 'CAN FD', 'network_id': 'CAN_1'}
            for i in range(2001)]
    rows[-1].update(technology='Ethernet', network_id='ETH_Test_01')
    result, reload = persist(tmp_path, monkeypatch, rows)
    assert result['imported_events'] == 2000
    assert result['source_type'] == 'ImportTrace'
    assert result['simulation_run_ref'] is None
    assert result['time_range'] == {'start_s': 0, 'end_s': 2000}
    assert result['technologies'] == ['CAN FD', 'Ethernet']
    assert result['networks'] == ['CAN_1', 'ETH_Test_01']
    assert result['sync_status'] == 'single_timebase'
    for key in ('source', 'source_type', 'time_range', 'timebase', 'networks', 'technologies', 'sync_status'):
        assert reload[key] == result[key]


@pytest.mark.parametrize('rows,status', [
    ([{'time_s': 1}], 'unknown'),
    ([{'message': 'missing time'}], 'unavailable'),
    ([{'time_s': 1, 'time_basis': 'clock-a'}, {'time_s': 2, 'time_basis': 'clock-b'}], 'unsynchronized'),
])
def test_no_invented_synchronization(tmp_path, monkeypatch, rows, status):
    result, _ = persist(tmp_path, monkeypatch, rows)
    assert result['sync_status'] == status
    if status == 'unsynchronized':
        assert result['time_range'] == {'start_s': None, 'end_s': None}
        index = json.loads((tmp_path / 'sessions' / result['session_id'] / 'events.index.json').read_text())
        assert not index['ordered']


def test_invalid_metadata_leaves_no_session(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='Trace-Metadaten'):
        persist(tmp_path, monkeypatch, [{'time_s': 0, 'time_basis': {'clock': 'bad'}}])
    assert list((tmp_path / 'sessions').iterdir()) == []
