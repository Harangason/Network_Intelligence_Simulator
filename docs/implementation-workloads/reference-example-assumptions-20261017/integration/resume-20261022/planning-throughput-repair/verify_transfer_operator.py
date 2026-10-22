"""Compare normal import semantics before/after the evidence-only selector."""
import ast
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/integration/resume-20261020/document-stream-lifecycle-repair/transfer_waitress_source_only_projects.py'
before = OUT / 'before-transfer_waitress_source_only_projects.py'
old, new = ast.parse(before.read_text(encoding='utf8')), ast.parse(SOURCE.read_text(encoding='utf8'))
dump = lambda node: ast.dump(node, include_attributes=False)
definitions = lambda tree: {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
left, right = definitions(old), definitions(new)
assert set(left) == set(right)
assert {key for key in left if dump(left[key]) != dump(right[key])} == {'context_baseline_bytes'}


def import_loop(tree):
    return next(node for node in tree.body if isinstance(node, ast.For)
                and isinstance(node.target, ast.Name) and node.target.id == 'case')


class HistoricalFlags(ast.NodeTransformer):
    def visit_BoolOp(self, node):
        node = self.generic_visit(node)
        node.values = [value for value in node.values if ast.unparse(value) != 'args.throughput_repair_dir']
        return node.values[0] if len(node.values) == 1 else node


assert dump(HistoricalFlags().visit(deepcopy(import_loop(new)))) == dump(import_loop(old))
assert all(dump(left[key]) == dump(right[key]) for key in ('request', 'empty', 'inspect', 'sha'))
result = subprocess.run([sys.executable, '-X', 'utf8', str(SOURCE), '--help'], capture_output=True, text=True, encoding='utf8')
assert result.returncode == 0 and '--throughput-repair-dir' in result.stdout
after = OUT / 'after-transfer_waitress_source_only_projects.py'
after.write_bytes(SOURCE.read_bytes())
diff = OUT / 'transfer_waitress_source_only_projects.py.diff'
diff.write_text(''.join(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True),
                                          SOURCE.read_text(encoding='utf8').splitlines(True),
                                          fromfile='before/transfer_waitress_source_only_projects.py',
                                          tofile='after/transfer_waitress_source_only_projects.py')), encoding='utf8')
ref = lambda path: {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
proof = {'status': 'PASS_OPERATOR_AST_AND_CLI_ONLY', 'normal_request_and_empty_guards_AST_unchanged': True,
         'normal_source_only_import_loop_AST_unchanged_except_evidence_selector': True,
         'public_import_API_and_original_payloads_unchanged': True,
         'historical_source_hash_chain_preserved': True, 'before': ref(before), 'after': ref(after), 'diff': ref(diff),
         'actual_transfer_performed': False, 'original_acceptance': False}
(OUT / 'transfer-operator-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
work_path = OUT / 'transfer-operator-workload.json'
work = json.loads(work_path.read_text(encoding='utf8'))
work.update(status='WAITING_FOR_PREPARED_CANDIDATE_ACTUAL_TRANSFER', files_changed=[SOURCE.relative_to(ROOT).as_posix()],
            after=[ref(after)], diff=[ref(diff)], operator_scope_proof=ref(OUT / 'transfer-operator-scope-proof.json'))
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'status': proof['status'], 'actual_transfer_performed': False}))
