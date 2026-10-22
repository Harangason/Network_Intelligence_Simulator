"""Verify the completed handoff and freeze, then use the official image builder."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
expected = json.loads((OUT / 'final-input-identity.json').read_text())
owned = json.loads((OUT / 'final-joint-owned-manifest.json').read_text())
for relative, row in owned.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('Source drift', relative)
cleanup_root = ROOT / 'docs/implementation-workloads/portfolio-parser-20261018/cleanup-ten-20261018'
cleanup = json.loads((cleanup_root / 'removal-result.json').read_text())
audit = json.loads((cleanup_root / 'archive-audit.json').read_text())
assert len(cleanup['removed']) == 10 and cleanup['image_count_after'] == 90
assert len(audit['images']) == 10 and all(row['index_verified'] and row['config_verified'] and row['all_layers_verified'] for row in audit['images'])
archive = Path(audit['archive']['path'])
assert archive.stat().st_size == 8745050112
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == '9a6e04f23bfc0218b21608fb6a3fa421b902155f475a736b6ff034eb4815df7d'
relocation = json.loads((OUT / 'archive-relocation.json').read_text())
assert relocation['status'] == 'COMPLETE_LEGACY_RECOVERY_PATHS_AND_IMMUTABLE_ARCHIVES_PRESERVED'
assert shutil.disk_usage(ROOT).free > 20 * 1024**3
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']

def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()

count = len(set(call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split()))
assert count == 90
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
assert call('inspect', 'nis-e2e-app-d520e6b852e5', '--format', '{{.Image}}') == 'sha256:2c2840df896a406910ef4c1c68f3c43afcb48f819dae1f493805d0aeb4d0d896'
assert call('inspect', 'nis-e2e-app-d851f62a961b', '--format', '{{.Image}}') == 'sha256:0a191a95598704d2dc1c0f1a7060665b8c896bfdf8d36ec8a43a5daa1a6a5d74'
for container in ['nis-e2e-db-d520e6b852e5', 'nis-e2e-db-d851f62a961b']:
    assert call('inspect', container, '--format', '{{.State.Running}}') == 'true'
for row in cleanup['removed']:
    assert subprocess.run([docker, 'image', 'inspect', row['tag']], capture_output=True).returncode != 0
spec = importlib.util.spec_from_file_location('final_normative_release_owner', ROOT / 'scripts/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
assert owner.current_identity() == (expected['source_sha256'], expected['commit_id'], expected['verification_sha256'])
assert owner.active_gate(owner.receipt_paths(), expected['source_sha256']) is None
output = ROOT / 'backend/test-output/release-gates/joint-normative-originals-227a0c4214c9'
assert not output.exists(), 'Inspect any existing candidate instead of starting a duplicate preparation.'
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': expected, 'owned_files': len(owned),
          'archive_handoff_sha256': audit['archive']['sha256'], 'image_count_before': count,
          'source_free_bytes': shutil.disk_usage(ROOT).free, 'command': command,
          'development_base': None, 'production_changed': False,
          'scope': 'Normal production image preparation only. Both original native simulations, full gate and exact-image deployment remain mandatory.'}
(OUT / 'new-candidate-freeze.json').write_text(json.dumps(freeze, indent=2) + '\n', encoding='utf-8')
decision_path = OUT / 'cleanup-decision.json'
decision = json.loads(decision_path.read_text())
decision.update(status='NOT_REQUIRED_CAPACITY_RESOLVED_WITH_TEN_OTHER_IMAGES',
                human_approval_not_inferred=True, containers_and_image_retained=True,
                superseded_by_cleanup=str(cleanup_root / 'removal-result.json'))
decision_path.write_text(json.dumps(decision, indent=2) + '\n', encoding='utf-8')
workload_path = OUT.parents[1] / 'workload.json'
workload = json.loads(workload_path.read_text(encoding='utf-8-sig'))
workload.update(status='VALIDATING', unresolved_decisions=[])
workload['active_stage'] = {'stage': 'FINAL_NORMATIVE_CANDIDATE_PREPARATION', 'at_utc': freeze['at_utc'], 'command': command, 'full_pass': False}
workload['completion_status'] = 'Ten-image cleanup completed by sole peer operator and archived evidence verified. Legacy43/66 archives relocated with hashes and legacy paths preserved. Final227a source frozen; official normal candidate preparation now starting. Both original simulations and full productive release remain pending.'
workload_path.write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'STARTING_OFFICIAL_NORMAL_PREPARE', 'source_sha256': expected['source_sha256'], 'image_count_before': count, 'source_free_bytes': freeze['source_free_bytes']}), flush=True)
subprocess.run(command, cwd=ROOT, check=True)
