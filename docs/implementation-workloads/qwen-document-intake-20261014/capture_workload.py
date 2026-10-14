"""Capture only this task's delta against its preserved before snapshots."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
root = work.parents[2]
state = json.loads((work / 'workload.json').read_text(encoding='utf-8-sig'))
paths = list(state['revision_before'])
if 'backend/nis/agent/orchestration/local_reasoner.py' in paths:
    paths.append('frontend/src/features/agent/lib/document-intake-response.test.mjs')
diff = []
before_evidence = []
after_evidence = []
missing = []
def evidence(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
for name in paths:
    target = root / name
    after = work / 'after' / name
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, after)
    after_evidence.append(evidence(after))
    before = work / 'before' / name
    if before.exists():
        before_evidence.append(evidence(before))
        old = before.read_text(encoding='utf-8')
    else:
        missing.append(name)
        old = ''
    diff.extend(difflib.unified_diff(old.splitlines(keepends=True), target.read_text(encoding='utf-8').splitlines(keepends=True),
                                   fromfile='before/' + name, tofile='after/' + name))
(work / 'before-absent.json').write_text(json.dumps(missing, indent=2), encoding='utf-8')
before_evidence.append(evidence(work / 'before-absent.json'))
(work / 'owned-changes.diff').write_text(''.join(diff), encoding='utf-8')
state.update(files_changed=paths, before=before_evidence, after=after_evidence, diff=[evidence(work / 'owned-changes.diff')],
             completion_status='VALIDATING', remaining_findings=['Full original-source Qwen and shared release/deployment are pending.'])
(work / 'workload.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
