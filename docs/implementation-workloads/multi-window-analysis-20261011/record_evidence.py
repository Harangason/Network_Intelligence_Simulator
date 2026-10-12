"""Record verified targeted checks without claiming release or delivery."""
from pathlib import Path
import json, hashlib, difflib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
path=HERE/'workload.json'; work=json.loads(path.read_text())
review=HERE/'failed-candidate-storage-review.json'
storage=json.loads(review.read_text())
storage['reason']='This unused candidate has a FAIL receipt. Its complete recoverable archive and original FAIL evidence are verified for a scoped retention exception because a new candidate is blocked by the 100-image budget. This is not a production PASS or feature-delivery equivalence claim.'
review.write_text(json.dumps(storage,indent=2)+'\n')
after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in work['revision_before'] if (ROOT/name).is_file()}
(HERE/'after-hashes.json').write_text(json.dumps(after,indent=2)+'\n')
original={str(Path(item['path']).relative_to(HERE/'before')).replace('\\','/'):Path(item['path']) for item in work['before'] if Path(item['path']).is_relative_to(HERE/'before')}
original['frontend/src/app/studio/simulation/page.tsx']=HERE/'before-page.tsx'
diff=[]
for name in after:
    before=original.get(name)
    left=before.read_text(encoding='utf-8').splitlines(keepends=True) if before else []
    right=(ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
    diff.extend(difflib.unified_diff(left,right,fromfile='before/'+name,tofile='after/'+name))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8')
work['files_changed']=list(after)
work['completion_status']='IMPLEMENTING'
path.write_text(json.dumps(work,indent=2)+'\n')
