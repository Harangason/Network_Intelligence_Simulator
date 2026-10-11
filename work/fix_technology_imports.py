"""Resolve moved child imports explicitly, retaining the original bound names."""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
plan = json.loads((OUT / 'technology-migration-plan.json').read_text())
children = {Path(s).stem: t for s, t in plan['mappings'].items()
            if s.startswith('backend/communication/technologies/')
            and len(Path(s).parts) == 4 and s.endswith('.py') and Path(s).stem != '__init__'}
candidates = set(plan['writes']) | {r['path'] for r in json.loads((OUT / 'inventory-before.json').read_text())['files']}
writes = {}
for relative in sorted(candidates):
    path = ROOT / relative
    if path.suffix != '.py' or not path.is_file():
        continue
    text = path.read_text(encoding='utf-8-sig')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    lines = text.splitlines(keepends=True)
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != 'backend.nis.communication':
            continue
        if not any(a.name in children for a in node.names):
            continue
        pieces = []
        for alias in node.names:
            if alias.name in children:
                target = '.'.join(Path(children[alias.name]).with_suffix('').parts)
                parent, name = target.rsplit('.', 1)
                pieces.append(f'from {parent} import {name} as {alias.asname or alias.name}')
            else:
                pieces.append('from backend.nis.communication import ' + alias.name +
                              (' as ' + alias.asname if alias.asname else ''))
        start = sum(len(x) for x in lines[:node.lineno - 1]) + node.col_offset
        end = sum(len(x) for x in lines[:node.end_lineno - 1]) + node.end_col_offset
        edits.append((start, end, ('\n' + ' ' * node.col_offset).join(pieces)))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    if edits:
        compile(text, relative, 'exec')
        writes[relative] = text
subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), *writes], check=True)
for relative, text in writes.items():
    (ROOT / relative).write_text(text, encoding='utf-8')
print(json.dumps({'corrected_import_consumers': list(writes)}))
