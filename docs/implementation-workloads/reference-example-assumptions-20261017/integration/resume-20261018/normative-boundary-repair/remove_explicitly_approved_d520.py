"""Execute the subsequent exact human d520 approval; protect the new candidate."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
REVIEW = OUT / 'archive-review-d520e6b852e5'
TAG = 'networkis:candidate-d520e6b852e5'
IMAGE = 'sha256:2c2840df896a406910ef4c1c68f3c43afcb48f819dae1f493805d0aeb4d0d896'
APP, DB = 'nis-e2e-app-d520e6b852e5', 'nis-e2e-db-d520e6b852e5'
PRODUCTION = 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
CURRENT = 'sha256:3bfa6ce10900bea57fa13c73bde4663c07bb5f3a8b5b46ea9237e963f6f19511'
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']

def call(*args):
    return subprocess.check_output([DOCKER, *args], text=True, encoding='utf-8').strip()

def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.resolve()), 'sha256': digest, 'bytes': path.stat().st_size}

def protect():
    assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == PRODUCTION
    assert call('inspect', 'nis-e2e-app-b2bb3887246e', '--format', '{{.Image}}') == CURRENT
    assert call('inspect', 'nis-e2e-db-b2bb3887246e', '--format', '{{.State.Running}}') == 'true'
    assert call('inspect', 'nis-e2e-app-d851f62a961b', '--format', '{{.Image}}') == 'sha256:0a191a95598704d2dc1c0f1a7060665b8c896bfdf8d36ec8a43a5daa1a6a5d74'

protect()
audit = json.loads((REVIEW / 'archive-audit.json').read_text())
assert audit['image'] == IMAGE and len(audit['verified_blobs']) == 23
assert audit['immutable_index_verified'] and audit['immutable_config_verified'] and audit['all_layers_verified']
archive = Path(audit['archive']['path'])
assert ref(archive)['sha256'] == audit['archive']['sha256']
assert ref(Path(audit['database_dump']['path']))['sha256'] == audit['database_dump']['sha256']
image = json.loads(call('image', 'inspect', TAG))[0]
assert image['Id'] == IMAGE and image['RepoTags'] == [TAG]
ids = call('ps', '-aq', '--no-trunc').split()
containers = json.loads(call('inspect', *ids)) if ids else []
references = [row for row in containers if row['Image'] == IMAGE]
assert [row['Name'].lstrip('/') for row in references] == [APP]
receipts = []
for parent in [ROOT / 'backend/test-output', ROOT / 'work']:
    for path in parent.rglob('receipt.json'):
        row = json.loads(path.read_text(encoding='utf-8-sig'))
        if row.get('image_id') == IMAGE:
            assert row.get('status') in {'PREPARED', 'FAIL'}, 'PASS/active/unknown release protects image.'
            receipts.append({**ref(path), 'status': row['status']})
assert receipts
authorization = {'question_id': 'call_cd81d90838fb4fb4b13cd0bdae82e3e6/0',
                 'verbatim_answer': 'Diese gesicherten Testcontainer und genau dieses Image entfernen',
                 'source': 'Subsequent direct human reply in this chat to the exact app/db/image cleanup question.',
                 'scope': [APP, DB, TAG], 'at_utc': datetime.now(timezone.utc).isoformat()}
# Secure the latest complete test database too, rather than assuming that the
# earlier snapshot remained unchanged while the delayed question was pending.
latest_dump = archive.parent / 'native-test-projects-d520e6b852e5-final-20261018.dump'
assert not latest_dump.exists(), 'Never overwrite a secured final snapshot.'
with latest_dump.open('wb') as output:
    subprocess.run([DOCKER, 'exec', DB, 'sh', '-c', 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=output, check=True)
with latest_dump.open('rb') as source:
    result = subprocess.run([DOCKER, 'exec', '-i', DB, 'pg_restore', '--list'], stdin=source, capture_output=True, check=True)
(REVIEW / 'final-database-restore-list.txt').write_bytes(result.stdout)
exports = []
for project in ['20261018110232672-964994ce', '20261018113821095-5bb997f2']:
    request = Request('http://127.0.0.1:61987/api/engineering/projects/export', headers={'X-Project-ID': project})
    with urlopen(request, timeout=45) as response:
        raw = response.read()
    assert json.loads(raw)['project_id'].removeprefix('network-project-') == project
    path = REVIEW / (project + '-final-bundle.json')
    path.write_bytes(raw)
    exports.append(ref(path))
before_count = len(set(call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split()))
record = {'at_utc': authorization['at_utc'], 'authorization': authorization, 'tag': TAG, 'image_id': IMAGE,
          'archive': ref(archive), 'archive_verified_blobs': audit['verified_blobs'],
          'latest_database_dump': ref(latest_dump), 'latest_database_contents_readable': True,
          'latest_project_exports': exports, 'receipts': receipts,
          'container_snapshot': [{'id': row['Id'], 'name': row['Name'], 'image': row['Image']} for row in containers],
          'image_count_before': before_count, 'production': PRODUCTION, 'current_candidate': CURRENT,
          'scope_note': 'One subsequent exact human-approved d520 cleanup, separate from the peer ten-image cleanup.'}
(REVIEW / 'explicit-final-removal-audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
protect()
assert call('inspect', APP, '--format', '{{.Image}}') == IMAGE
subprocess.run([DOCKER, 'stop', APP, DB], check=True, stdout=subprocess.DEVNULL)
subprocess.run([DOCKER, 'rm', APP, DB], check=True, stdout=subprocess.DEVNULL)
ids = call('ps', '-aq', '--no-trunc').split()
fresh = json.loads(call('inspect', *ids)) if ids else []
assert all(row['Image'] != IMAGE for row in fresh)
assert call('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE
command = [DOCKER, 'image', 'rm', '--no-prune', TAG]
result = subprocess.run(command, text=True, encoding='utf-8', capture_output=True, check=True)
assert subprocess.run([DOCKER, 'image', 'inspect', TAG], capture_output=True).returncode != 0
protect()
after_count = len(set(call('image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}').split()))
assert after_count == before_count - 1
record.update(status='EXACT_USER_APPROVED_TEST_RUNTIME_AND_IMAGE_REMOVED', image_removal_command=command,
              image_removal_exit_code=result.returncode, image_removal_output=result.stdout,
              image_count_after=after_count, production_unchanged=True, current_candidate_unchanged=True)
(REVIEW / 'explicit-final-removal-result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
decision_path = OUT / 'cleanup-decision.json'
decision = json.loads(decision_path.read_text())
decision.update(status='SUBSEQUENT_EXPLICIT_HUMAN_APPROVAL_EXECUTED', subsequent_authorization=authorization,
                actual_removal_result=ref(REVIEW / 'explicit-final-removal-result.json'))
decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': record['status'], 'image_count_before': before_count, 'image_count_after': after_count,
                  'production_unchanged': True, 'new_candidate_unchanged': True}), flush=True)
