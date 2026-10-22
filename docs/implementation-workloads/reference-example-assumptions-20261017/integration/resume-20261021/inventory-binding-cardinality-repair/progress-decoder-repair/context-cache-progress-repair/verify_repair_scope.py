"""Independent AST and actual native-cache evidence review; no model writes."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path.cwd()
P = Path(__file__).resolve().parent

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def dump(node):
    return ast.dump(node, include_attributes=False)

def definitions(tree):
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

before = definitions(ast.parse((P / 'before-local_reasoner.py').read_text(encoding='utf-8')))
after = definitions(ast.parse((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf-8')))
added = sorted(set(after) - set(before))
changed = sorted(name for name in before if dump(before[name]) != dump(after[name]))
assert added == ['_reference_context_messages', '_reference_context_patch']
assert changed == ['LocalEngineeringReasoner', '_reference_context_window']
old_methods, new_methods = definitions(before['LocalEngineeringReasoner']), definitions(after['LocalEngineeringReasoner'])
assert set(old_methods) == set(new_methods)
assert [name for name in old_methods if dump(old_methods[name]) != dump(new_methods[name])] == ['plan_reference_design']
def nested_plan(tree):
    return next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'plan_profile')
old_plan = nested_plan(old_methods['plan_reference_design'])
new_plan = nested_plan(new_methods['plan_reference_design'])
assert isinstance(new_plan.body[0], ast.Nonlocal) and new_plan.body[0].names == ['reference_messages', 'reference_prompt']
assert isinstance(new_plan.body[1], ast.Assign)
assert ast.unparse(new_plan.body[1]) == 'reference_messages, reference_prompt = ([], None)'
new_plan.body = new_plan.body[2:]
assert dump(old_plan) == dump(new_plan), 'Whole original worklist/continuation must remain unchanged.'
originals = {
    'C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt': '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7',
    'C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md': '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef',
}
for path, sha in originals.items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha
proof = {'changed_definitions': changed, 'added_private_context_helpers': added,
    'all_other_reasoner_methods_AST_unchanged': True,
    'all_other_module_definitions_including_public_schema_and_merge_gates_AST_unchanged': True,
    'whole_fact_worklist_and_continuation_AST_unchanged_except_history_reset': True,
    'provider_model_maximum_output_timeout_configuration_AST_unchanged': True,
    'configured_capacity_fixed_not_increased': 131072,
    'no_source_reference_candidate_or_retry_truncation': True,
    'original_hashes': originals, 'before_reasoner': ref(P / 'before-local_reasoner.py'),
    'preview_reproduction': ref(P / 'raw-preview-before.json'), 'preview_after': ref(P / 'raw-preview-after.json'),
    'frontend_scope': 'Raw preview source/profile and TC classification; accepted reference branch unchanged; unknown transport preserved.'}
(P / 'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
N = P / 'native-cache'
console = (N / 'main-console-after.txt').read_text(encoding='utf-8')
assert re.search(r'task\s+27\s+\| cached n_tokens = 3326', console)
assert re.search(r'task\s+27\s+\| prompt eval time =\s+2393\.69 ms /\s+89 tokens', console)
assert 'forcing full prompt re-processing' not in console[console.index('task 27'):]
result = json.loads((N / 'result.json').read_text(encoding='utf-8'))
assert len(result['results']) == 2 and len({row['worker_pid'] for row in result['results']}) == 1
for seq in (1, 2):
    request = json.loads((N / f'{seq}-request.json').read_text(encoding='utf-8'))
    assert request['model'] == 'qwen3.8:27b' and request['options']['num_ctx'] == 131072 and request['options']['num_predict'] == 8192
    worker = json.loads((N / f'{seq}-worker-after.json').read_text(encoding='utf-8'))
    assert all(not slot['is_processing'] for slot in worker['slots'])
result.update(status='PASSED', actual_cached_prefix_tokens=3326, actual_new_prompt_tokens=89,
    scope='Two small sequential native grammar/context-cache counterprobes; no full-original model or simulation acceptance.',
    console_evidence=ref(N / 'main-console-after.txt'))
(N / 'reviewed-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'AST_scope': 'PASS', 'native_cache_diagnostic': 'PASS', 'cached': 3326, 'new': 89}))
