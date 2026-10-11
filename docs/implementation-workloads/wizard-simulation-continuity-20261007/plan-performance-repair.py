import hashlib, json, shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history', []).append(work['repair'])
evidence = out/'parameter-generation-profile.txt'
work['repair'] = {
    'finding_ids': ['LARGE_PARAMETER_PHASE_REPEATED_WORK'], 'owner': 'PROJECT_PRODUCT',
    'root_cause': 'The profiled parameter phase takes 615 seconds: zoning apply already dimensions and calculates the new buses, then generate_parameters repeats sizing preview. Bus grouping copies the entire registered profile for every message although it only needs medium_access_model (35.5 seconds over three grouping calls). Native rate planning also recomputes identical payload frames at each fixed operating point.',
    'first_failing_layer': 'Parameter generation shared sizing and grouping services',
    'reproduction': 'Existing full captured 50/250/250 isolated test, cProfile observes generate_parameters unchanged.',
    'evidence': [{'path': str(evidence.resolve()), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}],
    'affected_files': ['backend/nis/agent/tools/wizard_generation.py', 'backend/nis/agent/tools/validation.py', 'backend/nis/engineering/capacity/dimensioning.py'],
    'acceptance_criteria': ['Reuse completed zoning dimensioning for the same unchanged physical buses', 'Read detached profile medium access once per technology per grouping', 'Reuse native frame calculations only within an identical operating point and payload size', 'Preserve all messages, scopes, provenance, native validation and existing watchdog budgets'],
    'targeted_tests': ['test_simulation_parameter_defaults.py', 'test_technology_parameter_review.py', 'test_communication_dimensioning.py', 'test_spatial_zoning.py', 'exact confirmed 50/250/250 graph'],
    'weaken_assertions_to_pass': False, 'status': 'READY',
}
for name in ['backend/nis/engineering/capacity/dimensioning.py']:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before = out/'before'/name
        before.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/name, before)
work['revision_before'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status'] = 'REPAIRING'
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Measured performance repair planned; full large graph and watchdog remain required.')
