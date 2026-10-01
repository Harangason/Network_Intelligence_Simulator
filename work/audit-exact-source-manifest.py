"""Emit per-file hashes for the exact write-build-info.py source manifest."""
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
excluded = {'.venv', 'node_modules', 'test-output', 'tests', '__pycache__', 'generated'}
paths = set()
for base in ('backend', 'frontend/src', 'frontend/scripts'):
    directory = root / base
    if not directory.exists():
        continue
    for current, dirs, files in os.walk(directory):
        dirs[:] = [item for item in dirs if item not in excluded
                   and not (base == 'backend' and Path(current) == directory and item == 'runtime')]
        for name in files:
            path = Path(current) / name
            if base == 'backend' and path.suffix != '.py':
                continue
            paths.add(path)
paths.update((root / 'config').glob('*.json'))
paths.update((root / 'frontend').glob('*config*'))
paths.update(root / name for name in (
    'Dockerfile', '.dockerignore', 'generate_realistic_communication_tool.py',
    'scripts/write-build-info.py', 'scripts/verify-runtime-lock.py',
    'scripts/release_storage.py', 'backend/requirements.txt',
    'backend/requirements.lock', 'backend/pyproject.toml', 'backend/uv.lock',
    'frontend/package.json', 'frontend/package-lock.json',
))
hashes = {}
for path in sorted(paths):
    if not path.is_file() or excluded.intersection(path.relative_to(root).parts):
        continue
    if path.relative_to(root).parts[:2] == ('backend', 'runtime'):
        continue
    if path.suffix in {'.pyc', '.tsbuildinfo'}:
        continue
    hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
source = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
print(json.dumps({'source_sha256': source, 'files': hashes}, sort_keys=True, separators=(',', ':')))
