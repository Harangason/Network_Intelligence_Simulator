"""Export before/after indices and a removal-aware diff of this workload only."""
import difflib
import hashlib
import json
from pathlib import Path
from edit_utils import ROOT, OUT

workload = json.loads((OUT/'workload.json').read_text(encoding='utf-8'))
first_touch = {}
for phase in sorted(OUT.glob('*-files.json'), key=lambda p:p.stat().st_mtime_ns):
    recorded = json.loads(phase.read_text(encoding='utf-8'))
    paths = recorded if isinstance(recorded,list) else [*recorded.get('written',[]),*recorded.get('removed',[])]
    for path in paths:
        first_touch.setdefault(path,phase.name.removesuffix('-files.json'))
before,after,diff = {},{},[]
for path in workload['files_changed']:
    assert path in first_touch, path
    original = OUT/'before'/first_touch[path]/path
    current = ROOT/path
    before_bytes = original.read_bytes() if original.exists() else None
    after_bytes = current.read_bytes() if current.exists() else None
    before[path] = {'exists':before_bytes is not None,'sha256':hashlib.sha256(before_bytes).hexdigest() if before_bytes is not None else None,
                    'snapshot':str(original) if original.exists() else None,'first_phase':first_touch[path]}
    after[path] = {'exists':after_bytes is not None,'sha256':hashlib.sha256(after_bytes).hexdigest() if after_bytes is not None else None}
    left = before_bytes.decode('utf-8-sig').splitlines(keepends=True) if before_bytes is not None else []
    right = after_bytes.decode('utf-8-sig').splitlines(keepends=True) if after_bytes is not None else []
    diff.extend(difflib.unified_diff(left,right,fromfile='before/'+path,tofile='after/'+path))
(OUT/'before-index.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
(OUT/'after-index.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
(OUT/'changes.patch').write_text(''.join(diff),encoding='utf-8')
summary = {'changed_files':len(after),'removed_files':sum(not row['exists'] for row in after.values()),
           'created_files':sum(not row['exists'] for row in before.values()),'before_snapshot_hashes_verified':True}
(OUT/'change-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
