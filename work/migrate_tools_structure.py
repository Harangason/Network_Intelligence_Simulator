"""Stage tool owners by responsibility; retain forwarding entrypoints."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
writes = {}
moves = {}
for source in sorted((ROOT / 'scripts').glob('*.py')):
    name = source.name
    if name in {'write-build-info.py', 'verify-runtime-lock.py'}:
        group = 'build'
    elif name in {'release_storage.py', 'release-and-deploy.py', 'run-release-gate.py', 'deploy-verified-release.py'}:
        group = 'release'
    elif name.startswith(('repair', 'reconcile', 'normalize', 'apply_', 'prepare_', 'resume-')) or name == 'manage-technology-license.py':
        group = 'maintenance'
    else:
        group = 'verification'
    relative = source.relative_to(ROOT).as_posix()
    target = f'scripts/{group}/{name}'
    text = source.read_text(encoding='utf-8-sig')
    text = re.sub(r'(Path\(__file__\)\.resolve\(\)\.parents)\[1\]', r'\1[2]', text)
    # Direct canonical execution retains sibling compatibility imports too.
    import ast
    tree = ast.parse(text)
    insert = max([n.end_lineno for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == '__future__']
                 or ([tree.body[0].end_lineno] if tree.body and isinstance(tree.body[0], ast.Expr)
                     and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str) else [0]))
    lines = text.splitlines(keepends=True)
    lines.insert(insert, '\nimport sys as _entry_sys\nfrom pathlib import Path as _EntryPath\n'
                        '_entry_sys.path.insert(0, str(_EntryPath(__file__).resolve().parents[1]))\n')
    writes[target] = ''.join(lines)
    writes[relative] = ('"""Compatibility entrypoint; implementation is in the responsibility folder."""\n'
                        'from pathlib import Path as _CompatPath\n'
                        f'_compat_target = _CompatPath(__file__).parent / {group!r} / {name!r}\n'
                        '__file__ = str(_compat_target)\n'
                        'exec(compile(_compat_target.read_text(encoding="utf-8"), __file__, "exec"), globals(), globals())\n')
    moves[relative] = target
out = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003/tools-migration-plan.json'
out.write_text(json.dumps({'moves': moves, 'writes': writes}, indent=2), encoding='utf-8')
subprocess.run([sys.executable, str(ROOT/'work/structure_guard.py'), '--plan', str(out)], check=True)
for relative, content in writes.items():
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
print(json.dumps({'tools_moved': len(moves)}))
