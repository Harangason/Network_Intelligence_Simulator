"""Read-only production identity/availability check for this exact delivery."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import urllib.request

root = Path(__file__).resolve().parents[3]
receipt_path = root / 'backend/test-output/release-gates/delivery-9ba63de4dd43/cd21261e671d/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('delivery_storage', root / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
assert storage.complete_pass(receipt), 'A complete actual PASS receipt is required'
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container = json.loads(subprocess.check_output([docker, 'inspect', 'NetworkIS'], text=True, encoding='utf-8'))[0]
assert container['Image'] == receipt['image_id']
assert container['State']['Running'] is True
environment = dict(item.split('=', 1) for item in container['Config']['Env'] if '=' in item)
assert environment['LOCAL_AI_MODEL'] == environment['LOCAL_AI_FAST_MODEL'] == 'llama3.1:8b'
report = {
    'at': datetime.now(timezone.utc).isoformat(),
    'status': 'PASSED',
    'scope': 'Read-only exact running image, configured models, readiness, source and frontend/LAN checks',
    'receipt': {'path': str(receipt_path), 'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()},
    'image_id': container['Image'],
    'source_sha256': receipt['release']['source_sha256'],
    'container_running': True,
    'container_health': container['State'].get('Health', {}).get('Status'),
    'models': {key: environment[key] for key in ('LOCAL_AI_MODEL', 'LOCAL_AI_FAST_MODEL')},
    'http': [],
}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for base in ['http://127.0.0.1:13500', 'http://127.0.0.1:15050', 'http://192.168.178.10:13500']:
    for path in ['/api/ready', '/api/build-info']:
        with opener.open(base + path, timeout=15) as response:
            raw = response.read()
            assert response.status == 200
        value = json.loads(raw)
        if path == '/api/ready':
            assert value['status'] == 'ready'
        else:
            assert value['source_sha256'] == report['source_sha256']
        report['http'].append({'url': base + path, 'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest(), 'value': value})
project = '20261105153906213-bb2b7f6d'
canonical_project = 'network-project-' + project
with opener.open('http://127.0.0.1:13500/api/engineering/projects', timeout=15) as response:
    inventory = json.load(response)
assert any(item['project_id'] == canonical_project for item in inventory['items'])
report['project'] = {'url_id': project, 'canonical_id': canonical_project, 'registered': True}
for base in ['http://127.0.0.1:13500', 'http://192.168.178.10:13500']:
    url = base + '/studio/engineering?project=' + project
    with opener.open(url, timeout=15) as response:
        raw = response.read()
        assert response.status == 200 and b'<html' in raw.lower()
    report['http'].append({'url': url, 'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest()})
destination = Path(__file__).parent / ('live-delivery-' + sys.argv[1] + '.json')
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'path': str(destination), 'image_id': report['image_id'], 'http_checks': len(report['http'])}))
