"""Remove only this completed, evidenced disposable native stack; keep image."""
from pathlib import Path
import datetime
import json
import subprocess

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
verification = json.loads((OUT / 'native-verification.json').read_text(encoding='utf-8'))
audit = json.loads((OUT / 'native-tool-audit.json').read_text(encoding='utf-8'))
assert verification['status'] in {'PASSED', 'FAILED'} and audit['status'] == 'PASSED'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()
names = runtime['containers']
for kind in ('app', 'db', 'network', 'runtime'):
    assert names[kind].startswith('nis-e2e-' + kind + '-') and names[kind].endswith('ba70268dda42')
app = json.loads(call('inspect', names['app']))[0]
db = json.loads(call('inspect', names['db']))[0]
assert app['Id'] == runtime['app_container_id'] and app['Image'] == runtime['image_id']
assert all(item['Config']['Labels']['networkis.test'] == 'disposable' for item in (app, db))
network = json.loads(call('network', 'inspect', names['network']))[0]
volume = json.loads(call('volume', 'inspect', names['runtime']))[0]
assert network['Labels']['networkis.test'] == volume['Labels']['networkis.test'] == 'disposable'
assert {item['Name'] for item in network['Containers'].values()} == {names['app'], names['db']}
assert set(call('ps', '-a', '--filter', 'volume=' + names['runtime'], '--format', '{{.Names}}').splitlines()) == {names['app']}
production_before = call('inspect', 'NetworkIS', '--format', '{{.Id}} {{.Image}}')
with (OUT / 'native-app.log').open('w', encoding='utf-8') as log:
    subprocess.run([docker, 'logs', names['app']], stdout=log, stderr=subprocess.STDOUT, check=True)
call('stop', names['app'], names['db'])
call('rm', names['app'], names['db'])
call('volume', 'rm', names['runtime'])
call('network', 'rm', names['network'])
assert call('inspect', 'NetworkIS', '--format', '{{.Id}} {{.Image}}') == production_before
record = {'status': 'COMPLETED_NATIVE_STACK_REMOVED', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'native_result': verification['status'], 'resources': names, 'app_id': app['Id'], 'db_id': db['Id'],
          'image_retained': runtime['image_id'], 'production_unchanged': True, 'evidence_retained': True,
          'prepared_receipt_history_unchanged': True, 'currently_active_native_work': False}
(OUT / 'native-stack-cleanup.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))

