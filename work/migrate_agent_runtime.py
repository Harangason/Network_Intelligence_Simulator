"""Runtime here is executable agent code, not a cache: classify and move it."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
plan = json.loads((OUT / 'backend-migration-plan.json').read_text())
aliases = json.loads((ROOT / 'backend/nis/compatibility.json').read_text())
paths = list((ROOT / 'backend/agent_core/runtime').glob('*.py'))
writes = {}
added = []
for path in paths:
    source = path.relative_to(ROOT).as_posix()
    target = source.replace('backend/agent_core/', 'backend/nis/agent/', 1)
    old_module = '.'.join(Path(source).with_suffix('').parts)
    new_module = '.'.join(Path(target).with_suffix('').parts)
    if path.name == '__init__.py':
        old_module = old_module.removesuffix('.__init__')
        new_module = new_module.removesuffix('.__init__')
    aliases[old_module] = new_module
    added.append({'path': source, 'bytes': path.stat().st_size,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'classification': 'EXECUTABLE_AGENT_RUNTIME_NOT_CACHE'})
    plan['mappings'][source] = target
    text = path.read_text(encoding='utf-8-sig')
    def replace(match):
        name = match.group()
        for prefix in sorted(aliases, key=len, reverse=True):
            if name == prefix or name.startswith(prefix + '.'):
                return aliases[prefix] + name[len(prefix):]
        return name
    text = re.sub(r'backend\.(?:app|engineering|agent_core|communication|knowledge|workflow)(?:\.[A-Za-z_][A-Za-z_0-9]*)*', replace, text)
    compile(text, target, 'exec')
    writes[target] = text
    writes[source] = f'"""Compatibility alias for executable agent runtime."""\nimport importlib\nimport sys\nsys.modules[__name__] = importlib.import_module({new_module!r})\n'
writes['backend/nis/compatibility.json'] = json.dumps(aliases, indent=2) + '\n'
temporary_plan = OUT / 'agent-runtime-step.json'
temporary_plan.write_text(json.dumps({'writes': {p: hashlib.sha256(t.encode()).hexdigest() for p, t in writes.items()}, 'before': added}, indent=2))
subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), '--plan', str(temporary_plan)], check=True)
for relative, text in writes.items():
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))
(OUT / 'backend-migration-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
inventory = json.loads((OUT / 'inventory-before.json').read_text())
inventory['files'].extend(added)
(OUT / 'inventory-before.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
print(json.dumps({'executable_agent_modules_moved': len(paths)}))
