"""Record actual release scope and the prepared, still unapproved retention exception."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
old_receipt = ROOT / 'backend/test-output/release-gates/delivery-f87cc6f48f53/ba52fd62fb41/receipt.json'
new_receipt = ROOT / 'backend/test-output/release-gates/delivery-41b324e91fee/84b9599a0e5a/receipt.json'
review_path = HERE / 'failed-candidate-storage-review.json'
old = json.loads(old_receipt.read_text(encoding='utf-8'))
new = json.loads(new_receipt.read_text(encoding='utf-8'))
review = json.loads(review_path.read_text(encoding='utf-8'))
assert old['status'] == new['status'] == 'FAIL'
assert new['storage']['image_budget']['existing_image_count'] == 100
assert review['deleted'] is False and review['immutable_index_verified']
def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
summary = {
    'status': 'BLOCKED_NEW_SCOPED_RETENTION_EXCEPTION_REQUIRED',
    'production_changed': False,
    'production_contains_pending_visibility_and_binding_repairs': False,
    'previous_candidate': {'image_id': old['image_id'], 'source_sha256': old['release']['source_sha256'],
        'receipt': ref(old_receipt), 'frontend_passed': 599, 'backend_passed': 21756,
        'backend_skipped': 2, 'browser_passed': 104, 'browser_failed': 1,
        'failed_case': 'Exact confirmed 50/250/250 real wizard review exceeds required 1200000ms timeout.',
        'nine_stage_large_e2e_proven': False},
    'performance_repair': {'isolated_tests_passed': 537, 'exact_large_capacity_comparison': ref(HERE / 'capacity-comparison.json'),
        'new_source_sha256': new['initial_source_sha256'], 'full_gate_passed': False},
    'new_gate': {'receipt': ref(new_receipt), 'checks_run': len(new['checks']), 'reason': new['error']},
    'retention_review': ref(review_path),
    'requested_exception': 'Remove only unused candidate-ba52fd62fb41 via image rm --no-prune after verified complete archive preservation; no general pruning or production/rollback changes.',
    'prior_specific_exception': 'The previous Freigabe removed only archived candidate-42a674cad1bc; that authorization was executed and does not authorize arbitrary further image removal.',
    'workers': {'state': 'RESTORED', 'evidence': ref(HERE.parent / 'simulation-visibility-20261010/authorized-worker-pause.json')},
    'prepared_canonical_reconciliation': {'applied': False, 'proposal_id': '06a903ac-2cf2-4579-9263-00946cf30e80', 'change_count': 86},
    'next': ['Fresh explicit approval for this one recoverable candidate retention exception.',
        'Recheck immutable identity, all container references, archive SHA and running production before exact removal.',
        'Run release-and-deploy.py for current source without weakening checks; restore paused workers.',
        'After complete PASS, verify exact production identity and apply/revalidate prepared canonical reconciliation.',
        'Verify actual production signal/sequence visibility and zero obsolete port warnings, then complete all workload guards.']
}
summary_path = HERE / 'delivery-blocker.json'
summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
for name in ('wizard-capacity-performance-20261010', 'simulation-visibility-20261010', 'stranded-capacity-channels-20261010'):
    workload_path = HERE.parent / name / 'workload.json'
    work = json.loads(workload_path.read_text(encoding='utf-8'))
    work['completion_status'] = 'IN_PROGRESS'
    work['unresolved_decisions'] = [{'decision': 'EXACT_ARCHIVED_FAILED_CANDIDATE_RETENTION_EXCEPTION',
        'image_id': review['image_id'], 'requested_delete_count': 1,
        'review': ref(review_path), 'reason': new['error']}]
    work.setdefault('delivery', {}).update(status='BLOCKED_IMAGE_RETENTION_BUDGET',
        latest_attempt=ref(new_receipt), delivery_blocker=ref(summary_path))
    work['remaining_findings'] = ['Fresh scoped recoverable retention exception required before a new complete release gate.',
        'Current source still needs a complete PASS receipt and exact tested-image production delivery.',
        'Prepared canonical 86-change binding reconciliation and affected production verification remain pending.']
    workload_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
visibility_summary = HERE.parent / 'simulation-visibility-20261010/verification-summary.json'
visibility = json.loads(visibility_summary.read_text(encoding='utf-8'))
visibility['latest_delivery_blocker'] = ref(summary_path)
visibility['limitations'] = ['UI browser fixture checks do not prove persisted large nine-stage wizard E2E.',
    'Previous complete release attempt: 104 browser tests passed; large wizard timeout failed.',
    'New performance source has 537 isolated regression passes and exact large capacity equivalence, but its new gate is blocked by the 100-image retention budget.',
    'The previous explicitly approved image removal was executed; the newly failed candidate is fully archived but remains undeleted pending its own scoped exception.',
    'Production still lacks the pending changes and canonical binding reconciliation.']
visibility_summary.write_text(json.dumps(visibility, indent=2), encoding='utf-8')
print(json.dumps({'status': summary['status'], 'production_changed': False, 'archive_verified': True, 'image_deleted': False}))
