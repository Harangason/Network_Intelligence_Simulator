"""Freeze actual green checks without claiming either original or delivery."""
import ast
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


cases, runs = {}, []
for name in ('final-reasoner-regressions.xml', 'final-adjacent-regressions.xml'):
    path = OUT / name
    tests = list(ET.parse(path).getroot().iter('testcase'))
    assert tests
    for test in tests:
        assert all(test.find(key) is None for key in ('failure', 'error', 'skipped')), test.attrib
        identity = test.attrib['classname'] + '::' + test.attrib['name']
        assert identity not in cases, 'Final regression scopes must be disjoint.'
        cases[identity] = {'id': identity, 'latest_pass': True, 'xml': ref(path)}
    runs.append({'xml': ref(path), 'cases': len(tests), 'passed': len(tests), 'failed': 0, 'skipped': 0})
assert len(cases) > 587
write('regression-aggregate.json', {'runs': runs, 'distinct_latest_pass': len(cases), 'cases': list(cases.values()),
    'two_disjoint_complete_green_runs': True, 'single_full_green_run': False,
    'earlier_failures_preserved': [ref(OUT / name) for name in ('red.xml', 'independent-red.xml', 'first-green.xml', 'scoped-green.xml')]})
frontend = read(OUT / 'frontend-result.json')
assert frontend['tests_exit'] == frontend['typecheck_exit'] == 0
assert '# tests 160' in (OUT / 'frontend-regressions.log').read_text(encoding='utf8')
projected_frontend = read(OUT / 'projection-sync-repair/frontend-result.json')
assert projected_frontend['tests_exit'] == projected_frontend['typecheck_exit'] == 0
assert '# tests 160' in (OUT / 'projection-sync-repair/frontend-regressions.log').read_text(encoding='utf8')
image_proof = read(OUT / 'projection-sync-repair/independent-image-source-proof.json')
assert image_proof['all_normalized_application_files_exact'] and image_proof['source_file_count'] == 2313
assert image_proof['host_source_sha256'] == image_proof['actual_image_source_sha256'] == '36697938df50d658e8a6d7a88e5e5618758e1b407db9efe47f3e127487eb6056'
scope = read(OUT / 'source-scope-proof.json')
assert scope['canonical_after']['source_sha256'] == '36697938df50d658e8a6d7a88e5e5618758e1b407db9efe47f3e127487eb6056'
native = read(OUT / 'native-ordered-bindings/result.json')
assert native['status'] == 'PASS' and native['actual_native_responses'] == 1
boundary = read(OUT / 'native-ordered-boundary/result.json')
assert boundary['status'] == 'PASS' and boundary['identities'] == 8 and boundary['fact_bindings'] == 16
binding = read(OUT / 'native-scope-binding.json')
assert binding['native_source_sha256'] == native['local_reasoner_sha256']
assert boundary['local_reasoner_sha256'] == native['local_reasoner_sha256']
assert binding['current_local_reasoner_sha256'] == ref(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py')['sha256']
assert binding['all_module_level_decoder_runtime_transport_helpers_AST_exact']
assert read(OUT / 'portfolio-current-audit/execution-review.json')['profiles'] == 100
assert read(OUT / 'portfolio-current-audit/execution-review.json')['source_reconstruction_and_all_requirement_ids_verified']

files = ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/nis/domain/inventory-vocabulary.json',
    'frontend/src/features/agent/lib/inventory-vocabulary.json',
    'backend/tests/test_reference_reasoner.py', 'backend/tests/test_reference_planning_throughput.py',
    'backend/tests/test_reference_source_binding.py')
after, diffs = [], []
for name in files:
    live, before, snapshot = ROOT / name, OUT / 'before' / name, OUT / 'after' / name
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(live.read_bytes())
    diff = OUT / (live.name + '.diff')
    diff.write_text(''.join(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True) if before.exists() else [],
        live.read_text(encoding='utf8').splitlines(True), fromfile='before/' + name, tofile='after/' + name)), encoding='utf8')
    after.append(ref(snapshot))
    diffs.append(ref(diff))

