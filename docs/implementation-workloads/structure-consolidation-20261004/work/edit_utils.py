"""Revision-checked, snapshotted edits for this implementation workload."""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
WRITES = {}
REMOVALS = []

def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')

def write(path, content):
    if path.endswith('.py'):
        ast.parse(content)
    WRITES[path] = content

def extract(source, names):
    lines = source.splitlines(keepends=True)
    nodes = [n for n in ast.parse(source).body if getattr(n, 'name', None) in names]
    chunks = []
    for node in nodes:
        start = min([node.lineno, *[d.lineno for d in getattr(node, 'decorator_list', [])]]) - 1
        chunks.append(''.join(lines[start:node.end_lineno]))
    for node in reversed(nodes):
        start = min([node.lineno, *[d.lineno for d in getattr(node, 'decorator_list', [])]]) - 1
        del lines[start:node.end_lineno]
    return '\n\n'.join(chunks) + '\n', ''.join(lines)

def apply(label):
    workload_path = OUT / 'workload.json'
    workload = json.loads(workload_path.read_text(encoding='utf-8'))
    revision = {}
    for path in [*WRITES, *REMOVALS]:
        target = (ROOT / path).resolve()
        assert target.is_relative_to(ROOT)
        revision[path] = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if target.exists():
            before = OUT / 'before' / label / path
            before.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, before)
    workload['revision_before'] = revision
    workload['files_changed'] = sorted(set(workload['files_changed']) | set(revision))
    workload_path.write_text(json.dumps(workload, indent=2), encoding='utf-8')
    guard = subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py', 'before-apply', '--workload', str(workload_path)], capture_output=True, text=True)
    (OUT / (label + '-guard.json')).write_text(guard.stdout, encoding='utf-8')
    if guard.returncode:
        raise RuntimeError(guard.stdout + guard.stderr)
    for path, content in WRITES.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
    for path in REMOVALS:
        (ROOT / path).unlink()
    (OUT / (label + '-files.json')).write_text(json.dumps({'written':list(WRITES), 'removed':REMOVALS}, indent=2), encoding='utf-8')
    print(label, len(WRITES), 'writes,', len(REMOVALS), 'removals')
