"""Apply exactly the reviewed delta after the peer's release handoff."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
handoff = json.loads((OUT / 'source-handoff.json').read_text(encoding='utf-8'))
assert handoff['status'] == 'RELEASED_BY_PEER' and handoff['production_identity_verified'] is True
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
guard = subprocess.run([sys.executable,
    'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py',
    '--workload', str(work_path), 'before-apply'], capture_output=True, text=True, encoding='utf-8')
(OUT / 'before-apply-guard.json').write_text(guard.stdout, encoding='utf-8')
assert guard.returncode == 0 and json.loads(guard.stdout)['allowed'], guard.stdout + guard.stderr
changed = []
for relative in work['revision_before']:
    target = (ROOT / relative).resolve()
    staged = (OUT / 'staged' / relative).resolve()
    assert target.is_relative_to(ROOT) and staged.is_relative_to(OUT / 'staged')
    assert staged.is_file(), relative
    data = staged.read_bytes()
    if target.is_file() and target.read_bytes() == data:
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    after.write_bytes(data)
    changed.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
work['status'] = work['completion_status'] = 'IMPLEMENTING'
work['files_changed'] = [row['path'] for row in changed]
work['revision_after'] = {row['path']: row['sha256'] for row in changed}
work['applied_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'apply-result.json').write_text(json.dumps({'status': 'APPLIED_FOR_VERIFICATION',
    'files': changed, 'at_utc': work['applied_at_utc'], 'source_handoff': handoff}, indent=2), encoding='utf-8')
print(json.dumps({'changed_files': len(changed), 'status': 'APPLIED_FOR_VERIFICATION'}))
