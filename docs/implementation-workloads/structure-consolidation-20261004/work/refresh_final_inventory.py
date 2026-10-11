import ast
import importlib.util
import json
import os
from pathlib import Path
from edit_utils import ROOT, OUT, read, write, apply

spec = importlib.util.spec_from_file_location('mapping', ROOT/'scripts/migrations/structure_mapping.py')
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)
write('docs/migrations/structure_mapping.csv',mapping.reconcile())
apply('final-retired-root-mapping')
inventory = []
empty,placeholders = [],[]
for root in ('backend/nis','frontend/src'):
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
                inventory.append({'path':source.relative_to(ROOT).as_posix(),'definitions':[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))],
                                  'imports':sorted({n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module})})
old = json.loads((OUT/'ownership-after.json').read_text(encoding='utf-8'))
old.update(physically_empty=empty,docstring_only_leaf_packages=placeholders,python_dependency_inventory=inventory,
           legacy_technology_source_trees_present=[folder for folder in ['backend/communication/technologies','backend/specializations/technologies'] if (ROOT/folder).exists()])
assert not empty and not placeholders and not old['legacy_technology_source_trees_present']
(OUT/'ownership-after.json').write_text(json.dumps(old,indent=2,ensure_ascii=False),encoding='utf-8')
print('Final inventory PASS:',len(inventory),'Python modules, no empty source scaffolding or old technology source trees')
