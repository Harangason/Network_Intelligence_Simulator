"""Diagnostic adapter: existing Playwright cases on source, never a release PASS.

Invoke only through scripts/run-isolated-tests.py. It owns the database lifecycle;
this adapter owns only its HTTP/frontend processes and disposable runtime.
"""
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def test_existing_browser_cases_on_isolated_source(tmp_path):
    database = os.environ.get('ENGINEERING_TEST_DATABASE_URL', '')
    assert database and database == os.environ.get('DATABASE_URL')
    assert re.fullmatch(r'/nis_test_[a-z0-9_]+', urlsplit(database).path)
    assert urlsplit(database).hostname == '127.0.0.1'
    environment = {**os.environ, 'NIS_DATA_DIR': str(tmp_path / 'data'),
        'NIS_RUNTIME_DIR': str(tmp_path / 'runtime'), 'SIMULATOR_RUNTIME_ROOT': str(tmp_path / 'runtime'),
        'NETWORKIS_ALLOW_NON_CANONICAL_ROOT': '1', 'NUMERIC_ACCELERATOR': 'cpu',
        'LOCAL_AI_BASE_URL': 'http://127.0.0.1:1/v1', 'CLOUD_ESCALATION': 'never'}
    os.environ.update(environment)
    sys.path.insert(0, str(ROOT))
    from backend.nis.app import create_app
    from backend.nis.app.__main__ import ExclusiveThreadedWSGIServer
    server = ExclusiveThreadedWSGIServer('127.0.0.1', 0, create_app(testing=True))
    assert server.server_port not in (13500, 15050)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    assert port not in (13500, 15050, server.server_port)
    node = shutil.which('node')
    assert node
    environment.update(SIMULATOR_BACKEND_API_URL=f'http://127.0.0.1:{server.server_port}/api',
        NETWORKIS_NEXT_DIST_DIR='.next-safety-regression', NIS_E2E_ISOLATED='1',
        NIS_E2E_URL=f'http://127.0.0.1:{port}', NIS_E2E_OUTPUT=str(HERE / 'isolated-browser'),
        NIS_E2E_REPORT=str(HERE / 'isolated-browser.json'))
    frontend = ROOT / 'frontend'
    with (HERE / 'isolated-frontend.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([node, 'node_modules/next/dist/bin/next', 'dev', '--webpack', '-p', str(port)], cwd=frontend, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                assert process.poll() is None, 'Isolated frontend stopped; inspect its log.'
                try:
                    with urlopen(environment['NIS_E2E_URL'] + '/api/health', timeout=2) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.5)
            else:
                raise AssertionError('Isolated HTTP/frontend readiness timed out.')
            with (HERE / 'isolated-browser.log').open('w', encoding='utf-8') as browser_log:
                result = subprocess.run([node, 'node_modules/playwright/cli.js', 'test',
                    'e2e/safety-assurance.spec.ts', '--grep', '@safety-assurance'],
                    cwd=frontend, env=environment, stdout=browser_log, stderr=subprocess.STDOUT, timeout=300)
            assert result.returncode == 0, 'Existing browser cases failed; inspect isolated-browser.log.'
        finally:
            if process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
