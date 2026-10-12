import difflib, hashlib, json
from pathlib import Path

work = Path(__file__).parent
workload = json.loads((work / 'workload.json').read_text(encoding='utf-8'))
root = Path(workload['repository'])
diffs = []
after = []
changed = []
for name in workload['revision_before']:
    source = root / name
    original = work / 'before' / name
    if source.read_bytes() == original.read_bytes():
        continue
    changed.append(name)
    target = work / 'after' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    after.append({'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    diffs.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True),
        source.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
diff = work / 'owned-changes.diff'
diff.write_text(''.join(diffs), encoding='utf-8')
workload.update(files_changed=changed, after=after, diff=[{'path': str(diff), 'sha256': hashlib.sha256(diff.read_bytes()).hexdigest()}], completion_status='VALIDATING')
(work / 'workload.json').write_text(json.dumps(workload, indent=2), encoding='utf-8')
print(json.dumps({'changed_files': len(changed), 'diff_lines': len(diffs)}))
