"""Run existing browser regressions only against our disposable prepared stack."""
import json, os, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse

output = Path(__file__).parent.resolve()
root = output.parents[2]
receipt_path = Path(sys.argv[1]).resolve()
assert receipt_path.is_relative_to(output/'browser-target-stack')
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED'
assert receipt['image_id'] == 'sha256:4ae5cb12dd7131f7c2a406b2c135767471a345df2220446df6960e265d61375b'
assert receipt['release']['source_sha256'] == '1b66e7387a62c26b1ba9c9bad7ee2b1d27c87edfd778cd463ca5eaeae032ee4f'
endpoint = urlparse(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port != 13500
names = receipt['containers']
for key, prefix in {'app':'nis-e2e-app-', 'db':'nis-e2e-db-',
                    'network':'nis-e2e-network-', 'runtime':'nis-e2e-runtime-'}.items():
    assert names[key].startswith(prefix)
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
environment = {**os.environ, 'NIS_E2E_ISOLATED':'1', 'NIS_E2E_URL':receipt['base_url'],
    'NIS_E2E_APP_CONTAINER':names['app'], 'NIS_TEST_DOCKER':docker,
    'NIS_E2E_OUTPUT':str(output/'browser-target'), 'NIS_E2E_REPORT':str(output/'browser-target.json')}
environment.pop('NIS_E2E_BROWSER_CHANNEL', None)
cleanup = []
try:
    with (output/'browser-target.log').open('w',encoding='utf-8') as log:
        result = subprocess.run(['C:/Program Files/nodejs/node.exe', 'node_modules/playwright/cli.js',
            'test', 'e2e/wizard.spec.ts', '--grep', 'new small wizard|Raspberry Pi'],
            cwd=root/'frontend',env=environment,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode == 0:
        report = json.loads((output/'browser-target.json').read_text(encoding='utf-8'))
        assert report['stats']['expected'] == 3 and report['stats']['unexpected'] == 0 and not report.get('errors')
    print(json.dumps({'exit_code':result.returncode, 'scope':'Existing small nine-stage restore and two native configuration negatives'}))
finally:
    for kind, key in [('container','app'), ('container','db'), ('network','network'), ('volume','runtime')]:
        inspect = [docker, 'inspect'] if kind == 'container' else [docker,kind,'inspect']
        label = '{{ index .Config.Labels "networkis.test" }}' if kind == 'container' else '{{ index .Labels "networkis.test" }}'
        observed = subprocess.check_output([*inspect,names[key],'--format',label],text=True).strip()
        assert observed == 'disposable', (kind,names[key],observed)
        command = [docker,'rm','-f',names[key]] if kind == 'container' else [docker,kind,'rm',names[key]]
        removal = subprocess.run(command,capture_output=True,text=True)
        cleanup.append({'kind':kind,'name':names[key],'exit_code':removal.returncode})
        assert removal.returncode == 0, removal.stderr
    (output/'browser-target-cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
sys.exit(result.returncode)
