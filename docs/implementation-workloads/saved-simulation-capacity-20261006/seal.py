"""Bind completion to actual PASS, immutable deployment and live project evidence."""
import hashlib
import json
from pathlib import Path
import sys

out = Path(__file__).parent
receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
required_checks = {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests',
                   'browser-e2e', 'small-http', 'large-http'}
assert receipt['status'] == 'PASS'
assert required_checks <= {row['name'] for row in receipt['checks'] if row['exit_code'] == 0}
proof_path = out / 'functional-proof.json'
proof = json.loads(proof_path.read_text(encoding='utf-8'))
assert proof['status'] == 'PASSED'
assert proof['image_id'] == receipt['image_id']
assert proof['source_sha256'] == receipt['release']['source_sha256']
assert proof['saved_rates_unchanged'] and proof['save_reload_stable']
assert proof['false_missing_rate_findings'] == 0

def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

gate = ref(receipt_path)
functional = ref(proof_path)
deployment = ref(out / 'deployment.log')
review = ref(out / 'after-reload-live/review.json')
build = ref(out / 'after-reload-live/build.json')
browser = ref(out / 'browser-repair.log')
work_path = out / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work['outcomes'] = {
    'saved_native_parameter_resolution': {'status': 'PASSED', 'evidence': [functional, browser, gate]},
    'correct_simulation_capacity_review': {'status': 'PASSED', 'evidence': [review, functional, gate]},
    'shared_sizing_and_validation': {'status': 'PASSED', 'evidence': [gate, functional]},
    'production_delivery': {'status': 'PASSED', 'evidence': [gate, deployment, build, functional]},
}
work['validations'] = {
    'targeted_regression': {'status': 'PASSED', 'evidence': [browser, gate]},
    'full_release_gate': {'status': 'PASSED', 'evidence': [gate]},
    'production_verification': {'status': 'PASSED', 'evidence': [functional, review, build]},
}
work['delivery'].update(tested_version=receipt['image_id'], running_version=proof['image_id'], checks={
    'release': {'status': 'PASSED', 'evidence': [gate]},
    'deployment': {'status': 'PASSED', 'evidence': [deployment, functional]},
    'health': {'status': 'PASSED', 'evidence': [functional, build]},
    'functional': {'status': 'PASSED', 'evidence': [functional, review]},
})
work['remaining_findings'] = []
work['limitations'] = ['Project scenario load is calculated under recorded assumptions; actual device, schedule and functional timing qualification remain separate.',
                       'Nine-stage release evidence comes from isolated small and unchanged large fixtures, not a claim of completion of the pending user model.']
work['completion_status'] = 'COMPLETED'
work_path.write_text(json.dumps(work, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'status': 'COMPLETED', 'receipt': str(receipt_path), 'image_id': proof['image_id']}))
