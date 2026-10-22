"""Bounded real HTTP/Waitress reproduction with fake inference and no SQL."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path.cwd()))

from flask import Flask
from waitress import create_server
from backend.nis.agent.api.tool_contract import ToolResult
from backend.nis.agent.tools import api
from backend.nis.agent.tools.cancellation import active_document_request, bind_document_request, request_cancel

OUT = Path(__file__).resolve().parent / 'waitress-wire-reproduction'
OUT.mkdir(exist_ok=False)
originals = api.execute, api._slots, api._executor
results = []
for lookahead in (0, 1):
    started, interrupted, done = threading.Event(), threading.Event(), threading.Event()
    controls, environment = [], []
    def execute(*args):
        controls.append(active_document_request.get())
        async def infer():
            bind_document_request()
            started.set()
            try:
                await asyncio.sleep(120)
                raise AssertionError('No next stage may run')
            except asyncio.CancelledError:
                interrupted.set()
                raise
        try:
            asyncio.run(infer())
            return ToolResult(data={'unexpected': True})
        finally:
            done.set()
    app = Flask(__name__)
    @app.post('/document')
    def route():
        from flask import request
        environment.append('waitress.client_disconnected' in request.environ)
        return api._local_document_response('interpret_project_document', None, 'initial')
    executor = ThreadPoolExecutor(max_workers=1)
    api.execute, api._slots, api._executor = execute, threading.BoundedSemaphore(1), executor
    server = create_server(app, host='127.0.0.1', port=0, threads=2, channel_request_lookahead=lookahead)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        response = urlopen(Request(f'http://127.0.0.1:{server.effective_port}/document', data=b'{}', headers={'Content-Type': 'application/json', 'Accept': 'application/x-ndjson', 'X-Project-ID': 'wire-diagnostic'}), timeout=10)
        assert json.loads(response.readline())['type'] == 'PROGRESS'
        assert started.wait(5)
        began = time.monotonic()
        response.close()
        observed = interrupted.wait(36)
        record = {'lookahead': lookahead, 'waitress_disconnect_callback_available': environment, 'worker_interrupted': observed, 'seconds_after_client_close': time.monotonic() - began}
        results.append(record)
        (OUT / 'result.json').write_text(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__, 'results': results}, indent=2), encoding='utf8')
        print(json.dumps(record), flush=True)
    finally:
        for control in controls:
            request_cancel(*control.key)
        done.wait(5)
        server.close()
        executor.shutdown(wait=True)
        api.execute, api._slots, api._executor = originals
