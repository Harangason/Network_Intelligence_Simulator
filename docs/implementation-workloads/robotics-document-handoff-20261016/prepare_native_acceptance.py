"""Prepare an independent native UI stack using the exact gate candidate.

This never builds an image, modifies production, or issues a release PASS.
The separate stack survives the release suite's intentional app restarts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--candidate-receipt', type=Path, required=True)
args = parser.parse_args()
candidate = json.loads(args.candidate_receipt.read_text(encoding='utf-8'))
assert candidate['status'] in {'RUNNING', 'PASS'} and candidate.get('image_id')
assert any(check['name'] == 'production-build' and check['exit_code'] == 0 for check in candidate['checks'])
assert not (OUT / 'native-runtime-preparation.json').exists(), 'Do not interrupt an existing native run.'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']


def call(*command):
    return subprocess.check_output([docker, *command], text=True, encoding='utf-8').strip()


production = json.loads(call('inspect', 'NetworkIS'))[0]
production_env = dict(entry.split('=', 1) for entry in production['Config']['Env'] if '=' in entry)
model_keys = ('LOCAL_AI_BASE_URL', 'LOCAL_AI_MODEL', 'LOCAL_AI_CONTEXT_TOKENS',
              'LOCAL_AI_TIMEOUT_SECONDS', 'OLLAMA_KEEP_ALIVE')
model_env = {key: production_env[key] for key in model_keys if key in production_env}
address = urlsplit(model_env.get('LOCAL_AI_BASE_URL', 'http://127.0.0.1:11434/v1'))
assert address.hostname in {'localhost', '127.0.0.1', '::1', 'host.docker.internal', 'ollama'}
assert address.username is None and address.password is None
environment = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': address.geturl()}
stack_output = OUT / 'native-acceptance-stack'
with (OUT / 'native-prepare.log').open('w', encoding='utf-8') as log:
    subprocess.run([sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare',
                    '--image', candidate['image_id'], '--output', str(stack_output)],
                   env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
receipts = list(stack_output.glob('*/receipt.json'))
assert len(receipts) == 1
receipt_path = receipts[0]
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and receipt['image_id'] == candidate['image_id']
assert receipt['initial_source_sha256'] == candidate['initial_source_sha256']
names = receipt['containers']
assert all(names[key].startswith('nis-e2e-' + key + '-') for key in ('app', 'db', 'network', 'runtime'))
test_app = json.loads(call('inspect', names['app']))[0]
assert test_app['Config']['Labels']['networkis.test'] == 'disposable'
assert test_app['Image'] == candidate['image_id'] and test_app['Id'] != production['Id']
test_env = dict(entry.split('=', 1) for entry in test_app['Config']['Env'] if '=' in entry)
database = urlsplit(test_env['DATABASE_URL'])
assert database.hostname == 'test-db' and database.path == '/nis_test_e2e'
port = test_app['HostConfig']['PortBindings']['13500/tcp'][0]
assert port['HostIp'] == '127.0.0.1' and int(port['HostPort']) != 13500
assert any(mount['Name'] == names['runtime'] and mount['Destination'] == '/app/var/data'
           for mount in test_app['Mounts'] if mount['Type'] == 'volume')
# Match the product's model/context/timeout settings without copying its DB.
# Only this still-empty, owned disposable app is recreated; its DB survives.
call('stop', names['app'])
call('rm', names['app'])
test_env.update(model_env)
test_env.update(AI_PROVIDER='hybrid-demand', CLOUD_ESCALATION='never')
keys = ('DATABASE_URL', 'NETWORKIS_ALLOW_NON_CANONICAL_ROOT', 'NUMERIC_ACCELERATOR',
        'NIS_DATA_DIR', 'NIS_RUNTIME_DIR', 'SIMULATION_EXECUTOR', 'AI_PROVIDER', 'CLOUD_ESCALATION', *model_keys)
command = [docker, 'run', '-d', '--name', names['app'], '--network', names['network'],
           '--label', 'networkis.test=disposable']
for key in keys:
    if key in test_env:
        command.extend(['-e', key])  # No DB credential is embedded in command text.
command.extend(['-p', f"127.0.0.1:{port['HostPort']}:13500", '--mount',
                'type=volume,source=' + names['runtime'] + ',target=/app/var/data', candidate['image_id']])
subprocess.run(command, env={**os.environ, **test_env}, check=True, capture_output=True, text=True)
base = receipt['base_url']
for attempt in range(60):
    try:
        with urlopen(base + '/api/ready', timeout=2) as response:
            ready = json.load(response)
        with urlopen(base + '/api/build-info', timeout=2) as response:
            build = json.load(response)
        if ready.get('status') == 'ready' and build['source_sha256'] == candidate['initial_source_sha256']:
            break
    except (OSError, ValueError):
        pass
    time.sleep(1)
else:
    raise RuntimeError('Independent native UI stack did not become ready.')
running = json.loads(call('inspect', names['app']))[0]
assert running['Image'] == candidate['image_id']
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == production['Image']
record = {'status': 'READY_FOR_NATIVE_ACCEPTANCE', 'release_pass': False,
          'candidate_receipt': str(args.candidate_receipt.resolve()), 'prepared_receipt': str(receipt_path),
          'image_id': running['Image'], 'source_sha256': build['source_sha256'], 'base_url': base,
          'containers': names, 'app_container_id': running['Id'], 'model_environment': model_env,
          'uses_product_database': False, 'production_unchanged': True,
          'runtime_environment_sha256': hashlib.sha256(json.dumps(model_env, sort_keys=True).encode()).hexdigest()}
(OUT / 'native-runtime-preparation.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps({key: record[key] for key in ('status', 'base_url', 'image_id', 'source_sha256')}))
