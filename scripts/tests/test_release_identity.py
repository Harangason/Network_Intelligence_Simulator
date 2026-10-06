"""Runtime bibliography and operator code must invalidate image reuse."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('release_identity', Path(__file__).resolve().parents[1] / 'write-build-info.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ReleaseIdentityTests(unittest.TestCase):
    def test_frontend_test_changes_retest_without_changing_the_application_image(self):
        gate_spec = importlib.util.spec_from_file_location('gate_identity', Path(__file__).resolve().parents[1] / 'run-release-gate.py')
        gate = importlib.util.module_from_spec(gate_spec)
        gate_spec.loader.exec_module(gate)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            test = root / 'frontend/src/features/example/lib/example.test.mjs'
            test.parent.mkdir(parents=True)
            test.write_text('assert.equal(value, 1)', encoding='utf-8')
            before_source = MODULE.build_manifest(root)['source_sha256']
            with patch.object(gate, 'ROOT', root):
                before_verification = gate.verification_manifest()
                test.write_text('assert.equal(value, 2)', encoding='utf-8')
                self.assertNotEqual(before_verification, gate.verification_manifest())
            self.assertEqual(before_source, MODULE.build_manifest(root)['source_sha256'])

    def test_bibliography_and_rights_changes_require_another_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'backend/nis/communication/services/source_metadata.json'
            source.parent.mkdir(parents=True)
            source.write_text('{"permission":"UNRESOLVED"}', encoding='utf-8')
            before = MODULE.build_manifest(root)['source_sha256']
            source.write_text('{"permission":"CONDITIONAL"}', encoding='utf-8')
            self.assertNotEqual(before, MODULE.build_manifest(root)['source_sha256'])

    def test_operator_clearance_code_changes_require_another_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'scripts/manage-technology-license.py'
            source.parent.mkdir(parents=True)
            source.write_text('print("require evidence")', encoding='utf-8')
            before = MODULE.build_manifest(root)['source_sha256']
            source.write_text('print("changed review policy")', encoding='utf-8')
            self.assertNotEqual(before, MODULE.build_manifest(root)['source_sha256'])

    def test_projection_generator_changes_require_a_new_tested_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            generator = root / 'scripts/build/project-vocabulary.py'
            generator.parent.mkdir(parents=True)
            generator.write_text('projection = "canonical"', encoding='utf-8')
            before = MODULE.build_manifest(root)['source_sha256']
            generator.write_text('projection = "changed"', encoding='utf-8')
            self.assertNotEqual(before, MODULE.build_manifest(root)['source_sha256'])
            artifact = root / 'backend/build/lib/backend/generated.py'
            artifact.parent.mkdir(parents=True)
            stable = MODULE.build_manifest(root)['source_sha256']
            artifact.write_text('temporary wheel artifact', encoding='utf-8')
            self.assertEqual(stable, MODULE.build_manifest(root)['source_sha256'])

    def test_generated_build_info_is_not_an_identity_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = MODULE.build_manifest(root)['source_sha256']
            generated = root / 'backend/nis/app/build-info.json'
            generated.parent.mkdir(parents=True)
            generated.write_text('{"built_at":"changing timestamp"}', encoding='utf-8')
            self.assertEqual(before, MODULE.build_manifest(root)['source_sha256'])

if __name__ == '__main__':
    unittest.main()
