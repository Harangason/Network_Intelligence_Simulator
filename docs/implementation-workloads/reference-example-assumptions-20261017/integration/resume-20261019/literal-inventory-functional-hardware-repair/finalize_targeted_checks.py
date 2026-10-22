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
frozen = {name: sha(ROOT / name) for name in [*workload['owned_files'],
    'backend/nis/agent/tools/wizard_generation.py', 'backend/nis/agent/orchestration/project_intake.py',
    'backend/tests/test_reference_design_integration.py', 'backend/tests/test_reference_model_persistence.py',
    'backend/tests/test_reference_identifiers.py', 'backend/tests/test_reference_parameter_roles.py']}
write('validation-source-freeze.json', frozen)
cases = list(ET.parse(OUT / 'affected-reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 224, len(cases)
assert all(case.find('failure') is None and case.find('error') is None and case.find('skipped') is None for case in cases)
probe_path = OUT / 'native-private-schema-checks.json'
probes = json.loads(probe_path.read_text(encoding='utf8'))
assert len(probes['results']) == 9 and all(row['http_status'] == 200 for row in probes['results'])
assert sum(row['one_token_compiler_only'] for row in probes['results']) == 7
assert sum(row['completed_grammar_fixture_only'] for row in probes['results']) == 2
prior_reasoner = OUT / 'reasoner-before-raw-metadata-guard.py'
assert sha(prior_reasoner) == probes['reasoner_file_sha256']
def schema_node(path):
    tree = ast.parse(path.read_text(encoding='utf8'))
    return ast.dump(next(node for node in tree.body if getattr(node, 'name', None) == '_reference_schema_for_stage'))
assert schema_node(prior_reasoner) == schema_node(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py')
import sys
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage
from backend.nis.agent.orchestration.project_intake import prepare_reference_design, reference_inventory_members
from backend.nis.engineering.projects.project_context import activate_project, reset_project
case = OUT.parents[1] / 'native-scoped-vehicle'
state = json.loads((case / 'state.json').read_text(encoding='utf8'))
token = activate_project(state['project_id'])
try:
    prepared = prepare_reference_design(json.loads((case / 'plan-reference/request.json').read_text(encoding='utf8')))
finally:
    reset_project(token)
declared = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE' and fact['role'] == 'CONTROLLER')
member_fact = next(key for key, fact in prepared['facts'].items() if reference_inventory_members(fact))
member = reference_inventory_members(prepared['facts'][member_fact])[0]
derived = [key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}]
schemas = {
    'declared': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={'fact_id': declared, 'minimum_rows': 1}),
    'literal-member': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={'fact_id': member_fact, 'member': member, 'minimum_rows': 1}),
    'literal-covered-closure': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={'fact_id': member_fact, 'member': member, 'minimum_rows': 0}),
    'derived': _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=derived),
    **{field: _reference_schema_for_stage(prepared, {field}, device_ids=('SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT',), port_intent=field == 'ports') for field in ('ports', 'measurements', 'commands')},
    'singleton-full': _reference_schema_for_stage(prepared, {'devices'}, inventory_target={'fact_id': declared, 'minimum_rows': 1, 'names': ['SCHEMA_ONLY_NOT_A_MODEL_PARTICIPANT']}),
    'empty-derived-full': _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=derived),
}
for name, schema in schemas.items():
    assert schema == json.loads((OUT / (name + '-decoder-schema.json')).read_text(encoding='utf8')), name
write('final-schema-equality-proof.json', {'scope': 'Exact final private schema objects and schema-function AST equal the actually tested compiler/arity fixtures. Only raw metadata duplicate guards/order changed after these native probes; no new original/model/simulation proof.',
    'prior_reasoner': {'path': str(prior_reasoner), 'sha256': sha(prior_reasoner)},
    'final_reasoner_sha256': sha(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'),
    'exact_schemas_rechecked': list(schemas), 'native_probe_origin': {'path': str(probe_path), 'sha256': sha(probe_path)}})
intake_name = 'backend/nis/agent/orchestration/project_intake.py'
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
write('source-change-scope-proof.json', {
    'unchanged_other_methods_including_intake_and_defaults': True,
    'unchanged_document_intake_methods_and_response_validation': True,
    'unchanged_nonreference_module_ast_including_imports_and_constants': True,
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
    'affected_isolated_cases': len(cases), 'failures': 0, 'errors': 0, 'skipped': 0,
    'xml_sha256': sha(OUT / 'affected-reference-regressions.xml'),
    'native_compiler_probes': 7, 'completed_native_grammar_fixtures': 2, 'native_original_pass': False,
    'source_hashes_recorded_after_run_no_edits_during_run': frozen,
    'native_original_plan_pass': False, 'simulation_pass': False, 'full_release_pass': False,
    'productive_delivery': False})
print(json.dumps({'cases_passed': len(cases), 'compiler_probes': 7, 'completed_grammar_fixtures': 2, 'identity': identity['source_sha256']}))
