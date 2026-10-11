import hashlib, json
from pathlib import Path
out = Path(__file__).parent.resolve()
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history', []).append(work['repair'])
proof = out/'before-idempotent-seed-catalog-browser.log'
work['repair'] = {
    'finding_ids': ['FULL_CASE_IDEMPOTENT_SEED_EXPECTATION'], 'owner': 'TOOL_CHECKER',
    'category': 'TEST_INTEGRATION', 'cause': 'IDENTICAL_SEED_AT_EACH_REVIEW',
    'root_cause': 'The partitioned full case reused seed42 at each proposal phase. At the first routing save all scoped values were unchanged, so preserving VALIDATED was correct; the helper deliberately expects OUTDATED after a real edit.',
    'first_failing_layer': 'Full browser review edit setup',
    'reproduction': 'Four smaller cases pass. Large model returns pass; first routing save receives VALIDATED instead of OUTDATED at wizard.spec.ts:295.',
    'evidence': [{'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()}],
    'affected_files': ['frontend/e2e/wizard.spec.ts'],
    'acceptance_criteria': ['Use distinct seeds41,43,42 for model,routing,topology phases so every loop actually edits saved parameters', 'Preserve the OUTDATED and VALIDATED assertions, complete document equality, run identity, no START/application assertions and all original deadlines', 'Keep nine integrated returns and 27 separate review-only returns; final full-flow seed remains42', 'No application change; reuse exact tested image and rerun all eight cases'],
    'targeted_tests': ['eight-case real isolated browser scope'],
    'weaken_assertions_to_pass': False, 'status': 'READY',
}
work['revision_before'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings'] = ['Eight-case browser scope and complete gate pending', 'Exact production delivery pending']
work['completion_status'] = 'REPAIRING'
path.write_text(json.dumps(work, indent=2, ensure_ascii=False), encoding='utf-8')
print('Real edits at every review, unchanged assertions and deadlines.')
