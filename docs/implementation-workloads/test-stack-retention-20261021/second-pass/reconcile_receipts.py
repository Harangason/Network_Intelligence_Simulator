"""Resolve all historical receipt roots instead of assuming absent means unused."""
import importlib.util
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
spec = importlib.util.spec_from_file_location('previous_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
spec = importlib.util.spec_from_file_location('retention_owner', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)

roots = [ROOT / 'backend/test-output/release-gates', ROOT / 'work', ROOT / 'reports',
         ROOT / 'docs/implementation-workloads']
worktrees = subprocess.check_output(['git', 'worktree', 'list', '--porcelain'], text=True)
for line in worktrees.splitlines():
    if line.startswith('worktree '):
        tree = Path(line[9:])
        if tree.resolve() != ROOT.resolve():
            roots.extend([tree / 'backend/test-output/release-gates', tree / 'work', tree / 'reports'])
receipts, errors = [], []
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob('*receipt*.json'):
        if any(part in {'before', 'after', '.venv', 'node_modules', 'second-pass', 'retired-receipts'} for part in path.parts):
            continue
        try:
            row = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(row, dict) or row.get('status') not in {'PASS', 'FAIL', 'PREPARED', 'RUNNING'}:
                continue
            receipts.append({'data': row, **prior.ref(path), 'complete_pass': storage.complete_pass(row)})
        except (OSError, ValueError) as error:
            errors.append({'path': str(path), 'error': str(error)})
images = json.loads((OUT / 'inventory-before.json').read_text())['images']
for image in images:
    token = image['labels'].get('networkis.release.gate') or image['tags'][0].split('candidate-')[-1]
    related = []
    for item in receipts:
        row = item['data']
        identity = row.get('image_id')
        if identity == image['id']:
            binding = 'EXACT_IMMUTABLE_ID'
        elif (row.get('image_tag') in image['tags'] or Path(item['path']).parent.name == token):
            if identity and identity != image['id']:
                binding = 'CONFLICT_DIFFERENT_IMMUTABLE_ID'
            elif row.get('initial_source_sha256') == image['labels'].get('networkis.release.source'):
                binding = 'TAG_GATE_AND_SOURCE_NO_IMAGE_ID_IN_RECEIPT'
            else:
                binding = 'UNVERIFIED_TAG_OR_GATE_ONLY'
        else:
            continue
        related.append({**item, 'binding': binding})
    image['all_receipts'] = related
    image['resolved_statuses'] = sorted(set(r['data']['status'] for r in related if r['binding'] in {'EXACT_IMMUTABLE_ID', 'TAG_GATE_AND_SOURCE_NO_IMAGE_ID_IN_RECEIPT'}))
    image['complete_pass_receipts'] = [r['path'] for r in related if r['complete_pass'] and r['binding'] == 'EXACT_IMMUTABLE_ID']
prior.write('resolved-images.json', {'receipt_roots': list(map(str, roots)), 'receipt_count': len(receipts),
                                    'errors': errors, 'images': images})
for image in sorted(images, key=lambda i: i['created'], reverse=True):
    print(json.dumps({'tag': image['tags'][0], 'status': image['resolved_statuses'],
                      'passes': len(image['complete_pass_receipts']),
                      'bindings': sorted(set(r['binding'] for r in image['all_receipts'])),
                      'receipts': [r['path'] for r in image['all_receipts'] if r['binding'] != 'EXACT_IMMUTABLE_ID']}), flush=True)
print(json.dumps({'receipt_count': len(receipts), 'errors': errors}), flush=True)
