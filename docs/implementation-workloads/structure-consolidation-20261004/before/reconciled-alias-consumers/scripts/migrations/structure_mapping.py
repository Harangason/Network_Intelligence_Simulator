"""Reconcile structure transitions with current import and entry-point references.

Only repository consumers are observable. An empty list is never permission
to remove an externally published or persisted legacy path.
"""
import ast
import csv
import io
import json
import re
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = ('/.venv/', '/node_modules/', '/test-output/', '/runtime/', '/backend/build/',
            '/before/', '/archive/', '/archives/', '/__pycache__/', '/.next/',
            '/project-scanner/', '/implementation-workloads/')

def inventory(root=ROOT):
    paths = []
    pruned = {'.pytest_cache', '.git', '.venv', 'node_modules', 'test-output', 'runtime', 'before', 'archive',
              'archives', '__pycache__', '.next', 'project-scanner', 'implementation-workloads'}
    for folder in ['backend', 'frontend/src', 'scripts', 'docs']:
        for directory, dirs, files in os.walk(root / folder):
            dirs[:] = [name for name in dirs if name not in pruned]
            for name in files:
                path = (Path(directory) / name).relative_to(root).as_posix()
                if not any(part in '/' + path for part in EXCLUDED) and Path(path).suffix in {
                    '.py', '.ts', '.tsx', '.mjs', '.json', '.md', '.ps1', '.sh', '.yml', '.yaml'}:
                    paths.append(path)
    return sorted(paths)


def module_name(path):
    if not path.endswith('.py'): return None
    return path[:-3].replace('/', '.').removesuffix('.__init__')

def consumers(root, paths, virtual_paths=()):
    modules = {module_name(p): p for p in [*virtual_paths, *paths] if p.endswith('.py')}
    # Bare backend ingress names are supported compatibility paths too.
    modules.update({key.removeprefix('backend.'): value for key,value in list(modules.items()) if key.startswith('backend.')})
    reverse = defaultdict(set)
    pathset = set(paths) | set(virtual_paths)
    def edge(target, consumer):
        if target in pathset and target != consumer: reverse[target].add(consumer)
    def imported(name, consumer):
        while name:
            if name in modules:
                edge(modules[name], consumer)
                return
            name = name.rpartition('.')[0]
    for path in paths:
        text = (root / path).read_text(encoding='utf-8-sig', errors='replace')
        if path.endswith('.py'):
            try: tree = ast.parse(text)
            except SyntaxError: continue
            package = module_name(path) if path.endswith('/__init__.py') else module_name(path).rpartition('.')[0]
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imported(alias.name, path)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ''
                    if node.level:
                        prefix = package.split('.')[:len(package.split('.')) - node.level + 1]
                        base = '.'.join([*prefix, base]).strip('.')
                    imported(base, path)
                    for alias in node.names: imported(base + '.' + alias.name, path)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in modules: imported(node.value, path)
        if path.startswith('frontend/src/'):
            for match in re.finditer(r'(?:from\s*|import\s*\()\s*[\'\"]([^\'\"]+)', text):
                value = match.group(1)
                if value.startswith('@/'): base = root / 'frontend/src' / value[2:]
                elif value.startswith('.'): base = root / Path(path).parent / value
                else: continue
                for suffix in ['', '.ts', '.tsx', '.mjs', '.json', '/index.ts', '/index.tsx']:
                    candidate = Path(str(base) + suffix).resolve()
                    if candidate.is_relative_to(root): edge(candidate.relative_to(root).as_posix(), path)
        # Quoted/backtick tokens cover CLI and Markdown references without
        # catastrophic path-regex backtracking through large fixture payloads.
        for value in re.findall(r"[\"'`](.{1,400}?)[\"'`]", text):
            value = value.replace('\\', '/')
            if '/' not in value or Path(value).suffix not in {'.py', '.ts', '.tsx', '.mjs', '.json', '.md', '.ps1', '.sh'}:
                continue
            edge(value, path)
            candidate = (root / Path(path).parent / value).resolve()
            if candidate.is_relative_to(root): edge(candidate.relative_to(root).as_posix(), path)
    return reverse

def reconcile(root=ROOT):
    mapping = root / 'docs/migrations/structure_mapping.csv'
    existing = list(csv.DictReader(mapping.read_text(encoding='utf-8-sig').splitlines()))
    paths = inventory(root)
    reverse = consumers(root, paths, [row['source_path'] for row in existing])
    accounted = {row['source_path'] for row in existing} | {row['target_path'] for row in existing}
    for path in paths:
        if path not in accounted:
            existing.append(dict(source_path=path, target_path=path, action='canonical-owner' if '/nis/' in path or '/features/' in path else 'unchanged'))
    for row in existing:
        source, target = row['source_path'], row['target_path']
        refs = sorted(reverse.get(source, set()))
        owner = module_name(target) or str(Path(target).parent).replace('\\', '/')
        row['responsibility'] = 'Canonical module owner: ' + owner
        row['owner'] = owner
        row['consumers'] = json.dumps(refs, ensure_ascii=False)
        row['canonical_consumers'] = json.dumps(sorted(reverse.get(target, set())), ensure_ascii=False)
        row['consumer_scan'] = 'Python AST (including retired alias module paths, relative and literal dynamic imports), TypeScript imports, literal paths and documentation links; external/persisted consumers not observable'
        row['data_impact'] = row.get('data_impact') or 'No schema or stored identity change'
        row['verification'] = 'backend/tests/test_structure_architecture.py; backend/tests/test_structure_completion.py; full release receipt linked in completion report'
        row['status'] = ('RETAINED_COMPATIBLE' if (root / source).is_file() else 'IMPORT_ALIAS_ONLY') if row['action'] == 'move-with-forwarding-entry' else 'CANONICAL_PRESENT' if (root / target).is_file() else 'HISTORICAL_REFERENCE'
        row['removal_criterion'] = (f'Owner {owner} must migrate repository consumers {json.dumps(refs)}; inventory persisted module/CLI references and supported external callers for {source}; prove alias/import and behavior regressions plus full release PASS before removal. No retirement deadline authorized.'
                                    if row['action'] == 'move-with-forwarding-entry' else 'Not a removable compatibility wrapper')
    fields = ['source_path','target_path','action','responsibility','consumers','data_impact','verification','status',
              'owner','canonical_consumers','consumer_scan','removal_criterion']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(sorted(existing, key=lambda row: (row['source_path'], row['target_path'])))
    return output.getvalue()

if __name__ == '__main__':
    (ROOT / 'docs/migrations/structure_mapping.csv').write_text(reconcile(), encoding='utf-8', newline='\n')
