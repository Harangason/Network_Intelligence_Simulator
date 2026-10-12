"""Targeted real-browser verification, invoked only by run-isolated-tests.py."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def ready(url, process, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, f'Service exited before readiness: {url}'
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(.5)
    raise AssertionError(f'Service readiness timeout: {url}')

def test_real_multi_window_browser(tmp_path):
    dsn = os.environ.get('ENGINEERING_TEST_DATABASE_URL', '')
    assert '@127.0.0.1:' in dsn and '/nis_test_' in dsn
    assert os.environ.get('DATABASE_URL') == dsn
    backend_port, frontend_port = port(), port()
    base = f'http://127.0.0.1:{frontend_port}'
    env = dict(os.environ, SIMULATOR_BACKEND_API_URL=f'http://127.0.0.1:{backend_port}/api',
               SIMULATOR_ENGINEERING_API_URL=f'http://127.0.0.1:{backend_port}/api/engineering',
               NIS_E2E_ISOLATED='1', NIS_E2E_URL=base, FRONTEND_ORIGIN=base,
               NIS_E2E_OUTPUT=str(HERE/'browser-results'), NIS_E2E_REPORT=str(HERE/'browser-report.json'),
               NIS_RUNTIME_DIR=str(tmp_path/'runtime'), NIS_DATA_DIR=str(tmp_path/'data'),
               NIS_ARTIFACTS_DIR=str(tmp_path/'artifacts'), NUMERIC_ACCELERATOR='cpu')
    processes = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    node = r'C:/Program Files/nodejs/node.exe'
    try:
        with (HERE/'targeted-backend.log').open('w') as backend_log, (HERE/'targeted-frontend.log').open('w') as frontend_log, (HERE/'targeted-browser.log').open('w') as browser_log:
            backend = subprocess.Popen([sys.executable, '-m', 'flask', '--app', 'backend.nis.app:create_app', 'run', '--host', '127.0.0.1', '--port', str(backend_port)], cwd=ROOT, env=env, stdout=backend_log, stderr=subprocess.STDOUT, creationflags=flags)
            processes.append(backend)
            ready(f'http://127.0.0.1:{backend_port}/api/health', backend)
            build = subprocess.run([node, str(ROOT/'frontend/node_modules/next/dist/bin/next'), 'build', '--webpack'], cwd=ROOT/'frontend', env=env, stdout=frontend_log, stderr=subprocess.STDOUT, creationflags=flags, timeout=600)
            assert build.returncode == 0, 'Production frontend build failed; see targeted-frontend.log.'
            frontend = subprocess.Popen([node, str(ROOT/'frontend/node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', str(frontend_port)], cwd=ROOT/'frontend', env=env, stdout=frontend_log, stderr=subprocess.STDOUT, creationflags=flags)
            processes.append(frontend)
            ready(base+'/trace-analysis?project=nis-e2e-readiness', frontend)
            print(f'Isolated actual browser stack ready at {base}', flush=True)
            result = subprocess.run([node, 'node_modules/playwright/cli.js', 'test', 'analysis-workspace.spec.ts', 'trace-session.spec.ts'], cwd=ROOT/'frontend', env=env, stdout=browser_log, stderr=subprocess.STDOUT, creationflags=flags, timeout=1800)
            assert result.returncode == 0, (HERE/'targeted-browser.log').read_text(encoding='utf-8')[-12000:]
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
                else:
                    process.terminate()
                process.wait(timeout=30)
