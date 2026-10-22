"""Read-only checkpoint of the isolated diagnostic DB; no production DB access."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent / 'waiting-capacity-checkpoint'
OUT.mkdir(exist_ok=True)
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
DB = 'nis-e2e-db-d851f62a961b'
APP = 'nis-e2e-app-d851f62a961b'
IMAGE = 'sha256:0a191a95598704d2dc1c0f1a7060665b8c896bfdf8d36ec8a43a5daa1a6a5d74'


def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()


db = json.loads(call('inspect', DB))[0]
assert db['Name'] == '/' + DB and db['State']['Running']
assert 'nis-e2e-' in next(iter(db['NetworkSettings']['Networks']))
assert db['HostConfig']['Tmpfs']
assert call('inspect', APP, '--format', '{{.Image}}') == IMAGE
production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
remote = '/tmp/nis-joint-awaiting-capacity.dump'
call('exec', DB, 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc', '-f', remote)
dump = OUT / 'isolated-database.dump'
call('cp', DB + ':' + remote, str(dump))
toc = call('exec', DB, 'pg_restore', '--list', remote)
assert 'DATABASE' in toc or 'TABLE' in toc
(OUT / 'database-toc.txt').write_text(toc + '\n', encoding='utf-8')
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'ISOLATED_DIAGNOSTIC_DB_CHECKPOINTED',
    'database_container': DB, 'database': 'nis_test_e2e', 'application_image': IMAGE,
    'serving_source_sha256': '2d0d2b566456e5a8614b4cace16380ec0a3cb73525076fcf510ca8b0b538f0bd',
    'pending_joint_source_sha256': 'cf37e30cc3a5e18124c1eec3936373c4920d295d48657b70dcbc0ee9be929b56',
    'dump': {'path': str(dump), 'bytes': dump.stat().st_size, 'sha256': hashlib.sha256(dump.read_bytes()).hexdigest()},
    'diagnostic_projects': ['20261017190202251-60e9cb65', '20261018080054592-1985b7e0'],
    'canonical_model_changes_by_agent': 0, 'new_native_simulations': 0,
    'production_unchanged': call('inspect', 'NetworkIS', '--format', '{{.Image}}') == production,
    'containers_stopped': False, 'full_release_pass': False}
(OUT / 'checkpoint.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result), flush=True)
