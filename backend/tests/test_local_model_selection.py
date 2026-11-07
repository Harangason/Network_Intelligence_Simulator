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


@pytest.mark.parametrize('model,family', [
    ('local-gemma:4b', 'gemma'), ('mistral:7b', 'llama'),
    ('reviewed-model:latest', 'qwen35')])
def test_selected_local_completion_models_and_aliases_do_not_require_a_brand_prefix(model, family):
    info = {**metadata(family), 'capabilities': ['completion']}
    assert _local_model_author(model, info) == 'LOCAL_LLM'


@pytest.mark.parametrize('updates', [
    {'capabilities': ['embedding']}, {'capabilities': []},
    {'capabilities': 'completion'}, {'details': {'family': 'gemma', 'format': 'remote'}},
    {'model_info': {'general.parameter_count': float('inf')}},
    {'model_info': {'general.parameter_count': float('nan')}},
    {'remote_host': 'https://example.invalid'}, {'remote_model': 'remote'},
])
def test_generic_identity_still_rejects_remote_noncompletion_and_unverifiable_models(updates):
    info = {**metadata('gemma'), 'capabilities': ['completion'], **updates}
    with pytest.raises(ValueError):
        _local_model_author('local-gemma:4b', info)


def generic_function_specification():
    from backend.tests.test_qwen_function_blocks import specification
    spec = deepcopy(specification())
    spec['function_block']['provenance'].update(
        generated_by='LOCAL_LLM', model='local-gemma:4b',
        model_identity={**metadata('gemma'), 'capabilities': ['completion']},
        response={'model': 'local-gemma:4b', 'done': True, 'done_reason': 'stop'})
    return spec


def test_generic_function_preflight_keeps_bounded_execution_and_independent_cases():
    spec = generic_function_specification()
    block = validate_function_spec(spec)
    assert block.step({'value': 18.}, spec['block_parameters'], 0).value is True
    assert block.step({'value': 22.}, spec['block_parameters'], .5).value is False
    spec['function_block']['source_code'] = 'import os'
    with pytest.raises(ValueError):
        validate_function_spec(spec)


@pytest.mark.parametrize('updates', [
    {'model_identity': None},
    {'model_identity': {**metadata('gemma'), 'capabilities': ['embedding']}},
    {'model': 'local-gemma:cloud'},
    {'response': {'model': 'different:4b', 'done': True}},
    {'response': {'model': 'local-gemma:4b', 'done': False}},
    {'response': {'model': 'local-gemma:4b', 'done': True, 'done_reason': 'length'}},
    {'generated_by': 'UNKNOWN'},
])
def test_generic_function_provenance_requires_verified_identity_and_exact_complete_response(updates):
    spec = generic_function_specification()
    spec['function_block']['provenance'].update(updates)
    with pytest.raises(ValueError, match='authorship'):
        validate_function_spec(spec)


def test_generic_generator_uses_only_selected_model_and_records_identity(monkeypatch):
    monkeypatch.setenv('LOCAL_AI_MODEL', 'local-gemma:4b')
    generator = QwenBlockGenerator()
    calls = []
    info = {**metadata('gemma'), 'capabilities': ['completion']}
    def respond(path, payload=None):
        calls.append((path, payload))
        if path == '/api/show':
            assert payload == {'model': 'local-gemma:4b'}
            return info
        if path == '/api/tags':
            return {'models': [{'name': 'local-gemma:4b', 'digest': 'unit-gemma-digest'}]}
        assert payload['model'] == 'local-gemma:4b'
        return {'model': 'local-gemma:4b', 'done': True, 'message': {'content': json.dumps({
            'source_code': 'class Unit(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  return inputs["value"]\n'})}}
    monkeypatch.setattr(generator, 'request', respond)
    result = generator.generate('Unit contract', {}, {}, {})
    assert result['provenance']['generated_by'] == 'LOCAL_LLM'
    assert result['provenance']['model'] == 'local-gemma:4b'
    assert result['provenance']['model_identity'] == info
    assert [path for path, _ in calls] == ['/api/show', '/api/tags', '/api/chat']


@pytest.mark.parametrize('model,family,author', [
    ('qwen3.8:27b', 'qwen35', 'QWEN'), ('llama3.1:8b', 'llama', 'LLAMA')])
def test_historical_local_identity_metadata_remains_compatible(model, family, author):
    info = metadata(family)
    del info['details']['format']
    assert _local_model_author(model, info) == author


@pytest.mark.parametrize('model,author,source', [
    ('llama3.1:8b', 'LLAMA', 'LLAMA generated expected output'),
    ('local-gemma:4b', 'LOCAL_LLM', 'local-gemma generated expected output'),
    ('local-gemma:4b', 'LOCAL_LLM', 'LOCAL_LLM generated expected output'),
])
def test_expected_values_cannot_be_attributed_to_the_generating_model(model, author, source):
    from backend.tests.test_qwen_function_blocks import specification
    from backend.nis.simulation.signals.core.function_block import verify_function_cases
    spec = specification()
    definition = spec['function_block']
    definition['provenance'].update(model=model, generated_by=author)
    definition['verification_cases'] = [{'source': source, 'steps': [
        {'inputs': {'value': 18.}, 'dt_s': 0., 'expected': True}]}]
    with pytest.raises(ValueError, match='independent source'):
        verify_function_cases(definition, spec['block_parameters'], spec['transport_inputs'])


