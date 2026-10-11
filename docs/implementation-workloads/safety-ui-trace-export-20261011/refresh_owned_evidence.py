"""Refresh owned source snapshots; does not alter application or test inputs."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def reference(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

for name in ('safety-ui-trace-export-20261011', 'wizard-whitespace-20261011'):
    folder = HERE.parent / name
    workload_path = folder / 'workload.json'
    workload = json.loads(workload_path.read_text(encoding='utf-8-sig'))
    before, after, differences = [], [], []
    for relative in workload['files_changed']:
        original = folder / 'before' / relative
        updated = folder / 'after' / relative
        updated.parent.mkdir(parents=True, exist_ok=True)
        updated.write_bytes((ROOT / relative).read_bytes())
        if original.exists():
            before.append(reference(original))
        after.append(reference(updated))
        differences.extend(difflib.unified_diff(
            original.read_text(encoding='utf-8-sig').splitlines(keepends=True) if original.exists() else [],
            updated.read_text(encoding='utf-8-sig').splitlines(keepends=True),
            fromfile='before/' + relative, tofile='after/' + relative))
    diff_path = folder / 'owned-changes.diff'
    diff_path.write_text(''.join(differences), encoding='utf-8')
    workload['before'], workload['after'], workload['diff'] = before, after, [reference(diff_path)]
    # Rebind existing diff evidence to the exact refreshed owned snapshot.
    for collection in ('outcomes', 'validations'):
        for row in workload.get(collection, {}).values():
            row['evidence'] = [reference(diff_path) if item.get('path') == str(diff_path.resolve()) else item
                               for item in row.get('evidence', [])]
    workload_path.write_text(json.dumps(workload, indent=2) + '\n', encoding='utf-8')
    print(name, len(after), 'owned files snapshotted')
