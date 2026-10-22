"""Prepare the final joint source only after the pending exact storage authorization."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
expected = json.loads((OUT / 'joint-release-input-identity.json').read_text())
validation = json.loads((OUT / 'joint-validation.json').read_text())
assert validation['identity'] == expected and validation['unique_final_passing_backend_cases'] == 358
assert validation['frontend_tests'] == 260 and validation['typecheck']['exit_code'] == 0
removal_path = OUT.parent.parent / 'archive-review-43d202d1dbde/removal-result.json'
removal = json.loads(removal_path.read_text())  # Absent until exact human authorization and audited removal.
assert removal['status'] == 'REMOVED' and removal['tag'] == 'networkis:candidate-43d202d1dbde'
assert removal['image_id'] == 'sha256:8addd0edb77baf9daec17b3cae1c8c917e3e768d6e3d8508fb964ea6171c98e0'
assert removal['production_unchanged'] and removal['image_count_after'] == 99
manifest = json.loads((OUT / 'joint-owned-manifest.json').read_text())
for relative, row in manifest.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('PLAN_STALE', relative)
spec = importlib.util.spec_from_file_location('joint_delivery_owner', ROOT / 'scripts/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
source, commit, verification = owner.current_identity()
assert (source, commit, verification) == tuple(expected[key] for key in ('source_sha256', 'commit_id', 'verification_sha256')), 'Release input drift after targeted checks'
destination = ROOT / 'backend/test-output/release-gates' / ('joint-reference-portfolio-native-' + source[:12])
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(destination)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': expected, 'owned_files': len(manifest),
          'command': command, 'output_directory': str(destination), 'development_base': None,
          'scope': 'Normal production Dockerfile preparation only; both unchanged original native simulations and the full gate remain required before productive delivery.'}
(OUT / 'joint-candidate-freeze.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'STARTING_JOINT_PREPARE', 'source': source, 'output_directory': str(destination)}), flush=True)
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
raise SystemExit(subprocess.run(command, cwd=ROOT, env=env).returncode)
