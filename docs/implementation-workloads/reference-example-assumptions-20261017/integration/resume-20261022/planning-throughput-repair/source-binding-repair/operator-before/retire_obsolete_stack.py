"""Preserve and retire only this task's obsolete isolated 6d4 stack.

The immutable candidate image and its original PREPARED receipt remain retained.
No production data, image pruning, model edits or inference are performed.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'retire-6d4-stack'
OUT.mkdir(exist_ok=True)
ARCHIVE = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-recoverable-archives-20261021/retire-6d4-stack')
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
IMAGE = 'sha256:189ca2794ddf3f6b6ae320f830f2dd9de8096c9707725e71cf2dabaa4fcfb639'
PROD = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
ROLLBACK = 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478'
RECEIPT = ROOT / 'backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d/6d41919070e2/receipt.json'
NAMES = {'app': 'nis-e2e-app-6d41919070e2', 'db': 'nis-e2e-db-6d41919070e2',
         'network': 'nis-e2e-network-6d41919070e2', 'runtime': 'nis-e2e-runtime-6d41919070e2'}
STATE_PREFIX = 'native-single-choice'
CAPTURE = 'retirement-6d4-20261021'

# Reuse the audited backup/retirement path for an explicitly selected retained
# PREPARED receipt. Never infer a different target or replace its receipt.
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--receipt', type=Path)
parser.add_argument('--state-prefix', default=STATE_PREFIX)
parser.add_argument('--capture', default=CAPTURE)
args = parser.parse_args()
if args.receipt:
    RECEIPT = args.receipt.resolve(strict=True)
    assert RECEIPT.is_relative_to((ROOT / 'backend/test-output/release-gates').resolve())
    selected = json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert selected['status'] == 'PREPARED'
    nonce = selected['image_tag'].removeprefix('networkis:candidate-')
    assert re.fullmatch('[0-9a-f]{12}', nonce)
    IMAGE, NAMES = selected['image_id'], selected['containers']
    assert NAMES == {key: 'nis-e2e-' + key + '-' + nonce for key in ('app', 'db', 'network', 'runtime')}
    assert re.fullmatch('native-[a-z-]+', args.state_prefix)
    assert re.fullmatch('retirement-[a-z0-9-]+', args.capture)
    STATE_PREFIX, CAPTURE = args.state_prefix, args.capture
    OUT = Path(__file__).resolve().parent / ('retire-' + nonce + '-stack')
    OUT.mkdir(exist_ok=True)
    ARCHIVE = ARCHIVE.parent / ('retire-' + nonce + '-stack')
    assert ARCHIVE.resolve().is_relative_to(Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c').resolve())


def call(*args):
    return subprocess.check_output([DOCKER, *args], encoding='utf-8').strip()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}


def inspect(name):
    return json.loads(call('inspect', name))[0]


def containers():
    ids = call('ps', '-aq').splitlines()
    return json.loads(call('inspect', *ids)) if ids else []


def protected():
    p = inspect('NetworkIS')
    assert p['Image'] == PROD and p['State']['Health']['Status'] == 'healthy'
    assert inspect('networkis:candidate-c557b3914eac')['Id'] == ROLLBACK
    return {'production_id': p['Id'], 'production_image': p['Image'],
            'rollback_image': ROLLBACK, 'production_database_id': inspect('NetworkIS-db')['Id']}


def verify_image_archive(path):
    verified = set()
    with tarfile.open(path) as tar:
        def verify(desc):
            digest = desc['digest']
            if digest in verified:
                return
            name = 'blobs/' + digest.replace(':', '/')
            with tar.extractfile(name) as stream:
                raw = stream.read()
            assert len(raw) == desc['size']
            assert hashlib.sha256(raw).hexdigest() == digest.split(':')[1]
            verified.add(digest)
            if any(kind in desc.get('mediaType', '') for kind in ('manifest', 'index')):
                data = json.loads(raw)
                for child in data.get('manifests', []):
                    verify(child)
                if 'config' in data:
                    verify(data['config'])
                for child in data.get('layers', []):
                    verify(child)
        index = json.load(tar.extractfile('index.json'))
        verify(next(row for row in index['manifests'] if row['digest'] == IMAGE))
    return {'archive': ref(path), 'verified_blobs': sorted(verified), 'image_id': IMAGE}


def run():
    assert not (OUT / 'retirement.json').exists(), 'Never repeat completed retirement.'
    host = ROOT / 'docs/implementation-workloads/test-stack-retention-20261021'
    work = read(host / 'workload.json')
    assert work['status'] == 'COMPLETED'
    assert read(host / 'live-tooling-verification.json')['status'] == 'PASSED'
    for row in work['after']:
        saved = Path(row['path'])
        live = ROOT / saved.relative_to(host / 'after')
        assert ref(live)['sha256'] == row['sha256'] == ref(saved)['sha256']
    receipt = read(RECEIPT)
    original_receipt = ref(RECEIPT)
    assert receipt['status'] == 'PREPARED' and receipt['image_id'] == IMAGE
    assert receipt['containers'] == NAMES
    command = "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'native_original_document_driver.py|native_original_workflow_driver.py' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    assert not subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip(), 'Active native driver; do not retire.'
    baseline = protected()
    before = containers()
    app, db = inspect(NAMES['app']), inspect(NAMES['db'])
    assert app['Image'] == IMAGE
    assert db['Image'] == 'sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685'
    for c in (app, db):
        assert c['Config']['Labels'].get('networkis.test') == 'disposable'
        assert set(c['NetworkSettings']['Networks']) == {NAMES['network']}
    assert any(m.get('Name') == NAMES['runtime'] for m in app['Mounts'])
    assert db['Config']['Env'].count('POSTGRES_DB=nis_test_e2e') == 1
    assert not any(c['Id'] not in (app['Id'], db['Id']) and
                   (NAMES['network'] in c['NetworkSettings']['Networks'] or
                    any(m.get('Name') == NAMES['runtime'] for m in c['Mounts'])) for c in before)
    for case in ('vehicle', 'robot'):
        manifest = ROOT / ('docs/implementation-workloads/reference-example-assumptions-20261017/integration/' + STATE_PREFIX + '-' + case + '/' + CAPTURE + '/manifest.json')
        captured = read(manifest)
        assert captured['status'] == 'COMPLETE_GET_CAPTURE' and captured['image_id'] == IMAGE
    write('precheck.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'protected': baseline,
          'original_receipt': original_receipt, 'exact_container_ids': [app['Id'], db['Id']],
          'authorization': 'Resume both original checks and verified delivery; retire this obsolete isolated diagnostic stack as required by AGENTS/WIZARD_RELEASE_GATE before its replacement. Human also authorized old-image cleanup; this operation retains the image.'})
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    call('stop', app['Id'])
    backups = []
    for c in (app, db):
        path = OUT / (c['Name'].lstrip('/') + '.log')
        if not path.exists():
            with path.open('wb') as stream:
                subprocess.run([DOCKER, 'logs', c['Id']], stdout=stream, stderr=subprocess.STDOUT, check=True)
        backups.append(ref(path))
    dump = ARCHIVE / 'nis-test-e2e.dump'
    if not dump.exists():
        with dump.open('wb') as stream:
            subprocess.run([DOCKER, 'exec', db['Id'], 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc'], stdout=stream, check=True)
    with dump.open('rb') as source, (OUT / 'pg-restore-toc.txt').open('wb') as target:
        subprocess.run([DOCKER, 'exec', '-i', db['Id'], 'pg_restore', '--list'], stdin=source, stdout=target, check=True)
    assert 'TABLE DATA' in (OUT / 'pg-restore-toc.txt').read_text()
    backups.extend([ref(dump), ref(OUT / 'pg-restore-toc.txt')])
    volume = ARCHIVE / 'runtime.tar'
    code = "import tarfile; t=tarfile.open('/backup/runtime.tar','w'); t.add('/source',arcname='data'); t.close()"
    if not volume.exists():
        subprocess.run([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--entrypoint', 'python',
                        '--mount', 'type=volume,source=' + NAMES['runtime'] + ',target=/source,readonly',
                        '--mount', 'type=bind,source=' + str(ARCHIVE) + ',target=/backup', IMAGE, '-c', code], check=True)
    with tarfile.open(volume) as tar:
        members = []
        for member in tar:
            if member.isfile():
                with tar.extractfile(member) as stream:
                    members.append({'name': member.name, 'bytes': member.size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()})
    backups.append({**ref(volume), 'members': members})
    image_path = ARCHIVE / (NAMES['app'].replace('nis-e2e-app-', 'candidate-') + '.tar')
    if not image_path.exists():
        subprocess.run([DOCKER, 'image', 'save', '--output', str(image_path), IMAGE], check=True)
    image_audit = verify_image_archive(image_path)
    write('image-archive-audit.json', image_audit)
    write('backup-audit.json', {'backups': backups, 'image_audit': ref(OUT / 'image-archive-audit.json'), 'receipt': original_receipt})
    print(json.dumps({'status': 'FULL_STACK_BACKUP_VERIFIED', 'image_blobs': len(image_audit['verified_blobs']), 'dump_bytes': dump.stat().st_size}), flush=True)
    assert original_receipt == ref(RECEIPT)
    assert protected() == baseline
    call('stop', db['Id'])
    operations = []
    for c in (app, db):
        fresh = inspect(c['Id'])
        assert fresh['Image'] == c['Image'] and fresh['State']['Status'] == 'exited'
        operations.append({'command': ['container', 'rm', c['Id']], 'result': call('container', 'rm', c['Id'])})
    for kind, name in (('network', NAMES['network']), ('volume', NAMES['runtime'])):
        remaining = containers()
        assert all(name not in c['NetworkSettings']['Networks'] and all(m.get('Name') != name for m in c['Mounts']) for c in remaining)
        resource = json.loads(call(kind, 'inspect', name))[0]
        assert resource.get('Labels', {}).get('networkis.test') == 'disposable'
        operations.append({'command': [kind, 'rm', name], 'result': call(kind, 'rm', name)})
    assert protected() == baseline and ref(RECEIPT) == original_receipt
    assert inspect('networkis:candidate-' + NAMES['app'].removeprefix('nis-e2e-app-'))['Id'] == IMAGE
    assert not any(c['Id'] in (app['Id'], db['Id']) for c in containers())
    write('retirement.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'EXACT_OBSOLETE_STACK_RETIRED',
          'operations': operations, 'backups': ref(OUT / 'backup-audit.json'), 'image_preserved': IMAGE,
          'original_receipt_preserved': original_receipt, 'protected_unchanged': baseline,
          'no_image_removed': True, 'full_release_pass': False})
    print(json.dumps({'status': 'EXACT_OBSOLETE_STACK_RETIRED', 'image_preserved': IMAGE}), flush=True)


spec = importlib.util.spec_from_file_location('nis_retire_delivery', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
with owner.gate_lock(ROOT):
    run()
