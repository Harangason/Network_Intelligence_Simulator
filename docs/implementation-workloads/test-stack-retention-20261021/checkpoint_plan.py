"""Advance revision expectations only after reviewing this task's own diff."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
path = OUT / 'workload.json'
work = json.loads(path.read_text())
root = Path(work['repository'])
work.setdefault('revision_history', []).append(work['revision_before'])
work['revision_before'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           if (root / name).exists() else None for name in work['revision_before']}
path.write_text(json.dumps(work, indent=2) + '\n', encoding='utf-8')
