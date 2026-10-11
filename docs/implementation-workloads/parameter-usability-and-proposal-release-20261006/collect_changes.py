"""Record this repair against its preserved starting point, not against Git HEAD."""
import difflib
import hashlib
import json
import shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
work = json.loads((out / 'workload.json').read_text(encoding='utf-8'))

def reference(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

changed, before, after, diff = [], [], [], []
for name in work['files_inspected']:
    initial, current = out / 'before' / name, root / name
    if initial.read_bytes() == current.read_bytes():
        continue
    changed.append(name)
    copied = out / 'after' / name
    copied.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(current, copied)
    patch = out / 'diff' / (name + '.patch')
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text(''.join(difflib.unified_diff(
        initial.read_text(encoding='utf-8').splitlines(keepends=True),
        current.read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='before/' + name, tofile='after/' + name)), encoding='utf-8')
    before.append(reference(initial))
    after.append(reference(copied))
    diff.append(reference(patch))
work.update(files_changed=changed, before=before, after=after, diff=diff,
            completion_status='VALIDATING')
(out / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'changed_files': len(changed), 'files': changed}))
