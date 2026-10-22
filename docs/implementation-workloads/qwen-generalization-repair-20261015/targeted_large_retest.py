"""Run one complete large wizard against the existing immutable image in a disposable stack."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

base = Path(__file__).resolve().parent
root = base.parents[2]
receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
image = receipt['image_id']
assert re.fullmatch(r'sha256:[0-9a-f]{64}', image)
assert not receipt.get('development_only')
assert receipt['status'] == 'PREPARED' and receipt['image_id'] == image
assert receipt['initial_source_sha256'] == receipt['release']['source_sha256']
url = urlparse(receipt['base_url'])
assert url.hostname == '127.0.0.1' and url.port not in (13500, 15050, None)
names = receipt['containers']
for kind in ('app', 'db', 'network', 'runtime'):
    assert re.fullmatch('nis-e2e-' + kind + '-[0-9a-f]{12}', names[kind])
docker = json.loads((root/'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
for kind in ('app', 'db'):
    info = json.loads(subprocess.check_output([docker, 'inspect', names[kind]], text=True))[0]
    assert info['Config']['Labels']['networkis.test'] == 'disposable'
    if kind == 'app':
        assert info['Image'] == image
output = receipt_path.parent/'targeted-browser'
temp = receipt_path.parent/'targeted-temp'
temp.mkdir(exist_ok=True)
env = {**os.environ, 'NIS_E2E_ISOLATED': '1', 'NIS_E2E_URL': receipt['base_url'],
       'NIS_E2E_APP_CONTAINER': names['app'], 'NIS_TEST_DOCKER': docker,
       'NIS_E2E_OUTPUT': str(output), 'NIS_E2E_REPORT': str(output/'report.json'),
       'TEMP': str(temp), 'TMP': str(temp), 'TMPDIR': str(temp)}
env.pop('NIS_E2E_BROWSER_CHANNEL', None)
node = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
command = [node, 'node_modules/playwright/cli.js', 'test',
           'e2e/wizard.spec.ts', '--grep', 'exact confirmed 50/250/250 request completes through real wizard review']
result = {'status': 'RUNNING', 'image_id': image, 'prepared_receipt': str(receipt_path),
          'scope': 'One complete real50/250/250 nine-stage wizard, real parameter write receipts, unchanged180swrite/240sstage/20minwhole limits; not a full release PASS'}
exit_code = 1
try:
    with (base/'targeted-large-browser.log').open('w', encoding='utf-8') as log:
        run = subprocess.run(command, cwd=root/'frontend', env=env, stdout=log, stderr=subprocess.STDOUT)
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    result.update(status='FAILED', exit_code=run.returncode, stats=report['stats'])
    assert run.returncode == 0 and report['stats']['expected'] == 1
    assert report['stats']['unexpected'] == 0 and report['stats']['skipped'] == 0
    result['status'] = 'PASSED'
    exit_code = 0
finally:
    # Only the exact disposable resources verified above; never remove the image.
    cleanup = []
    for kind in ('app', 'db'):
        with (base/('targeted-' + kind + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([docker, 'logs', '--tail', '200', names[kind]], stdout=log, stderr=subprocess.STDOUT)
        command_result = subprocess.run([docker, 'rm', '-f', names[kind]], capture_output=True, text=True)
        cleanup.append({'kind': 'container', 'name': names[kind], 'exit_code': command_result.returncode})
    for kind, resource in (('network', 'network'), ('volume', 'runtime')):
        command_result = subprocess.run([docker, kind, 'rm', names[resource]], capture_output=True, text=True)
        cleanup.append({'kind': kind, 'name': names[resource], 'exit_code': command_result.returncode})
    result['cleanup'] = cleanup
    (base/'targeted-large-browser-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
assert all(item['exit_code'] == 0 for item in result['cleanup'])
raise SystemExit(exit_code)
