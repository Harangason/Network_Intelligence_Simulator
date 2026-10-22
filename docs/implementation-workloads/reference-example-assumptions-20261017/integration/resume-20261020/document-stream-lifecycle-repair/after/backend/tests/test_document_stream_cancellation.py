"""Transient document ownership; fake inference transport, never a native/E2E PASS."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import threading

from flask import Flask
import httpx
import pytest

from backend.nis.agent.api.tool_contract import ToolResult
from backend.nis.agent.tools import api
from backend.nis.agent.tools.cancellation import (
    RunCancellation, active_document_request, bind_document_request, request_cancel,
)
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner


def test_production_waitress_observes_document_disconnect(monkeypatch):
    """Exercise the real production entry point, not Flask's iterator.close()."""
    import socket
    from types import SimpleNamespace
    from urllib.request import Request, urlopen
    from waitress import create_server
    import waitress
    from backend.nis.app import __main__ as entry

    started, interrupted, finished, listening = (threading.Event() for _ in range(4))
    controls, servers, exits = [], [], []
    def execute(*args):
        controls.append(active_document_request.get())
        async def inference():
            bind_document_request()
            started.set()
            try:
                await asyncio.sleep(120)
                pytest.fail('Abandoned document must not reach a later stage')
            except asyncio.CancelledError:
                interrupted.set()
                raise
        try:
            asyncio.run(inference())
        finally:
            finished.set()

    app = Flask(__name__)
    app.post('/document')(lambda: api._local_document_response('interpret_project_document', None, 'initial'))
    def serve(application, **kwargs):
        server = create_server(application, **kwargs)
        servers.append(server)
        listening.set()
        server.run()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    monkeypatch.setenv('FLASK_HOST', '127.0.0.1')
    monkeypatch.setenv('FLASK_PORT', str(port))
    monkeypatch.setenv('FLASK_DEBUG', '0')
    monkeypatch.setattr(entry, 'create_app', lambda: app)
    monkeypatch.setattr(entry, 'runtime_settings', lambda: SimpleNamespace(api_threads=2, simulation_workers=1))
    monkeypatch.setattr(waitress, 'serve', serve)
    monkeypatch.setattr(api, 'execute', execute)
    monkeypatch.setattr(api, '_slots', threading.BoundedSemaphore(1))
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(api, '_executor', executor)
        server_thread = threading.Thread(target=lambda: exits.append(entry.main()), daemon=True)
        server_thread.start()
        try:
            assert listening.wait(5)
            response = urlopen(Request(f'http://127.0.0.1:{port}/document', data=b'{}', headers={
                'Content-Type': 'application/json', 'Accept': 'application/x-ndjson', 'X-Project-ID': 'wire-cancel'}), timeout=10)
            assert json.loads(response.readline())['type'] == 'PROGRESS'
            assert started.wait(5)
            response.close()
            assert interrupted.wait(20), 'Production HTTP server must observe the closed document stream'
            assert finished.wait(2)
        finally:
            for control in controls:
                request_cancel(*control.key)
            for server in servers:
                server.close()
            server_thread.join(3)
        assert exits == [0]


@pytest.mark.parametrize('tool', ['interpret_project_document', 'generate_reference_design'])
def test_closed_document_stream_interrupts_await_and_releases_slot(monkeypatch, tool):
    started, interrupted, finished = threading.Event(), threading.Event(), threading.Event()
    later_calls = []
    controls = []
    def execute(authority, name, permission, arguments, handler):
        controls.append(active_document_request.get())
        async def inference():
            bind_document_request()
            started.set()
            try:
                await asyncio.sleep(60)
                later_calls.append('next native section')
            except asyncio.CancelledError:
                interrupted.set()
                raise
        try:
            asyncio.run(inference())
            return ToolResult(data={'unexpected': True})
        finally:
            finished.set()
    monkeypatch.setattr(api, 'execute', execute)
    monkeypatch.setattr(api, '_slots', threading.BoundedSemaphore(1))
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(api, '_executor', executor)
        app = Flask(__name__)
        app.post('/document')(lambda: api._local_document_response(tool, None, 'initial'))
        response = app.test_client().post('/document', json={},
            headers={'Accept': 'application/x-ndjson', 'X-Project-ID': 'cancel-document'}, buffered=False)
        assert started.wait(3)
        response.close()
        assert interrupted.wait(3) and finished.wait(3)
    assert later_calls == []
    assert controls[0].cancelled.is_set()
    assert api._slots.acquire(blocking=False)
    api._slots.release()
    assert not request_cancel(*controls[0].key), 'Terminal request must release its registry entry'


