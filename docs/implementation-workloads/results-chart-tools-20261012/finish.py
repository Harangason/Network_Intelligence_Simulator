import difflib,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def evidence(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((HERE/'workload.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text());functional=json.loads((HERE/'production-functional.json').read_text())
assert prod['status']==functional['status']=='PASSED'
assert prod['patch_id']==functional['patch_id'] and prod['artifact_sha256']==functional['artifact_sha256']
for name in ['typecheck','chart-data','build']: assert json.loads((HERE/(name+'.json')).read_text())['status']=='PASSED'
assert prod['image_created'] is False and prod['full_gate_run'] is False
diff=[];w['after']=[]
for name in w['files_changed']:
    current=ROOT/name;before=HERE/'before'/name
    w['after'].append(evidence(current));diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True) if before.exists() else [],current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(HERE/'implementation.diff').write_text(''.join(diff),encoding='utf-8');w['diff']=[evidence(HERE/'implementation.diff')]
def passed(*names):return {'status':'PASSED','evidence':[evidence(HERE/n) for n in names]}
(HERE/'small-checks.json').write_text(json.dumps({'status':'PASSED','scope':'Five chart data tests, frontend TypeScript and compilation, focused existing historical snapshot browser controls/placement/responsive verification, production identity and local/LAN health','image_created':False,'full_release_gate':False,'patch_id':prod['patch_id'],'limitations':['Saved aggregate jitter is not a jitter time series; it covers the entire selected run, independently of plotted time zoom','No real hardware/functional timing approval','Frontend overlay survives container restart; recreate requires archived artifact restoration or a source release']},indent=2),encoding='utf-8')
w['outcomes']={name:passed('production-functional.json') for name in w['required_outcomes']}
w['outcomes']['verified_direct_production_delivery']=passed('production-verification.json','production-functional.json')
w['validations']={'typecheck':passed('typecheck.json'),'chart_data':passed('chart-data.json'),'focused_browser':passed('production-functional.json'),'production':passed('production-verification.json','production-functional.json')}
w['delivery'].update(tested_version=prod['artifact_sha256'],running_version=prod['artifact_sha256'],base_image=prod['base_image'],frontend_patch_id=prod['patch_id'],checks={'release':passed('small-checks.json'),'deployment':passed('production-verification.json'),'health':passed('production-verification.json'),'functional':passed('production-functional.json')})
w['files_inspected']=['frontend/src/features/workflow/stage_08_results_analysis/results-workbench.tsx','frontend/src/features/workflow/stage_09_intelligence/intelligence-workbench.tsx','frontend/src/features/capacity/ui/capacity-workbench.tsx','frontend/src/shared/api/types.ts','backend/nis/engineering/capacity/service.py','backend/nis/simulation/runtime_analysis.py','frontend/AGENTS.md','frontend/node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md']
w['remaining_findings']=[];w['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(w,indent=2,ensure_ascii=False),encoding='utf-8')
(HERE/'implementation-notes.md').write_text(f'''# Results chart tools — 2026-10-12

Communication sizing removed only from Intelligence, preserved in Capacity.
Standalone historical Results banner removed; canonical staleness, snapshot list
status, source versions, preflight and stale-run handling are unchanged.

Expanded peak charts show all filtered networks, with a viewport-sized scroll area
and more useful label/plot proportions. Expanded route donut scales up and includes
saved runtime network counts by bus technology, route counts by network and by
sender/receiver pair. Multicast route involvement does not imply extra wire traffic.

Trend tools support up to six networks across different technologies, line/step/
point/bar representation, automatic or 0–100 percent scale, zoom, pan and reset.
The SVG adapts to available width while keeping readable typography. Each series
retains its original timestamps and window size. Extrema sampling plots real points,
not fabricated averages; all selected-window values remain in a paginated table.

Partner jitter uses saved aggregate route metrics, not invented time-series data.
The metric is absolute actual reception interval minus expected cycle in ms.
At least two received events and a positive expected cycle are required to assess it.
Explicit zero limits are valid. Missing limits are open, never silently passing.
The saved aggregates cover the entire run, independently of chart time zoom.

For the reviewed project, stored engineering overview capacity_verified and
timing_verified are false, with peak/reserve/E2E fields null. The capacity service
intentionally separates nominal assumptions in network.simulation_capacity
(CALCULATED_UNDER_ASSUMPTIONS, hardware_evidence=false) from verified hardware
capacity. That is why a numerical runtime peak previously appeared alongside
“Nicht nachgewiesen”. Results now shows complete frozen assumption values separately
from open hardware proof, with explicit source explanation. A historical forecast
never falls back to today's capacity snapshot. No simulation value replaces a proof.

Five focused data checks, TypeScript, production frontend compilation and actual
historical-snapshot browser checks passed. No backend/database test writes, new
simulation, new image, full campaign or complete-image gate was run. This is the
explicitly user-authorized direct frontend delivery scope, recorded in AGENTS.md.

The initial browser check found wrapping select labels included their option text;
explicit accessible names were added and verified. A second verifier failure was
the test using innerText on an SVG node; it was corrected to textContent, without
changing application behavior. The final focused check passed with no page errors.

Frontend patch {prod['patch_id']}, artifact {prod['artifact_sha256']}.
Base image unchanged: {prod['base_image']}.
Rollback: {prod['rollback_path']}. Archive: {prod['artifact_archive_local']}.
This frontend overlay survives restart of the existing container; recreation from
the unchanged base image requires restoring the archived artifact or releasing the
canonical updated source. The base image PASS receipt does not cover this patch.
''',encoding='utf-8')
print('Evidence complete; run completion guard')
