import hashlib
import json
import shutil
from pathlib import Path

out = Path(__file__).parent.resolve()
root = out.parents[2]
path = out / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
name = 'backend/tests/test_routing_prospective_model.py'
if name not in work['files_inspected']:
    work['files_inspected'].append(name)
    before = out / 'before' / name
    before.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, before)
work.setdefault('repair_history', []).append(work['repair'])
evidence = [out / 'full-validate-2-profile.txt', out / 'catalog-browser.json']
work['repair'] = {
    'finding_ids': ['ROUTING_RETURN_REPEATED_SQL'], 'owner': 'PROJECT_PRODUCT', 'category': 'PROJECT_PRODUCT',
    'cause': 'REPEATED_NATIVE_ROUTING_SQL',
    'root_cause': 'The actual isolated routing validation profile performs 6,511 SQL statements and 12,884 connection/savepoint contexts for 766 routes. Latest regular browser candidate passes all nine model parameter-return cycles but first routing return exceeds unchanged 60-second readiness.',
    'first_failing_layer': 'Complete proposal routing validation',
    'reproduction': 'Current five-case browser: four pass; large passes model detours then fails pending routing refresh. Existing complete SQL test profiling observes routing validation unchanged.',
    'evidence': [{'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()} for file in evidence],
    'affected_files': ['backend/nis/agent/tools/proposal_service.py', name],
    'acceptance_criteria': ['Capture complete selected canonical model once per routing proposal validation', 'Use existing strict snapshot RoutingValidator, retaining all route payload/physical/duplicate/timing/reference rules', 'Never reuse snapshot across requests or add human approval/model writes', 'Preserve PERIODIC_ACQUISITION prospective overlay and exclude-route semantics', 'Verify SQL and snapshot outputs are identical; edited/deleted physical links and foreign project snapshots still fail', 'Keep every test and readiness deadline and deliver exact fully tested image'],
    'targeted_tests': ['test_routing_prospective_model.py', 'test_proposal_capacity.py', 'test_proposals.py', 'test_agent_periodic_acquisition.py', 'large actual repeated-return browser'],
    'weaken_assertions_to_pass': False, 'status': 'READY',
}
work['revision_before'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings'] = ['Large real routing parameter-return refresh exceeds readiness; model detours pass', 'Complete gate and production delivery pending']
work['completion_status'] = 'REPAIRING'
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
with (out / 'diagnosis.md').open('a', encoding='utf-8') as stream:
    stream.write('\nRegular candidate cec9d47d49b0: four browser cases pass; large successfully saves/reloads/returns nine times before model approval, then fails first routing return at the unchanged 60-second readiness budget. The isolated routing profile has 6,511 SQL executions/12,884 connection contexts for 766 routes. Complete current canonical snapshot is already supported by strict RoutingValidator and has SQL-equivalence/foreign-context/physical-removal tests. No deployment.\n')
print('Measured routing return repair planned.')
