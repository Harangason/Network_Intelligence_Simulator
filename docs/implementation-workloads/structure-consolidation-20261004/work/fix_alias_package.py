import csv
import hashlib
import io
import json
from edit_utils import ROOT, OUT, read, write, REMOVALS, apply

path = 'backend/nis/communication/ownership.py'
new = 'backend/nis/communication/ownership/__init__.py'
write(new, read(path))
REMOVALS.append(path)
workload = json.loads((OUT/'workload.json').read_text(encoding='utf-8'))
evidence = OUT/'final-targeted.xml'
workload['kind'] = 'repair'
workload['repair'] = {'owner':'PROJECT_PRODUCT',
    'root_cause':'Legacy technology package alias resolves to a non-package canonical ownership.py module, preventing Python from importing its registered child aliases.',
    'first_failing_layer':'Python parent-package import protocol before MetaPathFinder child resolution',
    'reproduction':'test_removed_physical_technology_aliases_still_import_same_owner: ModuleNotFoundError for backend.specializations.technologies.aerospace; parent is not a package',
    'evidence':[{'path':str(evidence), 'sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()}],
    'affected_files':[path,new],
    'acceptance_criteria':['All published legacy technology imports resolve to the identical canonical module object', 'The canonical ownership module retains its exact manifest exports'],
    'targeted_tests':['backend/tests/test_structure_consolidation.py'],
    'weaken_assertions_to_pass':False}
(OUT/'workload.json').write_text(json.dumps(workload,indent=2),encoding='utf-8')
rows = list(csv.DictReader(io.StringIO(read('docs/migrations/structure_mapping.csv'))))
for row in rows:
    if row['target_path'] == path:
        row['target_path'] = new
        if row['source_path'] == path:
            row['action'] = 'move-preserving-module'
stream = io.StringIO(newline='')
writer = csv.DictWriter(stream,list(rows[0]),lineterminator='\n')
writer.writeheader()
writer.writerows(rows)
write('docs/migrations/structure_mapping.csv',stream.getvalue())
apply('legacy-namespace-package-repair')
workload = json.loads((OUT/'workload.json').read_text(encoding='utf-8'))
workload['kind'] = 'implementation'
(OUT/'workload.json').write_text(json.dumps(workload,indent=2),encoding='utf-8')
