"""Reuse a verified candidate or run the gate, then deploy and verify it."""
from __future__ import annotations

import sys as _entry_sys
from pathlib import Path as _EntryPath
_entry_sys.path.insert(0, str(_EntryPath(__file__).resolve().parents[1]))

import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = ROOT / 'backend/test-output/release-gates'


@contextmanager
def gate_lock(root):
    """One gate per checkout, even for direct calls and different output paths.

    The OS releases the lock after a crash; an old lock file never owns a lease.
    """
    path = root / 'backend/test-output/release-gates/.gate.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Another release/preparation gate holds the checkout lock; no new build was started.') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def prepared_stack(docker, paths, source, commit, *, prepare, keep, ai_url,
                   image=None, development_base=None, model_environment=None):
    """Reuse one healthy exact stack; never accumulate retained environments.

    Stopped and unclassified containers count too: deletion needs a separate
    audited retirement. Normal transient full gates still clean up in finally.
    """
    paths = list(paths)
    if not (prepare or keep):
        # A previous cleanup failure must not be multiplied by another full gate.
        failed = set()
        for path in paths:
            try:
                receipt = json.loads(path.read_text(encoding='utf-8-sig'))
                if isinstance(receipt, dict) and receipt.get('cleanup_incomplete') is True:
                    failed.update(value for value in receipt.get('containers', {}).values()
                                  if isinstance(value, str) and value.startswith('nis-e2e-'))
            except (OSError, ValueError, AttributeError):
                continue
        if failed:
            for command in (['ps', '-a', '--format', '{{.Names}}'],
                            ['volume', 'ls', '--format', '{{.Name}}'],
                            ['network', 'ls', '--format', '{{.Name}}']):
                actual = set(subprocess.check_output([docker, *command], text=True).split())
                if failed & actual:
                    raise RuntimeError('A previous test-stack cleanup is incomplete; reconcile its exact resources before another gate. No image was built.')
        return None
    ids = subprocess.check_output(
        [docker, 'ps', '-aq', '--filter', 'name=nis-e2e-'], text=True).split()
    if not ids:
        # Networks/volumes left by an interrupted prepare also need reconciliation.
        for kind, name in (('volume', 'nis-e2e-runtime-'), ('network', 'nis-e2e-network-')):
            names = subprocess.check_output(
                [docker, kind, 'ls', '--format', '{{.Name}}'], text=True).split()
            if any(item.startswith(name) for item in names):
                raise RuntimeError('Retained test resources exist without containers. Archive/retire their exact receipt resources before preparing another stack.')
        return None
    containers = json.loads(subprocess.check_output([docker, 'inspect', *ids], text=True))
    actual_names = {row['Name'].lstrip('/') for row in containers}
    for path in paths:
        try:
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(receipt, dict):
                continue
            names = receipt.get('containers', {})
            if not isinstance(names, dict):
                continue
            expected = {names.get('app'), names.get('db')}
            if (prepare and receipt.get('status') == 'PREPARED'
                    and receipt.get('initial_source_sha256') == source
                    and receipt.get('initial_commit_id') == commit
                    and receipt.get('development_only') is not True
                    and development_base is None
                    and (image is None or image in {receipt.get('image_id'), receipt.get('image_tag')})
                    and receipt.get('stack_retirement') is None
                    and None not in expected and actual_names == expected):
                app = next(row for row in containers if row['Name'].lstrip('/') == names['app'])
                db = next(row for row in containers if row['Name'].lstrip('/') == names['db'])
                if (app['Image'] != receipt.get('image_id')
                        or any(row['State']['Status'] != 'running' for row in (app, db))
                        or any((row['Config'].get('Labels') or {}).get('networkis.test') != 'disposable' for row in (app, db))
                        or f'LOCAL_AI_BASE_URL={ai_url}' not in app['Config'].get('Env', [])):
                    continue
                env = dict(item.split('=', 1) for item in app['Config'].get('Env', []) if '=' in item)
                if any(env.get(name) != value for name, value in (model_environment or {}).items()):
                    continue
                database = urlsplit(env.get('DATABASE_URL', ''))
                if (database.hostname != 'test-db' or database.username != 'nis_test'
                        or database.port != 5432 or database.path != '/nis_test_e2e'
                        or not names.get('network') or not names.get('runtime')
                        or any(names['network'] not in row['NetworkSettings']['Networks'] for row in (app, db))
                        or not any(m.get('Name') == names['runtime'] and m['Destination'] == '/app/var/data'
                                   for m in app.get('Mounts', []))):
                    continue
                base = receipt['base_url']
                # The URL must be the actual isolated loopback publication.
                ports = app['NetworkSettings']['Ports']['13500/tcp']
                if not any(p['HostIp'] == '127.0.0.1' and base == 'http://127.0.0.1:' + p['HostPort'] for p in ports):
                    continue
                with urlopen(base + '/api/ready', timeout=3) as response:
                    if response.status != 200:
                        continue
                with urlopen(base + '/api/build-info', timeout=3) as response:
                    live = json.load(response)
                if live.get('source_sha256') == source and live.get('commit_id') == commit:
                    return path, receipt
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            continue
    raise RuntimeError('A retained test stack already exists (' + ', '.join(sorted(actual_names))
                       + '). Reuse/resume it or archive and retire its exact receipt resources before preparing another; no image was built.')