def completion_only_planner(monkeypatch, *, status=400, error='model does not support tools', wire=None):
    from backend.nis.agent.context.agent_context import AgentContext
    monkeypatch.setenv('LOCAL_AI_MODEL', 'local-completion:4b')
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', 'local-completion:4b')
    payloads = []
    original = [{'role': 'user', 'content': 'Prüfe genau die ursprüngliche Anforderung Ü-42.'},
        {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'prior-1', 'type': 'function',
            'function': {'name': 'inspect_project', 'arguments': {'revision': 1}}}]},
        {'role': 'tool', 'tool_call_id': 'prior-1', 'content': '{"revision": 2, "findings": []}'},
        {'role': 'user', 'content': 'Prüfe jetzt Revision 2 mit inspect_project.'}]
    history = deepcopy(original)
    tool = {'name': 'inspect_project', 'description': 'Read the exact current project revision.',
        'input_schema': {'type': 'object', 'properties': {'revision': {'type': 'integer', 'minimum': 1}},
                         'required': ['revision'], 'additionalProperties': False}}
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def respond(request):
            payloads.append(json.loads(request.content))
            if len(payloads) == 1:
                return httpx.Response(status, json={'error': error})
            response = {'model': 'local-completion:4b', 'done': True,
                'message': {'content': json.dumps({'content': '', 'tool_calls': [
                    {'function': {'name': 'inspect_project', 'arguments': {'revision': 2}}}]})}}
            response.update(wire or {})
            return httpx.Response(200, json=response)
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            return await reasoner.next(history, AgentContext(active_project_id='completion-test'), [tool])
        finally:
            await reasoner.close()
            assert history == original
    return run, payloads


def test_completion_only_planner_preserves_model_history_and_exact_tool_schema(monkeypatch):
    run, payloads = completion_only_planner(monkeypatch)
    result = asyncio.run(run())
    assert len(payloads) == 2
    first, second = payloads
    assert first['model'] == second['model'] == 'local-completion:4b'
    assert first['options'] == second['options'] and first['keep_alive'] == second['keep_alive']
    assert 'tools' not in second
    assert 'ursprüngliche Anforderung Ü-42' in json.dumps(second['messages'], ensure_ascii=False)
    assert any(json.loads(m['content']).get('tool_result', {}).get('content') == '{"revision": 2, "findings": []}'
               for m in second['messages'] if m.get('content', '').startswith('{'))
    alternative = second['format']['properties']['tool_calls']['items']['anyOf'][0]
    args = alternative['properties']['function']['properties']['arguments']
    assert args['required'] == ['revision'] and args['properties']['revision']['minimum'] == 1
    assert args['additionalProperties'] is False
    assert [(c['name'], c['arguments']) for c in result['calls']] == [('inspect_project', {'revision': 2})]


@pytest.mark.parametrize('status,error', [(503, 'temporarily unavailable'), (400, 'invalid context'),
                                       (400, 'model not found')])
def test_unrelated_planner_errors_never_switch_protocol_or_model(monkeypatch, status, error):
    run, payloads = completion_only_planner(monkeypatch, status=status, error=error)
    with pytest.raises(RuntimeError, match=f'HTTP {status}'):
        asyncio.run(run())
    assert len(payloads) == 1


@pytest.mark.parametrize('wire', [
    {'done': False}, {'done_reason': 'length'}, {'model': 'different-model:4b'},
    {'message': {'content': '{"content":"","tool_calls":[{"function":{"name":"delete_project","arguments":{}}}]}'}},
    {'message': {'content': '{"content":"","tool_calls":[{"function":{"name":"inspect_project","arguments":{"revision":0}}}]}'}},
])
def test_structured_planner_rejects_incomplete_wrong_model_and_schema_bypasses(monkeypatch, wire):
    run, payloads = completion_only_planner(monkeypatch, wire=wire)
    with pytest.raises(RuntimeError, match='strukturierte Werkzeugantwort'):
        asyncio.run(run())
    assert len(payloads) == 2


def test_successful_transport_does_not_require_error_status_or_protocol_adaptation(monkeypatch):
    from types import SimpleNamespace
    from backend.nis.agent.context.agent_context import AgentContext
    monkeypatch.setenv('LOCAL_AI_MODEL', 'main-test-model')
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', 'main-test-model')
    calls = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        async def post(url, json):
            calls.append(json)
            return SimpleNamespace(is_error=False, json=lambda: {'message': {'content': 'Model contract explanation.'}})
        reasoner.client.post = post
        try:
            return await reasoner.next([{'role': 'user', 'content': 'Erkläre den Modellvertrag.'}],
                AgentContext(active_project_id='successful-transport'), [{'name': 'inspect_project',
                    'description': 'Read project', 'input_schema': {'type': 'object', 'properties': {}}}])
        finally:
            await reasoner.close()
    result = asyncio.run(run())
    assert result['text'] == 'Model contract explanation.' and result['calls'] == []
    assert len(calls) == 1 and calls[0]['model'] == 'main-test-model' and 'format' not in calls[0]
