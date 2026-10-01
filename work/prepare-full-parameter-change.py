from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
path = folder / 'workload.json'
data = json.loads(path.read_text(encoding='utf-8'))
for relative in sys.argv[1:]:
    source = root / relative
    if source.exists():
        before = folder / 'before' / relative
        if not before.exists():
            before.parent.mkdir(parents=True, exist_ok=True)
            before.write_bytes(source.read_bytes())
        data['revision_before'][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    if relative not in data['repair']['affected_files']:
        data['repair']['affected_files'].append(relative)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
