"""Persist the actual native failure, repair state and pending scoped decision."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
INTEGRATION = BASE.parent
at = datetime.now(timezone.utc).isoformat()
audit_path = OUT / 'archive-review-d520e6b852e5/archive-audit.json'
audit = json.loads(audit_path.read_text())
assert len(audit['verified_blobs']) == 23 and audit['container_removal'] is False and audit['image_removal'] is False
decision = {
    'at_utc': at, 'status': 'PENDING_HUMAN_RESPONSE',
    'code': 'EXACT_SECURED_TEST_RUNTIME_AND_PREPARED_IMAGE_CLEANUP',
    'containers': ['nis-e2e-app-d520e6b852e5', 'nis-e2e-db-d520e6b852e5'],
    'tag': audit['tag'], 'image_id': audit['image'],
    'archive_audit': {'path': str(audit_path), 'sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest()},
    'auto_review_rejection': {
        'action': 'Stop and remove candidate app/database containers after backing up their state',
        'reason': 'Destructive loss of non-trivial test-project runtime state not specifically authorized by the user.',
        'safer_completed_action': 'Exports, database dump, full immutable image archive and all 23 referenced blobs verified, without stopping/removing containers or image.',
    },
    'prior_43_image_authorization_not_extended': True,
    'production_unchanged': True,
}
(OUT / 'cleanup-decision.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for case in ['vehicle', 'robot']:
    path = INTEGRATION / ('native-joint-' + case) / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8'))
    state.update(at_utc=at, superseded_by_source_repair=True, source_repair=str(OUT / 'workload.json'))
    if case == 'vehicle':
        state.update(status='FAILED_AGGREGATE_SOURCE_CONTEXT_CHECK_AFTER_ALL_16_LOCAL_QWEN_SECTIONS',
                     failure='Four ISO rows falsely demanded in neighboring subchapter context by full-source grouping.',
                     document_adopted=False)
    else:
        state.update(status='ORIGINAL_FULLY_UPLOADED_INFERENCE_NOT_STARTED_ON_SUPERSEDED_CANDIDATE')
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
path = INTEGRATION / 'workload.json'
workload = json.loads(path.read_text(encoding='utf-8'))
workload['status'] = 'VALIDATING'
workload['unresolved_decisions'] = [decision]
workload['active_stage'] = {'stage': 'NORMATIVE_CONTEXT_REPAIR_REGRESSIONS_AND_PENDING_CLEANUP_DECISION',
                            'at_utc': at, 'tests_log': str(OUT / 'regressions.log'),
                            'native_original_simulations': False, 'full_pass': False}
workload['joint_delivery'].update(new_candidate_status='SUPERSEDED_NATIVE_FAILURE_SOURCE_REPAIR_PENDING_NEW_CANDIDATE', production_changed=False, full_pass=False)
workload['completion_status'] = 'Actual final-native vehicle intake exposed cross-subchapter normative citation grouping. General two-file repair has 4 new regression passes; complete affected suites running. New candidate blocked on pending exact secured test-runtime/image cleanup. Both original simulations and full productive release remain pending.'
path.write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
note = ('\nAktueller Stand ' + at + ': Der 16-Abschnitt-Fahrzeuglauf auf d520e6b852e5 scheiterte am allgemeinen Normenkontext-Gruppierungsfehler. '
        'Die eng begrenzte Korrektur ist unter normative-boundary-repair gesichert, vier neue Tests bestehen. '
        'Das alte Testimage, die Datenbank und beide Projekte sind vollständig gesichert; nichts davon wurde entfernt. '
        'Die automatische Freigabeprüfung lehnte Containerentfernung ohne ausdrückliche Freigabe ab. '
        'Die genaue Container-/Image-Entfernung ist angefragt. Beide Originalsimulationen und Full-Gate/Produktion bleiben offen.\n')
resume = BASE / 'RESUME.md'
old = resume.read_text(encoding='utf-8')
resume.write_text(note + '\n---\n' + old, encoding='utf-8')
print(json.dumps({'status': 'ACTUAL_PROGRESS_AND_PENDING_DECISION_SAVED', 'no_deletion': True, 'production_changed': False}))
