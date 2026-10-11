import hashlib
import json
import shutil
from pathlib import Path

out = Path(__file__).parent.resolve()
root = out.parents[2]
path = out / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
for name in ('backend/nis/agent/tools/proposal_service.py', 'backend/tests/test_proposal_capacity.py'):
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before = out / 'before' / name
        before.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, before)
work.setdefault('repair_history', []).append(work['repair'])
evidence = out / 'full-validate-1-profile.txt'
work['repair'] = {
    'finding_ids': ['LARGE_RETURN_FULL_VALIDATION_REPEATED_WORK'],
    'owner': 'PROJECT_PRODUCT', 'category': 'PROJECT_PRODUCT',
    'cause': 'REPEATED_NATIVE_REVIEW_WORK',
    'root_cause': 'Actual isolated SQL proposal validation takes 73.3 seconds under profiling. It reads networks/workflow 121/124 times (9.2 seconds), scans 3.59 million duplicate-name candidates (11.4 seconds), and copies the entire profile for 653 messages (10.2 seconds). Native frame costs are repeated for identical scope/payload pairs. Ingress copies rich schema metadata although it only needs transport-origin keys or aliases/roles, and removes every known foreign key although few are present (7.98 million pop calls).',
    'first_failing_layer': 'Backend complete proposal and native parameter review',
    'reproduction': 'Existing full captured 50/250/250 isolated test, unchanged SQL execution observed through cProfile; latest real browser large return still fails its existing 60-second budget.',
    'evidence': [{'path': str(evidence), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}],
    'affected_files': ['backend/nis/agent/tools/proposal_service.py', 'backend/nis/agent/tools/validation.py', 'backend/tests/test_proposal_capacity.py', 'backend/nis/engineering/capacity/service.py', 'backend/nis/communication/registry.py', 'backend/tests/test_technology_registry_metadata.py'],
    'acceptance_criteria': ['Read existing canonical network identifiers once per validation', 'Index exact existing duplicate-name semantics for effective graph, including parent scope and UPDATE/DELETE overlays', 'Use detached native capabilities only for stream checks', 'Reuse deterministic frames only for identical complete scope and payload; retain every message release and load', 'Filter present fields using identical foreign-key set; retain strict unknown native validation', 'Read transport-origin key set directly from current registered schema, never cache saved values or return mutable definition', 'Keep all native validation, hardware provenance and existing browser budgets', 'Pass full gate and deploy exact tested image'],
    'targeted_tests': ['test_proposal_capacity.py', 'test_technology_parameter_review.py', 'test_agent_tools.py', 'existing large actual browser return'],
    'weaken_assertions_to_pass': False, 'status': 'READY',
}
work['revision_before'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status'] = 'REPAIRING'
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
with (out / 'diagnosis.md').open('a', encoding='utf-8') as stream:
    stream.write('\nFull SQL validation profile: 73.3 s, 121 network reads/124 workflow reads, 3.59 million name comparisons, 653 complete message profile copies. The newest regular candidate still has four passing browser cases and a failing large return. No delivery. Repair targets repeated work while preserving strict semantics and existing readiness budgets.\n')
print('Full request repair planned from measured SQL/native evidence.')
