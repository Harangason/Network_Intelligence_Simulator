import hashlib, json
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history', []).append(work['repair'])
base = root/'backend/test-output/release-gates/delivery-e9e540f4d7a2/951b0d517929/browser'
evidence = [{'path':str(file.resolve()), 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            for file in sorted(base.glob('wizard-*/error-context.md'))]
work['repair'] = {
    'finding_ids': ['RESTORE_TEST_ROUTE_CLEANUP_RACE', 'NATIVE_CONFIGURATION_ASSERTIONS'],
    'owner': 'TEST_DATA',
    'root_cause': 'The delayed real request handler is removed before it finishes, causing route.continue to be handled twice. Nonautomotive assertions expect missing device evidence while native condition/rate findings actually block the saved configuration.',
    'first_failing_layer': 'Playwright route handler cleanup and outdated test assertion',
    'reproduction': 'Full browser suite: new small route.continue already handled; I2C device key undefined; Modbus native dependency mismatch instead of missing proof.',
    'evidence': evidence,
    'affected_files': ['frontend/e2e/wizard.spec.ts'],
    'acceptance_criteria': ['Await request handler completion without swallowing its errors',
                            'Preserve restore spinner, same run, saved rates, no START and no automatic model application assertions',
                            'Assert native dependency errors remain blockers, hardware sources are not invented, and no simulation job starts'],
    'targeted_tests': ['new small wizard', 'Raspberry Pi I2C', 'Raspberry Pi Modbus RTU'],
    'weaken_assertions_to_pass': False, 'status':'READY',
}
work['revision_before'] = {name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                           for name in work['files_inspected']}
work.update(completion_status='REPAIRING', remaining_findings=[
    'Large browser frontier 3/9 exceeded parameter phase budget; diagnostic profiling pending.'])
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Browser repair plan recorded; large-phase performance remains open.')
