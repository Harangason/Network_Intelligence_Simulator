"""Explicit-only Codex stdio repair adapter. No initialization at import time."""
from __future__ import annotations
import getpass
import hashlib
import inspect
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid

SCHEMA = Path(__file__).resolve().parents[1] / 'config' / 'codex-protocol-schema'
METHODS = {
    'item/tool/requestUserInput': ('ToolRequestUserInputParams', 'ToolRequestUserInputResponse'),
    'item/commandExecution/requestApproval': ('CommandExecutionRequestApprovalParams', 'CommandExecutionRequestApprovalResponse'),
    'item/fileChange/requestApproval': ('FileChangeRequestApprovalParams', 'FileChangeRequestApprovalResponse'),
    'mcpServer/elicitation/request': ('McpServerElicitationRequestParams', 'McpServerElicitationRequestResponse'),
}

def validate(name, value):
    # jsonschema is required only in repair mode; absence fails closed.
    from jsonschema import Draft7Validator
    schema = json.loads((SCHEMA / (name + '.json')).read_text(encoding='utf-8'))
    Draft7Validator(schema).validate(value)

def redact(value):
    """Minimized logs deliberately omit payloads, commands, model text and answers."""
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k in {
            'method', 'id', 'event', 'status', 'phase', 'percentage', 'attempt', 'case_id'}}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r'(?i)(bearer\s+\S+|sk-[\w-]+|(?:token|password|secret|api_key)\s*[=:]\s*\S+)', '[REDACTED]', value)
    return value

def protected_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(safe_evidence(data), stream, ensure_ascii=False, indent=2)
    if os.name == 'nt':
        acl = subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
            getpass.getuser() + ':(F)'], capture_output=True)
        if acl.returncode: raise PermissionError('Cannot protect repair evidence ACL')

def safe_evidence(value):
    if isinstance(value, dict):
        return {k: safe_evidence(v) for k,v in value.items()
            if not re.search(r'(?i)(password|secret|token|authorization|api.?key|reasoning|encrypted_content)', k)}
    if isinstance(value, list): return [safe_evidence(v) for v in value]
    if isinstance(value, str): return redact(value)
    return value

def request_key(value):
    if type(value) not in (int, str): raise ValueError('Invalid request ID')
    return (type(value).__name__, value)

