"""Existing four-case browser regression against a regular disposable candidate."""
import importlib.util, json, os, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse

output = Path(__file__).parent.resolve()
root = output.parents[2]
prefix = sys.argv[2] if len(sys.argv) > 2 else 'performance'
assert prefix in {'performance', 'catalog'}
receipt_path = Path(sys.argv[1]).resolve()
assert receipt_path.is_relative_to(output/'performance-stack')
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and not receipt.get('development_only')
spec = importlib.util.spec_from_file_location('build_info', root/'scripts/write-build-info.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
assert receipt['release']['source_sha256'] == module.build_manifest()['source_sha256']
endpoint = urlparse(receipt['base_url'])
assert endpoint.hostname == '127.0.0.1' and endpoint.port != 13500
names = receipt['containers']
for key, expected_prefix in {'app':'nis-e2e-app-', 'db':'nis-e2e-db-', 'network':'nis-e2e-network-', 'runtime':'nis-e2e-runtime-'}.items():
    assert names[key].startswith(expected_prefix)
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
assert subprocess.check_output([docker,'inspect',names['app'],'--format','{{.Image}}'],text=True).strip() == receipt['image_id']
temp = output/(prefix+'-browser-temp'); temp.mkdir(exist_ok=True)
environment = {**os.environ, 'TEMP':str(temp), 'TMP':str(temp), 'TMPDIR':str(temp),
    'NIS_E2E_ISOLATED':'1', 'NIS_E2E_URL':receipt['base_url'],
    'NIS_E2E_APP_CONTAINER':names['app'], 'NIS_TEST_DOCKER':docker,
    'NIS_E2E_OUTPUT':str(output/(prefix+'-browser')), 'NIS_E2E_REPORT':str(output/(prefix+'-browser.json'))}
environment.pop('NIS_E2E_BROWSER_CHANNEL', None)
cleanup = []
try:
    files = ['e2e/wizard.spec.ts'] + (['e2e/technology-parameter-review.spec.ts'] if prefix == 'catalog' else [])
    selected = 'new small wizard|Raspberry Pi|exact confirmed 50' + ('|native simulation rates' if prefix == 'catalog' else '')
    with (output/(prefix+'-browser.log')).open('w',encoding='utf-8') as log:
        result = subprocess.run(['C:/Program Files/nodejs/node.exe', 'node_modules/playwright/cli.js',
            'test', *files, '--grep', selected],
            cwd=root/'frontend',env=environment,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode == 0:
        report = json.loads((output/(prefix+'-browser.json')).read_text(encoding='utf-8'))
        assert report['stats']['expected'] == (8 if prefix == 'catalog' else 4) and report['stats']['unexpected'] == 0 and not report.get('errors')
    print(json.dumps({'exit_code':result.returncode,'scope':'Small full workflow, two native negatives, captured large full nine-stage flow and separate three-phase repeated review continuity'}))
finally:
    for key in ('app','db'):
        with (output/(prefix+'-'+key+'-container.log')).open('w',encoding='utf-8') as log:
            subprocess.run([docker,'logs',names[key]],stdout=log,stderr=subprocess.STDOUT)
        details = json.loads(subprocess.check_output([docker,'inspect',names[key]],text=True))[0]
        (output/(prefix+'-'+key+'-state.json')).write_text(json.dumps({
            'State':details['State'], 'Ports':details['NetworkSettings']['Ports'],
            'PortBindings':details['HostConfig']['PortBindings']},indent=2),encoding='utf-8')
    for kind, key in [('container','app'),('container','db'),('network','network'),('volume','runtime')]:
        inspect = [docker,'inspect'] if kind == 'container' else [docker,kind,'inspect']
        label = '{{ index .Config.Labels "networkis.test" }}' if kind == 'container' else '{{ index .Labels "networkis.test" }}'
        assert subprocess.check_output([*inspect,names[key],'--format',label],text=True).strip() == 'disposable'
        command = [docker,'rm','-f',names[key]] if kind == 'container' else [docker,kind,'rm',names[key]]
        removal = subprocess.run(command,capture_output=True,text=True)
        cleanup.append({'kind':kind,'name':names[key],'exit_code':removal.returncode})
        assert removal.returncode == 0, removal.stderr
    (output/(prefix+'-browser-cleanup.json')).write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
sys.exit(result.returncode)
