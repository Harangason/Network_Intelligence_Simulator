"""Import the exact preserved source-only test bundles into this normal candidate.

Normal API only. No generated model, route, signal, profile or SQL replacement.
Actual Qwen intake remains explicitly attributed to the earlier 36f image.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--receipt', type=Path, required=True)
repair = parser.add_mutually_exclusive_group()
repair.add_argument('--context-repair-dir', type=Path)
repair.add_argument('--inventory-cardinality-repair-dir', type=Path)
repair.add_argument('--inventory-progress-repair-dir', type=Path)
repair.add_argument('--context-cache-progress-repair-dir', type=Path)
repair.add_argument('--launcher-repair-dir', type=Path)
repair.add_argument('--fresh-id-repair-dir', type=Path)
repair.add_argument('--throughput-repair-dir', type=Path)
repair.add_argument('--source-binding-repair-dir', type=Path)
repair.add_argument('--selected-identity-repair-dir', type=Path)
repair.add_argument('--cache-output-repair-dir', type=Path)
repair.add_argument('--inventory-focus-repair-dir', type=Path)
repair.add_argument('--known-owner-field-repair-dir', type=Path)
repair.add_argument('--port-intent-identity-repair-dir', type=Path)
repair.add_argument('--port-response-paging-repair-dir', type=Path)
parser.add_argument('--destination-prefix', default='native-waitress-lifecycle')
args = parser.parse_args()
port_response_dir = args.port_response_paging_repair_dir.resolve() if args.port_response_paging_repair_dir else None
port_intent_dir = (port_response_dir.parent if port_response_dir else
                   args.port_intent_identity_repair_dir.resolve() if args.port_intent_identity_repair_dir else None)
known_owner_dir = (port_intent_dir.parent if port_intent_dir else
                   args.known_owner_field_repair_dir.resolve() if args.known_owner_field_repair_dir else None)
inventory_focus_dir = (known_owner_dir.parent if known_owner_dir else
                       args.inventory_focus_repair_dir.resolve() if args.inventory_focus_repair_dir else None)
cache_output_dir = (inventory_focus_dir.parent if inventory_focus_dir else
                    args.cache_output_repair_dir.resolve() if args.cache_output_repair_dir else None)
selected_identity_dir = (cache_output_dir.parent if cache_output_dir else
                         args.selected_identity_repair_dir.resolve() if args.selected_identity_repair_dir else None)
source_binding_dir = (selected_identity_dir.parent if selected_identity_dir else
                      args.source_binding_repair_dir.resolve() if args.source_binding_repair_dir else None)
if source_binding_dir:
    # Keep the verified4da3 chain immutable. Its prior snapshots are evidence,
    # never a claim that the newly repaired app has the old source identity.
    args.throughput_repair_dir = source_binding_dir.parent
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
ROOT = OUT.parents[5]
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
assert re.fullmatch('[a-z0-9-]+', args.destination_prefix)
repair_dir = source_binding_dir or args.context_repair_dir or args.inventory_cardinality_repair_dir or args.inventory_progress_repair_dir or args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir
evidence_dir = repair_dir.resolve() if repair_dir else OUT
transfer_evidence_dir = port_response_dir or port_intent_dir or known_owner_dir or inventory_focus_dir or cache_output_dir or selected_identity_dir or evidence_dir
historical_dir = args.throughput_repair_dir.resolve() if source_binding_dir else evidence_dir
assert evidence_dir.is_relative_to(BASE.resolve())
assert transfer_evidence_dir.is_relative_to(BASE.resolve())
fresh_id_dir = (BASE / 'resume-20261021/inventory-binding-cardinality-repair/progress-decoder-repair/context-cache-progress-repair/launcher-repair/fresh-id-decoder-repair') if args.throughput_repair_dir else evidence_dir
identity = json.loads((transfer_evidence_dir / ('current-input-identity.json' if repair_dir else 'waitress-candidate-input-identity.json')).read_text(encoding='utf-8'))
port_intent_identity = (json.loads((port_intent_dir / 'current-input-identity.json').read_text())
                        if port_response_dir else identity)
known_owner_identity = (json.loads((known_owner_dir / 'current-input-identity.json').read_text())
                        if port_intent_dir else identity)
inventory_focus_identity = (json.loads((inventory_focus_dir / 'current-input-identity.json').read_text())
                            if known_owner_dir else identity)
cache_output_identity = (json.loads((cache_output_dir / 'current-input-identity.json').read_text())
                         if inventory_focus_dir else identity)
source_binding_identity = json.loads((evidence_dir / 'current-input-identity.json').read_text()) if selected_identity_dir else identity
selected_identity = (json.loads((selected_identity_dir / 'current-input-identity.json').read_text())
                     if selected_identity_dir else identity)
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
assert receipt['initial_source_sha256'] == identity['source_sha256']
assert receipt['initial_commit_id'] == identity['commit_id']
endpoint = urlsplit(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def known_owner_baseline_bytes(name):
    """Bind the parent repair to its exact pre-change source, not today's file."""
    before = known_owner_dir / 'before' / name if known_owner_dir else None
    return before.read_bytes() if before and before.is_file() else port_intent_baseline_bytes(name)


def port_intent_baseline_bytes(name):
    """Preserve the actual parent image/operator bytes across the child repair."""
    before = port_intent_dir / 'before' / name if port_intent_dir else None
    return before.read_bytes() if before and before.is_file() else port_response_baseline_bytes(name)


