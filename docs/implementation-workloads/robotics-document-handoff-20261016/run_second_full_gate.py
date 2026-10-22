"""Full required gate only after actual native acceptance and its cleanup."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
NATIVE = OUT / 'native-attempt-2'
runtime = json.loads((NATIVE / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
assert json.loads((NATIVE / 'native-verification.json').read_text(encoding='utf-8'))['status'] == 'PASSED'
assert json.loads((NATIVE / 'native-classification-review.json').read_text(encoding='utf-8'))['status'] == 'PASSED'
assert json.loads((NATIVE / 'native-tool-audit.json').read_text(encoding='utf-8'))['status'] == 'PASSED'
cleanup = json.loads((NATIVE / 'native-stack-cleanup.json').read_text(encoding='utf-8'))
assert cleanup['status'] == 'COMPLETED_NATIVE_STACK_REMOVED' and cleanup['native_result'] == 'PASSED'
assert cleanup['image_retained'] == runtime['image_id'] and cleanup['currently_active_native_work'] is False
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in work['revision_after'].items())
work['verification_phase'] = 'SECOND_NATIVE_PASSED_FULL_RELEASE_RUNNING'
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
directory = ROOT / 'backend/test-output/release-gates/robotics-semantic-full-release-20261016'
assert not directory.exists(), 'Preserve all existing gate attempts'
with (OUT / 'semantic-full-release.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, '-u', 'scripts/run-release-gate.py', '--image', runtime['image_id'], '--output', str(directory)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
paths = list(directory.glob('*/receipt.json'))
assert len(paths) == 1
receipt = json.loads(paths[0].read_text(encoding='utf-8'))
assert receipt['image_id'] == runtime['image_id'] and receipt['initial_source_sha256'] == runtime['source_sha256']
print(json.dumps({'status': receipt['status'], 'receipt': str(paths[0]), 'image_id': receipt['image_id']}), flush=True)
raise SystemExit(result.returncode)
