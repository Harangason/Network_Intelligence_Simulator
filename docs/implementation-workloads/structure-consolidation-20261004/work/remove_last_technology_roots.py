import shutil
from edit_utils import ROOT, OUT, read, write, REMOVALS, apply

folders = ['backend/communication/technologies','backend/specializations/technologies']
for folder in folders:
    REMOVALS.append(folder + '/__init__.py')
path = 'backend/tests/test_structure_consolidation.py'
source = read(path).replace("        assert {path.name for path in (ROOT / folder).rglob('*.py')} == {'__init__.py'}", "        assert not (ROOT / folder).exists(), folder")
write(path, source)
path = 'docs/architecture/project-structure.md'
source = read(path).replace('103 redundant physical technology forwarding files, the catalog forwarding file,', '106 redundant physical technology forwarding files (including catalog and roots),')
source += '\nThe two old technology source trees are completely retired. Their parent ingress\npackages already install the exact alias finder; empty technology roots are unnecessary.\n'
write(path, source)
apply('remove-last-technology-roots')
for folder in folders:
    target = (ROOT/folder).resolve()
    assert target.is_relative_to(ROOT)
    entries = list(target.iterdir())
    assert all(entry.name == '__pycache__' for entry in entries)
    for entry in entries:
        assert entry.resolve().is_relative_to(target)
        assert all(p.suffix == '.pyc' for p in entry.rglob('*') if p.is_file())
        shutil.rmtree(entry)
    target.rmdir()
print('Both legacy technology source trees removed completely')
