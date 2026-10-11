"""Read-only delivery checks for the reported project and exact tested image."""
import argparse
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
project = '20261009072206008-4bb505f1'
receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS'
config = json.loads(Path('config/networkis.resources.json').read_text(encoding='utf-8-sig'))
running = subprocess.check_output([config['paths']['docker_cli'], 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']

def get(url, project_header=False):
    request = Request(url, headers={'X-Project-ID': project} if project_header else {})
    with urlopen(request, timeout=45) as response:
        data = response.read()
        return response.status, json.loads(data) if 'json' in response.headers.get('Content-Type', '') else None

checks = {'tested_image': receipt['image_id'], 'running_image': running}
for base in ['http://127.0.0.1:13500', 'http://192.168.178.10:13500']:
    status, ready = get(base + '/api/ready')
    assert status == 200
    checks[base] = {'ready': ready}
    for path in [f'/studio?mode=network&project={project}', f'/studio/simulation?project={project}']:
        status, _ = get(base + path)
        assert status == 200
        checks[base][path] = status
_, build = get('http://127.0.0.1:13500/api/build-info')
checks['build'] = build
_, workflow = get('http://127.0.0.1:13500/api/engineering/workflow', True)
baseline = root / 'production-workflow-predeploy.json'
assert baseline.is_file(), 'Capture the latest production state immediately before deployment.'
before = json.loads(baseline.read_text(encoding='utf-8-sig'))
checks['baseline'] = str(baseline)
checks['project_unchanged'] = {key: before[key] == workflow[key] for key in ['parameters', 'topology', 'edit_tokens', 'versions', 'statuses']}
assert all(checks['project_unchanged'].values()), checks['project_unchanged']
(root / 'production-workflow-after.json').write_text(json.dumps(workflow, ensure_ascii=False), encoding='utf-8')
(root / 'production-verification.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(checks, ensure_ascii=False))
