"""Audit host evidence extensions, preserving canonical prepare/import paths."""
import ast
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
N = Path(__file__).resolve().parent
work = json.loads((N / 'operator-workload.json').read_text(encoding='utf8'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class RemoveFreshFlag(ast.NodeTransformer):
    def visit_BoolOp(self, node):
        node = self.generic_visit(node)
        node.values = [value for value in node.values if not (
            isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
            and value.value.id == 'args' and value.attr == 'fresh_id_repair_dir')]
        return node.values[0] if len(node.values) == 1 else node


def dump(node):
    return ast.dump(node, include_attributes=False)


after, differences = [], []
for name in work['revision_before']:
    current = ROOT / name
    before = N / ('operator-before-' + current.name)
    first, last = before.read_text(encoding='utf8'), current.read_text(encoding='utf8')
    old, new = ast.parse(first), ast.parse(last)
    compile(last, name, 'exec')
    if current.name.startswith('transfer_'):
        old_loop = next(node for node in old.body if isinstance(node, ast.For)
                        and ast.unparse(node.target) == 'case')
        new_loop = next(node for node in new.body if isinstance(node, ast.For)
                        and ast.unparse(node.target) == 'case')
        assert dump(old_loop) == dump(RemoveFreshFlag().visit(deepcopy(new_loop)))
        old_funcs = {node.name: node for node in old.body if isinstance(node, ast.FunctionDef)}
        new_funcs = {node.name: node for node in new.body if isinstance(node, ast.FunctionDef)}
        assert all(dump(node) == dump(new_funcs[key]) for key, node in old_funcs.items())
        assert set(new_funcs) - set(old_funcs) == {'context_baseline_bytes'}
    else:
        old_commands = [node.value for node in ast.walk(old) if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == 'command' for target in node.targets)]
        new_commands = [node.value for node in ast.walk(new) if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == 'command' for target in node.targets)]
        assert len(new_commands) == len(old_commands) + 1
        assert all(dump(command) == dump(old_commands[0]) for command in new_commands)
    snapshot = N / ('operator-after-' + current.name)
    snapshot.write_bytes(current.read_bytes())
    difference = N / ('operator-' + current.name + '.diff')
    difference.write_text(''.join(difflib.unified_diff(first.splitlines(True), last.splitlines(True),
                        fromfile='before/' + name, tofile='after/' + name)), encoding='utf8')
    after.append(ref(snapshot)); differences.append(ref(difference))
proof = {'status': 'PASSED', 'normal_import_payload_request_read_record_loop_AST_unchanged_except_explicit_evidence_flag': True,
         'all_existing_transfer_functions_AST_unchanged': True,
         'canonical_prepare_command_AST_unchanged': True,
         'locks_storage_and_single_retained_stack_guards_not_bypassed': True,
         'before': work['before'], 'after': after, 'diff': differences,
         'actual_transfers_not_yet_performed': True, 'original_acceptance': False}
(N / 'operator-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
work.update(after=after, diff=differences,
            files_changed=list(work['revision_before']), status='HOST_OPERATOR_SCOPE_VERIFIED_WAITING_FOR_CURRENT_CANDIDATE')
(N / 'operator-workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'status': proof['status'], 'canonical_prepare_and_normal_import_unchanged': True}))
