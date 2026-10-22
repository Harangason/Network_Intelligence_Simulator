"""Finalize only the verified structure-map repair, not the joint release."""
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent / 'structure-mapping-repair'
before = list(csv.DictReader((OUT / 'before.csv').read_text().splitlines()))
after = list(csv.DictReader((ROOT / 'docs/migrations/structure_mapping.csv').read_text().splitlines()))
new = {(row['source_path'], row['target_path']): row for row in after}
assert all((row['source_path'], row['target_path']) in new and
           all(new[(row['source_path'], row['target_path'])][key] == row[key] for key in ('action', 'data_impact'))
           for row in before)
assert (ROOT / 'docs/migrations/structure_mapping.csv').read_bytes() == (OUT / 'after.csv').read_bytes()
suites = ET.parse(OUT / 'regressions.xml').getroot().iter('testsuite')
counts = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
for suite in suites:
    for key in counts:
        counts[key] += int(suite.get(key, 0))
assert counts == {'tests': 12, 'failures': 0, 'errors': 0, 'skipped': 0}, counts
proof = {'status': 'SCOPED_MAPPING_REPAIR_VERIFIED', 'before_rows': len(before), 'after_rows': len(after),
         'existing_transitions_preserved': True, 'test_counts': counts, 'joint_release_pass': False,
         'native_original_simulations': 'PENDING', 'production_changed': False}
(OUT / 'transition-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')


def ref(name):
    path = OUT / name
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


workload = json.loads((OUT / 'workload.json').read_text())
workload.update(status='READY_FOR_REVIEW', before=[ref('before.csv')], after=[ref('after.csv')], diff=[ref('changes.diff')],
    delivery={'decision': 'NOT_APPLICABLE', 'reason': 'This scoped repair changes only repository structure metadata, with no runtime code or deployment artifact. The authorized full joint image release remains required and pending in the parent workload.'},
    outcomes={'inventory_covered': {'status': 'PASSED', 'evidence': [ref('regressions.xml')]},
              'transitions_preserved': {'status': 'PASSED', 'evidence': [ref('transition-proof.json')]}},
    validations={'structure_guards': {'status': 'PASSED', 'evidence': [ref('regressions.xml'), ref('regressions.log')]}},
    completion_status='Scoped metadata repair verified; joint original simulation and productive delivery remain pending')
(OUT / 'workload.json').write_text(json.dumps(workload, indent=2) + '\n', encoding='utf-8')
print(json.dumps(proof), flush=True)
