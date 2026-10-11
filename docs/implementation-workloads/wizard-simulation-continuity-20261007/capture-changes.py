import difflib, hashlib, json, shutil
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
def evidence(file):
    return {'path':str(file.resolve()), 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
changes, before_refs, after_refs, differences = [], [], [], []
for relative in work['files_inspected']:
    source, before = root/relative, out/'before'/relative
    if source.read_bytes() == before.read_bytes():
        continue
    after = out/'after'/relative
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, after)
    changes.append(relative)
    before_refs.append(evidence(before))
    after_refs.append(evidence(after))
    differences.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),
        source.read_text(encoding='utf-8').splitlines(True), fromfile='before/'+relative, tofile='after/'+relative))
diff = out/'change.diff'
diff.write_text(''.join(differences),encoding='utf-8')
work.update(files_changed=changes, before=before_refs, after=after_refs, diff=[evidence(diff)],
    completion_status='VALIDATING', remaining_findings=work.get('remaining_findings', []))
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print(json.dumps({'changed_files':len(changes), 'diff':str(diff)}))
