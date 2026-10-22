"""Independently compare private selected-wire changes with actual366 source."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
SOURCE = 'backend/nis/agent/orchestration/local_reasoner.py'
old = ast.parse((OUT / 'before' / SOURCE).read_text(encoding='utf8'))
new = ast.parse((ROOT / SOURCE).read_text(encoding='utf8'))
dump = lambda node: ast.dump(node, include_attributes=False)
definitions = lambda tree: {node.name: node for node in tree.body if hasattr(node, 'name')}
left, right = definitions(old), definitions(new)
added = set(right) - set(left)
assert added == {'_reference_expand_selected_ports', '_reference_expand_selected_functions'}
assert not set(left) - set(right)
changed = {key for key in left if dump(left[key]) != dump(right[key])}
assert changed == {'_reference_schema_for_stage', 'LocalEngineeringReasoner'}
methods = [definitions(tree['LocalEngineeringReasoner']) for tree in (left, right)]
assert {key for key in methods[0] if dump(methods[0][key]) != dump(methods[1][key])} == {'plan_reference_design'}


def normalize_plan(method):
    method = deepcopy(method)
    infer = next(node for node in ast.walk(method)
                 if isinstance(node, ast.AsyncFunctionDef) and node.name == 'infer')
    prompt = next(node for node in infer.body if isinstance(node, ast.Assign)
                  and any(isinstance(key, ast.Name) and key.id == 'prompt' for key in node.targets))
    index = next(index for index, key in enumerate(prompt.value.keys)
                 if isinstance(key, ast.Constant) and key.value == 'instruction')
    prompt.value.values[index] = ast.Constant('REVIEWED_PRIVATE_SELECTED_WIRE_INSTRUCTION')
    start = next(index for index, node in enumerate(infer.body)
                 if isinstance(node, ast.Assign) and any(isinstance(key, ast.Name)
                    and key.id == 'progress_details' for key in node.targets))
    end = next(index for index, node in enumerate(infer.body)
               if isinstance(node, ast.FunctionDef) and node.name == 'report_validation')
    # Only the new read-only selection labels live in this contiguous block.
    assert all(isinstance(node, (ast.Assign, ast.If)) for node in infer.body[start + 1:end])
    del infer.body[start + 1:end]

    class ReviewedPrivateAdaptation(ast.NodeTransformer):
        def visit_If(self, node):
            expansions = {item.func.id for item in ast.walk(node) if isinstance(item, ast.Call)
                          and isinstance(item.func, ast.Name)}
            if expansions & {'_reference_expand_selected_ports', '_reference_expand_selected_functions'}:
                assert isinstance(node.test, ast.Name) and node.test.id in {'port_ids', 'function_ids'}
                return None
            return self.generic_visit(node)

        def visit_JoinedStr(self, node):
            node.values = [part for part in node.values if not (isinstance(part, ast.FormattedValue)
                           and isinstance(part.value, ast.Name) and part.value.id == 'selection_text')]
            return self.generic_visit(node)

        def visit_Dict(self, node):
            entries = [(key, value) for key, value in zip(node.keys, node.values, strict=True)
                       if not (key is None and isinstance(value, ast.Call)
                           and isinstance(value.func, ast.Name) and value.func.id == 'deepcopy'
                           and len(value.args) == 1 and isinstance(value.args[0], ast.Name)
                           and value.args[0].id == 'selection_metadata')]
            node.keys, node.values = [pair[0] for pair in entries], [pair[1] for pair in entries]
            return self.generic_visit(node)

    return ReviewedPrivateAdaptation().visit(method)


assert dump(normalize_plan(methods[0]['plan_reference_design'])) == dump(
    normalize_plan(methods[1]['plan_reference_design']))
# This includes every profile/worklist/repair/normalization loop, public model
# validation, runtime identity/source merges, provider request, caps and timeout.
for name in ('_reference_merge_port_parameters', '_reference_context_window', '_reference_context_messages',
             '_reference_context_snapshot', '_reference_stream_response', '_reference_merge_inventory_devices'):
    assert dump(left[name]) == dump(right[name]), name

spec = importlib.util.spec_from_file_location('selected_identity_manifest', ROOT / 'scripts/build/write-build-info.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
original_read = Path.read_bytes
def before_read(path):
    return original_read(OUT / 'before' / SOURCE) if path.resolve() == (ROOT / SOURCE).resolve() else original_read(path)
with patch.object(Path, 'read_bytes', before_read):
    before = manifest.build_manifest(ROOT)
assert before['source_sha256'] == '36697938df50d658e8a6d7a88e5e5618758e1b407db9efe47f3e127487eb6056'
after = manifest.build_manifest(ROOT)
assert after['commit_id'] == before['commit_id'] == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
previous_files = json.loads((OUT.parent / 'projection-sync-repair/actual-host-source-files.json').read_text(encoding='utf8'))['files']
current_files = {name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                 for name in previous_files}
assert len(current_files) == after['source_file_count']
assert hashlib.sha256(json.dumps(current_files, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == after['source_sha256']
assert {name for name in current_files if current_files[name] != previous_files[name]} == {SOURCE}
proof = {'at_utc': datetime.now(timezone.utc).isoformat(), 'canonical_before': before, 'canonical_after': after,
    'application_delta': [SOURCE], 'application_file_count': len(current_files),
    'added_private_helpers': sorted(added), 'changed_definitions': sorted(changed),
    'all_other_module_and_class_definitions_AST_exact': True,
    'entire_reference_pipeline_AST_exact_except_private_selected_output_expansion_instruction_and_progress': True,
    'public_port_merge_and_source_inventory_guards_AST_exact': True,
    'model_provider_context_output_timeout_request_AST_exact': True,
    'no_original_acceptance_or_delivery_claim': True}
(OUT / 'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(proof, ensure_ascii=False))
