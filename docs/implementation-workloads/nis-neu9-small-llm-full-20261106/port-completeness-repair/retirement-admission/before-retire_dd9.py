"""Recoverably retire one explicitly bound obsolete diagnostic stack; preserve images."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'retire-dd9'
ARCHIVE = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-neu9-small-llm-20261106/retire-dd9')
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
RECEIPT = ROOT / 'backend/test-output/release-gates/dd9f86a47cc7/receipt.json'
IMAGE = 'sha256:9bd311f3637d475161079b7e9cbfaea40d0612856c10e72b720e659f6ff5cd34'
PROD = 'sha256:c7edda158398ce6c13b5563f56df70575aa61345539fbc23a5aeb847164fca33'
NAMES = {kind: 'nis-e2e-' + kind + '-dd9f86a47cc7' for kind in ('app', 'db', 'network', 'runtime')}

def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()

def inspect(name):
    return json.loads(call('inspect', name))[0]

def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def inventory():
    ids = call('ps', '-aq').split()
    return json.loads(call('inspect', *ids)) if ids else []

def protected():
    app, db = inspect('NetworkIS'), inspect('NetworkIS-db')
    assert app['Image'] == PROD and app['State']['Running'] and app['State']['Health']['Status'] == 'healthy'
    assert db['State']['Running']
    return {'app_id': app['Id'], 'image': app['Image'], 'db_id': db['Id']}

def verify_image(path):
    verified = set()
    with tarfile.open(path) as archive:
        def visit(desc):
            digest = desc['digest']
            if digest in verified:
                return
            member = archive.getmember('blobs/' + digest.replace(':', '/'))
            assert member.size == desc['size']
            with archive.extractfile(member) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest.split(':')[1]
            verified.add(digest)
            if any(kind in desc.get('mediaType', '') for kind in ('manifest', 'index')):
                data = json.load(archive.extractfile(member))
                for child in data.get('manifests', []):
                    visit(child)
                if 'config' in data:
                    visit(data['config'])
                for child in data.get('layers', []):
                    visit(child)
        index = json.load(archive.extractfile('index.json'))
        for desc in index['manifests']:
            visit(desc)
    assert IMAGE in verified, 'Exact immutable image is not reachable in archive'
    return {'archive': ref(path), 'image_id': IMAGE, 'verified_blobs': sorted(verified)}

def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'retirement.json').exists(), 'Never repeat a terminal retirement'
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    original = ref(RECEIPT)
    assert receipt['status'] == 'PREPARED' and receipt['image_id'] == IMAGE and receipt['containers'] == NAMES
    baseline = protected()
    app, db = inspect(NAMES['app']), inspect(NAMES['db'])
    assert app['Image'] == IMAGE
    command = "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'native_original_document_driver.py|native_original_workflow_driver.py' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    assert not subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True).strip(), 'A native driver is active; do not retire'
    if PLAN:
        state = json.loads(Path(PLAN['state']).read_text(encoding='utf-8'))
        assert state['image_id'] == IMAGE and state['containers'] == NAMES
        if PLAN.get('reason') == 'VERIFIED_SERVER_CANCELED_CLIENT_EXIT_UNKNOWN':
            # A lost stream can leave the original client state stale. Admit only
            # the independently bound terminal server generation, never relabel
            # it a human cancellation, native failure, or release FAIL.
            from urllib.request import Request, build_opener, ProxyHandler
            evidence = PLAN['terminal_evidence']
            proof_path = Path(evidence['path']).resolve(strict=True)
            assert proof_path.is_relative_to(Path(__file__).resolve().parent)
            assert ref(proof_path)['sha256'] == evidence['sha256']
            terminal = json.loads(proof_path.read_text(encoding='utf-8'))
            assert terminal['server_generation']['status'] == 'CANCELED'
            assert terminal['server_draft_status'] == 'REFERENCE_CANCELED'
            assert terminal['actual_native_driver_processes'] == []
            assert terminal['client_exit_code'] is None and terminal['normal_client_result_available'] is False
            assert terminal['canonical_model_empty'] is True and terminal['simulation_jobs'] == 0
            assert state['base_url'] == receipt['base_url']
            observed = {}
            for key, endpoint in [('draft', '/api/engineering/agent/project-draft'),
                                  ('export', '/api/engineering/projects/export'),
                                  ('jobs', '/api/simulations')]:
                query = Request(receipt['base_url'] + endpoint, headers={'X-Project-ID': state['project_id']})
                with build_opener(ProxyHandler({})).open(query, timeout=20) as response:
                    observed[key] = json.load(response)
            current = observed['draft']['data']
            assert current['reference_generation'] == terminal['server_generation']
            assert current['reference_generation']['source_sha256'] == state['original_sha256']
            assert current['status'] == 'REFERENCE_CANCELED' and not current.get('reference_design')
            assert not any(observed['export']['source_data'].values()) and observed['jobs']['jobs'] == []
            save('fresh-server-terminal-precheck.json', observed)
        elif state['status'] == 'OPERATOR_VERIFIED_REFERENCE_CANCELED':
            # A human-requested cancellation is not a failed-model receipt.
            # Bind its saved evidence and re-read the normal isolated project API.
            from urllib.request import Request, build_opener, ProxyHandler
            evidence = PLAN['cancellation_evidence']
            proof_path = Path(evidence['path']).resolve(strict=True)
            assert proof_path.is_relative_to(Path(__file__).resolve().parent)
            assert ref(proof_path)['sha256'] == evidence['sha256']
            canceled = json.loads(proof_path.read_text(encoding='utf-8'))
            assert canceled['classification'] == 'EXPLICIT_USER_CANCELLATION_NOT_NATIVE_FAILURE'
            assert canceled['server_generation']['status'] == 'CANCELED'
            assert state['base_url'] == receipt['base_url']
            query = Request(receipt['base_url'] + '/api/engineering/agent/project-draft',
                            headers={'X-Project-ID': state['project_id']})
            with build_opener(ProxyHandler({})).open(query, timeout=20) as response:
                current = json.load(response)['data']
            assert current['reference_generation'] == canceled['server_generation']
            assert current['status'] == 'REFERENCE_CANCELED' and not current.get('reference_design')
            assert current['reference_generation']['source_sha256'] == state['original_sha256']
            save('fresh-cancellation-precheck.json', current)
        elif state['status'] == 'READY_FOR_NATIVE_INTAKE':
            # An unused preparation with the disabled provider is not a native failure.
            assert PLAN.get('reason') == 'UNUSED_DISABLED_PROVIDER_PREPARATION'
            assert state['base_url'] == receipt['base_url']
            state_dir = Path(PLAN['state']).parent
            assert not any((state_dir / stage).exists() for stage in ('intake', 'plan-reference'))
            environment = dict(row.split('=', 1) for row in app['Config']['Env'] if '=' in row)
            assert environment['LOCAL_AI_BASE_URL'] == 'http://127.0.0.1:1/v1'
            from urllib.request import Request, build_opener, ProxyHandler
            observed = {}
            for key, endpoint in [('draft', '/api/engineering/agent/project-draft'),
                                  ('export', '/api/engineering/projects/export'),
                                  ('jobs', '/api/simulations')]:
                query = Request(receipt['base_url'] + endpoint, headers={'X-Project-ID': state['project_id']})
                with build_opener(ProxyHandler({})).open(query, timeout=20) as response:
                    observed[key] = json.load(response)
            assert not observed['draft'].get('data')
            assert not any(observed['export']['source_data'].values())
            assert observed['jobs']['jobs'] == []
            save('fresh-unused-precheck.json', observed)
        else:
            assert state['status'].endswith('_FAILED')
    assert db['Image'] == 'sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685'
    for item in (app, db):
        assert item['Config']['Labels'].get('networkis.test') == 'disposable'
        assert set(item['NetworkSettings']['Networks']) == {NAMES['network']}
    assert any(m.get('Name') == NAMES['runtime'] and m['Destination'] == '/app/var/data' for m in app['Mounts'])
    assert not any(c['Id'] not in {app['Id'], db['Id']} and (NAMES['network'] in c['NetworkSettings']['Networks'] or
                   any(m.get('Name') == NAMES['runtime'] for m in c['Mounts'])) for c in inventory())
    images_before = sorted(set(call('image', 'ls', '-q', '--no-trunc').split()))
    precheck = {'at': datetime.now(timezone.utc).isoformat(), 'protected': baseline,
         'container_ids': [app['Id'], db['Id']], 'receipt': original, 'images': images_before,
         'authorization': 'Current explicit full neu9 request and canonical single retained diagnostic stack rule. Exact recoverable retirement; no image deletion.'}
    if (OUT / 'precheck.json').exists():
        previous = json.loads((OUT / 'precheck.json').read_text(encoding='utf-8'))
        assert all(previous[key] == precheck[key] for key in ('protected', 'container_ids', 'receipt', 'images'))
    else:
        save('precheck.json', precheck)
    assert ARCHIVE.resolve().is_relative_to(Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c').resolve())
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    assert {path.name for path in ARCHIVE.iterdir()} <= {'database.dump', 'runtime.tar', 'image.tar'}
    if app['State']['Running'] and not ARCHIVE_ONLY:
        call('stop', app['Id'])
    runtime_logs=OUT/'application-runtime-logs'
    runtime_logs.mkdir(exist_ok=True)
    call('cp',app['Id']+':/app/var/runtime/logs/.',str(runtime_logs))
    for item in (app, db):
        log = OUT / (item['Name'].lstrip('/') + '.log')
        if not log.exists():
            with log.open('wb') as stream:
                subprocess.run([DOCKER, 'logs', item['Id']], stdout=stream, stderr=subprocess.STDOUT, check=True)
    if not db['State']['Running']:
        assert not ARCHIVE_ONLY, 'Read-only archive does not start a database'
        call('start', db['Id'])
    try:
        for attempt in range(60):
            result = subprocess.run([DOCKER, 'exec', db['Id'], 'pg_isready', '-U', 'nis_test', '-d', 'nis_test_e2e'], capture_output=True)
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Exact isolated database did not become ready')
        dump = ARCHIVE / 'database.dump'
        query = "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';"
        table_count = int(call('exec', db['Id'], 'psql', '-U', 'nis_test', '-d', 'nis_test_e2e', '-At', '-c', query))
        if not dump.exists():
            with dump.open('wb') as stream:
                subprocess.run([DOCKER, 'exec', db['Id'], 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc'], stdout=stream, check=True)
        with dump.open('rb') as source, (OUT / 'pg-restore-toc.txt').open('wb') as target:
            subprocess.run([DOCKER, 'exec', '-i', db['Id'], 'pg_restore', '--list'], stdin=source, stdout=target, check=True)
        toc = (OUT / 'pg-restore-toc.txt').read_text()
        assert 'Format: CUSTOM' in toc and ('TABLE DATA' in toc or table_count == 0)
        save('database-backup-verification.json', {'table_count': table_count, 'dump': ref(dump),
             'toc': ref(OUT / 'pg-restore-toc.txt'), 'scope': 'Native pg_restore list Exit0; no table data entries are required only when fresh isolated database catalog proves zero user tables.'})
    except Exception as error:
        save('backup-failure.json', {'error':str(error),'database_left_running':True,
             'reason':'Preserve original tmpfs data until a complete dump and archive are verified.'})
        raise
    runtime = ARCHIVE / 'runtime.tar'
    code = "import tarfile; t=tarfile.open('/backup/runtime.tar','w'); t.add('/source',arcname='data'); t.close()"
    subprocess.run([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--entrypoint', 'python',
                    '--mount', 'type=volume,source=' + NAMES['runtime'] + ',target=/source,readonly',
                    '--mount', 'type=bind,source=' + str(ARCHIVE) + ',target=/backup', IMAGE, '-c', code], check=True)
    members = []
    with tarfile.open(runtime) as archive:
        for item in archive:
            if item.isfile():
                with archive.extractfile(item) as stream:
                    members.append({'path': item.name, 'bytes': item.size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()})
    image_archive = ARCHIVE / 'image.tar'
    subprocess.run([DOCKER, 'image', 'save', '--output', str(image_archive), IMAGE], check=True)
    image_proof = verify_image(image_archive)
    pg_volumes = [m['Name'] for m in db['Mounts'] if m['Type'] == 'volume']
    backup = {'database': ref(dump), 'table_count': table_count, 'toc': ref(OUT / 'pg-restore-toc.txt'), 'runtime': ref(runtime),
              'runtime_files': members, 'image': image_proof, 'raw_pg_volumes_preserved': pg_volumes, 'original_receipt': original,
              'application_runtime_logs':[ref(path) for path in sorted(runtime_logs.rglob('*')) if path.is_file()]}
    save('backup-audit.json', backup)
    print(json.dumps({'status': 'FULL_BACKUP_VERIFIED', 'image_blobs': len(image_proof['verified_blobs']), 'runtime_files': len(members)}), flush=True)
    assert protected() == baseline and ref(RECEIPT) == original
    if ARCHIVE_ONLY:
        fresh_app, fresh_db = inspect(app['Id']), inspect(db['Id'])
        assert fresh_app['State']['Status']==app['State']['Status'] and fresh_db['State']['Status']==db['State']['Status']
        assert sorted(set(call('image','ls','-q','--no-trunc').split()))==images_before
        save('archive-only.json',{'at':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_ARCHIVE_VERIFIED_RESOURCES_UNCHANGED',
             'backup':ref(OUT/'backup-audit.json'),'protected_unchanged':baseline,'container_ids':[app['Id'],db['Id']],
             'no_stack_stop_remove_or_image_delete':True,'receipt_preserved':original})
        print(json.dumps({'status':'READ_ONLY_ARCHIVE_VERIFIED_RESOURCES_UNCHANGED','no_stack_stop_remove_or_image_delete':True}),flush=True)
        return
    call('stop', db['Id'])
    for item in (app, db):
        fresh = inspect(item['Id'])
        assert fresh['Image'] == item['Image'] and fresh['State']['Status'] == 'exited'
        call('container', 'rm', item['Id'])
    for kind, name in [('network', NAMES['network']), ('volume', NAMES['runtime'])]:
        assert not any(name in c['NetworkSettings']['Networks'] or any(m.get('Name') == name for m in c['Mounts']) for c in inventory())
        assert json.loads(call(kind, 'inspect', name))[0]['Labels']['networkis.test'] == 'disposable'
        call(kind, 'rm', name)
    assert protected() == baseline and ref(RECEIPT) == original
    assert sorted(set(call('image', 'ls', '-q', '--no-trunc').split())) == images_before
    save('retirement.json', {'at': datetime.now(timezone.utc).isoformat(), 'status': 'EXACT_OBSOLETE_STACK_RETIRED',
         'backup': ref(OUT / 'backup-audit.json'), 'protected_unchanged': baseline, 'no_image_removed': True,
         'receipt_preserved': original, 'raw_pg_volumes_preserved': pg_volumes})
    print(json.dumps({'status': 'EXACT_OBSOLETE_STACK_RETIRED', 'no_image_removed': True}), flush=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan',type=Path)
parser.add_argument('--archive-only',action='store_true',help='Read-only full backup; never stop or remove stack resources.')
args = parser.parse_args()
PLAN = json.loads(args.plan.read_text(encoding='utf-8')) if args.plan else None
ARCHIVE_ONLY=args.archive_only
if PLAN:
    assert args.plan.resolve().is_relative_to(Path(__file__).resolve().parent)
    RECEIPT = Path(PLAN['receipt']).resolve(strict=True)
    assert RECEIPT.is_relative_to(ROOT/'backend/test-output/release-gates')
    OUT = Path(PLAN['output']).resolve()
    assert OUT.is_relative_to(Path(__file__).resolve().parent)
    ARCHIVE = Path(PLAN['archive']).resolve()
    if ARCHIVE_ONLY:
        OUT=OUT.with_name(OUT.name+'-archive-only')
        ARCHIVE=ARCHIVE.with_name(ARCHIVE.name+'-archive-only')
    IMAGE,PROD,NAMES = PLAN['image_id'],PLAN['expected_production_image'],PLAN['resources']
    token = NAMES['app'].removeprefix('nis-e2e-app-')
    assert len(token)==12 and all(char in '0123456789abcdef' for char in token)
    assert NAMES == {kind:'nis-e2e-'+kind+'-'+token for kind in ('app','db','network','runtime')}
spec = importlib.util.spec_from_file_location('neu9_release_owner', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
with owner.gate_lock(ROOT):
    main()
