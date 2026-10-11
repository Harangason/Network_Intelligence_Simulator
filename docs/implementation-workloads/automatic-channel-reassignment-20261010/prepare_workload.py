import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
files = ['backend/nis/engineering/network/physical_ports.py',
         'backend/nis/agent/tools/wizard_generation.py',
         'backend/tests/test_physical_ports.py',
         'backend/tests/test_wizard_large_routing.py']
revisions = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
before = folder / 'before'
before.mkdir(exist_ok=True)
for name in files:
    target = before / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((root / name).read_bytes())
diagnosis = folder / 'diagnosis.json'
diagnosis.write_text(json.dumps({
    'root_cause': 'Capacity splitting drops old drawing ports but materialization does not reconcile the primary Message.hardware_interface_id with the approved physical senders. It creates replacement channels even when the same reviewed connector moves entirely to one network. Manual assignment and zoning already reconcile the primary.',
    'evidence': {'physical_ports_sha256': revisions[files[0]], 'wizard_generation_sha256': revisions[files[1]],
                 'existing_project_evidence': str(root / 'docs/implementation-workloads/studio-toolbar-trace-defaults-20261009/light-warning-evidence.json')},
    'owner': 'PROJECT_PRODUCT',
    'constraints': ['No invented routes or changed encodings', 'Preserve parallel physical channels', 'No removal of inventory resources or suppression of actual invalid bindings', 'Preview/apply remains revision controlled and atomic']
}, indent=2), encoding='utf-8')
ref = lambda p: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
work = {'goal_id': folder.name, 'kind': 'repair', 'repository': str(root), 'project_scope': '20261009072206008-4bb505f1',
        'modify_code': True, 'allow_repair': True, 'revision_before': revisions, 'files_inspected': files,
        'required_outcomes': ['consistent_primary_binding', 'single_channel_reuse', 'parallel_channel_preservation', 'wizard_regression', 'production_delivery'],
        'validation_requirements': ['targeted_regression', 'release_gate', 'live_verification'],
        'unresolved_decisions': [], 'remaining_findings': ['Implementation and delivery pending'],
        'completion_status': 'PLANNING', 'files_changed': [],
        'implementation_plan': ['Reconcile primary and all physical transmission bindings in the shared materializer', 'Reuse a previously connected channel only on an unambiguous complete move; retain parallel channels', 'Pass prior topology from capacity remediation', 'Verify split/apply/reload and unchanged signals in isolated SQL and full release'],
        'repair': {'owner': 'PROJECT_PRODUCT', 'root_cause': json.loads(diagnosis.read_text())['root_cause'],
                   'first_failing_layer': 'Canonical physical channel/message reconciliation',
                   'reproduction': 'Stored Licht message retains detached original channel although approved topology binds its real sender on Komfort_02; shared source and existing tests confirm only configuration changes.',
                   'evidence': [ref(diagnosis)], 'affected_files': files,
                   'acceptance_criteria': ['Primary belongs to actual reviewed source channels', 'One-to-one channel moves preserve identity', 'Parallel channels are never collapsed', 'Missing or invalid bindings still fail validation'],
                   'targeted_tests': ['test_physical_ports.py', 'test_wizard_large_routing.py'], 'weaken_assertions_to_pass': False},
        'before': [ref(before / name) for name in files],
        'delivery': {'decision': 'YES', 'basis': 'Standing AGENTS.md authorization after complete PASS release gate', 'status': 'PENDING'}}
(folder / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'workload': str(folder / 'workload.json'), 'files': len(files)}))
