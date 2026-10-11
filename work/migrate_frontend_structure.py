"""Move UI/client code by feature; preserve routes and exact test assertions."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'

def feature(name):
    if name.startswith(('agent-', 'assistant-', 'global-agent', 'engineering-agent', 'engineering-response', 'goal-', 'specialist-', 'workload-', 'reasoning-', 'wizard-')):
        return 'agent'
    if name.startswith(('technology-', 'bus-', 'communication-')) or name == 'catalog-proxy': return 'communication'
    if name.startswith(('capacity-', 'preflight-')): return 'capacity'
    if name.startswith(('routing-',)): return 'routing'
    if name.startswith(('network-', 'topology', 'hardware-', 'ecu-')): return 'network'
    if name.startswith(('project-',)): return 'projects'
    if name.startswith(('engineering-', 'structure-', 'signal-')): return 'engineering'
    if name.startswith(('simulation-', 'model-simulation', 'results-', 'e2e-')): return 'simulation'
    if name.startswith(('trace-',)): return 'traces'
    if name.startswith(('intelligence-',)): return 'intelligence'
    if name.startswith(('settings-', 'user-settings')): return 'settings'
    if name.startswith(('source-',)): return 'sources'
    if name.startswith(('workflow-', 'use-workflow', 'studio-', 'runtime-status')): return 'workflow'
    if name == 'marketing-shell': return 'marketing'
    return None

def main():
    mappings = {}
    files = [p for folder in ('frontend/src/components', 'frontend/src/lib') for p in (ROOT / folder).rglob('*') if p.is_file()]
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        name = path.name.replace('.test.mjs', '').replace('.module.css', '').rsplit('.', 1)[0]
        chosen = 'agent' if '/lib/agent/' in relative else feature(name)
        if '/components/' in relative:
            target = f'frontend/src/features/{chosen}/ui/{path.name}' if chosen else f'frontend/src/shared/ui/{path.name}'
        else:
            target = f'frontend/src/features/{chosen}/lib/{path.name}' if chosen else f'frontend/src/shared/lib/{path.name}'
            if name in {'api', 'backend-endpoints', 'engineering-api', 'engineering-server-client', 'types', 'lossless-json'}:
                target = 'frontend/src/shared/api/' + path.name
        mappings[relative] = target
    mappings['frontend/src/app/sources/page.tsx'] = 'frontend/src/features/sources/ui/source-directory-page.tsx'
    candidates = [p for folder in ('frontend/src', 'frontend/scripts', 'frontend/e2e') for p in (ROOT / folder).rglob('*')
                  if p.is_file() and p.suffix in {'.ts', '.tsx', '.mjs', '.css'}]
    writes = {}; deletes = []
    def replacement(value, source, target):
        if value.startswith('@/'):
            candidate = 'frontend/src/' + value[2:]
            base = next((p for p in (candidate, candidate + '.ts', candidate + '.tsx', candidate + '.mjs') if p in mappings), None)
            if base:
                mapped = mappings[base]
                if base != candidate: mapped = mapped.rsplit('.', 1)[0]
                return '@/' + mapped[len('frontend/src/'):]
        elif value.startswith('.'):
            candidate_path = (ROOT / source).parent / value
            candidate = candidate_path.resolve().relative_to(ROOT).as_posix() if candidate_path.resolve().is_relative_to(ROOT) else ''
            base = next((p for p in (candidate, candidate + '.ts', candidate + '.tsx', candidate + '.mjs') if p in mappings), None)
            if base:
                mapped = mappings[base]
                if base != candidate: mapped = mapped.rsplit('.', 1)[0]
                result = os.path.relpath(ROOT / mapped, (ROOT / target).parent).replace('\\', '/')
                return result if result.startswith('.') else './' + result
        elif value.startswith('src/') and 'frontend/' + value in mappings:
            return mappings['frontend/' + value][len('frontend/'):]
        return value
    literal = re.compile(r'''(?P<q>['"])(?P<v>[^'"\r\n]*)(?P=q)''')
    for path in candidates:
        source = path.relative_to(ROOT).as_posix()
        target = mappings.get(source, source)
        before = path.read_text(encoding='utf-8-sig')
        after = literal.sub(lambda m: m['q'] + replacement(m['v'], source, target) + m['q'], before)
        if source != target or after != before:
            writes[target] = after
        if source != target:
            if path.suffix in {'.ts', '.tsx'}:
                result = os.path.relpath(ROOT / target, path.parent).replace('\\', '/').rsplit('.', 1)[0]
                result = result if result.startswith('.') else './' + result
                wrapper = f'/** Compatibility export; canonical implementation: {target}. */\nexport * from {json.dumps(result)};\n'
                if re.search(r'\bexport\s+default\b', before): wrapper += f'export {{ default }} from {json.dumps(result)};\n'
                writes[source] = wrapper
            else:
                deletes.append(source)
    for source, target in mappings.items():
        path = ROOT / source
        if path.suffix == '.json':
            writes[target] = path.read_text(encoding='utf-8-sig')
            deletes.append(source)
    package_path = 'frontend/package.json'
    package = json.loads((ROOT / package_path).read_text())
    for key, value in package['scripts'].items():
        for source, target in sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True):
            value = value.replace(source[len('frontend/'):], target[len('frontend/'):])
        if key == 'test': value = 'node --experimental-strip-types --test src/features/*/lib/*.test.mjs src/shared/*/*.test.mjs'
        package['scripts'][key] = value
    writes[package_path] = json.dumps(package, indent=2) + '\n'
    vocab = 'backend/nis/agent/tools/inventory_quantities.py'
    writes[vocab] = (ROOT / vocab).read_text().replace('frontend/src/lib/agent/inventory-vocabulary.json',
        'frontend/src/features/agent/lib/inventory-vocabulary.json')
    step = OUT / 'frontend-migration-plan.json'
    step.write_text(json.dumps({'mappings': mappings, 'writes': {p: hashlib.sha256(s.encode()).hexdigest() for p, s in writes.items()},
                                'deletes': deletes}, indent=2), encoding='utf-8')
    # Deleted copies are backed up and revision-checked as well.
    guard_plan = OUT / 'frontend-guard-plan.json'
    guard_plan.write_text(json.dumps({'writes': {p: None for p in set(writes) | set(deletes)}}))
    subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), '--plan', str(guard_plan)], check=True)
    for relative, text in writes.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
    for relative in deletes:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT / 'frontend/src'):
            raise SystemExit('Unsafe deletion: ' + relative)
        path.unlink()
    work_path = OUT / 'workload.json'
    work = json.loads(work_path.read_text())
    work['files_changed'] = sorted(set(work['files_changed']) | set(writes) | set(deletes))
    work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
    print(json.dumps({'feature_moves': len(mappings), 'updated_files': len(writes), 'duplicate_tests_assets_removed': len(deletes)}))

if __name__ == '__main__':
    main()
