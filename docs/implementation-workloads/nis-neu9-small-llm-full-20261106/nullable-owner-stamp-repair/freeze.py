"""Bind observed owner-schema checks and unchanged original requirements to source."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
GOAL = OUT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


assert not (OUT / 'source-scope-proof.json').exists()
identity = read(OUT / 'identity-after-fixture-review.json')
for name, digest in identity['files'].items():
    assert ref(ROOT / name)['sha256'] == digest
runs = []
for name, session in [('green-codec.xml', 58667), ('regression-fixtures.xml', 19496)]:
    suites = list(ET.parse(OUT / name).getroot().iter('testsuite'))
    totals = {key: sum(int(s.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    assert totals['tests'] > 0 and totals['failures'] == totals['errors'] == totals['skipped'] == 0
    runs.append({'session': session, **totals, 'evidence': ref(OUT / name)})
original_cases = list(ET.parse(OUT / 'regression.xml').getroot().iter('testcase'))
failed_cases = {case.get('name') for case in original_cases if case.find('failure') is not None}
assert failed_cases == {
    'test_existing_binding_schema_offers_only_identity_selection_and_scoped_metadata',
    'test_existing_binding_schema_excludes_incompatible_immutable_identities[name]',
    'test_existing_binding_schema_excludes_incompatible_immutable_identities[member]'}
assert all(case.find('error') is None and case.find('skipped') is None for case in original_cases)
assert len(original_cases) == 189
repeated_cases = {case.get('name') for case in ET.parse(OUT / 'regression-fixtures.xml').getroot().iter('testcase')}
assert failed_cases <= repeated_cases
native = read(OUT / 'native-grammar/result.json')
assert native['status'] == 'PASS' and native['actual_generation_requests'] == 3
assert native['source_sha256'] == identity['files']['backend/nis/agent/orchestration/local_reasoner.py']
assert {c['kind'] for c in native['cases']} == {'SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT'}
before = ast.parse((OUT / 'before/local_reasoner.py').read_text(encoding='utf-8'))
after = ast.parse((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf-8'))
for tree in (before, after):
    tree.body = [node for node in tree.body if getattr(node, 'name', None) != '_reference_schema_for_stage']
assert ast.dump(before) == ast.dump(after)
aggregate = {'runs': runs, 'native': {'session': 47282, 'exit_code': 0, 'evidence': ref(OUT / 'native-grammar/result.json')},
             'original_regression': {'session': 69048, 'exit_code': 1, 'passed': 186, 'failed': sorted(failed_cases),
                                     'evidence': ref(OUT / 'regression.xml')},
             'single_fully_green_regression_run': False,
             'red': ref(OUT / 'red-corrected-fixture.xml'), 'initial_fixture_error_run_preserved': ref(OUT / 'red.xml'),
             'original_acceptance': False, 'production_delivered': False}
save(OUT / 'regression-aggregate.json', aggregate)
work = read(OUT / 'workload.json')
after_refs, changes = [], []
for name in work['repair']['affected_files']:
    source = ROOT / name
    baseline = OUT / 'before' / source.name
    old = baseline.read_text(encoding='utf-8') if source.name != 'test_reference_owner_evidence_schema.py' else ''
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    after_refs.append(ref(destination))
    changes.extend(difflib.unified_diff(old.splitlines(True), source.read_text(encoding='utf-8').splitlines(True),
                                        fromfile='before/' + name, tofile='after/' + name))
(OUT / 'final-change.diff').write_text(''.join(changes), encoding='utf-8')
proof = {**identity, 'at': datetime.now(timezone.utc).isoformat(), 'validation_pending': False,
         'only_private_reference_schema_changed': True, 'public_validator_and_planner_unchanged': True,
         'regression': ref(OUT / 'regression-aggregate.json'), 'native_probe_source': ref(OUT / 'native_counter.py'),
         'original_acceptance': False, 'production_delivered': False}
save(OUT / 'source-scope-proof.json', proof)
evidence = [ref(OUT / name) for name in ('finding.json', 'regression-aggregate.json', 'source-scope-proof.json', 'ast-scope-proof.json')]
work.update(status='LOCALLY_AND_NATIVE_COUNTER_VERIFIED_FULL_ORIGINAL_PENDING',
            files_changed=work['repair']['affected_files'], after=after_refs, diff=[ref(OUT / 'final-change.diff')],
            outcomes={key: {'status': 'PASSED', 'evidence': evidence} for key in work['required_outcomes']},
            validations={key: {'status': 'PASSED', 'evidence': evidence} for key in work['validation_requirements']},
            remaining_findings=['Full unchanged neu9, successful simulation, complete release gate and exact production delivery remain open.'])
save(OUT / 'workload.json', work)
root = read(GOAL / 'workload.json')
for name, digest in root['frozen_files'].items():
    if name not in identity['files']:
        assert ref(ROOT / name)['sha256'] == digest, name
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 7
assert ref(Path(root['source']['path']))['sha256'] == root['source']['sha256']
root['frozen_files'].update(identity['files'])
root.update(frozen_source=identity['source'], frozen_verification_sha256=identity['verification'],
            current_repair=ref(OUT / 'workload.json'), status='PREPARING_FRESH_ORIGINAL',
            final_local_repair_evidence=ref(OUT / 'source-scope-proof.json'), active_native_request=None)
for name in identity['files']:
    if name not in root['files_changed']:
        root['files_changed'].append(name)
save(GOAL / 'workload.json', root)
print(json.dumps({'source': identity['source'], 'verification': identity['verification'], 'runs': runs}))
