"""Prepare native acceptance as soon as this gate's exact image is ready."""
from pathlib import Path
import json
import subprocess
import sys
import time

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
receipt_path = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016/911347665bea/receipt.json'
deadline = time.monotonic() + 5400
while time.monotonic() < deadline:
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        time.sleep(5)
        continue
    if receipt.get('status') == 'FAIL':
        raise RuntimeError('Release gate failed; no native acceptance stack will be prepared.')
    if receipt.get('image_id') and any(c['name'] == 'production-build' and c['exit_code'] == 0 for c in receipt.get('checks', [])):
        break
    time.sleep(10)
else:
    raise RuntimeError('Candidate preparation deadline exceeded.')
with (OUT / 'native-preparation-process.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, str(OUT / 'prepare_native_acceptance.py'), '--candidate-receipt', str(receipt_path)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
print({'native_preparation_exit_code': result.returncode})
raise SystemExit(result.returncode)
