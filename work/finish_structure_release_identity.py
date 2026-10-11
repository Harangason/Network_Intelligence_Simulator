from finish_structure_owners import *

path = 'scripts/build/project-vocabulary.py'
write(path, read(path).replace("proposal = review.get('rate_proposal') or profile.get('parameter_proposals') or {}", "proposal = profile.get('parameter_proposals') or {}"))
path = 'scripts/build/write-build-info.py'
source = read(path).replace('"generated", "build"}', '"generated"}')
source = source.replace('relative_parts[:2] == ("backend", "runtime"):', 'relative_parts[:2] in {("backend", "runtime"), ("backend", "build")}:')
write(path, source)
path = 'scripts/tests/test_release_identity.py'
source = read(path)
at = source.index('    def test_generated_build_info')
test = '''    def test_projection_generator_changes_require_a_new_tested_image(self):
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

'''
write(path, source[:at] + test + source[at:])
apply('build-generator-release-identity')
