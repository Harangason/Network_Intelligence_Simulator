import hashlib, json, shutil
from pathlib import Path

root = Path(__file__).resolve().parents[3]
work = Path(__file__).parent
files = [
    'frontend/src/app/globals.css',
    'frontend/src/features/workflow/stage_08_results_analysis/results-workbench.tsx',
    'frontend/src/features/capacity/ui/capacity-workbench.tsx',
    'frontend/src/features/capacity/lib/capacity-network-inspection.ts',
    'frontend/src/features/capacity/lib/capacity-network-inspection.test.mjs',
    'frontend/src/features/simulation/ui/simulation-wizard.tsx',
    'frontend/src/features/simulation/ui/model-simulation-runner.tsx',
    'frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx',
    'frontend/src/features/simulation/lib/e2e-sequence.ts',
    'frontend/src/features/simulation/lib/e2e-sequence.test.mjs',
]
revision = {}
before = []
for name in files:
    source = root / name
    target = work / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    revision[name] = digest
    before.append({'path': str(target), 'sha256': digest})
workload = dict(goal_id=work.name, goal_type='implementation', kind='implementation',
    repository=str(root), project_scope='13 approved Studio simulation/results/capacity/parameter changes',
    modify_code=True, allow_repair=True, revision_before=revision, before=before,
    required_outcomes=['scope_collapsed', 'runtime_full_width_50_rows', 'equal_expandable_charts',
        'snapshot_filter_six_rows', 'capacity_busload_tab', 'capacity_evidence_explanation',
        'parameter_navigation_removed', 'parameter_three_columns', 'computed_capacity_metrics',
        'optimization_semantics', 'scenario_semantics', 'sequence_fifteen_rows', 'boolean_sequence_search', 'production_delivery'],
    validation_requirements=['functional_unit_tests', 'typecheck', 'full_release_gate', 'production_identity_health'],
    constraints=['User explicitly approved all 13 points and production delivery',
        'No separate design/UI test run; mandatory complete production gate retained',
        'Aggregate stored capacity metrics only; never invent hardware or functional timing acceptance',
        'Shared simulation/observed sequence model and participant filtering preserved',
        'No product-database test writes, no EIP deployment, no unauthorized image pruning'],
    implementation_plan=['Reuse existing pagination and tables', 'Move busload list into new tab',
        'Add deterministic boolean search parser and stored-metric aggregation',
        'Apply responsive layouts, then mandatory exact-image release/deploy'],
    unresolved_decisions=[], remaining_findings=[], files_changed=[], outcomes={}, validations={},
    completion_status='IMPLEMENTING')
(work / 'workload.json').write_text(json.dumps(workload, indent=2), encoding='utf-8')
print(json.dumps({'files': len(files), 'workload': str(work / 'workload.json')}))
