"""Strict optional tokenizer admission; no mocked Original acceptance."""
import asyncio
from copy import deepcopy
import hashlib
import json

import httpx
import pytest

from backend.nis.agent.orchestration import local_reasoner as r


def module():
    from backend.nis.agent.orchestration import reference_token_budget
    return reference_token_budget


def test_supported_renderer_preserves_internal_text_and_actual_nothink_suffix():
    b = module()
    messages = [{'role': 'system', 'content': '  Exact µ system\n'},
                {'role': 'user', 'content': '\nLiteral /~ source\ninside\n'},
                {'role': 'assistant', 'content': ' {"literal":false} '},
                {'role': 'user', 'content': 'Next\x1c'}]
    before = deepcopy(messages)
    assert b.render_supported_chat(messages) == (
        '<|im_start|>system\nExact µ system<|im_end|>\n'
        '<|im_start|>user\nLiteral /~ source\ninside<|im_end|>\n'
        '<|im_start|>assistant\n{"literal":false}<|im_end|>\n'
        '<|im_start|>user\nNext\x1c<|im_end|>\n'
        '<|im_start|>assistant\n<think>\n\n</think>\n\n')
    assert messages == before


@pytest.mark.parametrize('messages', [
    [], [None], [{'role': 'tool', 'content': 'x'}], [{'role': 'user', 'content': ['x']}],
    [{'role': 'user', 'content': 'x', 'images': ['x']}],
    [{'role': 'assistant', 'content': 'prefill'}],
    [{'role': 'assistant', 'content': 'x</think>hidden'}, {'role': 'user', 'content': 'x'}],
    [{'role': 'user', 'content': 'x', 'tool_calls': []}],
])
def test_unknown_message_shapes_never_receive_exact_admission(messages):
    with pytest.raises(ValueError):
        module().render_supported_chat(messages)


def test_original_byte_guard_is_unchanged():
    messages = [{'role': 'user', 'content': 'µ' * 100}]
    assert r._reference_context_window(messages, 10440) == 10440
    with pytest.raises(ValueError):
        r._reference_context_window(messages, 10439)


def test_unavailable_exact_count_keeps_complete_oversized_input_rejected():
    b = module()
    messages = [{'role': 'user', 'content': 'Original source\n' * 10000}]
    before = deepcopy(messages)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(503))) as client:
            budget = b.ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'authored:model', 131072)
            with pytest.raises(ValueError, match='keine Quelle gekürzt'):
                await budget.admit(messages)
    asyncio.run(run())
    assert messages == before


def native_fixture():
    b = module()
    show = {'template': '{{ .Prompt }}', 'modelfile': 'FROM /models/sha256-' + 'a' * 64
            + '\nRENDERER qwen3.5\nPARSER qwen3.5\n', 'details': {'family': 'qwen35'},
            'model_info': {'tokenizer.ggml.add_bos_token': False}}
    return {'version': '0.33.1'}, {'models': [{'name': 'test:small', 'digest': 'b' * 64}]}, show


def transport_for(messages, tokens, corrupt=None):
    b = module()
    version, tags, show = native_fixture()
    descriptor = b.model_descriptor('test:small', version, tags, show)
    proof = {'schema_version': 1, 'contract': b.CONTRACT,
        'host_source_sha256': b.HOST_SOURCE_HASH,
        'contract_source_sha256': b.contract_source_hash(), 'descriptor': descriptor,
        'worker_identity': 'c' * 64, 'worker_context': 131072,
        'request_sha256': b.digest(messages),
        'prompt_sha256': hashlib.sha256(b.render_supported_chat(messages).encode()).hexdigest(),
        'input_tokens': tokens}
    if corrupt:
        proof.update(corrupt)
    def handle(request):
        values = {'/api/version': version, '/api/tags': tags, '/api/show': show,
                  '/tokenize-chat': proof}
        if request.url.path == '/tokenize-chat':
            assert json.loads(request.content)['messages'] == messages
        return httpx.Response(200, json=values[request.url.path])
    return httpx.MockTransport(handle), proof


