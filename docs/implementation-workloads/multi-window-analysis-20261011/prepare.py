import hashlib, json, shutil
from pathlib import Path
root = Path(__file__).resolve().parents[3]
work = Path(__file__).resolve().parent
files = ['frontend/src/features/traces/lib/analysis-workspace.ts', 'frontend/src/features/traces/lib/analysis-workspace-browser.ts', 'frontend/src/features/traces/lib/analysis-workspace.test.mjs', 'frontend/src/features/traces/lib/trace-window-reader.ts', 'frontend/src/features/traces/ui/analysis-workspace-tools.tsx', 'frontend/src/features/traces/ui/analysis-compare.tsx', 'frontend/public/nis-analysis-worker.js', 'frontend/src/features/traces/ui/trace-analysis-workbench.tsx', 'frontend/src/features/simulation/ui/model-simulation-runner.tsx', 'frontend/src/features/agent/lib/assistant-context.ts', 'frontend/src/app/globals.css', 'backend/nis/interfaces/http/engineering.py', 'backend/nis/workflow/services/service.py', 'frontend/src/features/workflow/lib/workflow-api.ts', 'frontend/e2e/analysis-workspace.spec.ts']
revision, before = {}, []
for name in files:
    source = root / name
    revision[name] = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
    if source.exists():
        target = work / 'before' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        before.append({'path': str(target), 'sha256': revision[name]})
outcomes = ['detach_and_registry', 'shared_metadata_only_context', 'follow_independent_compare', 'time_and_selection_sync', 'finding_root_cause_sync', 'profiles_save_restore', 'project_and_session_scope', 'bounded_shared_trace_reads', 'assistant_context', 'deep_links_and_manual_monitor_placement', 'required_e2e', 'verified_production_delivery']
data = dict(goal_id='multi-window-analysis-20261011', goal_type='implementation', kind='implementation', repository=str(root), project_scope='NIS simulation and trace analysis multi-window workspace', requested_change='Implement attached Multi Window Simulation Trace Analyse specification, browser phases 0-6 with desktop-adapter-ready descriptors.', modify_code=True, allow_repair=True, revision_before=revision, before=before, required_outcomes=outcomes, outcomes={}, validation_requirements=['targeted', 'typecheck', 'release', 'production'], validations={}, forbidden_changes=['No shadow technical model', 'No simulation writes from restored analysis windows', 'No automatic clock alignment or inferred causes', 'No EIP deployment', 'No unaudited image pruning'], constraints=['Canonical services, shared sequence renderer, project-scoped read APIs', 'Existing repair campaign, not a campaign PASS', 'Manual monitor placement; popup fallback link'], unresolved_decisions=[], files_changed=[], implementation_plan=['Typed presentation-context and descriptor protocol', 'Project-scoped BroadcastChannel with authoritative primary, handshake, bounded registry and no traces in events', 'Existing bounded trace API and shared worker cache; server scope checks preserved', 'Workspace toolbar, modes, profile restore, explicit comparisons and assistant references', 'Wire real simulation and trace selections/time with stale response guards', 'Isolated E2E and canonical release-and-deploy exact image'], delivery={'decision':'YES', 'authorization':'User AGENTS.md standing production delivery authorization', 'target':'Canonical NIS stack ports 13500/15050'}, completion_status='PLANNING')
(work / 'workload.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
shutil.copy2(Path('H:/OneDrive/Download/NIS_Implementierungsanweisung_Multi_Window_Simulation_Trace_Analyse.md'), work / 'requirements.md')
print(json.dumps({'planned_files':len(files), 'outcomes':len(outcomes), 'root':str(root)}))