def port_response_baseline_bytes(name):
    """Read the exact prior port-identity image/operator, never today's child repair."""
    before = port_response_dir / 'before' / name if port_response_dir else None
    return (before if before and before.is_file() else ROOT / name).read_bytes()


def focus_baseline_bytes(name):
    """Read the immutable prior source, never relabel it as the new app."""
    before = inventory_focus_dir / 'before' / name if inventory_focus_dir else None
    return before.read_bytes() if before and before.is_file() else port_intent_baseline_bytes(name)


def context_baseline_bytes(name):
    # Bind historical b47 evidence to immutable before snapshots, then validate
    # the new current files separately. Never substitute historical app inputs.
    if (args.fresh_id_repair_dir or args.throughput_repair_dir) and name in {
            'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'}:
        return (fresh_id_dir / ('before-' + Path(name).name)).read_bytes()
    if args.throughput_repair_dir and (historical_dir / 'before' / name).is_file():
        return (historical_dir / 'before' / name).read_bytes()
    if cache_output_dir and (cache_output_dir / 'before' / name).is_file():
        return (cache_output_dir / 'before' / name).read_bytes()
    return focus_baseline_bytes(name)


def source_binding_baseline_bytes(name):
    if selected_identity_dir and (selected_identity_dir / 'before' / name).is_file():
        return (selected_identity_dir / 'before' / name).read_bytes()
    if cache_output_dir and (cache_output_dir / 'before' / name).is_file():
        return (cache_output_dir / 'before' / name).read_bytes()
    return focus_baseline_bytes(name)


def selected_identity_baseline_bytes(name):
    if cache_output_dir and (cache_output_dir / 'before' / name).is_file():
        return (cache_output_dir / 'before' / name).read_bytes()
    return focus_baseline_bytes(name)


def inspect(name):
    return json.loads(subprocess.check_output([D, 'inspect', name]))[0]


nonce = receipt['containers']['app'].removeprefix('nis-e2e-app-')
assert re.fullmatch('[0-9a-f]{12}', nonce)
assert receipt['containers']['db'] == 'nis-e2e-db-' + nonce
assert receipt['containers']['network'] == 'nis-e2e-network-' + nonce
app, db = inspect(receipt['containers']['app']), inspect(receipt['containers']['db'])
assert app['Image'] == receipt['image_id'] and app['State']['Running'] and db['State']['Running']
network = receipt['containers']['network']
assert app['HostConfig']['NetworkMode'] == db['HostConfig']['NetworkMode'] == network
assert app['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': str(endpoint.port)}]
assert app['NetworkSettings']['Networks'][network]['NetworkID'] == db['NetworkSettings']['Networks'][network]['NetworkID']
dsn = urlsplit(dict(value.split('=', 1) for value in app['Config']['Env'])['DATABASE_URL'])
aliases = set(db['NetworkSettings']['Networks'][network].get('Aliases') or [])
aliases.update(db['NetworkSettings']['Networks'][network].get('DNSNames') or [])
aliases.add(receipt['containers']['db'])
assert dsn.hostname in aliases and dsn.path == '/nis_test_e2e' and dsn.username == 'nis_test'
production = inspect('NetworkIS')['Image']
scope = json.loads((OUT.parent.parent / 'resume-20261019/inventory-choice-cardinality-repair/source-change-scope-proof.json').read_text(encoding='utf-8'))
current_scope = json.loads((OUT.parent / 'functional-hardware-stage-scope-repair/source-change-scope-proof.json').read_text(encoding='utf8'))
lifecycle_scope = json.loads((OUT / 'source-change-scope-proof.json').read_text(encoding='utf8'))
assert lifecycle_scope['reasoner_only_optional_cancellation_binding']
assert lifecycle_scope['provider_model_context_timeout_token_limit_schemas_semantics_unchanged']
assert current_scope['outside_private_schema_and_reference_planner_ast_unchanged']
assert current_scope['outside_nested_infer_and_plan_profile_ast_unchanged']
assert scope['unchanged_other_methods_including_intake_and_defaults']
assert scope['unchanged_document_intake_methods_and_response_validation']
assert scope['unchanged_nonreference_module_ast_including_imports_and_constants']
frozen = json.loads((OUT / 'waitress-validation-source-freeze.json').read_text(encoding='utf-8'))
if args.context_repair_dir:
    context_proof = json.loads((evidence_dir / 'source-scope-proof.json').read_text())
    assert context_proof['all_other_application_ast_unchanged']
    assert context_proof['no_source_reference_candidate_or_retry_truncation']
    assert context_proof['no_model_provider_budget_gate_change']
    freeze = json.loads((evidence_dir / 'candidate-prepare-freeze.json').read_text())
    assert freeze['identity'] == identity and freeze['targeted_current_cases'] == 253
    for name, digest in freeze['frozen_affected_files'].items():
        assert name in {'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'}
        assert sha((ROOT / name).read_bytes()) == digest
        frozen[name] = digest
