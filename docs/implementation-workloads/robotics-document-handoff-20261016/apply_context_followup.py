"""Guard and apply the prepared numeric/system-context repair only."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
path = OUT / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
owned = list(work['revision_before_initial_apply'])
current = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in owned}
assert current == work['revision_after'], 'Unexpected canonical source drift'
work.setdefault('revision_history', []).append({'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'revision_before': work['revision_before'], 'revision_after': current})
work['revision_before'] = current
work['repair']['root_cause'] += ' Numeric outline headings previously lost source identity during composition; overview coverage compared semantic chapter paths instead of the containing source system.'
proof = OUT / 'numbered-context-before-fix.json'
work['repair']['evidence'].append({'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()})
work['repair']['acceptance_criteria'] += ['Numeric profile identity survives section composition, including repeated labels and repeated ordinals.', 'Explicit overview coverage may reference another chapter of the same source system, never a different source system.']
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
guard = subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py', '--workload', str(path), 'before-apply'], capture_output=True, text=True, encoding='utf-8')
(OUT / 'context-before-apply-guard.json').write_text(guard.stdout, encoding='utf-8')
assert guard.returncode == 0 and json.loads(guard.stdout)['allowed'], guard.stdout + guard.stderr
changed = []
for relative in owned:
    staged = OUT / 'staged' / relative
    target = ROOT / relative
    data = staged.read_bytes()
    if data != target.read_bytes():
        target.write_bytes(data)
        changed.append(relative)
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    after.write_bytes(data)
work['files_changed'] = owned
work['revision_after'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in owned}
work['context_followup'] = {'status': 'APPLIED_FOR_VERIFICATION', 'changed': changed, 'full_release_not_started': True}
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(work['context_followup']))
