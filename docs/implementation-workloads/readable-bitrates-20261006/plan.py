import hashlib, json, shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
files = ['frontend/src/features/communication/lib/technology-parameters.ts',
         'frontend/src/features/communication/lib/technology-parameters.test.mjs',
         'frontend/src/features/simulation/ui/simulation-wizard.tsx',
         'frontend/e2e/technology-parameter-review.spec.ts']
work = dict(goal_id=out.name, goal_type='READABLE_BITRATES', kind='implementation',
    repository=str(root), project_scope='20261006151837393-c677c6ca; profile bit/s controls',
    requested_change='Display and edit rates as 19,2 kbit/s, 2 Mbit/s, 1 Gbit/s; persist exact canonical bit/s.',
    modify_code=True, allow_repair=True, unresolved_decisions=[],
    required_outcomes=['readable_editable_rates', 'lossless_canonical_persistence', 'production_delivery'],
    validation_requirements=['targeted_regression', 'full_release_gate', 'production_verification'],
    constraints=['Profile units and limits remain authoritative', 'No rounded rates or changed defaults', 'Preserve all existing dirty changes'],
    forbidden_changes=['Product database test fixtures', 'Changed acceptance gates', 'Hardware qualification from formatting'],
    files_inspected=files, revision_before={}, completion_status='IMPLEMENTING',
    context={'independent_campaign_id':'nis-ea-independent-20260924-run1', 'campaign_passed':False},
    implementation_plan=['Extend existing numeric field parser with decimal SI notation.', 'Format bit/s controls and rate summaries; keep JSON/API in bit/s.', 'Extend existing parameter regression cases and verify live reload after full tested delivery.'],
    delivery={'decision':'YES', 'authorization':'Standing user AGENTS.md rule', 'target':'NetworkIS localhost:13500'})
for file in files:
    source=root/file
    work['revision_before'][file]=hashlib.sha256(source.read_bytes()).hexdigest()
    target=out/'before'/file
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source,target)
(out/'workload.json').write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Four file revisions recorded; independent campaign remains unchanged.')
