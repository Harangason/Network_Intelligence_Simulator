"""Retire the archived diagnostic only after its replacement is actually ready."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
spec = importlib.util.spec_from_file_location('previous_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
OLD = 'sha256:db0b949a1bb0926e8c6c95bd0a6a7484f6b1f65c8a009d9352c7f2184b70ce1f'
TAG = 'networkis:candidate-6d6fe881f4bd'
NEW_RECEIPT = ROOT / 'backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d/6d41919070e2/receipt.json'
ORIGINAL_AUDIT = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261021/inventory-binding-cardinality-repair/retire-6d6-stack/image-archive-audit.json'


def replacement():
    receipt = json.loads(NEW_RECEIPT.read_text())
    assert receipt['status'] == 'PREPARED' and receipt['image_id'] != OLD
    containers = prior.containers()
    app = next(c for c in containers if c['name'] == receipt['containers']['app'])
    assert app['image'] == receipt['image_id'] and app['state'] == 'running'
    with urlopen(receipt['base_url'] + '/api/ready', timeout=10) as response:
        assert response.status == 200
    with urlopen(receipt['base_url'] + '/api/build-info', timeout=10) as response:
        manifest = json.load(response)
    assert manifest['source_sha256'] == receipt['initial_source_sha256']
    assert not any(c['image'] == OLD for c in containers)
    return {'receipt': prior.ref(NEW_RECEIPT), 'image': receipt['image_id'], 'source': manifest['source_sha256'],
            'readiness': 'HTTP 200', 'status': 'PREPARED_ONLY_NOT_RELEASE_PASS'}


def verify():
    initial = json.loads((OUT / 'inventory-before.json').read_text())
    target = next(row for row in initial['images'] if row['id'] == OLD)
    archive = json.loads(ORIGINAL_AUDIT.read_text())['archive']
    # The existing owner exported by immutable ID, so Docker RepoTags is null.
    # Bind manifest/config/layers by their immutable OCI descriptors instead.
    verified, configs = set(), set()
    with tarfile.open(archive['path']) as tar:
        def check(desc):
            digest = desc['digest']
            if digest in verified:
                return
            member = tar.getmember('blobs/sha256/' + digest.split(':')[1])
            assert member.isfile() and member.size == desc['size']
            with tar.extractfile(member) as stream:
                assert 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() == digest
            verified.add(digest)
            if desc.get('mediaType', '').endswith(('index.v1+json', 'manifest.v1+json', 'manifest.v2+json', 'manifest.list.v2+json')):
                row = json.load(tar.extractfile(member))
                for child in row.get('manifests', []):
                    check(child)
                if 'config' in row:
                    configs.add('blobs/sha256/' + row['config']['digest'].split(':')[1])
                    check(row['config'])
                for child in row.get('layers', []):
                    check(child)
        index = json.load(tar.extractfile('index.json'))
        check(next(desc for desc in index['manifests'] if desc['digest'] == OLD))
        manifest = json.load(tar.extractfile('manifest.json'))
        entry = next(row for row in manifest if row['Config'] in configs)
        assert all(tar.getmember(layer).isfile() and 'sha256:' + layer.split('/')[-1] in verified for layer in entry['Layers'])
    actual = {'archive': prior.ref(Path(archive['path'])), 'image_count': 1,
              'verified_blobs': sorted(verified), 'index_config_and_all_layers_verified': True,
              'exported_by_immutable_id_without_tags': True}
    assert actual['archive']['sha256'] == archive['sha256']
    prior.write('old-diagnostic-archive-reverified.json', {**actual,
        'original_archive_audit': prior.ref(ORIGINAL_AUDIT), 'replacement': replacement(),
        'authorization': 'Current explicit request to identify and safely remove additionally unused old candidates; prior PREPARED cleanup authorization remains in force.',
        'no_original_receipt_modified': True})
    print(json.dumps({'verified': TAG, 'replacement': '6d41919070e2'}), flush=True)


def remove():
    completed = json.loads((OUT / 'additional-removal-result.json').read_text())
    assert completed['status'] == 'COMPLETED', 'Finish the original plan before extending the retired identities'
    proof = json.loads((OUT / 'old-diagnostic-archive-reverified.json').read_text())
    assert proof['archive'] == prior.ref(Path(proof['archive']['path']))
    current = replacement()
    rows = prior.receipts()[0]
    matches = [r for r in rows if r['image_id'] == OLD]
    assert matches and all(row['status'] == 'PREPARED' for row in matches)
    original = json.loads((OUT / 'inventory-before.json').read_text())
    assert prior.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == original['production']['image']
    assert prior.call('image', 'inspect', original['rollback'], '--format', '{{.Id}}') == original['rollback']
    actual = json.loads(prior.call('image', 'inspect', TAG))[0]
    assert actual['Id'] == OLD and actual['RepoTags'] == [TAG]
    assert not any(c['image'] == OLD for c in prior.containers())
    command = ['image', 'rm', '--no-prune', TAG]
    result = prior.call(*command)
    prior.write('old-diagnostic-removal.json', {'status': 'COMPLETED', 'epoch': time.time(),
        'image': OLD, 'command': [prior.DOCKER, *command], 'result': result,
        'archive_proof': prior.ref(OUT / 'old-diagnostic-archive-reverified.json'),
        'fresh_replacement': current, 'original_receipts_preserved': matches})
    prior.inventory('inventory-after-extra.json')
    print(json.dumps({'status': 'COMPLETED', 'extra_image_removed': TAG}), flush=True)


if __name__ == '__main__':
    {'verify': verify, 'remove': remove}[sys.argv[1]]()
