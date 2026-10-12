import hashlib,json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
path=here/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
name='AGENTS.md'
target=here/'before'/name
assert not target.exists()
data=(root/name).read_bytes()
target.write_bytes(data)
work['before'].append({'path':str(target),'sha256':hashlib.sha256(data).hexdigest()})
work['files_changed'].append(name)
work['revision_before']={file:hashlib.sha256((root/file).read_bytes()).hexdigest() for file in work['files_changed']}
work['implementation_plan'].append('Record explicit human standing authorization for future audited unused fully archived FAIL-candidate cleanup without repeated questions; retain production, rollback, other receipt classifications and all-container checks.')
path.write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
print('RETENTION_RULE_BEFORE_EVIDENCE_RECORDED')
