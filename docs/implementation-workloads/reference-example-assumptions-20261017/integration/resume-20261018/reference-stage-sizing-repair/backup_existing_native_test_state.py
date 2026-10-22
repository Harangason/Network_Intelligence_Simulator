"""Read-only backup of the exact isolated native-test database and projects."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

D = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
OUT = Path(__file__).resolve().parent / 'before-test-image-upgrade'
OUT.mkdir(exist_ok=False)
APP = 'nis-e2e-app-bec4ad8557f2'
DB = 'nis-e2e-db-bec4ad8557f2'
IMAGE = 'sha256:ef9d9385fdedd4ae3caf8e690b1144960df86b1e4043fb533cad2e7159793764'
BASE = 'http://127.0.0.1:54447'
PROJECTS = ['20261018160006106-ee6625c9', '20261018160157264-5f0fa2a4']


def run(*args, data=None):
    return subprocess.run([D, *args], input=data, capture_output=True, check=True).stdout


app = json.loads(run('inspect', APP))[0]
db = json.loads(run('inspect', DB))[0]
assert app['Image'] == IMAGE and app['State']['Running'] and db['State']['Running']
assert app['HostConfig']['NetworkMode'] == 'nis-e2e-network-bec4ad8557f2'
assert db['HostConfig']['NetworkMode'] == app['HostConfig']['NetworkMode']
production = json.loads(run('inspect', 'NetworkIS'))[0]['Image']
records = []
for project in PROJECTS:
    for name, path in {
        'bundle': '/api/engineering/projects/export',
        'draft': '/api/engineering/agent/project-draft',
        'workflow': '/api/engineering/workflow',
        'jobs': '/api/simulations',
    }.items():
        with urlopen(Request(BASE + path, headers={'X-Project-ID': project}), timeout=30) as response:
            raw = response.read()
        if name == 'bundle':
            bundle = json.loads(raw)
            assert bundle['project_id'].removeprefix('network-project-') == project
            assert not any(len(value) for value in bundle['source_data'].values())
        path = OUT / f'{project}-{name}.json'
        path.write_bytes(raw)
        records.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
dump = run('exec', DB, 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc')
assert dump.startswith(b'PGDMP')
dump_path = OUT / 'native-test-projects-bec4-before-upgrade.dump'
dump_path.write_bytes(dump)
toc = run('exec', '-i', DB, 'pg_restore', '--list', data=dump)
assert b'engineering_agent_conversations' in toc
(OUT / 'database-dump-toc.txt').write_bytes(toc)
assert json.loads(run('inspect', 'NetworkIS'))[0]['Image'] == production
manifest = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'READ_ONLY_TEST_BACKUP_VERIFIED',
    'scope': __doc__, 'app': APP, 'database': DB, 'image_id': IMAGE,
    'runtime_volume': [mount['Name'] for mount in app['Mounts'] if mount['Type'] == 'volume'],
    'actual_project_ids': PROJECTS, 'records': records,
    'database_dump': {'path': str(dump_path), 'bytes': len(dump), 'sha256': hashlib.sha256(dump).hexdigest(),
                      'pg_restore_list_verified': True},
    'production_image_id_unchanged': production, 'database_writes_or_restore': False,
    'containers_stopped_or_changed': False, 'models_corrected': False}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': manifest['status'], 'projects': PROJECTS, 'dump_bytes': len(dump),
                  'production_changed': False}), flush=True)
