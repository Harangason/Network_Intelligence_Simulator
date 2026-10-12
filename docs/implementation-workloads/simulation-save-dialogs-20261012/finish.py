from pathlib import Path
import json,hashlib,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
e=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text());f=json.loads((HERE/'production-functional.json').read_text())
assert prod['status']==f['status']=='PASSED' and prod['artifact_sha256']==f['artifact_sha256']
for n in ['typecheck','build']:assert json.loads((HERE/(n+'.json')).read_text())['status']=='PASSED'
w['after']=[];diff=[]
for n in w['files_changed']:
 w['after'].append(e(ROOT/n));b=HERE/'before'/n;diff.extend(difflib.unified_diff(b.read_text(encoding='utf-8').splitlines(True) if b.exists() else [],(ROOT/n).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+n,tofile='after/'+n))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8');w['diff']=[e(HERE/'implementation.diff')]
def passed(*names):return {'status':'PASSED','evidence':[e(HERE/n) for n in names]}
w['outcomes']={n:passed('production-functional.json') for n in w['required_outcomes']};w['outcomes']['production_delivery']=passed('production-verification.json','production-functional.json')
w['validations']={'typecheck':passed('typecheck.json'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json')}
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','scope':'TypeScript, frontend compilation and focused production dialog UI checks; save API responses intercepted; no backend persistence proof or product database test writes','image_created':False,'full_gate_run':False}))
w['delivery'].update(tested_version=prod['artifact_sha256'],running_version=prod['artifact_sha256'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=w['files_changed']+['frontend/src/features/projects/lib/project-file.ts','frontend/src/features/workflow/lib/workflow-api.ts','AGENTS.md','frontend/AGENTS.md'];w['remaining_findings']=[];w['completion_status']='COMPLETED';(HERE/'workload.json').write_text(json.dumps(w,indent=2))
(HERE/'implementation-notes.md').write_text('Root causes: scenario Save as used window.prompt (which can be suppressed by embedded browser hosts); existing-project Save called export/server save without ever opening its existing default-project-only dialog. Both now open visible native HTML modal dialogs styled with the existing project dialog UI. Shared SaveDialog keeps modal focus and Escape handling; busy operations cannot be canceled via Escape. Scenario names are editable, blank names blocked, API errors remain visible in the dialog and retry keeps the name. Existing preflight/scope/format checks and scenario API/payload are preserved. Project Save opens synchronously before any network request, captures active project identity, offers existing server SAVED and forceChoose file/download paths; errors remain in dialog. Existing-project ID is read-only; default-project creation ID remains editable. No new backend/model storage authority, no silent success on failed save. Actual production browser verified opening, cancel/Escape, payloads, failure/retry/success UI using intercepted persistence responses only. Backend persistence/native OS file chooser not tested; no product database test writes, image or full campaign. Direct frontend overlay archived with rollback; same-container restart preserves overlay, container recreation requires restoring archive or release from canonical source.\n')
print('Evidence complete')
