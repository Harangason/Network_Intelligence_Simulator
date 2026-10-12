import hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FILES = ['frontend/src/features/simulation/ui/model-simulation-runner.tsx', 'frontend/src/app/globals.css', 'AGENTS.md']
def evidence(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
before = []
revisions = {}
for name in FILES:
    source = ROOT / name
    target = HERE / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    before.append(evidence(target))
    revisions[name] = evidence(source)['sha256']
workload = {
    'goal_id': HERE.name, 'goal_type': 'implementation', 'kind': 'implementation',
    'repository': str(ROOT), 'project_scope': 'NIS simulation presentation and historical playback',
    'requested_change': 'Bundle upper controls beside view tabs; remove separate outdated banner; add playback/pause/stop at timeline. Explicit user rule: small final checks and direct production without new image or full gate.',
    'modify_code': True, 'allow_repair': True, 'revision_before': revisions, 'before': before,
    'required_outcomes': ['compact_controls', 'historical_playback_controls', 'verified_direct_production_delivery'],
    'validation_requirements': ['typecheck', 'focused_browser', 'production'],
    'constraints': ['No new image or full release gate under explicit current user instruction', 'Preserve saved run, stale/preflight gates, multiwindow cursor, existing fields and faults'],
    'forbidden_changes': ['No backend/model/database mutations', 'No EIP deployment', 'No simulated full PASS receipt'],
    'unresolved_decisions': [], 'files_changed': FILES,
    'implementation_plan': ['Reuse playhead/playing and shared workspace publication', 'Default closed controls next to tabs, errors remain visible', 'Stage Linux frontend production build in existing container, preserve old frontend for rollback, swap frontend and restart existing container', 'Small typecheck and focused existing-run playback verification, verify live artifact hashes and health'],
    'delivery': {'decision': 'YES', 'authorization': 'Current explicit user request: only code, small final checks, no image and no big test, direct production', 'target': 'Canonical NetworkIS production container frontend'},
    'completion_status': 'IMPLEMENTING'
}
(HERE / 'workload.json').write_text(json.dumps(workload, indent=2, ensure_ascii=False), encoding='utf-8')
