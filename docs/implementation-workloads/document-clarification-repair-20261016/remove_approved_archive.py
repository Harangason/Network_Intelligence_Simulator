"""Remove only the exact archived candidate explicitly approved in this chat."""
from pathlib import Path
import hashlib
import json
import subprocess

from archive_for_review import OUT, ARCHIVE, DOCKER, IMAGE, TAG, inventory, ref

authorization = {
    'tag': 'networkis:candidate-e4af20244aaf',
    'image_id': 'sha256:a3d3a49496842b1186d6691af7bd75931d13dd2973454d45907b32bbb1e6efa0',
    'user_answer': 'Genau dieses archivierte Image entfernen und fortsetzen',
    'question_item': 'request_user_input_async/call_094a8e1e34154bd2a8a158114804b246/0',
    'scope': 'One exact unused archived mixed PREPARED/FAIL candidate; no pruning, force, production or rollback removal',
}
assert authorization['tag'] == TAG and authorization['image_id'] == IMAGE
audit = json.loads((OUT / 'archive-audit.json').read_text(encoding='utf-8'))
assert audit['status'] == 'ARCHIVED_VERIFIED' and audit['tag'] == TAG and audit['image'] == IMAGE
assert audit['immutable_index_verified'] and audit['immutable_config_verified'] and audit['all_layers_verified']
assert ref(ARCHIVE) == audit['archive'] and ARCHIVE.stat().st_size == audit['archive_bytes']
observed = inventory()  # Fresh running AND stopped container, tag and receipt checks.
assert observed['production'] == audit['production'] and observed['production'] != IMAGE
command = [DOCKER, 'image', 'rm', '--no-prune', TAG]
record = {**authorization, 'archive': audit['archive'], 'command': command, **observed}
(OUT / 'fresh-removal-audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
assert subprocess.check_output([DOCKER, 'image', 'inspect', TAG, '--format', '{{.Id}}'], text=True).strip() == IMAGE
result = subprocess.run(command, check=True, capture_output=True, text=True)
assert subprocess.check_output([DOCKER, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == observed['production']
assert subprocess.run([DOCKER, 'image', 'inspect', TAG], capture_output=True).returncode != 0
report = {'status': 'REMOVED', 'tag': TAG, 'image_id': IMAGE, 'removed_count': 1, 'command': command,
          'exit_code': result.returncode, 'output': result.stdout, 'production_unchanged': True,
          'authorization': authorization}
(OUT / 'removal-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
