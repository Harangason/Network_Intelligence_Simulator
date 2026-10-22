"""Deliver only the complete official PASS receipt for the native-tested image."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
receipt_path = ROOT / 'backend/test-output/release-gates/robotics-semantic-full-release-20261016/502e1b59f134/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
native = json.loads((OUT / 'native-attempt-2/native-verification.json').read_text(encoding='utf-8'))
runtime = json.loads((OUT / 'native-attempt-2/native-runtime-preparation.json').read_text(encoding='utf-8'))
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and native['status'] == 'PASSED'
assert receipt['image_id'] == runtime['image_id']
assert receipt['initial_source_sha256'] == runtime['source_sha256']
assert all(item['exit_code'] == 0 for item in receipt['checks'])
assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in work['revision_after'].items())
with (OUT / 'production-deploy.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, '-u', 'scripts/release-and-deploy.py', '--receipt', str(receipt_path)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
print(json.dumps({'exit_code': result.returncode, 'receipt': str(receipt_path), 'image_id': receipt['image_id']}), flush=True)
raise SystemExit(result.returncode)
