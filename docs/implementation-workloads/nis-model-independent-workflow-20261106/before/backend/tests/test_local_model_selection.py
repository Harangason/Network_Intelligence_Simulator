"""Mocked selection/provenance regressions; native acceptance is recorded separately."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner, _local_model_author
from backend.nis.agent.tools.function_blocks import QwenBlockGenerator
from backend.nis.simulation.signals.core.function_block import validate_function_spec


def metadata(family='llama'):
    return {'details': {'family': family, 'format': 'gguf'},
            'model_info': {'general.parameter_count': 8_000_000_000}}


@pytest.mark.parametrize('model,family,author', [
    ('llama3.1:8b', 'llama', 'LLAMA'), ('qwen3.8:27b', 'qwen35', 'QWEN')])
def test_selected_local_family_is_verified_without_changing_model(model, family, author):
    assert _local_model_author(model, metadata(family)) == author


@pytest.mark.parametrize('model,updates', [
    ('llama3.1:8b', {'remote_host': 'https://example.invalid'}),
    ('llama3.1:8b', {'remote_model': 'another-model'}),
    ('llama3.1:cloud', {}),
    ('unknown:8b', {}),
    ('qwen3.8:27b', {}),
    ('llama3.1:8b', {'details': {'family': 'qwen35'}}),
    ('llama3.1:8b', {'model_info': {}}),
    ('llama3.1:8b', {'model_info': {'general.parameter_count': 0}}),
    ('llama3.1:8b', {'model_info': {'general.parameter_count': True}}),
])
def test_remote_unknown_missing_or_mismatched_identity_cannot_become_a_fallback(model, updates):
    with pytest.raises(ValueError, match='Cloud-Modelle'):
        _local_model_author(model, {**metadata(), **updates})


def test_nis_config_and_unconfigured_defaults_select_only_llama(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / 'config/networkis.resources.json').read_bytes())
    selected = config['ai']['providers']['ollama']
    assert selected['model'] == selected['fast_model'] == 'llama3.1:8b'
    assert config['ai']['active_provider'] == 'local'
    assert config['ai']['cloud_escalation'] == 'never'
    for key in ('LOCAL_AI_MODEL', 'LOCAL_AI_FAST_MODEL'):
        monkeypatch.delenv(key, raising=False)
    reasoner = LocalEngineeringReasoner()
    try:
        assert reasoner.model == reasoner.fast_model == 'llama3.1:8b'
        from backend.nis.app.runtime_config import runtime_settings
        settings = runtime_settings()
        assert settings.local_ai_model == settings.local_ai_fast_model == 'llama3.1:8b'
    finally:
        asyncio.run(reasoner.client.aclose())


def test_llama_reference_plan_preserves_full_sources_and_configured_model(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    payloads = []
    instance, prepared, _ = reasoner_with_transport(monkeypatch, family='llama', capture=payloads)
    instance.model = 'llama3.1:8b'
    result = run_reference(instance, prepared)
    assert result['model'] == 'llama3.1:8b'
    assert all(payload['model'] == 'llama3.1:8b' for payload in payloads)
    assert result['source_evidence']['source_text'] == prepared['source_evidence']['source_text']
    assert result['canonical_writes'] is False


def test_llama_document_intake_preserves_review_and_source_contract(monkeypatch):
    from backend.tests.test_qwen_document_intake import SOURCE, interpretation, model_wire_response
    monkeypatch.setenv('LOCAL_AI_MODEL', 'llama3.1:8b')
    captured = []

    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()

        def respond(request):
            payload = json.loads(request.content)
            assert payload['model'] == 'llama3.1:8b'
            if request.url.path.endswith('/show'):
                return httpx.Response(200, json=metadata())
            captured.append(payload)
            return httpx.Response(200, json={'message': {
                'content': json.dumps(model_wire_response(interpretation(), payload))}})

        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            return await reasoner.interpret_document(SOURCE, 'llama-selection-test.txt')
        finally:
            await reasoner.client.aclose()

    result = asyncio.run(run())
    assert result['model'] == 'llama3.1:8b'
    assert result['source_complete'] is True and result['source_chars'] == len(SOURCE)
    assert result['status'] == 'REVIEW_REQUIRED' and result['canonical_writes'] is False
    assert SOURCE == ''.join(json.loads(captured[0]['messages'][1]['content'])['source_lines'].values())


def test_llama_generated_function_retains_its_actual_author_and_exact_model(monkeypatch):
    monkeypatch.setenv('LOCAL_AI_MODEL', 'llama3.1:8b')
    generator = QwenBlockGenerator()  # Existing public class name remains compatible.
    generated = {'name': 'unit', 'source_code': 'def step(inputs, state, params, dt):\n    return inputs["value"]\n'}
    calls = []

    def respond(path, payload=None):
        calls.append((path, payload))
        if path == '/api/show':
            return metadata()
        if path == '/api/tags':
            return {'models': [{'name': 'llama3.1:8b', 'digest': 'unit-model-digest'}]}
        assert payload['model'] == 'llama3.1:8b'
        return {'model': 'llama3.1:8b', 'done': True,
                'message': {'content': json.dumps(generated)}}

    monkeypatch.setattr(generator, 'request', respond)
    result = generator.generate('Unit contract', {}, {}, {})
    assert result['provenance']['generated_by'] == 'LLAMA'
    assert result['provenance']['model'] == 'llama3.1:8b'
    assert result['provenance']['model_digest'] == 'unit-model-digest'
    assert result['source_sha256']
    assert [path for path, _ in calls] == ['/api/show', '/api/tags', '/api/chat']


@pytest.mark.parametrize('author,model,valid', [
    ('QWEN', 'qwen3:8b', True), ('LLAMA', 'llama3.1:8b', True),
    ('LLAMA', 'qwen3:8b', False), ('QWEN', 'llama3.1:8b', False),
    ('LLAMA', 'llama3.1:cloud', False), ('UNKNOWN', 'llama3.1:8b', False)])
def test_function_preflight_keeps_author_and_model_consistent(author, model, valid):
    from backend.tests.test_qwen_function_blocks import specification
    spec = deepcopy(specification())
    spec['function_block']['provenance'].update(generated_by=author, model=model)
    if valid:
        validate_function_spec(spec)
    else:
        with pytest.raises(ValueError, match='authorship'):
            validate_function_spec(spec)
