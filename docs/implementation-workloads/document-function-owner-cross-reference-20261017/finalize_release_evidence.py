"""Finalize this scoped code delivery only after complete real release proofs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
path = OUT / 'workload.json'
workload = json.loads(path.read_text(encoding='utf-8'))
receipt_path = ROOT / workload['release_receipt']
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
freeze = json.loads((OUT / 'source-freeze.json').read_text(encoding='utf-8'))
production_path = OUT / 'production-verification.json'
production = json.loads(production_path.read_text(encoding='utf-8'))
removal = json.loads((OUT / 'removal-result.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and all(check['exit_code'] == 0 for check in receipt['checks'])
assert {check['name'] for check in receipt['checks']} >= {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'}
assert receipt['initial_source_sha256'] == freeze['source_sha256'] == production['source_sha256']
assert receipt['verification_sha256'] == freeze['verification_sha256']
assert production['status'] == 'PASSED' and production['image_id'] == receipt['image_id']
assert removal['status'] == 'REMOVED' and removal['archive_retained'] and removal['production_unchanged']


def ref(file):
    return {'path': str(file.resolve()), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}


workload['status'] = 'COMPLETED'
workload['outcomes']['verified_exact_image_productive'] = {'status': 'PASSED', 'evidence': [ref(production_path)]}
workload['validations']['full_release_gate'] = {'status': 'PASSED', 'evidence': [ref(receipt_path)]}
workload['validations']['production_identity_function'] = {'status': 'PASSED', 'evidence': [ref(production_path)]}
workload['delivery'].update(tested_version=receipt['image_id'], running_version=production['image_id'],
    release={'status': 'PASSED', 'evidence': [ref(receipt_path)]},
    deployment={'status': 'PASSED', 'evidence': [ref(production_path)]},
    health={'status': 'PASSED', 'evidence': [ref(production_path)]},
    functional={'status': 'PASSED', 'evidence': [ref(production_path)]})
workload['delivery']['checks'] = {
    key: workload['delivery'][key] for key in ('release', 'deployment', 'health', 'functional')
}
workload['current_production_contains_this_repair'] = True
workload['actual_vehicle_simulation_completed'] = False
workload['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
workload['completion_scope'] = 'Only exact unique cross-section source-owner code repair and verified delivery. Original model/simulation and reference-design completion remain separate required work.'
path.write_text(json.dumps(workload, indent=2) + '\n', encoding='utf-8')
(OUT / 'release-pass-receipt.json').write_bytes(receipt_path.read_bytes())
print(json.dumps({'status': 'SCOPED_CODE_DELIVERY_COMPLETE', 'image_id': receipt['image_id'], 'source_sha256': freeze['source_sha256'], 'original_vehicle_simulation_complete': False}))
