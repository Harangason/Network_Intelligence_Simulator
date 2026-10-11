import hashlib
import json
import shutil
from pathlib import Path
folder = Path(__file__).resolve().parent
root = folder.parents[2]
files = ['backend/nis/engineering/routing/validation.py', 'backend/nis/engineering/capacity/sizing_service.py',
         'backend/tests/test_routing_prospective_model.py', 'backend/tests/test_communication_sizing_api.py']
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
revisions = {}
work = json.loads((folder / 'workload.json').read_text())
for name in files:
    source, before = root / name, folder / 'before' / name
    assert not before.exists(), 'Do not replace original evidence'
    before.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, before)
    revisions[name] = ref(source)['sha256']
    work['files_changed'].append(name)
    work['revision_before'][name] = revisions[name]
repair = {
    'goal_id': 'wizard-sizing-performance', 'kind': 'repair', 'repository': str(root),
    'modify_code': True, 'allow_repair': True, 'revision_before': revisions,
    'unresolved_decisions': [], 'repair': {
        'owner': 'PROJECT_PRODUCT',
        'root_cause': 'Each batch route reloads references through SQL despite a captured physical plan. Sizing rewrites already synchronized transmission metadata using a fresh source token, invalidating and reapproving unchanged canonical objects.',
        'first_failing_layer': 'Communication sizing adoption during capacity_timing continuation',
        'reproduction': 'Captured 552-device/1404-signal model replayed through real preview/apply in scripts/run-isolated-tests.py: 144.625 seconds, 20071 SQL execute calls, 694 route validations.',
        'evidence': [ref(folder / 'sizing-before-profile.txt'), ref(folder / 'sizing-before-stacks.txt'), ref(folder / 'delivery-blocker.json')],
        'affected_files': files,
        'acceptance_criteria': 'Current project snapshot checks every route without per-route SQL reads; repeat sizing preserves synchronized object versions and approved routes; stale tokens and atomic rollback still enforced; full release bounds unchanged.',
        'targeted_tests': 'SQL/snapshot validation equivalence and fresh snapshot after model edit; repeated real sizing adoption version preservation; existing stale-token and injected-failure rollback regression; same captured workload measured again.',
        'weaken_assertions_to_pass': False,
    },
}
(folder / 'performance-repair.json').write_text(json.dumps(repair, indent=2))
work['completion_status'] = 'REPAIRING'
work['performance_repair'] = ref(folder / 'performance-repair.json')
(folder / 'workload.json').write_text(json.dumps(work, indent=2))
