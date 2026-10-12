"""Append only this workload's missing canonical owners; retain existing rows."""
import csv,hashlib,importlib.util,io,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
name='docs/migrations/structure_mapping.csv';path=ROOT/name
work_path=HERE/'workload.json';work=json.loads(work_path.read_text())
if name not in work['revision_before']:
    before=HERE/'before'/name;before.parent.mkdir(parents=True,exist_ok=True);before.write_bytes(path.read_bytes())
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    work['before'].append({'path':str(before),'sha256':digest});work['revision_before'][name]=digest
    work_path.write_text(json.dumps(work,indent=2)+'\n')
    print('STRUCTURE_SCOPE_CAPTURED; run guard before --apply')
else:
    import sys
    if '--apply' not in sys.argv:raise SystemExit('Use --apply after the revision guard.')
    spec=importlib.util.spec_from_file_location('mapping',ROOT/'scripts/migrations/structure_mapping.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=list(csv.DictReader(path.read_text(encoding='utf-8-sig').splitlines()))
    covered={r['source_path'] for r in rows}|{r['target_path'] for r in rows}
    paths=module.inventory(ROOT);missing=set(paths)-covered
    assert missing <= set(work['revision_before']),f'Foreign missing files: {missing}'
    reverse=module.consumers(ROOT,paths,[r['source_path'] for r in rows])
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=list(rows[0]))
    for item in sorted(missing):
        owner=module.module_name(item) or str(Path(item).parent).replace('\\','/')
        refs=json.dumps(sorted(reverse.get(item,set())),ensure_ascii=False)
        writer.writerow(dict(source_path=item,target_path=item,action='canonical-owner' if '/features/' in item else 'unchanged',
          responsibility='Canonical module owner: '+owner,owner=owner,consumers=refs,canonical_consumers=refs,
          data_impact='No schema or stored identity change',verification='backend/tests/test_structure_architecture.py; backend/tests/test_structure_completion.py; full release receipt linked in completion report',
          status='CANONICAL_PRESENT',consumer_scan='Python AST (including retired alias module paths, relative and literal dynamic imports), TypeScript imports, literal paths and documentation links; external/persisted consumers not observable',removal_criterion='Not a removable compatibility wrapper'))
    with path.open('ab') as stream:stream.write(output.getvalue().encode('utf-8'))
    print(json.dumps({'registered':sorted(missing),'count':len(missing)}))