# Untouched test functions, including all their domain assertions and exception
# checks, remain byte-independent AST equals. Changed fixtures are listed openly.
fixture_changes = []
for name in ('test_reference_reasoner.py', 'test_reference_planning_throughput.py'):
    before = ast.parse((OUT / 'before/backend/tests' / name).read_text(encoding='utf8'))
    current = ast.parse((ROOT / 'backend/tests' / name).read_text(encoding='utf8'))
    definitions = lambda tree: {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    left, right = definitions(before), definitions(current)
    assert set(left) <= set(right)
    changed = [key for key in left if ast.dump(left[key], include_attributes=False) != ast.dump(right[key], include_attributes=False)]
    fixture_changes.append({'file': name, 'changed_functions': changed, 'unchanged_functions': len(left) - len(changed),
        'all_unchanged_assertions_and_exception_checks_AST_exact': True})
write('fixture-assertion-proof.json', {'files': fixture_changes,
    'changes': ['Private EXISTING arrays become one keyed EXISTING_BATCH; identity, foreign fact, member, role and quantity negatives remain.',
        'Function/requirement packet bound changes4to16 under explicit human batching request; exact full ordered coverage and pre-IO completion asserted.',
        'Authored late-scope fixture adds two functions so the new16fact bound still exercises a second scope; original texts are untouched.',
        'The native object-property-count gap is independently RED; finite ordered single-ID nodes now encode the unchanged8 bound and exclude duplicate identities without maxProperties.',
        'Terminal diagnostic assertion still checks one terminal entry, with added requirement that both rejected attempts are logged.',
        'Mock transport packs only unique authored identities; it never deduplicates an invalid duplicate-ID fixture.'],
    'actual_runtime_guards_AST_unchanged': True, 'regressions': ref(OUT / 'regression-aggregate.json')})

spec = importlib.util.spec_from_file_location('source_binding_delivery_identity', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
identity = {'source_sha256': source, 'commit_id': commit, 'verification_sha256': verification}
assert source == scope['canonical_after']['source_sha256']
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
write('current-input-identity.json', identity)
frozen = read(OUT.parent / 'candidate-prepare-freeze.json')['frozen_affected_files']
frozen.update({name: ref(ROOT / name)['sha256'] for name in files})
evidence = [ref(OUT / name) for name in ('regression-aggregate.json', 'final-reasoner-regressions.xml',
    'final-adjacent-regressions.xml', 'fixture-assertion-proof.json', 'source-scope-proof.json',
    'native-ordered-bindings/result.json', 'native-ordered-boundary/result.json', 'native-scope-binding.json', 'actual-original-projection-proof.json',
    'vehicle-all-source-intervals.json', 'robot-all-source-intervals.json', 'vehicle-hardware-worklist-proof.json',
    'portfolio-current-audit/canonical-audit.json', 'portfolio-current-audit/execution-review.json',
    'frontend-result.json', 'frontend-regressions.log', 'typecheck.log')]
evidence.extend(ref(OUT / 'projection-sync-repair' / name) for name in (
    'canonical-projection-bytes.json', 'independent-image-source-proof.json',
    'frontend-result.json', 'frontend-regressions.log', 'typecheck.log', 'original-review-projection-proof.json'))
freeze = {**identity, 'identity': identity, 'frozen_affected_files': frozen,
    'complete_regression_cases': len(cases), 'complete_regressions_passed': True,
    'two_disjoint_complete_green_runs': True, 'single_full_green_run': False,
    'validation_evidence': evidence, 'both_full_original_acceptances': False,
    'full_release_pass': False, 'productive_delivery': False}
write('candidate-prepare-freeze.json', freeze)
work = read(OUT / 'workload.json')
work.update(status='LOCAL_CHECKS_VALIDATED_WAITING_NORMAL_PREPARATION_AND_BOTH_ORIGINALS',
    files_changed=list(files), after=after, diff=diffs, regression_aggregate=ref(OUT / 'regression-aggregate.json'),
    before=[ref(OUT / 'before' / name) for name in files if (OUT / 'before' / name).exists()])
work['tests']['final_disjoint_green_runs'] = runs
work['tests']['distinct_latest_pass'] = len(cases)
work['tests']['single_full_green_run'] = False
work['remaining_findings'] = ['Both full unchanged originals, complete final-image release gate and actual productive delivery remain mandatory.']
write('workload.json', work)
print(json.dumps({'status': 'FROZEN_FOR_NORMAL_PREPARATION', **identity, 'distinct_passed': len(cases),
    'single_full_green_run': False, 'original_acceptance': False, 'productive_delivery': False}))
