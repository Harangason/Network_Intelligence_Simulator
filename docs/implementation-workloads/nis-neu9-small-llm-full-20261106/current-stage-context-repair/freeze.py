"""Bind the repair's local and real-model evidence without claiming neu9 acceptance."""
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


assert not (OUT / 'source-scope-proof.json').exists(), 'Do not overwrite frozen evidence'
work, root = read(OUT / 'workload.json'), read(GOAL / 'workload.json')
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 7
assert ref(Path(root['source']['path']))['sha256'] == root['source']['sha256']
allowed = set(work['files_changed']) | {'docs/implementation-workloads/nis-neu9-small-llm-full-20261106/retire_dd9.py'}
for name, digest in root['frozen_files'].items():
    if name not in allowed:
        assert ref(ROOT / name)['sha256'] == digest, name
latest, runs = {}, {}
for name in ('green-after-fixture-repair.xml', 'order-green-backend.xml', 'regression.xml'):
    cases = list(ET.parse(OUT / name).getroot().iter('testcase'))
    assert cases and all(all(case.find(kind) is None for kind in ('failure', 'error', 'skipped')) for case in cases)
    runs[name] = {'passed': len(cases), 'evidence': ref(OUT / name)}
    for case in cases:
        latest[(case.get('classname'), case.get('name'))] = True
inventory_reader = read(OUT / 'native-inventory-view/result.json')
assert inventory_reader['status'] == 'PASS'
assert inventory_reader['actual_response']['counts'] == {'CONTROLLER':50,'GATEWAY':1,'SENSOR':100,'ACTUATOR':100}
assert inventory_reader['actual_response']['unknown_phy_still_open'] is True
assert inventory_reader['reasoner_sha256'] == ref(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py')['sha256']
native_dir = OUT / 'native-counter-ordered-backend'
native = read(native_dir / 'result.json')
assert native['status'] == 'PASS' and native['participants'] == native['planned_ports'] == 4
admission = read(Path(read(native_dir / 'admission.json')['path']))
assert admission['model']['name'] == 'qwen3.5:9b'
assert admission['model']['digest'].removeprefix('sha256:') == '56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'
assert all(slot['n_ctx'] == 131072 for worker in admission['slots'] for slot in worker['slots'])
app = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
assert native['reasoner_sha256'] == ref(app)['sha256']
equivalence = read(OUT / 'schema-order-equivalence.json')
assert equivalence['status'] == 'PASS' and len(equivalence['schemas']) == 8
assert equivalence['after_sha256'] == ref(app)['sha256']
assert all(row['all_values_identical'] for row in equivalence['schemas'])
streams = []
for number in range(1, native['actual_native_requests'] + 1):
    request_path, response_path = native_dir / f'request-{number}.json', native_dir / f'response-{number}.ndjson'
    request = read(request_path)
    assert request['model'] == 'qwen3.5:9b'
    assert request['options']['num_ctx'] == 131072 and request['options']['num_predict'] == 8192
    responses = [json.loads(line) for line in response_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert sum(bool(row.get('done')) for row in responses) == 1
    last = responses[-1]
    assert last['done'] is True and last['done_reason'] == 'stop' and last['eval_count'] > 0
    assert last['model'] == 'qwen3.5:9b'
    raw = ''.join(row.get('message', {}).get('content', '') for row in responses)
    decoded = json.loads(raw)
    if 'port_groups_by_device' in request['format']['properties']:
        from jsonschema import Draft202012Validator
        Draft202012Validator(request['format']).validate(decoded)
        assert decoded['port_plan_complete'] is True
        assert decoded['unresolved'] == [], 'The completed port decision must not invent new open findings'
        groups = decoded['port_groups_by_device']
        assert len(groups) == 4 and all(len(row['connections']) == 1 for row in groups.values())
        assert all(row['connections'][0]['technology'] == 'can_fd' for row in groups.values())
    streams.append({'request': ref(request_path), 'response': ref(response_path),
        'eval_count': last['eval_count'], 'prompt_eval_count': last['prompt_eval_count'],
        'response_sha256': hashlib.sha256(raw.encode()).hexdigest()})
rebases = read(native_dir / 'forced-rebases.json')
assert rebases and all(row['history_was_present'] and row['selected_device_count'] == 4 for row in rebases)
save(native_dir / 'independent-stream-review.json', {'status': 'PASS', 'actual_requests': len(streams),
    'streams': streams, 'source': ref(native_dir / 'source-request.json'),
    'provider_binding': ref(Path(read(native_dir / 'admission.json')['path'])),
    'forced_complete_context_rebases': ref(native_dir / 'forced-rebases.json'),
    'stored_previous_findings': native['unresolved'], 'original_acceptance': False})
trees = [ast.parse(path.read_text(encoding='utf-8')) for path in (OUT / 'before/local_reasoner.py', app)]
for tree in trees:
    tree.body = [node for node in tree.body if getattr(node, 'name', '') not in
        {'_reference_context_messages', '_reference_schema_for_stage'}]
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'LocalEngineeringReasoner':
            node.body = [method for method in node.body if getattr(method, 'name', '') != 'plan_reference_design']
assert ast.dump(trees[0]) == ast.dump(trees[1]), 'Change outside current-stage context projection/planner prompt/schema order'
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
source = module('port_complete_build', ROOT / 'scripts/write-build-info.py').build_manifest()
verification = module('port_complete_gate', ROOT / 'scripts/run-release-gate.py').verification_manifest()
files = {name: ref(ROOT / name)['sha256'] for name in work['files_changed']}
save(OUT / 'regression-aggregate.json', {'status': 'PASS', 'distinct_cases': len(latest), 'runs': runs,
    'original_red': ref(OUT / 'red.xml'), 'native_counter': ref(native_dir / 'result.json'),
    'decision_order_red': ref(OUT / 'order-red.xml'),
    'schema_semantics_comparison': ref(OUT / 'schema-order-equivalence.json'),
    'wrong_python_environment_run': ref(OUT / 'order-green.xml'),
    'failed_direct_view_only_counter': ref(OUT / 'native-counter/failure.json'),
    'decisive_order_only_probe': ref(OUT / 'ordered-decisions-probe/result.json'),
    'native_stream_review': ref(native_dir / 'independent-stream-review.json'),
    'single_green_regression': True, 'earlier_regression_54pass_2fixturefail': ref(OUT/'green.xml'), 'baseline_fixture_failures_verified': ref(OUT/'baseline-fixture-proof.xml'), 'native_251_inventory_reader': ref(OUT/'native-inventory-view/result.json'), 'original_acceptance': False, 'simulation_acceptance': False})
save(OUT / 'source-scope-proof.json', {'at': datetime.now(timezone.utc).isoformat(), 'source': source,
    'verification': verification, 'files': files, 'rest_of_reasoner_ast_identical': True,
    'public_schema_and_model_limits_unchanged': True, 'source_original_unchanged': root['source'],
    'regression': ref(OUT / 'regression-aggregate.json'), 'production_delivered': False})
evidence = [ref(OUT / name) for name in ('regression-aggregate.json', 'source-scope-proof.json')]
work.update(status='LOCALLY_AND_NATIVE_COUNTER_VERIFIED', after=after, diff=[ref(OUT / 'change.diff')],
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
