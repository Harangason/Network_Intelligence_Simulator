from pathlib import Path
import hashlib, json, shutil
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def evidence(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
w = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
for name in ['frontend/next.config.ts', 'frontend/src/features/workflow/ui/runtime-status.tsx']:
    source = ROOT / name
    target = HERE / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    w['revision_before'][name] = evidence(source)['sha256']
    w['before'].append(evidence(target))
    w['files_changed'].append(name)
# The first apply already happened; only these additional files are checked now.
remaining = dict(w)
remaining['revision_before'] = {name: w['revision_before'][name] for name in w['files_changed'][-2:]}
(HERE / 'provenance-apply.json').write_text(json.dumps(remaining, indent=2), encoding='utf-8')
(HERE / 'workload.json').write_text(json.dumps(w, indent=2), encoding='utf-8')
