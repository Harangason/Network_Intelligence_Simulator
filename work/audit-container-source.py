"""Read-only inventory of application files inside historical NIS images."""
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/app')
patterns = {
    'backend': '*',
    'frontend/src': '*',
    'frontend/scripts': '*',
    'config': '*',
    'scripts': '*',
}
excluded = {'.venv', 'node_modules', 'runtime', 'test-output', '__pycache__', '.next', 'tests', 'e2e'}
items = {}
for base in patterns:
    directory = root / base
    if not directory.exists():
        continue
    for current, dirs, files in os.walk(directory):
        dirs[:] = [name for name in dirs if name not in excluded]
        for name in files:
            path = Path(current) / name
            if path.suffix in {'.pyc', '.tsbuildinfo'}:
                continue
            relative = path.relative_to(root).as_posix()
            try:
                items[relative] = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            except (OSError, PermissionError):
                if root == Path('/app'):
                    raise
for name in ('Dockerfile', '.dockerignore', 'generate_realistic_communication_tool.py'):
    path = root / name
    if path.is_file():
        items[name] = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
print(json.dumps(items, sort_keys=True, separators=(',', ':')))
