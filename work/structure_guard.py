"""Refresh revision evidence for one migration step and run the read-only guard."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
revision = {}
paths = sys.argv[1:]
if paths[:1] == ['--plan']:
    paths = list(json.loads(Path(paths[1]).read_text(encoding='utf-8'))['writes'])
for relative in paths:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise SystemExit('Outside workspace: ' + relative)
    revision[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if path.is_file():
        backup = OUT / 'before/steps' / revision[relative] / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(path, backup)
work['revision_before'] = revision
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py',
                'before-apply', '--workload', str(work_path)], check=True)
