"""Release delivery selection must never reuse unverified or stale candidates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_and_deploy', ROOT / 'scripts/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
deploy_spec = importlib.util.spec_from_file_location('deploy_verified_release', ROOT / 'scripts/deploy-verified-release.py')
deploy = importlib.util.module_from_spec(deploy_spec)
deploy_spec.loader.exec_module(deploy)


class CanonicalCheckoutGuardTests(unittest.TestCase):
    def test_direct_deployment_requires_exact_canonical_source_tests_and_commit(self):
        receipt = {
            'initial_source_sha256': 'a' * 64,
            'verification_sha256': 'b' * 64,
            'initial_commit_id': 'c' * 40,
            'release': {'commit_id': 'c' * 40},
        }
        deploy.verify_local_checkout(receipt, 'a' * 64, 'c' * 40, 'b' * 64)
        for identity in (('d' * 64, 'c' * 40, 'b' * 64),
                         ('a' * 64, 'c' * 40, 'd' * 64),
                         ('a' * 64, 'd' * 40, 'b' * 64)):
            with self.subTest(identity=identity), self.assertRaises(SystemExit):
                deploy.verify_local_checkout(receipt, *identity)


class DeliverySelectionTests(unittest.TestCase):
    def test_reuse_requires_complete_pass_and_matching_source_tests_and_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            receipt = {
                'status': 'PASS', 'development_only': False,
                'image_id': 'sha256:' + 'a' * 64,
                'initial_source_sha256': 'b' * 64,
                'initial_commit_id': 'c' * 40,
                'verification_sha256': 'd' * 64,
                'release': {'source_sha256': 'b' * 64, 'commit_id': 'c' * 40},
                'checks': [{'name': name, 'exit_code': 0} for name in
                           ('typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http')],
            }
            path.write_text(json.dumps(receipt), encoding='utf-8')
            select = lambda: delivery.matching_receipt([path], 'b' * 64, 'c' * 40, 'd' * 64)
            self.assertEqual(select()[0], path)
            self.assertIsNone(delivery.matching_receipt([path], 'e' * 64, 'c' * 40, 'd' * 64))
            self.assertIsNone(delivery.matching_receipt([path], 'b' * 64, 'e' * 40, 'd' * 64))
            self.assertIsNone(delivery.matching_receipt([path], 'b' * 64, 'c' * 40, 'e' * 64))
            receipt['checks'].pop()
            path.write_text(json.dumps(receipt), encoding='utf-8')
            self.assertIsNone(select())
            self.assertIsNone(delivery.matching_receipt([Path(temp) / 'missing.json'], 'b' * 64, 'c' * 40, 'd' * 64))

    def test_running_image_must_equal_receipt_before_http_checks(self):
        receipt = {'image_id': 'sha256:' + 'a' * 64, 'release': {'source_sha256': 'b' * 64}}
        with patch.object(delivery, 'load_module') as load, patch.object(delivery.subprocess, 'check_output') as inspect:
            load.return_value.docker_executable.return_value = 'docker'
            inspect.return_value = 'sha256:' + 'c' * 64
            with self.assertRaisesRegex(RuntimeError, 'differs from tested image'):
                delivery.verify_live(receipt)

    def test_recent_gate_for_same_source_prevents_duplicate_build(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            path.write_text(json.dumps({'status': 'RUNNING',
                                        'initial_source_sha256': 'b' * 64}), encoding='utf-8')
            self.assertEqual(delivery.active_gate([path], 'b' * 64, now=path.stat().st_mtime), path)
            self.assertIsNone(delivery.active_gate([path], 'c' * 64, now=path.stat().st_mtime))
            self.assertIsNone(delivery.active_gate([path], 'b' * 64,
                                                   now=path.stat().st_mtime + 2 * 60 * 60 + 1))
            path.write_text(json.dumps({'status': 'RUNNING', 'gate_pid': 99999999,
                                        'initial_source_sha256': 'b' * 64}), encoding='utf-8')
            with patch.object(delivery.os, 'kill', side_effect=ProcessLookupError):
                self.assertIsNone(delivery.active_gate([path], 'b' * 64, now=path.stat().st_mtime))

    def test_same_source_image_can_be_retested_without_building(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            image = 'sha256:' + 'a' * 64
            path.write_text(json.dumps({'status': 'PASS', 'image_id': image,
                                        'initial_source_sha256': 'b' * 64,
                                        'initial_commit_id': 'c' * 40}), encoding='utf-8')
            with patch.object(delivery, 'load_module') as load, patch.object(delivery.subprocess, 'run') as run:
                load.return_value.docker_executable.return_value = 'docker'
                run.return_value.returncode = 0
                run.return_value.stdout = image + '\n'
                self.assertEqual(delivery.reusable_image([path], 'b' * 64, 'c' * 40), image)
                self.assertIsNone(delivery.reusable_image([path], 'b' * 64, 'd' * 40))

    def test_matching_pass_deploys_without_running_another_gate(self):
        path = Path('existing/receipt.json')
        receipt = {'image_id': 'sha256:' + 'a' * 64,
                   'release': {'source_sha256': 'b' * 64}}
        with (patch.object(sys, 'argv', ['release-and-deploy.py']),
              patch.object(delivery, 'current_identity', return_value=('b' * 64, 'c' * 40, 'd' * 64)),
              patch.object(delivery, 'matching_receipt', return_value=(path, receipt)),
              patch.object(delivery.subprocess, 'run') as run,
              patch.object(delivery, 'verify_live', return_value={'image_id': receipt['image_id'], 'ready': {}}),
              patch('builtins.print')):
            delivery.main()
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('run-release-gate.py', ' '.join(map(str, run.call_args.args[0])))


if __name__ == '__main__':
    unittest.main()
