"""Freeze only the verified two-file repair over the previous joint snapshot."""
import difflib
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
BASE = OUT.parent
old = json.loads((BASE / 'joint-owned-manifest.json').read_text())
repair = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
revised = {row['file']: row['after']['sha256'] for row in repair['snapshots']}
assert set(revised) == {'backend/nis/agent/orchestration/project_intake.py', 'backend/tests/test_qwen_document_intake.py'}
current, diff = {}, []
for relative, row in old.items():
    data = (ROOT / relative).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == revised.get(relative, row['current']), ('Unexpected source drift', relative)
    target = OUT / 'final-joint-after' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    current[relative] = {**row, 'current': digest, 'native_normative_repair': relative in revised}
    before = BASE / 'joint-before' / relative
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8-sig').splitlines(True), data.decode('utf-8-sig').splitlines(True), fromfile='before/' + relative, tofile='after/' + relative))
assert len(current) == 30
(OUT / 'final-joint-owned-manifest.json').write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
(OUT / 'final-joint-owned.diff').write_text(''.join(diff), encoding='utf-8')
spec = importlib.util.spec_from_file_location('normative_joint_release_owner', ROOT / 'scripts/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
source, commit, verification = owner.current_identity()
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
for relative, row in current.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current']
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source, 'commit_id': commit,
          'verification_sha256': verification, 'owned_files_verified': 30, 'scoped_repair_files': list(revised),
          'previous_source_sha256': 'cf37e30cc3a5e18124c1eec3936373c4920d295d48657b70dcbc0ee9be929b56',
          'status': 'INPUT_IDENTITY_ONLY_NATIVE_AND_RELEASE_PENDING', 'new_candidate_prepared': False,
          'native_original_simulations': False, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'final-input-identity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result), flush=True)
