"""Record completion only after the full release and verified canonical repair."""
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

folder = Path(__file__).resolve().parent
work_path = folder / 'workload.json'
work = json.loads(work_path.read_text())
root = Path(work['repository'])
receipt_path = Path(work['active_release_receipt'])
receipt = json.loads(receipt_path.read_text())
assert receipt['status'] == 'PASS'
required_checks = {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests',
                   'production-build', 'browser-e2e', 'small-http', 'large-http'}
checks = {item['name']: item['exit_code'] for item in receipt['checks']}
assert required_checks <= checks.keys() and all(checks[name] == 0 for name in required_checks)
delivery_path = folder / 'production-delivery-verification.json'
delivery = json.loads(delivery_path.read_text())
alignment_path = folder / 'existing-project-alignment-verification.json'
alignment = json.loads(alignment_path.read_text())
assert delivery['tested_image'] == delivery['running_image'] == receipt['image_id']
assert all(delivery['project_unchanged_by_deployment'].values())
assert alignment['status'] == 'APPLIED_AND_VERIFIED' and all(alignment['checks'].values())
functional_path = folder / 'production-functional-verification.json'
functional = json.loads(functional_path.read_text())
assert functional['remaining_primary_repairs'] == 0
assert functional['running_image'] == receipt['image_id']
assert functional['licht']['hardware_interface_id'] == alignment['licht'][0]['after']
assessment_path = folder / 'existing-project-refreshed-assessments.json'
assessment = json.loads(assessment_path.read_text())
assert assessment['capacity_status'] == 'COMPLETE' and assessment['preflight_status'] == 'READY'
assert assessment['ready_for_simulation'] and assessment['preflight_is_current']
ui_path = folder / 'production-ui-verification.json'
ui = json.loads(ui_path.read_text())
assert ui['observed_build'] == receipt['release']['build_id']
assert ui['frontend_backend_agree'] and not ui['message_sender_warning_present']
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == receipt['image_id']
health_path = folder / 'production-final-health.json'
health = {'running_image': receipt['image_id'], 'endpoints': {}}
for base in ('http://127.0.0.1:13500', 'http://192.168.178.10:13500'):
    with urlopen(base + '/api/ready', timeout=30) as response:
        ready = json.load(response)
        assert response.status == 200 and ready['status'] == 'ready'
    with urlopen(base + '/api/build-info', timeout=30) as response:
        build = json.load(response)
        assert response.status == 200 and build['source_sha256'] == receipt['initial_source_sha256']
    health['endpoints'][base] = {'ready': ready, 'source_sha256': build['source_sha256']}
health_path.write_text(json.dumps(health, indent=2), encoding='utf-8')

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}

work['validations']['release_gate'] = passed(receipt_path)
work['validations']['live_verification'] = passed(delivery_path, alignment_path, functional_path, ui_path)
if 'postrepair_assessments' not in work['validation_requirements']:
    work['validation_requirements'].append('postrepair_assessments')
work['validations']['postrepair_assessments'] = passed(assessment_path, folder / 'existing-project-refreshed-preflight.json')
work['outcomes']['production_delivery'] = passed(receipt_path, delivery_path)
work['outcomes']['existing_project_consistency'] = passed(alignment_path, functional_path)
assert 'existing_project_consistency' in work['required_outcomes']
work['delivery'].update(status='DEPLOYED_AND_VERIFIED', tested_version=receipt['image_id'],
                        running_version=receipt['image_id'], checks={
    'release': passed(receipt_path), 'deployment': passed(delivery_path),
    'health': passed(delivery_path, health_path), 'functional': passed(alignment_path, functional_path, ui_path, assessment_path)})
work['resource_observations'] = ['Licht retains one actual unconnected hardware-interface warning; the stale message sender warning is removed. Hardware inventory and physical paths were preserved.']
work['assessment_observations'] = ['Capacity is COMPLETE and current preflight is READY. Prior simulation/results/assessment snapshots correctly remain OUTDATED after the model correction; their identities and jobs are preserved.']
work['remaining_findings'] = []
work['unresolved_decisions'] = []
work['completion_status'] = 'VALIDATING'
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
guard = Path('F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py')
result = subprocess.run([str(root / 'backend/.venv/Scripts/python.exe'), str(guard),
                         'completion', '--workload', str(work_path)], capture_output=True, text=True, check=True)
completion = json.loads(result.stdout)
assert completion['status'] == 'COMPLETED' and not completion['issues']
(folder / 'completion-guard.json').write_text(json.dumps(completion, indent=2), encoding='utf-8')
work['completion_status'] = 'COMPLETED'
work['completion_evidence'] = ref(folder / 'completion-guard.json')
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'status': 'COMPLETED', 'image_id': receipt['image_id'], 'aligned': alignment['aligned']}))
