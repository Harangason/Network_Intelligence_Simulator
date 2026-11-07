"""Optional verified native token counts; the conservative byte guard remains default.

Text renderer contract: Ollama v0.33.1 model/renderers/qwen35.go and renderer.go.
Only the verified text-only, think=false subset is supported. This is not a
tokenizer implementation: token IDs always come from the actual loaded worker.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import httpx


CONTRACT = 'ollama-0.33.1-qwen35-text-nothink-v1'
GO_SPACE = '\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def contract_source_hash():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def render_supported_chat(messages):
    if (not isinstance(messages, list) or not messages
            or not isinstance(messages[-1], dict) or messages[-1].get('role') != 'user'):
        raise ValueError('Unsupported chat framing')
    parts = []
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                or message['role'] not in {'system', 'user', 'assistant'}
                or not isinstance(message['content'], str)):
            raise ValueError('Unsupported message fields')
        content = message['content'].strip(GO_SPACE)
        # The upstream renderer extracts tagged assistant reasoning. Refuse that
        # less common shape rather than silently applying an unverified rule.
        if message['role'] == 'assistant' and any(tag in content for tag in ('<think>', '</think>')):
            raise ValueError('Unsupported assistant reasoning content')
        parts.append('<|im_start|>' + message['role'] + '\n' + content + '<|im_end|>\n')
    return ''.join(parts) + '<|im_start|>assistant\n<think>\n\n</think>\n\n'


def model_descriptor(model, version, tags, show):
    if version.get('version') != '0.33.1':
        raise ValueError('Unverified provider renderer version')
    matches = [row for row in tags.get('models', []) if row.get('name') == model]
    if len(matches) != 1:
        raise ValueError('Ambiguous model identity')
    identity = matches[0].get('digest', '').removeprefix('sha256:')
    if not re.fullmatch('[0-9a-f]{64}', identity):
        raise ValueError('Missing immutable model digest')
    header = show.get('modelfile', '').split('\nLICENSE ', 1)[0]
    if (show.get('template', '').strip() != '{{ .Prompt }}'
            or re.findall(r'^RENDERER (.+)$', header, re.M) != ['qwen3.5']
            or re.findall(r'^PARSER (.+)$', header, re.M) != ['qwen3.5']
            or show.get('details', {}).get('family') != 'qwen35'
            or show.get('model_info', {}).get('tokenizer.ggml.add_bos_token') is not False
            or show.get('system') or show.get('messages')
            or re.search(r'^ADAPTER ', header, re.M)):
        raise ValueError('Unverified model/template configuration')
    sources = re.findall(r'^FROM (.+)$', header, re.M)
    if not sources or not re.search(r'sha256-[0-9a-f]{64}$', sources[0]):
        raise ValueError('Missing tokenizer model artifact')
    return {'model': model, 'model_digest': identity, 'provider_version': '0.33.1',
            'template_sha256': digest(show['template']), 'renderer': CONTRACT,
            'model_blob_sha256': sources[0][-64:],
            'configuration_sha256': digest({k: show.get(k) for k in
                ('template', 'parameters', 'system', 'messages', 'details')})}


class _NeedsCount(Exception):
    def __init__(self, messages):
        self.messages = messages


class ReferenceTokenBudget:
    """Request-scoped evidence cache; selected requests are freshly revalidated."""
    def __init__(self, client, chat_url, model, maximum, *, bridge_url=None):
        self.client, self.chat_url, self.model, self.maximum = client, chat_url, model, maximum
        base = urlsplit(chat_url)
        self.api_root = chat_url.removesuffix('/api/chat')
        self.bridge_url = bridge_url or os.environ.get('NIS_LOCAL_TOKENIZER_URL') or (
            f'http://{base.hostname}:13502/tokenize-chat' if base.hostname else '')
        bridge = urlsplit(self.bridge_url)
        self.available = (base.scheme == bridge.scheme == 'http'
            and base.hostname in {'127.0.0.1', 'localhost', 'host.docker.internal'}
            and base.port == 11434 and bridge.hostname == base.hostname
            and bridge.path == '/tokenize-chat' and not bridge.query
            and not bridge.username and not base.username)
        self.proofs = {}

    async def _descriptor(self):
        responses = [await self.client.get(self.api_root + '/api/version', timeout=15),
                     await self.client.get(self.api_root + '/api/tags', timeout=15),
                     await self.client.post(self.api_root + '/api/show', json={'model': self.model}, timeout=15)]
        for response in responses:
            response.raise_for_status()
        return model_descriptor(self.model, *(response.json() for response in responses))

    async def _measure(self, messages):
        if not self.available:
            return None
        try:
            prompt = render_supported_chat(messages)
            descriptor = await self._descriptor()
            response = await self.client.post(self.bridge_url, json={
                'model': self.model, 'messages': messages, 'think': False,
                'descriptor': descriptor, 'contract_source_sha256': contract_source_hash()}, timeout=30)
            response.raise_for_status()
            proof = response.json()
            if (proof.get('schema_version') != 1 or proof.get('contract') != CONTRACT
                    or proof.get('contract_source_sha256') != contract_source_hash()
                    or proof.get('request_sha256') != digest(messages)
                    or proof.get('prompt_sha256') != hashlib.sha256(prompt.encode('utf8')).hexdigest()
                    or proof.get('descriptor') != descriptor
                    or type(proof.get('input_tokens')) is not int or proof['input_tokens'] <= 0
                    or type(proof.get('worker_context')) is not int or proof['worker_context'] < self.maximum
                    or not isinstance(proof.get('worker_identity'), str)
                    or not re.fullmatch('[0-9a-f]{64}', proof['worker_identity'])
                    or await self._descriptor() != descriptor):
                return None
            return proof
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def check(self, messages, maximum):
        from .local_reasoner import _reference_context_window
        if maximum != self.maximum:
            raise ValueError('Context maximum changed')
        try:
            return _reference_context_window(messages, maximum)
        except ValueError as byte_error:
            key = digest(messages)
            if key not in self.proofs:
                raise _NeedsCount(messages) from byte_error
            proof = self.proofs[key]
            if proof is not None and proof['input_tokens'] + 8192 + 2048 <= maximum:
                return maximum
            raise byte_error

    async def select(self, builder, *args, **kwargs):
        while True:
            try:
                return builder(*args, **kwargs, capacity_check=self.check)
            except _NeedsCount as needed:
                self.proofs[digest(needed.messages)] = await self._measure(needed.messages)

    async def admit(self, messages):
        from .local_reasoner import _reference_context_window
        try:
            return _reference_context_window(messages, self.maximum)
        except ValueError:
            # Refresh the selected message, including each retry, immediately
            # before dispatch. A historical worker count cannot authorize it.
            self.proofs[digest(messages)] = await self._measure(messages)
            return self.check(messages, self.maximum)

    async def verify_response(self, messages, body):
        proof = self.proofs.get(digest(messages))
        if proof is None:
            return
        current = await self._measure(messages)
        if (current is None or current != proof
                or type(body.get('prompt_eval_count')) is not int
                or body['prompt_eval_count'] != proof['input_tokens']
                or body.get('model') != self.model):
            raise ValueError('Lokale Tokenprüfung: Modell-, Vorlagen- oder Eingabeidentität hat sich geändert. Kein Entwurf übernommen.')

    def evidence(self, messages):
        proof = self.proofs.get(digest(messages))
        return None if proof is None else dict(proof)
