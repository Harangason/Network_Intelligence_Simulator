"""Read-only comparison of the cache/output repair with its receipted baseline."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
SOURCE = 'backend/nis/agent/orchestration/local_reasoner.py'
dump = lambda node: ast.dump(node, include_attributes=False)
definitions = lambda tree: {node.name: node for node in tree.body if hasattr(node, 'name')}
trees = [ast.parse(path.read_text(encoding='utf8')) for path in (OUT / 'before' / SOURCE, ROOT / SOURCE)]
left, right = [definitions(tree) for tree in trees]
assert set(left) == set(right)
changed = {name for name in left if dump(left[name]) != dump(right[name])}
assert changed == {'_reference_schema_for_stage', '_reference_context_messages', 'LocalEngineeringReasoner'}
methods = [definitions(side['LocalEngineeringReasoner']) for side in (left, right)]
assert set(methods[0]) == set(methods[1])
assert {name for name in methods[0] if dump(methods[0][name]) != dump(methods[1][name])} == {'plan_reference_design'}


def normalize_plan(method):
    method = deepcopy(method)
    infer = next(node for node in ast.walk(method) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'infer')
    prompt = next(node for node in infer.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'prompt' for target in node.targets))
    index = next(i for i, key in enumerate(prompt.value.keys) if isinstance(key, ast.Constant) and key.value == 'instruction')
    prompt.value.values[index] = ast.Constant('REVIEWED_CONCISE_PRIVATE_OUTPUT_INSTRUCTION')
    start = next(i for i, node in enumerate(infer.body) if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'progress_details' for target in node.targets))
    end = next(i for i, node in enumerate(infer.body) if isinstance(node, ast.FunctionDef) and node.name == 'report_validation')
    assert all(isinstance(node, (ast.Assign, ast.If)) for node in infer.body[start + 1:end])
    del infer.body[start + 1:end]
    report = next(node for node in ast.walk(infer) if isinstance(node, ast.FunctionDef) and node.name == 'report_progress')
    class ReadOnlyFunctionLabel(ast.NodeTransformer):
        def visit_If(self, node):
            if isinstance(node.test, ast.Name) and node.test.id == 'function_ids':
                assert len(node.body) == 1 and isinstance(node.body[0], ast.Assign)
                assert dump(node.body[0].targets[0]) == dump(ast.Name(id='scope_text', ctx=ast.Store()))
                assert not node.orelse
                return None
            return self.generic_visit(node)
    ReadOnlyFunctionLabel().visit(report)

    class ReviewedPrivateChanges(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
                target = node.targets[0]
                indices = [i for i, value in enumerate(target.elts)
                           if isinstance(value, ast.Name) and value.id == 'reference_anchors']
                if indices:
                    assert isinstance(node.value, ast.Tuple) and len(node.value.elts) == len(target.elts)
                    for i in reversed(indices):
                        assert isinstance(node.value.elts[i], ast.List) and not node.value.elts[i].elts
                        del target.elts[i]
                        del node.value.elts[i]
            return self.generic_visit(node)

        def visit_Nonlocal(self, node):
            node.names = [name for name in node.names if name != 'reference_anchors']
            return node

        def visit_Expr(self, node):
            if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                    and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'reference_anchors'):
                assert node.value.func.attr == 'append' and len(node.value.args) == 1
                assert isinstance(node.value.args[0], ast.Name) and node.value.args[0].id == 'reference_anchor'
                return None
            return self.generic_visit(node)

        def visit_If(self, node):
            expected = ast.parse('if len(reference_anchors) > 8:\n    del reference_anchors[1]').body[0]
            if dump(node) == dump(expected):
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == '_reference_context_messages':
                node.keywords = [item for item in node.keywords if item.arg != 'anchors']
            return self.generic_visit(node)

    return ReviewedPrivateChanges().visit(method)


old_plan, new_plan = [normalize_plan(side['plan_reference_design']) for side in methods]
if dump(old_plan) != dump(new_plan):
    (OUT / 'scope-normalization-diagnostic.diff').write_text('\n'.join(difflib.unified_diff(
        ast.unparse(old_plan).splitlines(), ast.unparse(new_plan).splitlines())), encoding='utf8')
    raise AssertionError('An unreviewed pipeline delta remains; inspect diagnostic, never suppress it.')
for name in ('_reference_context_window', '_reference_context_snapshot', '_reference_context_patch',
             '_reference_stream_response', '_reference_merge_inventory_devices',
             '_reference_merge_port_parameters', '_reference_expand_selected_ports', '_reference_expand_selected_functions'):
    assert dump(left[name]) == dump(right[name]), name
module_normalized = [deepcopy(tree) for tree in trees]
for tree in module_normalized:
    tree.body = [node for node in tree.body if getattr(node, 'name', None) not in changed]
assert dump(module_normalized[0]) == dump(module_normalized[1])

spec = importlib.util.spec_from_file_location('cache_output_manifest', ROOT / 'scripts/build/write-build-info.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
original_read = Path.read_bytes
def before_read(path):
    return original_read(OUT / 'before' / SOURCE) if path.resolve() == (ROOT / SOURCE).resolve() else original_read(path)
with patch.object(Path, 'read_bytes', before_read):
    before = manifest.build_manifest(ROOT)
assert before['source_sha256'] == 'ce5ebb53538d9fe38b7536066bea2a8143eaa6f4106cf72159518927e35ecf37'
after = manifest.build_manifest(ROOT)
assert after['commit_id'] == before['commit_id'] == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
previous = json.loads((OUT.parent.parent / 'projection-sync-repair/actual-host-source-files.json').read_text(encoding='utf8'))['files']
previous[SOURCE] = hashlib.sha256((OUT / 'before' / SOURCE).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
assert hashlib.sha256(json.dumps(previous, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == before['source_sha256']
current = {name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for name in previous}
assert len(current) == after['source_file_count']
assert hashlib.sha256(json.dumps(current, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == after['source_sha256']
assert {name for name in current if current[name] != previous[name]} == {SOURCE}
proof = {'at_utc': datetime.now(timezone.utc).isoformat(), 'canonical_before': before, 'canonical_after': after,
         'application_delta': [SOURCE], 'application_file_count': len(current), 'changed_definitions': sorted(changed),
         'all_other_module_and_class_definitions_AST_exact': True,
         'whole_plan_pipeline_AST_exact_except_reviewed_private_anchor_bookkeeping_instruction_and_progress': True,
         'public_model_merge_source_identity_and_continuation_guards_AST_exact': True,
         'model_provider_maximum_output_timeout_and_byte_guard_AST_exact': True,
         'no_original_acceptance_full_gate_or_delivery_claim': True}
(OUT / 'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(OUT / 'actual-host-source-files.json').write_text(json.dumps({'files': current}, sort_keys=True, indent=2) + '\n', encoding='utf8')
print(json.dumps(proof, ensure_ascii=False))
