"""Read-only tokenizer access through the existing Windows host bridge.

Never loads/restarts a model, generates text, or probes a private provider.
Only the process actually listening on the main Ollama port and its direct
worker are eligible. Every count is bound before and after tokenization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
import urllib.request

from .reference_token_budget import (
    CONTRACT, contract_source_hash, digest, model_descriptor, render_supported_chat,
)

_lock = threading.Lock()
_file_hashes = {}
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(port, endpoint, data=None):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/{endpoint}',
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode('utf8'),
        headers={'Content-Type': 'application/json'})
    with _opener.open(request, timeout=15) as response:
        return json.load(response)


def _processes():
    command = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
# Some Windows builds return State=0 for the listener. Bind the unique local
# endpoint with no remote peer; never use a TIME_WAIT or client connection.
$owners = @(Get-NetTCPConnection -LocalPort 11434 -ErrorAction Stop | Where-Object { $_.LocalAddress -in @('127.0.0.1','0.0.0.0','::') -and $_.RemotePort -eq 0 -and $_.RemoteAddress -in @('0.0.0.0','::') -and $_.OwningProcess -gt 0 } | Select-Object -ExpandProperty OwningProcess -Unique)
if ($owners.Count -ne 1) { throw 'Ambiguous main provider listener' }
$main = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($owners[0])" | Where-Object { $_.Name -eq 'llama-server.exe' })
@($main) + $children | Select-Object ProcessId,ParentProcessId,Name,CommandLine,ExecutablePath,@{N='CreationStamp';E={$_.CreationDate.ToUniversalTime().ToString('O')}} | ConvertTo-Json -Compress
"""
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command],
        encoding='utf8', timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError('Exactly one main provider and loaded worker required')
    main, worker = rows
    if (main['Name'] != 'ollama.exe' or worker['Name'] != 'llama-server.exe'
            or worker['ParentProcessId'] != main['ProcessId']
            or not main.get('ExecutablePath') or not worker.get('ExecutablePath')
            or not main.get('CreationStamp') or not worker.get('CreationStamp')):
        raise ValueError('Main provider process binding missing')
    return main, worker


def _file_identity(path):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    key = (str(path).casefold(), before.st_size, before.st_mtime_ns, before.st_ino)
    value = _file_hashes.get(key)
    if value is None:
        with path.open('rb') as stream:
            value = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.stat()
        if (after.st_size, after.st_mtime_ns, after.st_ino) != key[1:]:
            raise ValueError('Tokenizer artifact changed while hashing')
        if len(_file_hashes) > 12:
            _file_hashes.clear()
        _file_hashes[key] = value
    return {'sha256': value, 'bytes': before.st_size, 'mtime_ns': before.st_mtime_ns}


def _binding(model):
    main, worker = _processes()
    command = worker.get('CommandLine') or ''
    match = re.search(r'--port\s+(\d+)(?:\s|$)', command)
    if match is None:
        raise ValueError('Worker port absent')
    port = int(match[1])
    version, tags, show = _http(11434, 'api/version'), _http(11434, 'api/tags'), _http(11434, 'api/show', {'model': model})
    descriptor = model_descriptor(model, version, tags, show)
    loaded = [row for row in _http(11434, 'api/ps').get('models', []) if row.get('name') == model]
    if len(loaded) != 1 or loaded[0].get('digest', '').removeprefix('sha256:') != descriptor['model_digest']:
        raise ValueError('Requested model is not the loaded immutable model')
    props = _http(port, 'props')
    header = show['modelfile'].split('\nLICENSE ', 1)[0]
    model_path = re.findall(r'^FROM (.+)$', header, re.M)[0]
    if (Path(props.get('model_path', '')).resolve() != Path(model_path).resolve()
            or str(model_path).casefold() not in command.casefold()):
        raise ValueError('Loaded worker uses a different tokenizer artifact')
    artifact = _file_identity(model_path)
    if artifact['sha256'] != descriptor['model_blob_sha256']:
        raise ValueError('Model blob content does not match its immutable identity')
    slots = _http(port, 'slots')
    if len(slots) != 1 or slots[0].get('is_processing'):
        raise ValueError('Main worker is occupied')
    context = props.get('default_generation_settings', {}).get('n_ctx')
    if type(context) is not int or context <= 0:
        raise ValueError('Worker context is unknown')
    identity = {'main': main, 'worker': worker, 'artifact': artifact,
        'main_binary': _file_identity(main['ExecutablePath']),
        'worker_binary': _file_identity(worker['ExecutablePath']),
        'worker_build': props.get('build_info'), 'worker_template': props.get('chat_template'),
        'context': context, 'descriptor': descriptor}
    return descriptor, digest(identity), context, port


def count_chat(request):
    if (not isinstance(request, dict)
            or set(request) != {'model', 'messages', 'think', 'descriptor', 'contract_source_sha256'}
            or request['think'] is not False or not isinstance(request['model'], str)
            or request['contract_source_sha256'] != contract_source_hash()):
        raise ValueError('Unsupported tokenizer request contract')
    prompt = render_supported_chat(request['messages'])
    if not _lock.acquire(blocking=False):
        raise ValueError('Tokenizer observation already in progress')
    try:
        before = _binding(request['model'])
        descriptor, identity, context, port = before
        if descriptor != request['descriptor']:
            raise ValueError('Caller model/template binding is stale')
        tokens = _http(port, 'tokenize', {'content': prompt, 'add_special': False}).get('tokens')
        if not isinstance(tokens, list) or not tokens or any(type(t) is not int or t < 0 for t in tokens):
            raise ValueError('Native tokenizer did not return actual token IDs')
        if _binding(request['model']) != before:
            raise ValueError('Provider/worker/tokenizer changed during tokenization')
        return {'schema_version': 1, 'contract': CONTRACT,
            'contract_source_sha256': contract_source_hash(), 'descriptor': descriptor,
            'worker_identity': identity, 'worker_context': context,
            'request_sha256': digest(request['messages']),
            'prompt_sha256': hashlib.sha256(prompt.encode('utf8')).hexdigest(),
            'input_tokens': len(tokens)}
    finally:
        _lock.release()
