"""Remove only the exact newly audited and archived non-PASS identities."""
import importlib.util
import json
from pathlib import Path
import time

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('previous_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
plan = json.loads((OUT / 'additional-cleanup-plan.json').read_text())
audit = json.loads((OUT / 'additional-image-archive-audit.json').read_text())
assert audit['plan'] == prior.ref(OUT / 'additional-cleanup-plan.json')
assert audit['index_config_and_all_layers_verified'] and audit['image_count'] == len(plan['images'])
assert prior.ref(Path(audit['archive']['path'])) == audit['archive']
resolved = json.loads((OUT / 'resolved-images.json').read_text())
roots = [Path(path) for path in resolved['receipt_roots']]
targets = {row['id']: row for row in plan['images']}


def fresh_statuses():
    found = {image: [] for image in targets}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob('*receipt*.json'):
            if any(part in {'before', 'after', '.venv', 'node_modules', 'second-pass', 'retired-receipts'} for part in path.parts):
                continue
            try:
                row = json.loads(path.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError):
                # A newly corrupted receipt cannot be safely classified.
                raise RuntimeError('Unverified receipt during removal: ' + str(path))
            if not isinstance(row, dict):
                continue
            for identity, image in targets.items():
                if (row.get('image_id') == identity or row.get('image_tag') in image['tags']):
                    assert row.get('status') in {'PREPARED', 'FAIL'}, (str(path), row.get('status'))
                    if row.get('image_id'):
                        assert row['image_id'] == identity, 'Tag points to conflicting receipt identity'
                    found[identity].append({**prior.ref(path), 'status': row['status']})
    assert all(found.values()), 'A planned receipt binding is no longer available'
    return found


fresh = prior.inventory('inventory-pre-removal.json')
assert fresh['production']['id'] == plan['production']['id']
assert fresh['production']['image'] == plan['production']['image'] and fresh['production']['health'] == 'healthy'
assert prior.call('image', 'inspect', plan['rollback'], '--format', '{{.Id}}') == plan['rollback']
statuses = fresh_statuses()
prior.write('fresh-target-receipt-evidence.json', statuses)
operations = []
result_path = OUT / 'additional-removal-result.json'


def save(status):
    prior.write(result_path.name, {'status': status, 'operations': operations,
        'plan': prior.ref(OUT / 'additional-cleanup-plan.json'), 'archive': audit['archive'],
        'new_or_active_images_outside_the_exact_plan_are_protected': True,
        'concurrency_safety': 'No build or source writes; exact old IDs only, recheck all running/stopped references before each removal, and Docker enforces no-force/no-prune reference protection.'})


save('REMOVING')
for identity, image in targets.items():
    assert prior.call('inspect', 'NetworkIS', '--format', '{{.Image}}') == plan['production']['image']
    current = prior.containers()
    assert not any(row['image'] == identity for row in current), 'A fresh container reference protects this image'
    observed = json.loads(prior.call('image', 'inspect', image['tags'][0]))[0]
    assert observed['Id'] == identity and observed['RepoTags'] == image['tags']
    assert observed['Config'].get('Labels', {}) == image['labels']
    assert identity not in {plan['production']['image'], plan['rollback']}
    result = prior.call('image', 'rm', '--no-prune', image['tags'][0])
    operations.append({'epoch': time.time(), 'image': identity, 'command': [prior.DOCKER, 'image', 'rm', '--no-prune', image['tags'][0]], 'result': result})
    save('REMOVING')
    print(json.dumps({'removed': image['tags'][0], 'completed': len(operations), 'total': len(targets)}), flush=True)
after = prior.inventory('inventory-after.json')
assert after['production']['id'] == plan['production']['id'] and after['production']['image'] == plan['production']['image']
assert after['production']['health'] == 'healthy'
after_ids = {row['id'] for row in after['images']}
assert all(row['id'] in after_ids for row in plan['protected_images'])
assert not after_ids.intersection(targets)
save('COMPLETED')
print(json.dumps({'status': 'COMPLETED', 'removed': len(operations), 'remaining_images': len(after_ids)}), flush=True)
