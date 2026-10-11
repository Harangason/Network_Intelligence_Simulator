import hashlib, json, shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
relative = 'backend/tests/test_simulation_observation.py'
before = out/'before'/relative
assert not before.exists()
before.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root/relative, before)
work['files_inspected'].append(relative)
work['revision_before'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                           for name in work['files_inspected']}
log = root/'backend/test-output/release-gates/delivery-efe7b22bb26e/da5ddb213950/backend-tests.log'
work.update(kind='repair', completion_status='REPAIRING', repair={
    'finding_ids': ['SIMULATION_CSV_PROVENANCE_SCHEMA', 'OBSOLETE_ROBOTICS_HARDWARE_GATE_ASSERTION'],
    'owner': 'SHARED',
    'independent_causes': ['PROJECT_PRODUCT: native scenario trace metadata absent from CSV field schema',
                          'TEST_DATA: robotics simulation test expects actual hardware proof to block valid saved assumptions'],
    'root_cause': 'CSV serialization rejects new explicit simulation evidence metadata. A mixed robotics artifact test retains the superseded actual-only completeness rule.',
    'first_failing_layer': 'CSV serializer; robotics artifact acceptance assertion',
    'reproduction': 'Complete isolated backend gate: 21654 passed, 2 failed; errors captured in backend-tests.log.',
    'evidence': [{'path':str(log.resolve()), 'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}],
    'affected_files': ['backend/nis/traces/universal_trace.py', 'backend/tests/test_simulation_parameter_defaults.py', relative],
    'affected_services': ['universal trace export', 'simulation parameter artifact'],
    'required_fix': 'Export simulation provenance without discarding fields. Verify valid native DDS simulation assumptions are complete without cross-technology bitrate or fabricated device evidence, and forged provenance is still rejected.',
    'acceptance_criteria': ['CSV and JSONL preserve scenario timing basis and false hardware/functional evidence',
                            'Saved native DDS assumptions permit simulation configuration, not hardware qualification',
                            'Forged DDS scenario provenance remains incomplete'],
    'targeted_tests': ['test_simulation_parameter_defaults.py', 'test_simulation_observation.py',
                       'test_wizard_generation.py::test_combined_wizard_creates_validated_model_without_reasoner'],
    'regression_scope': 'Complete mandatory release gate after targeted tests',
    'status': 'READY', 'weaken_assertions_to_pass': False,
})
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Repair plan and immutable failure evidence recorded.')
