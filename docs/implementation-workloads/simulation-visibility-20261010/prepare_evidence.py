import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FILES = [
    'frontend/src/features/simulation/lib/simulation-signal-view.ts',
    'frontend/src/features/simulation/lib/simulation-signal-view.test.mjs',
    'frontend/src/features/simulation/ui/model-simulation-runner.tsx',
    'frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx',
    'frontend/src/app/globals.css',
    'frontend/e2e/studio-export-controls.spec.ts',
    'frontend/src/features/simulation/lib/simulation-pagination.ts',
    'frontend/src/features/simulation/lib/simulation-pagination.test.mjs',
    'frontend/src/features/simulation/ui/simulation-page-controls.tsx',
]
def ref(p):
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

baseline = {}
before = []
for name in FILES:
    source = ROOT / name
    baseline[name] = ref(source)['sha256'] if source.exists() else None
    if source.exists():
        dest = HERE / 'before' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        before.append(ref(dest))
evidence = HERE / 'source-findings.json'
evidence.write_text(json.dumps({
    'project': '20261009072206008-4bb505f1',
    'signals': 'Initial selection sorts and slices to 18; DYNAMIC default hides static signals; render slices at 60 with no access to later matches.',
    'sequence': 'Row highlight paints opaque surface above lifelines and activations. Label background spans the complete route. Events beyond 200 have no navigation.',
    'existing_tests': 'simulation-signal-view.test.mjs asserts the restrictive 18 default; studio-export-controls.spec.ts covers simulation controls but not displayed traces; e2e-sequence.test.mjs covers canonical projection, not the SVG interaction.',
    'campaign': 'nis-ea-independent-20260924-run1 REPAIR_1_ACTIVE; no new campaign or registry.',
}, indent=2), encoding='utf-8')
work = {
    'goal_id': 'simulation-visibility-20261010', 'kind': 'repair', 'repository': str(ROOT),
    'modify_code': True, 'allow_repair': True, 'revision_before': baseline,
    'files_changed': FILES, 'before': before, 'unresolved_decisions': [],
    'required_outcomes': ['all_signals_accessible', 'all_sequence_events_accessible', 'non_obscuring_highlight', 'release_and_deploy'],
    'validation_requirements': ['targeted_frontend', 'typecheck', 'isolated_browser', 'release_gate', 'production_verification'],
    'repair': {'owner': 'PROJECT_PRODUCT', 'root_cause': 'Restrictive display defaults, inaccessible hard truncation and opaque SVG overlays.',
        'first_failing_layer': 'Frontend selection and SVG painting', 'reproduction': 'User screenshot: 18 selected, 473 dynamic matches, hover hides shared activation.',
        'evidence': [ref(evidence)], 'affected_files': FILES,
        'acceptance_criteria': ['Default all signals and all behaviors; reach every filtered selected signal/event through explicit bounded pages.', 'Hover and keyboard focus preserve lifelines, activation bars, arrows and labels.', 'Canonical signals and events remain unchanged.'],
        'targeted_tests': ['Signal default, page completeness and boundaries; actual UI navigation and highlight in existing studio controls suite.'],
        'weaken_assertions_to_pass': False},
    'action_scope': 'Authorized local UI source correction only. Pending historical image retention exception belongs to stranded-capacity-channels workload; this guard authorizes no image deletion or model repair.',
    'completion_status': 'IN_PROGRESS',
    'delivery': {'decision': 'YES', 'authorization': 'Standing verified NIS production delivery authorization', 'status': 'PENDING_STORAGE_EXCEPTION'},
}
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
