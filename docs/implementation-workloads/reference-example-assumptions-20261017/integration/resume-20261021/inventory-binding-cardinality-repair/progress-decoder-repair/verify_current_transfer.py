"""Independently hash actual source-only imports and the live isolated stack."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[2]
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
RECEIPT = ROOT / 'backend/test-output/release-gates/joint-progress-inventory-originals-d399fecdc0b7/99b17a68b19b/receipt.json'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--receipt', type=Path)
parser.add_argument('--evidence-dir', type=Path)
parser.add_argument('--destination-prefix', default='native-progress')
args = parser.parse_args()
assert bool(args.receipt) == bool(args.evidence_dir)
assert re.fullmatch('native-[a-z-]+', args.destination_prefix)
if args.receipt:
    RECEIPT = args.receipt.resolve(strict=True)
    assert RECEIPT.is_relative_to((ROOT / 'backend/test-output/release-gates').resolve())
    OUT = args.evidence_dir.resolve(strict=True)
    assert OUT.is_relative_to(BASE.resolve())


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def inspect(name):
    return json.loads(subprocess.check_output([D, 'inspect', name]))[0]


receipt = read(RECEIPT)
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
actual_identity = read(OUT / 'prepared-current-identity.json')
for live, saved in (('source_sha256', 'initial_source_sha256'), ('commit_id', 'initial_commit_id'), ('verification_sha256', 'verification_sha256')):
    assert actual_identity[live] == receipt[saved]
app, db = [inspect(receipt['containers'][key]) for key in ('app', 'db')]
assert app['Image'] == receipt['image_id'] and app['State']['Running'] and db['State']['Running']
network = receipt['containers']['network']
assert set(app['NetworkSettings']['Networks']) == set(db['NetworkSettings']['Networks']) == {network}
dsn = urlsplit(dict(value.split('=', 1) for value in app['Config']['Env'])['DATABASE_URL'])
assert dsn.username == 'nis_test' and dsn.path == '/nis_test_e2e'
resolved = json.loads(subprocess.check_output([D, 'exec', receipt['containers']['app'], 'python', '-c',
    'import socket,json,sys; print(json.dumps(sorted(set(x[4][0] for x in socket.getaddrinfo(sys.argv[1],5432,type=socket.SOCK_STREAM)))))', dsn.hostname]))
assert resolved == [db['NetworkSettings']['Networks'][network]['IPAddress']]
assert app['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': str(urlsplit(receipt['base_url']).port)}]
assert inspect(receipt['image_tag'])['Id'] == receipt['image_id']
prod = inspect('NetworkIS')
assert prod['Image'] == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
assert prod['State']['Health']['Status'] == 'healthy'
rows, response_count, import_count = [], 0, 0
for case in ('vehicle', 'robot'):
    folder = BASE / (args.destination_prefix + '-' + case)
    state = read(folder / 'state.json')
    record = read(folder / 'source-only-transfer.json')
    assert record['status'] == 'SOURCE_ONLY_TRANSFER_VERIFIED'
    assert not record['fresh_document_inference'] and not record['canonical_model_corrections']
    assert state['image_id'] == record['candidate_image_id'] == receipt['image_id']
    assert state['source_sha256'] == actual_identity['source_sha256']
    assert len(record['http_evidence']) == 8
    for item in record['http_evidence']:
        response = folder / (item['name'] + '.json')
        assert ref(response)['sha256'] == item['response_sha256']
        assert item['status'] == 200
        response_count += 1
        if item['method'] == 'POST':
            assert item['name'] == 'normal-source-only-import'
            request = folder / (item['name'] + '-request.json')
            assert ref(request)['sha256'] == item['request_sha256']
            assert request.read_bytes() == (BASE / ('native-staged-' + case) / 'normal-import-result-request.json').read_bytes()
            import_count += 1
    assert ref(Path(state['source']))['sha256'] == state['original_sha256']
    assert ref(Path(state['document_response']))['sha256'] == state['reviewed_document_response_sha256']
    assert state['document_origin']['source_sha256'] == '36f95018707e25958b5f19a28421185f69d26615610aa1350584ff534f381cb4'
    exported = read(folder / 'after-import.json')
    assert all(not value for value in exported['source_data'].values())
    assert all(not value for value in exported['project_data'].values())
    assert read(folder / 'jobs-after-import.json')['jobs'] == []
    rows.append({'case': case, 'state': ref(folder / 'state.json'), 'transfer': ref(folder / 'source-only-transfer.json'),
                 'original': ref(Path(state['source'])), 'actual_historical_intake': ref(Path(state['document_response'])),
                 'canonical_model_empty': True, 'jobs_empty': True})
assert response_count == 16 and import_count == 2
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'INDEPENDENT_CURRENT_TRANSFER_VERIFIED',
          'receipt': ref(RECEIPT), 'image_id': receipt['image_id'], 'identity': actual_identity,
          'response_hashes_checked': response_count, 'exact_original_import_requests_checked': import_count,
          'cases': rows, 'production_image_unchanged': prod['Image'],
          'fresh_full_intake_claimed': False, 'full_models_simulations_gate_and_delivery_pending': True}
path = OUT / 'independent-current-transfer-review.json'
path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
child_path = OUT / 'transfer-operator-workload.json'
child = read(child_path)
child['status'] = 'COMPLETED'
child['outcomes']['normal_api_transfer_current_evidence'] = {'status': 'PASSED', 'evidence': [ref(path)]}
child['validations']['actual_hash_bound_source_only_transfer'] = {'status': 'PASSED', 'evidence': [ref(path)]}
child['remaining_findings'] = []
child_path.write_text(json.dumps(child, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'responses': response_count, 'import_requests': import_count, 'image_id': receipt['image_id']}))
