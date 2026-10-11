import csv,io,json
from pathlib import Path
root=Path(__file__).resolve().parents[3];path=root/'docs/migrations/structure_mapping.csv'
rows=list(csv.DictReader(path.read_text(encoding='utf-8').splitlines()));fields=list(rows[0])
covered={row['source_path'] for row in rows}|{row['target_path'] for row in rows}
for source,consumers in [('frontend/src/shared/api/catalog-response.ts',['frontend/src/shared/api/api.ts','frontend/src/shared/api/catalog-response.test.mjs']),
                         ('frontend/src/shared/api/catalog-response.test.mjs',['scripts/release/run-release-gate.py'])]:
    assert (root/source).is_file()
    if source in covered:continue
    owner='frontend/src/shared/api'
    rows.append({'source_path':source,'target_path':source,'action':'unchanged',
        'responsibility':'Canonical module owner: '+owner,'consumers':json.dumps(consumers),
        'data_impact':'No schema or stored identity change',
        'verification':'backend/tests/test_structure_architecture.py; backend/tests/test_structure_completion.py; full release receipt linked in completion report',
        'status':'CANONICAL_PRESENT','owner':owner,'canonical_consumers':json.dumps(consumers),
        'consumer_scan':'Python AST (including retired alias module paths, relative and literal dynamic imports), TypeScript imports, literal paths and documentation links; external/persisted consumers not observable',
        'removal_criterion':'Not a removable compatibility wrapper'})
out=io.StringIO(newline='');writer=csv.DictWriter(out,fields,lineterminator='\n');writer.writeheader()
writer.writerows(sorted(rows,key=lambda row:(row['source_path'],row['target_path'])))
path.write_text(out.getvalue(),encoding='utf-8',newline='\n')
print('Mapped the two canonical catalog response files; existing row metadata preserved.')
