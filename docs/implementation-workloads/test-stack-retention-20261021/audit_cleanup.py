"""Task-scoped Docker audit. Mutations require the reviewed exact plan below."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ARCHIVES = Path('F:/CodexOrdner/visualizations/2026/10/21/01a15ce5-2b16-7d01-844d-6232dd03f254/nis-cleanup-archives')
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']


def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()


def write(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return path


def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.resolve()), 'sha256': digest}


def containers():
    ids = call('ps', '-aq', '--no-trunc').split()
    rows = json.loads(call('inspect', *ids)) if ids else []
    return [{
        'id': row['Id'], 'name': row['Name'].lstrip('/'), 'image': row['Image'],
        'state': row['State']['Status'], 'health': row['State'].get('Health', {}).get('Status'),
        'created': row['Created'], 'labels': row['Config'].get('Labels') or {},
        'mounts': row.get('Mounts', []),
        'networks': list(row['NetworkSettings'].get('Networks', {})),
        'ports': row['HostConfig'].get('PortBindings'),
        'tmpfs': row['HostConfig'].get('Tmpfs'),
    } for row in rows]


def receipts():
    rows, errors = [], []
    for parent in (ROOT / 'backend/test-output', ROOT / 'work', ROOT / 'reports'):
        for path in parent.rglob('receipt.json'):
            try:
                value = json.loads(path.read_text(encoding='utf-8-sig'))
                if not isinstance(value, dict):
                    raise ValueError('not an object')
                rows.append({**ref(path), **{key: value.get(key) for key in (
                    'status', 'image_id', 'image_tag', 'initial_source_sha256',
                    'initial_commit_id', 'containers', 'gate_pid', 'development_only')}})
            except (OSError, ValueError) as error:
                errors.append({'path': str(path), 'error': str(error)})
    return rows, errors


def inventory(name='inventory-before.json'):
    cs = containers()
    ids = sorted(set(call('image', 'ls', 'networkis', '-q', '--no-trunc').split()))
    images = json.loads(call('image', 'inspect', *ids))
    rs, errors = receipts()
    production = next(row for row in cs if row['name'] == 'NetworkIS')
    rollback = 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478'
    assert rollback in ids, 'Recorded rollback is missing'
    rows = []
    for image in images:
        related = [r for r in rs if r['image_id'] == image['Id']]
        rows.append({'id': image['Id'], 'tags': image.get('RepoTags', []),
                     'created': image['Created'], 'size': image['Size'],
                     'labels': image['Config'].get('Labels') or {},
                     'statuses': sorted(set(r['status'] or 'UNKNOWN' for r in related)),
                     'receipts': related,
                     'containers': [c['name'] for c in cs if c['image'] == image['Id']]})
    data = {'captured_epoch': time.time(), 'engine': call('info', '--format', '{{.ID}}'),
            'production': production, 'rollback': rollback, 'containers': cs,
            'images': rows, 'receipt_errors': errors}
    write(name, data)
    print(json.dumps({'images': len(rows), 'test_containers': sum(c['name'].startswith('nis-e2e-') for c in cs),
                      'production': production['image'], 'rollback': rollback,
                      'image_status_counts': {str(status): sum(r['statuses'] == status for r in rows)
                                              for status in (['PREPARED'], ['FAIL'], ['PASS'], [], ['FAIL', 'PREPARED'])},
                      'receipt_errors': len(errors),
                      'prepared': [{'tags': r['tags'], 'containers': r['containers']} for r in rows if r['statuses'] == ['PREPARED']]}), flush=True)
    return data


def object_rows(kind):
    ids = call(kind, 'ls', '-q', '--filter', 'label=networkis.test=disposable').split()
    return json.loads(call(kind, 'inspect', *ids)) if ids else []


def make_plan():
    data = inventory('inventory-plan.json')
    keep = 'networkis:candidate-6d6fe881f4bd'
    targets = [r for r in data['images'] if r['statuses'] == ['PREPARED'] and keep not in r['tags']]
    assert len(targets) == 26
    assert all(len(r['tags']) == 1 and r['tags'][0].startswith('networkis:candidate-') for r in targets)
    cs = [c for c in data['containers'] if c['name'].startswith('nis-e2e-') and '6d6fe881f4bd' not in c['name']]
    assert len(cs) == 28
    assert all(c['state'] == 'exited' and c['labels'].get('networkis.test') == 'disposable' for c in cs)
    tokens = {r['tags'][0].split('candidate-')[1] for r in targets}
    tokens.update(c['name'].split('-')[3] for c in cs)
    resources = {}
    for kind, prefix in [('volume', 'nis-e2e-runtime-'), ('network', 'nis-e2e-network-')]:
        resources[kind] = [r for r in object_rows(kind) if r['Name'] in {prefix + t for t in tokens}]
        names = {r['Name'] for r in resources[kind]}
        for c in data['containers']:
            if c['id'] not in {c['id'] for c in cs}:
                assert not names.intersection(c['networks'] if kind == 'network' else
                    [m.get('Name') for m in c['mounts']]), 'External reference protects resource'
    plan = {'authorization': 'Explicit user request 2026-10-21: safely clean old test containers and unused candidates; preserve production and needed rollback images.',
            'disposition': 'RETIRED_UNUSED_PREPARED_BY_EXPLICIT_REQUEST; no FAIL/PASS or delivered-equivalence claim',
            'production': data['production'], 'rollback': data['rollback'], 'keep_candidate': keep,
            'images': targets, 'containers': cs, 'resources': resources,
            'protected_images': [r for r in data['images'] if r not in targets],
            'inventory': ref(OUT / 'inventory-plan.json')}
    write('cleanup-plan.json', plan)
    print(json.dumps({'planned_images': len(targets), 'containers': len(cs),
                      'volumes': len(resources['volume']), 'networks': len(resources['network'])}), flush=True)


def verify_image_archive(path, targets):
    verified = set()
    with tarfile.open(path) as tar:
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
        for target in targets:
            verify(next(d for d in index['manifests'] if d['digest'] == target['id']))
            entry = next(e for e in manifest if target['tags'][0] in e['RepoTags'])
            content = tar.extractfile(entry['Config']).read()
            digest = hashlib.sha256(content).hexdigest()
            assert entry['Config'] == 'blobs/sha256/' + digest
            assert 'sha256:' + digest in verified
            assert all(tar.getmember(layer).isfile() and 'sha256:' + layer.split('/')[-1] in verified for layer in entry['Layers'])
    return {'verified_blobs': sorted(verified), 'image_count': len(targets), 'archive': ref(path),
            'index_config_and_all_layers_verified': True}


def archive():
    plan = json.loads((OUT / 'cleanup-plan.json').read_text())
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    image_archive = ARCHIVES / 'retired-prepared-images.tar'
    if not image_archive.exists():
        subprocess.run([DOCKER, 'image', 'save', '--output', str(image_archive),
                        *[r['tags'][0] for r in plan['images']]], check=True)
    audit = verify_image_archive(image_archive, plan['images'])
    write('image-archive-audit.json', audit)
    print(json.dumps({'image_archive_verified': len(plan['images']), 'bytes': image_archive.stat().st_size}), flush=True)
    for image in plan['images']:
        for index, receipt in enumerate(image['receipts']):
            path = Path(receipt['path'])
            assert ref(path)['sha256'] == receipt['sha256']
            write('retired-receipts/' + image['tags'][0].split(':')[1] + '-' + str(index) + '.json',
                  json.loads(path.read_text(encoding='utf-8-sig')))
    backups = []
    for c in plan['containers']:
        assert json.loads(call('inspect', c['id']))[0]['State']['Status'] == 'exited'
        log = OUT / 'logs' / (c['name'] + '.log')
        log.parent.mkdir(exist_ok=True)
        with log.open('wb') as stream:
            subprocess.run([DOCKER, 'logs', c['id']], stdout=stream, stderr=subprocess.STDOUT, check=True)
        backups.append(ref(log))
    for row in plan['resources']['volume']:
        path = ARCHIVES / (row['Name'] + '.tar')
        if not path.exists():
            code = "import tarfile; t=tarfile.open('/backup/" + path.name + "','w'); t.add('/source',arcname='data'); t.close()"
            subprocess.run([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--entrypoint', 'python',
                            '--mount', 'type=volume,source=' + row['Name'] + ',target=/source,readonly',
                            '--mount', 'type=bind,source=' + str(ARCHIVES) + ',target=/backup',
                            plan['production']['image'], '-c', code], check=True)
        files = []
        with tarfile.open(path) as tar:
            for member in tar:
                if member.isfile():
                    with tar.extractfile(member) as stream:
                        files.append({'name': member.name, 'size': member.size,
                                      'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()})
        backups.append({**ref(path), 'volume': row['Name'], 'files': files})
        print(json.dumps({'volume_archived': row['Name'], 'files': len(files)}), flush=True)
    write('stack-backup-audit.json', {'backups': backups,
          'stopped_tmpfs_databases': 'Already stopped tmpfs contents are not recoverable from Docker. Existing historical database dumps/project exports are retained unchanged; no old database is restarted.',
          'plan': ref(OUT / 'cleanup-plan.json'), 'image_audit': ref(OUT / 'image-archive-audit.json')})


def remove():
    spec = importlib.util.spec_from_file_location('cleanup_gate_owner', ROOT / 'scripts/release-and-deploy.py')
    delivery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(delivery)
    with delivery.gate_lock(ROOT):
        return remove_locked()


def remove_locked():
    plan = json.loads((OUT / 'cleanup-plan.json').read_text())
    audit = json.loads((OUT / 'image-archive-audit.json').read_text())
    backups = json.loads((OUT / 'stack-backup-audit.json').read_text())
    assert backups['plan'] == ref(OUT / 'cleanup-plan.json')
    assert backups['image_audit'] == ref(OUT / 'image-archive-audit.json')
    assert audit['archive'] == ref(Path(audit['archive']['path']))
    assert all(ref(Path(r['path'])) == {k: r[k] for k in ('path', 'sha256')} for r in backups['backups'])
    fresh = inventory('inventory-pre-removal.json')
    assert fresh['production']['id'] == plan['production']['id']
    assert fresh['production']['image'] == plan['production']['image']
    assert fresh['production']['health'] == 'healthy'
    assert fresh['rollback'] == plan['rollback']
    target_ids = {r['id'] for r in plan['images']}
    cs = {c['id']: c for c in fresh['containers']}
    removable = {c['id'] for c in plan['containers']}
    for c in plan['containers']:
        assert c['id'] in cs and cs[c['id']]['name'] == c['name']
        assert cs[c['id']]['state'] == 'exited' and cs[c['id']]['image'] == c['image']
        assert cs[c['id']]['labels'].get('networkis.test') == 'disposable'
    assert all(c['id'] in removable for c in fresh['containers'] if c['image'] in target_ids)
    current = {r['id']: r for r in fresh['images']}
    for image in plan['images']:
        actual = current[image['id']]
        assert actual['tags'] == image['tags'] and actual['statuses'] == ['PREPARED']
        assert actual['receipts'] == image['receipts'], 'Receipt changed since review'
        assert image['id'] not in {plan['production']['image'], plan['rollback']}
    operations = []
    write('removal-result.json', {'status': 'REMOVING', 'operations': operations})
    def execute(*args):
        result = call(*args)
        operations.append({'epoch': time.time(), 'command': [DOCKER, *args], 'result': result})
        write('removal-result.json', {'status': 'REMOVING', 'operations': operations})
    for c in plan['containers']:
        actual = json.loads(call('inspect', c['id']))[0]
        assert actual['State']['Status'] == 'exited' and actual['Image'] == c['image']
        execute('container', 'rm', c['id'])
    for kind in ('network', 'volume'):
        for row in plan['resources'][kind]:
            remaining = containers()
            assert all(row['Name'] not in (c['networks'] if kind == 'network' else [m.get('Name') for m in c['mounts']]) for c in remaining)
            observed = json.loads(call(kind, 'inspect', row['Name']))[0]
            assert observed.get('Labels', {}).get('networkis.test') == 'disposable'
            if kind == 'network':
                assert observed['Id'] == row['Id']
            else:
                assert observed['CreatedAt'] == row['CreatedAt']
            execute(kind, 'rm', row['Name'])
    for image in plan['images']:
        assert not any(c['image'] == image['id'] for c in containers())
        assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == plan['production']['image']
        actual = json.loads(call('image', 'inspect', image['tags'][0]))[0]
        assert actual['Id'] == image['id'] and actual['RepoTags'] == image['tags']
        execute('image', 'rm', '--no-prune', image['tags'][0])
    after = inventory('inventory-after.json')
    assert after['production']['id'] == plan['production']['id']
    assert after['production']['image'] == plan['production']['image']
    assert after['production']['health'] == 'healthy'
    assert all(r['id'] in {a['id'] for a in after['images']} for r in plan['protected_images'])
    write('removal-result.json', {'status': 'COMPLETED', 'operations': operations,
                                'after': ref(OUT / 'inventory-after.json'),
                                'production_and_all_protected_images_preserved': True})
    print(json.dumps({'status': 'COMPLETED', 'images_removed': len(plan['images']),
                      'containers_removed': len(plan['containers']), 'operations': len(operations)}), flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'inventory'
    {'inventory': inventory, 'plan': make_plan, 'archive': archive, 'remove': remove}[mode]()
