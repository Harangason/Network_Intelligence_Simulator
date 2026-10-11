"""Add diagnostic sampling without changing the candidate image or app source."""
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
RECEIPT = OUT.parents[2] / 'backend/test-output/release-gates/bus-rate-large-diagnostic-20261006/ec8528aadd0b/receipt.json'
receipt = json.loads(RECEIPT.read_text())
assert receipt['status'] == 'PREPARED'
name = receipt['containers']['app']
assert name == 'nis-e2e-app-ec8528aadd0b'
def docker(*args):
    return subprocess.check_output([DOCKER, *args], text=True).strip()
original = json.loads(docker('inspect', name))[0]
assert original['Config']['Labels']['networkis.test'] == 'disposable'
assert original['Image'] == receipt['image_id']
ports = original['HostConfig']['PortBindings']['13500/tcp']
assert len(ports) == 1 and ports[0]['HostIp'] == '127.0.0.1'
assert int(ports[0]['HostPort']) not in {13500, 15050}
assert original['Config']['Entrypoint'] is None
assert original['Config']['Cmd'] == ['python', 'generate_realistic_communication_tool.py']
command = ['run', '-d', '--name', name, '--network', receipt['containers']['network'],
           '--label', 'networkis.test=disposable', '-p', '127.0.0.1:' + ports[0]['HostPort'] + ':13500']
for mount in original['Mounts']:
    assert mount['Type'] == 'volume' and mount['Name'] == receipt['containers']['runtime']
    command += ['--mount', 'type=volume,source=' + mount['Name'] + ',target=' + mount['Destination']]
command += ['--mount', 'type=bind,source=' + str(OUT / 'diagnostic') + ',target=/tmp/nis-diagnostic,readonly']
environment = [item for item in original['Config']['Env'] if not item.startswith('PYTHONPATH=')]
environment.append('PYTHONPATH=/tmp/nis-diagnostic:/app')
for item in environment:
    command += ['-e', item]
command.append(receipt['image_id'])
docker('stop', '-t', '10', name)
docker('rm', name)
created = docker(*command)
for _ in range(180):
    try:
        with urlopen(receipt['base_url'] + '/api/ready', timeout=2) as response:
            if response.status == 200:
                break
    except Exception:
        pass
    time.sleep(1)
else:
    raise RuntimeError('Isolated diagnostic app readiness failed')
assert docker('inspect', name, '--format', '{{.Image}}') == receipt['image_id']
print(json.dumps({'diagnostic_only': True, 'image_unchanged': True, 'app': name, 'container': created}))
