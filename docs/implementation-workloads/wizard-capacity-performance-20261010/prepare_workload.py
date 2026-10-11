"""Capture the pre-change baseline for the measured wizard performance repair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DIAG = HERE.parent / 'simulation-visibility-20261010'
files = ['backend/nis/communication/registry.py', 'backend/nis/engineering/capacity/service.py',
         'backend/tests/test_technology_registry_metadata.py', 'backend/tests/test_simulation_parameter_defaults.py']
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
assert not (HERE / 'workload.json').exists(), 'Preserve the original baseline.'
before = []
revisions = {}
for relative in files:
    source = ROOT / relative
    target = HERE / 'before' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    before.append(ref(target))
    revisions[relative] = ref(source)['sha256']
work = {'goal_id': HERE.name, 'kind': 'repair', 'repository': str(ROOT), 'modify_code': True,
    'allow_repair': True, 'revision_before': revisions, 'files_changed': files, 'before': before,
    'unresolved_decisions': [], 'required_outcomes': ['native_validation_reuse', 'scope_revision_input_isolation', 'full_wizard', 'release_and_deploy'],
    'validation_requirements': ['isolated_regression', 'release_gate', 'production_verification'],
    'repair': {'owner': 'PROJECT_PRODUCT', 'root_cause': 'Large calculation repeats pure native profile parameter validation thousands of times: 43/57 profiled seconds in resolution and 21 seconds inside validation.',
      'first_failing_layer': 'Capacity technology parameter validation',
      'reproduction': 'Real captured 50/250/250 nine-stage browser wizard exceeds 1200000ms; unchanged 20-minute boundary.',
      'evidence': [ref(DIAG / 'isolated-capacity-profile.log'), ref(DIAG / 'large-timeout-attachments.json')],
      'affected_files': files, 'acceptance_criteria': ['Reuse only exact JSON inputs for pure built-in validators during one calculation.',
        'Preserve technology, registry revision, strict evidence and mutable-result isolation; no sharing with another calculation or custom validator.',
        'Full unchanged release gate passes and the exact tested image is delivered.'],
      'targeted_tests': ['Registry metadata regression, capacity scenario defaults and native technology parameter isolation.'],
      'weaken_assertions_to_pass': False},
    'action_scope': 'Implement the measured performance repair; preserve every validation rule and test timeout. The already-failed immutable candidate continues its remaining browser cases unchanged.',
    'completion_status': 'IN_PROGRESS', 'delivery': {'decision': 'YES', 'authorization': 'Standing verified NIS production authorization and current Freigabe', 'target': 'canonical production stack on port 13500'}}
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Performance repair baseline captured.')
