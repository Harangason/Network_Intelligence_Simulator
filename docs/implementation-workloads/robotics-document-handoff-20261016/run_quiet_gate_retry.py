"""One complete unchanged-image retest after native acceptance and first gate.

No limit changes, source changes, partial receipt reuse or repeated retry loop.
"""
from pathlib import Path
import json
import subprocess
import sys
import time

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
original = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016/911347665bea/receipt.json'
while True:
    try:
        first = json.loads(original.read_text(encoding='utf-8'))
        native = json.loads((OUT / 'native-verification.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        time.sleep(10)
        continue
    if native['status'] != 'PASSED':
        raise RuntimeError('Native acceptance failed; unchanged-image retest is not authorized by this plan.')
    if first['status'] == 'PASS':
        raise RuntimeError('Original full gate passed; a duplicate full retest is unnecessary.')
    if first['status'] == 'FAIL':
        break
    time.sleep(10)
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
assert first['image_id'] == runtime['image_id']
assert first['initial_source_sha256'] == runtime['source_sha256']
output = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016-retest'
assert not output.exists(), 'This plan permits exactly one controlled complete retest.'
with (OUT / 'full-release-retest-process.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, '-u', str(ROOT / 'scripts/run-release-gate.py'),
                             '--image', runtime['image_id'], '--output', str(output)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
print({'complete_unchanged_image_retest_exit_code': result.returncode})
raise SystemExit(result.returncode)
