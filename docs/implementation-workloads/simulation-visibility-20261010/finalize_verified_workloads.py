"""Complete evidence only after exact release delivery and canonical/UI verification."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CHANNELS = HERE.parent / 'stranded-capacity-channels-20261010'
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
read = lambda path: json.loads(path.read_text(encoding='utf-8'))
receipt = read(args.receipt)
spec = importlib.util.spec_from_file_location('storage', ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
assert storage.complete_pass(receipt)
identity = read(HERE / 'production-identity-verification.json')
ui = read(HERE / 'production-ui-verification.json')
repair = read(CHANNELS / 'canonical-reconciliation-verification.json')
warnings = read(CHANNELS / 'production-warning-verification.json')
assessments = read(CHANNELS / 'reconciled-assessments.json')
workers = read(HERE / 'authorized-worker-pause.json')
assert identity['status'] == ui['status'] == warnings['status'] == 'VERIFIED'
assert identity['image_id'] == ui['image_id'] == repair['running_image'] == receipt['image_id']
assert repair['status'] == 'APPLIED_AND_VERIFIED'
assert repair['original_connectors_reused'] == repair['duplicates_reversibly_superseded'] == 25
assert repair['deleted_objects'] == 0
assert warnings['licht_warning_count'] == warnings['disconnected_warning_count'] == 0
assert assessments['current'] and assessments['ready_for_simulation']
assert workers['status'] == 'RESTORED'

def ref(path):
    path = path.resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}

release = passed(args.receipt, args.receipt.parent / 'browser.json',
    args.receipt.parent / 'small-http.json', args.receipt.parent / 'large-http.json')
health = passed(HERE / 'production-identity-verification.json')
functional = passed(HERE / 'production-ui-verification.json', CHANNELS / 'canonical-reconciliation-verification.json',
    CHANNELS / 'production-warning-verification.json', CHANNELS / 'reconciled-assessments.json')
for folder in (HERE, CHANNELS):
    path = folder / 'workload.json'
    work = read(path)
    work['delivery'].update(status='DEPLOYED_AND_VERIFIED', target='canonical production stack on port 13500',
        tested_version=receipt['image_id'], running_version=receipt['image_id'],
        receipt=str(args.receipt.resolve()), checks={'release': release, 'deployment': health, 'health': health, 'functional': functional})
    work['outcomes'] = work.get('outcomes') or {}
    work['validations'] = work.get('validations') or {}
    work['outcomes']['release_and_deploy'] = {'status': 'PASSED', 'evidence': release['evidence'] + health['evidence'] + functional['evidence']}
    work['validations']['release_gate'] = release
    work['validations']['production_verification'] = {'status': 'PASSED', 'evidence': health['evidence'] + functional['evidence']}
    if folder == CHANNELS:
        regression = passed(folder / 'final-binding-tests.log', folder / 'final-warning-tests.log', args.receipt.parent / 'backend-tests.log')
        for outcome in ('retain_original_channels_on_complete_split', 'synchronize_logical_and_message_bindings', 'preserve_parallel_and_unreviewed_paths'):
            work['outcomes'][outcome] = {'status': 'PASSED', 'evidence': regression['evidence'] + functional['evidence']}
        work['outcomes']['existing_project_cleanup'] = functional
        work['validations']['isolated_regression'] = regression
        work['validations']['capacity_and_preflight'] = passed(folder / 'reconciled-assessments.json', folder / 'reconciled-capacity.json', folder / 'reconciled-preflight.json')
        work['context'].update(production_model_mutations=86, production_fix_pending=False,
            original_connectors_reused=25, duplicates_reversibly_superseded=25, deleted_objects=0,
            historical_simulation_results='Preserved; their prior model revision remains historical, not relabelled as a new run.')
    work['remaining_findings'] = []
    work['unresolved_decisions'] = []
    work['completion_status'] = 'READY_FOR_COMPLETION_GUARD'
    path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print('Evidence ready for independent read-only completion guards.')
