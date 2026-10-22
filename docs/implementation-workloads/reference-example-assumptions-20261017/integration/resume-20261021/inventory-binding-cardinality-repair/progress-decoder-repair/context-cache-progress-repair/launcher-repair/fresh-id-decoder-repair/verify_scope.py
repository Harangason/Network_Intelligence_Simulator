"""Read-only AST/source audit using the canonical manifest implementation."""
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
N = Path(__file__).resolve().parent
L = N.parent
reasoner = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
before = (N / 'before-local_reasoner.py').read_bytes()
old = ast.parse(before.decode('utf8'))
new = ast.parse(reasoner.read_text(encoding='utf8'))


def dump(value):
    return ast.dump(value, include_attributes=False)


def definitions(tree):
    return {node.name: node for node in tree.body if hasattr(node, 'name')}


left, right = definitions(old), definitions(new)
changed = {name for name in left if dump(left[name]) != dump(right[name])}
assert changed == {'_reference_schema_for_stage', '_reference_expand_inventory_bindings', 'LocalEngineeringReasoner'}
assert set(right) - set(left) == {'_reference_fresh_inventory_id'}
assert not (set(left) - set(right))


class RemoveNewIdChoice(ast.NodeTransformer):
    removed = 0

    def visit_Assign(self, node):
        if any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
               and item.func.id == '_reference_fresh_inventory_id' for item in ast.walk(node)):
            assert len(node.targets) == 1 and ast.unparse(node.targets[0]) == "properties['id']"
            self.removed += 1
            return None
        return self.generic_visit(node)


transform = RemoveNewIdChoice()
schema = transform.visit(deepcopy(right['_reference_schema_for_stage']))
assert transform.removed == 1 and dump(schema) == dump(left['_reference_schema_for_stage'])

binding = deepcopy(right['_reference_expand_inventory_bindings'])
old_condition = next(node for node in left['_reference_expand_inventory_bindings'].body
                     if isinstance(node, ast.If) and 'current' in ast.unparse(node.test))
new_condition = next(node for node in binding.body
                     if isinstance(node, ast.If) and dump(node.test) == dump(old_condition.test))
assert len(new_condition.body) == 2 and isinstance(new_condition.body[-1], ast.Raise)
new_condition.body = deepcopy(old_condition.body)
assert dump(binding) == dump(left['_reference_expand_inventory_bindings'])

original_instruction = next(node.value for node in ast.walk(left['LocalEngineeringReasoner'])
                            if isinstance(node, ast.Constant) and isinstance(node.value, str)
                            and node.value.startswith('Inventarstufen liefern'))


class NormalizePrompt(ast.NodeTransformer):
    roster = 0
    instruction = 0

    def visit_Dict(self, node):
        retained = []
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == 'existing_inventory_for_this_stage':
                self.roster += 1
            else:
                retained.append((key, value))
        node.keys = [key for key, _ in retained]
        node.values = [value for _, value in retained]
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value.startswith('Inventarstufen liefern'):
            self.instruction += 1
            return ast.Constant(value=original_instruction)
        return node


prompt = NormalizePrompt()
normalized = prompt.visit(deepcopy(right['LocalEngineeringReasoner']))
assert prompt.roster == 1 and prompt.instruction == 1
assert dump(normalized) == dump(left['LocalEngineeringReasoner'])

spec = importlib.util.spec_from_file_location('nis_fresh_identity_delivery', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
info = delivery.load_module('nis_fresh_identity_manifest', ROOT / 'scripts/write-build-info.py')
read_bytes = Path.read_bytes
with patch.object(Path, 'read_bytes', lambda path: before if path == reasoner else read_bytes(path)):
    prior = info.build_manifest()
expected = json.loads((L / 'current-identity.json').read_text(encoding='utf8'))
assert prior['source_sha256'] == expected['source_sha256']
source, commit, verification = delivery.current_identity()
identity = {'source_sha256': source, 'commit_id': commit, 'verification_sha256': verification}
assert source != prior['source_sha256'] and commit == expected['commit_id']
files = ['backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py']
identity['affected_files'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
proof = {'at_utc': datetime.now(timezone.utc).isoformat(), 'only_application_source_changed': files[0],
         'canonical_before': prior, 'canonical_after': identity,
         'changed_definitions': sorted(changed), 'new_helper': '_reference_fresh_inventory_id',
         'all_other_module_definitions_AST_unchanged': True,
         'private_schema_only_adds_exact_new_id_enum': True,
         'runtime_identity_guard_condition_and_merge_AST_unchanged': True,
         'reasoner_only_adds_existing_identity_projection_and_inventory_instruction': True,
         'provider_model_maximum_output_timeout_worklist_AST_unchanged': True,
         'public_model_schemas_source_scope_and_existing_identity_domain_unchanged': True,
         'hardware_and_source_decisions_still_native': True,
         'original_model_acceptance': False, 'full_release_pass': False, 'productive_delivery': False}
for name, value in [('source-scope-proof.json', proof), ('current-identity.json', identity)]:
    (N / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
for name in files:
    current = ROOT / name
    snapshot = N / 'after' / name
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(current.read_bytes())
    previous = N / ('before-' + current.name)
    (N / (current.name + '.diff')).write_text(''.join(difflib.unified_diff(
        previous.read_text(encoding='utf8').splitlines(True), current.read_text(encoding='utf8').splitlines(True),
        fromfile='b47/' + name, tofile='current/' + name)), encoding='utf8')
print(json.dumps({'identity': identity, 'scope_audit': 'PASSED'}), flush=True)
