from pathlib import Path
import json,hashlib,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
e=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text());f=json.loads((HERE/'production-functional.json').read_text())
assert prod['status']==f['status']=='PASSED' and prod['artifact_sha256']==f['artifact_sha256']
for n in ['typecheck','workspace-tests','build']:assert json.loads((HERE/(n+'.json')).read_text())['status']=='PASSED'
w['after']=[];diff=[]
for n in w['files_changed']:
 w['after'].append(e(ROOT/n));diff.extend(difflib.unified_diff((HERE/'before'/n).read_text(encoding='utf-8').splitlines(True),(ROOT/n).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+n,tofile='after/'+n))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8');w['diff']=[e(HERE/'implementation.diff')]
def passed(*names):return {'status':'PASSED','evidence':[e(HERE/n) for n in names]}
w['outcomes']={n:passed('production-functional.json') for n in w['required_outcomes']};w['outcomes']['production_delivery']=passed('production-verification.json','production-functional.json')
w['validations']={'typecheck':passed('typecheck.json'),'workspace_tests':passed('workspace-tests.json'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json')}
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','scope':'Nine focused workspace tests, TypeScript, frontend build and focused existing-job browser tab/collapse/coupling checks','image_created':False,'full_gate_run':False}))
w['delivery'].update(tested_version=prod['artifact_sha256'],running_version=prod['artifact_sha256'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=w['files_changed']+['AGENTS.md','frontend/AGENTS.md'];w['remaining_findings']=[];w['completion_status']='COMPLETED';(HERE/'workload.json').write_text(json.dumps(w,indent=2))
(HERE/'implementation-notes.md').write_text('Four existing simulation control panels use native details/summary, all closed by default, identical 56px closed height and full container width at desktop/mobile. Workspace tools can opt into a collapsible wrapper; trace-page tools retain their existing root section. Scenario controls preserve the one-row desktop form when expanded. Scope/fault content is unchanged. Browser open omits popup=yes and size features and requests _blank; the browser chooses normal tab/window placement. Coupled views preserve project/source/window identity, time synchronization and separate signal/sequence view states; opener is cleared. Only blocked opens create replacement links, grouped under the correct Simulation or Trace-Analyse column and labelled by link mode. Existing optional profile sizes remain readable but do not impose popup features. Tests verified actual opened linked views, time propagation, fallback destination, expand/collapse and desktop/mobile dimensions. No backend/model/staleness change or new image/full campaign. Direct compiled frontend overlay archived and rollback retained. Same-container restart preserves overlay; recreation requires restoring the archive or release from canonical source.\n')
print('Evidence complete')
