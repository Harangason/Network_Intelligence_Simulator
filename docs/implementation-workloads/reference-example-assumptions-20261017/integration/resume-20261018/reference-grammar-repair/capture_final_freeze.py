"""Bind final repair deltas and all shared owned files to current identities."""
import difflib
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
workload = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
prior = json.loads((OUT.parent / 'normative-boundary-repair/final-joint-owned-manifest.json').read_text())
changed = set(workload['files_changed'])
owned = {}
for relative, row in prior.items():
    current = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    if relative not in changed:
        assert current == row['current'], ('Unowned source drift', relative)
    owned[relative] = {**row, 'current': current}
diff = []
for row in workload['snapshots']:
    relative = row['file']
    before = Path(row['before']['path'])
    assert hashlib.sha256(before.read_bytes()).hexdigest() == row['before']['sha256']
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, after)
    row['after'] = {'path': str(after), 'sha256': hashlib.sha256(after.read_bytes()).hexdigest()}
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(keepends=True),
                                   after.read_text(encoding='utf-8').splitlines(keepends=True),
                                   fromfile='before/' + relative, tofile='after/' + relative))
diff_file = OUT / 'changes.diff'
diff_file.write_text(''.join(diff), encoding='utf-8')
workload['diff'] = [{'path': str(diff_file), 'sha256': hashlib.sha256(diff_file.read_bytes()).hexdigest()}]
workload['status'] = 'VALIDATING'
workload['completion_status'] = 'Final decoder adapter and supported local runtime defaults frozen; complete affected regressions running. Native original simulations, complete release gate and production remain pending.'
spec = importlib.util.spec_from_file_location('grammar_delivery_identity', ROOT / 'scripts/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
assert delivery.active_gate(delivery.receipt_paths(), source) is None
identity = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source,
            'commit_id': commit, 'verification_sha256': verification,
            'owned_files': len(owned), 'changed_from_227a': sorted(changed),
            'candidate_image': None, 'full_pass': False, 'production_changed': False}
(OUT / 'final-input-identity.json').write_text(json.dumps(identity, indent=2)+'\n')
(OUT / 'final-joint-owned-manifest.json').write_text(json.dumps(owned, indent=2)+'\n')
workload['final_input_identity'] = identity
(OUT / 'workload.json').write_text(json.dumps(workload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(identity), flush=True)
