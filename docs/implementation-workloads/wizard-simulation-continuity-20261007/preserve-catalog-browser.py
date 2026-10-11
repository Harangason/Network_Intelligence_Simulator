import hashlib
import json
import re
import sys
from pathlib import Path

out = Path(__file__).parent.resolve()
prefix = sys.argv[1]
assert re.fullmatch(r'[a-z]+(?:-[a-z]+)*', prefix)
names = ['catalog-browser.json', 'catalog-browser.log', 'catalog-browser-cleanup.json',
         'catalog-app-container.log', 'catalog-db-container.log', 'catalog-app-state.json',
         'catalog-db-state.json', 'catalog-browser-runner.log', 'catalog-browser', 'catalog-browser-temp']
moved = {}
for name in names:
    source = (out / name).resolve()
    target = (out / (prefix + '-' + name)).resolve()
    assert source.parent == out and target.parent == out
    assert not target.exists(), target
    if source.exists():
        source.rename(target)
        moved[str(source)] = str(target)
path = out / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
for repair in [work['repair'], *work.get('repair_history', [])]:
    for ref in repair.get('evidence', []):
        for source, target in moved.items():
            original = Path(ref['path'])
            if original.is_relative_to(Path(source)):
                ref['path'] = str(Path(target)/original.relative_to(Path(source)))
                assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() == ref['sha256']
                break
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Completed browser results and cleanup retained under ' + prefix)
