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
args = parser.parse_args()
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
ROOT = OUT.parents[5]
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
identity = json.loads((OUT / 'candidate-input-identity.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
assert receipt['initial_source_sha256'] == identity['source_sha256']
assert receipt['initial_commit_id'] == identity['commit_id']
endpoint = urlsplit(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


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
scope = json.loads((OUT / 'source-change-scope-proof.json').read_text(encoding='utf-8'))
assert scope['unchanged_other_methods_including_intake_and_defaults']
assert scope['unchanged_document_intake_methods_and_response_validation']
assert scope['unchanged_nonreference_module_ast_including_imports_and_constants']
owned = json.loads((OUT / 'candidate-owned-manifest.json').read_text(encoding='utf-8'))
assert all(sha((ROOT / name).read_bytes()) == row['current'] for name, row in owned.items())


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
            assert scope['previous_intake_module_sha256'] == digest
            assert sha(Path(scope['source_intake_baseline_snapshot']['path']).read_bytes()) == digest
            assert sha((ROOT / name).read_bytes()) == scope['current_intake_module_sha256']
        else:
            assert sha((ROOT / name).read_bytes()) == digest
    raw = (old_dir / 'normal-import-result-request.json').read_bytes()
    prior_import = next(row for row in previous['http_evidence'] if row['name'] == 'normal-import-result')
    assert sha(raw) == prior_import['request_sha256']
    payload = json.loads(raw)
    assert set(payload) == {'bundle'}
    empty(payload['bundle'], project)
    destination = BASE / ('native-binding-' + case)
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
(OUT / 'source-only-transfer-result.json').write_text(json.dumps({'scope': __doc__,
    'transfers': transfers, 'production_changed': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'transfers': transfers, 'production_changed': False}, ensure_ascii=False))
