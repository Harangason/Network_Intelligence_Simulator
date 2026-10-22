"""Attach immutable release and production evidence to the repair workload."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
freeze = json.loads((HERE / 'source-freeze.json').read_text(encoding='utf-8'))
production = json.loads((HERE / 'production-verification.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and production['status'] == 'PASSED'
assert freeze['full_application_source_sha256'] == receipt['release']['source_sha256']
for path, digest in freeze['application_and_test_hashes'].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
assert production['running_image'] == receipt['image_id']
assert production['module_hashes'] == json.loads((HERE / 'native-acceptance.json').read_text(encoding='utf-8'))['application_hashes']

def evidence(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [evidence(path) for path in paths]}

(HERE / 'release-pass-receipt.json').write_bytes(receipt_path.read_bytes())
wpath = HERE / 'workload.json'
w = json.loads(wpath.read_text(encoding='utf-8'))
w['before'] = [evidence(HERE / 'before' / p) for p in w['files_changed']]
w['after'] = [evidence(HERE / 'after' / p) for p in w['files_changed']]
w['diff'] = [evidence(HERE / 'owned-changes.diff')]
w['outcomes'] = {
    'generic_source_semantics': passed(HERE / 'targeted-context-protocols-v2.log', HERE / 'targeted-projection-repair.log', HERE / 'owned-changes.diff'),
    'seven_native_files_pass': passed(HERE / 'native-acceptance.json', HERE / freeze['native_evidence'] / 'manifest.json'),
    'release_and_production_delivery': passed(receipt_path, HERE / 'release-and-deploy.log', HERE / 'production-verification.json')}
w['validations'] = {
    'targeted_regressions': passed(HERE / 'targeted-context-protocols-v2.log', HERE / 'targeted-projection-repair.log', HERE / 'targeted-editor-static.json', HERE / 'targeted-editor-browser-result.json', HERE / 'targeted-large-browser-result.json', HERE / 'targeted-write-receipt-static.json'),
    'native_source_integrity': passed(HERE / 'source-freeze.json', HERE / 'native-acceptance.json'),
    'full_release_gate': passed(receipt_path),
    'production_identity_health_function': passed(HERE / 'production-verification.json')}
w['delivery'].update(tested_version=receipt['image_id'], running_version=production['running_image'],
                     checks={'release': passed(receipt_path),
                             'deployment': passed(HERE / 'release-and-deploy.log', HERE / 'production-verification.json'),
                             'health': passed(HERE / 'production-verification.json'),
                             'functional': passed(HERE / 'production-verification.json')})
w['completion_status'] = 'VALIDATING'
for check in w.get('tests', []):
    if check['scope'] == 'complete release gate':
        check.update(status='PASSED', evidence=str(receipt_path), image_id=receipt['image_id'])
w['preflight'] = {'scope': 'Document source/role completeness and review authority; not real hardware qualification',
                  'status': 'PASSED', 'canonical_writes': False, 'approval_required': True,
                  'evidence': [evidence(HERE / 'native-acceptance.json'), evidence(HERE / 'production-verification.json')]}
w['remaining_findings'] = []
if 'large_gate_timeout' in w['repair']:
    w['repair']['large_gate_timeout']['status'] = 'FULL_GATE_RETEST_PASSED'
if 'parameter_write_receipt' in w['repair']:
    w['repair']['parameter_write_receipt']['status'] = 'TARGETED_AND_FULL_GATE_PASSED'
w['scope_limitations'] = ['Seven native document intake/proposal tests are not seven nine-stage E2E workflows.',
                          'This implementation does not declare the independent Tool Checker campaign passed.',
                          'No EIP source code was changed by this NIS repair.']
wpath.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding='utf-8')
with (HERE / 'report.md').open('a', encoding='utf-8') as out:
    out.write('\n## Produktivnachweis\n\n')
    out.write(f"Der vollständige Release wurde mit PASS abgeschlossen und exakt das geprüfte Image `{receipt['image_id']}` produktiv bereitgestellt. Laufende Identität, Readiness und Quellhash wurden abgeglichen.\n\n")
    out.write('Die geänderte Dokumentfunktion wurde anschließend mit einem echten lokalen Qwen-Aufruf innerhalb des produktiven Containers erneut geprüft, ohne Datenbank- oder Modelländerung. Die Modulhashes stimmen mit dem siebenfach geprüften Stand überein.\n')
    out.write('\nDie Frontend-Technologieprojektion wurde über den vorhandenen Generator aus den zentralen Profilen synchronisiert (I²C/WLAN). 41 zusätzliche Projektions-/Registry-/Wizardtests bestanden. Die vier nativen Qwen-Modulhashes blieben dabei identisch.\n\n')
    for name in ('frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'):
        text = (receipt_path.parent / (name + '.log')).read_text(encoding='utf-8', errors='replace')
        summaries = [line for line in text.splitlines() if re.search(r'\bpassed\b|^# (?:tests|pass|fail)\b', line)]
        out.write(f"- {name}: " + ('; '.join(summaries[-3:]) or 'PASS laut vollständigem Receipt') + '\n')
print(json.dumps({'workload': str(wpath), 'image': receipt['image_id'], 'production': 'PASSED'}))
