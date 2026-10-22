"""Keep the original-file run state honest while candidate creation is pending."""
from pathlib import Path
from datetime import datetime, timezone
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
directory = ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics'
path = directory / 'state.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(status='IMPLEMENTED_PENDING_CANDIDATE_AND_ORIGINAL_NATIVE_VERIFICATION',
    execution_scope='Authorized coordinated product implementation plus isolated SQL/component verification; complete original-file Wizard/model/simulation acceptance still pending.',
    last_updated_utc=datetime.now(timezone.utc).isoformat(),
    robotics_phase='CANONICAL_IMPLEMENTATION_APPLIED_ORIGINAL_CANDIDATE_RUN_PENDING',
    model_and_simulation_started=False, robotics_model_writes=False, robotics_simulation_started=False,
    human_question_pending=True,
    next_action='Existing exact archived-image cleanup question is pending in NIS starten. After canonical checks and approved storage action: prepare exact candidate, verify both full originals through normal Wizard/model/saved simulation, full release gate and exact-image delivery.',
    implementation_evidence=[str(OUT / 'workload.json'), str(OUT / 'qualification-stage/canonical-apply-verification.json'),
        str(OUT / 'original-robot-source-verification.json'), str(OUT / 'projection-role-consistency.json')],
    candidate_built=False, new_feature_productive=False,
    blocking_condition='Image-count budget is full. Fully archived candidate 66a892b0b219 has a newer PREPARED attempt than its FAIL receipt, so the existing human cleanup question cannot be replaced with standing FAIL-only authorization.',
    qwen_owner='NIS starten coordinates exclusive candidate inference. Root has not started new inference.',
    source_question='Resolved: examples with expected gaps; NIS generates reviewable reference assumptions. No renewed real-project BOM request.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status':state['status'], 'original_model_and_simulation':'PENDING', 'new_feature_productive':False}))
