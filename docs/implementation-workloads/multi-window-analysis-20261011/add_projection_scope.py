from pathlib import Path
import json, hashlib
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
path=HERE/'workload.json'
w=json.loads(path.read_text())
for name in ['backend/nis/traces/trace_sessions.py','frontend/src/app/trace-analysis/page.tsx']:
    if name in w['revision_before']: continue
    source=ROOT/name; before=HERE/'before'/name
    before.parent.mkdir(parents=True,exist_ok=True)
    before.write_bytes(source.read_bytes())
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    w['before'].append({'path':str(before),'sha256':digest})
    w['revision_before'][name]=digest
path.write_text(json.dumps(w,indent=2)+'\n')
