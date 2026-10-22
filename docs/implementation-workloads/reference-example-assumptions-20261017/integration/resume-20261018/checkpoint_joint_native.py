"""Record operator progress only; never writes any NIS model or proposal."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = Path(__file__).resolve().parent
INTEGRATION = BASE.parent
receipt_path = ROOT / 'backend/test-output/release-gates/joint-reference-portfolio-native-cf37e30cc3a5/d520e6b852e5/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['image_id'] == 'sha256:2c2840df896a406910ef4c1c68f3c43afcb48f819dae1f493805d0aeb4d0d896'
assert receipt['initial_source_sha256'] == 'cf37e30cc3a5e18124c1eec3936373c4920d295d48657b70dcbc0ee9be929b56'
cases = [
    ('vehicle', '20261018110232672-964994ce', Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt'), '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7', 19088),
    ('robot', '20261018113821095-5bb997f2', Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md'), '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef', 63705),
]
at = datetime.now(timezone.utc).isoformat()
for name, project, original, expected_hash, chars in cases:
    raw = original.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == expected_hash, (name, digest)
    assert len(raw.decode('utf-8')) == chars, (name, 'original text size changed')
    state = {
        'at_utc': at, 'project_id': project, 'source': str(original),
        'original_sha256': digest, 'original_chars': chars,
        'image_tag': receipt['image_tag'], 'image_id': receipt['image_id'],
        'source_sha256': receipt['initial_source_sha256'],
        'candidate_status': receipt['status'],
        'base_url': receipt['base_url'],
        'engineering_url': receipt['base_url'] + '/studio/engineering?project=' + project,
        'status': 'NATIVE_DOCUMENT_INTAKE_RUNNING' if name == 'vehicle' else 'ORIGINAL_UPLOADED_WAITING_SERIAL_INFERENCE',
        'source_transfer': 'Normal browser file chooser; UI confirms full text read.',
        'manual_model_corrections': False, 'model_generated': False,
        'simulation_pass': False, 'full_release_pass': False,
        'productive_delivery': False,
    }
    target = INTEGRATION / ('native-joint-' + name)
    target.mkdir(exist_ok=True)
    (target / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
workload_path = INTEGRATION / 'workload.json'
workload = json.loads(workload_path.read_text(encoding='utf-8'))
workload['active_stage'] = {'stage': 'NATIVE_ORIGINAL_DOCUMENT_INTAKE', 'at_utc': at, 'candidate_receipt': str(receipt_path), 'session_id': None, 'full_pass': False}
workload['joint_delivery'].update(new_candidate_status='PREPARED', native_vehicle_project=cases[0][1], native_robot_project=cases[1][1], production_changed=False, full_pass=False)
workload['storage_resolution']['subsequent_explicit_confirmation'] = {
    'question_id': 'call_c2394a49c943474fbf83284e996e63c1/0',
    'answer': 'Genau dieses archivierte Image entfernen und fortsetzen',
    'scope': 'networkis:candidate-43d202d1dbde only; already removed, not repeated',
}
workload['completion_status'] = 'Joint candidate PREPARED and healthy. Both originals fully uploaded into new isolated projects; actual local Qwen vehicle intake running. Both native simulations, full release gate and productive delivery pending.'
workload_path.write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'CHECKPOINT_SAVED', 'vehicle_project': cases[0][1], 'robot_project': cases[1][1], 'original_hashes_verified': True}))
