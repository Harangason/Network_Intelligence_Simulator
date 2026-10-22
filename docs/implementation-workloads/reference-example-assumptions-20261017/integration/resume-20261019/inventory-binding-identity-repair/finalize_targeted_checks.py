"""Record actual affected checks and source boundaries, without granting release PASS."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def module(path, excluded):
    tree = ast.parse(path.read_text(encoding='utf8'))
    tree.body = [node for node in tree.body if getattr(node, 'name', None) not in excluded]
    return ast.dump(tree)


workload = json.loads((OUT / 'workload.json').read_text(encoding='utf8'))
manifest, differences = {}, []
for name in workload['owned_files']:
    before, after = OUT / 'before' / name, ROOT / name
    assert sha(before) == workload.get('initial_revision_before', workload['revision_before'])[name]
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(after.read_bytes())
    manifest[name] = {'before': sha(before), 'current': sha(after)}
    differences.extend(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True),
        after.read_text(encoding='utf8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
(OUT / 'changes.diff').write_text(''.join(differences), encoding='utf8')
write('candidate-owned-manifest.json', manifest)
frozen = json.loads((OUT / 'validation-source-freeze.json').read_text(encoding='utf-8'))
assert all(sha(ROOT / name) == digest for name, digest in frozen.items()), 'Source changed during checks'
cases = list(ET.parse(OUT / 'affected-reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 245, len(cases)
prior_cases = list(ET.parse(OUT.parent / 'literal-inventory-functional-hardware-repair/affected-reference-regressions.xml').getroot().iter('testcase'))
assert len(prior_cases) == 224
case_id = lambda row: (row.attrib.get('classname'), row.attrib['name'])
assert {case_id(row) for row in prior_cases} <= {case_id(row) for row in cases}, 'A prior required case was omitted'
failed = [case for case in cases if case.find('failure') is not None]
assert len(failed) == 1 and all(case.find('error') is None and case.find('skipped') is None for case in cases)
assert failed[0].attrib['name'] == 'test_local_reference_planner_uses_decoder_projection_but_rejects_oversized_response'
retests = list(ET.parse(OUT / 'wire-fixture-retest.xml').getroot().iter('testcase'))
assert len(retests) == 1 and case_id(retests[0]) == case_id(failed[0])
assert retests[0].find('failure') is None and retests[0].find('error') is None and retests[0].find('skipped') is None
fixture_proof = json.loads((OUT / 'wire-fixture-only-change-proof.json').read_text(encoding='utf-8'))
assert fixture_proof['all_other_module_ast_unchanged'] and fixture_proof['original_assertion_nodes_unchanged']
assert sha(ROOT / fixture_proof['test_module']) == fixture_proof['after_sha256']
fixture_before = ast.parse((OUT / 'before' / fixture_proof['test_module']).read_text(encoding='utf-8'))
fixture_after = ast.parse((ROOT / fixture_proof['test_module']).read_text(encoding='utf-8'))
case_name = fixture_proof['corrected_case']
old_case = next(n for n in fixture_before.body if getattr(n, 'name', None) == case_name)
new_case = next(n for n in fixture_after.body if getattr(n, 'name', None) == case_name)
assert [ast.dump(n) for n in ast.walk(old_case) if isinstance(n, ast.Assert)] == [ast.dump(n) for n in ast.walk(new_case) if isinstance(n, ast.Assert)]
fixture_before.body = [n for n in fixture_before.body if getattr(n, 'name', None) != case_name]
fixture_after.body = [n for n in fixture_after.body if getattr(n, 'name', None) != case_name]
assert ast.dump(fixture_before) == ast.dump(fixture_after)

probe_path = OUT / 'native-private-schema-checks.json'
probes = json.loads(probe_path.read_text(encoding='utf8'))
assert len(probes['results']) == 12 and all(row['http_status'] == 200 for row in probes['results'])
assert sum(row['one_token_compiler_only'] for row in probes['results']) == 9
assert sum(row['completed_grammar_fixture_only'] for row in probes['results']) == 3
assert sha(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py') == probes['reasoner_file_sha256']
for row in probes['results']:
    name = row['name']
    schema = OUT / (name + '-decoder-schema.json')
    response = OUT / (name + '-compiler-response.json')
    request = json.loads((OUT / (name + '-compiler-request.json')).read_text(encoding='utf-8'))
    assert sha(schema) == row['schema_sha256'] and sha(response) == row['response_sha256']
    assert request['format'] == json.loads(schema.read_text(encoding='utf-8'))
    if row['completed_grammar_fixture_only']:
        assert json.loads(response.read_text(encoding='utf-8'))['done_reason'] == 'stop'
write('final-schema-equality-proof.json', {'scope': 'Entire final reasoner SHA matches actual current local compiler/grammar probes;12 exact request/schema/response hashes checked. Compiler/fixtures only, not original/model/simulation evidence.',
    'final_reasoner_sha256': probes['reasoner_file_sha256'],
    'exact_schemas_rechecked': [row['name'] for row in probes['results']],
    'native_probe_origin': {'path': str(probe_path), 'sha256': sha(probe_path)}})
intake_name = 'backend/nis/agent/orchestration/project_intake.py'
prior_frozen = json.loads((OUT.parent / 'literal-inventory-functional-hardware-repair/validation-source-freeze.json').read_text(encoding='utf-8'))
for unchanged in (intake_name, 'backend/nis/agent/tools/wizard_generation.py'):
    assert sha(ROOT / unchanged) == prior_frozen[unchanged], 'Public/reference validators or persistence changed: ' + unchanged
intake_baseline = OUT.parent / 'early-inventory-repair/before' / intake_name
excluded = {'ReferenceDevice', 'reference_inventory_members', '_validate_reference_design', '_validate_reference_inventory'}
assert module(intake_baseline, excluded) == module(ROOT / intake_name, excluded)
reasoner_name = 'backend/nis/agent/orchestration/local_reasoner.py'
before_tree = ast.parse((OUT / 'before' / reasoner_name).read_text(encoding='utf8'))
after_tree = ast.parse((ROOT / reasoner_name).read_text(encoding='utf8'))


def class_members(tree):
    node = next(node for node in tree.body if getattr(node, 'name', None) == 'LocalEngineeringReasoner')
    return [ast.dump(row) for row in node.body if getattr(row, 'name', None) != 'plan_reference_design']


assert class_members(before_tree) == class_members(after_tree)
for name in ('_reference_merge_inventory_devices', '_reference_scoped_inventory_delta', '_reference_inventory_progress', '_reference_declared_instances'):
    assert ast.dump(next(row for row in before_tree.body if getattr(row, 'name', None) == name)) == ast.dump(next(row for row in after_tree.body if getattr(row, 'name', None) == name)), name
write('source-change-scope-proof.json', {
    'unchanged_other_methods_including_intake_and_defaults': True,
    'unchanged_document_intake_methods_and_response_validation': True,
    'unchanged_nonreference_module_ast_including_imports_and_constants': True,
    'unchanged_complete_public_reference_validator_and_persistence_files_vs_prior_candidate': True,
    'unchanged_shared_identity_metadata_count_and_progress_guards_ast': True,
    'excluded_reference_definitions': sorted(excluded),
    'source_intake_baseline_snapshot': {'path': str(intake_baseline), 'sha256': sha(intake_baseline)},
    'previous_intake_module_sha256': sha(intake_baseline),
    'current_intake_module_sha256': sha(ROOT / intake_name),
    'compiler_origin': {'path': str(probe_path), 'sha256': sha(probe_path)},
    'fresh_original_document_intake': False})


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


build = load('stage_contract_build', ROOT / 'scripts/write-build-info.py')
gate = load('stage_contract_gate', ROOT / 'scripts/run-release-gate.py')
identity = build.build_manifest()
write('candidate-input-identity.json', {
    'commit_id': identity['commit_id'], 'source_sha256': identity['source_sha256'],
    'verification_sha256': gate.verification_manifest()})
write('validation-summary.json', {'at_utc': datetime.now(timezone.utc).isoformat(),
    'affected_distinct_cases_with_pass_evidence': len(cases), 'broad_cases': len(cases), 'broad_passed': len(cases) - len(failed), 'broad_failures': len(failed), 'corrected_wire_fixture_retest_passed': len(retests), 'single_full_affected_run_pass': False, 'errors': 0, 'skipped': 0,
    'wire_fixture_retest_xml_sha256': sha(OUT / 'wire-fixture-retest.xml'), 'fixture_ast_proof_sha256': sha(OUT / 'wire-fixture-only-change-proof.json'),
    'xml_sha256': sha(OUT / 'affected-reference-regressions.xml'),
    'native_compiler_probes': 9, 'completed_native_grammar_fixtures': 3, 'native_original_pass': False,
    'source_hashes_recorded_after_run_no_edits_during_run': frozen,
    'native_original_plan_pass': False, 'simulation_pass': False, 'full_release_pass': False,
    'productive_delivery': False})
print(json.dumps({'distinct_cases_with_pass_evidence_across_two_runs': len(cases), 'single_full_run_pass': False, 'compiler_probes': 9, 'completed_grammar_fixtures': 3, 'identity': identity['source_sha256']}))
