"""An import is accepted only after its complete directory is published."""
import errno

import pytest
from flask import Flask

from backend.app import trace_sessions
from backend.app.trace_import import trace_import_api


@pytest.fixture
def publication(monkeypatch, tmp_path):
    root = tmp_path / 'sessions'
    monkeypatch.setattr(trace_sessions, 'session_root', lambda: root)
    app = Flask(__name__)
    app.register_blueprint(trace_import_api, url_prefix='/api')
    sleeps = []
    monkeypatch.setattr(trace_sessions.time, 'sleep', sleeps.append)
    return root, app.test_client(), sleeps


def upload(client):
    return client.post('/api/trace-import?filename=actual.json',
                       data=b'[{"time_s":0,"payload":"original"}]',
                       content_type='application/octet-stream')


@pytest.mark.parametrize('blocked_attempts', [1, 4])
def test_transient_lock_retries_same_complete_staging_directory(monkeypatch, publication, blocked_attempts):
    root, client, sleeps = publication
    replace = trace_sessions.os.replace
    attempts = []

    def locked(stage, destination):
        attempts.append((stage, destination))
        assert stage.parent == destination.parent == root
        assert {p.name for p in stage.iterdir()} == {
            'source.trace', 'events.jsonl', 'events.index.json', 'metadata.json'}
        assert not destination.exists()
        if len(attempts) <= blocked_attempts:
            raise PermissionError(errno.EACCES, 'transient directory lock')
        replace(stage, destination)

    monkeypatch.setattr(trace_sessions.os, 'replace', locked)
    response = upload(client)
    assert response.status_code == 200, response.json
    assert response.json['events'][0]['payload'] == 'original'
    assert len(set(attempts)) == 1
    assert len(attempts) == blocked_attempts + 1
    assert len(sleeps) == blocked_attempts and sum(sleeps) <= 0.75
    assert [p.name for p in root.iterdir()] == [response.json['session_id']]


@pytest.mark.parametrize('error,expected_attempts', [
    (PermissionError(errno.EACCES, 'persistent lock'), 5),
    (OSError(errno.EIO, 'disk error'), 1),
])
def test_failed_publication_never_accepts_or_leaves_partial_session(monkeypatch, publication, error, expected_attempts):
    root, client, sleeps = publication
    attempts = []

    def fail(stage, destination):
        attempts.append((stage, destination))
        raise error

    monkeypatch.setattr(trace_sessions.os, 'replace', fail)
    response = upload(client)
    assert response.status_code == 422
    assert 'session_id' not in response.json
    assert len(attempts) == expected_attempts
    assert len(sleeps) == expected_attempts - 1
    assert list(root.iterdir()) == []


def test_conflicting_destination_is_preserved_without_retry(monkeypatch, publication):
    root, client, sleeps = publication
    destinations = []

    def conflict(stage, destination):
        destination.mkdir()
        (destination / 'existing').write_text('keep', encoding='utf-8')
        destinations.append(destination)
        raise PermissionError(errno.EACCES, 'destination appeared')

    monkeypatch.setattr(trace_sessions.os, 'replace', conflict)
    response = upload(client)
    assert response.status_code == 422
    assert len(destinations) == 1 and sleeps == []
    assert (destinations[0] / 'existing').read_text(encoding='utf-8') == 'keep'
    assert list(root.iterdir()) == destinations