def receipt_paths():
    for parent in (RECEIPTS, ROOT / 'work'):
        if parent.exists():
            yield from parent.rglob('receipt.json')


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matching_receipt(paths, source: str, commit: str, verification: str):
    storage = load_module('release_storage', ROOT / 'scripts/release_storage.py')
    existing = [path for path in paths if path.is_file()]
    for path in sorted(existing, key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if (storage.complete_pass(receipt)
                and receipt.get('initial_source_sha256') == source
                and receipt.get('initial_commit_id') == commit
                and receipt.get('verification_sha256') == verification
                and receipt.get('release', {}).get('commit_id') == commit
                and isinstance(receipt.get('image_id'), str)):
            return path, receipt
    return None


def active_gate(paths, source: str, *, now=None):
    current = time.time() if now is None else now
    for path in paths:
        try:
            if current - path.stat().st_mtime > 2 * 60 * 60:
                continue
            receipt = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if receipt.get('status') == 'RUNNING' and receipt.get('initial_source_sha256') == source:
            pid = receipt.get('gate_pid')
            if type(pid) is int and pid > 0:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                except PermissionError:
                    pass
            return path
    return None


def reusable_image(paths, source: str, commit: str):
    candidates = []
    for path in paths:
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            image = receipt.get('image_id')
            if (receipt.get('initial_source_sha256') == source
                    and receipt.get('initial_commit_id') == commit
                    and receipt.get('status') in {'PASS', 'FAIL', 'PREPARED'}
                    and receipt.get('stack_retirement') is None
                    and receipt.get('development_only') is not True
                    and isinstance(image, str)
                    and re.fullmatch(r'sha256:[0-9a-f]{64}', image)):
                candidates.append((path.stat().st_mtime, image))
        except (OSError, ValueError):
            continue
    if not candidates:
        return None
    isolation = load_module('isolation', ROOT / 'scripts/run-isolated-tests.py')
    docker = isolation.docker_executable()
    for _, image in sorted(candidates, reverse=True):
        found = subprocess.run([docker, 'image', 'inspect', image, '--format', '{{.Id}}'],
                               capture_output=True, text=True)
        if found.returncode == 0 and found.stdout.strip() == image:
            return image
    return None


def current_identity():
    build = load_module('write_build_info', ROOT / 'scripts/write-build-info.py')
    gate = load_module('run_release_gate', ROOT / 'scripts/run-release-gate.py')
    manifest = build.build_manifest()
    return manifest['source_sha256'], manifest['commit_id'], gate.verification_manifest()


def verify_live(receipt, *, base_url='http://127.0.0.1:13500'):
    isolation = load_module('isolation', ROOT / 'scripts/run-isolated-tests.py')
    docker = isolation.docker_executable()
    expected = receipt['image_id']
    running = subprocess.check_output(
        [docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
    if running != expected:
        raise RuntimeError(f'Running image {running} differs from tested image {expected}')
    for attempt in range(30):
        try:
            with urlopen(base_url + '/api/ready', timeout=5) as response:
                ready = json.load(response)
            with urlopen(base_url + '/api/build-info', timeout=5) as response:
                live = json.load(response)
            if ready.get('status') == 'ready' and live.get('source_sha256') == receipt['release']['source_sha256']:
                return {'image_id': running, 'source_sha256': live['source_sha256'], 'ready': ready}
        except (OSError, ValueError):
            pass
        if attempt < 29:
            time.sleep(2)
    raise RuntimeError('Production readiness or source identity did not match the PASS receipt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, help='Deploy this existing PASS receipt; do not build an image.')
    parser.add_argument('--no-reuse', action='store_true', help='Run a fresh full gate; an existing exact-source image is still reused.')
    args = parser.parse_args()
    if not os.environ.get('NIS_TEST_DOCKER') and not shutil.which('docker'):
        config = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))
        os.environ['NIS_TEST_DOCKER'] = config['paths']['docker_cli']
    source, commit, verification = current_identity()
    if not commit:
        parser.error('A Git base commit is required for a release.')
    selected = None
    if args.receipt:
        selected = matching_receipt([args.receipt], source, commit, verification)
        if selected is None:
            parser.error('The specified receipt is not a complete PASS for the current source and tests.')
    elif not args.no_reuse:
        selected = matching_receipt(receipt_paths(), source, commit, verification)
    if selected is None:
        other = None if args.no_reuse else active_gate(receipt_paths(), source)
        if other:
            raise SystemExit(f'Another release gate for this source is running: {other}')
        candidate = reusable_image(receipt_paths(), source, commit)
        output = RECEIPTS / ('delivery-' + uuid.uuid4().hex[:12])
        command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--output', str(output)]
        if candidate:
            command += ['--image', candidate]
        subprocess.run(command, cwd=ROOT, check=True)
        selected = matching_receipt(output.rglob('receipt.json'), source, commit, verification)
        if selected is None:
            raise RuntimeError('Gate finished without a complete PASS for the current source and tests.')
    if current_identity() != (source, commit, verification):
        raise RuntimeError('Source or verification inputs changed during delivery; run the gate again.')
    path, receipt = selected
    # The Windows launcher preserves the configured GPU, AI and runtime settings.
    command = (["powershell", "-NoProfile", "-File", str(ROOT / 'start-networkis.ps1'),
                "-ReleaseReceipt", str(path)] if os.name == 'nt' else
               [sys.executable, str(ROOT / 'scripts/deploy-verified-release.py'), str(path)])
    subprocess.run(command, cwd=ROOT, check=True)
    live = verify_live(receipt)
    print(json.dumps({'status': 'DEPLOYED', 'receipt': str(path), **live}), flush=True)


if __name__ == '__main__':
    main()
