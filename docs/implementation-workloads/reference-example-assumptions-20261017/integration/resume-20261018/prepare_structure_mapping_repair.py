"""Plan a canonical structure-map refresh; never edits the canonical map."""
import csv
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent / 'structure-mapping-repair'
OUT.mkdir(exist_ok=True)
TARGET = ROOT / 'docs/migrations/structure_mapping.csv'
before = TARGET.read_bytes()
spec = importlib.util.spec_from_file_location('structure_map_owner', ROOT / 'scripts/migrations/structure_mapping.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
old = list(csv.DictReader(before.decode('utf-8-sig').splitlines()))
covered = {row['source_path'] for row in old} | {row['target_path'] for row in old}
missing = sorted(set(owner.inventory()) - covered)
assert missing, 'No reproduced missing inventory entries'
after = owner.reconcile().encode('utf-8')
new = list(csv.DictReader(after.decode('utf-8').splitlines()))
by_pair = {(row['source_path'], row['target_path']): row for row in new}
for row in old:
    preserved = by_pair[(row['source_path'], row['target_path'])]
    assert preserved['action'] == row['action'], 'Existing migration action changed'
    assert preserved['data_impact'] == row['data_impact'], 'Existing data-impact record changed'
assert set(owner.inventory()) <= ({row['source_path'] for row in new} | {row['target_path'] for row in new})
(OUT / 'before.csv').write_bytes(before)
(OUT / 'after.csv').write_bytes(after)
(OUT / 'changes.diff').write_text(''.join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True), fromfile='before/docs/migrations/structure_mapping.csv', tofile='after/docs/migrations/structure_mapping.csv')), encoding='utf-8')
evidence = OUT.parent / 'joint-backend-completion.log'
workload = {'repository': str(ROOT), 'kind': 'repair', 'modify_code': True, 'allow_repair': True,
    'status': 'PLANNING', 'requested_change': 'Register new reference-design files through the existing structure mapping owner; preserve all migration transitions.',
    'revision_before': {'docs/migrations/structure_mapping.csv': hashlib.sha256(before).hexdigest()},
    'files_changed': ['docs/migrations/structure_mapping.csv'], 'unresolved_decisions': [],
    'required_outcomes': ['inventory_covered', 'transitions_preserved'], 'validation_requirements': ['structure_guards'],
    'repair': {'owner': 'PROJECT_PRODUCT', 'finding_ids': ['REFERENCE_FILES_MISSING_STRUCTURE_MAP'],
        'root_cause': 'New reference-design test files were not registered in the canonical repository structure inventory.',
        'first_failing_layer': 'Repository structure metadata; the existing guard correctly rejects incomplete coverage.',
        'reproduction': 'test_structure_completion.py::test_mapping_covers_current_application_and_every_transition',
        'affected_files': ['docs/migrations/structure_mapping.csv'], 'required_fix': 'Use scripts/migrations/structure_mapping.py.reconcile without changing test assertions or application behavior.',
        'acceptance_criteria': ['Current inventory is fully covered', 'Every existing source/target transition, action and data-impact record retained'],
        'targeted_tests': ['backend/tests/test_structure_completion.py', 'backend/tests/test_structure_architecture.py'],
        'weaken_assertions_to_pass': False, 'evidence': [{'path': str(evidence), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}]}}
(OUT / 'workload.json').write_text(json.dumps(workload, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'PLANNED', 'missing': missing, 'old_rows': len(old), 'new_rows': len(new), 'existing_transitions_preserved': True}), flush=True)
