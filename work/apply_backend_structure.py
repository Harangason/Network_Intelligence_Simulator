"""Apply the checked stage with per-file recovery copies; no recursive deletion."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
STAGE = ROOT / 'work/backend-structure-stage'
plan_path = OUT / 'backend-migration-plan.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
for relative, expected in plan['writes'].items():
    target = (ROOT / relative).resolve()
    source = (STAGE / relative).resolve()
    if not target.is_relative_to(ROOT) or not source.is_relative_to(STAGE):
        raise SystemExit('Unsafe target: ' + relative)
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise SystemExit('Stale staging: ' + relative)
subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), '--plan', str(plan_path)], check=True)
for relative in plan['writes']:
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STAGE / relative, target)
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work['files_changed'] = sorted(set(work['files_changed']) | set(plan['writes']))
work['completion_status'] = 'IMPLEMENTING'
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'applied_files': len(plan['writes']), 'canonical_moves': len(plan['mappings'])}))
