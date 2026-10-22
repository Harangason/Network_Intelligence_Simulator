"""Extend the same repair workload with independently reproduced preview defects."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
HERE = Path(__file__).resolve().parent
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
for name in ('frontend/src/features/agent/lib/engineering-specification.ts',
             'frontend/src/features/agent/lib/engineering-specification.test.mjs'):
    file = Path(name)
    raw = file.read_bytes()
    snapshot = HERE / ('before-preview-' + file.name)
    assert not snapshot.exists()
    snapshot.write_bytes(raw)
    work['revision_before'][name] = hashlib.sha256(raw).hexdigest()
    work['before'].append({'path': str(snapshot), 'sha256': hashlib.sha256(raw).hexdigest()})
    work['repair']['affected_files'].append(name)
# Already applied and tested backend revision is the starting point for this next mutation.
for name in list(work['revision_before']):
    work['revision_before'][name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
for name in ('preview-red.txt', 'raw-preview-before.json', 'green.xml'):
    file = HERE / name
    work['repair']['evidence'].append({'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
work['repair']['root_cause_preview'] = 'Raw contexts merge by bare device name across profiles; missing connections borrow global protocol; TC source assertions are treated as physical declarations.'
work['repair']['acceptance_criteria'] += ['Preserve raw source profile identity and all source text', 'No foreign-profile connection fallback', 'No installed device inferred solely from TC citations']
(HERE / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
result = subprocess.run([sys.executable, '-X', 'utf8', 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py',
    'before-apply', '--workload', str(HERE / 'workload.json')], check=True, capture_output=True, text=True)
(HERE / 'before-preview-guard.json').write_text(result.stdout, encoding='utf-8')
print(result.stdout)
