"""Archive only resolved unused non-PASS candidates for the additional cleanup."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('existing_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
ARCHIVES = prior.ARCHIVES / 'second-pass'


def plan():
    data = json.loads((OUT / 'resolved-images.json').read_text())
    original = json.loads((OUT / 'inventory-before.json').read_text())
    protected_ids = {original['production']['image'], original['rollback']}
    current = prior.containers()
    referenced = {row['image'] for row in current}
    targets, protected = [], []
    for row in data['images']:
        statuses = set(row['resolved_statuses'])
        if (statuses and statuses <= {'FAIL', 'PREPARED'} and not row['complete_pass_receipts']
                and row['id'] not in protected_ids | referenced
                and not any(r['binding'].startswith(('CONFLICT', 'UNVERIFIED')) for r in row['all_receipts'])):
            targets.append(row)
        else:
            protected.append(row)
    assert 24 <= len(targets) <= 25, [(r['tags'], r['resolved_statuses']) for r in targets]
    result = {'authorization': 'Explicit user follow-up: inspect which remaining images are actually needed and safely remove additional unused old candidates; preceding cleanup request remains authorized.',
              'scope': 'Resolved PREPARED/FAIL images only; all PASS, unresolved, RUNNING, production, rollback, container-referenced or newly built images are protected.',
              'images': targets, 'protected_images': protected, 'production': original['production'],
              'rollback': original['rollback'], 'resolved_inventory': prior.ref(OUT / 'resolved-images.json'),
              'no_feature_delivery_claim': True, 'no_receipt_status_rewriting': True}
    prior.write('additional-cleanup-plan.json', result)
    print(json.dumps({'targets': len(targets), 'protected_from_original_inventory': len(protected)}), flush=True)


def archive():
    plan = json.loads((OUT / 'additional-cleanup-plan.json').read_text())
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    assert shutil.disk_usage(ARCHIVES).free > sum(r['size'] for r in plan['images']) + 20 * 1024**3
    path = ARCHIVES / 'additional-unused-candidates.tar'
    if not path.exists():
        subprocess.run([prior.DOCKER, 'image', 'save', '--output', str(path),
                        *[r['tags'][0] for r in plan['images']]], check=True)
    audit = prior.verify_image_archive(path, plan['images'])
    for row in plan['images']:
        for index, item in enumerate(row['all_receipts']):
            assert prior.ref(Path(item['path']))['sha256'] == item['sha256']
            prior.write('preserved-receipts/' + row['tags'][0].split(':')[1] + '-' + str(index) + '.json', item['data'])
    prior.write('additional-image-archive-audit.json', {**audit, 'plan': prior.ref(OUT / 'additional-cleanup-plan.json')})
    print(json.dumps({'archive_verified': len(plan['images']), 'bytes': path.stat().st_size,
                      'verified_blobs': len(audit['verified_blobs'])}), flush=True)


if __name__ == '__main__':
    import sys
    {'plan': plan, 'archive': archive}[sys.argv[1]]()
