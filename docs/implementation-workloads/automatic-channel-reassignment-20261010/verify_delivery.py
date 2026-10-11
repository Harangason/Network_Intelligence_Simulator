"""Capture and verify the exact delivered image, health and unchanged project state."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--capture', action='store_true')
parser.add_argument('--receipt', type=Path)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
root = folder.parents[2]
project = '20261009072206008-4bb505f1'
def get(url, scoped=False):
    with urlopen(Request(url, headers={'X-Project-ID': project} if scoped else {}), timeout=45) as response:
        body = response.read()
        return response.status, json.loads(body) if 'json' in response.headers.get('Content-Type', '') else None
baseline = folder / 'production-workflow-predeploy.json'
if args.capture:
    _, state = get('http://127.0.0.1:13500/api/engineering/workflow', True)
    baseline.write_text(json.dumps(state), encoding='utf-8')
    print(json.dumps({'baseline': str(baseline), 'captured_at': datetime.now(timezone.utc).isoformat()}))
    raise SystemExit(0)
assert args.receipt and baseline.exists()
receipt = json.loads(args.receipt.read_text())
assert receipt['status'] == 'PASS'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']
checks = {'tested_image': receipt['image_id'], 'running_image': running, 'receipt': str(args.receipt)}
for base in ('http://127.0.0.1:13500', 'http://192.168.178.10:13500'):
    status, ready = get(base + '/api/ready')
    assert status == 200 and ready['status'] == 'ready'
    checks[base] = {'ready': ready}
    status, published_build = get(base + '/api/build-info')
    assert status == 200 and published_build['source_sha256'] == receipt['release']['source_sha256']
    checks[base]['source_sha256'] = published_build['source_sha256']
    for path in (f'/studio?mode=network&project={project}', f'/studio/engineering?project={project}'):
        status, _ = get(base + path)
        assert status == 200
        checks[base][path] = status
_, build = get('http://127.0.0.1:13500/api/build-info')
assert build['source_sha256'] == receipt['release']['source_sha256'] == receipt['initial_source_sha256']
checks['build'] = build
_, workflow = get('http://127.0.0.1:13500/api/engineering/workflow', True)
before = json.loads(baseline.read_text())
checks['project_unchanged_by_deployment'] = {key: before[key] == workflow[key] for key in ('parameters', 'topology', 'edit_tokens', 'versions', 'statuses')}
assert all(checks['project_unchanged_by_deployment'].values()), checks['project_unchanged_by_deployment']
(folder / 'production-workflow-after-deploy.json').write_text(json.dumps(workflow), encoding='utf-8')
(folder / 'production-delivery-verification.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
print(json.dumps({'image_id': running, 'source_sha256': build['source_sha256'], 'local_and_lan_ready': True,
                  'project_unchanged_by_deployment': True}))
