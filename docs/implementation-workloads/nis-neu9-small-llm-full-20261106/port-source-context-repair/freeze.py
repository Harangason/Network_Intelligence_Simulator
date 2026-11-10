"""Bind exact local/native repair evidence, without claiming Original acceptance."""
import ast
from dataclasses import asdict
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
GOAL = OUT.parent

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

assert not (OUT / 'source-scope-proof.json').exists(), 'Never overwrite a frozen identity'
work, root = read(OUT / 'workload.json'), read(GOAL / 'workload.json')
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 7
assert ref(Path(root['source']['path']))['sha256'] == root['source']['sha256']
for name, digest in root['frozen_files'].items():
    if name not in work['files_changed']:
        assert ref(ROOT / name)['sha256'] == digest, name
latest, runs = set(), {}
for name in ('green.xml', 'phy-diagnostic-green.xml', 'regression.xml'):
    cases = list(ET.parse(OUT / name).getroot().iter('testcase'))
    assert cases and all(all(case.find(kind) is None for kind in ('failure', 'error', 'skipped')) for case in cases)
    runs[name] = {'passed': len(cases), 'evidence': ref(OUT / name)}
    latest.update((case.get('classname'), case.get('name')) for case in cases)
assert runs['regression.xml']['passed'] == len(latest), 'The full regression must include all targeted cases'

native_dir = OUT / 'native-counter-physical'
native = read(native_dir / 'result.json')
app = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
assert native['status'] == 'PASS' and native['participants'] == native['planned_ports'] == 4
assert native['reasoner_sha256'] == ref(app)['sha256']
provider_path = Path(read(native_dir / 'admission.json')['path'])
provider = read(provider_path)
assert provider['model']['name'] == 'qwen3.5:9b'
assert provider['model']['digest'].removeprefix('sha256:') == '56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'
assert all(slot['n_ctx'] == 131072 for worker in provider['slots'] for slot in worker['slots'])
from backend.tests.test_reference_reasoner import effective_reference_context
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from jsonschema import Draft202012Validator
streams = []
for number in range(1, native['actual_native_requests'] + 1):
    request_path, response_path = native_dir / f'request-{number}.json', native_dir / f'response-{number}.ndjson'
    request = read(request_path)
    assert request['model'] == 'qwen3.5:9b'
    assert request['options']['num_ctx'] == 131072 and request['options']['num_predict'] == 8192
    responses = [json.loads(line) for line in response_path.read_text(encoding='utf8').splitlines() if line.strip()]
    assert sum(bool(row.get('done')) for row in responses) == 1
    last = responses[-1]
    assert last['done'] is True and last['done_reason'] == 'stop' and last['eval_count'] > 0
    assert last['model'] == 'qwen3.5:9b'
    raw = ''.join(row.get('message', {}).get('content', '') for row in responses)
    decoded = json.loads(raw)
    if 'port_groups_by_device' in request['format']['properties']:
        Draft202012Validator(request['format']).validate(decoded)
        assert decoded['port_plan_complete'] is True and decoded['unresolved'] == []
        groups = decoded['port_groups_by_device']
        assert len(groups) == 4 and all(len(row['connections']) == 1 for row in groups.values())
        assert all(row['connections'][0]['technology'] == 'can_fd' and row['connections'][0]['count'] == 1 for row in groups.values())
        context = effective_reference_context(request['messages'])
        view = json.loads(request['messages'][-1]['content'])['nis_current_selection']
        assert view['selected_port_source_context'] == context['selected_port_source_context']
        physical = json.loads(json.dumps(asdict(DEFAULT_TECHNOLOGY_REGISTRY.physical_profile('can_fd'))))
        assert view['source_technologies']['can_fd']['physical_profile'] == physical
    streams.append({'request': ref(request_path), 'response': ref(response_path),
        'eval_count': last['eval_count'], 'prompt_eval_count': last['prompt_eval_count'],
        'response_sha256': hashlib.sha256(raw.encode()).hexdigest()})
