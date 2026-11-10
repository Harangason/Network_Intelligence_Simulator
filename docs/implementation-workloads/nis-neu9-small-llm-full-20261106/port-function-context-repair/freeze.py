"""Freeze port-context repair evidence without replacing failed test receipts."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
GOAL = OUT.parent


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


assert not (OUT / 'source-scope-proof.json').exists(), 'Do not overwrite frozen proof'
work = read(OUT / 'workload.json')
root = read(GOAL / 'workload.json')
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 7
assert ref(Path(root['source']['path']))['sha256'] == root['source']['sha256']
for name, digest in root['frozen_files'].items():
    if name not in work['files_changed']:
        assert ref(ROOT / name)['sha256'] == digest, name
latest, runs = {}, {}
for name in ('green.xml', 'regression.xml', 'regression-fixtures.xml'):
    path = OUT / name
    tree = ET.parse(path).getroot()
    cases = list(tree.iter('testcase'))
    assert all(case.find('error') is None and case.find('skipped') is None for case in cases)
    failures = [case.get('name') for case in cases if case.find('failure') is not None]
    runs[name] = {'cases': len(cases), 'failures': failures, 'evidence': ref(path)}
    for case in cases:
        latest[(case.get('classname'), case.get('name'))] = case.find('failure') is None
assert all(latest.values()), 'Every original failed case needs its exact successful rerun'
assert not runs['regression-fixtures.xml']['failures']
native = read(OUT / 'native-counter/result.json')
assert native['status'] == 'PASS' and len(native['cases']) == 2
assert native['reasoner_sha256'] == ref(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py')['sha256']
assert read(OUT / 'native-counter/independent-stream-review.json')['actual_requests'] == 6
trees = [ast.parse(p.read_text(encoding='utf-8')) for p in (
    OUT / 'before/local_reasoner.py', ROOT / 'backend/nis/agent/orchestration/local_reasoner.py')]
for tree in trees:
    tree.body = [node for node in tree.body if getattr(node, 'name', '') != '_reference_port_function_context']
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'LocalEngineeringReasoner':
            node.body = [method for method in node.body if getattr(method, 'name', '') != 'plan_reference_design']
assert ast.dump(trees[0]) == ast.dump(trees[1]), 'Changes outside planner/focused context'
aggregate = {'status': 'PASS_ACROSS_TARGETED_RUNS', 'distinct_cases': len(latest), 'runs': runs,
    'original_red': ref(OUT / 'red.xml'), 'single_fully_green_regression_claimed': False,
    'native_counter': ref(OUT / 'native-counter/result.json'),
    'native_stream_review': ref(OUT / 'native-counter/independent-stream-review.json'),
    'native_findings_preserved': True, 'original_acceptance': False, 'simulation_acceptance': False}
save(OUT / 'regression-aggregate.json', aggregate)
changes, after = [], []
for name in work['files_changed']:
    path = ROOT / name
    old_path = OUT / 'before' / path.name
    old = old_path.read_text(encoding='utf-8') if old_path.exists() else ''
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(path.read_bytes())
    after.append(ref(destination))
    changes.extend(difflib.unified_diff(old.splitlines(True), path.read_text(encoding='utf-8').splitlines(True),
                                      fromfile='before/' + name, tofile='after/' + name))
(OUT / 'change.diff').write_text(''.join(changes), encoding='utf-8')
source = module('port_context_build', ROOT / 'scripts/write-build-info.py').build_manifest()
verification = module('port_context_gate', ROOT / 'scripts/run-release-gate.py').verification_manifest()
files = {name: ref(ROOT / name)['sha256'] for name in work['files_changed']}
proof = {'at': datetime.now(timezone.utc).isoformat(), 'source': source, 'verification': verification,
    'files': files, 'app_scope': 'Only normal reference planner ordering/instruction and lossless selected function context',
    'rest_of_reasoner_ast_identical': True, 'public_schema_validator_registry_and_model_limits_unchanged': True,
    'regression': ref(OUT / 'regression-aggregate.json'), 'original_acceptance': False, 'production_delivered': False}
save(OUT / 'source-scope-proof.json', proof)
evidence = [ref(OUT / name) for name in ('finding.json', 'regression-aggregate.json', 'source-scope-proof.json')]
work.update(status='LOCALLY_AND_NATIVE_PORT_COUNTER_VERIFIED', after=after, diff=[ref(OUT / 'change.diff')],
    outcomes={key: {'status': 'PASSED', 'evidence': evidence} for key in work['required_outcomes']},
    validations={key: {'status': 'PASSED', 'evidence': evidence} for key in work['validation_requirements']},
    remaining_findings=['Full neu9, successful ALL simulation, full gate and exact production delivery remain open.'])
save(OUT / 'workload.json', work)
root['frozen_files'].update(files)
root.update(frozen_source=source, frozen_verification_sha256=verification, current_repair=ref(OUT / 'workload.json'),
    final_local_repair_evidence=ref(OUT / 'source-scope-proof.json'), status='PREPARING_FRESH_ORIGINAL', active_native_request=None)
for name in files:
    if name not in root['files_changed']:
        root['files_changed'].append(name)
save(GOAL / 'workload.json', root)
print(json.dumps({'source': source, 'verification': verification, 'distinct_cases': len(latest)}))
