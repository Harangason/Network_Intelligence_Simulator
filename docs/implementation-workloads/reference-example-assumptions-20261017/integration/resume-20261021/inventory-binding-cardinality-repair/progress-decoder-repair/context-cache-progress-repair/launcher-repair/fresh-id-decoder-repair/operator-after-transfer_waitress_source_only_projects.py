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
parser.add_argument('--destination-prefix', default='native-waitress-lifecycle')
args = parser.parse_args()
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
ROOT = OUT.parents[5]
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
assert re.fullmatch('[a-z0-9-]+', args.destination_prefix)
repair_dir = args.context_repair_dir or args.inventory_cardinality_repair_dir or args.inventory_progress_repair_dir or args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir
evidence_dir = repair_dir.resolve() if repair_dir else OUT
assert evidence_dir.is_relative_to(BASE.resolve())
identity = json.loads((evidence_dir / ('current-input-identity.json' if repair_dir else 'waitress-candidate-input-identity.json')).read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
assert receipt['initial_source_sha256'] == identity['source_sha256']
assert receipt['initial_commit_id'] == identity['commit_id']
endpoint = urlsplit(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def context_baseline_bytes(name):
    # Bind historical b47 evidence to immutable before snapshots, then validate
    # the new current files separately. Never substitute historical app inputs.
    if args.fresh_id_repair_dir and name in {
            'backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py'}:
        return (evidence_dir / ('before-' + Path(name).name)).read_bytes()
    return (ROOT / name).read_bytes()


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
if args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir:
    launcher_dir = evidence_dir.parent if args.fresh_id_repair_dir else evidence_dir
    context_dir = launcher_dir.parent if args.launcher_repair_dir or args.fresh_id_repair_dir else evidence_dir
    if args.launcher_repair_dir or args.fresh_id_repair_dir:
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
    context_identity = json.loads((context_dir / 'prepared-current-identity.json').read_text()) if args.launcher_repair_dir or args.fresh_id_repair_dir else identity
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
if args.fresh_id_repair_dir:
    proof = json.loads((evidence_dir / 'source-scope-proof.json').read_text())
    for key in ('private_schema_only_adds_exact_new_id_enum',
                'runtime_identity_guard_condition_and_merge_AST_unchanged',
                'provider_model_maximum_output_timeout_worklist_AST_unchanged',
                'public_model_schemas_source_scope_and_existing_identity_domain_unchanged'):
        assert proof[key] is True
    assert proof['canonical_before']['source_sha256'] == launcher_identity['source_sha256']
    assert {key: proof['canonical_after'][key] for key in identity} == identity
    freeze = json.loads((evidence_dir / 'candidate-prepare-freeze.json').read_text())
    assert {key: freeze[key] for key in identity} == identity
    assert json.loads((evidence_dir / 'candidate-prepare-result.json').read_text())['exit_code'] == 0
    grammar = json.loads((evidence_dir / 'native-grammar-enum/result.json').read_text())
    assert grammar['status'] == 'PASSED' and len(grammar['results']) == 6
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
            assert sha((ROOT / name).read_bytes()) == intake_frozen[name]
        elif (args.context_cache_progress_repair_dir or args.launcher_repair_dir or args.fresh_id_repair_dir) and name == 'frontend/src/features/agent/lib/engineering-specification.ts':
            assert sha((context_dir / 'before-preview-engineering-specification.ts').read_bytes()) == digest
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
(evidence_dir / 'waitress-source-only-transfer-result.json').write_text(json.dumps({'scope': __doc__,
    'transfers': transfers, 'production_changed': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'transfers': transfers, 'production_changed': False}, ensure_ascii=False))
