from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
w=json.loads((HERE/'workload.json').read_text());n='frontend/src/app/studio/simulation/page.tsx';p=ROOT/n
b=HERE/'before'/n;b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(p.read_bytes())
w['files_changed'].append(n);w['revision_before'][n]=hashlib.sha256(p.read_bytes()).hexdigest();w['before'].append({'path':str(b),'sha256':w['revision_before'][n]})
(HERE/'workload.json').write_text(json.dumps(w,indent=2))
w['revision_before']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in w['files_changed']}
(HERE/'apply-secondary.json').write_text(json.dumps(w,indent=2))
s=json.loads((HERE/'stage.json').read_text());s['source_hashes']['src/app/studio/simulation/page.tsx']=w['revision_before'][n];s['before_source_hashes']['src/app/studio/simulation/page.tsx']=w['revision_before'][n]
(HERE/'stage.json').write_text(json.dumps(s,indent=2))
