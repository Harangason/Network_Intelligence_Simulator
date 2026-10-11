"""Rebase every real relative reference, including unmoved contracts and fixtures."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
plan_path = OUT / 'frontend-migration-plan.json'
plan = json.loads(plan_path.read_text())
work = json.loads((OUT / 'workload.json').read_text())
oldmap = dict(plan['mappings'])
mappings = dict(oldmap)
for source in mappings:
    if '/lib/agent/' in source:
        mappings[source] = 'frontend/src/features/agent/lib/' + source.split('/lib/agent/', 1)[1]
owners = {}
for source, target in mappings.items():
    if target in owners:
        raise SystemExit('Ownership collision: ' + source + ' / ' + owners[target])
    owners[target] = source

def original(relative):
    revision = work['revision_before'].get(relative)
    backup = OUT / 'before/steps' / str(revision) / relative
    return backup.read_text(encoding='utf-8-sig') if revision and backup.is_file() else (ROOT / relative).read_text(encoding='utf-8-sig')

def replace(value, source, target):
    if value.startswith('@/'):
        candidate = 'frontend/src/' + value[2:]
    elif value.startswith('.'):
        path = ((ROOT / source).parent / value).resolve()
        if not path.is_relative_to(ROOT): return value
        candidate = path.relative_to(ROOT).as_posix()
    elif value.startswith('src/'):
        candidate = 'frontend/' + value
    else:
        return value
    base = next((p for p in (candidate, candidate + '.ts', candidate + '.tsx', candidate + '.mjs', candidate + '/index.ts')
                 if p in mappings or (ROOT / p).is_file()), None)
    if base is None: return value
    mapped = mappings.get(base, base)
    if base != candidate and not base.endswith('/index.ts'): mapped = mapped.rsplit('.', 1)[0]
    if value.startswith('@/'): return '@/' + mapped[len('frontend/src/'):]
    if value.startswith('src/'): return mapped[len('frontend/'):]
    result = os.path.relpath(ROOT / mapped, (ROOT / target).parent).replace('\\', '/')
    return result if result.startswith('.') else './' + result

literal = re.compile(r'''(?P<q>['"])(?P<v>[^'"\r\n]*)(?P=q)''')
writes = {}; deletes = []
for source, target in mappings.items():
    before = original(source)
    text = literal.sub(lambda m: m['q'] + replace(m['v'], source, target) + m['q'], before)
    if (ROOT / target).exists() and (ROOT / target).read_text(encoding='utf-8-sig') == text:
        continue
    writes[target] = text
    if Path(source).suffix in {'.ts', '.tsx'}:
        result = os.path.relpath(ROOT / target, (ROOT / source).parent).replace('\\', '/').rsplit('.', 1)[0]
        result = result if result.startswith('.') else './' + result
        writes[source] = f'/** Compatibility export; canonical implementation: {target}. */\nexport * from {json.dumps(result)};\n'
        if re.search(r'\bexport\s+default\b', before): writes[source] += f'export {{ default }} from {json.dumps(result)};\n'
for relative in plan['writes']:
    if relative in mappings or relative in oldmap.values() or not relative.endswith(('.ts', '.tsx', '.mjs', '.css')):
        continue
    before = original(relative)
    text = literal.sub(lambda m: m['q'] + replace(m['v'], relative, relative) + m['q'], before)
    if text != (ROOT / relative).read_text(encoding='utf-8-sig'): writes[relative] = text
for source, old in oldmap.items():
    if old != mappings[source] and old not in mappings.values() and (ROOT / old).is_file():
        deletes.append(old)
step_path = OUT / 'frontend-location-fix.json'
step_path.write_text(json.dumps({'writes': {p: None for p in set(writes) | set(deletes)}, 'removed_generated_flattened_copies': deletes}, indent=2))
subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), '--plan', str(step_path)], check=True)
for relative, text in writes.items():
    path = ROOT / relative; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))
for relative in deletes:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT / 'frontend/src/features/agent/lib'): raise SystemExit('Unsafe deletion')
    path.unlink()
plan['mappings'] = mappings
plan_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
print(json.dumps({'fixed_files': len(writes), 'unified_owners': len(mappings), 'duplicate_flattened_copies_removed': len(deletes)}))
