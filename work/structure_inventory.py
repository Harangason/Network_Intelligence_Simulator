"""Read-only inventory for the approved structure migration; preserve dirty work."""
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
SKIP = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', '.next', '.next-networkis',
        'test-output', 'runtime', 'work', 'artifacts', '.tool-checker', 'var'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for directory, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')
                   and (Path(directory) != ROOT or d in {'backend', 'frontend', 'scripts', 'config', 'docs', 'tests', 'tool-checker'})]
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith('docs/implementation-workloads/'):
                continue
            row = {'path': relative, 'bytes': path.stat().st_size,
                   'sha256': sha(path) if path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3'} else None}
            if path.suffix == '.py':
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                    row['imports'] = [{'module': n.module, 'level': n.level,
                                       'names': [a.name for a in n.names]} if isinstance(n, ast.ImportFrom)
                                      else {'names': [a.name for a in n.names]}
                                      for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
                    row['definitions'] = [n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
                except (SyntaxError, UnicodeError) as error:
                    row['parse_error'] = str(error)
            records.append(row)
    status = subprocess.check_output(['git', 'status', '--porcelain=v1', '-z'], cwd=ROOT)
    (OUT / 'git-before.txt').write_bytes(status.replace(b'\0', b'\n'))
    inventory = {'repository': str(ROOT), 'files': records, 'existing_working_tree_entries': status.count(b'\0')}
    (OUT / 'inventory-before.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    work = {'goal_id': 'project-structure-migration-20261003', 'goal_type': 'STRUCTURE_MIGRATION',
        'repository': str(ROOT), 'project_scope': 'Canonical NIS backend, frontend, deployment and persistence',
        'requested_change': 'Vollständige Umsetzung NIS_PROJEKTSTRUKTUR_UND_MIGRATIONSPLAN.md',
        'modify_code': True, 'kind': 'implementation', 'completion_status': 'ANALYZING',
        'constraints': ['Preserve all existing dirty changes, technology identities, API and stored data',
                        'One canonical implementation and registry; compatibility wrappers only',
                        'Exact complete release PASS receipt and production image verification'],
        'required_outcomes': ['canonical_technologies', 'canonical_backend', 'frontend_features',
            'central_storage', 'documentation_tools', 'complete_mapping', 'compatibility', 'production_delivery'],
        'validation_requirements': ['architecture', 'identity_capability_equivalence', 'storage_migration',
            'backend_regression', 'frontend_regression', 'release_gate', 'production_functionality'],
        'unresolved_decisions': [], 'revision_before': {r['path']: r['sha256'] for r in records
            if r['path'].startswith(('backend/', 'frontend/src/', 'scripts/', 'config/'))
            or r['path'] in ('Dockerfile', 'generate_realistic_communication_tool.py')},
        'delivery': {'decision': 'YES', 'authorization': 'Standing production delivery authorization in AGENTS.md',
                     'target': 'canonical NetworkIS production stack'},
        'files_inspected': [r['path'] for r in records], 'remaining_findings': []}
    (OUT / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(records), 'python': sum('imports' in r for r in records),
                      'dirty_entries': status.count(b'\0'), 'evidence': str(OUT)}))

if __name__ == '__main__':
    main()
