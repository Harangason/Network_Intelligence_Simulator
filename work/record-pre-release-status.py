from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
progress_path = folder / 'progress.json'
progress = json.loads(progress_path.read_text(encoding='utf-8'))
first = root / 'backend/test-output/release-gates/delivery-cf7061c7af49/14f85abc1de2/receipt.json'
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
progress['complete_release_gate'] = 'FAILED_FIRST_RUN_REPAIRED_AWAITING_FULL_RERUN'
progress['release_history'] = [{'status': 'FAIL', 'evidence': ref(first),
    'scope': 'First full gate; 117 backend failures. No candidate image or production deployment.'}]
progress['production_delivered'] = False
progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
work_path = folder / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work['validation']['complete_release_gate'] = {'status': 'FAILED_FIRST_RUN_AWAITING_FULL_RERUN',
                                             'evidence': [ref(first), ref(progress_path)]}
work['documentation_followup']['status'] = 'UPDATED_AWAITING_VERIFIED_DELIVERY'
work['audit_notes'].append('Public profile/transport data isolation verified for all 125 registered identities; internal validation reads definitions without repeated copies. Full fresh gate remains mandatory.')
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'profiles': 125, 'gate': progress['complete_release_gate'], 'production_delivered': False}))
