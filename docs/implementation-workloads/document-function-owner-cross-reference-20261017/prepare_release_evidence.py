"""Record the scoped source freeze and its actual original-source counterprobe."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def ref(path):
    return {'path': str(path.resolve()), 'sha256': digest(path)}


workload = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
files = workload['files_changed']
peer = json.loads((ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics/profile-boundary-independent-review.json').read_text(encoding='utf-8'))
assert all(digest(ROOT / name) == value for name, value in peer['source_hashes'].items())
from backend.nis.agent.orchestration.project_intake import document_fact_identity, document_source_scope, document_system_scope


def pure_methods(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if (isinstance(node, ast.FunctionDef) and node.name == '_reviewed_document_functions')
             or (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '_CONTROLLER_DEVICE_TYPES' for target in node.targets))]
    assert len(nodes) == 2
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_reviewed_document_functions']


inputs = json.loads((OUT / 'actual-source-counterprobe-inputs.json').read_text(encoding='utf-8'))
pair = [fact for fact in inputs['facts'] if fact['name'] == 'Fahrdynamikregelung']
assert len(pair) == 2 and len(inputs['owners']) == 5
chains = [{'hardware_name': owner['name'], 'device_type': 'ECU', 'configuration': {
    'document_equipment_evidence': {'source_context': owner['source_context']},
    'source_scoped_functions': owner['duties']}} for owner in inputs['owners']]
hosts = [owner['name'].casefold() for owner in inputs['owners']]
evidence = {'components': pair, 'source_sha256': '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'}
name = 'backend/nis/agent/tools/wizard_generation.py'
try:
    pure_methods(OUT / 'before' / name)(evidence, hosts, chains)
except ValueError as error:
    before_failure = str(error)
else:
    raise AssertionError('Original function must reproduce the missing owner')
result = pure_methods(ROOT / name)(evidence, hosts, chains)
assert len(result) == 2
assert all(item['host'] == 'chassis domain controller (cdc)' and item['assignment_source'] == 'source_scoped_function' for item in result)
assert len({item['fact_id'] for item in result}) == 2
report = {'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Exact old/current pure product method bodies with actual original-source pair and all five declared owners. No SQL, model mutation or simulation.',
          'method_source_hashes': {name: digest(ROOT / name)}, 'before_failure': before_failure,
          'declared_host_count': len(hosts), 'after_results': result, 'source_provenance_consistent': True}
(OUT / 'actual-source-backend-counterprobe.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
diff = []
for name in files:
    after = OUT / 'after' / name
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / name, after)
    diff.extend(difflib.unified_diff((OUT / 'before' / name).read_text(encoding='utf-8').splitlines(True),
                                   after.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
(OUT / 'owned-changes.diff').write_text(''.join(diff), encoding='utf-8')
old = json.loads((OUT.parent / 'document-clarification-repair-20261016/followup-communication-actions/source-freeze.json').read_text(encoding='utf-8'))
drift = [name for name, value in old['files'].items() if name not in files and digest(ROOT / name) != value]
assert not drift, drift
build = module('nis_current_build', ROOT / 'scripts/write-build-info.py').build_manifest()
verification = module('nis_current_gate', ROOT / 'scripts/run-release-gate.py').verification_manifest()
freeze = {**build, 'at_utc': datetime.now(timezone.utc).isoformat(), 'verification_sha256': verification,
          'previous_source_sha256': old['source_sha256'], 'changed_scope': files, 'foreign_hash_drift': drift,
          'files': {name: digest(ROOT / name) for name in sorted(set(old['files']) | set(files))},
          'note': 'Freeze until required full release gate and exact tested image delivery. No original model/simulation success implied.'}
(OUT / 'source-freeze.json').write_text(json.dumps(freeze, indent=2) + '\n', encoding='utf-8')
workload['after'] = [ref(OUT / 'after' / name) for name in files]
workload['diff'] = [ref(OUT / 'owned-changes.diff')]
workload['source_freeze'] = ref(OUT / 'source-freeze.json')
for key, artifact in [('frontend_regressions', 'targeted-frontend.log'), ('isolated_backend_regressions', 'targeted-backend.xml'), ('actual_source_counterprobe', 'actual-source-counterprobe.json')]:
    workload['validations'][key] = {'status': 'PASSED', 'evidence': [ref(OUT / artifact)]}
for key, artifact in [('unique_cross_section_source_owner', 'actual-source-counterprobe.json'), ('profile_ambiguity_and_subject_guards_preserved', 'targeted-backend.xml'), ('source_provenance_consistent', 'actual-source-backend-counterprobe.json')]:
    workload['outcomes'][key] = {'status': 'PASSED', 'evidence': [ref(OUT / artifact)]}
workload['independent_profile_review'] = ref(ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics/profile-boundary-independent-review.json')
(OUT / 'workload.json').write_text(json.dumps(workload, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'FROZEN', 'source_sha256': build['source_sha256'], 'verification_sha256': verification, 'counterprobe': report['status'], 'foreign_hash_drift': drift}))
