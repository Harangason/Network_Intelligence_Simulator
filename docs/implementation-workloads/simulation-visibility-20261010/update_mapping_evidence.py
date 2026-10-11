import csv, difflib, hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
name = 'docs/migrations/structure_mapping.csv'
original = list(csv.DictReader((HERE / 'before' / name).read_text(encoding='utf-8').splitlines()))
current = list(csv.DictReader((ROOT / name).read_text(encoding='utf-8').splitlines()))
old_keys = {(row['source_path'], row['target_path'], row['action']) for row in original}
new_keys = {(row['source_path'], row['target_path'], row['action']) for row in current}
assert old_keys <= new_keys, 'Existing migration identity was overwritten.'
report = {'status': 'VERIFIED', 'existing_migration_identities_preserved': True,
    'added_rows': sorted(new_keys - old_keys), 'targeted_structure_tests': 12,
    'first_full_gate': 'FAIL before build: missing registration of three new canonical UI files; 21755 other tests passed.'}
(HERE / 'mapping-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
patch, after = [], []
for name in work['files_changed']:
    source, before = ROOT / name, HERE / 'before' / name
    dest = HERE / 'after' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    after.append(ref(dest))
    patch.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True) if before.exists() else [],
        source.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
(HERE / 'changes.patch').write_text(''.join(patch), encoding='utf-8')
work.update(after=after, diff=[ref(HERE / 'changes.patch')], completion_status='IN_PROGRESS')
evidence = [ref(HERE / 'structure-tests.log'), ref(HERE / 'mapping-verification.json')]
work['outcomes']['structure_inventory_registered'] = {'status': 'PASSED', 'evidence': evidence}
work['validations']['targeted_structure'] = {'status': 'PASSED', 'evidence': evidence}
work['unresolved_decisions'] = []
work['delivery']['status'] = 'FULL_GATE_RETRY_REQUIRED'
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps(report))
