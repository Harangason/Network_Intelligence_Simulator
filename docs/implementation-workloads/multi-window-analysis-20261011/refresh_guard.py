"""Capture this task's repair revision; original before evidence remains intact."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[3]
path=Path(__file__).with_name('workload.json')
work=json.loads(path.read_text())
work['revision_before']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() if (ROOT/name).exists() else None for name in work['revision_before']}
work['completion_status']='IMPLEMENTING'
path.write_text(json.dumps(work,indent=2)+'\n')
