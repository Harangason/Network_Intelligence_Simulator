"""Check production, rollback, every retained PASS and concurrent active work."""
import importlib.util
import json
from pathlib import Path
from datetime import datetime
import time
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
spec = importlib.util.spec_from_file_location('existing_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
spec = importlib.util.spec_from_file_location('retention_owner', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
initial = json.loads((OUT / 'inventory-before.json').read_text())
resolved = json.loads((OUT / 'resolved-images.json').read_text())
after = json.loads((OUT / 'inventory-after-extra.json').read_text())
plan = json.loads((OUT / 'additional-cleanup-plan.json').read_text())
extra = json.loads((OUT / 'old-diagnostic-removal.json').read_text())
retired = {row['id'] for row in plan['images']} | {extra['image']}
remaining = {row['id']: row for row in after['images']}
assert not retired.intersection(remaining)
for row in initial['images']:
    if row['id'] not in retired:
        assert row['id'] in remaining and row['tags'] == remaining[row['id']]['tags']
cs = prior.containers()
for name in ('NetworkIS', 'NetworkIS-db'):
    original = next(row for row in initial['containers'] if row['name'] == name)
    current = next(row for row in cs if row['name'] == name)
    assert (current['id'], current['image'], current['mounts']) == (original['id'], original['image'], original['mounts'])
    assert current['state'] == 'running' and current['health'] == 'healthy'
assert not any(row['name'] == 'compassionate_stonebraker' for row in cs), 'Own transient read probe cleanup is not complete'
passes = []
for row in resolved['images']:
    if row['complete_pass_receipts']:
        assert row['id'] in remaining
        for path in row['complete_pass_receipts']:
            assert storage.complete_pass(json.loads(Path(path).read_text(encoding='utf-8-sig')))
        passes.append(row['id'])
assert len(passes) == 42
assert initial['rollback'] in passes
active = json.loads((ROOT / 'backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d/6d41919070e2/receipt.json').read_text())
assert active['image_id'] in remaining
app = next(row for row in cs if row['name'] == active['containers']['app'])
db = next(row for row in cs if row['name'] == active['containers']['db'])
assert app['image'] == active['image_id'] and app['state'] == db['state'] == 'running'
health = {}
for path in ('/api/ready', '/api/build-info'):
    with urlopen('http://127.0.0.1:13500' + path, timeout=10) as response:
        assert response.status == 200
        health[path] = json.load(response)
result = {'status': 'PASSED', 'production_image': initial['production']['image'],
    'rollback_image': initial['rollback'], 'production_container_and_database_storage_unchanged': True,
    'all_complete_pass_images_preserved': len(passes), 'all_unretired_original_tags_preserved': True,
    'new_active_candidate_preserved': active['image_id'], 'own_read_probe_container_removed': True,
    'retired_images': len(retired), 'remaining_images': len(remaining), 'health': health}
prior.write('production-and-rollback-after.json', result)
# Evaluate the real current engine inventory, including the concurrently built
# candidate, rather than calling the initial 73-image question scope complete.
receipt_roots = [Path(path) for path in resolved['receipt_roots']]
receipts, errors = [], []
for root in receipt_roots:
    if not root.exists():
        continue
    for path in root.rglob('*receipt*.json'):
        if any(part in {'before', 'after', '.venv', 'node_modules', 'second-pass', 'retired-receipts'} for part in path.parts):
            continue
        try:
            row = json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(row, dict) and row.get('status') in {'PASS', 'FAIL', 'PREPARED', 'RUNNING'}:
                receipts.append(row)
        except (OSError, ValueError) as error:
            errors.append({'path': str(path), 'error': str(error)})
bound = []
for image in after['images']:
    related = []
    for receipt in receipts:
        if receipt.get('image_id') == image['id']:
            related.append(receipt)
        elif (not receipt.get('image_id') and receipt.get('image_tag') in image['tags']
                and receipt.get('initial_source_sha256') == image['labels'].get('networkis.release.source')):
            related.append({**receipt, 'image_id': image['id']})
    bound.extend(related or [{'image_id': image['id'], 'status': 'UNKNOWN'}])
now = time.time()
container_path = prior.write('post-cleanup-container-inventory.json', {
    'schema': 'nis-container-inventory-v1', 'engine_id': prior.call('info', '--format', '{{.ID}}'),
    'captured_epoch': now,
    'containers': [{'name': row['name'], 'container_id': row['id'], 'image_id': row['image']} for row in cs]})
snapshot = {'inventory_complete': True, 'receipt_inventory_complete': not errors,
    'production_image_id': initial['production']['image'], 'rollback_image_id': initial['rollback'],
    'container_inventory_complete': True, 'container_image_ids': sorted({row['image'] for row in cs}),
    'container_inventory_evidence': prior.ref(container_path), 'receipts': bound,
    'images': [{'image_id': row['id'], 'created_epoch': datetime.fromisoformat(row['created'].replace('Z', '+00:00')).timestamp(),
                'audit_disposition': 'UNCLASSIFIED_FEATURE_DELIVERY'} for row in after['images']]}
prior.write('post-cleanup-policy-snapshot.json', snapshot)
post_policy = storage.retention_plan(snapshot, now=now)
assert not post_policy['blockers'] and not post_policy['eligible']
prior.write('post-cleanup-policy-result.json', post_policy)
prior.write('receipt-inventory-completeness.json', {'receipt_roots': list(map(str, receipt_roots)),
    'release_receipts_read': len(receipts), 'errors': errors, 'current_images': len(after['images'])})
# Preserve the initial-scope evaluation as preliminary, not a complete live
# engine snapshot now that a new image was built in a concurrent workflow.
pre_path = OUT / 'retention-policy-snapshot.json'
pre = json.loads(pre_path.read_text())
pre['inventory_complete'] = False
pre['scope_note'] = 'Initial 73-image question scope only; superseded for live-engine decisions by post-cleanup-policy-snapshot.json, including the concurrent new candidate.'
prior.write(pre_path.name, pre)
preliminary = storage.retention_plan(pre, now=pre['container_inventory_evidence'] and json.loads(Path(pre['container_inventory_evidence']['path']).read_text())['captured_epoch'])
prior.write('ordinary-retention-policy-result.json', preliminary)
print(json.dumps({k: v for k, v in result.items() if k != 'health'}), flush=True)
