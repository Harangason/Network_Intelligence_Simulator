import hashlib,json
from pathlib import Path
out=Path(__file__).parent.resolve();path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'));old=out/'catalog-browser';new=out/'before-sizing-only-catalog-browser'
for repair in [work['repair'],*work.get('repair_history',[])]:
    for ref in repair.get('evidence',[]):
        original=Path(ref['path'])
        if original.is_relative_to(old):
            target=new/original.relative_to(old)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==ref['sha256']
            ref['path']=str(target)
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Nested failure evidence retained with verified identical hashes.')
