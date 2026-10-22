"""Record immutable source and the owned delta without writing Git state."""
from pathlib import Path
import datetime
import difflib
import hashlib
import importlib.util
import json

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
spec = importlib.util.spec_from_file_location('robotics_build_identity', ROOT / 'scripts/build/write-build-info.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = module.build_manifest(ROOT)
(OUT / 'source-final-before-gate.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
freeze = json.loads((OUT / 'source-freeze.json').read_text(encoding='utf-8'))
freeze.setdefault('previous_sources', []).append(freeze['source_sha256'])
freeze['source_sha256'] = manifest['source_sha256']
freeze['at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
freeze['files'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in freeze['files']}
(OUT / 'source-freeze.json').write_text(json.dumps(freeze, indent=2), encoding='utf-8')
diff = []
for relative in work['revision_before_initial_apply']:
    before = OUT / 'before' / relative
    old = before.read_text(encoding='utf-8').splitlines(keepends=True) if before.exists() else []
    new = (ROOT / relative).read_text(encoding='utf-8').splitlines(keepends=True)
    diff.extend(difflib.unified_diff(old, new, fromfile='before/' + relative, tofile='after/' + relative))
(OUT / 'prepared-owned.diff').write_text(''.join(diff), encoding='utf-8')
print(json.dumps(manifest))
