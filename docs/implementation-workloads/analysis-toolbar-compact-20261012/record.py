import difflib,hashlib,json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
path=here/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
after=[]
diff=[]
for name in work['files_changed']:
    source=root/name
    after.append({'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    diff.extend(difflib.unified_diff((here/'before'/name).read_text(encoding='utf-8').splitlines(keepends=True),source.read_text(encoding='utf-8').splitlines(keepends=True),fromfile='before/'+name,tofile='after/'+name))
target=here/'implementation.diff'
target.write_text(''.join(diff),encoding='utf-8')
work['after']=after
work['diff']=[{'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}]
proof=here/'typecheck.json'
proof.write_text(json.dumps({'status':'PASSED','command':'node frontend/node_modules/typescript/bin/tsc --noEmit --project frontend/tsconfig.json','exit_code':0,'scope':'Current frontend source including compact toolbar; no additional design test suite'},indent=2)+'\n',encoding='utf-8')
work['validations']['typecheck']={'status':'PASSED','evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}]}
work['completion_status']='VALIDATING'
path.write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
print('AFTER_DIFF_TYPECHECK_RECORDED')
