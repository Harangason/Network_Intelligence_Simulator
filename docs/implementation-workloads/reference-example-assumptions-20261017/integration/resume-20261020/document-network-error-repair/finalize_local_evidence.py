"""Record scoped local checks without claiming native model/release acceptance."""
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
PARENT = OUT.parent / 'document-stream-lifecycle-repair'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ref(path):
    return {'path': str(path), 'sha256': sha(path)}

work = read(OUT / 'workload.json')
tap = (OUT / 'frontend-final-18.tap').read_text()
assert '# pass 18' in tap and '# fail 0' in tap
browser = read(OUT / 'browser-final.json')
assert browser['stats']['expected'] == 4 and browser['stats']['unexpected'] == 0
assert browser['stats']['skipped'] == 0 and browser['stats']['flaky'] == 0
assert read(OUT / 'typecheck-result.json')['exit_code'] == 0
diff = []
after = []
for name in work['files_changed']:
    before = OUT / 'before' / name
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, destination)
    after.append(ref(destination))
    diff.extend(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True),
                                   destination.read_text(encoding='utf8').splitlines(True),
                                   fromfile='before/' + name, tofile='after/' + name))
(OUT / 'owned-changes.diff').write_text(''.join(diff), encoding='utf8')
work['after'] = after
work['diff'] = [ref(OUT / 'owned-changes.diff')]
work['repair']['evidence'] = [ref(OUT / 'finding.json')]
work['status'] = 'VALIDATING'
work['before_snapshot_note'] = 'Original revision_before entries retained as recorded; actual before bytes and hashes in before[] are authoritative for scoped diff. No reconstructed pre-apply PASS claimed.'
work['outcomes'] = {name: {'status': 'PASSED', 'evidence': [ref(OUT / 'browser-final.json'), ref(OUT / 'frontend-final-18.tap')]} for name in work['required_outcomes']}
work['validations'] = {
    'frontend_transport_regressions': {'status': 'PASSED', 'cases': 18, 'evidence': [ref(OUT / 'frontend-final-18.tap')]},
    'typecheck': {'status': 'PASSED', 'evidence': [ref(OUT / 'typecheck-result.json')]},
    'isolated_browser_fault_contract': {'status': 'PASSED', 'cases': 4, 'evidence': [ref(OUT / 'browser-final.json')]},
}
work['validation_scope'] = 'Local Next16.2.11 frontend against isolated PREPARED306 backend; connection-reset requests intercepted before inference. No native Qwen/original-model/simulation/current-image/release PASS. Other3 browser cases include deterministic fixture behavior. Saved screenshot retains fields but error is below modal viewport; DOM assertions are alert evidence.'
write(OUT / 'workload.json', work)

