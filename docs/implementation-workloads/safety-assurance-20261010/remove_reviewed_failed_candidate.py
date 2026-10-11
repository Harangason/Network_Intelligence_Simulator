"""Execute only a fresh explicit user-approved recoverable retention exception."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--authorization', required=True, help='The explicit new user authorization for this exact image.')
args = parser.parse_args()
assert args.authorization.strip()
here = Path(__file__).resolve().parent
root = here.parents[2]
review = json.loads((here / 'failed-candidate-storage-review.json').read_text(encoding='utf-8'))
image = 'sha256:2adf2500166755ab5e19c6768d25fd4153d65976bcc40b6c5c6c0d3d1aee3669'
tag = 'networkis:candidate-1d8155ff129c'
protected = 'sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1'
assert review['image_id'] == image and review['tag'] == tag
assert review['requested_delete_count'] == 1 and review['deleted'] is False
assert all(review[key] is True for key in ('immutable_index_verified', 'immutable_config_verified', 'all_layers_present'))
archive = Path(review['archive'])
assert archive.resolve().parent == Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c').resolve()
assert archive.stat().st_size == review['archive_bytes']
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == review['archive_sha256']
receipt_path = Path(review['failed_receipt'])
assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == review['failed_receipt_sha256']
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'FAIL' and receipt['image_id'] == image
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
def command(*parts):
    return subprocess.check_output([docker, *parts], text=True, encoding='utf-8').strip()
ids = command('ps', '-aq', '--no-trunc').split()
containers = json.loads(command('inspect', *ids)) if ids else []
assert not any(row['Image'] == image for row in containers)
assert next(row['Image'] for row in containers if row['Name'] == '/NetworkIS') == protected
target = json.loads(command('image', 'inspect', tag))[0]
assert target['Id'] == image and target['RepoTags'] == [tag]
record = dict(review, status='AUTHORIZED_EXACT_RECOVERABLE_EXCEPTION', authorization=args.authorization,
              authorized_at=datetime.now(timezone.utc).isoformat(), deleted=False)
output = here / 'authorized-failed-candidate-removal.json'
output.write_text(json.dumps(record, indent=2), encoding='utf-8')
removed = command('image', 'rm', '--no-prune', tag)
assert subprocess.run([docker, 'image', 'inspect', image], capture_output=True).returncode != 0
assert command('inspect', 'NetworkIS', '--format', '{{.Image}}') == protected
assert archive.is_file() and archive.stat().st_size == review['archive_bytes']
record.update(status='EXACT_ARCHIVED_FAILED_IMAGE_REMOVED', deleted=True, removal_output=removed)
output.write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps({'status': record['status'], 'image_id': image, 'retained_archive': str(archive)}))
