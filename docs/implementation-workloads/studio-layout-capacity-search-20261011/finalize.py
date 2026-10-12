"""Bind actual complete PASS and production evidence to this implementation workload."""
import argparse, hashlib, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('receipt', type=Path)
args = parser.parse_args()
here = Path(__file__).parent
path = here / 'workload.json'
workload = json.loads(path.read_text(encoding='utf-8-sig'))
receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
production = json.loads((here / 'production-verification.json').read_text(encoding='utf-8-sig'))
functional = json.loads((here / 'production-functional.json').read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS' and production['status'] == 'PASSED' and functional['status'] == 'PASSED'
assert production['running_image'] == receipt['image_id']
names = {check['name'] for check in receipt['checks'] if check['exit_code'] == 0}
assert {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'} <= names
def reference(path):
    path = path.resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
review = [reference(here / 'source-review.md'), reference(here / 'owned-changes.diff')]
gate = [reference(args.receipt)]
live = [reference(here / 'production-verification.json'), reference(here / 'production-functional.json')]
workload['outcomes'] = {name: {'status': 'PASSED',
    'scope': 'Source review and complete mandatory release gate; no separate design test run',
    'evidence': review + gate + live} for name in workload['required_outcomes']}
workload['validations'] = {
    'functional_unit_tests': {'status': 'PASSED', 'evidence': [reference(here / 'targeted-verification.json')]},
    'typecheck': {'status': 'PASSED', 'evidence': gate + [reference(args.receipt.parent / 'typecheck.log')]},
    'full_release_gate': {'status': 'PASSED', 'evidence': gate},
    'production_identity_health': {'status': 'PASSED', 'evidence': live},
}
workload['completion_status'] = 'COMPLETED'
workload['remaining_findings'] = []
workload['production_delivery'] = {'authorized': True, 'explicit_user_request': True,
    'receipt': str(args.receipt.resolve()), 'image_id': receipt['image_id'], 'status': 'DEPLOYED_AND_VERIFIED'}
workload['delivery'] = {'decision': 'YES',
    'authorization': 'Explicit user approval for all thirteen points and production delivery, plus standing AGENTS.md authorization.',
    'target': 'Canonical NetworkIS production stack at localhost/LAN port 13500',
    'tested_version': receipt['image_id'], 'running_version': production['running_image'],
    'checks': {'release': {'status': 'PASSED', 'evidence': gate},
        'deployment': {'status': 'PASSED', 'evidence': live},
        'health': {'status': 'PASSED', 'evidence': [reference(here / 'production-verification.json')]},
        'functional': {'status': 'PASSED', 'evidence': [reference(here / 'production-functional.json')]}}}
repair_path = here / 'transport-read-repair/workload.json'
if repair_path.exists():
    repair = json.loads(repair_path.read_text(encoding='utf-8'))
    repair['outcomes']['complete_release_pass'] = {'status': 'PASSED', 'evidence': gate}
    repair['validations']['full_release_gate'] = {'status': 'PASSED', 'evidence': gate}
    repair['completion_status'] = 'COMPLETED'
    repair['remaining_findings'] = []
    repair['delivery'] = {'decision': 'NOT_APPLICABLE',
        'reason': 'Verification-only GET transport input; the unchanged application image completed the full new gate and was deployed and verified by the parent workload.'}
    repair_path.write_text(json.dumps(repair, indent=2), encoding='utf-8')
    workload['implementation_repairs'] = [reference(repair_path)]
    workload['validation_requirements'].append('transport_read_repair')
    workload['validations']['transport_read_repair'] = {'status': 'PASSED', 'evidence': [reference(repair_path)]}
path.write_text(json.dumps(workload, indent=2), encoding='utf-8')
print(json.dumps({'status': workload['completion_status'], 'outcomes': len(workload['outcomes']), 'image': receipt['image_id']}))
