"""Snapshot the verified browser-test repair scope after the failed gate ends."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GATE = ROOT / 'backend/test-output/release-gates/delivery-dde7985139ee/cbeea5a4f97b'

def reference(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

receipt = json.loads((GATE / 'receipt.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'FAIL', 'Wait for the failed gate to stop before repairing verification.'
files = ['frontend/e2e/safety-assurance.spec.ts', 'frontend/e2e/studio-export-controls.spec.ts']
before = []
for relative in files:
    target = HERE / 'before' / relative
    assert not target.exists(), 'Do not overwrite original repair snapshots.'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / relative).read_bytes())
    before.append(reference(target))
evidence = [reference(HERE / 'finding.md'), reference(GATE / 'receipt.json')]
for directory in ('safety-assurance-safety-re-e80b4-unapproved-safety-assurance',
                  'studio-export-controls-sim-22341-controls-simulation-display'):
    evidence.append(reference(GATE / 'browser' / directory / 'error-context.md'))
work = {
    'goal_id': HERE.name, 'goal_type': 'repair', 'kind': 'repair',
    'repository': str(ROOT), 'modify_code': True, 'allow_repair': True,
    'campaign_id': 'nis-ea-independent-20260924-run1',
    'project_scope': 'NIS release browser verification only; application source unchanged',
    'revision_before': {name: reference(ROOT / name)['sha256'] for name in files},
    'required_outcomes': ['semantic_safety_selector', 'registered_catalog_fixture', 'production_delivery'],
    'validation_requirements': ['targeted_browser_regression', 'full_release_gate'],
    'unresolved_decisions': [], 'files_changed': files, 'before': before,
    'constraints': ['Preserve all original assertions and timeouts', 'No product fallback',
                    'Reuse exact application image when only verification changes',
                    'The separate 13-point UI proposal still awaits approval'],
    'repair': {
        'owner': 'SHARED',
        'independent_causes': ['Exact wrapping-select label locator includes option content',
                               'Empty catalog and technology scope in an enabled-Start UI fixture'],
        'root_cause': 'Browser selector misuse and incomplete native-format fixture, not a product fallback defect',
        'first_failing_layer': 'Browser verification adapter and fixture',
        'reproduction': 'Safety Norm selectOption times out while accessible combobox Norm is visible; empty native catalog keeps Start correctly disabled',
        'evidence': evidence, 'affected_files': files,
        'acceptance_criteria': ['Safety save/reload/CAS version and unapproved state assertions remain intact',
                                'No raw JSON editor',
                                'Start disabled with catalog unresolved and no universal-format flash',
                                'Start enabled after real registered Ethernet catalog resolves',
                                'All 125 signals and 405 sequence events remain reachable',
                                'Complete release PASS for unchanged immutable image before production'],
        'targeted_tests': ['Safety requirement persistence case', 'Simulation signal/sequence display case'],
        'weaken_assertions_to_pass': False,
    },
    'delivery': {'decision': 'YES', 'authorization': 'Vorgeschriebenen Release-Prüflauf durchführen und danach produktiv übernehmen',
                 'target': 'canonical NetworkIS production', 'status': 'PENDING_REQUIRED_PASS'},
    'tests': {'status': 'REPAIR_PLANNED'}, 'completion_status': 'REPAIR_PLANNED',
    'remaining_findings': ['Correct verification, then full current-input gate and exact-image production delivery'],
}
(HERE / 'workload.json').write_text(json.dumps(work, indent=2) + '\n', encoding='utf-8')
print('Verified two-file repair scope prepared; immutable image:', receipt['image_id'])
