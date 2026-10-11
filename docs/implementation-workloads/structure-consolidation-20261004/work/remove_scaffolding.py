"""Remove placeholder packages and redundant physical technology alias trees."""
import ast
import csv
import io
import json
import shutil
from pathlib import Path
from edit_utils import ROOT, OUT, read, write, REMOVALS, apply

aliases = json.loads(read('backend/nis/compatibility.json'))
retired = {}
audit = json.loads(read('docs/implementation-workloads/structure-consolidation-20261004/ownership-before.json'))
generator_exports = {}
for item in audit['init_only_leaf_packages']:
    path = item['path']
    if '/handlers/' in path:
        replacement = 'backend.nis.agent.handlers'
    elif '/generators/' in path:
        replacement = 'backend.nis.agent.generators'
        tree = ast.parse(read(path + '/__init__.py'))
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign))
        assert ast.unparse(assignment.value) == 'BaseGenerator'
        generator_exports[assignment.targets[0].id] = 'BaseGenerator'
    elif path == 'backend/nis/physics':
        replacement = 'backend.nis.industries'
    else:
        continue  # Actual capability metadata and workflow-stage exports stay.
    retired[path.replace('/', '.')] = replacement
    REMOVALS.append(path + '/__init__.py')
for old, canonical in list(aliases.items()):
    if canonical in retired:
        aliases[old] = retired[canonical]
aliases.update(retired)
write('backend/nis/compatibility.json', json.dumps(aliases, ensure_ascii=False, indent=2) + '\n')
path = 'backend/nis/agent/generators/__init__.py'
write(path, read(path) + '\n# Historical names are aliases of BaseGenerator, not separate implementations.\n' + '\n'.join(f'{name} = {value}' for name,value in generator_exports.items()) + '\n')

# All imports retain their exact alias table entry. Published executable file
# paths are kept; these selected wrappers have neither functions nor a main.
redundant = []
for folder in ['backend/communication/technologies', 'backend/specializations/technologies']:
    for path in (ROOT / folder).rglob('*.py'):
        relative = path.relative_to(ROOT).as_posix()
        if relative.endswith('/__init__.py') and path.parent == ROOT / folder:
            continue  # Bare-root ingress bootstraps backend and its finder.
        source = read(relative)
        tree = ast.parse(source)
        module = relative[:-3].replace('/', '.').removesuffix('.__init__')
        target = aliases.get(module)
        if target is None or target not in source:
            continue
        assert not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If)) for n in tree.body), relative
        assert 'sys.modules' in source or '_sys.modules' in source, relative
        redundant.append(relative)
REMOVALS.extend(redundant)

# Redirect each retired placeholder's mapping to an actual package file.
rows = list(csv.DictReader(io.StringIO(read('docs/migrations/structure_mapping.csv'))))
for row in rows:
    module = row['target_path'][:-3].replace('/', '.').removesuffix('.__init__') if row['target_path'].endswith('.py') else None
    if module in retired:
        row['target_path'] = retired[module].replace('.', '/') + '/__init__.py'
        row['action'] = 'move-with-forwarding-entry'
write('docs/migrations/structure_mapping.csv', ''.join([])) if False else None
stream = io.StringIO(newline='')
writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
writer.writeheader()
writer.writerows(rows)
write('docs/migrations/structure_mapping.csv', stream.getvalue())
apply('remove-empty-and-redundant-tech-trees')

# Only proven removed source folders and physically empty routes are cleaned.
# Resolved absolute paths are checked before any recursive cache deletion.
cleaned = []
folders = {str((ROOT / p).parent.relative_to(ROOT)) for p in REMOVALS}
folders.update(audit['physically_empty'])
for relative in sorted(folders, key=lambda p: len(Path(p).parts), reverse=True):
    target = (ROOT / relative).resolve()
    assert target.is_relative_to(ROOT) and target != ROOT
    if not target.exists():
        continue
    entries = list(target.iterdir())
    if all(p.name == '__pycache__' for p in entries):
        for cache in entries:
            assert cache.resolve().is_relative_to(target)
            assert all(p.suffix == '.pyc' for p in cache.rglob('*') if p.is_file())
            shutil.rmtree(cache)
        target.rmdir()
        cleaned.append(target.relative_to(ROOT).as_posix())
(OUT / 'removed-directories.json').write_text(json.dumps({'retired_placeholders':retired, 'physical_alias_files':redundant, 'removed_directories':cleaned}, indent=2), encoding='utf-8')
print('Removed', len(cleaned), 'verified empty directories;', len(redundant), 'redundant physical aliases')
