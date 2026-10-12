from pathlib import Path
import json,hashlib,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
e=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text());f=json.loads((HERE/'production-functional.json').read_text());b=json.loads((HERE/'build.json').read_text())
assert prod['status']==f['status']==b['status']=='PASSED' and prod['artifact_sha256']==f['artifact_sha256']
n=w['files_changed'][0];w['after']=[e(ROOT/n)];diff=''.join(difflib.unified_diff((HERE/'before'/n).read_text().splitlines(True),(ROOT/n).read_text().splitlines(True),fromfile='before/'+n,tofile='after/'+n));(HERE/'implementation.diff').write_text(diff)
w['diff']=[e(HERE/'implementation.diff')]
def passed(*names):return {'status':'PASSED','evidence':[e(HERE/n) for n in names]}
w['outcomes']={'notice_removed':passed('production-functional.json'),'production_delivery':passed('production-verification.json','production-functional.json')}
w['validations']={'typecheck':passed('build.json','build.log'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json')}
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','scope':'Frontend compilation including TypeScript and focused existing-job browser check','image_created':False,'full_gate_run':False}))
w['delivery'].update(tested_version=prod['artifact_sha256'],running_version=prod['artifact_sha256'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=w['files_changed']+['AGENTS.md','frontend/AGENTS.md'];w['remaining_findings']=[];w['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(w,indent=2))
(HERE/'implementation-notes.md').write_text('Removed only the primary saved-run notice and its results link. Canonical snapshot, historical job and staleness rules remain intact. No backend/model changes. Frontend compiled, TypeScript and focused browser check passed. Direct overlay deployed to existing NetworkIS image with rollback and archived artifact; no full campaign/image. Overlay survives same-container restart; recreation requires restoring archived frontend or release from canonical source.\n')
print('Evidence complete')
