"""Record bounded staging checks without claiming release or native acceptance."""
from pathlib import Path
import hashlib
import json
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parent
reports = []
for name in ['staged-real-bridge-all.xml', 'staged-real-bridge-counts.xml', 'staged-real-bridge-scope.xml']:
    path = OUT / name
    suite = ET.parse(path).getroot().find('testsuite')
    reports.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'tests': int(suite.attrib['tests']), 'failures': int(suite.attrib['failures']),
        'errors': int(suite.attrib['errors']), 'seconds': float(suite.attrib['time'])})
record = {
    'status': 'STAGED_COMPONENT_REVIEW',
    'scope': 'Actual staged Python validator and shared Node catalog in disposable databases; read-only TypeScript overlays and compiler unit fixtures.',
    'backend': reports,
    'interpretation': '112/113 complete real-bridge run passed. Its sole malformed-question fixture was corrected with the complete normal question identity and passed its exact rerun. The additional measurement/profile boundary and existing transport case passed together. This is not a single final canonical suite PASS.',
    'frontend': {'semantic_and_compiler_tests': 14, 'typecheck': 'PASS', 'overlay_files': 6},
    'native_reference_inference': 'PENDING', 'original_projects_model_and_saved_simulation': 'PENDING',
    'new_feature_exact_image_delivery': 'PENDING', 'canonical_application_source_changed_by_root': False,
}
(OUT / 'component-review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
proposal_file = OUT / 'dto-contract-proposal.json'
proposal = json.loads(proposal_file.read_text(encoding='utf-8'))
proposal['status'] = 'STAGED_REVIEW_SOURCE_FREEZE_ENDED'
proposal['authoritative_schema'] = 'backend/nis/agent/orchestration/project_intake.py:ReferenceDesignProposal (staged owned manifest)'
proposal['profile_feedback'] = 'Internal shared validator only; whole original request revalidated, exact source profile checked; final project acceptance always checks all facts.'
proposal['machine_result']['devices'][0]['quantity'] = 'Electronic participants individually named quantity=1; physical/software context quantity1..1000.'
proposal['transport_contract'] = {'roles': ['MEASUREMENT', 'COMMAND', 'FEEDBACK', 'STATUS', 'FUNCTION_OUTPUT'],
    'release': 'Existing native CYCLIC/EVENT/MIXED/ON_REQUEST transmission.profile; no fabricated request/event timestamps.',
    'encoding': 'Actuator commands bind to selected or inherited encoding; measurement wire unit/type/payload binds to the existing catalog.',
    'ports': 'Separate stable physical port identities, receive-only without synthetic messages; no-port electronics explicit.'}
proposal_file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Staging review and current contract documentation recorded; native/release outcomes pending.')
