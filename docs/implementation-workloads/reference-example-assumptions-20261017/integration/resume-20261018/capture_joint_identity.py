"""Read the official release inputs; does not build, test or deploy."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
manifest = json.loads((OUT / 'joint-owned-manifest.json').read_text())
spec = importlib.util.spec_from_file_location('joint_release_identity_owner', ROOT / 'scripts/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
source, commit, verification = owner.current_identity()
for relative, row in manifest.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('PLAN_STALE', relative)
assert commit == '70f0c160bc4f08bd23437f6b3c175523d1e5859c', 'Git revision changed'
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source,
          'commit_id': commit, 'verification_sha256': verification,
          'owned_files_verified': len(manifest), 'status': 'INPUT_IDENTITY_ONLY',
          'full_release_pass': False, 'new_candidate_prepared': False}
(OUT / 'joint-release-input-identity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result), flush=True)
