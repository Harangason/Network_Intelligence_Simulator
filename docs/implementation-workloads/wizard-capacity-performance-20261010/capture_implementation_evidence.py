"""Preserve the bounded patch and successful diagnostic/isolated checks."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
work_path = HERE / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
comparison = json.loads((HERE / 'capacity-comparison.json').read_text(encoding='utf-8'))
assert comparison['success'] and comparison['data']['status'] == 'EXACT_RESULTS_PRESERVED'
assert '537 passed' in (HERE / 'isolated-regression-complete.log').read_text(encoding='utf-8')
after, diff = [], []
for relative in work['files_changed']:
    source = ROOT / relative
    target = HERE / 'after' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    after.append(ref(target))
    before = HERE / 'before' / relative
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),
        source.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + relative, tofile='after/' + relative))
patch = HERE / 'changes.patch'
patch.write_text(''.join(diff), encoding='utf-8')
work['after'] = after
work['diff'] = [ref(patch)]
proof = {'status': 'PASSED', 'evidence': [ref(HERE / 'isolated-regression-complete.log'), ref(HERE / 'capacity-comparison.json')]}
work['outcomes'] = {'native_validation_reuse': proof, 'scope_revision_input_isolation': proof,
    'full_wizard': {'status': 'PENDING', 'evidence': []}, 'release_and_deploy': {'status': 'PENDING', 'evidence': []}}
work['validations'] = {'isolated_regression': proof, 'release_gate': {'status': 'PENDING', 'evidence': []},
    'production_verification': {'status': 'PENDING', 'evidence': []}}
work['remaining_findings'] = ['A new complete release gate and exact production deployment are required.']
work['delivery']['status'] = 'IMPLEMENTED_AWAITING_NEW_FULL_GATE'
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Bounded source patch and 537 passing regressions captured; no delivery claimed.')
