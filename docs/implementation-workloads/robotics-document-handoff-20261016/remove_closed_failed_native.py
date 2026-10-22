"""Remove only the fully archived, demonstrably closed own FAIL candidate."""
from pathlib import Path
import hashlib
import json
import subprocess
import time
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
IMAGE = 'sha256:64020013cfb59eaa17acefa4484680bab1c7216ceb3ed54d96254e14288f355a'
TAG = 'networkis:candidate-911347665bea'
audit = json.loads((OUT / 'native-failed-archive-audit.json').read_text(encoding='utf-8'))
assert audit['status'] == 'ARCHIVED_VERIFIED' and audit['image'] == IMAGE and audit['tag'] == TAG
assert audit['immutable_index_verified'] and audit['immutable_config_verified'] and audit['all_layers_verified']
archive = Path(audit['archive']['path'])
assert archive.stat().st_size == audit['archive_bytes']
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == audit['archive']['sha256']
cleanup = json.loads((OUT / 'native-stack-cleanup.json').read_text(encoding='utf-8'))
assert cleanup['status'] == 'COMPLETED_NATIVE_STACK_REMOVED'
assert cleanup['image_retained'] == IMAGE and cleanup['currently_active_native_work'] is False
assert json.loads((OUT / 'native-verification.json').read_text(encoding='utf-8'))['status'] == 'FAILED'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
def call(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()
ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *ids)) if ids else []
assert all(row['Image'] != IMAGE for row in containers)
observed = json.loads(call('image', 'inspect', TAG))[0]
assert observed['Id'] == IMAGE and observed['RepoTags'] == [TAG]
receipts = []
for parent in (ROOT / 'backend/test-output', ROOT / 'work', ROOT / 'docs/implementation-workloads'):
    for path in parent.rglob('receipt.json'):
        try:
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError):
            continue
        if receipt.get('image_id') != IMAGE:
            continue
        assert receipt['status'] in {'FAIL', 'PREPARED'}, str(path)
        if receipt['status'] == 'PREPARED':
            assert path.resolve() == (OUT / 'native-acceptance-stack/d0fae42aa592/receipt.json').resolve()
            assert receipt['containers'] == cleanup['resources']
        receipts.append({'path': str(path.resolve()), 'status': receipt['status'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
assert any(row['status'] == 'FAIL' for row in receipts)
assert {(row['path'], row['sha256']) for row in receipts} == {(row['path'], row['sha256']) for row in audit['receipts']}
production = call('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert production != IMAGE
command = [docker, 'image', 'rm', '--no-prune', TAG]
record = {'status': 'FRESH_REFERENCE_AND_HISTORY_CHECK_PASSED', 'captured_epoch': time.time(),
          'authorization': 'AGENTS.md standing authorization for archived failed-candidate cleanup; no age/delivered-equivalence inference. Own historical PREPARED use is explicitly closed by native FAILED evidence and complete resource cleanup; receipt unchanged.',
          'image_id': IMAGE, 'tag': TAG, 'archive': audit['archive'], 'receipts': receipts,
          'no_running_or_stopped_container_references': True, 'prepared_use_proven_closed': cleanup,
          'production_image': production, 'command': command}
(OUT / 'native-failed-fresh-removal-audit.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
assert call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == production
assert subprocess.run([docker, 'image', 'inspect', TAG], capture_output=True).returncode != 0
(OUT / 'native-failed-removal-result.json').write_text(json.dumps({**record, 'status': 'REMOVED', 'output': result.stdout, 'production_unchanged': True}, indent=2), encoding='utf-8')
print(json.dumps({'status': 'REMOVED', 'image_id': IMAGE, 'production_unchanged': True, 'recoverable_archive_retained': True}))
