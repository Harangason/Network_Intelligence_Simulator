"""Resume real source-only test projects through the normal project import API.

Reuses immutable actual Qwen document findings with explicit original-image
provenance. It imports no generated model, route, signal or replacement profile.
Reference planning must revalidate those source findings in the ordinary product
path. No fresh document inference, complete native workflow or release PASS is
claimed by this transfer. Production and the old test stack are unchanged.
"""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--receipt', required=True, type=Path)
args = parser.parse_args()
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
endpoint = urlsplit(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}
D = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'


def inspect(name):
    return json.loads(subprocess.check_output([D, 'inspect', name]))[0]


assert receipt['containers']['app'].startswith('nis-e2e-app-')
assert receipt['containers']['db'].startswith('nis-e2e-db-')
nonce = receipt['containers']['app'].removeprefix('nis-e2e-app-')
assert re.fullmatch('[0-9a-f]{12}', nonce)
assert receipt['containers']['db'] == 'nis-e2e-db-' + nonce
assert receipt['containers']['network'] == 'nis-e2e-network-' + nonce
app = inspect(receipt['containers']['app'])
db = inspect(receipt['containers']['db'])
assert app['Image'] == receipt['image_id'] and app['State']['Running']
assert app['HostConfig']['NetworkMode'] == receipt['containers']['network']
assert app['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': str(endpoint.port)}]
assert db['State']['Running']
network = receipt['containers']['network']
assert db['HostConfig']['NetworkMode'] == network
actual_network = json.loads(subprocess.check_output([D, 'network', 'inspect', network]))[0]
assert actual_network['Name'] == network
assert app['NetworkSettings']['Networks'][network]['NetworkID'] == actual_network['Id']
assert db['NetworkSettings']['Networks'][network]['NetworkID'] == actual_network['Id']
database_url = urlsplit(dict(value.split('=', 1) for value in app['Config']['Env'])['DATABASE_URL'])
database_aliases = set(db['NetworkSettings']['Networks'][network].get('Aliases') or [])
database_aliases.update(db['NetworkSettings']['Networks'][network].get('DNSNames') or [])
database_aliases.add(receipt['containers']['db'])
assert database_url.hostname in database_aliases and database_url.path == '/nis_test_e2e'
assert database_url.username == 'nis_test' and database_url.port in {None, 5432}
production_image = inspect('NetworkIS')['Image']
method_proof = json.loads((OUT / 'unchanged-intake-methods.json').read_text(encoding='utf-8'))
assert method_proof['changed_class_methods'] == ['plan_reference_design']
assert method_proof['public_source_parser_byte_unchanged']
ROOT = OUT.parents[5]
after = OUT / 'after/backend/nis/agent/orchestration/local_reasoner.py'
assert hashlib.sha256(after.read_bytes()).hexdigest() == hashlib.sha256(
    (ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()
frozen = json.loads((OUT.parent / 'reference-grammar-repair/final-joint-owned-manifest.json').read_text(encoding='utf-8'))
dependency_hashes = {}
for name in ('backend/nis/agent/orchestration/project_intake.py',
             'frontend/src/features/agent/lib/document-clarification.ts',
             'frontend/src/features/agent/lib/engineering-specification.ts',
             'frontend/scripts/extract-wizard-specification.mjs',
             'backend/nis/domain/inventory-vocabulary.json',
             'frontend/src/features/agent/lib/inventory-vocabulary.json'):
    dependency_hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    assert dependency_hashes[name] == frozen[name]['current'], ('Intake dependency changed', name)


def method_hashes(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'LocalEngineeringReasoner')
    return {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


old_reasoner = OUT / 'before/backend/nis/agent/orchestration/local_reasoner.py'
assert hashlib.sha256(old_reasoner.read_bytes()).hexdigest() == frozen['backend/nis/agent/orchestration/local_reasoner.py']['current']
assert method_hashes(old_reasoner) == method_proof['before_method_digests']
assert method_hashes(ROOT / 'backend/nis/agent/orchestration/local_reasoner.py') == method_proof['after_method_digests']


def request(directory, audit, name, base, project, path, payload=None):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    if body is not None:
        (directory / (name + '-request.json')).write_bytes(body)
    req = Request(base + path, data=body,
                  headers={'X-Project-ID': project, 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=180) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        raw = error.read()
        (directory / (name + '-http-error.txt')).write_bytes(raw)
        audit.append({'name': name, 'path': path, 'http_status': error.code,
                      'request_sha256': hashlib.sha256(body).hexdigest() if body is not None else None,
                      'error_response_sha256': hashlib.sha256(raw).hexdigest()})
        raise
    # Persist the actual response before any parsing or semantic assertion.
    (directory / (name + '.json')).write_bytes(raw)
    audit.append({'name': name, 'path': path, 'http_status': status,
                  'request_sha256': hashlib.sha256(body).hexdigest() if body is not None else None,
                  'response_sha256': hashlib.sha256(raw).hexdigest(), 'response_bytes': len(raw)})
    return json.loads(raw)


def assert_source_only(bundle, project):
    assert bundle['project_id'].removeprefix('network-project-') == project
    if bundle.get('source_project_id'):
        assert bundle['source_project_id'].removeprefix('network-project-') == project
    assert all(isinstance(rows, list) and not rows for rows in bundle['source_data'].values())
    assert all(isinstance(rows, list) and not rows for rows in bundle['project_data'].values())
    workflow = bundle['workflow']
    assert workflow['project_id'].removeprefix('network-project-') == project
    assert workflow['parameters'] == {} and workflow['topology'] == {}
    assert workflow['statuses'] and all(status == 'EMPTY' for status in workflow['statuses'].values())
    context = workflow.get('context') or {}
    assert set(context) <= {'active_project', 'active_workflow_step', 'engineering_wizard_settings',
                           'project_name', 'selected_network', 'selected_object', 'selected_route',
                           'selected_signal', 'selected_simulation'}
    if context.get('active_project'):
        assert str(context['active_project']).removeprefix('network-project-') == project
    if context.get('project_name'):
        assert str(context['project_name']).upper().startswith('TEST')
    assert not any(context.get(key) for key in ('selected_network', 'selected_object', 'selected_route',
                                               'selected_signal', 'selected_simulation'))


records = []
for case in ('vehicle', 'robot'):
    old_dir = BASE / ('native-36f-' + case)
    state = json.loads((old_dir / 'state.json').read_text(encoding='utf-8'))
    project = state['project_id']
    assert state['document_review_status'] == 'APPROVED_LITERAL_SOURCE_FINDINGS'
    assert hashlib.sha256(Path(state['source']).read_bytes()).hexdigest() == state['original_sha256']
    assert hashlib.sha256(Path(state['document_response']).read_bytes()).hexdigest() == state['reviewed_document_response_sha256']
    document = json.loads(Path(state['document_response']).read_text(encoding='utf-8'))
    # Earlier actual source checkpoints used explicit actual_* names. Accept
    # either recorded spelling, require evidence, and reject conflicting aliases.
    origin = state['document_origin']
    original_digests = [origin[key] for key in ('original_sha256', 'actual_original_sha256') if key in origin]
    response_digests = [origin[key] for key in ('response_sha256', 'actual_response_sha256') if key in origin]
    assert original_digests and all(value == document['source_sha256'] == state['original_sha256'] for value in original_digests)
    assert response_digests and all(value == state['reviewed_document_response_sha256'] for value in response_digests)
    assert document['source_chars'] == state['original_chars']
    assert document['source_complete'] and document['canonical_writes'] is False
    assert document['provider'] == 'local_ollama' and document['status'] == 'REVIEW_REQUIRED'
    new_dir = BASE / ('native-staged-' + case)
    new_dir.mkdir(exist_ok=False)
    manifest = {'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__,
        'actual_project_id': project, 'old_base_url': state['base_url'], 'new_base_url': receipt['base_url'],
        'old_document_image_id': state['document_origin']['image_id'], 'new_image_id': receipt['image_id'],
        'canonical_model_corrections': False, 'fresh_document_inference': False, 'status': 'TRANSFER_INCOMPLETE',
        'unchanged_dependency_sha256': dependency_hashes, 'http_evidence': []}
    def read(name, path, *, old=False, payload=None):
        return request(new_dir, manifest['http_evidence'], name,
                       state['base_url'] if old else receipt['base_url'], project, path, payload)
    try:
        build = read('target-build-info', '/api/build-info')
        assert build['source_sha256'] == receipt['release']['source_sha256']
        assert read('target-ready', '/api/ready')['status'] == 'ready'
        original = read('original-source-only-bundle', '/api/engineering/projects/export', old=True)
        empty = read('target-before-import', '/api/engineering/projects/export')
        assert_source_only(original, project)
        assert_source_only(empty, project)
        assert read('target-jobs-before-import', '/api/simulations')['jobs'] == []
        imported = read('normal-import-result', '/api/engineering/projects/import', payload={'bundle': original})
        assert imported['project_id'].removeprefix('network-project-') == project
        after = read('target-after-import', '/api/engineering/projects/export')
        assert_source_only(after, project)
        assert after['project_id'].removeprefix('network-project-') == project
        assert after['source_data'] == original['source_data']
        assert not any(len(rows) for rows in after['source_data'].values())
        assert read('target-jobs-after-import', '/api/simulations')['jobs'] == []
        next_state = deepcopy(state)
        for field in ('error', 'ui_progress', 'post_failure_model_observation', 'reference_record', 'canonical_model_observation'):
            next_state.pop(field, None)
        next_state.update(at_utc=datetime.now(timezone.utc).isoformat(), status='SOURCE_ONLY_TRANSFERRED_WAITING_NATIVE_REFERENCE',
            base_url=receipt['base_url'], source_sha256=receipt['release']['source_sha256'],
            image_id=receipt['image_id'], image_tag=receipt['image_tag'], candidate_status='PREPARED',
            model_generated=False, simulation_pass=False, full_release_pass=False, productive_delivery=False,
            source_evidence_reused=True, source_origin_project_id=project,
            source_transfer_scope='Actual unchanged source-only evidence reused; no fresh Qwen intake on new image. Normal product reference preparation must revalidate all source evidence.',
            source_transfer=str((new_dir / 'source-only-transfer.json').resolve()))
        (new_dir / 'state.json').write_text(json.dumps(next_state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert inspect('NetworkIS')['Image'] == production_image
        manifest.update(status='SOURCE_ONLY_TRANSFER_VERIFIED', source_tables_all_empty=True,
                        document_response_sha256=state['reviewed_document_response_sha256'],
                        document_origin=state['document_origin'], product_import_result=imported['report'])
        records.append({'case': case, 'project_id': project, 'status': manifest['status']})
    except Exception as error:
        manifest.update(status='SOURCE_ONLY_TRANSFER_FAILED', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (new_dir / 'source-only-transfer.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'scope': __doc__, 'projects': records, 'production_changed': False}), flush=True)