def test_document_closed_before_worker_binds_never_starts_inference(monkeypatch):
    queued = []
    class QueuedExecutor:
        def submit(self, worker):
            queued.append(worker)
    monkeypatch.setattr(api, '_executor', QueuedExecutor())
    monkeypatch.setattr(api, '_slots', threading.BoundedSemaphore(1))
    monkeypatch.setattr(api, 'execute', lambda *args: pytest.fail('Canceled queued work must not execute'))
    app = Flask(__name__)
    with app.test_request_context('/document', json={}, headers={'Accept': 'application/x-ndjson'}):
        response = api._local_document_response('interpret_project_document', None, 'initial')
        response.close()  # No first iteration: call_on_close must also own cancellation.
    queued.pop()()
    assert api._slots.acquire(blocking=False)
    api._slots.release()


def test_normal_document_completion_is_not_canceled_by_response_cleanup(monkeypatch):
    controls = []
    def execute(*args):
        controls.append(active_document_request.get())
        return ToolResult(data={'complete': True})
    monkeypatch.setattr(api, 'execute', execute)
    monkeypatch.setattr(api, '_slots', threading.BoundedSemaphore(1))
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(api, '_executor', executor)
        app = Flask(__name__)
        app.post('/document')(lambda: api._local_document_response('interpret_project_document', None, 'initial'))
        response = app.test_client().post('/document', json={},
            headers={'Accept': 'application/x-ndjson'}, buffered=True)
        events = [json.loads(line) for line in response.text.splitlines()]
        response.close()
    assert events[-1]['result']['data'] == {'complete': True}
    assert not controls[0].cancelled.is_set()
    assert api._slots.acquire(blocking=False)
    api._slots.release()


def test_document_submission_failure_does_not_leak_capacity(monkeypatch):
    class FailedExecutor:
        def submit(self, worker):
            raise RuntimeError('executor unavailable')
    monkeypatch.setattr(api, '_executor', FailedExecutor())
    monkeypatch.setattr(api, '_slots', threading.BoundedSemaphore(1))
    with Flask(__name__).test_request_context('/document', json={}, headers={'Accept': 'application/x-ndjson'}):
        with pytest.raises(RuntimeError, match='executor unavailable'):
            api._local_document_response('interpret_project_document', None, 'initial')
    assert api._slots.acquire(blocking=False)
    api._slots.release()


@pytest.mark.parametrize('stage', ['document', 'reference'])
def test_real_reasoner_binds_cancellation_to_pending_http_transport(stage):
    async def run():
        entered = asyncio.Event()
        calls = []
        async def transport(request):
            calls.append(str(request.url))
            entered.set()
            await asyncio.Event().wait()
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        control = RunCancellation('document-transport-' + stage, 'request')
        async def inference():
            token = active_document_request.set(control)
            try:
                if stage == 'document':
                    await reasoner.interpret_document('Controller: PDC\nSensor: Temperatur', 'source.txt')
                else:
                    await reasoner.plan_reference_design({})  # Interrupted at /show, before design use.
            finally:
                active_document_request.reset(token)
        task = asyncio.create_task(inference())
        try:
            await asyncio.wait_for(entered.wait(), timeout=10)
            assert request_cancel(*control.key)
            with pytest.raises(asyncio.CancelledError):
                await task
            assert len(calls) == 1 and calls[0].endswith('/api/show')
        finally:
            control.close()
            await reasoner.client.aclose()
    asyncio.run(run())


def test_document_request_cancellation_does_not_cancel_another_project():
    async def run():
        first, second = RunCancellation('project-a', 'document'), RunCancellation('project-b', 'document')
        started = asyncio.Event()
        release = asyncio.Event()
        async def one(control):
            token = active_document_request.set(control)
            try:
                bind_document_request()
                started.set()
                await release.wait()
                return 'completed'
            finally:
                active_document_request.reset(token)
        a, b = asyncio.create_task(one(first)), asyncio.create_task(one(second))
        try:
            await started.wait()
            await asyncio.sleep(0)
            assert request_cancel(*first.key)
            with pytest.raises(asyncio.CancelledError):
                await a
            assert not second.cancelled.is_set() and not b.done()
            release.set()
            assert await b == 'completed'
        finally:
            first.close(); second.close()
    asyncio.run(run())
