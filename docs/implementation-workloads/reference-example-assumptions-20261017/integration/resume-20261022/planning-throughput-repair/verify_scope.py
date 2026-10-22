"""Read-only AST and canonical manifest comparison against the tested0ed app."""
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
SOURCE = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
BEFORE = OUT / 'before/backend/nis/agent/orchestration/local_reasoner.py'
old, new = ast.parse(BEFORE.read_text(encoding='utf8')), ast.parse(SOURCE.read_text(encoding='utf8'))
dump = lambda node: ast.dump(node, include_attributes=False)
definitions = lambda tree: {node.name: node for node in tree.body if hasattr(node, 'name')}
left, right = definitions(old), definitions(new)
changed = {name for name in left if dump(left[name]) != dump(right[name])}
assert changed == {'_reference_schema_for_stage', '_reference_expand_inventory_bindings',
                   '_reference_expand_inventory_choices', '_reference_merge_inventory_devices',
                   '_reference_scoped_inventory_delta', '_reference_context_messages', 'LocalEngineeringReasoner'}
assert set(right) - set(left) == {'_reference_context_snapshot', '_reference_stream_response'}
assert not set(left) - set(right)
assert dump(left['_reference_context_window']) == dump(right['_reference_context_window'])
assert dump(left['_reference_merge_port_parameters']) == dump(right['_reference_merge_port_parameters'])
assert dump(left['_reference_context_patch']) == dump(right['_reference_context_patch'])

old_methods, new_methods = definitions(left['LocalEngineeringReasoner']), definitions(right['LocalEngineeringReasoner'])
assert {key for key in old_methods if dump(old_methods[key]) != dump(new_methods[key])} == {'plan_reference_design'}


def assignment(function, name):
    return next(node for node in function.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


for name, target in [('_reference_expand_inventory_bindings', 'limit'), ('_reference_expand_inventory_choices', 'maximum')]:
    normal = deepcopy(right[name])
    changed_assignment = assignment(normal, target)
    normal.body[normal.body.index(changed_assignment)] = deepcopy(assignment(left[name], target))
    if name.endswith('_choices'):
        extra = [node for node in normal.body if isinstance(node, ast.If)
                 and ast.unparse(node.test) == 'not inventory_target and proposed and (bindings or len(proposed) != 1)']
        assert len(extra) == 1
        normal.body.remove(extra[0])
    assert dump(normal) == dump(left[name]), name

for name, variable in [('_reference_merge_inventory_devices', 'bound'), ('_reference_scoped_inventory_delta', 'maximum')]:
    normal = deepcopy(right[name])
    normal.body.remove(assignment(normal, variable))
    old_condition = next(node for node in left[name].body if isinstance(node, ast.If) and 'len(' in ast.unparse(node.test))
    new_condition = next(node for node in normal.body if isinstance(node, ast.If) and variable in ast.unparse(node.test))
    new_condition.test = deepcopy(old_condition.test)
    assert dump(normal) == dump(left[name]), name

schema = deepcopy(right['_reference_schema_for_stage'])
inventory_schema = schema.body[-2]
assert isinstance(inventory_schema, ast.If)
assert isinstance(inventory_schema.body[-1], ast.If) and ast.unparse(inventory_schema.body[-1].test) == 'derivation_fact_ids is not None'
inventory_schema.body.pop()
assert dump(schema) == dump(left['_reference_schema_for_stage'])

for label in ('old', 'new'):
    method = old_methods['plan_reference_design'] if label == 'old' else new_methods['plan_reference_design']
    profile = next(node for node in ast.walk(method) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'plan_profile')
    loops = {ast.unparse(node.iter): node for node in profile.body if isinstance(node, ast.For)}
    if label == 'old':
        protected = {key: dump(loops[key]) for key in ('inventory', 'range(0, len(derivation_ids), 4)')}
    else:
        assert all(dump(loops[key]) == value for key, value in protected.items())

spec = importlib.util.spec_from_file_location('canonical_nis_manifest', ROOT / 'scripts/build/write-build-info.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
original_read = Path.read_bytes
def baseline_read(path):
    return original_read(BEFORE) if path.resolve() == SOURCE.resolve() else original_read(path)
with patch.object(Path, 'read_bytes', baseline_read):
    baseline = manifest.build_manifest(ROOT)
assert baseline['source_sha256'] == '0ed8389c863abbca20027128b2c371a1a5c8042ad059f677d78f0d8091d1f15e'
actual = manifest.build_manifest(ROOT)
assert actual['commit_id'] == baseline['commit_id'] == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
assert actual['source_sha256'] != baseline['source_sha256']

after = []
for relative in ('backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py', 'backend/tests/test_reference_planning_throughput.py'):
    live = ROOT / relative
    target = OUT / 'after' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(live.read_bytes())
    before = OUT / 'before' / relative
    text = ''.join(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True) if before.exists() else [],
                                      live.read_text(encoding='utf8').splitlines(True), fromfile='before/' + relative, tofile='after/' + relative))
    diff = OUT / (live.name + '.diff')
    diff.write_text(text, encoding='utf8')
    after.append({'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
proof = {'at_utc': datetime.now(timezone.utc).isoformat(), 'canonical_before': baseline, 'canonical_after': actual,
         'only_application_delta': 'backend/nis/agent/orchestration/local_reasoner.py', 'changed_definitions': sorted(changed),
         'new_helpers': sorted(set(right) - set(left)), 'all_other_definitions_AST_unchanged': True,
         'all_other_reasoner_methods_including_model_provider_context_timeout_AST_unchanged': True,
         'complete_UTF8_guard_and_output_reserve_AST_unchanged': True, 'exact_port_parameter_merge_AST_unchanged': True,
         'source_fact_worklists_and_declared_inventory_loops_AST_unchanged': True,
         'all_existing_identity_source_member_reference_checks_preserved_AST': True,
         'bounded_private_batch_lengths_changed_explicitly': True, 'after': after,
         'original_acceptance': False, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'status': 'PASS', 'source_sha256': actual['source_sha256'], 'only_application_delta': proof['only_application_delta']}))
