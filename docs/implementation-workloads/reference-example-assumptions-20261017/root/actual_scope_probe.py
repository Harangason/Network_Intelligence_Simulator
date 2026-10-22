"""Read-only original-fact probe; does not run Qwen or change a project."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
staged = OUT / 'staged/backend/nis/agent/orchestration/project_intake.py'
spec = importlib.util.spec_from_file_location('root_staged_scope_review', staged)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
vehicle_file = ROOT / 'docs/implementation-workloads/document-function-owner-cross-reference-20261017/actual-source-counterprobe-inputs.json'
robot_file = ROOT / 'docs/implementation-workloads/robotics-document-handoff-20261016/joint-retest-20261017/native-adopted-facts.json'
source_file = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md')
assert hashlib.sha256(source_file.read_bytes()).hexdigest() == '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
vehicle = json.loads(vehicle_file.read_text(encoding='utf-8'))['facts']
robot = json.loads(robot_file.read_text(encoding='utf-8'))
_, contexts = module.document_source_contexts(source_file.read_text(encoding='utf-8-sig'))
context_map = {}
for context in contexts:
    label = ' / '.join(context)
    assert label not in context_map or context_map[label] == context
    context_map[label] = context
vehicle_scopes = sorted({tuple(module.document_system_scope(fact.get('source_context', []))) for fact in vehicle})
robot_scopes = sorted({tuple(module.document_system_scope(context_map[fact['context']])) for fact in robot})
assert vehicle_scopes == [()] and len(robot_scopes) == 10
assert all(len(scope) == 2 and scope[1].startswith(f'{index:03d}.')
           for index, scope in zip(range(54, 64), robot_scopes))
report = {'status': 'PASSED_PURE_ACTUAL_SCOPE_PROBE', 'vehicle_facts': len(vehicle),
    'vehicle_scopes': vehicle_scopes, 'robot_facts': len(robot), 'robot_scopes': robot_scopes,
    'robot_context_origin': 'Exact display-join lookup in original heading arrays, with no ambiguous joins.',
    'scope': 'Actual preserved original facts; no new Native, model or simulation proof.',
    'inputs': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in [vehicle_file, robot_file, source_file]],
    'staged_source_sha256': hashlib.sha256(staged.read_bytes()).hexdigest()}
(OUT / 'actual-scope-probe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
pattern = json.loads((OUT / 'generic-system-chapter-pattern.json').read_text(encoding='utf-8'))['pattern']
ts = (ROOT / 'frontend/src/features/agent/lib/document-clarification.ts').read_text(encoding='utf-8')
needle = '    return /^(?:Systemstruktur'
assert ts.count(needle) == 1
ts = ts.replace(needle, '    return new RegExp(' + json.dumps('^(?:' + pattern + ')$') + ', "i").test(title) || /^(?:Systemstruktur')
(OUT / 'execution-source-scope-projection.ts').write_text(ts, encoding='utf-8')
print(json.dumps({'status': report['status'], 'vehicle_facts': len(vehicle), 'robot_facts': len(robot), 'robot_profiles': len(robot_scopes)}))
