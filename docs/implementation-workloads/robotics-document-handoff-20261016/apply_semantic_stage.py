"""Revision-guarded application of an already reviewed semantic stage."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
path = OUT / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
current = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in work['revision_after']}
assert current == work['revision_after'], 'Source drift'
work['revision_before'] = current
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
guard = subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py', '--workload', str(path), 'before-apply'], capture_output=True, text=True, encoding='utf-8')
assert guard.returncode == 0 and json.loads(guard.stdout)['allowed'], guard.stdout + guard.stderr
changed = []
for relative in current:
    data = (OUT / 'semantic-staged' / relative).read_bytes()
    target = ROOT / relative
    if data != target.read_bytes():
        target.write_bytes(data)
        changed.append(relative)
    (OUT / 'after' / relative).write_bytes(data)
work['revision_after'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in current}
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'allowed': True, 'changed': changed}))
