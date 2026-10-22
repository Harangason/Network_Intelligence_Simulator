"""Archive and retire exact unused disposable NIS resources, preserving images."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path.cwd()
REPAIR = Path(__file__).resolve().parent
OUT = REPAIR / 'retire-orphan-resources'
OUT.mkdir(exist_ok=True)
ARCHIVE = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-recoverable-archives-20261021/retire-orphan-resources')
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
IMAGE = 'sha256:db0b949a1bb0926e8c6c95bd0a6a7484f6b1f65c8a009d9352c7f2184b70ce1f'


def call(*args):
    return subprocess.check_output([D, *args], encoding='utf-8').strip()


def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def containers():
    ids = call('ps', '-aq').split()
    return json.loads(call('inspect', *ids)) if ids else []


def protected():
    names = ('NetworkIS', 'NetworkIS-db', 'networkis:candidate-c557b3914eac')
    rows = json.loads(call('inspect', *names))
    assert rows[0]['Image'] == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
    assert rows[0]['State']['Health']['Status'] == 'healthy'
    assert rows[2]['Id'] == 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478'
    return [{'id': row['Id'], 'image': row.get('Image'), 'mounts': row.get('Mounts')} for row in rows]


spec = importlib.util.spec_from_file_location('nis_orphan_delivery', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
with owner.gate_lock(ROOT):
    assert not (OUT / 'retirement.json').exists()
    baseline = protected()
    cs = containers()
    assert not any(c['Name'].lstrip('/').startswith('nis-e2e-') for c in cs)
    resources = {}
    for kind, prefix in (('volume', 'nis-e2e-runtime-'), ('network', 'nis-e2e-network-')):
        names = [name for name in call(kind, 'ls', '--format', '{{.Name}}').split() if name.startswith(prefix)]
        rows = json.loads(call(kind, 'inspect', *names)) if names else []
        assert all(row.get('Labels', {}).get('networkis.test') == 'disposable' for row in rows)
        for row in rows:
            assert all(row['Name'] not in c['NetworkSettings']['Networks'] and
                       all(m.get('Name') != row['Name'] for m in c['Mounts']) for c in cs)
            if kind == 'network':
                assert not row['Containers']
        resources[kind] = rows
    assert resources['network'] or resources['volume']
    receipts = []
    target_names = {row['Name'] for rows in resources.values() for row in rows}
    for path in owner.receipt_paths():
        try:
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        if isinstance(receipt, dict) and target_names.intersection(receipt.get('containers', {}).values()):
            assert receipt.get('status') != 'RUNNING', 'Active/unknown operation must be reconciled first.'
            receipts.append({'receipt': ref(path), 'status': receipt.get('status'), 'resources': receipt.get('containers'), 'image_preserved': receipt.get('image_id')})
    resume = sys.argv[1:] == ['--resume-verified-backup']
    if resume:
        prior = json.loads((OUT / 'inventory.json').read_text())
        assert prior['resources'] == resources and prior['receipts_preserved'] == receipts
        assert prior['protected'] == baseline
        audit = json.loads((OUT / 'backup-audit.json').read_text())
        assert audit['inventory'] == ref(OUT / 'inventory.json')
    else:
        assert not (OUT / 'inventory.json').exists(), 'Inspect an existing attempt, never overwrite it.'
        write('inventory.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'resources': resources,
              'receipts_preserved': receipts, 'protected': baseline,
              'scope': 'Recoverable retirement of only unused disposable NIS test resources required by the canonical retained-stack gate. No image/container/production/unrelated resource removal.'})
    previous = REPAIR / 'prepare-attempt-57322'
    previous.mkdir(exist_ok=resume)
    for name in ('candidate-prepare-freeze.json', 'candidate-prepare-result.json', 'candidate-prepare.log'):
        if resume:
            assert (REPAIR / name).read_bytes() == (previous / name).read_bytes()
        else:
            shutil.copy2(REPAIR / name, previous / name)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    backups = audit['backups'] if resume else []
    if resume:
        assert {row['volume'] for row in backups} == {row['Name'] for row in resources['volume']}
        for backup in backups:
            assert ref(Path(backup['path'])) == {key: backup[key] for key in ('path', 'sha256', 'bytes')}
    for row in ([] if resume else resources['volume']):
        archive = ARCHIVE / (row['Name'] + '.tar')
        assert not archive.exists()
        code = "import tarfile; t=tarfile.open('/backup/" + archive.name + "','w'); t.add('/source',arcname='data'); t.close()"
        subprocess.run([D, 'run', '--rm', '--network', 'none', '--read-only', '--entrypoint', 'python',
                        '--mount', 'type=volume,source=' + row['Name'] + ',target=/source,readonly',
                        '--mount', 'type=bind,source=' + str(ARCHIVE) + ',target=/backup', IMAGE, '-c', code], check=True)
        members = []
        with tarfile.open(archive) as tar:
            for member in tar:
                if member.isfile():
                    with tar.extractfile(member) as stream:
                        members.append({'name': member.name, 'bytes': member.size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()})
        backups.append({**ref(archive), 'volume': row['Name'], 'members': members})
    if not resume:
        write('backup-audit.json', {'inventory': ref(OUT / 'inventory.json'), 'backups': backups})
    assert protected() == baseline
    operations = []
    for kind in ('network', 'volume'):
        for row in resources[kind]:
            cs = containers()
            assert all(row['Name'] not in c['NetworkSettings']['Networks'] and
                       all(m.get('Name') != row['Name'] for m in c['Mounts']) for c in cs)
            observed = json.loads(call(kind, 'inspect', row['Name']))[0]
            assert observed.get('Labels', {}).get('networkis.test') == 'disposable'
            if kind == 'network':
                assert observed['Id'] == row['Id'] and observed['Created'] == row['Created']
            else:
                assert observed['CreatedAt'] == row['CreatedAt']
            if kind == 'volume':
                backup = next(item for item in backups if item['volume'] == row['Name'])
                assert ref(Path(backup['path'])) == {key: backup[key] for key in ('path', 'sha256', 'bytes')}
            operations.append({'command': [kind, 'rm', row['Name']], 'result': call(kind, 'rm', row['Name'])})
            write('operations.json', operations)
    assert protected() == baseline
    assert call('image', 'inspect', IMAGE, '--format', '{{.Id}}') == IMAGE
    write('retirement.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'EXACT_ORPHAN_TEST_RESOURCES_ARCHIVED_AND_RETIRED',
          'networks': len(resources['network']), 'volumes': len(resources['volume']), 'operations': operations,
          'backups': ref(OUT / 'backup-audit.json'), 'protected_unchanged': baseline, 'no_images_removed': True})
    print(json.dumps({'status': 'EXACT_ORPHAN_TEST_RESOURCES_ARCHIVED_AND_RETIRED', 'volumes': len(resources['volume']), 'networks': len(resources['network'])}))
