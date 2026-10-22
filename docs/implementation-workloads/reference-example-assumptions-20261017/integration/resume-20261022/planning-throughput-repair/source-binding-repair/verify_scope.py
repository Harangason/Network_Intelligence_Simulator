"""Read-only source/AST comparison with the canonical4da3 candidate."""
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
source = 'backend/nis/agent/orchestration/local_reasoner.py'
vocabulary = 'backend/nis/domain/inventory-vocabulary.json'
frontend_vocabulary = 'frontend/src/features/agent/lib/inventory-vocabulary.json'
old = ast.parse((OUT / 'before' / source).read_text(encoding='utf8'))
new = ast.parse((ROOT / source).read_text(encoding='utf8'))
dump = lambda node: ast.dump(node, include_attributes=False)
definitions = lambda tree: {node.name: node for node in tree.body if hasattr(node, 'name')}
left, right = definitions(old), definitions(new)
changed = {name for name in left if dump(left[name]) != dump(right[name])}
assert changed == {'_reference_schema_for_stage', '_reference_expand_inventory_choices', 'LocalEngineeringReasoner'}
assert set(right) - set(left) == {'_reference_profile_sources'}
assert not set(left) - set(right)
old_methods, new_methods = definitions(left['LocalEngineeringReasoner']), definitions(right['LocalEngineeringReasoner'])
assert {name for name in old_methods if dump(old_methods[name]) != dump(new_methods[name])} == {'plan_reference_design'}
for name in ('_reference_context_window', '_reference_context_snapshot', '_reference_context_messages',
             '_reference_context_patch', '_reference_stream_response', '_reference_expand_inventory_bindings',
             '_reference_merge_inventory_devices', '_reference_scoped_inventory_delta', '_reference_merge_port_parameters'):
    assert dump(left[name]) == dump(right[name]), name

choices = deepcopy(right['_reference_expand_inventory_choices'])
batch = [node for node in choices.body if isinstance(node, ast.If)
         and any(isinstance(value, ast.Constant) and value.value == 'EXISTING_BATCH' for value in ast.walk(node))]
assert len(batch) == 1
choices.body.remove(batch[0])
assert dump(choices) == dump(left['_reference_expand_inventory_choices'])
schema = deepcopy(right['_reference_schema_for_stage'])
old_inventory = next(node for node in left['_reference_schema_for_stage'].body if isinstance(node, ast.If)
                     and 'derivation_fact_ids is not None' in ast.unparse(node.test))
new_inventory = next(node for node in schema.body if isinstance(node, ast.If)
                     and 'derivation_fact_ids is not None' in ast.unparse(node.test))
assert dump(old_inventory.test) == dump(new_inventory.test)
assert all(dump(a) == dump(b) for a, b in zip(old_inventory.body[:-1], new_inventory.body[:-1], strict=True))
assert dump(old_inventory.body[-1].test) == dump(new_inventory.body[-1].test)
new_inventory.body[-1] = deepcopy(old_inventory.body[-1])
assert dump(schema) == dump(left['_reference_schema_for_stage'])

profiles = []
for method in (old_methods['plan_reference_design'], new_methods['plan_reference_design']):
    profiles.append(next(node for node in ast.walk(method) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'plan_profile'))
old_loops = [node for node in profiles[0].body if isinstance(node, ast.For)]
new_loops = [node for node in profiles[1].body if isinstance(node, ast.For)]
assert len(old_loops) == len(new_loops)
for previous, actual in zip(old_loops, new_loops, strict=True):
    normalized = deepcopy(actual)
    if ast.unparse(previous.iter) == 'range(0, len(derivation_ids), 4)':
        assert ast.unparse(actual.iter) == 'range(0, len(derivation_ids), _REFERENCE_HARDWARE_FACT_BATCH)'
        normalized.iter = deepcopy(previous.iter)
        assert ast.unparse(actual.body[0].value) == 'derivation_ids[start:start + _REFERENCE_HARDWARE_FACT_BATCH]'
        normalized.body[0] = deepcopy(previous.body[0])
    assert dump(previous) == dump(normalized)
old_fact_worklist = next(node for node in profiles[0].body if isinstance(node, ast.Assign)
                        and any(isinstance(key, ast.Name) and key.id == 'derivation_ids' for key in node.targets))
new_fact_worklist = next(node for node in profiles[1].body if isinstance(node, ast.Assign)
                        and any(isinstance(key, ast.Name) and key.id == 'derivation_ids' for key in node.targets))
assert dump(old_fact_worklist) == dump(new_fact_worklist)

before_vocab = json.loads((OUT / 'before' / vocabulary).read_text(encoding='utf8'))
after_vocab = json.loads((ROOT / vocabulary).read_text(encoding='utf8'))
assert set(after_vocab['document_chapters']) - set(before_vocab['document_chapters']) == {'introduction', 'contents'}
normalized_vocab = deepcopy(after_vocab)
for name in ('introduction', 'contents'):
    normalized_vocab['document_chapters'].pop(name)
assert normalized_vocab == before_vocab

spec = importlib.util.spec_from_file_location('canonical_source_binding_manifest', ROOT / 'scripts/build/write-build-info.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
original_read = Path.read_bytes
assert (ROOT / frontend_vocabulary).read_bytes() == (ROOT / vocabulary).read_bytes()
replacements = {(ROOT / name).resolve(): OUT / 'before' / name for name in (source, vocabulary, frontend_vocabulary)}
def baseline_read(path):
    return original_read(replacements.get(path.resolve(), path))
with patch.object(Path, 'read_bytes', baseline_read):
    baseline = manifest.build_manifest(ROOT)
assert baseline['source_sha256'] == '4da3c74ee7d895b0e16a1a4ed9e601882a5f67b192d5190c78dc5080ac8c8afd'
actual = manifest.build_manifest(ROOT)
assert actual['commit_id'] == baseline['commit_id'] == '70f0c160bc4f08bd23437f6b3c175523d1e5859c'
assert actual['source_sha256'] != baseline['source_sha256']
originals = json.loads((OUT / 'actual-original-projection-proof.json').read_text())
assert len(originals) == 2 and all(row['all_intervals_have_owners'] for row in originals)
assert originals[0]['whole_source_equal'] and len(originals[1]['profiles']) == 10
proof = {'at_utc': datetime.now(timezone.utc).isoformat(), 'canonical_before': baseline, 'canonical_after': actual,
    'application_delta': [source, vocabulary, frontend_vocabulary], 'changed_definitions': sorted(changed),
    'new_helper': '_reference_profile_sources',
    'all_other_reasoner_methods_including_model_provider_context_timeout_AST_unchanged': True,
    'complete_UTF8_guard_and_output_reserve_AST_unchanged': True,
    'exact_port_parameter_merge_AST_unchanged': True,
    'all_existing_identity_source_member_reference_checks_preserved_AST': True,
    'complete_fact_worklist_preserved_with_explicit16_batch': True,
    'lossless_profile_source_intervals_and_independent_profiles': True,
    'shared_vocabulary_only_adds_introduction_and_contents': True,
    'derived_frontend_vocabulary_exact_authoritative_backend_bytes': True,
    'original_acceptance': False, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'source-scope-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'status': 'PASS', 'source_sha256': actual['source_sha256'], 'application_delta': proof['application_delta']}))
