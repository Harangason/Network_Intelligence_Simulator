import hashlib, json, shutil
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
files = ['backend/nis/engineering/capacity/service.py', 'backend/nis/engineering/capacity/calculators.py',
         'backend/nis/engineering/capacity/dimensioning.py', 'backend/nis/agent/tools/validation.py',
         'backend/nis/interfaces/http/engineering.py', 'frontend/src/features/simulation/ui/simulation-wizard.tsx',
         'frontend/src/features/communication/lib/technology-parameters.ts',
         'frontend/src/features/workflow/lib/workflow-api.ts',
         'backend/tests/test_technology_parameter_review.py', 'backend/tests/test_proposal_capacity.py',
         'backend/tests/test_bus_rate_planning.py', 'frontend/e2e/technology-parameter-review.spec.ts']
files += ['backend/nis/engineering/capacity/sizing_service.py',
          'backend/nis/agent/tools/proposal_service.py',
          'backend/nis/communication/technologies/lin/timing.py',
          'backend/nis/communication/technologies/can_fd/timing.py',
          'frontend/src/features/agent/lib/proposal-client.ts',
          'frontend/src/features/agent/ui/engineering-agent-event.tsx']
files += ['frontend/src/features/capacity/ui/capacity-workbench.tsx', 'frontend/src/shared/api/types.ts']

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

work = {
    'goal_id': OUT.name, 'goal_type': 'SAVED_SIMULATION_CAPACITY', 'kind': 'repair',
    'repository': str(ROOT), 'project_scope': '20261006151837393-c677c6ca; all registered technology parameter consumers',
    'requested_change': 'Saved native simulation parameters must drive review, validation and sizing without false missing-rate errors or hardware qualification.',
    'modify_code': True, 'allow_repair': True, 'unresolved_decisions': [],
    'required_outcomes': ['saved_native_parameter_resolution', 'correct_simulation_capacity_review', 'shared_sizing_and_validation', 'production_delivery'],
    'validation_requirements': ['targeted_regression', 'full_release_gate', 'production_verification'],
    'constraints': ['TechnologyProfile SSOT', 'Project-only user values', 'Keep strict hardware and functional timing gates', 'Preserve explicit inputs and native constraints'],
    'forbidden_changes': ['Product database tests', 'Invented evidence', 'Silent foreign-bus fallback', 'Weaken actual acceptance assertions'],
    'files_inspected': files, 'revision_before': {}, 'completion_status': 'IMPLEMENTING',
    'context': {'independent_campaign_id': 'nis-ea-independent-20260924-run1', 'campaign_passed': False},
    'repair': {
        'owner': 'PROJECT_PRODUCT', 'root_cause': 'parameters_for_protocol ignores proven stored simulation_parameter_assumptions; pending proposal rate planning is omitted; parameter review confuses unavailable hardware proof with missing simulation rate.',
        'first_failing_layer': 'Shared native parameter resolution',
        'reproduction': 'Read-only normal API reproduces 300 rate findings despite stored LIN19200, CANFD500000/2000000 and Ethernet1000000000 with exact ASSUMED provenance.',
        'evidence': [ref(OUT/'before-live'/'parameters.json'), ref(OUT/'before-live'/'review.json')],
        'affected_files': files, 'acceptance_criteria': ['Persist/reload uses exact same native values', 'Invalid assumptions still block; hardware evidence remains false', 'Pending and canonical graph get real native load and actionable missing fields'],
        'targeted_tests': ['test_technology_parameter_review.py', 'test_proposal_capacity.py', 'test_bus_rate_planning.py', 'technology-parameter-review.spec.ts'], 'weaken_assertions_to_pass': False,
    },
    'implementation_plan': ['Extend the existing native resolver for explicitly marked saved scenarios; retain strict default evidence mode.', 'Reuse registered timing estimators for scenario calculation, reject operational errors and foreign or stale provenance.', 'Check bus demand once per physical shared bus or switched transmitting port, including pending proposal graph; retain separate qualification findings.', 'Expose modelled load and native rate plans in parameter review and capacity results, preserve real preflight.', 'Verify persist/reload and negative cases, run complete release gate and deploy exact tested image.'],
    'delivery': {'decision': 'YES', 'authorization': 'Explicit standing user AGENTS.md production delivery rule', 'target': 'Canonical NetworkIS localhost:13500'},
}
for file in files:
    source = ROOT/file
    work['revision_before'][file] = hashlib.sha256(source.read_bytes()).hexdigest()
    target = OUT/'before'/file
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists(): shutil.copyfile(source, target)
(OUT/'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Planned', len(files), 'files; existing campaign untouched')
