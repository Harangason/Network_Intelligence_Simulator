"""Host-only regressions: concurrency, retained stacks and exact-source reuse."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('lifecycle_delivery', ROOT / 'scripts/release-and-deploy.py')
DELIVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELIVERY)


class LifecycleTests(unittest.TestCase):
    def gate(self):
        spec = importlib.util.spec_from_file_location('lifecycle_gate', ROOT / 'scripts/run-release-gate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_prepare_reuse_returns_before_receipt_creation_or_build(self):
        gate = self.gate()
        delivery = MagicMock()
        delivery.receipt_paths.return_value = []
        delivery.prepared_stack.return_value = (Path('existing/receipt.json'), {'base_url': 'http://127.0.0.1:12345'})
        info = SimpleNamespace(build_manifest=lambda: {'source_sha256': 's', 'commit_id': 'c'})
        isolation = SimpleNamespace(docker_executable=lambda: 'docker')
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        with (patch.object(sys, 'argv', ['run-release-gate.py', '--prepare']),
              patch.object(gate.importlib.util, 'spec_from_file_location', return_value=spec),
              patch.object(gate.importlib.util, 'module_from_spec', side_effect=[isolation, info]),
              patch.object(gate.secrets, 'token_hex') as token,
              patch.object(gate.subprocess, 'run') as mutate,
              patch('builtins.print') as output):
            self.assertEqual(gate.run_gate(delivery), 0)
            self.assertTrue(json.loads(output.call_args.args[0])['reused_stack'])
            token.assert_not_called()
            mutate.assert_not_called()
            delivery.reusable_image.assert_not_called()

    def test_retained_stack_rejection_precedes_build_and_any_receipt(self):
        gate = self.gate()
        delivery = MagicMock()
        delivery.receipt_paths.return_value = []
        delivery.prepared_stack.side_effect = RuntimeError('existing retained stack')
        info = SimpleNamespace(build_manifest=lambda: {'source_sha256': 's', 'commit_id': 'c'})
        isolation = SimpleNamespace(docker_executable=lambda: 'docker')
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        with (patch.object(sys, 'argv', ['run-release-gate.py', '--prepare']),
              patch.object(gate.importlib.util, 'spec_from_file_location', return_value=spec),
              patch.object(gate.importlib.util, 'module_from_spec', side_effect=[isolation, info]),
              patch.object(gate.secrets, 'token_hex') as token,
              patch.object(gate.subprocess, 'run') as mutate):
            with self.assertRaisesRegex(RuntimeError, 'existing retained stack'):
                gate.run_gate(delivery)
            token.assert_not_called()
            mutate.assert_not_called()

    def test_host_orchestration_changes_verification_without_application_rebuild(self):
        gate = self.gate()
        spec = importlib.util.spec_from_file_location('lifecycle_info', ROOT / 'scripts/write-build-info.py')
        info = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(info)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / 'scripts/release/run-release-gate.py'
            script.parent.mkdir(parents=True)
            script.write_text('version = 1')
            source = info.build_manifest(root)['source_sha256']
            with patch.object(gate, 'ROOT', root):
                verification = gate.verification_manifest()
                script.write_text('version = 2')
                self.assertNotEqual(verification, gate.verification_manifest())
            self.assertEqual(source, info.build_manifest(root)['source_sha256'])

    def test_second_process_is_blocked_and_lock_is_released_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = ("import importlib.util; from pathlib import Path; "
                    "s=importlib.util.spec_from_file_location('delivery'," + repr(str(ROOT / 'scripts/release-and-deploy.py')) + "); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "\nwith m.gate_lock(Path(" + repr(folder) + ")): print('acquired')")
            with self.assertRaisesRegex(ValueError, 'test failure'):
                with DELIVERY.gate_lock(root):
                    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('checkout lock', result.stderr)
                    raise ValueError('test failure')
            result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('acquired', result.stdout)

    def test_stopped_or_unknown_stack_blocks_before_any_docker_mutation(self):
        with patch.object(DELIVERY.subprocess, 'check_output', side_effect=[
                'a\nb', json.dumps([{'Name': '/nis-e2e-app-old'}, {'Name': '/nis-e2e-db-old'}])]) as run:
            with self.assertRaisesRegex(RuntimeError, 'retained test stack'):
                DELIVERY.prepared_stack('docker', [], 's', 'c', prepare=True, keep=False, ai_url='ai')
            self.assertEqual([c.args[0][1] for c in run.call_args_list], ['ps', 'inspect'])

    def test_orphan_volume_blocks_new_prepare(self):
        with patch.object(DELIVERY.subprocess, 'check_output', side_effect=['', 'nis-e2e-runtime-old']):
            with self.assertRaisesRegex(RuntimeError, 'without containers'):
                DELIVERY.prepared_stack('docker', [], 's', 'c', prepare=True, keep=False, ai_url='ai')

    def test_transient_full_gate_does_not_reuse_or_touch_retained_stack(self):
        with patch.object(DELIVERY.subprocess, 'check_output') as run:
            self.assertIsNone(DELIVERY.prepared_stack('docker', [], 's', 'c', prepare=False, keep=False, ai_url='ai'))
            run.assert_not_called()

    def test_failed_cleanup_blocks_full_gate_until_exact_resources_are_gone(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'receipt.json'
            path.write_text(json.dumps({'cleanup_incomplete': True,
                                        'containers': {'app': 'nis-e2e-app-failed', 'runtime': 'nis-e2e-runtime-failed'}}))
            for inventory in (['nis-e2e-app-failed'], ['', 'nis-e2e-runtime-failed']):
                with patch.object(DELIVERY.subprocess, 'check_output', side_effect=inventory):
                    with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'):
                        DELIVERY.prepared_stack('docker', [path], 's', 'c', prepare=False, keep=False, ai_url='ai')
            with patch.object(DELIVERY.subprocess, 'check_output', side_effect=['unrelated', '', '']):
                self.assertIsNone(DELIVERY.prepared_stack('docker', [path], 's', 'c', prepare=False, keep=False, ai_url='ai'))

    def test_identical_healthy_stack_is_reused_but_source_or_ai_drift_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'receipt.json'
            receipt = {'status': 'PREPARED', 'initial_source_sha256': 's', 'initial_commit_id': 'c',
                       'image_id': 'sha256:image', 'containers': {'app': 'nis-e2e-app-a', 'db': 'nis-e2e-db-a',
                           'network': 'nis-e2e-network-a', 'runtime': 'nis-e2e-runtime-a'},
                       'base_url': 'http://127.0.0.1:12345'}
            path.write_text(json.dumps(receipt), encoding='utf-8')
            app = {'Name': '/nis-e2e-app-a', 'Image': 'sha256:image', 'State': {'Status': 'running'},
                   'Config': {'Labels': {'networkis.test': 'disposable'}, 'Env': ['LOCAL_AI_BASE_URL=ai',
                       'DATABASE_URL=postgresql://nis_test:secret@test-db:5432/nis_test_e2e']},
                   'Mounts': [{'Name': 'nis-e2e-runtime-a', 'Destination': '/app/var/data'}],
                   'NetworkSettings': {'Networks': {'nis-e2e-network-a': {}},
                       'Ports': {'13500/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '12345'}]}}}
            db = {**app, 'Name': '/nis-e2e-db-a'}
            for source, ai_url, allowed in [('s', 'ai', True), ('different', 'ai', False), ('s', 'other', False)]:
                ready = io.StringIO('{}')
                ready.status = 200
                live = io.StringIO(json.dumps({'source_sha256': 's', 'commit_id': 'c'}))
                with (patch.object(DELIVERY.subprocess, 'check_output', side_effect=['a\nb', json.dumps([app, db])]),
                      patch.object(DELIVERY, 'urlopen', side_effect=[ready, live])):
                    if allowed:
                        self.assertEqual(DELIVERY.prepared_stack('docker', [path], source, 'c', prepare=True, keep=False, ai_url=ai_url), (path, receipt))
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'retained test stack'):
                            DELIVERY.prepared_stack('docker', [path], source, 'c', prepare=True, keep=False, ai_url=ai_url)
            for changes in ({'image': 'sha256:other'}, {'development_base': 'different'}):
                with patch.object(DELIVERY.subprocess, 'check_output', side_effect=['a\nb', json.dumps([app, db])]):
                    with self.assertRaisesRegex(RuntimeError, 'retained test stack'):
                        DELIVERY.prepared_stack('docker', [path], 's', 'c', prepare=True, keep=False, ai_url='ai', **changes)
            app['Config']['Env'][-1] = 'DATABASE_URL=postgresql://nis_test:secret@production-db:5432/nis_test_e2e'
            with patch.object(DELIVERY.subprocess, 'check_output', side_effect=['a\nb', json.dumps([app, db])]):
                with self.assertRaisesRegex(RuntimeError, 'retained test stack'):
                    DELIVERY.prepared_stack('docker', [path], 's', 'c', prepare=True, keep=False, ai_url='ai')

    def test_prepared_image_reused_but_development_retired_or_missing_never_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'receipt.json'
            baseline = {'status': 'PREPARED', 'initial_source_sha256': 's', 'initial_commit_id': 'c',
                        'image_id': 'sha256:' + 'a' * 64}
            for extra, allowed in [({}, True), ({'development_only': True}, False),
                                   ({'stack_retirement': {'status': 'ARCHIVED'}}, False),
                                   ({'initial_source_sha256': 'other'}, False)]:
                path.write_text(json.dumps({**baseline, **extra}), encoding='utf-8')
                with (patch.object(DELIVERY, 'load_module') as load,
                      patch.object(DELIVERY.subprocess, 'run') as run):
                    load.return_value.docker_executable.return_value = 'docker'
                    run.return_value.returncode = 0
                    run.return_value.stdout = baseline['image_id']
                    self.assertEqual(DELIVERY.reusable_image([path], 's', 'c'), baseline['image_id'] if allowed else None)
            path.write_text(json.dumps(baseline), encoding='utf-8')
            with patch.object(DELIVERY, 'load_module'), patch.object(DELIVERY.subprocess, 'run') as run:
                run.return_value.returncode = 1
                self.assertIsNone(DELIVERY.reusable_image([path], 's', 'c'))


if __name__ == '__main__':
    unittest.main()
