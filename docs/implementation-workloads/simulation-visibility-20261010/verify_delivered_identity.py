"""Read-only verification of the exact tested image, local and LAN readiness."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('release_storage', ROOT / 'scripts/release_storage.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.complete_pass(receipt)
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']
surfaces = {}
for base in ('http://127.0.0.1:13500', 'http://192.168.178.10:13500'):
    with urlopen(base + '/api/ready', timeout=20) as response:
        ready = json.load(response)
    with urlopen(base + '/api/build-info', timeout=20) as response:
        build = json.load(response)
    assert ready['status'] == 'ready'
    assert build['source_sha256'] == receipt['initial_source_sha256']
    surfaces[base] = {'ready': ready, 'build': build}
report = {'status': 'VERIFIED', 'image_id': running, 'receipt': str(args.receipt.resolve()), 'surfaces': surfaces}
(HERE / 'production-identity-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'image_id': running, 'surfaces': list(surfaces)}))
