"""Pure archive counterprobes; no Docker actions, SQL or original-model claim."""
import ast
from copy import deepcopy
import hashlib
import io
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import unittest

OPERATOR = Path('docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261021/inventory-binding-cardinality-repair/progress-decoder-repair/retire_obsolete_stack.py')


def current_verifier():
    tree = ast.parse(OPERATOR.read_text(encoding='utf8'))
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'verify_runtime_snapshot'), None)
    if function is None:
        # Execute the ACTUAL previous tar-verification statement in isolation.
        # Its missing coverage check must be observable, not fabricated as an
        # exception merely because a newly named helper is absent.
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        block = next(node for node in run.body if isinstance(node, ast.With)
                     and any(ast.unparse(item.context_expr) == 'tarfile.open(volume)' for item in node.items))
        function = ast.parse('def verify_runtime_snapshot(diff_text, volume):\n    pass\n').body[0]
        function.body = [deepcopy(block), ast.Return(value=ast.Name(id='members', ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {'tarfile': tarfile, 'hashlib': hashlib, 'PurePosixPath': PurePosixPath}
    exec(compile(module, str(OPERATOR), 'exec'), namespace)
    return namespace['verify_runtime_snapshot']


class RuntimeArchiveCoverage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nis-runtime-archive-counter-')
        self.path = Path(self.temp.name) / 'runtime.tar'
        self.verify = current_verifier()

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name='runtime/logs/backend.log'):
        payload = b'Independent native validation diagnostic\n'
        with tarfile.open(self.path, 'w') as archive:
            for directory in ('runtime', 'runtime/logs'):
                item = tarfile.TarInfo(directory)
                item.type = tarfile.DIRTYPE
                archive.addfile(item)
            item = tarfile.TarInfo(name)
            item.size = len(payload)
            archive.addfile(item, io.BytesIO(payload))
        return payload

    def test_volume_only_archive_cannot_satisfy_unmounted_log_coverage(self):
        self.archive('data/project-source.json')
        with self.assertRaises(ValueError):
            self.verify('A /app/var/runtime/logs/backend.log', self.path)

    def test_unknown_writable_data_blocks_retirement(self):
        self.archive()
        with self.assertRaises(ValueError):
            self.verify('A /outside-owned-runtime/private.data', self.path)

    def test_unrecorded_deleted_writable_path_blocks_retirement(self):
        self.archive()
        with self.assertRaises(ValueError):
            self.verify('D /app/var/runtime/logs/backend.log', self.path)

    def test_complete_runtime_archive_keeps_actual_file_hash(self):
        payload = self.archive()
        members = self.verify('C /app\nA /app/var\nA /app/var/data\nA /app/var/runtime\n'
            'A /app/var/runtime/logs\nA /app/var/runtime/logs/backend.log', self.path)
        backend = next(row for row in members if row['name'] == 'runtime/logs/backend.log')
        self.assertEqual(backend['bytes'], len(payload))
        self.assertEqual(backend['sha256'], hashlib.sha256(payload).hexdigest())


if __name__ == '__main__':
    unittest.main()
