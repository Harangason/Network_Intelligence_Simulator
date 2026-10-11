"""Preserve the task's own immutable failed image; this script deletes nothing."""
import hashlib
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
tag = 'networkis:candidate-42a674cad1bc'
identity = 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da'
assert subprocess.check_output([docker, 'image', 'inspect', tag, '--format', '{{.Id}}'], text=True).strip() == identity
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() != identity
target = folder / 'previous-production-42a674cad1bc.tar'
if not target.exists():
    subprocess.run([docker, 'image', 'save', '--output', str(target), tag], check=True)
verified = set()
with tarfile.open(target) as archive:
    def verify_descriptor(descriptor):
        digest = descriptor['digest']
        assert digest.startswith('sha256:')
        if digest in verified:
            return
        name = 'blobs/sha256/' + digest.split(':', 1)[1]
        member = archive.getmember(name)
        assert member.isfile() and member.size == descriptor['size']
        with archive.extractfile(member) as blob:
            assert 'sha256:' + hashlib.file_digest(blob, 'sha256').hexdigest() == digest
        verified.add(digest)
        media = descriptor.get('mediaType', '')
        if media.endswith('index.v1+json') or media.endswith('manifest.v1+json'):
            data = json.load(archive.extractfile(member))
            for child in data.get('manifests', []):
                verify_descriptor(child)
            if 'config' in data:
                verify_descriptor(data['config'])
            for child in data.get('layers', []):
                verify_descriptor(child)
    index = json.load(archive.extractfile('index.json'))
    descriptor = next(item for item in index['manifests'] if item['digest'] == identity)
    verify_descriptor(descriptor)
    manifest = json.load(archive.extractfile('manifest.json'))
    entry = next(item for item in manifest if tag in item['RepoTags'])
    config = archive.extractfile(entry['Config']).read()
    assert entry['Config'] == 'blobs/sha256/' + hashlib.sha256(config).hexdigest()
    assert 'sha256:' + hashlib.sha256(config).hexdigest() in verified
    for layer in entry['Layers']:
        assert archive.getmember(layer).isfile()
with target.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
report = {'archived_at': datetime.now(timezone.utc).isoformat(), 'image_id': identity,
          'tag': tag, 'archive': str(target), 'sha256': digest, 'bytes': target.stat().st_size,
          'immutable_index_verified': True, 'immutable_config_verified': True,
          'all_layers_present': True, 'verified_blob_count': len(verified),
          'source_sha256': 'e39f7a491d710ccf864f93f7bcc041ea174afe9cc82ae6d9f039f613702eeda1',
          'deleted': False, 'restore_command': 'docker image load --input ' + str(target),
          'scope': 'Previous production image, archived for a user-reviewed retention exception. Current ebba6b6c production remains protected. No deletion authorized by this script.'}
(folder / 'previous-production-archive.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
