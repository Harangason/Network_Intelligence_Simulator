import hashlib, json
from pathlib import Path
out = Path(__file__).parent.resolve()
root = out.parents[2]
assert out.is_relative_to(root)
names = ['performance-browser.json','performance-browser.log','performance-browser-cleanup.json',
    'performance-app-container.log','performance-db-container.log','performance-app-state.json','performance-db-state.json','performance-browser']
moved = {}
for name in names:
    source = (out/name).resolve()
    target = (out/name.replace('performance-', 'performance-first-',1)).resolve()
    assert source.parent == out and target.parent == out
    assert not target.exists(), target
    source.rename(target)
    moved[str(source)] = str(target)
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
for repair in [work['repair'],*work.get('repair_history',[])]:
    for ref in repair.get('evidence',[]):
        if ref['path'] in moved:
            ref['path'] = moved[ref['path']]
            assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() == ref['sha256']
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('First performance browser failure and container evidence preserved unchanged.')
