"""Pure regressions; no Docker, SQL, product runtime or release build."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import copy
import unittest
from unittest.mock import patch
from collections import namedtuple

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_storage', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence = Path(self.temp.name) / 'audit.json'
        self.prod, self.rollback, self.old = ['sha256:' + char * 64 for char in 'abc']
        self.now = storage.RETENTION_SECONDS + 1
        def document(name, data, role=None):
            path = Path(self.temp.name) / name
            path.write_text(json.dumps(data))
            return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **({'role': role} if role else {})}
        self.document = document
        self.manifest_ref = document('running.json', {'image_id': self.prod, 'source_sha256': 'd' * 64}, 'running_manifest')
        self.comparison_ref = document('delivery.json', {'candidate_image_id': self.old,
            'delivered_to_image_id': self.prod, 'delivered_source_sha256': 'd' * 64,
            'candidate_source_sha256': 'e' * 64, 'coverage': 'FULL_CANDIDATE_FEATURES',
            'feature_ids': ['feature-1']}, 'delivery_comparison')
        self.evidence.write_text(json.dumps({'accepted': True, 'image_id': self.old,
            'disposition': 'SUPERSEDED_DELIVERED', 'delivered_to_image_id': self.prod,
            'feature_delivery_evidence': [self.manifest_ref, self.comparison_ref]}))
        def receipt(identity):
            return {'image_id': identity, 'status': 'PASS', 'checks': [
                {'name': name, 'exit_code': 0} for name in storage.REQUIRED_CHECKS],
                'verification_sha256': '1' * 64, 'initial_source_sha256': '2' * 64,
                'release': {'source_sha256': '2' * 64}}
        self.snapshot = {'inventory_complete': True, 'receipt_inventory_complete': True,
            'production_image_id': self.prod, 'rollback_image_id': self.rollback,
            'container_inventory_complete': True, 'container_image_ids': [self.prod],
            'container_inventory_evidence': document('containers.json', {'schema': 'nis-container-inventory-v1',
                'engine_id': 'audited-test-engine', 'captured_epoch': self.now,
                'containers': [{'name': 'NetworkIS', 'container_id': 'f' * 64, 'image_id': self.prod}]}),
            'receipts': [receipt(i) for i in (self.prod, self.rollback, self.old)],
            'images': [{'image_id': i, 'created_epoch': 0, 'audit_disposition': 'SUPERSEDED_DELIVERED',
                'audit_evidence_path': str(self.evidence),
                'audit_evidence_sha256': hashlib.sha256(self.evidence.read_bytes()).hexdigest()}
                for i in (self.prod, self.rollback, self.old)]}

    def plan(self):
        return storage.retention_plan(self.snapshot, now=self.now)

    def test_only_audited_aged_superseded_pass_is_eligible(self):
        self.assertEqual([x['image_id'] for x in self.plan()['eligible']], [self.old])

    def test_fail_prepared_active_unknown_and_incomplete_pass_protected(self):
        for status in ('PREPARED', 'RUNNING', 'UNKNOWN'):
            with self.subTest(status=status):
                self.snapshot['receipts'][-1]['status'] = status
                self.assertEqual(self.plan()['eligible'], [])
        self.snapshot['receipts'][-1]['status'] = 'PASS'
        self.snapshot['receipts'][-1]['checks'].pop()
        self.assertEqual(self.plan()['eligible'], [])

    def test_container_including_stopped_and_undelivered_protected(self):
        self.snapshot['container_image_ids'] = [self.prod, self.old]
        self.assertEqual(self.plan()['eligible'], [])
        self.snapshot['container_image_ids'] = [self.prod]
        for disposition in ('UNDELIVERED', None, 'UNKNOWN'):
            self.snapshot['images'][-1]['audit_disposition'] = disposition
            self.assertEqual(self.plan()['eligible'], [])

    def test_missing_inventory_rollback_or_changed_audit_blocks(self):
        for field in ('inventory_complete', 'receipt_inventory_complete'):
            self.snapshot[field] = False
            self.assertEqual(self.plan()['eligible'], [])
            self.snapshot[field] = True
        self.snapshot['rollback_image_id'] = self.old + 'invalid'
        self.assertEqual(self.plan()['eligible'], [])

    def test_dsr01_omitted_malformed_stale_or_unbound_container_inventory_blocks(self):
        original = self.snapshot.copy()
        for field in ('container_image_ids', 'container_inventory_complete', 'container_inventory_evidence'):
            self.snapshot = original.copy()
            del self.snapshot[field]
            self.assertEqual(self.plan()['eligible'], [])
        for bad in (None, ' ', {}, ['bad-id']):
            self.snapshot = original.copy()
            self.snapshot['container_image_ids'] = bad
            self.assertEqual(self.plan()['eligible'], [])
        self.snapshot = original.copy()
        self.snapshot['container_inventory_evidence'] = self.document('stale.json',
            {'schema': 'nis-container-inventory-v1', 'engine_id': 'engine',
             'captured_epoch': self.now - 301, 'containers': []})
        self.assertEqual(self.plan()['eligible'], [])

    def test_dsr02_invalid_created_and_now_never_eligible(self):
        for bad in (float('nan'), float('-inf'), float('inf'), True, False, -1, '0', None, 10**1000):
            with self.subTest(created=bad):
                self.snapshot['images'][-1]['created_epoch'] = bad
                self.assertEqual(self.plan()['eligible'], [])
        self.snapshot['images'][-1]['created_epoch'] = self.now + 1
        self.assertEqual(self.plan()['eligible'], [])
        self.snapshot['images'][-1]['created_epoch'] = 0
        for bad in (float('nan'), float('-inf'), float('inf'), True, -1):
            self.assertEqual(storage.retention_plan(self.snapshot, now=bad)['eligible'], [])

    def update_audit(self, **changes):
        audit = json.loads(self.evidence.read_text())
        audit.update(changes)
        self.evidence.write_text(json.dumps(audit))
        self.snapshot['images'][-1]['audit_evidence_sha256'] = hashlib.sha256(self.evidence.read_bytes()).hexdigest()

    def test_dsr03_malformed_delivery_evidence_never_eligible(self):
        for bad in (' ', 'source comparison', [], {}, [True], [{'role': 'running_manifest'}]):
            self.update_audit(feature_delivery_evidence=bad)
            self.assertEqual(self.plan()['eligible'], [])
        self.update_audit(feature_delivery_evidence=[self.manifest_ref, self.comparison_ref],
                          delivered_to_image_id=self.rollback)
        self.assertEqual(self.plan()['eligible'], [])
        self.update_audit(delivered_to_image_id=self.prod)
        self.assertEqual([x['image_id'] for x in self.plan()['eligible']], [self.old])
        Path(self.manifest_ref['path']).write_text('changed actual running manifest')
        self.assertEqual(self.plan()['eligible'], [])

    def test_delivery_comparison_must_correlate_candidate_and_running_source(self):
        for field, bad in (('candidate_image_id', self.rollback), ('delivered_to_image_id', self.rollback),
                           ('delivered_source_sha256', '0' * 64), ('candidate_source_sha256', 'unknown'),
                           ('coverage', 'PARTIAL'), ('feature_ids', [' '])):
            data = json.loads(Path(self.comparison_ref['path']).read_text())
            original = data.copy()
            data[field] = bad
            ref = self.document('delivery.json', data, 'delivery_comparison')
            self.update_audit(feature_delivery_evidence=[self.manifest_ref, ref])
            self.assertEqual(self.plan()['eligible'], [])
            self.comparison_ref = self.document('delivery.json', original, 'delivery_comparison')
        self.snapshot['rollback_image_id'] = self.rollback
        self.evidence.write_text('changed')
        self.assertEqual(self.plan()['eligible'], [])

    def test_recent_protected_and_fail_requires_accepted_delivery_audit(self):
        self.snapshot['images'][-1]['created_epoch'] = storage.RETENTION_SECONDS
        self.assertEqual(self.plan()['eligible'], [])
        self.snapshot['images'][-1]['created_epoch'] = 0
        self.snapshot['receipts'].append({'image_id': self.old, 'status': 'FAIL'})
        self.assertEqual([x['image_id'] for x in self.plan()['eligible']], [self.old])
        self.snapshot['images'][-1]['audit_disposition'] = 'UNDELIVERED'
        self.assertEqual(self.plan()['eligible'], [])

    def test_cache_proposal_refuses_shared_builder(self):
        for builder in ('default', 'desktop-linux', '', 'nis-;bad'):
            with self.assertRaises(ValueError):
                storage.cache_cleanup_proposal(builder)
        command = storage.cache_cleanup_proposal('nis-release')
        self.assertIn('--max-used-space', command)
        self.assertNotIn('--force', command)

    def test_disk_guard_rejects_low_space_and_cannot_be_lowered(self):
        Usage = namedtuple('Usage', 'total used free')
        self.assertFalse(storage.disk_readiness([ROOT], disk_usage=lambda _: Usage(100, 99, 1))['ready'])
        self.assertTrue(storage.disk_readiness([ROOT], disk_usage=lambda _: Usage(100, 0, 30 * 1024**3))['ready'])
        with self.assertRaises(ValueError):
            storage.disk_readiness([ROOT], minimum_bytes=1)

    def test_image_budget_counts_ids_not_aliases_and_blocks_new_accumulation(self):
        self.assertTrue(storage.image_budget(['same'] * 261)['ready'])
        self.assertFalse(storage.image_budget([str(i) for i in range(100)])['ready'])

    def test_dsr04_invalid_hashes_codes_duplicate_checks_and_commits_protect(self):
        baseline = copy.deepcopy(self.snapshot)
        mutations = []
        for field in ('verification_sha256', 'initial_source_sha256'):
            for bad in (' ', 'UNKNOWN', {}, None, True, 'g' * 64):
                mutations.append(lambda row, f=field, value=bad: row.update({f: value}))
        for bad in (False, 0.0, '0', None, 1):
            mutations.append(lambda row, value=bad: row['checks'][0].update(exit_code=value))
        mutations.append(lambda row: row['checks'].append({'name': 'backend-tests', 'exit_code': 1}))
        mutations.append(lambda row: row['checks'].append({'name': 'backend-tests', 'exit_code': 0}))
        mutations.append(lambda row: row.update(initial_commit_id='a' * 40, release={**row['release'], 'commit_id': 'b' * 40}))
        mutations.append(lambda row: row.update(initial_commit_id='UNKNOWN'))
        mutations.append(lambda row: row.update(initial_source_sha256='UNKNOWN', release={'source_sha256': 'UNKNOWN'}))
        for index in (1, -1):
            for mutation in mutations:
                self.snapshot = copy.deepcopy(baseline)
                mutation(self.snapshot['receipts'][index])
                self.assertFalse(storage.complete_pass(self.snapshot['receipts'][index]))
                self.assertEqual(self.plan()['eligible'], [])
        row = copy.deepcopy(baseline['receipts'][1])
        self.assertTrue(storage.complete_pass(row))  # Historical absent commit fields.
        row['initial_commit_id'] = 'a' * 40
        row['release']['commit_id'] = 'a' * 40
        self.assertTrue(storage.complete_pass(row))

    def test_dsr05_malformed_input_returns_structured_protected_plan(self):
        baseline = copy.deepcopy(self.snapshot)
        for bad in (None, [], True, 'UNKNOWN', {}):
            for collection in ('receipts', 'images'):
                self.snapshot = copy.deepcopy(baseline)
                self.snapshot[collection][-1] = bad
                result = self.plan()
                self.assertEqual(result['eligible'], [])
                self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse(storage.complete_pass(bad))
        for bad in (None, [], True, 'UNKNOWN'):
            result = storage.retention_plan(bad, now=self.now)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(result['eligible'], [])
        for field, bad in (('checks', None), ('checks', [None]), ('release', [])):
            self.snapshot = copy.deepcopy(baseline)
            self.snapshot['receipts'][1][field] = bad
            result = self.plan()
            self.assertEqual(result['eligible'], [])
            self.assertEqual(result['status'], 'BLOCKED')

    def test_context_excludes_entire_checker_and_preserves_manifest_inputs(self):
        # Simple whole-root patterns apply to every child, including future archives.
        rules = {line.strip() for line in (ROOT / '.dockerignore').read_text().splitlines()
                 if line.strip() and not line.startswith('#')}
        for folder in ('.tool-checker', 'tool-checker', 'reports', 'presentation_output', '.uv-cache', 'work'):
            self.assertIn(folder, rules)
        manifest_spec = importlib.util.spec_from_file_location('build_info', ROOT / 'scripts/write-build-info.py')
        info = importlib.util.module_from_spec(manifest_spec)
        manifest_spec.loader.exec_module(info)
        # Exercise the real manifest algorithm on an isolated miniature checkout;
        # host historical runtime trees are deliberately outside this regression.
        model = Path(self.temp.name) / 'checkout'
        (model / 'backend/app').mkdir(parents=True)
        (model / 'scripts').mkdir()
        (model / 'backend/app/core.py').write_text('runtime = 1')
        (model / 'scripts/release_storage.py').write_text('policy = 1')
        (model / '.dockerignore').write_text('.tool-checker\n')
        (model / '.tool-checker/repair').mkdir(parents=True)
        with patch.object(info, 'commit_identity', return_value='a' * 40):
            before = info.build_manifest(model)['source_sha256']
            (model / '.tool-checker/repair/evidence.json').write_text('evidence')
            self.assertEqual(before, info.build_manifest(model)['source_sha256'])
            (model / 'scripts/release_storage.py').write_text('policy = 2')
            self.assertNotEqual(before, info.build_manifest(model)['source_sha256'])
        for folder in ('backend', 'frontend', 'config', 'scripts', 'docs'):
            self.assertNotIn(folder, rules)
        self.assertIn('".dockerignore"', (ROOT / 'scripts/write-build-info.py').read_text())
        self.assertIn('"scripts/release_storage.py"', (ROOT / 'scripts/write-build-info.py').read_text())


if __name__ == '__main__':
    unittest.main()
