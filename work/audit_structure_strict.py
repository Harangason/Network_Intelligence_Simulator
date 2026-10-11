"""Inventory actual ownership and empty source packages without importing code."""
import ast
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/structure-consolidation-20261004'
OUT.mkdir(parents=True, exist_ok=True)
SKIP = {'__pycache__', '.venv', 'node_modules', '.next', '.git', 'runtime', 'test-output', 'build'}
empty, shells, files = [], [], []
for base in ['backend/nis', 'frontend/src', 'scripts']:
    for folder, dirs, names in os.walk(ROOT / base):
        dirs[:] = [name for name in dirs if name not in SKIP]
        names = [name for name in names if not name.endswith(('.pyc', '.pyo'))]
        relative = Path(folder).relative_to(ROOT).as_posix()
        if not names and not dirs:
            empty.append(relative)
        elif names == ['__init__.py'] and not dirs:
            shells.append({'path': relative, 'content': (Path(folder) / '__init__.py').read_text(encoding='utf-8-sig')})
        files += [(Path(folder) / name).relative_to(ROOT).as_posix() for name in names]

symbols = {}
for relative in ['backend/nis/simulation/communication_generator.py', 'backend/nis/simulation/communication_simulator.py',
                 'backend/nis/engineering/capacity/dimensioning.py', 'backend/nis/engineering/capacity/service.py']:
    source = (ROOT / relative).read_text(encoding='utf-8-sig')
    nodes = ast.parse(source).body
    symbols[relative] = [{'name': n.name, 'line': n.lineno, 'lines': n.end_lineno-n.lineno+1,
                         'references': sorted({v.id for v in ast.walk(n) if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load)})}
                        for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
result = {'physically_empty': empty, 'init_only_leaf_packages': shells, 'symbols': symbols}
(OUT / 'ownership-before.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'physically_empty':empty,'init_only_leaf_packages':shells}, indent=2))
for relative, records in symbols.items():
    print(relative)
    print([(row['name'], row['line'], row['lines']) for row in records])
