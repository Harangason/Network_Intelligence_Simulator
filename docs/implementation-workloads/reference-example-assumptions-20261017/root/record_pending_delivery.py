"""Record passed bounded checks and the explicit unresolved delivery blocker."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
validation = OUT.parent / 'integration/current-validation.json'
report = json.loads(validation.read_text(encoding='utf-8'))
checks = report['checks']
assert checks['canonical_backend']['status'] == 'PASSED'
assert checks['canonical_frontend']['status'] == 'PASSED'
assert checks['canonical_typecheck']['status'] == 'PASSED'
ref = {'path': str(validation), 'sha256': hashlib.sha256(validation.read_bytes()).hexdigest()}
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work.update(status='WAITING_FOR_DECISION', completion_status='IMPLEMENTED_NOT_NATIVE_VERIFIED_OR_DEPLOYED',
    remaining_findings=['Human decision on fully archived candidate-66a892b0b219 removal pending in NIS starten; newer PREPARED receipt prevents standing FAIL-only cleanup.',
        'Exact new candidate build, both complete original native Wizard/model/simulation runs and full release gate pending',
        'New reference feature is not yet in production'],
    unresolved_decisions=['Existing archived-image cleanup permission question in NIS starten'])
for name in ['targeted_unit_component_regressions', 'isolated_backend_regressions', 'typecheck']:
    work['validations'][name] = {'status': 'PASSED', 'evidence': [ref],
        'scope': 'Canonical unit/component checks and real disposable SQL persistence with a mocked reference plan; not native original-file or release proof.'}
work['delivery'].update(status='PENDING', blocker='Candidate image-count budget full; archived-image human decision pending')
work['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
state_path = ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics/state.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(status='WAITING_FOR_DECISION', last_updated_utc=work['last_updated_utc'],
    canonical_component_checks={'backend':checks['canonical_backend'], 'frontend':checks['canonical_frontend'],
                                'typecheck':checks['canonical_typecheck']},
    new_feature_productive=False, robotics_model_writes=False, robotics_simulation_started=False)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status':work['status'], 'backend':checks['canonical_backend'].get('tests'),
    'frontend':checks['canonical_frontend'].get('tests'), 'original_file_simulations':'PENDING', 'new_feature_delivery':'PENDING'}))
