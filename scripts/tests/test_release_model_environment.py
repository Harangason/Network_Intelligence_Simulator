"""Host-only model-policy regressions; no Docker mutation or inference."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_existing_model_keys_reach_release_docker_arguments_without_secrets(monkeypatch):
    gate = load('model_gate', 'scripts/run-release-gate.py')
    monkeypatch.setenv('LOCAL_AI_MODEL', 'qwen3.8:27b')
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', 'qwen3.8:27b')
    monkeypatch.setenv('LOCAL_AI_API_KEY', 'authored-secret-that-must-not-be-forwarded')
    helper = getattr(gate, 'local_ai_model_environment', None)
    assert callable(helper), 'Canonical release must preserve explicitly requested model configuration.'
    environment = helper()
    assert environment == {'LOCAL_AI_MODEL': 'qwen3.8:27b', 'LOCAL_AI_FAST_MODEL': 'qwen3.8:27b'}
    assert gate.local_ai_model_arguments(environment) == [
        '-e', 'LOCAL_AI_MODEL=qwen3.8:27b', '-e', 'LOCAL_AI_FAST_MODEL=qwen3.8:27b']


def test_absent_model_overrides_preserve_existing_image_defaults(monkeypatch):
    gate = load('model_gate_defaults', 'scripts/run-release-gate.py')
    monkeypatch.delenv('LOCAL_AI_MODEL', raising=False)
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', '   ')
    helper = getattr(gate, 'local_ai_model_environment', None)
    assert callable(helper)
    assert helper() == {} and gate.local_ai_model_arguments(helper()) == []


@pytest.mark.parametrize('actual,allow', [('llama3.1:8b', False), ('qwen3.8:27b', True)])
def test_retained_stack_reuse_checks_actual_configured_model_environment(actual, allow):
    delivery = load('model_delivery', 'scripts/release-and-deploy.py')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'receipt.json'
        names = {'app': 'nis-e2e-app-a', 'db': 'nis-e2e-db-a',
                 'network': 'nis-e2e-network-a', 'runtime': 'nis-e2e-runtime-a'}
        receipt = {'status': 'PREPARED', 'initial_source_sha256': 's', 'initial_commit_id': 'c',
                   'image_id': 'sha256:image', 'containers': names, 'base_url': 'http://127.0.0.1:12345'}
        path.write_text(json.dumps(receipt), encoding='utf8')
        app = {'Name': '/' + names['app'], 'Image': 'sha256:image', 'State': {'Status': 'running'},
               'Config': {'Labels': {'networkis.test': 'disposable'}, 'Env': ['LOCAL_AI_BASE_URL=ai',
                   'DATABASE_URL=postgresql://nis_test:authored@test-db:5432/nis_test_e2e',
                   'LOCAL_AI_MODEL=qwen3.8:27b', 'LOCAL_AI_FAST_MODEL=' + actual]},
               'Mounts': [{'Name': names['runtime'], 'Destination': '/app/var/data'}],
               'NetworkSettings': {'Networks': {names['network']: {}},
                   'Ports': {'13500/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '12345'}]}}}
        db = {**app, 'Name': '/' + names['db']}
        ready = io.StringIO('{}'); ready.status = 200
        build = io.StringIO(json.dumps({'source_sha256': 's', 'commit_id': 'c'}))
        with (patch.object(delivery.subprocess, 'check_output', side_effect=['a\nb', json.dumps([app, db])]),
              patch.object(delivery, 'urlopen', side_effect=[ready, build]),
              patch.object(delivery.subprocess, 'run') as mutation):
            def reuse():
                return delivery.prepared_stack('docker', [path], 's', 'c', prepare=True, keep=False,
                    ai_url='ai', model_environment={'LOCAL_AI_MODEL': 'qwen3.8:27b',
                                                  'LOCAL_AI_FAST_MODEL': 'qwen3.8:27b'})
            if allow:
                assert reuse() == (path, receipt)
            else:
                with pytest.raises(RuntimeError, match='retained test stack'):
                    reuse()
            mutation.assert_not_called()
