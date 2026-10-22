"""Audit all remaining image roles and recover historical receipt identities."""
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
spec = importlib.util.spec_from_file_location('prior_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT


def inspect():
    data = prior.inventory('inventory-before.json')
    # Preserve raw immutable image metadata, excluding environment/credentials.
    rows = json.loads(prior.call('image', 'inspect', *[r['id'] for r in data['images']]))
    metadata = [{k: r.get(k) for k in ('Id', 'RepoTags', 'RepoDigests', 'Created', 'Size', 'RootFS', 'Metadata')}
                | {'labels': r['Config'].get('Labels') or {}} for r in rows]
    prior.write('image-metadata.json', metadata)
    evidence = []
    for row in data['images']:
        for item in row['receipts']:
            path = Path(item['path'])
            value = json.loads(path.read_text(encoding='utf-8-sig'))
            evidence.append({'image': row['id'], **prior.ref(path),
                'status': value.get('status'), 'source': value.get('initial_source_sha256'),
                'commit': value.get('initial_commit_id'), 'release': value.get('release'),
                'check_results': value.get('checks'), 'error': value.get('error'),
                'disposition': value.get('storage'), 'retirement': value.get('stack_retirement')})
    prior.write('receipt-details.json', evidence)
    lines = []
    for row in sorted(data['images'], key=lambda r: r['created'], reverse=True):
        labels = row['labels']
        lines.append({'image': row['id'][:19], 'tags': row['tags'], 'created': row['created'],
                      'statuses': row['statuses'], 'containers': row['containers'],
                      'labels': labels, 'receipts': [r['path'] for r in row['receipts']]})
    prior.write('image-summary.json', lines)
    for row in lines:
        print(json.dumps({k: v for k, v in row.items() if k != 'receipts'}), flush=True)


if __name__ == '__main__':
    inspect()
