"""A directory migration cannot silently remove frontend release coverage."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('frontend_release_gate', Path(__file__).resolve().parents[1] / 'run-release-gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class FrontendDiscoveryTests(unittest.TestCase):
    def test_features_shared_and_nested_tests_are_all_discovered(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = ['src/features/agent/lib/catalogs/catalog.test.mjs',
                        'src/features/sources/lib/source-directory.test.mjs',
                        'src/shared/api/api.test.mjs']
            for name in expected + ['src/features/sources/lib/source-directory.ts']:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('')
            self.assertEqual(GATE.frontend_test_files(root), expected)

    def test_empty_discovery_refuses_a_release_run(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'empty release test run'):
                GATE.frontend_test_files(Path(folder))
