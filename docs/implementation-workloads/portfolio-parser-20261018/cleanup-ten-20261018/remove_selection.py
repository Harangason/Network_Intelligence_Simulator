"""Remove only the ten explicitly requested, verified archived hot copies.

No containers, volumes, archives, build caches or other images are removed.
This is a bounded current user-directed operation, not automatic retention.
"""
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from archive_selection import ARCHIVE, DOCKER, OUT, ROOT, TAGS, call, inventory, ref


def main():
    audit_path = OUT / 'archive-audit.json'
    audit = json.loads(audit_path.read_text())
    assert audit['status'] == 'ARCHIVED_VERIFIED_NO_REMOVALS'
    assert ref(ARCHIVE) == audit['archive'], 'Recovery archive must still be byte-identical.'
    assert len(audit['images']) == 10 and all(r['index_verified'] and r['config_verified'] and r['all_layers_verified'] for r in audit['images'])
    selected, observed = inventory()
    selected_ids = {r['image_id'] for r in selected}
    assert selected_ids == {r['image_id'] for r in audit['images']}
    assert set(TAGS) == {r['tag'] for r in audit['images']}
    assert 'sha256:09d1f624dfddd6fae124e5728c0216785f79576f2a2169feef8a89c53748c478' not in selected_ids
    # All historical receipt roots are checked again, including development runs.
    receipt_evidence = []
    for parent in [ROOT / 'backend/test-output', ROOT / 'work']:
        for path in parent.rglob('receipt.json'):
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
            if receipt.get('image_id') in selected_ids:
                assert receipt['status'] == 'PASS' and receipt.get('development_only', False) is False
                receipt_evidence.append({**ref(path), 'image_id': receipt['image_id'], 'status': receipt['status']})
    assert selected_ids == {r['image_id'] for r in receipt_evidence}
    initial_ids = set(call('image', 'ls', 'networkis', '-q', '--no-trunc').split())
    assert len(initial_ids) == 100
    before = {'at_utc': datetime.now(timezone.utc).isoformat(),
              'authorization': {'source': 'Direct human message in this chat on 2026-10-18',
                                'verbatim': '10 überflüssige Images löschen und die fehlenden Punkte abarbeiten',
                                'scope': 'Exactly ten old unused complete-PASS historical NIS image copies; full recoverable archive preserved. No production, rollback, container, volume, unknown or active candidate removal.'},
              'mode': 'CURRENT_HUMAN_DIRECTED_ARCHIVED_COPY_CLEANUP',
              'automatic_retention_eligibility_claimed': False,
              'full_feature_delivery_equivalence_claimed': False,
              'recovery_of_complete_candidate_contents': audit['archive'],
              'archive_audit': ref(audit_path), 'selected': selected,
              'receipt_inventory': receipt_evidence, 'observed': observed,
              'initial_image_count': len(initial_ids), 'commands': [[DOCKER, 'image', 'rm', '--no-prune', r['tags'][0]] for r in selected]}
    (OUT / 'fresh-removal-audit.json').write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    removed = []
    for row in selected:
        cids = call('ps', '-aq', '--no-trunc').split()
        cs = json.loads(call('inspect', *cids)) if cids else []
        assert row['image_id'] not in {c['Image'] for c in cs}
        assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == observed['production']
        im = json.loads(call('image', 'inspect', row['tags'][0]))[0]
        assert im['Id'] == row['image_id'] and im['RepoTags'] == row['tags']
        current_ids = set(call('image', 'ls', 'networkis', '-q', '--no-trunc').split())
        assert current_ids == initial_ids - {r['image_id'] for r in removed}
        result = subprocess.run([DOCKER, 'image', 'rm', '--no-prune', row['tags'][0]], capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stderr
        removed.append({'image_id': row['image_id'], 'tag': row['tags'][0], 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        (OUT / 'removal-progress.json').write_text(json.dumps({'removed': removed}, indent=2) + '\n', encoding='utf-8')
        print('Removed archived copy ' + row['tags'][0], flush=True)
    final_ids = set(call('image', 'ls', 'networkis', '-q', '--no-trunc').split())
    assert final_ids == initial_ids - selected_ids and len(final_ids) == 90
    cids = call('ps', '-aq', '--no-trunc').split()
    cs = json.loads(call('inspect', *cids)) if cids else []
    old_containers = {r['id']: r['image_id'] for r in observed['containers']}
    assert all(old_containers[c['Id']] == c['Image'] for c in cs if c['Id'] in old_containers)
    assert set(old_containers) <= {c['Id'] for c in cs}, 'No old container may be removed.'
    assert call('inspect', 'NetworkIS', '--format', '{{.Image}}') == observed['production']
    result = {'status': 'TEN_ARCHIVED_UNUSED_IMAGE_COPIES_REMOVED', 'at_utc': datetime.now(timezone.utc).isoformat(),
              'removed': removed, 'image_count_before': len(initial_ids), 'image_count_after': len(final_ids),
              'archive': audit['archive'], 'fresh_audit': ref(OUT / 'fresh-removal-audit.json'),
              'production': observed['production'], 'production_health': call('inspect', 'NetworkIS', '--format', '{{.State.Health.Status}}'),
              'all_existing_containers_preserved': True, 'other_networkis_images_preserved': True,
              'force_used': False, 'pruning_used': False, 'new_correction_delivered': False}
    (OUT / 'removal-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['status', 'image_count_before', 'image_count_after', 'production_health']}), flush=True)


if __name__ == '__main__':
    main()
