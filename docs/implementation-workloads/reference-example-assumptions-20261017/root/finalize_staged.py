"""Refresh review evidence only. The release owner performs canonical apply."""
from pathlib import Path
import difflib
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
targets = [
    'backend/nis/agent/orchestration/project_intake.py',
    'backend/tests/test_reference_design.py',
    'frontend/src/features/agent/lib/actuator-commands.ts',
    'frontend/src/features/agent/lib/device-proposals.test.mjs',
    'frontend/src/features/agent/lib/engineering-specification.ts',
    'frontend/scripts/extract-wizard-specification.mjs',
    'frontend/src/features/agent/lib/reference-specification.test.mjs',
]
test = OUT / 'staged/backend/tests/test_reference_design.py'
test.parent.mkdir(parents=True, exist_ok=True)
test.write_bytes((OUT / 'test_reference_design.py').read_bytes())
digest = lambda value: hashlib.sha256(value).hexdigest()
manifest = {}
diff = []
for relative in targets:
    canonical = ROOT / relative
    before = canonical.read_bytes() if canonical.is_file() else None
    snapshot = OUT / 'before' / relative
    if before is not None:
        assert snapshot.is_file() and snapshot.read_bytes() == before, relative + ': canonical revision changed'
    staged = (OUT / 'staged' / relative).read_bytes()
    manifest[relative] = {'before': digest(before) if before is not None else None, 'staged': digest(staged)}
    diff.extend(difflib.unified_diff((before or b'').decode('utf-8').splitlines(True),
        staged.decode('utf-8').splitlines(True), fromfile='a/' + relative, tofile='b/' + relative))
(OUT / 'owned-staged.diff').write_text(''.join(diff), encoding='utf-8')
(OUT / 'staged-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
work.update(status='STAGED_REVIEW', completion_status='AWAITING_COORDINATED_CANONICAL_APPLY',
    revision_before={key: value['before'] for key, value in manifest.items()}, root_owned_files=targets,
    unresolved_decisions=[], remaining_findings=[
        'Canonical combined integration and tests pending',
        'Native NIS reference planning, two full original project simulations and exact tested image delivery pending',
    ])
work['constraints'][0] = 'Previous fd2d74 release completed; canonical apply remains coordinated by NIS starten after joint manifest and guard.'
work['repair']['affected_files'] = targets
def evidence(file):
    path = OUT / file
    return {'path': str(path), 'sha256': digest(path.read_bytes())}
work['staged_review'] = {'manifest': evidence('staged-manifest.json'), 'diff': evidence('owned-staged.diff'),
    'canonical_source_changed': False,
    'scope': 'Staging fixtures, catalog substitution and read-only loader/typecheck are unit evidence, not product inference or E2E.'}
(OUT / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status':'STAGED_REVIEW', 'targets':len(targets), 'canonical_source_changed':False}))
