"""Close only the evidenced dead gate's stale RUNNING state; never create a PASS."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

here = Path(__file__).resolve().parent
root = here.parents[2]
path = root / 'backend/test-output/release-gates/delivery-6ca4ab5fb4eb/bb493012fb1c/receipt.json'
review = json.loads((here / 'interrupted-release-review.json').read_text(encoding='utf-8'))
original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
assert original_hash == review['previous_receipt_sha256']
receipt = json.loads(path.read_text(encoding='utf-8'))
assert receipt['status'] == 'RUNNING' and receipt['gate_pid'] == 41116
assert subprocess.run(['powershell', '-NoProfile', '-Command',
    'if (Get-Process -Id 41116 -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }']).returncode == 0
original = here / 'interrupted-receipt-original.json'
assert not original.exists()
shutil.copyfile(path, original)
receipt.update(status='FAIL', error='Interrupted gate: process 41116 no longer exists; browser log ends after case 106. No complete browser/HTTP PASS was produced.',
    interrupted=True, state_finalized_at=datetime.now(timezone.utc).isoformat(),
    state_finalization_evidence=str(here / 'interrupted-release-review.json'))
path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
evidence = {'status': 'STALE_INTERRUPTED_STATE_CLOSED_AS_FAIL', 'gate_pid_absent': True,
    'original_receipt': str(original), 'original_sha256': original_hash,
    'closed_receipt': str(path), 'closed_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'checks_preserved': receipt['checks'], 'no_pass_created': True}
(here / 'interrupted-state-finalization.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps({'status': evidence['status'], 'no_pass_created': True}))
