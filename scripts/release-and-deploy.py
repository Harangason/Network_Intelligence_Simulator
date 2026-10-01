"""Reuse a verified candidate or run the gate, then deploy and verify it."""
from __future__ import annotations

import argparse
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
import uuid

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / 'backend/test-output/release-gates'


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
                    and receipt.get('status') in {'PASS', 'FAIL'}
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
    parser.add_argument('--no-reuse', action='store_true', help='Run a fresh gate even when this source already has a PASS.')
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
        candidate = None if args.no_reuse else reusable_image(receipt_paths(), source, commit)
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
