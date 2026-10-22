"""Remove only the human-authorized archived test app and exact image; keep DB."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'archive-review-30613c75a967'
AUDIT = json.loads((OUT / 'archive-audit.json').read_text())
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
TAG = 'networkis:candidate-30613c75a967'
IMAGE = 'sha256:d85e64ddadb9a1fc2ae9cff4ebe1bdf06decde8bc72b939a80449f391d130b66'
APP = 'nis-e2e-app-30613c75a967'
DB = 'nis-e2e-db-30613c75a967'
PRODUCTION = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'

def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf8').strip()

def fingerprint(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

assert not (OUT / 'authorized-removal.json').exists(), 'Inspect completed removal; do not repeat'
assert AUDIT['tag'] == TAG and AUDIT['image'] == IMAGE
assert len(AUDIT['verified_blobs']) == 23 and AUDIT['all_layers_verified'] and AUDIT['immutable_index_verified'] and AUDIT['immutable_config_verified']
for item in [AUDIT['archive'], AUDIT['database_dump'], AUDIT['receipt'], *AUDIT['exports']]:
    path = Path(item['path'])
    assert path.is_file() and path.stat().st_size == item['bytes']
    assert fingerprint(path) == item['sha256'], path
assert json.loads(Path(AUDIT['receipt']['path']).read_text())['status'] == 'PREPARED'
assert call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *ids))
refs = [{'id': c['Id'], 'name': c['Name'], 'image': c['Image']} for c in containers if c['Image'] == IMAGE]
assert len(refs) == 1 and refs[0]['name'] == '/' + APP
app = next(c for c in containers if c['Name'] == '/' + APP)
db = next(c for c in containers if c['Name'] == '/' + DB)
assert app['Id'] == '6dc22cb56c9c2fb646160760700e5deb0b617c6d4941befefdd0e4331b89c87b'
assert db['State']['Running'] and db['Image'] != IMAGE
db_before = {'id': db['Id'], 'image': db['Image'], 'running': True}
assert not any(c['Name'] == '/' + APP and c['State']['Restarting'] for c in containers)
exports = []
for project in ('20261018160006106-ee6625c9', '20261018160157264-5f0fa2a4'):
    for label, endpoint in [('bundle','/api/engineering/projects/export'), ('jobs','/api/simulations'), ('conversation','/api/engineering/agent/conversation')]:
        with urlopen(Request('http://127.0.0.1:60655' + endpoint, headers={'X-Project-ID': project}), timeout=30) as response:
            raw = response.read()
        data = json.loads(raw)
        if label == 'bundle':
            assert all(not rows for rows in data['source_data'].values())
        if label == 'jobs':
            assert not data['jobs']
        if label == 'conversation':
            assert not data.get('data', {}).get('active_workload')
        destination = OUT / (project + '-before-authorized-removal-' + label + '.json')
        destination.write_bytes(raw)
        exports.append({'path': str(destination), 'sha256': fingerprint(destination)})
# Preserve newer isolated browser-test metadata as well; no DB removal is authorized.
dump = Path(AUDIT['database_dump']['path']).with_name('native-test-projects-306-before-authorized-app-removal.dump')
assert not dump.exists()
with dump.open('wb') as stream:
    subprocess.run([DOCKER, 'exec', DB, 'sh', '-c', 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=stream, check=True)
with dump.open('rb') as stream:
    result = subprocess.run([DOCKER, 'exec', '-i', DB, 'pg_restore', '--list'], stdin=stream, capture_output=True, check=True)
assert b'TABLE DATA' in result.stdout
(OUT / 'before-authorized-removal-dump-toc.txt').write_bytes(result.stdout)
save('human-authorized-removal-precheck.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'authorization': {'question_id':'call_8da1cbae63dd4482bfa85f7bf32043bf', 'answer':'Genau diesen Test-Appcontainer und dieses Image entfernen'}, 'image': IMAGE, 'tag': TAG, 'fresh_refs': refs, 'archive_hash_rechecked': True, 'fresh_dump': {'path':str(dump),'sha256':fingerprint(dump)}, 'exports':exports,'retained_database':db_before,'production':PRODUCTION})
subprocess.run([DOCKER, 'stop', '--time', '30', APP], check=True)
subprocess.run([DOCKER, 'rm', APP], check=True)
ids = call('ps', '-aq', '--no-trunc').split()
remaining = json.loads(call('inspect', *ids)) if ids else []
assert not any(c['Image'] == IMAGE for c in remaining)
assert call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
subprocess.run([DOCKER, 'image', 'rm', '--no-prune', TAG], check=True)
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
assert call('inspect', DB, '--format', '{{.Id}}') == db_before['id']
assert call('inspect', DB, '--format', '{{.State.Running}}') == 'true'
save('authorized-removal.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'status':'EXACT_AUTHORIZED_APP_AND_IMAGE_REMOVED_DB_RETAINED', 'authorization_question_id':'call_8da1cbae63dd4482bfa85f7bf32043bf','app':APP,'image':IMAGE,'tag':TAG,'retained_database':db_before,'production_unchanged':True,'image_removal_flags':['--no-prune'],'force_or_bulk_prune':False})
print('Authorized app and exact image removed. Test DB and production retained.', flush=True)
