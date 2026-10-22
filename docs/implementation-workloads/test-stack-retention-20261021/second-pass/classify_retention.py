"""Explicitly separate operational need from unresolved retention evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
spec = importlib.util.spec_from_file_location('existing_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
spec = importlib.util.spec_from_file_location('retention_owner', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
data = json.loads((OUT / 'resolved-images.json').read_text())
initial = json.loads((OUT / 'inventory-before.json').read_text())
plan = json.loads((OUT / 'additional-cleanup-plan.json').read_text())
targets = {r['id'] for r in plan['images']}
current = prior.containers()
container_ref = prior.write('container-inventory.json', {
    'schema': 'nis-container-inventory-v1', 'engine_id': initial['engine'], 'captured_epoch': time.time(),
    'containers': [{'name': r['name'], 'container_id': r['id'], 'image_id': r['image']} for r in current]})
all_receipts = []
for image in data['images']:
    for item in image['all_receipts']:
        if item['binding'] == 'EXACT_IMMUTABLE_ID':
            all_receipts.append(item['data'])
        elif item['binding'] == 'TAG_GATE_AND_SOURCE_NO_IMAGE_ID_IN_RECEIPT':
            # Audit-derived binding is separate; the original receipt is unchanged.
            all_receipts.append({**item['data'], 'image_id': image['id']})
    if not image['all_receipts']:
        all_receipts.append({'image_id': image['id'], 'status': 'UNKNOWN'})
snapshot = {
    'inventory_complete': True, 'receipt_inventory_complete': not data['errors'],
    'production_image_id': initial['production']['image'], 'rollback_image_id': initial['rollback'],
    'container_inventory_complete': True, 'container_image_ids': sorted(set(r['image'] for r in current)),
    'container_inventory_evidence': prior.ref(container_ref), 'receipts': all_receipts,
    'images': [{'image_id': image['id'], 'created_epoch': __import__('datetime').datetime.fromisoformat(
        image['created'].replace('Z', '+00:00')).timestamp(),
        'audit_disposition': 'UNCLASSIFIED_FEATURE_DELIVERY'} for image in data['images']],
}
prior.write('retention-policy-snapshot.json', snapshot)
ordinary = storage.retention_plan(snapshot, now=time.time())
prior.write('ordinary-retention-policy-result.json', ordinary)
policy = {r['image_id']: r for r in ordinary['protected'] + ordinary['eligible']}
roles = []
for image in data['images']:
    statuses = set(image['resolved_statuses'])
    if image['id'] == initial['production']['image']:
        role, need = 'PRODUCTION', True
    elif image['id'] == initial['rollback']:
        role, need = 'REQUIRED_VERIFIED_ROLLBACK', True
    elif image['id'] in targets:
        role, need = 'ADDITIONAL_UNUSED_NON_PASS_RETIREMENT', False
    elif image['complete_pass_receipts']:
        role, need = 'HISTORICAL_PASS_NO_RUNTIME_REFERENCE_DELIVERY_AUDIT_MISSING', False
    elif image['tags'][0].endswith('6d6fe881f4bd'):
        role, need = 'LATEST_OLD_DIAGNOSTIC_ALREADY_ARCHIVED_STACK_RETIRED', False
    elif statuses == {'RUNNING'}:
        role, need = 'HISTORICAL_INCOMPLETE_RECEIPT_NOT_PROVEN_TERMINAL', None
    else:
        role, need = 'RELEASE_STATUS_NOT_RESOLVED', None
    commits = sorted(set(row['data'].get('initial_commit_id') for row in image['all_receipts']
                         if row['data'].get('initial_commit_id')))
    ancestry = {}
    for commit in commits:
        result = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], capture_output=True)
        ancestry[commit] = {0: 'ANCESTOR', 1: 'NOT_ANCESTOR'}.get(result.returncode, 'UNAVAILABLE')
    roles.append({'image': image['id'], 'tag': image['tags'][0], 'created': image['created'],
                  'operationally_required': need, 'role': role, 'resolved_statuses': image['resolved_statuses'],
                  'complete_pass_receipts': image['complete_pass_receipts'],
                  'currently_referenced_by': [c['name'] for c in current if c['image'] == image['id']],
                  'source': image['labels'].get('networkis.release.source'),
                  'base_commit_ancestry_only_not_feature_delivery_proof': ancestry,
                  'ordinary_retention_reasons': policy[image['id']]['reasons'],
                  'receipt_evidence': [{k: r[k] for k in ('path', 'sha256', 'binding')} for r in image['all_receipts']]})
prior.write('image-roles-and-retention.json', {'captured_epoch': time.time(), 'roles': roles,
    'note': 'No runtime reference does not establish complete feature delivery. A Git ancestor or old PASS is not accepted as that proof.'})
summary = {role: sum(r['role'] == role for r in roles) for role in sorted(set(r['role'] for r in roles))}
prior.write('classification-summary.json', {'initial_images': len(roles), 'roles': summary,
    'ordinary_retention_eligible': len(ordinary['eligible']), 'ordinary_retention_blockers': ordinary['blockers']})
print(json.dumps({'roles': summary, 'ordinary_retention_eligible': len(ordinary['eligible']),
                  'ordinary_retention_blockers': ordinary['blockers']}), flush=True)
