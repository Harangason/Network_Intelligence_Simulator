"""Read-only host binding rejects drift and never loads a model."""
from copy import deepcopy

import pytest

from backend.nis.agent.orchestration import host_tokenizer as h
from backend.nis.agent.orchestration.reference_token_budget import contract_source_hash


def request():
    return {'model': 'authored:small', 'messages': [{'role': 'user', 'content': 'Full source µ'}],
            'think': False, 'descriptor': {'immutable': 'authored'},
            'contract_source_sha256': contract_source_hash()}


def test_native_tokens_are_counted_without_generation(monkeypatch):
    original = request()
    monkeypatch.setattr(h, '_binding', lambda model: (original['descriptor'], 'a' * 64, 131072, 12345))
    calls = []
    def native(port, endpoint, data=None):
        calls.append((port, endpoint, data))
        assert endpoint == 'tokenize' and data['add_special'] is False
        return {'tokens': [1, 2, 3, 4]}
    monkeypatch.setattr(h, '_http', native)
    before = deepcopy(original)
    proof = h.count_chat(original)
    assert proof['input_tokens'] == 4 and proof['worker_context'] == 131072
    assert original == before and len(calls) == 1


@pytest.mark.parametrize('drift', ['descriptor', 'process', 'context', 'port'])
def test_worker_change_during_count_rejected(monkeypatch, drift):
    original = request()
    initial = (original['descriptor'], 'a' * 64, 131072, 12345)
    changed = list(initial)
    index = ['descriptor', 'process', 'context', 'port'].index(drift)
    changed[index] = [{'immutable': 'different'}, 'b' * 64, 65536, 12346][index]
    bindings = iter((initial, tuple(changed)))
    monkeypatch.setattr(h, '_binding', lambda _: next(bindings))
    monkeypatch.setattr(h, '_http', lambda *a: {'tokens': [1, 2]})
    with pytest.raises(ValueError, match='changed during tokenization'):
        h.count_chat(original)
    assert not h._lock.locked()


@pytest.mark.parametrize('tokens', [[], None, [True], [-1], ['1']])
def test_no_estimate_or_invalid_token_ids_allowed(monkeypatch, tokens):
    original = request()
    monkeypatch.setattr(h, '_binding', lambda _: (original['descriptor'], 'a' * 64, 131072, 12345))
    monkeypatch.setattr(h, '_http', lambda *a: {'tokens': tokens})
    with pytest.raises(ValueError, match='actual token IDs'):
        h.count_chat(original)


def test_stale_caller_never_contacts_tokenizer(monkeypatch):
    monkeypatch.setattr(h, '_binding', lambda _: ({'immutable': 'different'}, 'a' * 64, 131072, 12345))
    monkeypatch.setattr(h, '_http', lambda *a: pytest.fail('No tokenizer call for stale identity'))
    with pytest.raises(ValueError, match='stale'):
        h.count_chat(request())


def test_artifact_content_change_invalidates_cached_identity(tmp_path):
    path = tmp_path / 'model.gguf'
    path.write_bytes(b'old authored tokenizer')
    before = h._file_identity(path)
    path.write_bytes(b'new authored tokenizer with different length')
    after = h._file_identity(path)
    assert before['sha256'] != after['sha256']


@pytest.mark.parametrize('drift', ['contract_source_sha256', 'host_source_sha256'])
def test_http_bridge_refuses_code_loaded_after_different_startup_identity(monkeypatch, drift):
    import io
    import json
    from types import SimpleNamespace
    import host_metrics_bridge as bridge
    proof = {'contract_source_sha256': bridge.HOST_IMPLEMENTATION[bridge._HOST_FILES[1]],
             'host_source_sha256': bridge.HOST_IMPLEMENTATION[bridge._HOST_FILES[2]]}
    proof[drift] = '0' * 64
    monkeypatch.setattr(h, 'count_chat', lambda _: proof)
    handler = object.__new__(bridge.MetricsHandler)
    handler.path = '/tokenize-chat'
    handler.headers = {'Content-Length': '2'}
    handler.connection = SimpleNamespace(settimeout=lambda _: None)
    handler.rfile, handler.wfile = io.BytesIO(b'{}'), io.BytesIO()
    statuses = []
    handler.send_response = statuses.append
    handler.send_header = lambda *a: None
    handler.end_headers = lambda: None
    handler.do_POST()
    assert statuses == [503]
    assert json.loads(handler.wfile.getvalue()) == {'error': 'TOKENIZER_EVIDENCE_UNAVAILABLE'}


def test_loaded_contract_identity_does_not_follow_later_disk_edits(monkeypatch):
    from backend.nis.agent.orchestration import reference_token_budget as b
    identity = b.contract_source_hash()
    monkeypatch.setattr(b.Path, 'read_bytes', lambda _: b'changed file, not loaded code')
    assert b.contract_source_hash() == identity
