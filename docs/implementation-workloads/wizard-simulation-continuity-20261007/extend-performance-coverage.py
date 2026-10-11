import hashlib, json, shutil
from pathlib import Path
out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
name = 'backend/tests/test_bus_rate_planning.py'
if name not in work['files_inspected']:
    work['files_inspected'].append(name)
    before = out/'before'/name
    before.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root/name, before)
work['repair']['affected_files'].append(name)
work['revision_before'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
