"""Verify exact delivery and pure source-preview components; no model requests."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import subprocess
import sys
import urllib.request

directory = Path(__file__).resolve().parent
root = directory.parents[2]
receipt_path = root / 'backend/test-output/release-gates/delivery-6127991a9e47/4310b821dab9/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
module_spec = importlib.util.spec_from_file_location('preview_release_storage', root / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(storage)
assert storage.complete_pass(receipt)
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container = json.loads(subprocess.check_output([docker, 'inspect', 'NetworkIS'], text=True, encoding='utf-8'))[0]
assert container['Image'] == receipt['image_id'] and container['State']['Running'] is True
phase = sys.argv[1]
report = {'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Exact image identity and normal availability reads; optional pure source-preview component probe without inference or project writes',
          'image_id': container['Image'], 'source_sha256': receipt['release']['source_sha256'], 'phase': phase,
          'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(), 'http': []}
environment = dict(value.split('=', 1) for value in container['Config']['Env'] if '=' in value)
report['configured_models'] = {key: environment.get(key) for key in ['LOCAL_AI_MODEL', 'LOCAL_AI_FAST_MODEL']}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for base in ['http://127.0.0.1:13500', 'http://127.0.0.1:15050', 'http://192.168.178.10:13500']:
    for path in ['/api/ready', '/api/build-info']:
        with opener.open(base + path, timeout=15) as response:
            raw = response.read()
            assert response.status == 200
        value = json.loads(raw)
        if path == '/api/ready':
            assert value.get('status') == 'ready'
        else:
            assert value['source_sha256'] == report['source_sha256']
        report['http'].append({'url': base + path, 'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest(), 'value': value})
for base in ['http://127.0.0.1:13500', 'http://192.168.178.10:13500']:
    url = base + '/studio/engineering?project=20261106093746010-f2585546'
    with opener.open(url, timeout=15) as response:
        raw = response.read()
        assert response.status == 200 and b'<html' in raw.lower()
    report['http'].append({'url': url, 'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest()})
if phase == 'components':
    script = (directory / 'production_preview_probe.mjs').read_bytes()
    command = [docker, 'exec', '-i', '-e', 'NIS_PROBE_EXPECTED_SOURCE=' + report['source_sha256'],
               'NetworkIS', 'node', '--experimental-strip-types', '--input-type=module']
    with (directory / 'production-preview.stdout.json').open('wb') as stdout, (directory / 'production-preview.stderr.log').open('wb') as stderr:
        result = subprocess.run(command, input=script, stdout=stdout, stderr=stderr)
    report['component_exit_code'] = result.returncode
    report['script_sha256'] = hashlib.sha256(script).hexdigest()
    report['status'] = 'PROCESS_EXITED_0' if result.returncode == 0 else 'FAILED'
    (directory / 'live-components-process.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    assert result.returncode == 0, 'Inspect preserved stdout/stderr before any retry'
    assert json.loads((directory / 'production-preview.stdout.json').read_bytes())['status'] == 'PASSED'
report['status'] = 'PASSED'
destination = directory / ('live-' + phase + '.json')
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'path': str(destination), 'image_id': report['image_id'], 'http_checks': len(report['http']), 'component_exit_code': report.get('component_exit_code')}))
