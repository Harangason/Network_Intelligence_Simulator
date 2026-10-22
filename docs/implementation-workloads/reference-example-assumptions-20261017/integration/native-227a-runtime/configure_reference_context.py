"""Expand supported local planner runtime bounds, preserving app and database."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

P = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--previous', type=int, default=32768)
parser.add_argument('--context', type=int, default=65536)
args = parser.parse_args()
assert (args.previous, args.context) in {(32768, 65536), (65536, 131072)}
suffix = '' if args.context == 65536 else '-' + str(args.context)
D = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
APP = 'nis-e2e-app-b2bb3887246e'
OLD = APP + '-context' + str(args.previous)
DB = 'nis-e2e-db-b2bb3887246e'
IMAGE = 'sha256:3bfa6ce10900bea57fa13c73bde4663c07bb5f3a8b5b46ea9237e963f6f19511'
BASE = 'http://127.0.0.1:62470'
PROJECTS = ['20261018141834215-8feb758d', '20261018143136468-0e49a16b']

def run(*args, **kwargs):
    return subprocess.run([D, *args], check=True, capture_output=True, **kwargs)

def inspect(name):
    return json.loads(run('inspect', name, text=True).stdout)[0]

def export(project):
    with urlopen(Request(BASE + '/api/engineering/projects/export', headers={'X-Project-ID': project}), timeout=30) as r:
        return r.read()

a = inspect(APP)
assert a['Image'] == IMAGE
assert inspect(DB)['State']['Running']
prod = inspect('NetworkIS')['Image']
assert subprocess.run([D, 'inspect', OLD], capture_output=True).returncode != 0
env = dict(e.split('=', 1) for e in a['Config']['Env'])
assert env['LOCAL_AI_BASE_URL'] == 'http://host.docker.internal:11434/v1'
assert env['CLOUD_ESCALATION'] == 'never'
assert int(env.get('LOCAL_AI_CONTEXT_TOKENS', '32768')) == args.previous
assert int(env.get('LOCAL_AI_TIMEOUT_SECONDS', '600')) == (600 if args.previous == 32768 else 1200)
network = a['HostConfig']['NetworkMode']
assert network.startswith('nis-e2e-')
assert a['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '62470'}]
mounts = a['Mounts']
assert len(mounts) == 1 and mounts[0]['Type'] == 'volume' and mounts[0]['Destination'] == '/app/var/data'
volume = mounts[0]['Name']
for project in PROJECTS:
    (P / (project + '-before-context' + suffix + '.json')).write_bytes(export(project))
dump = run('exec', DB, 'pg_dump', '-U', 'nis_test', '-d', 'nis_test_e2e', '-Fc').stdout
assert dump.startswith(b'PGDMP')
(P / ('before-context-correction' + suffix + '.dump')).write_bytes(dump)
audit = {'at_utc': datetime.now(timezone.utc).isoformat(), 'image': IMAGE,
         'old_container': OLD, 'new_container': APP, 'database': DB,
         'previous_context_tokens': args.previous, 'context_tokens': args.context,
         'previous_timeout_seconds': int(env.get('LOCAL_AI_TIMEOUT_SECONDS', '600')), 'timeout_seconds': 1200,
         'reason': 'Actual reference planning rejected the complete unchanged source and catalogs at the previous bound before generation; no source truncation permitted.',
         'supported_model_context': 262144, 'supported_reasoner_context_max': 131072,
         'database_dump_sha256': hashlib.sha256(dump).hexdigest(), 'database_dump_bytes': len(dump),
         'original_container_preserved': True, 'production_changed': False,
         'source_changed': False, 'model_corrections': False, 'full_gate_pass': False}
(P / ('context-correction' + suffix + '.json')).write_text(json.dumps(audit, indent=2)+'\n')
run('stop', APP)
run('rename', APP, OLD)
env.update(LOCAL_AI_CONTEXT_TOKENS=str(args.context), LOCAL_AI_TIMEOUT_SECONDS='1200')
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
    raise RuntimeError('App not ready; preserved original app can be restored.')
assert inspect(APP)['Image'] == IMAGE and inspect('NetworkIS')['Image'] == prod
assert inspect(DB)['State']['Running'] and not inspect(OLD)['State']['Running']
for project in PROJECTS:
    raw = export(project)
    (P / (project + '-after-context' + suffix + '.json')).write_bytes(raw)
    before = json.loads((P / (project + '-before-context' + suffix + '.json')).read_bytes())
    after = json.loads(raw)
    before.pop('generated_at', None); after.pop('generated_at', None)
    assert before == after
audit.update(status='SUPPORTED_LOCAL_CONTEXT_EXPANDED_EXACT_IMAGE_AND_PROJECTS_PRESERVED')
(P / ('context-correction' + suffix + '.json')).write_text(json.dumps(audit, indent=2)+'\n')
print(json.dumps(audit), flush=True)
