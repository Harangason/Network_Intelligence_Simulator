"""Bind actual targeted/native grammar evidence; never grant a release PASS."""
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
PRIOR = OUT.parent / 'inventory-binding-identity-repair'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
freeze = json.loads((OUT / 'validation-source-freeze.json').read_text(encoding='utf-8'))
assert all(sha(ROOT / name) == digest for name, digest in freeze.items()), 'Source changed during final checks'
cases = list(ET.parse(OUT / 'tagged-targeted-reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 94, len(cases)
assert all(case.find(tag) is None for case in cases for tag in ('failure', 'error', 'skipped'))
counts = Counter(case.attrib['classname'] for case in cases)
assert counts == {
    'tests.test_reference_reasoner': 83, 'tests.test_reference_design': 1,
    'tests.test_reference_design_integration': 8, 'tests.test_reference_model_persistence': 2}
previous = list(ET.parse(OUT / 'targeted-reference-regressions.xml').getroot().iter('testcase'))
assert len(previous) == 87 and all(row.find('failure') is None for row in previous)
key = lambda row: (row.attrib['classname'], row.attrib['name'])
assert {key(row) for row in previous} <= {key(row) for row in cases}

manifest, differences = {}, []
for name in work['owned_files']:
    before, current = OUT / 'before' / name, ROOT / name
    assert sha(before) == work['initial_revision_before'][name]
    after = OUT / 'after' / name
    after.parent.mkdir(parents=True, exist_ok=True)
    after.write_bytes(current.read_bytes())
    manifest[name] = {'before': sha(before), 'current': sha(current)}
    differences.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),
        current.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
write('candidate-owned-manifest.json', manifest)
(OUT / 'changes.diff').write_text(''.join(differences), encoding='utf-8')

probes_path = OUT / 'final-native-schemas/native-private-schema-checks.json'
probes = json.loads(probes_path.read_text(encoding='utf-8'))
assert len(probes['results']) == 14
assert sum(row['one_token_compiler_only'] for row in probes['results']) == 9
assert sum(row['completed_grammar_fixture_only'] for row in probes['results']) == 5
reasoner = 'backend/nis/agent/orchestration/local_reasoner.py'
assert sha(ROOT / reasoner) == probes['reasoner_file_sha256']
for row in probes['results']:
    stem = OUT / 'final-native-schemas' / row['name']
    schema = Path(str(stem) + '-decoder-schema.json')
    request = Path(str(stem) + '-compiler-request.json')
    response = Path(str(stem) + '-compiler-response.json')
    assert row['http_status'] == 200
    assert sha(schema) == row['schema_sha256'] and sha(response) == row['response_sha256']
    assert json.loads(request.read_text(encoding='utf-8'))['format'] == json.loads(schema.read_text(encoding='utf-8'))
    if row['completed_grammar_fixture_only']:
        assert json.loads(response.read_text(encoding='utf-8'))['done_reason'] == 'stop'
for name in ('ports', 'measurements', 'commands'):
    assert json.loads((OUT / 'final-native-schemas' / (name + '-decoder-schema.json')).read_text(encoding='utf-8')) == json.loads((PRIOR / (name + '-decoder-schema.json')).read_text(encoding='utf-8'))
write('final-schema-equality-proof.json', {
    'scope': 'Exact final reasoner hash and14actual compiler/grammar request/schema/response artifacts verified. No original/model/simulation PASS.',
    'exact_schemas_rechecked': [row['name'] for row in probes['results']],
    'reasoner_file_sha256': sha(ROOT / reasoner), 'unchanged_noninventory_io_schemas': True,
    'native_probe_origin': {'path': str(probes_path), 'sha256': sha(probes_path)}})

prior_freeze = json.loads((PRIOR / 'validation-source-freeze.json').read_text(encoding='utf-8'))
intake = 'backend/nis/agent/orchestration/project_intake.py'
persistence = 'backend/nis/agent/tools/wizard_generation.py'
assert all(sha(ROOT / name) == prior_freeze[name] for name in (intake, persistence))
baseline = OUT.parent / 'early-inventory-repair/before' / intake
excluded = {'ReferenceDevice', 'reference_inventory_members', '_validate_reference_design', '_validate_reference_inventory'}


def intake_ast(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [row for row in tree.body if getattr(row, 'name', None) not in excluded]
    return ast.dump(tree)


assert intake_ast(baseline) == intake_ast(ROOT / intake)
old = ast.parse((OUT / 'before' / reasoner).read_text(encoding='utf-8'))
new = ast.parse((ROOT / reasoner).read_text(encoding='utf-8'))


def method(tree, name):
    cls = next(row for row in tree.body if getattr(row, 'name', None) == 'LocalEngineeringReasoner')
    return next(row for row in cls.body if getattr(row, 'name', None) == name)


old_cls = next(row for row in old.body if getattr(row, 'name', None) == 'LocalEngineeringReasoner')
new_cls = next(row for row in new.body if getattr(row, 'name', None) == 'LocalEngineeringReasoner')
assert [ast.dump(row) for row in old_cls.body if getattr(row, 'name', None) != 'plan_reference_design'] == [ast.dump(row) for row in new_cls.body if getattr(row, 'name', None) != 'plan_reference_design']


class WithoutNativeInfer(ast.NodeTransformer):
    def visit_AsyncFunctionDef(self, node):
        return None if node.name == 'infer' else self.generic_visit(node)


assert ast.dump(WithoutNativeInfer().visit(deepcopy(method(old, 'plan_reference_design')))) == ast.dump(WithoutNativeInfer().visit(deepcopy(method(new, 'plan_reference_design'))))
for name in ('_reference_merge_inventory_devices', '_reference_scoped_inventory_delta', '_reference_inventory_progress', '_reference_declared_instances'):
    assert ast.dump(next(row for row in old.body if getattr(row, 'name', None) == name)) == ast.dump(next(row for row in new.body if getattr(row, 'name', None) == name))
decoder_test = 'test_local_reference_planner_uses_decoder_projection_but_rejects_oversized_response'
test_file = 'backend/tests/test_reference_design.py'
before_test = ast.parse((OUT / 'before' / test_file).read_text(encoding='utf-8'))
after_test = ast.parse((ROOT / test_file).read_text(encoding='utf-8'))
before_test.body = [row for row in before_test.body if getattr(row, 'name', None) != decoder_test]
after_test.body = [row for row in after_test.body if getattr(row, 'name', None) != decoder_test]
assert ast.dump(before_test) == ast.dump(after_test)
write('source-change-scope-proof.json', {
    'unchanged_other_methods_including_intake_and_defaults': True,
    'unchanged_document_intake_methods_and_response_validation': True,
    'unchanged_nonreference_module_ast_including_imports_and_constants': True,
    'unchanged_full_public_validator_and_persistence_files': True,
    'unchanged_plan_profile_io_namespace_and_full_validation_outside_native_infer': True,
    'unchanged_shared_identity_count_metadata_progress_and_source_compilation_guards': True,
    'unchanged_other_public_reference_tests_and_fixtures': True,
    'source_intake_baseline_snapshot': {'path': str(baseline), 'sha256': sha(baseline)},
    'excluded_reference_definitions': sorted(excluded),
    'compiler_origin': {'path': str(probes_path), 'sha256': sha(probes_path)},
    'fresh_original_document_intake': False})

build = load('choice_final_build_identity', ROOT / 'scripts/write-build-info.py')
gate = load('choice_final_verification_identity', ROOT / 'scripts/run-release-gate.py')
identity = build.build_manifest()
write('candidate-input-identity.json', {
    'commit_id': identity['commit_id'], 'source_sha256': identity['source_sha256'],
    'verification_sha256': gate.verification_manifest()})
write('validation-summary.json', {
    'at_utc': datetime.now(timezone.utc).isoformat(), 'targeted_isolated_cases': len(cases),
    'cases_by_module': dict(counts), 'failures': 0, 'errors': 0, 'skipped': 0,
    'xml_sha256': sha(OUT / 'tagged-targeted-reference-regressions.xml'),
    'native_compiler_probes': 9, 'completed_native_grammar_fixtures': 5,
    'frozen_source_and_test_hashes': freeze,
    'scope': '94targeted cases and14actual local grammar/compiler cases only; complete backend/frontend/release gate and actual originals still required.',
    'original_workflow_pass': False, 'model_or_simulation_pass': False,
    'full_release_pass': False, 'productive_delivery': False})
print(json.dumps({'targeted_cases_passed': len(cases), 'native_compiler': 9,
                  'full_grammar_fixtures': 5, 'source_sha256': identity['source_sha256']}))
