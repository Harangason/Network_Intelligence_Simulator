"""Read-only verification of exact tested production identity and local/LAN readiness."""
import argparse, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument('receipt', type=Path)
args = parser.parse_args()
here = Path(__file__).parent
root = here.parents[2]
receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS' and receipt.get('development_only') is not True
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']
def read(url):
    with urlopen(url, timeout=15) as response:
        return json.load(response)
checks = {}
for label, base in [('local', 'http://127.0.0.1:13500'), ('lan_vpn', 'http://192.168.178.10:13500')]:
    ready = read(base + '/api/ready')
    build = read(base + '/api/build-info')
    assert ready['status'] == 'ready'
    assert build['source_sha256'] == receipt['release']['source_sha256']
    checks[label] = {'base_url': base, 'ready': ready, 'build': build}
proof = {'status': 'PASSED', 'captured_at': datetime.now(timezone.utc).isoformat(),
    'receipt': str(args.receipt.resolve()), 'receipt_sha256': hashlib.sha256(args.receipt.read_bytes()).hexdigest(),
    'expected_image': receipt['image_id'], 'running_image': running, 'checks': checks,
    'scope': 'Read-only exact-image identity, build source, readiness on local and LAN/VPN. No product database test writes.'}
(here / 'production-verification.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps({'status': proof['status'], 'image': running, 'source': receipt['release']['source_sha256'], 'local': True, 'lan_vpn': True}))