rebases = read(native_dir / 'forced-rebases.json')
assert rebases and all(row['history_was_present'] and row['selected_device_count'] == 4 for row in rebases)
save(native_dir / 'independent-stream-review.json', {'status': 'PASS', 'scope': 'Physical port closure only',
    'streams': streams, 'source': ref(native_dir / 'source-request.json'), 'provider': ref(provider_path),
    'stored_earlier_findings': native['unresolved'], 'original_acceptance': False})

trees = [ast.parse(path.read_text(encoding='utf8')) for path in (OUT / 'before/local_reasoner.py', app)]
for tree in trees:
    tree.body = [node for node in tree.body if getattr(node, 'name', '') not in
        {'_reference_context_messages', '_reference_port_source_context', '_reference_context_artifact'}]
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'LocalEngineeringReasoner':
            node.body = [method for method in node.body if getattr(method, 'name', '') != 'plan_reference_design']
assert ast.dump(trees[0]) == ast.dump(trees[1]), 'Unexpected change outside source/physical projection and terminal diagnostics'
changes, after = [], []
for name in work['files_changed']:
    path = ROOT / name
    old_path = OUT / 'before' / path.name
    old = old_path.read_text(encoding='utf8') if old_path.exists() else ''
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(path.read_bytes())
    after.append(ref(destination))
    changes.extend(difflib.unified_diff(old.splitlines(True), path.read_text(encoding='utf8').splitlines(True),
        fromfile='before/' + name, tofile='after/' + name))
(OUT / 'change.diff').write_text(''.join(changes), encoding='utf8')
source = module('source_freeze', ROOT / 'scripts/write-build-info.py').build_manifest()
verification = module('verification_freeze', ROOT / 'scripts/run-release-gate.py').verification_manifest()
files = {name: ref(ROOT / name)['sha256'] for name in work['files_changed']}
save(OUT / 'regression-aggregate.json', {'status': 'PASS', 'distinct_cases': len(latest), 'runs': runs,
    'original_red': ref(OUT / 'red.xml'), 'diagnostic_red_and_initial_phy_fixture_failure': ref(OUT / 'phy-diagnostic-red.xml'),
    'corrected_phy_fixture_red': ref(OUT / 'phy-red-corrected-fixture.xml'),
    'failed_source_only_native_counter': ref(OUT / 'native-counter-source-fixed/failure-verified.json'),
    'native_counter': ref(native_dir / 'result.json'), 'native_stream_review': ref(native_dir / 'independent-stream-review.json'),
    'single_green_regression': True, 'original_acceptance': False, 'simulation_acceptance': False})
save(OUT / 'source-scope-proof.json', {'at': datetime.now(timezone.utc).isoformat(), 'source': source,
    'verification': verification, 'files': files, 'rest_of_reasoner_ast_identical': True,
    'public_schema_merge_gates_and_model_limits_unchanged': True, 'source_original_unchanged': root['source'],
    'regression': ref(OUT / 'regression-aggregate.json'), 'production_delivered': False})
evidence = [ref(OUT / name) for name in ('regression-aggregate.json', 'source-scope-proof.json')]
work.update(status='LOCALLY_AND_NATIVE_COUNTER_VERIFIED', after=after, diff=[ref(OUT / 'change.diff')],
    outcomes={key: {'status': 'PASSED', 'evidence': evidence} for key in work['required_outcomes']},
    validations={key: {'status': 'PASSED', 'evidence': evidence} for key in work['validation_requirements']},
    remaining_findings=['Full neu9, ALL simulation, full release gate and exact production delivery remain open.'])
save(OUT / 'workload.json', work)
root['frozen_files'].update(files)
root.update(frozen_source=source, frozen_verification_sha256=verification, current_repair=ref(OUT / 'workload.json'),
    final_local_repair_evidence=ref(OUT / 'source-scope-proof.json'), status='PREPARING_FRESH_ORIGINAL', active_native_request=None)
for name in files:
    if name not in root['files_changed']:
        root['files_changed'].append(name)
save(GOAL / 'workload.json', root)
print(json.dumps({'source': source, 'verification': verification, 'distinct_cases': len(latest)}))
