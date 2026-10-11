from finish_structure_owners import *
import difflib

earliest = {}
ledger = OUT / 'before-index.json'
if ledger.is_file():
    for relative, evidence in json.loads(ledger.read_text()).items():
        earliest[relative] = None if evidence.get('absent') else Path(evidence['path'])
for listing in sorted(OUT.glob('*-files.json'), key=lambda p: p.stat().st_mtime):
    phase = listing.stem.removesuffix('-files')
    for relative in json.loads(listing.read_text()):
        if relative not in earliest:
            before = OUT / 'before' / phase / relative
            earliest[relative] = before if before.is_file() else None
before_index, after_index, patches = {}, {}, []
for relative, before in sorted(earliest.items()):
    actual = ROOT / relative
    before_index[relative] = {'path':str(before), 'sha256':hashlib.sha256(before.read_bytes()).hexdigest()} if before else {'absent':True}
    after_index[relative] = {'path':str(actual), 'sha256':hashlib.sha256(actual.read_bytes()).hexdigest()}
    previous = before.read_text(encoding='utf-8-sig').splitlines(keepends=True) if before else []
    current = actual.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    patches.extend(difflib.unified_diff(previous,current,fromfile='before/'+relative,tofile='after/'+relative))
(OUT / 'before-index.json').write_text(json.dumps(before_index,indent=2),encoding='utf-8')
(OUT / 'after-index.json').write_text(json.dumps(after_index,indent=2),encoding='utf-8')
(OUT / 'changes.patch').write_text(''.join(patches),encoding='utf-8')
print(json.dumps({'changed_files':len(earliest)}))
