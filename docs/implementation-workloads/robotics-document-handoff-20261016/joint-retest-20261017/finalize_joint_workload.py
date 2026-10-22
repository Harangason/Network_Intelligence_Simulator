"""Finalize joint metadata only after both natives and exact PASS delivery."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
PEER = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016'
FOLLOWUP = PEER / 'followup-communication-actions'
VEHICLE = PEER / 'native-be82385-20261017'
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
parser.add_argument('--delivery-log', type=Path, required=True)
args = parser.parse_args()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def valid_reference(item):
    return ref(item['path'])['sha256'] == item['sha256']


def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}


receipt_path = args.receipt.resolve(strict=True)
receipt = read(receipt_path)
required_checks = {'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests',
                   'browser-e2e', 'small-http', 'large-http'}
assert receipt['status'] == 'PASS'
assert required_checks <= {item['name'] for item in receipt['checks'] if item['exit_code'] == 0}
assert all(item['exit_code'] == 0 for item in receipt['checks'])
runtime = read(OUT / 'native-runtime-preparation.json')
acceptance = read(OUT / 'native-acceptance.json')
vehicle = read(VEHICLE / 'native-verification.json')
vehicle_semantics = read(VEHICLE / 'native-semantic-review.json')
production = read(OUT / 'production-identity-verification.json')
functional = read(OUT / 'production-functional-verification.json')
ui = read(OUT / 'production-ui-verification.json')
assert all(item['status'] == 'PASSED' for item in
           (acceptance, vehicle, vehicle_semantics, production, functional, ui))
assert all(valid_reference(item) for item in acceptance['evidence'])
assert valid_reference(acceptance['peer_vehicle_native'])
assert {item['image_id'] for item in (runtime, acceptance, vehicle, production, functional, ui)} == {receipt['image_id']}
assert runtime['source_sha256'] == receipt['initial_source_sha256'] == vehicle['source_sha256']
assert acceptance['application_source_sha256'] == runtime['source_sha256']
assert production['source_sha256'] == functional['source_sha256'] == ui['source_sha256'] == runtime['source_sha256']
assert production['container_health'] == 'healthy' and production['ready']['status'] == 'ready'
assert read(OUT / 'native-tab-cleanup.json')['status'] == 'CLOSED_OWN_TEMPORARY_TAB'
assert read(OUT / 'native-proposal-facts.json') == read(OUT / 'native-adopted-facts.json')
for directory, names in [(OUT, ['native-verification.json', 'native-classification-review.json',
                               'native-proposal-completeness.json', 'native-question-completeness.json',
                               'native-tool-audit.json', 'native-post-close-tool-audit.json']),
                         (VEHICLE, ['native-tool-audit.json'])]:
    assert all(read(directory / name)['status'] == 'PASSED' for name in names)
assert len(vehicle_semantics['communication_action']) == 1
assert vehicle_semantics['communication_action'][0]['kind'] == 'FUNCTION'
assert vehicle_semantics['communication_action'][0]['role'] == 'OTHER'
assert not vehicle_semantics['missing_requirement_ids']
assert not vehicle_semantics['missing_complete_requirement_lines']
assert not vehicle_semantics['missing_source_units']
assert vehicle_semantics['original_requirement_lines'] == 168
assert acceptance['complete_requirements'] == 110 and acceptance['functions'] == 97
freeze = read(FOLLOWUP / 'source-freeze.json')
assert production['module_hashes'] == freeze['files']
assert receipt['initial_commit_id'] == freeze['commit_id'] == production['build']['commit_id']
targeted_xml = FOLLOWUP / 'targeted-backend-final.xml'
suite = ET.parse(targeted_xml).getroot()
assert len(list(suite.iter('testcase'))) == 30
assert not list(suite.iter('failure')) and not list(suite.iter('error'))
frontend = (FOLLOWUP / 'targeted-frontend.log').read_text(encoding='utf-8-sig')
assert re.search(r'# pass 114\b', frontend) and re.search(r'# fail 0\b', frontend)
peer_work = read(FOLLOWUP / 'workload.json')
for group in ('before', 'after', 'diff'):
    assert peer_work[group] and all(valid_reference(item) for item in peer_work[group])

work_path = OUT / 'workload.json'
work = read(work_path)
work['outcomes'].update({
    'communication_repair_verified': passed(OUT / 'independent-communication-patch-review.json',
                                           targeted_xml, VEHICLE / 'native-semantic-review.json'),
    'robotics_native_full_retest': passed(OUT / 'native-acceptance.json', OUT / 'native-verification.json'),
    'vehicle_native_full_retest': passed(VEHICLE / 'native-verification.json', VEHICLE / 'native-tool-audit.json'),
    'complete_release_pass': passed(receipt_path),
    'exact_image_productive': passed(receipt_path, OUT / 'production-identity-verification.json',
                                     OUT / 'production-functional-verification.json'),
})
work['validations'] = {
    'literal_source_complete_handoff': passed(OUT / 'native-acceptance.json', VEHICLE / 'native-verification.json'),
    'both_native_runs_same_image': passed(OUT / 'native-tool-audit.json', VEHICLE / 'native-tool-audit.json'),
    'official_full_gate': passed(receipt_path),
    'running_image_health_and_function': passed(OUT / 'production-identity-verification.json',
                                               OUT / 'production-functional-verification.json',
                                               OUT / 'production-ui-verification.json'),
}
work['files_changed'] = peer_work['files_changed']
work['shared_change_ownership'] = 'Canonical two-file application/test repair applied by NIS starten; this chat only coordinated and verified with separate metadata/evidence helpers.'
for group in ('before', 'after', 'diff'):
    work[group] = peer_work[group]
work['delivery'].update(tested_version=receipt['image_id'], running_version=production['image_id'], checks={
    'release': passed(receipt_path),
    'deployment': passed(OUT / 'production-identity-verification.json', args.delivery_log),
    'health': passed(OUT / 'production-identity-verification.json'),
    'functional': passed(OUT / 'production-functional-verification.json', OUT / 'production-ui-verification.json'),
})
work['status'] = work['completion_status'] = 'COMPLETED'
work['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
work['verification_phase'] = 'BOTH_NEW_NATIVE_PASSED_EXACT_FULL_PASS_IMAGE_DEPLOYED_AND_VERIFIED'
work['remaining_findings'] = []
work['source_question_scope'] = 'Unproven robot quantities/types/connections/owners remain explicit source decisions. This completes original-file analysis/structured handoff and correction delivery; no nine-stage robot model or safety claim. Subsequent vehicle execution and later HMI inputs remain separately evidenced by NIS starten.'
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': work['status'], 'image_id': production['image_id'],
                  'source_sha256': production['source_sha256']}))
