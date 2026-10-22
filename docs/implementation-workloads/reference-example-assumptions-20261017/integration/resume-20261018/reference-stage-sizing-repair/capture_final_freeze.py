"""Freeze the guarded reference-only repair and the jointly owned source set."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
workload = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
prior = json.loads((OUT.parent / 'reference-grammar-repair/final-joint-owned-manifest.json').read_text(encoding='utf-8'))
changed = set(workload['files_changed'])
owned = {}
for name, row in prior.items():
    actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    if name not in changed:
        assert actual == row['current'], ('Unowned source drift', name)
    owned[name] = {**row, 'current': actual, 'reference_stage_repair': name in changed}
for row in workload['after']:
    snapshot = Path(row['path'])
    name = snapshot.relative_to(OUT / 'after').as_posix()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row['sha256']
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == row['sha256']
    if name not in owned:
        owned[name] = {'current': row['sha256'], 'reference_stage_repair': True}
validation = json.loads((OUT / 'combined-affected-validation.json').read_text(encoding='utf-8'))
assert validation['final_unique_passing_cases'] == 375
assert validation['app_source_changed_between_these_runs'] is False
for row in validation['run_history']:
    evidence = row['evidence']
    assert hashlib.sha256(Path(evidence['path']).read_bytes()).hexdigest() == evidence['sha256']
spec = importlib.util.spec_from_file_location('staged_delivery_identity', ROOT / 'scripts/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
assert delivery.active_gate(delivery.receipt_paths(), source) is None
identity = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source,
    'commit_id': commit, 'verification_sha256': verification, 'owned_files': len(owned),
    'changed_from_36f': sorted(changed), 'candidate_image': None,
    'full_pass': False, 'production_changed': False}
assert source != '36f95018707e25958b5f19a28421185f69d26615610aa1350584ff534f381cb4'
assert not (OUT / 'final-input-identity.json').exists()
(OUT / 'final-input-identity.json').write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
(OUT / 'final-joint-owned-manifest.json').write_text(json.dumps(owned, indent=2) + '\n', encoding='utf-8')
workload['final_input_identity'] = identity
(OUT / 'workload.json').write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(identity), flush=True)