spec = importlib.util.spec_from_file_location('delivery_identity', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
identity = {'at_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source, 'commit_id': commit, 'verification_sha256': verification}
previous = read(PARENT / 'waitress-candidate-input-identity.json')
previous_freeze = read(PARENT / 'waitress-validation-source-freeze.json')
if previous['source_sha256'] != source:
    write(PARENT / 'waitress-candidate-input-identity-before-network-ui.json', previous)
    write(PARENT / 'waitress-validation-source-freeze-before-network-ui.json', previous_freeze)
    # Read-only hypothetical identity: restore only the two changed application files.
    replacement = {str((ROOT / name).resolve()): (OUT / 'before' / name).read_bytes() for name in work['files_changed'] if name.endswith(('engineering-agent.ts', 'agent-chat-core.tsx'))}
    original = Path.read_bytes
    try:
        Path.read_bytes = lambda path: replacement.get(str(path.resolve()), None) if str(path.resolve()) in replacement else original(path)
        old_source = delivery.current_identity()[0]
    finally:
        Path.read_bytes = original
    assert old_source == previous['source_sha256'], (old_source, previous)
    write(OUT / 'source-transition.json', {'at_utc': identity['at_utc'], 'analysis_only': True, 'previous': previous, 'current': identity, 'hypothetical_identity_restoring_two_before_application_files': old_source, 'all_other_application_sources_identical_to_ed7': True, 'prior_server64_and_document452_are_revision_bound_historical_checks': True, 'new_native_image_and_full_release_still_required': True})
    write(PARENT / 'waitress-candidate-input-identity.json', identity)
    previous_freeze.update({name: sha(ROOT / name) for name in work['files_changed']})
    write(PARENT / 'waitress-validation-source-freeze.json', previous_freeze)
write(OUT / 'validated-local-identity.json', identity)
parent_work = read(PARENT / 'workload.json')
parent_work['current_source'] = identity
parent_work['additional_ui_repair'] = {'workload': str(OUT / 'workload.json'), 'local_cases': 18, 'browser_contract_cases': 4, 'typecheck': 'PASSED', 'production_deployed': False}
write(PARENT / 'workload.json', parent_work)
checkpoint = read(PARENT / 'checkpoint-awaiting-storage-authorization.json')
checkpoint['source'] = identity
checkpoint['at_utc'] = identity['at_utc']
checkpoint['tests']['frontend_reader'] = 18
checkpoint['tests']['isolated_browser_contract'] = 4
checkpoint['latest_ui_evidence'] = str(OUT / 'workload.json')
checkpoint['historical_scope_note'] = 'Server64 checks precede UI-only edits (ed7); document452 checks precede server option (19ec). Neither is a fresh full-suite PASS on current identity.'
write(PARENT / 'checkpoint-awaiting-storage-authorization.json', checkpoint)
report = f'''Die markierte rohe Transportfehlermeldung ist lokal korrigiert. Datei und Eingaben bleiben erhalten; ein bewusster Wiederholungsversuch sendet dieselbe vollständige Quelle mit neuer Request-ID. Fehlgeschlagene eigene Anfragen werden ausdrücklich abgebrochen. Spezifische Validierungsfehler bleiben erhalten.

18 Transportfälle, 4 isolierte Browserfälle und Typecheck bestanden. Browserquelle: synthetische 419634-Zeichen-Anlage; keine tatsächliche35-Profil-Qwen-Analyse. Kein neues Produktmodell, keine Simulation und kein Release-PASS aus diesen Checks. Originalauslöser des gemeldeten Netzwerkabbruchs bleibt ungeklärt; Dateigröße liegt innerhalb der geprüften produktiven Grenzen.

Aktuelle Source: {source}; HEAD: {commit}; Verification: {verification}.

Noch nicht produktiv. Gemeinsamer nächster normaler Kandidat und native Abbruch-/Originalprüfungen stehen aus. Imagebudget100/100; die bereits angefragte ausdrückliche Entfernung ausschließlich des gesicherten Test-Appcontainers306 und zugehörigen PREPARED-Images ist weiter offen. Keine Datenbanklöschung. Produktion bleibt Image3792. Alle15 Outcomes/15 Validations des Gesamtauftrags bleiben erhalten.
'''
(OUT / 'REPORT.md').write_text(report, encoding='utf8')
todo = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017/TODO.md'
old = todo.read_text(encoding='utf-8-sig')
marker = 'AKTUELL NETWORK-ERROR-REPAIR 2026-10-20'
if marker not in old:
    todo.write_text(marker + ':18 Transportfälle,4 isolierte Browserfälle und Typecheck bestanden. Fehlermeldung/gezielter Wiederholungsversuch erhalten vollständige Anlage und Eingaben; historischer Verbindungsabbruchauslöser bleibt unbekannt. Source' + source + ', Verification' + verification + '. Kein Original-/Simulations-/Release-/Produktiv-PASS. Weiter offen: exakte angefragte Speicherfreigabe für Test-App306+Image306 (Datenbank bleibt), neuer gemeinsamer normaler Kandidat, native Abbruchprüfung, beide Originale bis Simulation und vollständige produktive Auslieferung. Maßgeblich: integration/resume-20261020/document-network-error-repair/REPORT.md und document-stream-lifecycle-repair/checkpoint-awaiting-storage-authorization.json. Historie folgt.\n\n' + old, encoding='utf8')
print(json.dumps(identity))
