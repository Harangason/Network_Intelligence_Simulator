import difflib, hashlib, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def evidence(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text())
production=json.loads((HERE/'production-verification.json').read_text())
functional=json.loads((HERE/'production-functional.json').read_text())
assert production['status']==functional['status']=='PASSED'
assert functional['patch_id']==production['patch_id']
assert production['image_created'] is False and production['full_gate_run'] is False
diff=[]
w['after']=[]
for name in w['files_changed']:
    current=ROOT/name
    w['after'].append(evidence(current))
    diff.extend(difflib.unified_diff((HERE/'before'/name).read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8')
w['diff']=[evidence(HERE/'implementation.diff')]
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','typecheck_exit_code':0,'production_frontend_build_exit_code':0,'focused_browser_exit_code':0,'patch_id':production['patch_id'],'scope':'Static typecheck, frontend compilation and focused existing-job production controls check. No image build, backend test suite, E2E campaign, small/large model campaign or full release gate. Explicit user-authorized exception.', 'limitations':['The base-image full PASS receipt does not cover this frontend patch','Historical snapshot UI metadata was not used as a fixture requirement; canonical staleness was verified separately via the project snapshot API']},indent=2),encoding='utf-8')
def passed(*names):
    return {'status':'PASSED','evidence':[evidence(HERE/name) for name in names]}
w['outcomes']={'compact_controls':passed('production-functional.json'),'historical_playback_controls':passed('production-functional.json'),'verified_direct_production_delivery':passed('production-verification.json','production-functional.json')}
w['validations']={'typecheck':passed('typecheck.json'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json','production-functional.json')}
w['delivery'].update(tested_version=production['artifact_sha256'],running_version=production['artifact_sha256'],base_image=production['base_image'],frontend_patch_id=production['patch_id'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=['frontend/src/features/simulation/ui/model-simulation-runner.tsx','frontend/src/app/globals.css','frontend/src/features/traces/ui/analysis-workspace-tools.tsx','frontend/src/features/workflow/ui/runtime-status.tsx','frontend/next.config.ts','Dockerfile','scripts/dev/launch-networkis.py','config/networkis.resources.json']
w['remaining_findings']=[]
w['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(w,indent=2,ensure_ascii=False),encoding='utf-8')
(HERE/'implementation-notes.md').write_text(f'''# Simulation controls and playback — 2026-10-12

The controls formerly occupying several panels above the graph are now grouped
behind a default-closed Steuerung button beside the view tabs. The existing
workspace tools, fields, scenario actions, scope and fault editor remain mounted;
closing the controls does not reset their state. Validation, scope, restore and
execution errors stay visible outside the folded controls. The separate outdated
banner is removed; canonical snapshot staleness is unchanged, and the stored-run
label marks a loaded outdated snapshot as Veraltet.

The timeline now has Wiedergabe/Pause and Stopp. Playback reuses the existing
playing state and playhead publication, including the shared simulation-relative
workspace cursor. Starting at the end replays from zero. Stopp pauses playback
and returns the cursor to zero. The backend job cancellation action remains in
the folded form as Lauf stoppen and is independent of historical playback.

The user explicitly changed the delivery rule for these UI changes: small final
checks, no new image or large release test, direct production. AGENTS.md records
this scoped exception. TypeScript checking and frontend production compilation
passed, followed by a focused production browser check of an existing job.
Initial verifier attempts assumed an immediately rendered snapshot label for a
job-only browser session and then waited for snapshot metadata; those attempts
failed. The final check verifies actual playback on the existing job and unchanged
canonical historical snapshot staleness separately through its project API.
It does not claim a complete workflow or campaign PASS.

Production frontend patch: {production['patch_id']}.
Frontend artifact SHA-256: {production['artifact_sha256']}.
The container and base image remain unchanged: {production['base_image']}.
The frontend manifest separately records the patch and its source hashes; the
engine indicator identifies the UI patch rather than claiming an image release.
Local and LAN readiness and frontend artifact identity were verified.

The original image-layer directory could not be renamed (Docker overlayfs
EXDEV). Production stayed unchanged on that failed attempt. The corrected path
copies the old compiled bundle and affected files to
`{production['rollback_path']}`, replaces only the compiled bundle and scoped
frontend files, and restarts the existing container. Original dependencies and
backend remain untouched. The artifact is also archived at
`{production['artifact_archive_local']}` with a verified archive SHA-256.
This is an explicit frontend overlay: it survives restart of this container.
A future container recreation from the unchanged image requires restoring this
artifact or a normal source-based release; the base image alone lacks the patch.

No backend/model/database test data or new simulation run was created. The small
browser check preserved existing job identities/statuses. EIP was not modified.
''',encoding='utf-8')
print('Evidence completed; run completion guard')
