from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

progress_path = folder / 'progress.json'
progress = json.loads(progress_path.read_text(encoding='utf-8'))
progress['complete_release_gate'] = 'SECOND_GATE_FAILED_REPAIRED_AWAITING_FULL_RERUN'
progress['production_delivered'] = False
progress['release_history'] = [
    {'status': 'FAIL', 'evidence': ref(root / path), 'scope': scope}
    for path, scope in [
        ('backend/test-output/release-gates/delivery-cf7061c7af49/14f85abc1de2/receipt.json',
         '117 backend failures, 21251 passed; no candidate built or deployed.'),
        ('backend/test-output/release-gates/delivery-12bbdd6bffbb/b4c8fffb0ff0/receipt.json',
         '53 backend failures, 21442 passed; large native capacity and original encodings passed; no candidate built or deployed.')]]
progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
work_path = folder / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work['validation']['complete_release_gate'] = {'status': 'AWAITING_FULL_RERUN',
    'evidence': [row['evidence'] for row in progress['release_history']]}
work['documentation_followup']['status'] = 'UPDATED_AWAITING_VERIFIED_DELIVERY'
work['audit_notes'].append('Second full gate exposed canonical/UI rate alias disagreement in artifact readiness. The repair retains native provenance and conflicting facts, blocks missing conditional evidence, and qualifies only explicit virtual LIN test inputs. Required full gate and exact image deployment remain outstanding.')
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'profiles': 125, 'status': progress['complete_release_gate'], 'production_delivered': False}))
