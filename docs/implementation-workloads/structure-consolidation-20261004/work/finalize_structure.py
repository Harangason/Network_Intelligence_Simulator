import ast
import importlib.util
import json
import os
from pathlib import Path
from edit_utils import ROOT, OUT, read, write, apply

spec = importlib.util.spec_from_file_location('structure_mapping',ROOT/'scripts/migrations/structure_mapping.py')
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)
write('docs/migrations/structure_mapping.csv',mapping.reconcile())
path = 'docs/migrations/structure-checks.json'
case_document = json.loads(read(path))
serialized = json.dumps(case_document,indent=2,ensure_ascii=False) + '\n'
lines = serialized.splitlines()
starts = [i for i,line in enumerate(lines,1) if '"test_id":' in line]
for index,case in enumerate(case_document['test_cases']):
    case['source_lines'] = [starts[index]-1, starts[index+1]-2 if index+1 < len(starts) else len(lines)-2]
write(path,json.dumps(case_document,indent=2,ensure_ascii=False) + '\n')
owners = {
    'can':['encoding.py','formats/trace_model.py','formats/native_example.py','formats/restbus_example.py','formats/routing.py','formats/native_configuration.py','formats/mdf_writer.py','formats/archived_example.py'],
    'ethernet':['runtime.py','restbus.py','assessment.py','formats/trace_model.py'],
    'lin':['runtime.py','parameters.py','assessment.py'],
    'can_fd':['parameters.py','request_response.py'],
    'ip':['encoding.py'], 'udp':['encoding.py'], 'tcp':['encoding.py'], 'someip':['encoding.py'], 'someip_sd':['constants.py']}
for key,paths in owners.items():
    path = f'backend/nis/communication/technologies/{key}/README.md'
    write(path,read(path) + '\n\nZusätzlich konsolidierte vorhandene Implementierungen (2026-10-04):\n' + '\n'.join('- `' + p + '`' for p in paths) + '\n\nRegressionen: `backend/tests/test_structure_consolidation.py`;\nursprüngliche Unterstützungszustände und gespeicherte IDs bleiben maßgeblich.\n')
apply('complete-mapping-and-owner-documentation')

inventory = []
empty, placeholders = [], []
for root in ['backend/nis','frontend/src']:
    for directory,dirs,files in os.walk(ROOT/root):
        dirs[:] = [d for d in dirs if d not in {'__pycache__','.next','node_modules'}]
        path = Path(directory)
        if not files and not dirs:
            empty.append(path.relative_to(ROOT).as_posix())
        if files == ['__init__.py'] and not dirs:
            tree = ast.parse(path.joinpath('__init__.py').read_text(encoding='utf-8-sig'))
            if all(isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str) for n in tree.body):
                placeholders.append(path.relative_to(ROOT).as_posix())
        for file in files:
            if file.endswith('.py'):
                source = path/file
                tree = ast.parse(source.read_text(encoding='utf-8-sig'))
                inventory.append({'path':source.relative_to(ROOT).as_posix(), 'definitions':[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))],
                                  'imports': sorted({n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module})})
result = {'physically_empty':empty,'docstring_only_leaf_packages':placeholders,'technology_owners':owners,'python_dependency_inventory':inventory}
(OUT/'ownership-after.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print('After inventory:',len(inventory),'Python modules;',len(empty),'empty dirs;',len(placeholders),'docstring-only leaf packages')
