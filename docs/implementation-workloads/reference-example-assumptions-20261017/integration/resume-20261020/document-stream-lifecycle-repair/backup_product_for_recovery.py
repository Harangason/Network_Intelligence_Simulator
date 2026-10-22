"""Read-only production backup before bounded app-only worker recovery."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent / 'production-recovery-backup' / 'registered-projects-and-database'
if OUT.exists():
    assert not any(OUT.iterdir()), 'Preserve any partial backup instead of overwriting it'
else:
    OUT.mkdir()
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
records = []

def save(name, raw):
    path = OUT / name
    path.write_bytes(raw)
    records.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

def get(name, route, project=None):
    headers = {'X-Project-ID': project} if project else {}
    with urlopen(Request('http://127.0.0.1:13500' + route, headers=headers), timeout=45) as response:
        raw = response.read()
    save(name + '.json', raw)
    return json.loads(raw)

app = json.loads(subprocess.check_output([DOCKER, 'inspect', 'NetworkIS']))[0]
assert app['Image'] == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
get('ready', '/api/ready')
get('build-info', '/api/build-info')
projects = get('projects', '/api/engineering/projects')['items']
for row in projects:
    project = row['project_id']
    prefix = project.removeprefix('network-project-')
    get(prefix + '-bundle', '/api/engineering/projects/export', project)
    conversation = get(prefix + '-conversation', '/api/engineering/agent/conversation', project)
    assert not conversation.get('data', {}).get('active_workload'), project
    get(prefix + '-draft', '/api/engineering/agent/project-draft', project)
    jobs = get(prefix + '-jobs', '/api/simulations', project)['jobs']
    assert not any(str(job.get('status', '')).lower() in {'running', 'queued', 'pending'} for job in jobs), project

db = json.loads(subprocess.check_output([DOCKER, 'inspect', 'NetworkIS-db']))[0]
selected = dict(item.split('=', 1) for item in db['Config']['Env'] if item.startswith(('POSTGRES_USER=', 'POSTGRES_DB=')))
dump = OUT / 'production-readonly.pgcustom'
with dump.open('wb') as target:
    result = subprocess.run([DOCKER, 'exec', 'NetworkIS-db', 'pg_dump', '-U', selected['POSTGRES_USER'], '-d', selected['POSTGRES_DB'], '-Fc'], stdout=target, stderr=subprocess.PIPE)
assert result.returncode == 0, 'Read-only pg_dump failed'
with dump.open('rb') as source:
    toc = subprocess.run([DOCKER, 'exec', '-i', 'NetworkIS-db', 'pg_restore', '--list'], stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assert toc.returncode == 0 and b'TABLE DATA' in toc.stdout, 'Archive TOC verification failed'
save('production-readonly.toc', toc.stdout)
records.append({'path': dump.name, 'bytes': dump.stat().st_size, 'sha256': hashlib.file_digest(dump.open('rb'), 'sha256').hexdigest()})
review = {'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Operational read-only backup; no SQL tests, no restore, no model mutation.', 'production_image': app['Image'], 'registered_projects': [row['project_id'] for row in projects], 'active_persisted_workloads_or_jobs': False, 'deleted_default': 'Excluded from export because prior GET returned deleted-project 400; preserved in full database dump.', 'records': records, 'status': 'VERIFIED_READONLY_RECOVERY_BACKUP'}
(OUT / 'backup-review.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf8')
print(json.dumps({key: review[key] for key in ['status', 'production_image', 'registered_projects']}), flush=True)
