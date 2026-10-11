"""Preserve observed import edges for aliases whose physical files are gone."""
import importlib.util
import json
from edit_utils import ROOT, OUT, read, write, apply

path = 'scripts/migrations/structure_mapping.py'
source = read(path)
source = source.replace('def consumers(root, paths):', 'def consumers(root, paths, virtual_paths=()):')
source = source.replace("    modules = {module_name(p): p for p in paths if p.endswith('.py')}", "    modules = {module_name(p): p for p in [*virtual_paths, *paths] if p.endswith('.py')}")
source = source.replace('    pathset = set(paths)', '    pathset = set(paths) | set(virtual_paths)')
source = source.replace('    reverse = consumers(root, paths)', "    reverse = consumers(root, paths, [row['source_path'] for row in existing])")
source = source.replace('Python AST (including relative and literal dynamic imports)', 'Python AST (including retired alias module paths, relative and literal dynamic imports)')
write(path, source)
apply('alias-consumer-inventory')

spec = importlib.util.spec_from_file_location('migration_inventory',ROOT/path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
file = 'backend/communication/technologies/lin.py'
consumer = 'backend/tests/test_structure_consolidation.py'
# The independent fixture is a real source import of an absent physical module.
fixture = OUT/'work/alias-inventory-fixture'
fixture.mkdir(exist_ok=True)
fixture.joinpath('consumer.py').write_text('from backend.communication.technologies.lin import PROFILE\n',encoding='utf-8')
assert module.consumers(fixture,['consumer.py'],[file])[file] == {'consumer.py'}
fixture.joinpath('consumer.py').write_text('from communication.technologies.lin import PROFILE\n',encoding='utf-8')
assert module.consumers(fixture,['consumer.py'],[file])[file] == {'consumer.py'}
write('docs/migrations/structure_mapping.csv',module.reconcile())
apply('reconciled-alias-consumers')
(OUT/'alias-inventory-verification.json').write_text(json.dumps({'status':'PASS','absent_physical_module':file,'verified_absolute_and_bare_imports':True,'external_consumers':'Not observable; exact aliases retained'},indent=2),encoding='utf-8')
print('Absent physical alias dependencies verified and preserved in mapping')
