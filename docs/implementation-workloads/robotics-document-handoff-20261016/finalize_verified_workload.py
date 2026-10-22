"""Complete metadata only after actual gate, native and production evidence."""
from pathlib import Path
import argparse
from datetime import datetime
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
NATIVE = OUT / 'native-attempt-2'
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
receipt_path = args.receipt.resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and all(c['exit_code'] == 0 for c in receipt['checks'])
native = json.loads((NATIVE / 'native-verification.json').read_text(encoding='utf-8'))
audit = json.loads((NATIVE / 'native-tool-audit.json').read_text(encoding='utf-8'))
runtime = json.loads((NATIVE / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
production = json.loads((OUT / 'production-identity-verification.json').read_text(encoding='utf-8'))
functional = json.loads((OUT / 'production-functional-verification.json').read_text(encoding='utf-8'))
assert native['status'] == audit['status'] == production['status'] == functional['status'] == 'PASSED'
assert runtime['image_id'] == production['image_id'] == functional['image_id'] == receipt['image_id']
assert audit['image_id'] == receipt['image_id']
assert runtime['source_sha256'] == production['source_sha256'] == receipt['initial_source_sha256']
suite = ET.parse(OUT / 'targeted-backend.xml').getroot()
tests = [node for node in suite.iter('testcase')]
assert len(tests) == 252 and not list(suite.iter('failure')) and not list(suite.iter('error'))
manifest = json.loads((OUT / 'source-final-before-gate.json').read_text(encoding='utf-8'))
assert (OUT / 'targeted-backend.xml').stat().st_mtime > datetime.fromisoformat(manifest['built_at']).timestamp()
frontend = (OUT / 'semantic-frontend-tests.log').read_text(encoding='utf-8-sig')
assert re.search(r'# pass 114\b', frontend) and re.search(r'# fail 0\b', frontend)
work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))

def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}

work['outcomes'] = {
    'source_context_classification': passed(NATIVE / 'native-verification.json', NATIVE / 'native-adopted-facts.json'),
    'all_typed_facts_handoff': passed(NATIVE / 'native-verification.json', NATIVE / 'native-proposal-facts.json', NATIVE / 'native-adopted-facts.json'),
    'complete_real_robotics_wizard_acceptance': passed(NATIVE / 'native-verification.json', NATIVE / 'native-runtime-preparation.json', NATIVE / 'native-tool-audit.json'),
    'verified_production_delivery': passed(receipt_path, OUT / 'production-identity-verification.json', OUT / 'production-functional-verification.json'),
}
work['validations'] = {
    'targeted_regressions': passed(OUT / 'targeted-backend.xml', OUT / 'semantic-frontend-tests.log'),
    'frontend_typecheck': passed(OUT / 'semantic-typecheck-verification.json', receipt_path),
    'real_robotics_wizard': passed(NATIVE / 'native-verification.json', NATIVE / 'native-tool-audit.json'),
    'full_release_gate': passed(receipt_path),
    'production_identity_health_function': passed(OUT / 'production-identity-verification.json', OUT / 'production-functional-verification.json'),
}
work['before'] = [ref(OUT / 'before' / relative) for relative, old in work['revision_before_initial_apply'].items() if old]
work['after'] = [ref(OUT / 'after' / relative) for relative in work['revision_after']]
work['diff'] = [ref(OUT / 'prepared-owned.diff')]
work['delivery'].update(tested_version=receipt['image_id'], running_version=production['image_id'], checks={
    'release': passed(receipt_path), 'deployment': passed(OUT / 'production-identity-verification.json', OUT / 'production-deploy.log'),
    'health': passed(OUT / 'production-identity-verification.json'), 'functional': passed(OUT / 'production-functional-verification.json'),
})
work['status'] = work['completion_status'] = 'COMPLETED'
work['verification_phase'] = 'EXACT_PASS_IMAGE_DEPLOYED_AND_VERIFIED'
work['remaining_findings'] = []
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': work['status'], 'image_id': production['image_id']}))
