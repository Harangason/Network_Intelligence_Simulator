"""Archive ten reviewed, unused historical NIS releases; never remove images."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
ARCHIVE = Path('F:/CodexOrdner/visualizations/2026/10/14/01a139b0-6181-7642-9f5d-563105609790/nis-ten-historical-images-20261018.tar')
TAGS = ['networkis:candidate-' + suffix for suffix in [
    '2457b564a4db', 'f34199bd9752', '34d0edc85798', 'a6258db4cc43',
    'b81ef9f92f9f', 'f4a5cb4ee572', 'bdc9bef1951e', 'e169e94e6a7a',
    'bcae78949b5f', 'f0aa30697855']]
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
spec = importlib.util.spec_from_file_location('release_storage_owner', ROOT / 'scripts/release/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()


def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.resolve()), 'sha256': digest, 'bytes': path.stat().st_size}


def inventory():
    original = json.loads((OUT / 'inventory.json').read_text())
    selected = [row for row in original['images'] if row['tags'] == [next((tag for tag in TAGS if tag in row['tags']), '')]]
    assert len(selected) == len(TAGS) == 10
    cids = call('ps', '-aq', '--no-trunc').split()
    containers = json.loads(call('inspect', *cids)) if cids else []
    used = {c['Image'] for c in containers}
    production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
    assert production == original['production']
    for row in selected:
        assert row['image_id'] not in used
        assert datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(row['created'].replace('Z', '+00:00')).timestamp() > storage.RETENTION_SECONDS
        actual = json.loads(call('image', 'inspect', row['tags'][0]))[0]
        assert actual['Id'] == row['image_id'] and actual['RepoTags'] == row['tags']
        assert row['receipts'] and all(r['status'] == 'PASS' for r in row['receipts'])
        for r in row['receipts']:
            p = Path(r['path'])
            assert ref(p)['sha256'] == r['sha256']
            assert storage.complete_pass(json.loads(p.read_text(encoding='utf-8-sig')))
    return selected, {'production': production, 'containers': [{'name': c['Name'], 'id': c['Id'], 'image_id': c['Image']} for c in containers]}


def main():
    selected, observed = inventory()
    assert shutil.disk_usage(ARCHIVE.parent).free > sum(row['size'] for row in selected) + 20 * 1024**3
    selection = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'ARCHIVE_ONLY_REVIEW_PENDING',
                 'human_instruction': '10 überflüssige Images löschen und die fehlenden Punkte abarbeiten',
                 'selected': selected, **observed,
                 'scope': 'Ten old unused complete-PASS releases only. Current production, rollback, all container references, unknown and active receipts retained. No assertion of full feature equivalence from dates or PASS alone.',
                 'image_removals': 0}
    (OUT / 'selection.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert not ARCHIVE.exists(), 'Never replace an existing recovery archive.'
    print('Archiving ten exact tags into one deduplicated Docker archive', flush=True)
    subprocess.run([DOCKER, 'image', 'save', '--output', str(ARCHIVE), *TAGS], check=True)
    print('Archive written; verifying all immutable indexes, configurations and referenced layers', flush=True)
    verified = set()
    with tarfile.open(ARCHIVE) as tar:
        def verify(desc):
            digest = desc['digest']
            assert digest.startswith('sha256:')
            if digest in verified:
                return
            member = tar.getmember('blobs/sha256/' + digest.split(':')[1])
            assert member.isfile() and member.size == desc['size']
            with tar.extractfile(member) as stream:
                assert 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() == digest
            verified.add(digest)
            if desc.get('mediaType', '').endswith(('index.v1+json', 'manifest.v1+json', 'manifest.v2+json', 'manifest.list.v2+json')):
                value = json.load(tar.extractfile(member))
                for child in value.get('manifests', []):
                    verify(child)
                if 'config' in value:
                    verify(value['config'])
                for child in value.get('layers', []):
                    verify(child)
        index = json.load(tar.extractfile('index.json'))
        manifest = json.load(tar.extractfile('manifest.json'))
        image_results = []
        for row in selected:
            verify(next(desc for desc in index['manifests'] if desc['digest'] == row['image_id']))
            entry = next(item for item in manifest if row['tags'][0] in item['RepoTags'])
            config = tar.extractfile(entry['Config']).read()
            config_hash = hashlib.sha256(config).hexdigest()
            assert entry['Config'] == 'blobs/sha256/' + config_hash and 'sha256:' + config_hash in verified
            assert all(tar.getmember(layer).isfile() and 'sha256:' + layer.split('/')[-1] in verified for layer in entry['Layers'])
            for n, receipt in enumerate(row['receipts']):
                shutil.copy2(receipt['path'], OUT / (row['tags'][0].split(':')[1] + '-receipt-' + str(n) + '.json'))
            image_results.append({'image_id': row['image_id'], 'tag': row['tags'][0], 'index_verified': True, 'config_verified': True, 'all_layers_verified': True})
            print('Verified ' + row['tags'][0], flush=True)
    fresh_selected, fresh_observed = inventory()
    assert fresh_selected == selected
    audit = {'status': 'ARCHIVED_VERIFIED_NO_REMOVALS', 'at_utc': datetime.now(timezone.utc).isoformat(),
             'archive': ref(ARCHIVE), 'images': image_results, 'verified_blobs': sorted(verified),
             'selection': ref(OUT / 'selection.json'), 'fresh_inventory': fresh_observed, 'image_removals': 0,
             'restore_command': [DOCKER, 'image', 'load', '--input', str(ARCHIVE)]}
    (OUT / 'archive-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': audit['status'], 'images': len(image_results), 'blobs': len(verified), 'archive': audit['archive']}), flush=True)


if __name__ == '__main__':
    main()
