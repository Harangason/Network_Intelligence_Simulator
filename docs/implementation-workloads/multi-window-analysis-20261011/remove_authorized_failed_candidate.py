"""Execute the user's exact scoped retention exception, with fresh immutable checks."""
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

here = Path(__file__).parent
review_path = here / 'failed-candidate-storage-review.json'
review = json.loads(review_path.read_text(encoding='utf-8-sig'))
docker = review['requested_action'][0]
tag = 'networkis:candidate-a47ee30356bb'
image = 'sha256:98b2c881bebc4232bf97747376f16139dd49a095f1f7562e76955ff18b1667fb'
production = 'sha256:04d9a791b807799cbec822820db86f00ccd1554910f44cc1b01f3de5e59749c5'
assert review['tag'] == tag and review['image_id'] == image and review['deleted'] is False
assert review['verified_blob_count'] == 21 and review['all_layers_present'] and review['immutable_index_verified']
with Path(review['archive']).open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == review['archive_sha256']
assert hashlib.sha256(Path(review['failed_receipt']).read_bytes()).hexdigest() == review['failed_receipt_sha256']
def command(*args):
    return subprocess.check_output([docker, *args], text=True, encoding='utf-8').strip()
assert command('image', 'inspect', tag, '--format', '{{.Id}}') == image
assert command('inspect', 'NetworkIS', '--format', '{{.Image}}') == production
ids = command('ps', '-aq', '--no-trunc').split()
containers = json.loads(command('inspect', *ids)) if ids else []
assert not any(row['Image'] == image for row in containers), 'Authorized image now has a container reference.'
permission = {'authorization': 'Genau dieses archivierte Image entfernen und Release fortsetzen',
    'question_id': 'call_uqkclRbg6ktlz4o5eUwUv28M', 'question_tag': tag, 'approved_in_current_task': True, 'captured_at': datetime.now(timezone.utc).isoformat()}
(here / 'retention-authorization.json').write_text(json.dumps(permission, indent=2), encoding='utf-8')
result = command('image', 'rm', '--no-prune', tag)
assert command('inspect', 'NetworkIS', '--format', '{{.Image}}') == production
review.update(deleted=True, deleted_at=datetime.now(timezone.utc).isoformat(), deletion_result=result,
    fresh_container_images=[{'id': row['Id'], 'image': row['Image']} for row in containers])
review_path.write_text(json.dumps(review, indent=2), encoding='utf-8')
print(json.dumps({'status': 'AUTHORIZED_IMAGE_REMOVED', 'tag': tag, 'image_id': image, 'production_image': production}))