class CodexAppServer:
    def __init__(self, executable, cwd, *, log=None):
        self.executable, self.cwd, self.log = executable, str(cwd), log
        self.proc = None
        self.events = queue.Queue()
        self.pending, self.closed, self.responses = {}, set(), {}
        self.serial = 0
        self.thread_id = self.turn_id = None
        self.state = 'NEW'
        self.turn_result = None
        self.file_changes = {}

    def _reader(self):
        try:
            for line in self.proc.stdout:
                self.events.put(json.loads(line))
        except Exception:
            self.events.put({'_disconnect': True})
        finally:
            self.events.put({'_disconnect': True})

    def start(self):
        self.proc = subprocess.Popen([self.executable, 'app-server', '--stdio'], cwd=self.cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', bufsize=1)
        threading.Thread(target=self._reader, daemon=True).start()
        self.state = 'RUNNING'

    def send(self, value):
        if self.state == 'DISCONNECTED': raise ConnectionError('Disconnected; no replay permitted')
        if self.log: self.log(redact(value))
        self.proc.stdin.write(json.dumps(value, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()

    def receive(self, timeout=0.2):
        try: value = self.events.get(timeout=timeout)
        except queue.Empty: return None
        if value.get('_disconnect'):
            self.state = 'DISCONNECTED'
            return value
        if self.log: self.log(redact(value))
        method = value.get('method')
        params = value.get('params', {})
        if method == 'turn/started' and params.get('threadId') == self.thread_id:
            self.turn_id = params['turn']['id']
        if method in ('item/started','item/completed') and params.get('threadId') == self.thread_id:
            item = params.get('item', {})
            if item.get('type') == 'fileChange':
                self.file_changes[item['id']] = item.get('changes', [])
        if method == 'serverRequest/resolved':
            validate('ServerRequestResolvedNotification', params)
            key = request_key(params['requestId'])
            old = self.pending.get(key)
            if old and params['threadId'] == old['params']['threadId']:
                self.pending.pop(key)
                self.closed.add(key)
        elif method and 'id' in value:
            key = request_key(value['id'])
            if key in self.closed: return value
            if method not in METHODS:
                self.state = 'INPUT_REQUIRED'
                raise ValueError('Unsupported server request: ' + method)
            validate(METHODS[method][0], params)
            if params['threadId'] != self.thread_id or (params.get('turnId') and params['turnId'] != self.turn_id):
                raise ValueError('Foreign thread/turn request')
            if key in self.pending and self.pending[key] != value:
                raise ValueError('Conflicting duplicate request ID')
            self.pending[key] = value
        elif 'id' in value:
            self.responses[request_key(value['id'])] = value
        elif method == 'turn/completed' and params.get('threadId') == self.thread_id:
            turn = params.get('turn', {})
            if turn.get('id') == self.turn_id: self.turn_result = turn
        if self.state not in ('DISCONNECTED', 'INPUT_REQUIRED'):
            self.state = 'WAITING_FOR_USER' if self.pending else 'RUNNING'
        return value

    def call(self, method, params, timeout=20):
        self.serial += 1
        rid = 'checker-' + str(self.serial)
        self.send({'id': rid, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        key = request_key(rid)
        while key not in self.responses:
            self.receive()
            if self.state == 'DISCONNECTED': raise ConnectionError('Codex disconnected')
            if time.monotonic() > deadline: raise TimeoutError(method)
        answer = self.responses.pop(key)
        if 'error' in answer: raise RuntimeError('Codex protocol request failed: ' + method)
        return answer['result']

    def initialize(self):
        self.start()
        result = self.call('initialize', {'clientInfo': {'name': 'tool_checker', 'version': '1.0'},
            'capabilities': {'experimentalApi': True, 'requestAttestation': False}})
        self.send({'method': 'initialized', 'params': {}})
        return result

    def begin(self, prompt, model=None):
        params = {'cwd': self.cwd, 'approvalPolicy': 'on-request', 'approvalsReviewer': 'user',
            'sandbox': 'workspace-write', 'ephemeral': True}
        if model: params['model'] = model
        validate('ThreadStartParams', params)
        self.thread_id = self.call('thread/start', params)['thread']['id']
        response = self.call('turn/start', {'threadId': self.thread_id,
            'input': [{'type': 'text', 'text': prompt, 'text_elements': []}], 'summary': 'none'})
        self.turn_id = response['turn']['id']

    def answer(self, request_id, result):
        # Drain resolved notifications before accepting an answer entered asynchronously.
        while not self.events.empty(): self.receive(0)
        key = request_key(request_id)
        if self.state == 'DISCONNECTED': raise ConnectionError('No approval replay after disconnect')
        if key not in self.pending or key in self.closed: raise ValueError('Stale/already answered request')
        item = self.pending[key]
        if item['method'] == 'item/fileChange/requestApproval' and result.get('decision') in ('accept','acceptForSession'):
            if not self.file_changes.get(item['params']['itemId']) and not item['params'].get('grantRoot'):
                raise ValueError('File approval context unavailable; decline or cancel')
        validate(METHODS[item['method']][1], result)
        if item['method'] == 'item/tool/requestUserInput':
            questions = item['params']['questions']
            if set(result['answers']) != {q['id'] for q in questions}: raise ValueError('Answer every question exactly once')
            for question in questions:
                values = result['answers'][question['id']]['answers']
                if not values or any(not v.strip() for v in values): raise ValueError('Empty answer')
                labels = {o['label'] for o in question.get('options') or []}
                if labels and not question.get('isOther') and any(v not in labels for v in values):
                    raise ValueError('Invalid option')
        if item['method'] == 'mcpServer/elicitation/request' and result['action'] == 'accept':
            if item['params']['mode'] == 'url': raise ValueError('URL elicitation needs external completion; decline or cancel')
            from jsonschema import Draft7Validator
            Draft7Validator(item['params']['requestedSchema']).validate(result['content'])
        self.send({'id': request_id, 'result': result})
        self.pending.pop(key)
        self.closed.add(key)
        self.state = 'WAITING_FOR_USER' if self.pending else 'RUNNING'

    def abort(self):
        if self.thread_id and self.turn_id and self.state != 'DISCONNECTED':
            self.send({'id': 'checker-abort-' + uuid.uuid4().hex, 'method': 'turn/interrupt',
                'params': {'threadId': self.thread_id, 'turnId': self.turn_id}})
        self.state = 'ABORTED'
        self.close()

    def close(self):
        if self.proc:
            self.proc.terminate()
            try: self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()

class RepairProgress:
    # Immutable, predeclared workflow; never counts tokens, elapsed time or arbitrary events.
    plan = tuple({'step_id': name, 'phase': name, 'weight': 1} for name in ('package','attempt','diff','retest','persist'))
    weights = {'package': 10, 'attempt': 35, 'diff': 15, 'retest': 30, 'persist': 10}
    def __init__(self): self.completed = set()
    def complete(self, phase):
        expected = self.plan[len(self.completed)]['step_id'] if len(self.completed) < len(self.plan) else None
        if phase != expected: raise ValueError('Out-of-order repair phase')
        self.completed.add(phase)
    @property
    def percentage(self):
        from progress_model import percentage
        return percentage(self.plan, self.completed, self.weights)

class InputRequired(RuntimeError):
    pass

class QuietRepairView:
    """One replaceable progress line; questions always start on a separate line."""
    def __init__(self, case, output):
        self.output = output
        self.label = str(case.get('id', case.get('test_id'))) + ' ' + ' '.join(
            str(case.get('title', case.get('name', ''))).split())[:60]
        self.previous = None
        self.line_open = False
        try:
            inspect.signature(output).bind('', end='', flush=True)
            self.keyword_output = True
        except (TypeError, ValueError):
            self.keyword_output = False

    def progress(self, value):
        if value == self.previous: return
        filled = int(value / 5)
        line = '\r' + self.label.rstrip() + ' [' + '#' * filled + '-' * (20-filled) + '] ' + f'{value:g}%'
        if self.keyword_output: self.output(line, end='', flush=True)
        else: self.output(line)
        self.previous = value
        self.line_open = True

    def end_line(self):
        if self.line_open:
            self.output('')
            self.line_open = False

    def question(self, text):
        self.end_line()
        self.output(text)

def ask(client, request, input_fn, output):
    p, method = request['params'], request['method']
    rid = request['id']
    if input_fn is None: raise InputRequired('Interactive input channel unavailable')
    if method == 'item/tool/requestUserInput':
        answers = {}
        for q in p['questions']:
            labels = [o['label'] for o in q.get('options') or []]
            output(q['question'] + (' [' + ' / '.join(labels) + ']' if labels else ''))
            value = getpass.getpass('Antwort (abort zum Abbrechen): ') if q.get('isSecret') else input_fn('Antwort (abort zum Abbrechen): ')
            if value == 'abort': raise KeyboardInterrupt
            answers[q['id']] = {'answers': [value]}
        client.answer(rid, {'answers': answers})
    elif method.endswith('requestApproval'):
        context = {k:p[k] for k in ('command','cwd','reason','grantRoot') if p.get(k)}
        if method == 'item/fileChange/requestApproval':
            context['changes'] = client.file_changes.get(p['itemId'], [])
        output('Freigabe ' + str(rid) + ': ' + json.dumps(safe_evidence(context), ensure_ascii=False))
        value = input_fn('accept / decline / cancel / abort: ')
        if value == 'abort': raise KeyboardInterrupt
        if value not in ('accept', 'decline', 'cancel'): raise ValueError('Ungültige Antwort')
        client.answer(rid, {'decision': value})
    else:
        output(p['message'] + '\n' + json.dumps(p.get('requestedSchema', {'url': p.get('url')}), ensure_ascii=False))
        value = input_fn('JSON {action: accept/decline/cancel, content: ...} oder abort: ')
        if value == 'abort': raise KeyboardInterrupt
        response = json.loads(value)
        response.setdefault('_meta', None)
        response.setdefault('content', None)
        client.answer(rid, response)

def repair_case(checker, task, case, result, input_fn, output, *, retest=None):
    """Caller invokes only for an explicit repair request, after a failed native test.

    retest(case) returns a fresh native result; Codex completion alone never PASS.
    """
    cfg = checker.cfg() if callable(getattr(checker, 'cfg', None)) else checker.config
    settings = cfg.get('codex_repair', {})
    executable = settings.get('executable') or shutil.which('codex')
    progress = RepairProgress()
    record = {'case_id': case.get('id', case.get('test_id')), 'attempt': uuid.uuid4().hex,
        'status': 'BLOCKED', 'percentage': 0, 'phase': 'package'}
    view = QuietRepairView(case, output)
    def completed(phase):
        progress.complete(phase)
        record['phase'] = phase
        record['percentage'] = progress.percentage
        view.progress(progress.percentage)
    if not executable:
        record['message'] = 'Codex executable unavailable'; return record
    if retest is None:
        record['message'] = 'Native repair retest callback unavailable'; return record
    root = Path(cfg['project'])
    target = root / '.tool-checker' / 'repair' / record['attempt']
    events = []
    client = CodexAppServer(executable, root, log=events.append)
    lock = checker.lock_path()
    owner = 'repair-' + record['attempt']
    locked = False
    def release_lock():
        nonlocal locked
        if locked:
            current = json.loads(lock.read_text(encoding='utf-8'))
            if current.get('run_id') != owner:
                raise RuntimeError('Repair resource lock ownership changed')
            lock.unlink()
            locked = False
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('x', encoding='utf-8') as stream:
            json.dump({'run_id':owner,'task_id':str(task),'scope':'repair','attempt':record['attempt']}, stream)
        locked = True
        protected_json(target / 'package.json', {'case': case, 'result': result, 'task': str(task)})
        completed('package')
        before = subprocess.run(['git', 'diff', '--binary'], cwd=root, capture_output=True, check=True).stdout
        client.initialize()
        client.begin('Explicit repair request for test case ' + str(record['case_id']) +
            '. Read the supplied failure package at ' + str(target / 'package.json') +
            '. Preserve existing unrelated changes. Repair only this confirmed finding. '
            'Request mandatory decisions through structured request_user_input. Do not expose reasoning. '
            'Do not claim PASS; checker performs native retest.', settings.get('model'))
        while client.turn_result is None:
            client.receive()
            if client.state == 'DISCONNECTED': raise ConnectionError('Codex disconnected; no automatic replay')
            if client.pending:
                request = next(iter(client.pending.values()))
                try: ask(client, request, input_fn, view.question)
                except Exception as error:
                    from jsonschema.exceptions import ValidationError
                    if not isinstance(error, (ValueError, ValidationError)): raise
                    view.question('Ungültige Antwort; Frage bleibt offen.')
        if client.pending: raise RuntimeError('Unresolved request at turn completion')
        completed('attempt')
        after = subprocess.run(['git', 'diff', '--binary'], cwd=root, capture_output=True, check=True).stdout
        # No diff payload in general log; evidence only records whether changed.
        record['diff_changed'] = before != after
        protected_json(target / 'diff.json', {'before_sha256': hashlib.sha256(before).hexdigest(),
            'after_sha256': hashlib.sha256(after).hexdigest(), 'changed': before != after})
        completed('diff')
        # Native retest acquires the same existing resource lock itself.
        release_lock()
        view.end_line()
        record['retest'] = retest(case)
        completed('retest')
        record['status'] = record['retest'].get('status', 'BLOCKED')
        record['phase'] = 'persist'
        record['percentage'] = 100
        protected_json(target / 'events.json', events)
        protected_json(target / 'result.json', record)
        completed('persist')
        record['percentage'] = progress.percentage
        record['result_ref'] = str(target / 'result.json')
    except (KeyboardInterrupt, EOFError):
        client.abort(); record['status'] = 'ABORTED'
    except Exception as error:
        record['status'] = 'INPUT_REQUIRED' if isinstance(error, InputRequired) or client.state == 'INPUT_REQUIRED' else 'BLOCKED'
        record['message'] = str(error)
    finally:
        client.close()
        release_lock()
        record['percentage'] = progress.percentage
        view.end_line()
        if record['status'] in ('BLOCKED','ABORTED','INPUT_REQUIRED') and target.exists():
            protected_json(target / ('interrupted-' + uuid.uuid4().hex + '.json'),
                {'record': record, 'events': events})
    return record
