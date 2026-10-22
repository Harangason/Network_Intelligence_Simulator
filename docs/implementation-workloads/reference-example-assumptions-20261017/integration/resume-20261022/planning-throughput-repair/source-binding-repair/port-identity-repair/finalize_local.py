"""Freeze verified local/native identity repair; never claim original/release PASS."""
import ast
import difflib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text(encoding='utf8'))
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

identity = read(OUT / 'current-input-identity.json')
scope = read(OUT / 'source-scope-proof.json')
assert identity['source_sha256'] == scope['canonical_after']['source_sha256']
aggregate = read(OUT / 'regression-aggregate.json')
assert aggregate['distinct_latest_pass'] == 616 and aggregate['single_full_green_run'] is False
for run in aggregate['runs']:
    xml = Path(run['xml']['path'])
    assert ref(xml) == run['xml']
    assert all(all(case.find(key) is None for key in ('failure', 'error', 'skipped'))
               for case in ET.parse(xml).getroot().iter('testcase'))
module = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
module_hash = ref(module)['sha256']
assert read(OUT / 'native-source-freeze.json')['module']['sha256'] == module_hash
controls = []
for case, count in (('ports-positive', 4), ('ports-counter', 4), ('functions-positive', 2), ('functions-counter', 2)):
    folder = OUT / ('native-' + case)
    result = read(folder / 'result.json')
    assert result['status'] == 'PASS' and result['actual_native_responses'] == 1
    assert result['local_reasoner_sha256'] == module_hash and len(result['selected_identities']) == count
    assert result['canonical_writes'] is result['complete_original_acceptance'] is False
    request, response = read(folder / 'request.json'), read(folder / 'response.json')
    assert request['model'] == 'qwen3.8:27b' and request['options']['num_predict'] == 8192
    assert request['options']['num_ctx'] <= 131072 and request['stream'] is True
    assert response['done'] is True and response.get('done_reason') != 'length'
    controls.append({'case': case, **{name: ref(folder / (name + '.json'))
        for name in ('result', 'request', 'response')}})
write('native-selected-controls.json', {'status': 'PASS', 'actual_native_responses': 4,
    'local_reasoner_sha256': module_hash, 'results': controls,
    'complete_original_acceptance': False, 'canonical_writes': False})

files = ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py',
         'backend/tests/test_reference_selected_identity.py')
after, diffs = [], []
for name in files:
    live, before, saved = ROOT / name, OUT / 'before' / name, OUT / 'after' / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(live.read_bytes())
    diff = OUT / (live.name + '.diff')
    diff.write_text(''.join(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True) if before.exists() else [],
        live.read_text(encoding='utf8').splitlines(True), fromfile='before/' + name, tofile='after/' + name)), encoding='utf8')
    after.append(ref(saved)); diffs.append(ref(diff))
write('before-new-files.json', {'absent_before': ['backend/tests/test_reference_selected_identity.py'],
    'basis': 'Initial before-apply guard accepted revision_before=null before Add File; no prior file was overwritten.'})
old = ast.parse((OUT / 'before/backend/tests/test_reference_reasoner.py').read_text(encoding='utf8'))
new = ast.parse((ROOT / 'backend/tests/test_reference_reasoner.py').read_text(encoding='utf8'))
defs = lambda tree: {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
left, right = defs(old), defs(new)
changed = [key for key in left if ast.dump(left[key], include_attributes=False) != ast.dump(right[key], include_attributes=False)]
assert set(changed) == {'reasoner_with_transport', 'test_stage_decoder_narrows_outputs_but_does_not_modify_public_schema'}
assert set(left) <= set(right)
write('fixture-assertion-proof.json', {'changed_functions': changed,
    'complete_reasoner_regression_cases': 129,
    'all_other_reasoner_test_functions_AST_unchanged': True,
    'notes': ['Mock transport converts only unique authored rows with unchanged immutable identity; invalid rows are never deduplicated or repaired.',
              'Private schema assertion now checks exact required keys and forbidden immutable fields; public-schema equality assertion retained.',
              'All foreign-owner, duplicate-ID, role/name/member/quantity/source and strict merge negative tests retained.']})
validation = [ref(OUT / name) for name in ('regression-aggregate.json', 'first-green.xml', 'adjacent-green.xml',
    'red.xml', 'source-scope-proof.json', 'native-selected-controls.json', 'native-source-freeze.json', 'fixture-assertion-proof.json')]
validation.extend(ref(OUT.parent / name) for name in ('actual-original-projection-proof.json', 'vehicle-all-source-intervals.json',
    'robot-all-source-intervals.json', 'portfolio-current-audit/execution-review.json'))
if (OUT / 'portfolio-current-audit/execution-review.json').is_file():
    audit = read(OUT / 'portfolio-current-audit/execution-review.json')
    assert audit['profiles'] == 100 and audit['source_reconstruction_and_all_requirement_ids_verified']
    validation.extend(ref(OUT / 'portfolio-current-audit' / name) for name in ('canonical-audit.json', 'execution-review.json'))
freeze = {**identity, 'complete_regression_cases': 616, 'complete_regressions_passed': True,
    'two_disjoint_complete_green_runs': True, 'single_full_green_run': False, 'native_selected_control_cases': 4,
    'frozen_affected_files': {name: ref(ROOT / name)['sha256'] for name in files},
    'validation_evidence': validation, 'no_original_acceptance_or_full_gate_claim': True}
write('candidate-prepare-freeze.json', freeze)
work = read(OUT / 'workload.json')
work.update(status='LOCAL_CHECKS_AND4_NATIVE_CONTROLS_VALIDATED_WAITING_NORMAL_CANDIDATE_AND_BOTH_ORIGINALS',
    files_changed=list(files), after=after, diff=diffs)
if ref(OUT / 'before-new-files.json') not in work['before']:
    work['before'].append(ref(OUT / 'before-new-files.json'))
work['tests']['adjacent_complete'] = {'passed': 468, 'failed': 0, 'exit_code': 0, 'xml': ref(OUT / 'adjacent-green.xml')}
work['tests'].pop('adjacent_running', None)
work['tests']['distinct_latest_pass'] = 616
work['tests']['native_selected_controls'] = ref(OUT / 'native-selected-controls.json')
work['outcomes'] = {name: {'status': 'PASSED', 'evidence': [ref(OUT / 'source-scope-proof.json'),
    ref(OUT / 'regression-aggregate.json'), ref(OUT / 'native-selected-controls.json')]}
    for name in work['required_outcomes']}
work['validations'] = {name: {'status': 'PASSED', 'evidence': validation[:8]} for name in work['validation_requirements']}
write('workload.json', work)
write('local-result.json', {'at_utc': datetime.now(timezone.utc).isoformat(), **identity,
    'backend_distinct_pass': 616, 'native_controls_pass': 4, 'source_freeze': ref(OUT / 'candidate-prepare-freeze.json'),
    'complete_original_acceptance': False, 'full_release_pass': False, 'productive_delivery': False})
print(json.dumps(read(OUT / 'local-result.json'), ensure_ascii=False))
