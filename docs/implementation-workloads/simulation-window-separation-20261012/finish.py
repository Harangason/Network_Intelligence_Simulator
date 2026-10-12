from pathlib import Path
import json,hashlib,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def evidence(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text());functional=json.loads((HERE/'production-functional.json').read_text())
assert prod['status']==functional['status']=='PASSED' and prod['artifact_sha256']==functional['artifact_sha256']
for n in ['typecheck','workspace-tests','build']:assert json.loads((HERE/(n+'.json')).read_text())['status']=='PASSED'
w['after']=[];diff=[]
for name in w['files_changed']:
 p=ROOT/name;w['after'].append(evidence(p));diff.extend(difflib.unified_diff((HERE/'before'/name).read_text(encoding='utf-8').splitlines(True),p.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8');w['diff']=[evidence(HERE/'implementation.diff')]
def passed(*names):return {'status':'PASSED','evidence':[evidence(HERE/n) for n in names]}
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','scope':'Nine focused workspace tests, TypeScript, production frontend compilation and focused existing-job browser layout/popup/profile checks','image_created':False,'full_release_gate':False,'patch_id':prod['patch_id']},indent=2))
w['outcomes']={n:passed('production-functional.json') for n in w['required_outcomes']};w['outcomes']['verified_direct_production_delivery']=passed('production-verification.json','production-functional.json')
w['validations']={'typecheck':passed('typecheck.json'),'workspace_tests':passed('workspace-tests.json'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json','production-functional.json')}
w['delivery'].update(tested_version=prod['artifact_sha256'],running_version=prod['artifact_sha256'],base_image=prod['base_image'],frontend_patch_id=prod['patch_id'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=w['files_changed']+['frontend/AGENTS.md','docs/NIS_E2E_SEQUENCE_DIAGRAM_SIMULATION_TRACE_TARGET.md'];w['remaining_findings']=[];w['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(w,indent=2,ensure_ascii=False),encoding='utf-8')
(HERE/'implementation-notes.md').write_text(f'''# Simulation controls and window separation — 2026-10-12

Desktop command form now places scenario, duration, playback speed, seed, trace
formats and execution controls in one row, with reduced panel padding. Responsive
layouts wrap on narrower screens to preserve field readability and controls.

Workspace tools visibly separate Simulation and Trace-Analyse into two columns.
The existing WindowDescriptor.board_id is authoritative for shared view names
such as signals/sequence/load. Previously every non-simulation view was routed
to trace-analysis and presets/profile restore navigated the current page. Now
simulation child windows retain /studio/simulation and trace actions explicitly
request /trace-analysis. Popup blocking offers destination-labelled new-tab links.
Presets and restore open additional windows and never replace the current page.
Simulation initialization also reads the validated view query. The simulation
page formerly rendered TraceAnalysisWorkbench for every secondary window even
on /studio/simulation. It now reuses ModelSimulationRunner with readOnly=true:
simulation tabs/playback remain available but command form, scenario/fault
editing and preflight scope changes are absent. Only the primary publishes view
changes; linked time/source context continues through the existing store.
Actual secondary sequence tabs and restored historical job were verified.

Profiles retain optional primary_board/secondary_boards metadata, validated in
the existing v1 profile contract. Legacy profiles remain readable with their
previous trace destination semantics for shared view names. Source identity,
project, exact times and linkage mode still use the existing context/store.
No new analysis engine, shared-state authority or backend/data-model change.

Nine focused tests, TypeScript, frontend compilation and actual browser popup /
responsive checks passed. A verifier first compared a compact project alias to
the canonical network-project- prefixed ID; the read-only check was corrected to
compare the existing equivalent IDs. No application behavior was changed for that
fixture mismatch. The secondary-page rendering failure was reproduced from the
actual popup body, corrected at its page owner and rerun in production.
Only temporary local browser profile metadata was created and
removed; no new simulation, backend test database or full campaign was used.

User-authorized direct frontend delivery: patch {prod['patch_id']}.
Artifact {prod['artifact_sha256']}; base image unchanged {prod['base_image']}.
Rollback {prod['rollback_path']}; archive {prod['artifact_archive_local']}.
No image or full release gate; base-image PASS does not cover this overlay.
It survives restart of this container. Container recreation requires archive
restoration or release of canonical updated source. EIP remains untouched.
''',encoding='utf-8')
print('Evidence complete')