if args.inventory_cardinality_repair_dir:
    proof = json.loads((evidence_dir / 'source-scope-proof.json').read_text())
    assert proof['continuation_and_whole_fact_worklist_AST_unchanged']
    assert proof['model_context_output_timeout_and_provider_AST_unchanged']
    assert proof['runtime_merge_and_public_validators_unchanged']
    previous_context = OUT.parent / 'reference-context-serialization-repair'
    for name in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'):
        assert (evidence_dir / 'before' / name).read_bytes() == (previous_context / 'after' / name).read_bytes()
    freeze = json.loads((evidence_dir / 'candidate-prepare-freeze.json').read_text())
    assert freeze['identity'] == identity and freeze['targeted_cases_in_two_disjoint_runs'] == 258
    for name, digest in freeze['frozen_affected_files'].items():
        assert name in {'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'}
        assert sha((ROOT / name).read_bytes()) == digest
        frozen[name] = digest
if args.inventory_progress_repair_dir:
    proof = json.loads((evidence_dir / 'source-scope-proof.json').read_text())
    assert proof['whole_continuation_class_AST_unchanged_except_terminal_logging']
    assert proof['model_context_output_timeout_and_provider_unchanged']
    assert proof['all_runtime_merge_public_validators_unchanged']
    assert proof['no_original_text_edited']
    for name in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'):
        assert (evidence_dir / 'before' / name).read_bytes() == (evidence_dir.parent / 'after' / name).read_bytes()
    freeze = json.loads((evidence_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in identity} == identity
    assert freeze['targeted_distinct_cases'] == 262 and freeze['native_grammar_cases'] == 2
    result = json.loads((evidence_dir / 'candidate-prepare-result.json').read_text())
    assert result['exit_code'] == 0 and result['source_sha256'] == identity['source_sha256']
    aggregate = json.loads((evidence_dir / 'regression-aggregate.json').read_text())
    assert aggregate['distinct_latest_pass'] == 262 and all(row['latest_pass'] for row in aggregate['cases'])
    for row in aggregate['runs']:
        assert sha(Path(row['xml']['path']).read_bytes()) == row['xml']['sha256']
    grammar = json.loads((evidence_dir / 'native-grammar/result.json').read_text())
    assert grammar['status'] == 'PASSED' and len(grammar['results']) == 2
    assert all(row['schema_and_runtime_progress_valid'] for row in grammar['results'])
    work = json.loads((evidence_dir / 'workload.json').read_text())
    for row in work['after']:
        snapshot = Path(row['path'])
        name = snapshot.relative_to(evidence_dir / 'after').as_posix()
        assert name in {'backend/nis/agent/orchestration/local_reasoner.py',
                        'backend/tests/test_reference_reasoner.py', 'backend/tests/test_reference_design.py'}
        assert sha(snapshot.read_bytes()) == row['sha256'] == sha((ROOT / name).read_bytes())
        frozen[name] = row['sha256']
if args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir:
    launcher_dir = fresh_id_dir.parent if args.fresh_id_repair_dir or args.throughput_repair_dir else evidence_dir
    context_dir = launcher_dir.parent if args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir else evidence_dir
    if args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir:
        launcher_identity = json.loads((launcher_dir / 'current-input-identity.json').read_text())
        launcher_proof = json.loads((launcher_dir / 'source-scope-proof.json').read_text())
        assert launcher_proof['only_application_source_changed'] == 'scripts/dev/launch-networkis.py'
        assert launcher_proof['native_reasoner_preview_models_provider_budgets_validators_unchanged'] is True
        assert launcher_proof['canonical_after'] == launcher_identity
        assert launcher_proof['canonical_before']['source_sha256'] == json.loads((context_dir / 'prepared-current-identity.json').read_text())['source_sha256']
        launcher_freeze = json.loads((launcher_dir / 'candidate-prepare-freeze.json').read_text())
        assert {key: launcher_freeze[key] for key in launcher_identity} == launcher_identity
        assert json.loads((launcher_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
        for name, digest in launcher_freeze['frozen_affected_files'].items():
            assert sha(context_baseline_bytes(name)) == digest
            frozen[name] = digest
    proof = json.loads((context_dir / 'source-scope-proof.json').read_text(encoding='utf-8'))
    for key in ('all_other_reasoner_methods_AST_unchanged',
                'all_other_module_definitions_including_public_schema_and_merge_gates_AST_unchanged',
                'whole_fact_worklist_and_continuation_AST_unchanged_except_history_reset',
                'provider_model_maximum_output_timeout_configuration_AST_unchanged',
                'no_source_reference_candidate_or_retry_truncation'):
        assert proof[key] is True
    assert proof['configured_capacity_fixed_not_increased'] == 131072
    assert json.loads((context_dir / 'native-cache/reviewed-result.json').read_text())['status'] == 'PASSED'
    freeze = json.loads((context_dir / 'candidate-prepare-freeze.json').read_text())
    context_identity = json.loads((context_dir / 'prepared-current-identity.json').read_text()) if args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir else identity
    assert {key: freeze[key] for key in context_identity} == context_identity
    assert json.loads((context_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    # The prior d399 repair is historical evidence, not a claim about this new
    # source. Bind its exact saved files to this repair's before snapshots.
    parent_work = json.loads((context_dir.parent / 'workload.json').read_text())
    for row in parent_work['after']:
        snapshot = Path(row['path'])
        name = snapshot.relative_to(context_dir.parent / 'after').as_posix()
        before = context_dir / ('before-' + Path(name).name)
        baseline = before if before.exists() else ROOT / name
        if args.throughput_repair_dir and not before.exists() and (historical_dir / 'before' / name).is_file():
            baseline = historical_dir / 'before' / name
        if inventory_focus_dir and baseline == ROOT / name and (inventory_focus_dir / 'before' / name).is_file():
            baseline = inventory_focus_dir / 'before' / name
        assert sha(snapshot.read_bytes()) == row['sha256'] == sha(baseline.read_bytes())
        frozen[name] = row['sha256']
    current_work = json.loads((context_dir / 'workload.json').read_text())
    for row in current_work['after']:
        snapshot = Path(row['path'])
        name = snapshot.relative_to(context_dir / 'after').as_posix()
        assert name in {'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py',
                        'frontend/src/features/agent/lib/engineering-specification.ts',
                        'frontend/src/features/agent/lib/engineering-specification.test.mjs'}
        assert sha(snapshot.read_bytes()) == row['sha256'] == sha(context_baseline_bytes(name))
        frozen[name] = row['sha256']
if args.fresh_id_repair_dir or args.throughput_repair_dir:
    fresh_identity = json.loads((fresh_id_dir / 'current-input-identity.json').read_text()) if args.throughput_repair_dir else identity
    proof = json.loads((fresh_id_dir / 'source-scope-proof.json').read_text())
    for key in ('private_schema_only_adds_exact_new_id_enum',
                'runtime_identity_guard_condition_and_merge_AST_unchanged',
                'provider_model_maximum_output_timeout_worklist_AST_unchanged',
                'public_model_schemas_source_scope_and_existing_identity_domain_unchanged'):
        assert proof[key] is True
    assert proof['canonical_before']['source_sha256'] == launcher_identity['source_sha256']
    assert {key: proof['canonical_after'][key] for key in fresh_identity} == fresh_identity
    freeze = json.loads((fresh_id_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in fresh_identity} == fresh_identity
    assert json.loads((fresh_id_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    grammar = json.loads((fresh_id_dir / 'native-grammar-enum/result.json').read_text())
    assert grammar['status'] == 'PASSED' and len(grammar['results']) == 6
    for name, digest in freeze['frozen_affected_files'].items():
        baseline = historical_dir / 'before' / name if args.throughput_repair_dir else ROOT / name
        assert sha(baseline.read_bytes() if baseline.exists() else focus_baseline_bytes(name)) == digest
        frozen[name] = digest
if args.throughput_repair_dir:
    throughput_identity = json.loads((historical_dir / 'current-input-identity.json').read_text()) if source_binding_dir else identity
    proof = json.loads((historical_dir / 'source-scope-proof.json').read_text())
    assert proof['canonical_before']['source_sha256'] == fresh_identity['source_sha256']
    assert proof['canonical_after']['source_sha256'] == throughput_identity['source_sha256']
    assert proof['only_application_delta'] == 'backend/nis/agent/orchestration/local_reasoner.py'
    for key in ('all_other_reasoner_methods_including_model_provider_context_timeout_AST_unchanged',
                'complete_UTF8_guard_and_output_reserve_AST_unchanged',
                'exact_port_parameter_merge_AST_unchanged',
                'source_fact_worklists_and_declared_inventory_loops_AST_unchanged',
                'all_existing_identity_source_member_reference_checks_preserved_AST'):
        assert proof[key] is True
    freeze = json.loads((historical_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in throughput_identity} == throughput_identity
    assert freeze['complete_regression_cases'] > 568 and freeze['complete_regressions_passed'] is True
    assert freeze['validation_evidence']
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    assert json.loads((historical_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    native = json.loads((historical_dir / 'native-continuous-anchor/result.json').read_text())
    assert native['status'] == 'PASS_CONTINUOUS_WORKER_APPEND_AND_ANCHORED_REBASE'
    assert native['actual_worker_continuity_all3'] and native['all_sources_copies_and_expected_values_exact']
    for name, digest in freeze['frozen_affected_files'].items():
        baseline = evidence_dir / 'before' / name if source_binding_dir else ROOT / name
        assert sha(baseline.read_bytes() if baseline.exists() else selected_identity_baseline_bytes(name)) == digest
        frozen[name] = digest
if source_binding_dir:
    proof = json.loads((evidence_dir / 'source-scope-proof.json').read_text())
    assert proof['canonical_before']['source_sha256'] == throughput_identity['source_sha256']
    assert proof['canonical_after']['source_sha256'] == source_binding_identity['source_sha256']
    assert set(proof['application_delta']) == {'backend/nis/agent/orchestration/local_reasoner.py',
                                            'backend/nis/domain/inventory-vocabulary.json',
                                            'frontend/src/features/agent/lib/inventory-vocabulary.json'}
    assert proof['derived_frontend_vocabulary_exact_authoritative_backend_bytes']
    assert (ROOT / 'frontend/src/features/agent/lib/inventory-vocabulary.json').read_bytes() == (ROOT / 'backend/nis/domain/inventory-vocabulary.json').read_bytes()
    projected = json.loads((evidence_dir / 'projection-sync-repair/independent-image-source-proof.json').read_text())
    assert projected['all_normalized_application_files_exact'] and projected['source_file_count'] == 2313
    assert projected['host_source_sha256'] == projected['actual_image_source_sha256'] == source_binding_identity['source_sha256']
    previous_candidate = json.loads((evidence_dir / 'prepared-candidate.json').read_text()) if selected_identity_dir else None
    assert projected['image_id'] == (previous_candidate['image_id'] if previous_candidate else receipt['image_id'])
    if previous_candidate:
        assert previous_candidate['status'] == 'PREPARED' and previous_candidate['source_sha256'] == source_binding_identity['source_sha256']
    for key in ('all_other_reasoner_methods_including_model_provider_context_timeout_AST_unchanged',
                'complete_UTF8_guard_and_output_reserve_AST_unchanged',
                'exact_port_parameter_merge_AST_unchanged',
                'all_existing_identity_source_member_reference_checks_preserved_AST',
                'complete_fact_worklist_preserved_with_explicit16_batch',
                'lossless_profile_source_intervals_and_independent_profiles'):
        assert proof[key] is True
    original_scope = json.loads((evidence_dir / 'actual-original-projection-proof.json').read_text())
    assert len(original_scope) == 2 and all(row['all_intervals_have_owners'] for row in original_scope)
    assert original_scope[0]['whole_source_equal'] and len(original_scope[1]['profiles']) == 10
    native = json.loads((evidence_dir / 'native-ordered-bindings/result.json').read_text())
    assert native['status'] == 'PASS' and native['identities'] == 2 and native['fact_bindings'] == 4
    boundary = json.loads((evidence_dir / 'native-ordered-boundary/result.json').read_text())
    assert boundary['status'] == 'PASS' and boundary['identities'] == 8 and boundary['fact_bindings'] == 16
    assert boundary['local_reasoner_sha256'] == native['local_reasoner_sha256']
    binding = json.loads((evidence_dir / 'native-scope-binding.json').read_text())
    assert binding['all_module_level_decoder_runtime_transport_helpers_AST_exact']
    assert binding['exact_whole_module_bytes_for_both_native_controls']
    assert binding['current_local_reasoner_sha256'] == sha(source_binding_baseline_bytes('backend/nis/agent/orchestration/local_reasoner.py'))
    freeze = json.loads((evidence_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in source_binding_identity} == source_binding_identity
    assert freeze['complete_regression_cases'] > 587 and freeze['complete_regressions_passed'] is True
    assert freeze['validation_evidence']
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    assert json.loads((evidence_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha(source_binding_baseline_bytes(name)) == digest
        frozen[name] = digest
if selected_identity_dir:
    proof = json.loads((selected_identity_dir / 'source-scope-proof.json').read_text())
    assert proof['canonical_before']['source_sha256'] == source_binding_identity['source_sha256']
    assert proof['canonical_after']['source_sha256'] == selected_identity['source_sha256']
    assert proof['application_delta'] == ['backend/nis/agent/orchestration/local_reasoner.py']
    for key in ('all_other_module_and_class_definitions_AST_exact',
                'entire_reference_pipeline_AST_exact_except_private_selected_output_expansion_instruction_and_progress',
                'public_port_merge_and_source_inventory_guards_AST_exact',
                'model_provider_context_output_timeout_request_AST_exact'):
        assert proof[key] is True
    for name in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'):
        assert (selected_identity_dir / 'before' / name).read_bytes() == (evidence_dir / 'after' / name).read_bytes()
    freeze = json.loads((selected_identity_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in selected_identity} == selected_identity
    assert freeze['complete_regression_cases'] == 616 and freeze['complete_regressions_passed'] is True
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    controls = json.loads((selected_identity_dir / 'native-selected-controls.json').read_text())
    assert controls['status'] == 'PASS' and controls['actual_native_responses'] == 4
    assert {row['case'] for row in controls['results']} == {
        'ports-positive', 'ports-counter', 'functions-positive', 'functions-counter'}
    current_module_hash = sha(selected_identity_baseline_bytes('backend/nis/agent/orchestration/local_reasoner.py'))
    assert controls['local_reasoner_sha256'] == current_module_hash
    for row in controls['results']:
        for key in ('result', 'request', 'response'):
            assert sha(Path(row[key]['path']).read_bytes()) == row[key]['sha256']
        result = json.loads(Path(row['result']['path']).read_text())
        assert result['status'] == 'PASS' and result['actual_native_responses'] == 1
        assert result['local_reasoner_sha256'] == current_module_hash and result['complete_original_acceptance'] is False
    assert json.loads((selected_identity_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    for name, digest in freeze['frozen_affected_files'].items():
        assert name in {'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py',
                        'backend/tests/test_reference_selected_identity.py'}
        assert sha(selected_identity_baseline_bytes(name)) == digest
        frozen[name] = digest
if cache_output_dir:
    proof = json.loads((cache_output_dir / 'source-scope-proof.json').read_text())
    assert proof['canonical_before']['source_sha256'] == selected_identity['source_sha256']
    assert proof['canonical_after']['source_sha256'] == cache_output_identity['source_sha256']
    assert proof['application_delta'] == ['backend/nis/agent/orchestration/local_reasoner.py']
    for key in ('all_other_module_and_class_definitions_AST_exact',
                'whole_plan_pipeline_AST_exact_except_reviewed_private_anchor_bookkeeping_instruction_and_progress',
                'public_model_merge_source_identity_and_continuation_guards_AST_exact',
                'model_provider_maximum_output_timeout_and_byte_guard_AST_exact'):
        assert proof[key] is True
    for name in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py',
                 'backend/tests/test_reference_selected_identity.py'):
        assert sha((cache_output_dir / 'before' / name).read_bytes()) == json.loads(
            (selected_identity_dir / 'candidate-prepare-freeze.json').read_text())['frozen_affected_files'][name]
    freeze = json.loads((cache_output_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in cache_output_identity} == cache_output_identity
    assert freeze['complete_regression_cases'] == 629 and freeze['complete_regressions_passed'] is True
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    controls = json.loads((cache_output_dir / 'native-controls-3/result.json').read_text())
    assert controls['status'] == 'PASS' and len(controls['cases']) == 6
    assert sum(row['actual_native_responses'] for row in controls['cases']) == 9
    module_hash = sha(focus_baseline_bytes('backend/nis/agent/orchestration/local_reasoner.py'))
    assert all(row['status'] == 'PASS' and row['local_reasoner_sha256'] == module_hash
               and row['canonical_writes'] is False and row['complete_original_acceptance'] is False
               for row in controls['cases'])
    assert json.loads((cache_output_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha(focus_baseline_bytes(name)) == digest
        frozen[name] = digest
if inventory_focus_dir:
    proof = json.loads((inventory_focus_dir / 'source-scope-proof.json').read_text())
    assert proof['status'] == 'PASS_SOURCE_SCOPE_ONLY'
    assert proof['current_source_sha256'] == inventory_focus_identity['source_sha256']
    assert proof['all_source_files'] == 2313
    assert set(proof['changed_application_files']) == {
        'backend/nis/agent/orchestration/local_reasoner.py',
        'backend/nis/agent/orchestration/project_intake.py'}
    for key in ('planner_AST_exact_except_selected_scope_instruction_and_visible_selection_metadata',
                'context_helpers_snapshot_patch_window_stream_AST_exact',
                'public_validator_AST_exact_except_cross_literal_member_name_check',
                'whole_original_worklists_loops_quantities_merge_provider_model_context_output_timeout_unchanged'):
        assert proof[key] is True
    previous_files = json.loads((cache_output_dir / 'actual-host-source-files.json').read_text())['files']
    current_files = json.loads((inventory_focus_dir / 'actual-host-source-files.json').read_text())['files']
    for entries, expected in ((previous_files, cache_output_identity['source_sha256']),
                              (current_files, inventory_focus_identity['source_sha256'])):
        assert sha(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()) == expected
    assert set(previous_files) == set(current_files)
    assert {name for name in current_files if current_files[name] != previous_files[name]} == set(proof['changed_application_files'])
    for name in proof['changed_application_files']:
        assert sha((inventory_focus_dir / 'before' / name).read_bytes().replace(b'\r\n', b'\n')) == previous_files[name]
        assert sha(known_owner_baseline_bytes(name).replace(b'\r\n', b'\n')) == current_files[name]
    freeze = json.loads((inventory_focus_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in inventory_focus_identity} == inventory_focus_identity
    assert freeze['targeted_regression_cases'] == 341 and freeze['targeted_regressions_passed'] is True
    assert freeze['fresh_native_acceptance_claimed'] is False
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    result = json.loads((inventory_focus_dir / 'candidate-prepare-result.json').read_text())
    assert result['exit_code'] == 0 and result['source_sha256'] == inventory_focus_identity['source_sha256']
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha(known_owner_baseline_bytes(name)) == digest
        frozen[name] = digest
if known_owner_dir:
    proof = json.loads((known_owner_dir / 'source-scope-proof.json').read_text())
    assert proof['status'] == 'PASS_SOURCE_SCOPE_ONLY'
    assert proof['canonical_before']['source_sha256'] == inventory_focus_identity['source_sha256']
    assert {key: proof['canonical_after'][key] for key in known_owner_identity} == known_owner_identity
    assert proof['changed_application_files'] == ['backend/nis/agent/orchestration/local_reasoner.py']
    assert proof['only_private_schema_factory_AST_changed'] is True
    assert proof['public_gates_and_full_planner_AST_exact'] is True
    previous_files = json.loads((inventory_focus_dir / 'actual-host-source-files.json').read_text())['files']
    current_files = json.loads((known_owner_dir / 'actual-host-source-files.json').read_text())['files']
    for entries, expected in ((previous_files, inventory_focus_identity['source_sha256']),
                              (current_files, known_owner_identity['source_sha256'])):
        assert sha(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()) == expected
    assert set(previous_files) == set(current_files) and len(current_files) == 2313
    assert [name for name in sorted(current_files) if current_files[name] != previous_files[name]] == proof['changed_application_files']
    for name in proof['changed_application_files']:
        assert sha(known_owner_baseline_bytes(name).replace(b'\r\n', b'\n')) == previous_files[name]
        assert sha(port_intent_baseline_bytes(name).replace(b'\r\n', b'\n')) == current_files[name]
    freeze = json.loads((known_owner_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in known_owner_identity} == known_owner_identity
    assert freeze['targeted_regression_cases'] >= 9 and freeze['targeted_regressions_passed'] is True
    assert freeze['fresh_native_acceptance_claimed'] is False
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    result = json.loads((known_owner_dir / 'candidate-prepare-result.json').read_text())
    assert result['exit_code'] == 0 and result['source_sha256'] == known_owner_identity['source_sha256']
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha(port_intent_baseline_bytes(name)) == digest
        frozen[name] = digest
if port_intent_dir:
    proof = json.loads((port_intent_dir / 'source-scope-proof.json').read_text())
    assert proof['allowed_app_changes'] == ['backend/nis/agent/orchestration/local_reasoner.py']
    assert proof['public_validation_unchanged'] and proof['model_provider_context_output_timeout_unchanged']
    previous_files = json.loads((known_owner_dir / 'actual-host-source-files.json').read_text())['files']
    current_files = json.loads((port_intent_dir / 'actual-host-source-files.json').read_text())['files']
    for entries, expected in ((previous_files, known_owner_identity['source_sha256']),
                              (current_files, port_intent_identity['source_sha256'])):
        assert sha(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()) == expected
    assert set(previous_files) == set(current_files) and len(current_files) == 2313
    assert [name for name in sorted(current_files) if current_files[name] != previous_files[name]] == proof['allowed_app_changes']
    for name in proof['allowed_app_changes']:
        assert sha(port_intent_baseline_bytes(name).replace(b'\r\n', b'\n')) == previous_files[name]
        assert sha(port_response_baseline_bytes(name).replace(b'\r\n', b'\n')) == current_files[name]
    freeze = json.loads((port_intent_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in port_intent_identity} == port_intent_identity
    assert freeze['targeted_regressions_passed'] and freeze['native_grammar_passed']
    assert freeze['fresh_native_acceptance_claimed'] is False
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    result = json.loads((port_intent_dir / 'candidate-prepare-result.json').read_text())
    assert result['exit_code'] == 0 and result['source_sha256'] == port_intent_identity['source_sha256']
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha(port_response_baseline_bytes(name)) == digest
        frozen[name] = digest
if port_response_dir:
    proof = json.loads((port_response_dir / 'source-scope-proof.json').read_text())
    assert proof['unmodified_module_AST_outside_private_schema_and_plan_method']
    assert proof['all_previous_non_length_raise_ASTs_preserved'] and proof['provider_options_AST_exact']
    assert proof['actual_frozen_image_source_files_compared'] == 2313
    assert proof['all_other2312_frozen_source_files_exact']
    previous_files = json.loads((port_intent_dir / 'actual-host-source-files.json').read_text())['files']
    current_files = json.loads((port_response_dir / 'actual-host-source-files.json').read_text())['files']
    for entries, expected in ((previous_files, port_intent_identity['source_sha256']),
                              (current_files, identity['source_sha256'])):
        assert sha(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()) == expected
    assert set(previous_files) == set(current_files) and len(current_files) == 2313
    assert [name for name in sorted(current_files) if current_files[name] != previous_files[name]] == ['backend/nis/agent/orchestration/local_reasoner.py']
    for change in proof['actual_changed_application_files']:
        name = change['path']
        assert change['before'] == previous_files[name] and change['after'] == current_files[name]
        assert sha(port_response_baseline_bytes(name).replace(b'\r\n', b'\n')) == previous_files[name]
        assert sha((ROOT / name).read_bytes().replace(b'\r\n', b'\n')) == current_files[name]
    freeze = json.loads((port_response_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in identity} == identity
    assert freeze['targeted_regressions_passed'] and freeze['native_grammar_passed']
    assert freeze['fresh_native_acceptance_claimed'] is False
    for saved in freeze['validation_evidence']:
        assert sha(Path(saved['path']).read_bytes()) == saved['sha256']
    result = json.loads((port_response_dir / 'candidate-prepare-result.json').read_text())
    assert result['exit_code'] == 0 and result['source_sha256'] == identity['source_sha256']
    for name, digest in freeze['frozen_affected_files'].items():
        assert sha((ROOT / name).read_bytes()) == digest
        frozen[name] = digest
assert all(sha((ROOT / name).read_bytes()) == digest for name, digest in frozen.items())


def empty(bundle, project):
    assert bundle['project_id'].removeprefix('network-project-') == project
    assert all(isinstance(rows, list) and not rows for rows in bundle['source_data'].values())
    assert all(isinstance(rows, list) and not rows for rows in bundle['project_data'].values())
    workflow = bundle['workflow']
    assert workflow['parameters'] == {} and workflow['topology'] == {}
    assert all(status == 'EMPTY' for status in workflow['statuses'].values())
    context = workflow.get('context') or {}
    assert set(context) <= {'active_project', 'active_workflow_step', 'engineering_wizard_settings',
        'project_name', 'selected_network', 'selected_object', 'selected_route', 'selected_signal', 'selected_simulation'}
    assert not any(context.get(key) for key in ('selected_network', 'selected_object', 'selected_route', 'selected_signal', 'selected_simulation'))
    if context.get('project_name'):
        assert context['project_name'].upper().startswith('TEST')


transfers = []
for case in ('vehicle', 'robot'):
    old_dir = BASE / ('native-staged-' + case)
    old_state_file = old_dir / 'state.json'
    old = json.loads(old_state_file.read_text(encoding='utf-8'))
    project = old['project_id']
    assert old['document_review_status'] == 'APPROVED_LITERAL_SOURCE_FINDINGS'
    assert sha(Path(old['source']).read_bytes()) == old['original_sha256']
    assert sha(Path(old['document_response']).read_bytes()) == old['reviewed_document_response_sha256']
    origin = old['document_origin']
    for normal, alternate, expected in (
        ('original_sha256', 'actual_original_sha256', old['original_sha256']),
        ('response_sha256', 'actual_response_sha256', old['document_response_sha256'])):
        values = [origin[key] for key in (normal, alternate) if key in origin]
        assert values and all(value == expected for value in values)
    previous = json.loads((old_dir / 'source-only-transfer.json').read_text(encoding='utf-8'))
    assert origin['image_id'] == previous['old_document_image_id']
    assert origin['source_sha256'] == '36f95018707e25958b5f19a28421185f69d26615610aa1350584ff534f381cb4'
    for name, digest in previous['unchanged_dependency_sha256'].items():
        if name == 'backend/nis/agent/orchestration/project_intake.py':
            assert sha(Path(scope['source_intake_baseline_snapshot']['path']).read_bytes()) == digest
            intake_frozen = json.loads((OUT / 'waitress-validation-source-freeze.json').read_text(encoding='utf-8'))
            if inventory_focus_dir:
                assert sha(focus_baseline_bytes(name)) == intake_frozen[name]
                assert sha((ROOT / name).read_bytes()) == frozen[name]
            else:
                assert sha((ROOT / name).read_bytes()) == intake_frozen[name]
        elif (args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir or args.throughput_repair_dir) and name == 'frontend/src/features/agent/lib/engineering-specification.ts':
            assert sha((context_dir / 'before-preview-engineering-specification.ts').read_bytes()) == digest
            assert sha((ROOT / name).read_bytes()) == frozen[name]
        elif source_binding_dir and name in {'backend/nis/domain/inventory-vocabulary.json',
                                             'frontend/src/features/agent/lib/inventory-vocabulary.json'}:
            assert sha((evidence_dir / 'before' / name).read_bytes()) == digest
            assert sha((ROOT / name).read_bytes()) == frozen[name]
        else:
            assert sha((ROOT / name).read_bytes()) == digest
    raw = (old_dir / 'normal-import-result-request.json').read_bytes()
    prior_import = next(row for row in previous['http_evidence'] if row['name'] == 'normal-import-result')
    assert sha(raw) == prior_import['request_sha256']
    payload = json.loads(raw)
    assert set(payload) == {'bundle'}
    empty(payload['bundle'], project)
    destination = BASE / (args.destination_prefix + '-' + case)
    destination.mkdir(exist_ok=False)
    record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'project_id': project,
        'source_state': {'path': str(old_state_file), 'sha256': sha(old_state_file.read_bytes())},
        'candidate_image_id': receipt['image_id'], 'source_sha256': identity['source_sha256'],
        'canonical_model_corrections': False, 'fresh_document_inference': False,
        'document_origin': origin, 'http_evidence': []}

    def request(name, path, body=None):
        if body is not None:
            (destination / (name + '-request.json')).write_bytes(body)
        req = Request(receipt['base_url'] + path, data=body,
            headers={'X-Project-ID': project, 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=180) as response:
                result, status = response.read(), response.status
        except HTTPError as error:
            (destination / (name + '-http-error.txt')).write_bytes(error.read())
            raise
        (destination / (name + '.json')).write_bytes(result)
        record['http_evidence'].append({'name': name, 'path': path, 'method': req.get_method(),
            'status': status, 'response_sha256': sha(result), 'request_sha256': sha(body) if body is not None else None})
        return json.loads(result)

    try:
        assert request('build-info', '/api/build-info')['source_sha256'] == identity['source_sha256']
        assert request('ready', '/api/ready')['status'] == 'ready'
        before = request('before-import', '/api/engineering/projects/export')
        empty(before, project)
        assert request('jobs-before-import', '/api/simulations')['jobs'] == []
        assert request('reference-before-import', '/api/engineering/agent/document-reference-design')['data'] is None
        request('normal-source-only-import', '/api/engineering/projects/import', raw)
        after = request('after-import', '/api/engineering/projects/export')
        empty(after, project)
        assert after['workflow'] == payload['bundle']['workflow']
        assert request('jobs-after-import', '/api/simulations')['jobs'] == []
        keep = ('source', 'original_sha256', 'original_chars', 'project_id', 'reference_sources',
            'document_response', 'document_response_sha256', 'document_review_status',
            'reviewed_document_response_sha256', 'document_origin', 'independent_source_review')
        state = {key: old[key] for key in keep if key in old}
        state.update(at_utc=record['at_utc'], base_url=receipt['base_url'], image_tag=receipt['image_tag'],
            image_id=receipt['image_id'], source_sha256=identity['source_sha256'], candidate_status='PREPARED',
            status='SOURCE_ONLY_IMPORTED_WAITING_NATIVE_REFERENCE', source_evidence_reused=True,
            source_transfer=str(destination / 'source-only-transfer.json'),
            scope='Exact normal API source-only import; immutable actual36f Qwen document evidence reused with explicit origin. No fresh intake, canonical model, simulation or full release PASS.',
            manual_model_corrections=False, model_generated=False, simulation_pass=False,
            full_release_pass=False, productive_delivery=False)
        (destination / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        record['status'] = 'SOURCE_ONLY_TRANSFER_VERIFIED'
        transfers.append({'case': case, 'project_id': project, 'state': str(destination / 'state.json')})
    except Exception as error:
        record['status'] = 'FAILED'
        record['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (destination / 'source-only-transfer.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert inspect('NetworkIS')['Image'] == production
(transfer_evidence_dir / 'waitress-source-only-transfer-result.json').write_text(json.dumps({'scope': __doc__,
    'transfers': transfers, 'production_changed': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'transfers': transfers, 'production_changed': False}, ensure_ascii=False))
