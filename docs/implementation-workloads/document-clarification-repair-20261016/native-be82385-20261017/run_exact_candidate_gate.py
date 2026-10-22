"""Start the official full gate only after both native checks and owned cleanup."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
FOLLOWUP = OUT.parent/'followup-communication-actions'
runtime = json.loads((OUT/'native-runtime-preparation.json').read_text(encoding='utf-8'))
freeze = json.loads((FOLLOWUP/'source-freeze.json').read_text(encoding='utf-8'))
cleanup = json.loads((OUT/'native-stack-cleanup.json').read_text(encoding='utf-8'))
assert cleanup['status'] == 'COMPLETED_NATIVE_STACK_REMOVED'
assert cleanup['image_retained'] == runtime['image_id']
assert cleanup['production_unchanged'] is True
for folder in [OUT, ROOT/'docs/implementation-workloads/robotics-document-handoff-20261016/joint-retest-20261017']:
    assert json.loads((folder/'native-verification.json').read_text(encoding='utf-8'))['status'] == 'PASSED'
    audit = json.loads((folder/'native-tool-audit.json').read_text(encoding='utf-8'))
    assert audit['status'] == 'PASSED' and audit['image_id'] == runtime['image_id']
for path, expected in freeze['files'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
spec = importlib.util.spec_from_file_location('joint_gate_build_identity',ROOT/'scripts/write-build-info.py')
info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(info)
manifest = info.build_manifest()
assert manifest['source_sha256'] == runtime['source_sha256'] == freeze['source_sha256']
assert manifest['commit_id'] == freeze['commit_id']
output = ROOT/'backend/test-output/release-gates/communication-actions-full-release-20261017'
assert not output.exists(), 'Inspect and resume the existing gate; never start a duplicate.'
record = {'status':'SOURCE_MATCHES_FREEZE_BEFORE_FULL_GATE','source_sha256':manifest['source_sha256'],
          'commit_id':manifest['commit_id'],'image_id':runtime['image_id'],'new_build_requested':False}
(FOLLOWUP/'source-check-before-full-gate.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
command = [sys.executable,str(ROOT/'scripts/run-release-gate.py'),'--image',runtime['image_id'],'--output',str(output)]
with (FOLLOWUP/'full-release.log').open('w',encoding='utf-8') as log:
    result = subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
receipts = list(output.glob('*/receipt.json'))
assert len(receipts) == 1, receipts
receipt = json.loads(receipts[0].read_text(encoding='utf-8'))
if result.returncode == 0:
    assert receipt['status'] == 'PASS' and receipt['image_id'] == runtime['image_id']
    assert receipt['release']['source_sha256'] == freeze['source_sha256']
    (FOLLOWUP/'full-release-pass-receipt.json').write_bytes(receipts[0].read_bytes())
print(json.dumps({'gate_exit_code':result.returncode,'status':receipt['status'],'receipt':str(receipts[0]),
                  'image_id':receipt.get('image_id'),'production_deployed_by_this_command':False}),flush=True)
raise SystemExit(result.returncode)