@pytest.mark.parametrize('tokens,allowed', [(120832, True), (120833, False)])
def test_exact_count_boundary_keeps_all_reserves_and_full_source(tokens, allowed):
    messages = [{'role': 'user', 'content': 'Complete source µ\n' * 10000}]
    async def run():
        transport, proof = transport_for(messages, tokens)
        async with httpx.AsyncClient(transport=transport) as client:
            budget = module().ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'test:small', 131072)
            if allowed:
                assert await budget.admit(messages) == 131072
                await budget.verify_response(messages, {'model': 'test:small', 'prompt_eval_count': tokens})
                assert budget.evidence(messages) == proof
            else:
                with pytest.raises(ValueError, match='keine Quelle gekürzt'):
                    await budget.admit(messages)
    asyncio.run(run())


@pytest.mark.parametrize('corrupt', [
    {'request_sha256': '0' * 64}, {'prompt_sha256': '0' * 64}, {'worker_identity': ''},
    {'contract_source_sha256': '0' * 64}, {'contract': 'unknown'}, {'descriptor': {}},
    {'host_source_sha256': '0' * 64}, {'worker_context': 262144},
    {'input_tokens': True}, {'input_tokens': -1}, {'worker_context': 65536},
])
def test_unbound_native_counts_cannot_admit_any_source(corrupt):
    messages = [{'role': 'user', 'content': 'Full source\n' * 12000}]
    async def run():
        transport, _ = transport_for(messages, 40000, corrupt)
        async with httpx.AsyncClient(transport=transport) as client:
            budget = module().ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'test:small', 131072)
            with pytest.raises(ValueError, match='keine Quelle gekürzt'):
                await budget.admit(messages)
    asyncio.run(run())


@pytest.mark.parametrize('change', ['worker', 'tokens', 'model'])
def test_postresponse_drift_is_rejected_before_acceptance(change):
    messages = [{'role': 'user', 'content': 'Full source\n' * 12000}]
    async def run():
        transport, proof = transport_for(messages, 40000)
        async with httpx.AsyncClient(transport=transport) as client:
            budget = module().ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'test:small', 131072)
            await budget.admit(messages)
            body = {'model': 'test:small', 'prompt_eval_count': 40000}
            if change == 'worker':
                proof['worker_identity'] = 'd' * 64
            elif change == 'tokens':
                body['prompt_eval_count'] -= 1
            else:
                body['model'] = 'other:model'
            with pytest.raises(ValueError, match='Kein Entwurf übernommen'):
                await budget.verify_response(messages, body)
    asyncio.run(run())


@pytest.mark.parametrize('change', ['version', 'template', 'family', 'bos', 'system', 'adapter', 'digest'])
def test_unknown_model_configuration_cannot_claim_verified_renderer(change):
    version, tags, show = native_fixture()
    if change == 'version': version['version'] = '0.33.2'
    elif change == 'template': show['template'] = 'different'
    elif change == 'family': show['details']['family'] = 'other'
    elif change == 'bos': show['model_info']['tokenizer.ggml.add_bos_token'] = True
    elif change == 'system': show['system'] = 'extra hidden system text'
    elif change == 'adapter': show['modelfile'] += 'ADAPTER /other\n'
    else: tags['models'][0]['digest'] = 'unknown'
    with pytest.raises(ValueError):
        module().model_descriptor('test:small', version, tags, show)


def test_small_byte_bounded_requests_never_require_host_tokenizer():
    b = module()
    async def run():
        def forbidden(request):
            raise AssertionError('Unnecessary provider/host call')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
            budget = b.ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'any:model', 131072)
            assert await budget.admit([{'role': 'user', 'content': 'Complete small source'}]) == 131072
    asyncio.run(run())
