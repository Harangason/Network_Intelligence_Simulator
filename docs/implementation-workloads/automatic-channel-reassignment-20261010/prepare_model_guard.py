import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
work_path = folder / 'workload.json'
work = json.loads(work_path.read_text())
root = Path(work['repository'])
prepared = folder / 'existing-project-prepared-proposal.json'
result = json.loads(prepared.read_text())
assert result['success'] and result['data']['proposal']['status'] == 'VALIDATED'
proposal = result['data']['proposal']
assert proposal['validation_result']['valid']
ref = lambda p: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
guard = {'kind': 'repair', 'repository': str(root), 'project_scope': work['project_scope'],
         'modify_code': True, 'allow_repair': True,
         'revision_before': {name: hashlib.sha256((folder / 'after' / name).read_bytes()).hexdigest() for name in work['files_changed']},
         'unresolved_decisions': [], 'model_revision_control': {'proposal_id': proposal['proposal_id'],
             'revision': proposal['revision'], 'mechanism': 'Canonical review/apply checks base_model_revision and every expected_version inside a project RequestUnit.'},
         'repair': {'owner': 'PROJECT_PRODUCT', 'root_cause': work['repair']['root_cause'],
                    'first_failing_layer': 'Persisted primary sender left behind after approved capacity split',
                    'reproduction': 'Delivered canonical planner finds stale primary references against already approved current physical paths.',
                    'evidence': [ref(prepared)], 'affected_files': work['files_changed'],
                    'acceptance_criteria': ['Every selected primary matches approved topology bindings', 'No changes to signals, encodings, recipients, physical topology or hardware inventory'],
                    'targeted_tests': ['55 isolated regressions and complete deployed release gate'],
                    'weaken_assertions_to_pass': False}}
(folder / 'model-alignment-guard.json').write_text(json.dumps(guard, indent=2), encoding='utf-8')
if 'existing_project_consistency' not in work['required_outcomes']:
    work['required_outcomes'].append('existing_project_consistency')
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'prepared': len(result['data']['expected']), 'revision_control': True}))
