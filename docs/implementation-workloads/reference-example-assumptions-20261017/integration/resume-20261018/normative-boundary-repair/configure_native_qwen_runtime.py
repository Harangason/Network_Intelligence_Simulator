"""Reversibly correct the isolated prepared app's local provider address."""
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[2] / 'native-227a-runtime'
OUT.mkdir(exist_ok=True)
D = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
APP = 'nis-e2e-app-b2bb3887246e'
OLD = APP + '-provider-disabled'
DB = 'nis-e2e-db-b2bb3887246e'
IMAGE = 'sha256:3bfa6ce10900bea57fa13c73bde4663c07bb5f3a8b5b46ea9237e963f6f19511'
BASE = 'http://127.0.0.1:62470'
PROJECTS = ['20261018141834215-8feb758d', '20261018143136468-0e49a16b']

def run(*args, **kwargs):
    return subprocess.run([D, *args], check=True, capture_output=True, **kwargs)

def inspect(name):
    return json.loads(run('inspect', name, text=True).stdout)[0]

def read_project(project):
    with urlopen(Request(BASE + '/api/engineering/projects/export', headers={'X-Project-ID': project}), timeout=30) as r:
        return r.read()

a = inspect(APP)
assert a['Image'] == IMAGE
assert inspect(DB)['State']['Running']
prod = inspect('NetworkIS')['Image']
assert subprocess.run([D, 'inspect', OLD], capture_output=True).returncode != 0
env = dict(e.split('=', 1) for e in a['Config']['Env'])
assert env['LOCAL_AI_BASE_URL'] == 'http://127.0.0.1:1/v1'
assert env['CLOUD_ESCALATION'] == 'never'
network = a['HostConfig']['NetworkMode']
assert network.startswith('nis-e2e-')
assert a['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '62470'}]
mounts = a['Mounts']
assert len(mounts) == 1 and mounts[0]['Type'] == 'volume' and mounts[0]['Destination'] == '/app/var/data'
volume = mounts[0]['Name']
for p in PROJECTS:
    (OUT / (p + '-before.json')).write_bytes(read_project(p))
dump = run('exec', DB, 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc').stdout
(OUT / 'before-provider-correction.dump').write_bytes(dump)
assert dump.startswith(b'PGDMP')
audit = {'at_utc': datetime.now(timezone.utc).isoformat(), 'image': IMAGE,
         'old_container': OLD, 'new_container': APP, 'database': DB, 'runtime_volume': volume,
         'old_provider': env['LOCAL_AI_BASE_URL'], 'new_provider': 'http://host.docker.internal:11434/v1',
         'original_container_preserved': True, 'production_changed': False,
         'database_dump_sha256': hashlib.sha256(dump).hexdigest(), 'database_dump_bytes': len(dump),
         'source_changed': False, 'model_corrections': False, 'full_gate_pass': False}
(OUT / 'provider-correction.json').write_text(json.dumps(audit, indent=2)+'\n')
run('stop', APP)
run('rename', APP, OLD)
env['LOCAL_AI_BASE_URL'] = audit['new_provider']
command = ['run', '-d', '--name', APP, '--network', network, '--label', 'networkis.test=disposable',
           '-p', '127.0.0.1:62470:13500', '--mount', f'type=volume,source={volume},target=/app/var/data']
for key in env:
    command += ['-e', key]
command += [IMAGE]
run(*command, env={**os.environ, **env})
for _ in range(90):
    try:
        with urlopen(BASE + '/api/ready', timeout=2) as r:
            if r.status == 200:
                break
    except OSError:
        time.sleep(.5)
else:
    raise RuntimeError('Corrected app not ready; preserved original container can be restored.')
b = inspect(APP)
assert b['Image'] == IMAGE and inspect('NetworkIS')['Image'] == prod
assert inspect(DB)['State']['Running'] and not inspect(OLD)['State']['Running']
for p in PROJECTS:
    after = read_project(p)
    (OUT / (p + '-after.json')).write_bytes(after)
    before = json.loads((OUT / (p + '-before.json')).read_bytes())
    after_content = json.loads(after)
    before.pop('generated_at', None)
    after_content.pop('generated_at', None)
    assert after_content == before, 'Project content changed during runtime correction.'
result = run('exec', APP, 'python', '-c', "import json,urllib.request; p=json.load(urllib.request.urlopen('http://host.docker.internal:11434/api/tags')); m=next(x for x in p['models'] if x['name']=='qwen3.8:27b'); assert not m.get('remote_host'); print(json.dumps({'model':m['name'],'digest':m['digest'],'remote_host':m.get('remote_host')}))", text=True)
audit.update(status='LOCAL_PROVIDER_CORRECTED_EXACT_IMAGE_AND_PROJECTS_PRESERVED', provider_probe=json.loads(result.stdout))
(OUT / 'provider-correction.json').write_text(json.dumps(audit, indent=2)+'\n')
print(json.dumps(audit), flush=True)
