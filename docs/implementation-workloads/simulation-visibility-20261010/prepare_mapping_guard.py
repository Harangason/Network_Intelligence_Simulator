import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
name = 'docs/migrations/structure_mapping.csv'
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
dest = HERE / 'before' / name
assert not dest.exists()
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_bytes((ROOT / name).read_bytes())
work['files_changed'].append(name)
work['before'].append({'path': str(dest), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
work['required_outcomes'].append('structure_inventory_registered')
work['validation_requirements'].append('targeted_structure')
work['repair']['affected_files'].append(name)
work['repair']['root_cause'] += ' New canonical UI files also need the mandated structure mapping registration.'
work['repair']['targeted_tests'].append('backend/tests/test_structure_completion.py and test_structure_architecture.py through run-isolated-tests.py')
work['delivery']['failed_first_full_gate'] = str(ROOT / 'backend/test-output/release-gates/delivery-3ac4ef4dbc5b/edcb662fdc90/receipt.json')
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
work['revision_before'] = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() if (ROOT / n).exists() else None for n in work['files_changed']}
(HERE / 'mapping-before-apply-guard.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
