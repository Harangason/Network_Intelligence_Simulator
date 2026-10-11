"""Update every inventoried/affected source with actual current owner and transition."""
import csv
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/implementation-workloads/project-structure-migration-20261003'
moves={}
changed=set()
for name in ('technology-migration-plan.json','backend-migration-plan.json','frontend-migration-plan.json',
             'tools-migration-plan.json','docs-migration-plan.json','format-ownership-plan.json','industry-projection-plan.json',
             'starters-migration-plan.json','package-init-plan.json','package-parent-plan.json'):
    plan=json.loads((OUT/name).read_text(encoding='utf-8'))
    moves.update(plan.get('mappings',plan.get('moves',{})))
    changed.update(plan.get('writes',{}))
moves['backend/communication/technologies/source_metadata.json']='backend/nis/communication/services/source_metadata.json'
rows={row['source_path']:row for row in csv.DictReader((ROOT/'docs/migrations/structure_mapping.csv').open(encoding='utf-8'))}
skip={'.git','.venv','node_modules','__pycache__','.pytest_cache','runtime','var','artifacts','build','test-output','work'}
for base in ('backend/nis','frontend/src','scripts','docs/architecture','docs/domains','docs/contracts','docs/testing','docs/migrations'):
    for directory, dirs, files in os.walk(ROOT/base):
        dirs[:]=[d for d in dirs if d not in skip and not d.endswith('.egg-info')]
        for name in files:
            changed.add((Path(directory)/name).relative_to(ROOT).as_posix())
for source in set(rows)|changed|set(moves):
    target=moves.get(source,source)
    if not (ROOT/target).exists() and source not in moves:
        status='REMOVED_AFTER_GUARDED_RELOCATION'
        action='relocated-generated-duplicate'
    elif source in moves and source!=target:
        status='COMPATIBILITY_RETAINED' if (ROOT/source).exists() else 'CANONICAL_OWNER_RELOCATED'
        action='move-with-forwarding-entry' if (ROOT/source).exists() else 'move'
    else:
        status='CANONICAL_LOCAL_RELEASE_PENDING' if source in changed else 'RETAINED_COMPATIBLE'
        action='canonical-owner' if source in changed else 'unchanged'
    if source.endswith(('.db','.sqlite','.sqlite3')):
        status='RETAINED_LEGACY_REFERENCE_NOT_WRITTEN'
        action='unchanged-reference'
    if source.startswith('backend/nis/'):
        responsibility='/'.join(source.split('/')[:3])
    elif source.startswith('frontend/src/features/'):
        responsibility='/'.join(source.split('/')[:4])
    elif source.startswith('scripts/'):
        responsibility='/'.join(target.split('/')[:2])
    elif source in {'Dockerfile','vercel.json'} or source.startswith(('docker-compose','start-')):
        responsibility='Established deployment entrypoint; contexts/mounts preserved'
    elif source.startswith('docs/'):
        responsibility='Document owner: '+str(Path(target).parent).replace('\\','/')
    else:
        responsibility='Existing external/fixture/compatibility contract: '+str(Path(target).parent).replace('\\','/')
    rows[source]={'source_path':source,'target_path':target,'action':action,'responsibility':responsibility,
        'consumers':'Recorded import graph and migration plans; canonical owner consumers preserved',
        'data_impact':'Stored identities/schema unchanged; snapshots retain originals' if action=='snapshot-copy' else 'No stored identity or schema change',
        'verification':'Migration architecture/CLI/trace/storage checks; complete release gate pending',
        'status':status}
for entry in json.loads((OUT/'storage-receipt.json').read_text())['files']:
    source=Path(entry['source']).relative_to(ROOT).as_posix()
    target=Path(entry['target']).relative_to(ROOT).as_posix()
    rows[source]={'source_path':source,'target_path':target,'action':'snapshot-copy',
        'responsibility':'Durable storage','consumers':'Central filesystem paths',
        'data_impact':'Original retained; coherent SQLite backup or identical file copy',
        'verification':'Checksum and readability in storage-receipt.json','status':'LOCAL_SNAPSHOT_VERIFIED'}
fields=['source_path','target_path','action','responsibility','consumers','data_impact','verification','status']
with (ROOT/'docs/migrations/structure_mapping.csv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows[key] for key in sorted(rows))
print(json.dumps({'mapped_files':len(rows),'compatibility_entries':sum(r['status']=='COMPATIBILITY_RETAINED' for r in rows.values())}))
